"""Detecção de ambientes: o espaço livre entre paredes, esquadrias e soleiras vira polígono.

Regra principal: a IA não mede. Área e perímetro saem desta geometria, com a escala calibrada
pelas cotas, e são conferidos contra a área escrita no rótulo do arquiteto.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import shapely
from shapely.geometry import Point, box

from .ingestao import Pagina
from .portas import encontrar_portas
from .esquadrias import ler_esquadrias

# Camadas que limitam um ambiente: paredes, linhas de piso/soleira (fecham os vãos de porta),
# janelas e portas de vidro/correr, e batentes. Folhas e arcos de porta (A-DOOR) ficam de fora.
CAMADAS_LIMITE = ("A-WALL", "A-FLOR", "A-GLAZ", "A-DOOR-GLAZ", "A-DOOR-FRAM")
# mobiliário fixo cujo contorno às vezes cobre a face da parede na exportação do CAD
CAMADAS_SOBREPOSTAS = ("Q-SPCQ", "P-SANR-FIXT")
# o que indica que um vão entre duas pontas de parede é porta ou janela (e não passagem livre)
EVID_PORTA = ("A-DOOR", "A-DOOR-FRAM", "A-DOOR-GLAZ", "A-FLOR")
EVID_JANELA = ("A-GLAZ",)
NUM = re.compile(r"^\d{1,4},\d{2}$")
# varanda: guarda-corpo = mureta baixa (paredes desenhadas com traço fino, abaixo do plano de corte)
# com corrimão por cima. Altura da mureta e topo da abertura medidos na fachada (premissas editáveis).
VARANDA = ("gourmet", "varanda", "sacada", "terraço", "terraco")
PREMISSA_VARANDA = {"peitoril_m": 0.60, "topo_m": 2.20,
                    "fonte": "Fachada Frontal (rua Ernesto), prancha 4: mureta até 0,60 m, gradil e corrimão até ~1,10 m, "
                             "abertura até 2,20 m. A planta indica guarda-corpo h=1,30 m: confirmar."}


def _orient(s, tol=0.05):
    if abs(s[1] - s[3]) < tol:
        return "h", s[1], min(s[0], s[2]), max(s[0], s[2])
    if abs(s[0] - s[2]) < tol:
        return "v", s[0], min(s[1], s[3]), max(s[1], s[3])
    return None


def reparar_faces(paredes, outros, tol=0.3):
    """Recupera trechos de face de parede escondidos sob bancadas/louças: aceita segmentos
    de mobiliário colineares com a parede e encostados numa ponta de parede já aceita."""
    pontas = {}
    def marca(o, c, a, b):
        for v in (a, b):
            pontas.setdefault((o, round(c / tol), round(v / tol)), True)
    def toca(o, c, v):
        kc, kv = round(c / tol), round(v / tol)
        return any((o, kc + i, kv + j) in pontas for i in (-1, 0, 1) for j in (-1, 0, 1))
    for s in paredes:
        if (oc := _orient(s)):
            marca(*oc)
    cand = [(s, oc) for s in outros if (oc := _orient(s))]
    aceitos = []
    for _ in range(6):
        novos = [(s, oc) for s, oc in cand if toca(oc[0], oc[1], oc[2]) or toca(oc[0], oc[1], oc[3])]
        if not novos:
            break
        ids = {id(s) for s, _ in novos}
        cand = [(s, oc) for s, oc in cand if id(s) not in ids]
        for s, oc in novos:
            marca(*oc)
            aceitos.append(s)
    return aceitos


def vaos(paredes, evid_porta, evid_janela, m_por_pt):
    """Fecha vãos de porta/janela: pares de pontas de parede ('tampas') frente a frente,
    com porta, batente, vidro ou soleira entre elas. Devolve ([(retângulo, "porta"|"janela")],
    [retângulos sem evidência]) — os sem evidência são passagens livres, usados só se preciso."""
    evidencias = list(evid_porta) + list(evid_janela)
    geo_p = shapely.linestrings(np.array(evid_porta, dtype=float).reshape(-1, 2, 2)) if evid_porta else None
    arv_p = shapely.STRtree(geo_p) if evid_porta else None
    tampas = []
    for s in paredes:
        oc = _orient(s)
        if oc and 0.08 <= (oc[3] - oc[2]) * m_por_pt <= 0.40:   # espessura de parede plausível
            tampas.append(oc)
    arv_par = shapely.STRtree(shapely.linestrings(np.array(paredes, dtype=float).reshape(-1, 2, 2)))
    geo_ev = shapely.linestrings(np.array(evidencias, dtype=float).reshape(-1, 2, 2)) if evidencias else None
    arv_ev = shapely.STRtree(geo_ev) if evidencias else None
    rets, livres = [], []
    for o in ("v", "h"):
        ts = sorted({t for t in tampas if t[0] == o}, key=lambda t: t[1])
        for i, a in enumerate(ts):
            for b in ts[i + 1:]:
                gap = (b[1] - a[1]) * m_por_pt
                if gap < 0.3:
                    continue
                if gap > 3.0:
                    break
                if abs(a[2] - b[2]) > 1 or abs(a[3] - b[3]) > 1:
                    continue
                lo, hi = max(a[2], b[2]), min(a[3], b[3])
                r = box(a[1], lo, b[1], hi) if o == "v" else box(lo, a[1], hi, b[1])
                miolo = r.buffer(-0.5, join_style="mitre")
                if miolo.is_empty or len(arv_par.query(miolo, predicate="intersects")):
                    break   # há parede no meio: não é vão (e não adianta olhar mais longe)
                # evidência: algo DENTRO do vão (batente, folha, vidro) ou uma soleira cobrindo
                # boa parte da boca do vão — não basta encostar numa quina
                if arv_ev is not None:
                    dentro = len(arv_ev.query(miolo, predicate="intersects")) > 0
                    R = r.buffer(0.5, join_style="mitre")
                    ext = sum(geo_ev[k].intersection(R).length for k in arv_ev.query(R, predicate="intersects"))
                    if dentro or ext >= 0.5 * (b[1] - a[1]):
                        porta = arv_p is not None and len(arv_p.query(R, predicate="intersects")) > 0
                        rets.append((r.bounds, "porta" if porta else "janela"))
                    else:
                        livres.append(r.bounds)
                break
    return rets, livres


@dataclass
class Rotulo:
    nome: str
    area_m2: float
    x: float
    y: float


@dataclass
class Ambiente:
    pagina: int
    vista: str
    nome: str
    area_rotulo_m2: float
    area_m2: float | None = None
    perimetro_m: float | None = None
    poligono: list[tuple[float, float]] = field(default_factory=list)   # em pt, coordenadas da prancha
    furos: list[list[tuple[float, float]]] = field(default_factory=list)
    rotulo_xy: tuple[float, float] = (0.0, 0.0)
    status: str = "sem_poligono"
    area_piso_m2: float | None = None     # área total do polígono (piso)
    area_teto_m2: float | None = None     # área coberta (teto/forro)
    perimetro_parede_m: float | None = None   # contorno junto a parede (inclui vãos de porta/janela)
    sem_parede_m: float | None = None         # contorno sem parede (guarda-corpo, lado aberto)
    vaos: list[str] = field(default_factory=list)   # ids dos vãos (portas/janelas) no contorno
    observacao: str = ""

    @property
    def divergencia_pct(self) -> float | None:
        if self.area_m2 is None or not self.area_rotulo_m2:
            return None
        return (self.area_m2 / self.area_rotulo_m2 - 1) * 100


def _na_caixa(x, y, c, folga=0.0):
    return c[0] - folga <= x <= c[2] + folga and c[1] - folga <= y <= c[3] + folga


def ler_rotulos(pag: Pagina, caixa) -> list[Rotulo]:
    """Rótulo de ambiente = linha 'NN,NN m²' com o nome do ambiente logo acima."""
    ws = [w for w in pag.palavras if _na_caixa(w[0], w[1], caixa, 5)]
    rotulos = []
    for w in ws:
        if w[4] not in ("m²", "m2"):
            continue
        num = [v for v in ws if (v[5], v[6]) == (w[5], w[6]) and NUM.match(v[4]) and v[2] <= w[0] + 1]
        if not num:
            continue
        n = max(num, key=lambda v: v[2])
        x0, x1, y0 = n[0], w[2], min(n[1], w[1])
        acima = [v for v in ws if -1 < y0 - v[3] < 6 and v[0] < x1 + 25 and v[2] > x0 - 25]
        if not acima:
            continue
        yl = max(v[3] for v in acima)
        nome = " ".join(v[4] for v in sorted((v for v in acima if abs(v[3] - yl) < 1), key=lambda v: v[0]))
        rotulos.append(Rotulo(nome, float(n[4].replace(",", ".")), (x0 + x1) / 2, (n[1] + n[3]) / 2))
    return rotulos


def _parte_coberta(pag: Pagina, poly, camada: str = "A-FLOR-OVHD"):
    """Parte do ambiente sob a projeção do pavimento superior (linha tracejada de projeção)."""
    inter = poly.buffer(-1)
    pts = [(s[2], s[3], s[4], s[5]) for s in pag.segmentos
           if s[0] == camada and inter.contains(Point(s[2], s[3]))]
    if len(pts) < 8:
        return None
    a = np.array(pts)
    xs, ys = np.r_[a[:, 0], a[:, 2]], np.r_[a[:, 1], a[:, 3]]
    return poly.intersection(box(xs.min(), ys.min(), xs.max(), ys.max()))


def _dir(linha):
    (x0, y0), (x1, y1) = linha.coords[0], linha.coords[-1]
    L = max(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5, 1e-9)
    return np.array([(x1 - x0) / L, (y1 - y0) / L])


def _extremos(a, b):
    """Pontas mais afastadas entre dois segmentos colineares."""
    pts = list(a.coords) + list(b.coords)
    return max(((p, q) for p in pts for q in pts), key=lambda pq: (pq[0][0] - pq[1][0]) ** 2 + (pq[0][1] - pq[1][1]) ** 2)


def _varandas(pag: Pagina, c, m_por_pt: float, rotulos) -> list[tuple]:
    """Trechos de guarda-corpo em mureta: corrimão entre duas faces de parede finas (traço de
    projeção, não de corte), a até 3 m de um rótulo de varanda. Devolve os retângulos do corpo da mureta."""
    alvo = [r for r in rotulos if any(k in r.nome.lower() for k in VARANDA)]
    if not alvo:
        return []
    na = lambda s: _na_caixa(s[2], s[3], c) or _na_caixa(s[4], s[5], c)
    finas = [(s, oc) for s in pag.segmentos if s[0] == "A-WALL" and s[1] < 0.8 and na(s) and (oc := _orient(s[2:6]))]
    res = set()
    for s in pag.segmentos:
        if s[0] != "Corrimão" or not na(s) or not (oc := _orient(s[2:6])):
            continue
        o, cc, a, b = oc
        if (b - a) * m_por_pt < 0.5:
            continue
        lados = [f for f in finas if f[1][0] == o and 0.2 < abs(f[1][1] - cc) <= 0.15 / m_por_pt and f[1][2] < b - 1 and f[1][3] > a + 1]
        menor = [f for f in lados if f[1][1] < cc]
        maior = [f for f in lados if f[1][1] > cc]
        if not menor or not maior:
            continue
        f1 = max(menor, key=lambda f: f[1][1])[1]
        f2 = min(maior, key=lambda f: f[1][1])[1]
        lo, hi = max(a, f1[2], f2[2]), min(b, f1[3], f2[3])
        if (hi - lo) * m_por_pt < 0.5:
            continue
        rect = (lo, f1[1], hi, f2[1]) if o == "h" else (f1[1], lo, f2[1], hi)
        cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
        if min(((r.x - cx) ** 2 + (r.y - cy) ** 2) ** 0.5 for r in alvo) * m_por_pt > 3.0:
            continue
        res.add(tuple(round(v, 2) for v in rect))
    return sorted(res)


def _regioes(segs, retangulos, c, m_por_pt, eps, faixa_fina_m):
    linhas = shapely.linestrings(np.array(segs, dtype=float).reshape(-1, 2, 2))
    tinta = shapely.union_all(list(shapely.buffer(linhas, eps, cap_style="square", join_style="mitre"))
                              + [box(*r).buffer(eps, join_style="mitre") for r in retangulos])
    espaco = box(*c).difference(tinta)
    # abertura morfológica: some com faixas finas (miolo de parede, frestas, recuos de vão)
    r = faixa_fina_m / 2 / m_por_pt
    espaco = espaco.buffer(-r, join_style="mitre").buffer(r, join_style="mitre")
    partes = list(getattr(espaco, "geoms", [espaco]))
    externo = [p.bounds[0] <= c[0] + 1 or p.bounds[1] <= c[1] + 1 or p.bounds[2] >= c[2] - 1 or p.bounds[3] >= c[3] - 1
               for p in partes]
    return partes, externo, shapely.STRtree(partes)


def _achar(regioes, x, y):
    partes, externo, arv = regioes
    idx = arv.query(Point(x, y), predicate="intersects")
    return (int(idx[0]), partes[idx[0]], externo[idx[0]]) if len(idx) else (None, None, None)


def detectar(pag: Pagina, caixa, m_por_pt: float, vista: str = "", eps: float = 0.3,
             camadas=CAMADAS_LIMITE, faixa_fina_m: float = 0.20, vaos_saida: list | None = None,
             contexto: dict | None = None) -> list[Ambiente]:
    """Mede os ambientes rotulados de uma vista.

    Duas leituras: (A) só paredes, esquadrias e linhas de apoio; (B) igual, mais as linhas de
    piso (A-FLOR). Linha de piso não separa cômodo (é troca de acabamento, borda de escada),
    então vale (A) quando ela dá uma região fechada com um único rótulo; se (A) vaza para fora
    ou junta rótulos, usa (B). Se ainda houver dois rótulos na mesma região, fecha também as
    passagens sem porta entre eles.
    faixa_fina_m: espaços mais estreitos que isso (miolo de parede, fresta de batente,
    recuo de janela) não são ambiente e são descartados."""
    c = (caixa[0] - 20, caixa[1] - 20, caixa[2] + 20, caixa[3] + 20)
    na = lambda s: _na_caixa(s[2], s[3], c) or _na_caixa(s[4], s[5], c)
    paredes = [s[2:6] for s in pag.segmentos if s[0] == "A-WALL" and na(s)]
    sob = [s[2:6] for s in pag.segmentos if s[0] in CAMADAS_SOBREPOSTAS and na(s)]
    faces = reparar_faces(paredes, sob)
    # linhas de apoio: folha de cada porta na posição fechada, um pouco prolongada nas pontas
    apoio = []
    portas = encontrar_portas(pag, c)
    for p in portas:
        (x0, y0), (x1, y1) = p.dobradica, p.fechada
        L = max(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5, 1e-6)
        ux, uy = (x1 - x0) / L * 1.5, (y1 - y0) / L * 1.5
        apoio.append((x0 - ux, y0 - uy, x1 + ux, y1 + uy))
    evid_p = [s[2:6] for s in pag.segmentos if s[0] in EVID_PORTA and na(s)] + apoio
    evid_j = [s[2:6] for s in pag.segmentos if s[0] in EVID_JANELA and na(s)]
    vaos_tipados, livres = vaos(paredes + faces, evid_p, evid_j, m_por_pt)
    rets = [b for b, _ in vaos_tipados]
    # registro dos vãos (para quantitativos: rodapé, desconto de parede, soleiras)
    reg_vaos = []
    for k, (b, tipo) in enumerate(vaos_tipados):
        dx, dy = b[2] - b[0], b[3] - b[1]
        reg_vaos.append({"id": f"{vista or pag.numero}-V{k + 1:03d}", "tipo": tipo,
                         "largura_m": round(max(dx, dy) * m_por_pt, 3), "espessura_m": round(min(dx, dy) * m_por_pt, 3),
                         "centro": [round((b[0] + b[2]) / 2, 2), round((b[1] + b[3]) / 2, 2)],
                         "retangulo": [round(v, 2) for v in b], "ambientes": []})
    buf_vaos = [box(*b).buffer(2.0, join_style="mitre") for b in rets]
    # vãos "por vidro": esquadria desenhada sem interromper a parede no plano de corte
    # (janela alta, como basculante de banheiro) ou porta de correr encostada em parede
    # perpendicular. Só vira vão se houver etiqueta L x H de mesma largura por perto.
    vidro = [s[2:6] for s in pag.segmentos if s[0] in ("A-GLAZ", "A-DOOR-GLAZ", "A-DOOR-FRAM") and na(s)]
    if vidro:
        etiquetas = ler_esquadrias(pag, caixa)
        arv_r = shapely.STRtree([box(*b) for b in rets]) if rets else None
        # folhas de porta de correr e batentes ficam separados por frestas: agrupa com folga de ~5 cm
        folga = 0.025 / m_por_pt
        nuvem = shapely.union_all(shapely.buffer(shapely.linestrings(np.array(vidro, dtype=float).reshape(-1, 2, 2)), folga))
        usadas = set()
        so_vidro = shapely.STRtree(shapely.linestrings(np.array(
            [s[2:6] for s in pag.segmentos if s[0] in ("A-GLAZ", "A-DOOR-GLAZ") and na(s)] or [(0, 0, 0, 1e-3)], dtype=float).reshape(-1, 2, 2)))
        for g in getattr(nuvem, "geoms", [nuvem]):
            if arv_r is not None and len(arv_r.query(g, predicate="intersects")):
                continue
            if not len(so_vidro.query(g, predicate="intersects")):
                continue   # só batente/folha, sem vidro: não é esquadria de vidro
            x0, y0, x1, y1 = g.bounds
            x0, y0, x1, y1 = x0 + folga, y0 + folga, x1 - folga, y1 - folga
            larg = max(x1 - x0, y1 - y0) * m_por_pt
            if larg < 0.3:
                continue
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            cands = [(((e.x - cx) ** 2 + (e.y - cy) ** 2) ** 0.5 * m_por_pt, i) for i, e in enumerate(etiquetas)
                     if i not in usadas and abs(e.largura_m - larg) <= 0.10]
            cands = [c for c in cands if c[0] <= 3.0]
            if not cands:
                continue
            _, i = min(cands)
            usadas.add(i)
            reg_vaos.append({"id": f"{vista or pag.numero}-V{len(reg_vaos) + 1:03d}", "tipo": etiquetas[i].tipo,
                             "largura_m": round(larg, 3), "espessura_m": round(min(x1 - x0, y1 - y0) * m_por_pt, 3),
                             "centro": [round(cx, 2), round(cy, 2)], "retangulo": [round(v, 2) for v in (x0, y0, x1, y1)],
                             "ambientes": [], "por_vidro": True})
            # alcança os cômodos dos dois lados (até 20 cm), mas não passa das pontas do vão
            r_ = 0.20 / m_por_pt
            buf_vaos.append(box(x0 - 1, y0 - r_, x1 + 1, y1 + r_) if (x1 - x0) >= (y1 - y0)
                            else box(x0 - r_, y0 - 1, x1 + r_, y1 + 1))
    # vãos "por folha": porta de giro cujo vão não fechou por pontas de parede (ex.: porta
    # de duas folhas encostada em parede perpendicular). Folhas colineares e vizinhas = um vão.
    soltas = []
    arv_b = shapely.STRtree(buf_vaos) if buf_vaos else None
    for p in portas:
        seg = shapely.LineString([p.dobradica, p.fechada])
        if arv_b is not None and len(arv_b.query(seg.centroid, predicate="intersects")):
            continue
        soltas.append(seg)
    grupos = []
    for seg in soltas:
        for g in grupos:
            if g.distance(seg) < 3 and abs(abs(np.dot(_dir(g), _dir(seg))) - 1) < 1e-3:
                grupos[grupos.index(g)] = shapely.LineString(_extremos(g, seg))
                break
        else:
            grupos.append(seg)
    etiq = None
    for g in grupos:
        larg = g.length * m_por_pt
        if larg < 0.5:
            continue
        (x0, y0), (x1, y1) = g.coords[0], g.coords[-1]
        bx = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        cx, cy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
        if etiq is None:
            etiq = ler_esquadrias(pag, caixa)
        cands = [(((e.x - cx) ** 2 + (e.y - cy) ** 2) ** 0.5 * m_por_pt, e) for e in etiq
                 if e.tipo == "porta" and abs(e.largura_m - larg) <= 0.10]
        cands = [c_ for c_ in cands if c_[0] <= 3.0]
        reg_vaos.append({"id": f"{vista or pag.numero}-V{len(reg_vaos) + 1:03d}", "tipo": "porta",
                         "largura_m": round(min(cands, key=lambda c_: c_[0])[1].largura_m if cands else larg, 3),
                         "espessura_m": None, "centro": [round(cx, 2), round(cy, 2)],
                         "retangulo": [round(v, 2) for v in bx], "ambientes": [], "por_folha": True})
        r_ = 0.20 / m_por_pt
        buf_vaos.append(box(bx[0] - 1, bx[1] - r_, bx[2] + 1, bx[3] + r_) if (bx[2] - bx[0]) >= (bx[3] - bx[1])
                        else box(bx[0] - r_, bx[1] - 1, bx[2] + r_, bx[3] + 1))
    tinta_parede = shapely.union_all(shapely.buffer(
        shapely.linestrings(np.array(paredes + faces, dtype=float).reshape(-1, 2, 2)), 1.0, cap_style="flat"))
    base = [s[2:6] for s in pag.segmentos if s[0] in camadas and s[0] != "A-FLOR" and na(s)] + faces + apoio
    piso = [s[2:6] for s in pag.segmentos if s[0] == "A-FLOR" and na(s)]
    leitura_a = _regioes(base, rets, c, m_por_pt, eps, faixa_fina_m)
    leitura_b = _regioes(base + piso, rets, c, m_por_pt, eps, faixa_fina_m)
    leitura_c = None   # B + passagens livres fechadas (só se precisar)

    rotulos = ler_rotulos(pag, caixa)
    def contagem(reg):
        cont = {}
        for r in rotulos:
            i, _, _ = _achar(reg, r.x, r.y)
            cont[i] = cont.get(i, 0) + 1
        return cont
    cont_a, cont_b = contagem(leitura_a), contagem(leitura_b)

    # vãos de varanda: trecho de mureta (faces finas + corrimão) junto a um ambiente de varanda
    for rect in _varandas(pag, c, m_por_pt, rotulos):
        x0, y0, x1, y1 = rect
        reg_vaos.append({"id": f"{vista or pag.numero}-V{len(reg_vaos) + 1:03d}", "tipo": "varanda",
                         "largura_m": round(max(x1 - x0, y1 - y0) * m_por_pt, 3), "espessura_m": round(min(x1 - x0, y1 - y0) * m_por_pt, 3),
                         "centro": [round((x0 + x1) / 2, 2), round((y0 + y1) / 2, 2)], "retangulo": [round(v, 2) for v in rect],
                         "ambientes": [], "peitoril_m": PREMISSA_VARANDA["peitoril_m"],
                         "altura_m": round(PREMISSA_VARANDA["topo_m"] - PREMISSA_VARANDA["peitoril_m"], 2),
                         "etiqueta": True, "por_guarda_corpo": True})
        buf_vaos.append(box(*rect).buffer(2.0, join_style="mitre"))
    if vaos_saida is not None:
        vaos_saida.extend(reg_vaos)
    arv_vaos = shapely.STRtree(buf_vaos) if buf_vaos else None

    ambientes = []
    for r in rotulos:
        amb = Ambiente(pag.numero, vista, r.nome, r.area_m2, rotulo_xy=(r.x, r.y))
        i, poly, ext = _achar(leitura_a, r.x, r.y)
        if poly is not None and not ext and cont_a.get(i, 0) == 1:
            # junta só as regiões da leitura B que estão dentro desta região A
            # (une patamar + lances de escada; descarta faixas finas como a do guarda-corpo)
            pb, _, arv_b = leitura_b
            dentro = [pb[k] for k in arv_b.query(poly, predicate="intersects")
                      if pb[k].intersection(poly).area > 0.9 * pb[k].area]
            if dentro:
                poly = shapely.union_all([d.buffer(eps * 1.2, join_style="mitre") for d in dentro]).buffer(-eps * 0.2, join_style="mitre")
                if poly.geom_type != "Polygon":
                    poly = max(poly.geoms, key=lambda g: g.area)
                poly = poly.buffer(-eps, join_style="mitre")
        else:
            i, poly, ext = _achar(leitura_b, r.x, r.y)
            if poly is not None and not ext and cont_b.get(i, 0) > 1:
                if leitura_c is None:
                    leitura_c = _regioes(base + piso, rets + livres, c, m_por_pt, eps, faixa_fina_m)
                    cont_c = contagem(leitura_c)
                i, poly, ext = _achar(leitura_c, r.x, r.y)
                if poly is not None and cont_c.get(i, 0) > 1:
                    amb.status = "rotulos_juntos"
        if poly is not None and not ext:
            poly = poly.buffer(eps, join_style="mitre")
            amb.area_m2 = poly.area * m_por_pt ** 2
            amb.poligono = [(round(x, 2), round(y, 2)) for x, y in poly.exterior.coords]
            amb.furos = [[(round(x, 2), round(y, 2)) for x, y in h.coords] for h in poly.interiors]
            amb.area_piso_m2 = amb.area_teto_m2 = amb.area_m2
            # contorno: junto a parede, em vão (porta/janela) ou aberto
            borda = poly.boundary
            amb.perimetro_m = borda.length * m_por_pt
            adj = []
            if arv_vaos is not None:
                for k in arv_vaos.query(borda, predicate="intersects"):
                    if borda.intersection(buf_vaos[k]).length * m_por_pt >= 0.3:
                        adj.append(int(k))
            em_vao = shapely.union_all([buf_vaos[k] for k in adj]) if adj else None
            L_vao = borda.intersection(em_vao).length if em_vao is not None else 0.0
            resto = borda.difference(em_vao) if em_vao is not None else borda
            L_par = resto.intersection(tinta_parede).length
            amb.perimetro_parede_m = (L_vao + L_par) * m_por_pt
            amb.sem_parede_m = max(borda.length - L_vao - L_par, 0.0) * m_por_pt
            amb.vaos = [reg_vaos[k]["id"] for k in adj]
            for k in adj:
                reg_vaos[k]["ambientes"].append(r.nome)
            if "coberta" in r.nome.lower():
                cob = _parte_coberta(pag, poly)
                if cob is not None:
                    amb.area_m2 = amb.area_teto_m2 = cob.area * m_por_pt ** 2
                    amb.observacao = (f"Rótulo mede só a parte coberta (sob a projeção do pavimento-tipo). "
                                      f"Piso total da garagem: {amb.area_piso_m2:.2f} m².")
            if amb.status != "rotulos_juntos":
                d = abs(amb.divergencia_pct)
                amb.status = "ok" if d <= 2 else ("conferir" if d <= 10 else "divergente")
        ambientes.append(amb)
    if contexto is not None:
        # geometria de apoio para o modelo de paredes: tudo que não é espaço livre é parede/vão
        contexto.update(caixa=c, espacos=leitura_a[0], externo=leitura_a[1], vaos=reg_vaos)
    return ambientes
