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

# Camadas que limitam um ambiente: paredes, linhas de piso/soleira (fecham os vãos de porta),
# janelas e portas de vidro/correr, e batentes. Folhas e arcos de porta (A-DOOR) ficam de fora.
CAMADAS_LIMITE = ("A-WALL", "A-FLOR", "A-GLAZ", "A-DOOR-GLAZ", "A-DOOR-FRAM")
# mobiliário fixo cujo contorno às vezes cobre a face da parede na exportação do CAD
CAMADAS_SOBREPOSTAS = ("Q-SPCQ", "P-SANR-FIXT")
# o que indica que um vão entre duas pontas de parede é porta ou janela (e não passagem livre)
CAMADAS_VAO = ("A-DOOR", "A-DOOR-FRAM", "A-DOOR-GLAZ", "A-GLAZ", "A-FLOR")
NUM = re.compile(r"^\d{1,4},\d{2}$")


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


def vaos(paredes, evidencias, m_por_pt):
    """Fecha vãos de porta/janela: pares de pontas de parede ('tampas') frente a frente,
    com porta, batente, vidro ou soleira entre elas. Devolve (retângulos com evidência,
    retângulos sem evidência) — os sem evidência são passagens livres, usados só se preciso."""
    tampas = []
    for s in paredes:
        oc = _orient(s)
        if oc and 0.05 <= (oc[3] - oc[2]) * m_por_pt <= 0.40:
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
                        rets.append(r.bounds)
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
             camadas=CAMADAS_LIMITE, faixa_fina_m: float = 0.20) -> list[Ambiente]:
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
    for p in encontrar_portas(pag, c):
        (x0, y0), (x1, y1) = p.dobradica, p.fechada
        L = max(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5, 1e-6)
        ux, uy = (x1 - x0) / L * 1.5, (y1 - y0) / L * 1.5
        apoio.append((x0 - ux, y0 - uy, x1 + ux, y1 + uy))
    evid = [s[2:6] for s in pag.segmentos if s[0] in CAMADAS_VAO and na(s)] + apoio
    rets, livres = vaos(paredes + faces, evid, m_por_pt)
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
            amb.perimetro_m = poly.exterior.length * m_por_pt
            amb.poligono = [(round(x, 2), round(y, 2)) for x, y in poly.exterior.coords]
            amb.furos = [[(round(x, 2), round(y, 2)) for x, y in h.coords] for h in poly.interiors]
            amb.area_piso_m2 = amb.area_m2
            if "coberta" in r.nome.lower():
                cob = _parte_coberta(pag, poly)
                if cob is not None:
                    amb.area_m2 = cob.area * m_por_pt ** 2
                    amb.observacao = (f"Rótulo mede só a parte coberta (sob a projeção do pavimento-tipo). "
                                      f"Piso total da garagem: {amb.area_piso_m2:.2f} m².")
            if amb.status != "rotulos_juntos":
                d = abs(amb.divergencia_pct)
                amb.status = "ok" if d <= 2 else ("conferir" if d <= 10 else "divergente")
        ambientes.append(amb)
    return ambientes
