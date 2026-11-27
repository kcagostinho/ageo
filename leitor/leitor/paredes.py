"""Modelo de paredes ("BIM de alvenaria"): cada parede vira um objeto com eixo, espessura,
encontros, vãos e o que há de cada lado.

Como extrai:
1. Região de parede = tudo da planta que não é espaço livre (ambientes, shafts, exterior).
   Inclui o corpo das paredes e os vãos de porta/janela já fechados na Fase 1.
2. Essa região é rasterizada; em cada coluna (e em cada linha) da imagem, um trecho contínuo de
   parede com 7 a 45 cm é a espessura de uma parede horizontal (ou vertical). O meio do trecho é o eixo.
3. Pontos de eixo vizinhos com a mesma espessura viram segmentos; segmentos são prolongados até
   o eixo da parede perpendicular → encontros em L, T e X.
4. Vãos (portas/janelas) são projetados no eixo; os lados da parede são lidos nos polígonos dos
   ambientes (ou exterior).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import shapely
from PIL import Image, ImageDraw
from shapely.geometry import Point, box

RES = 0.25         # pt por pixel na rasterização
TINTA = 0.6        # pt: espessura do traço das faces incluída na região de parede (2 × 0,3)
NUCLEO = ("hall", "escada", "elevador", "circula")


@dataclass
class Segmento:
    o: str            # "h" (parede horizontal) ou "v"
    c: float          # coordenada do eixo (y para "h", x para "v"), em pt
    a: float          # início ao longo do eixo, em pt
    b: float          # fim
    t: float          # espessura, em pt


def _raster(geom, x0, y0, W, H):
    total = np.zeros((H, W), dtype=bool)
    f = lambda pts: [((x - x0) / RES, (y - y0) / RES) for x, y in pts]
    for poly in getattr(geom, "geoms", [geom]):
        if poly.is_empty or poly.geom_type != "Polygon":
            continue
        img = Image.new("1", (W, H), 0)
        dr = ImageDraw.Draw(img)
        dr.polygon(f(poly.exterior.coords), fill=1)
        for h in poly.interiors:
            dr.polygon(f(h.coords), fill=0)
        total |= np.array(img, dtype=bool)
    return total


def _corridas(mask):
    """Corridas de True ao longo do eixo 0 (linhas da matriz) para cada coluna: (col, ini, fim)."""
    m = mask.astype(np.int8)
    d = np.diff(np.pad(m, ((1, 1), (0, 0))), axis=0)
    ini = np.argwhere(d.T == 1)    # (col, linha) ordenado por coluna
    fim = np.argwhere(d.T == -1)
    return ini[:, 0], ini[:, 1], fim[:, 1]


def _segmentos(mask, x0, y0, m_por_pt, t_min=0.07, t_max=0.45):
    segs = []
    for o, M in (("h", mask), ("v", mask.T)):
        col, i0, i1 = _corridas(M)
        t = (i1 - i0) * RES * m_por_pt
        ok = (t >= t_min) & (t <= t_max)
        col, i0, i1 = col[ok], i0[ok], i1[ok]
        meio = (i0 + i1)  # em meio-pixels (inteiro)
        tl = i1 - i0
        ordem = np.lexsort((col, tl, meio))
        col, meio, tl = col[ordem], meio[ordem], tl[ordem]
        if not len(col):
            continue
        quebra = np.r_[True, (np.diff(meio) != 0) | (np.diff(tl) != 0) | (np.diff(col) > 2)]
        grupos = np.cumsum(quebra) - 1
        for g in range(grupos[-1] + 1):
            sel = grupos == g
            cc = col[sel]
            if o == "h":
                cy = y0 + meio[sel][0] / 2 * RES
                a, b = x0 + cc.min() * RES, x0 + (cc.max() + 1) * RES
            else:
                cy = x0 + meio[sel][0] / 2 * RES
                a, b = y0 + cc.min() * RES, y0 + (cc.max() + 1) * RES
            segs.append(Segmento(o, cy, a, b, tl[sel][0] * RES))
    return segs


def _juntar(segs, tol_c=2.0, tol_t=2.0, folga=3.0):
    """Une segmentos colineares (mesma linha de eixo e espessura parecida) que se tocam."""
    out = []
    for o in ("h", "v"):
        ss = sorted((s for s in segs if s.o == o), key=lambda s: (round(s.c / tol_c), s.a))
        usados = [False] * len(ss)
        for i, s in enumerate(ss):
            if usados[i]:
                continue
            cur = Segmento(s.o, s.c, s.a, s.b, s.t)
            peso = s.b - s.a
            mudou = True
            while mudou:
                mudou = False
                for j, r in enumerate(ss):
                    if usados[j] or j == i:
                        continue
                    if abs(r.c - cur.c) <= tol_c and abs(r.t - cur.t) <= tol_t and r.a <= cur.b + folga and r.b >= cur.a - folga:
                        L = r.b - r.a
                        cur.c = (cur.c * peso + r.c * L) / (peso + L)
                        cur.t = (cur.t * peso + r.t * L) / (peso + L)
                        cur.a, cur.b = min(cur.a, r.a), max(cur.b, r.b)
                        peso += L
                        usados[j] = mudou = True
            usados[i] = True
            out.append(cur)
    return out


def _limpar(segs, m_por_pt, min_m=0.15):
    """Remove pedaços curtos e 'sombras' (trecho paralelo e colado a uma parede maior,
    como caixa de janela saliente)."""
    segs = [s for s in segs if (s.b - s.a) * m_por_pt >= min_m]
    res = []
    for s in segs:
        L = s.b - s.a
        sombra = any(r is not s and r.o == s.o and (r.b - r.a) > L and abs(r.c - s.c) < (r.t + s.t) / 2 + 1
                     and r.a <= s.a + 1 and r.b >= s.b - 1 for r in segs)
        if not sombra:
            res.append(s)
    return res


def _prolongar(segs):
    """Leva cada ponta de eixo até o eixo da parede perpendicular que a recebe."""
    for s in segs:
        for lado in ("a", "b"):
            p = getattr(s, lado)
            melhor = None
            for r in segs:
                if r.o == s.o:
                    continue
                # r é perpendicular: sua coordenada de eixo r.c corre ao longo de s
                if not (r.a - s.t / 2 - 2 <= s.c <= r.b + s.t / 2 + 2):
                    continue
                d = abs(r.c - p)
                if d <= r.t / 2 + 2.5 and (melhor is None or d < melhor[0]):
                    melhor = (d, r.c)
            if melhor:
                setattr(s, lado, melhor[1])
    # e as perpendiculares que pararam antes do eixo de s (canto em L): a outra também se estende
    return segs


def _nominal(t_m: float) -> float:
    """Espessura medida → nominal: encosta no múltiplo de 5 cm mais próximo se estiver a até 1,2 cm."""
    n = round(t_m / 0.05) * 0.05
    return round(n if abs(n - t_m) <= 0.012 else round(t_m / 0.01) * 0.01, 3)


@dataclass
class Parede:
    id: str
    pavimento: str
    o: str
    eixo: tuple[float, float, float, float]
    comprimento_m: float
    espessura_m: float
    lado_a: list[str] = field(default_factory=list)   # acima/esquerda
    lado_b: list[str] = field(default_factory=list)   # abaixo/direita
    fachada: bool = False
    encontros: dict = field(default_factory=dict)     # {"a": "L"|"T"|"X"|"livre"|"passante", "b": ...}
    vaos: list[dict] = field(default_factory=list)
    tipo: str = "a definir"
    motivo: str = ""


def _no(segs, s, pos):
    """Tipo de encontro numa ponta:
    L = canto; T = esta parede morre no meio de outra; T-passante = esta parede continua e outra
    chega nela; X = cruzamento; continua = só emenda colinear; livre = ponta solta."""
    x, y = (pos, s.c) if s.o == "h" else (s.c, pos)
    chegam, passam, colinear = 0, 0, 0
    for r in segs:
        if r is s:
            continue
        rx = (r.a, r.c, r.b, r.c) if r.o == "h" else (r.c, r.a, r.c, r.b)
        d = Point(x, y).distance(shapely.LineString([(rx[0], rx[1]), (rx[2], rx[3])]))
        if d > max(r.t, s.t) / 2 + 1:
            continue
        tol = max(r.t, s.t) / 2 + 1
        ponta = (abs((x if r.o == "h" else y) - r.a) < tol) or (abs((x if r.o == "h" else y) - r.b) < tol)
        if r.o == s.o:
            colinear += 1
        elif ponta:
            chegam += 1
        else:
            passam += 1
    if passam:
        return "X" if colinear else "T"
    if colinear and chegam:
        return "X" if chegam >= 2 else "T-passante"
    if chegam >= 2:
        return "T"
    if chegam == 1:
        return "L"
    return "continua" if colinear else "livre"


def extrair(contexto: dict, ambientes: list[dict], pavimento: str, m_por_pt: float, prefixo: str) -> list[Parede]:
    c = contexto["caixa"]
    espacos = shapely.union_all(contexto["espacos"])
    parede = box(*c).difference(espacos)
    x0, y0 = c[0], c[1]
    W, H = int(math.ceil((c[2] - c[0]) / RES)) + 1, int(math.ceil((c[3] - c[1]) / RES)) + 1
    mask = _raster(parede, x0, y0, W, H)
    segs = _limpar(_juntar(_segmentos(mask, x0, y0, m_por_pt), tol_t=0.035 / m_por_pt), m_por_pt)
    for s_ in segs:
        s_.t = max(s_.t - TINTA, 0.01)
    # trecho de parede sobre porta de correr / vão de vidro sem parede desenhada no corte
    for v in contexto["vaos"]:
        if not v.get("por_vidro") or v["tipo"] != "porta":
            continue
        r = v["retangulo"]
        o = "h" if (r[2] - r[0]) >= (r[3] - r[1]) else "v"
        cc = (r[1] + r[3]) / 2 if o == "h" else (r[0] + r[2]) / 2
        a, b = (r[0], r[2]) if o == "h" else (r[1], r[3])
        if not any(x.o == o and abs(x.c - cc) < x.t and x.a <= a + 2 and x.b >= b - 2 for x in segs):
            seg = Segmento(o, cc, a, b, 0.15 / m_por_pt)
            seg.sobre_vao = True
            segs.append(seg)
    segs = _prolongar(segs)

    # ambientes da vista, para saber o que há de cada lado
    polys = [(a, shapely.Polygon(a["poligono"], a.get("furos") or [])) for a in ambientes if a.get("poligono")]
    arv = shapely.STRtree([p for _, p in polys]) if polys else None
    # exterior: o que encosta na borda da vista, ou espaço grande sem rótulo (terreno cercado por muros)
    rep_pts = [Point(*(a.get("rotulo_xy") or shapely.Polygon(a["poligono"]).representative_point().coords[0]))
               for a in ambientes if a.get("poligono")]
    ext_parts = [p for p, e in zip(contexto["espacos"], contexto["externo"])
                 if e or (p.area * m_por_pt ** 2 > 20 and not any(p.contains(q) for q in rep_pts))]
    exterior = shapely.union_all(ext_parts) if ext_parts else None

    def o_que_ha(x, y):
        pt = Point(x, y)
        if arv is not None:
            for k in arv.query(pt, predicate="intersects"):
                return polys[k][0]["_rotulo"]
        if exterior is not None and exterior.intersects(pt):
            return "exterior"
        return "—"

    paredes = []
    for n, s in enumerate(sorted(segs, key=lambda s: (s.o, s.c, s.a)), 1):
        L = s.b - s.a
        off = s.t / 2 + 0.12 / m_por_pt
        lados = {"a": set(), "b": set()}
        k = max(int(L * m_por_pt / 0.4), 2)
        for i in range(k + 1):
            u = s.a + (i + 0.5) / (k + 1) * L
            if s.o == "h":
                lados["a"].add(o_que_ha(u, s.c - off)); lados["b"].add(o_que_ha(u, s.c + off))
            else:
                lados["a"].add(o_que_ha(s.c - off, u)); lados["b"].add(o_que_ha(s.c + off, u))
        eixo = (s.a, s.c, s.b, s.c) if s.o == "h" else (s.c, s.a, s.c, s.b)
        pw = Parede(f"{prefixo}-P{n:03d}", pavimento, s.o, tuple(round(v, 2) for v in eixo),
                    round(L * m_por_pt, 3), _nominal(s.t * m_por_pt),
                    sorted(lados["a"] - {"—"}) or ["—"], sorted(lados["b"] - {"—"}) or ["—"])
        pw.fachada = "exterior" in lados["a"] or "exterior" in lados["b"]
        if getattr(s, "sobre_vao", False):
            pw.motivo = "trecho sobre porta de correr (espessura assumida 15 cm)"
        pw.encontros = {"a": _no(segs, s, s.a), "b": _no(segs, s, s.b)}
        pw._seg = s
        paredes.append(pw)

    # vãos: projeta cada porta/janela no eixo paralelo mais próximo
    for v in contexto["vaos"]:
        r = v["retangulo"]
        o = "h" if (r[2] - r[0]) >= (r[3] - r[1]) else "v"
        cx, cy = v["centro"]
        cand = []
        for pw in paredes:
            s = pw._seg
            if s.o != o:
                continue
            d = abs((cy if o == "h" else cx) - s.c)
            u = cx if o == "h" else cy
            if d <= s.t / 2 + 0.30 / m_por_pt and s.a - 2 <= u <= s.b + 2:
                cand.append((d, pw))
        if not cand:
            continue
        _, pw = min(cand, key=lambda t: t[0])
        s = pw._seg
        u0, u1 = (r[0], r[2]) if o == "h" else (r[1], r[3])
        pw.vaos.append({"vao": v["id"], "tipo": v["tipo"], "inicio_m": round((u0 - s.a) * m_por_pt, 3),
                        "largura_m": v["largura_m"], "altura_m": v.get("altura_m"), "peitoril_m": v.get("peitoril_m")})
    for pw in paredes:
        pw.vaos.sort(key=lambda x: x["inicio_m"])
        del pw._seg
    return paredes


def classificar(paredes: list[Parede], aptos: dict[str, str], tem_unidades: bool = True):
    """Regra inicial (o projeto estrutural manda):
    - espessura ≥ 19 cm → concreto (pilar/arrimo)
    - nenhum lado é ambiente da edificação → muro (fora da edificação)
    - pavimento sem unidades (térreo/subsolo sob a transição) → a definir
    - fachada, divisa entre unidades ou núcleo (hall/escada/elevador) → estrutural
    - os dois lados na mesma unidade → vedação"""
    for pw in paredes:
        extra = pw.motivo if pw.motivo.startswith("trecho") else ""
        lados = set(pw.lado_a) | set(pw.lado_b)
        nomes = {l.split(" · ")[-1].lower() for l in lados}
        unidades = {aptos.get(l) for l in lados if aptos.get(l)}
        if pw.espessura_m >= 0.19:
            pw.tipo, pw.motivo = "concreto", "espessura ≥ 19 cm (pilar ou arrimo)"
        elif not (lados - {"exterior", "—"}):
            pw.tipo, pw.motivo = "muro", "nenhum lado é ambiente da edificação"
        elif not tem_unidades:
            pw.tipo, pw.motivo = "a definir", "pavimento sob a transição: estrutura a confirmar com o engenheiro"
        elif pw.fachada:
            pw.tipo, pw.motivo = "estrutural", "fachada"
        elif any(n.startswith(NUCLEO) for n in nomes):
            pw.tipo, pw.motivo = "estrutural", "núcleo (hall/escada/elevador)"
        elif len(unidades) >= 2:
            pw.tipo, pw.motivo = "estrutural", "divisa entre unidades"
        elif len(unidades) == 1 and "—" not in lados:
            pw.tipo, pw.motivo = "vedação", "interna da unidade"
        else:
            pw.tipo, pw.motivo = "a definir", "lado sem ambiente identificado"
        if extra:
            pw.motivo = f"{pw.motivo}; {extra}"


def agrupar_unidades(ambientes: list[dict], vaos: list[dict], m_por_pt: float) -> dict[str, str]:
    """Unidades (apartamentos) = ambientes ligados por portas, sem passar pelo núcleo."""
    idx = {a["_rotulo"]: i for i, a in enumerate(ambientes) if a.get("poligono")}
    polys = {a["_rotulo"]: shapely.Polygon(a["poligono"]) for a in ambientes if a.get("poligono")}
    pai = {k: k for k in idx}
    def raiz(k):
        while pai[k] != k:
            pai[k] = pai[pai[k]]
            k = pai[k]
        return k
    nucleo = {k for k in idx if k.split(" · ")[-1].lower().startswith(NUCLEO)}
    for v in vaos:
        if v["tipo"] != "porta":
            continue
        r = box(*v["retangulo"]).buffer(0.22 / m_por_pt)
        viz = [k for k, p in polys.items() if k not in nucleo and p.intersects(r)]
        for a, b in zip(viz, viz[1:]):
            pai[raiz(a)] = raiz(b)
    grupos: dict[str, list[str]] = {}
    for k in idx:
        if k in nucleo:
            continue
        grupos.setdefault(raiz(k), []).append(k)
    # só conta como unidade o grupo que tem sala ou quarto
    unidades = [g for g in grupos.values() if any(("sala" in x.lower() or "quarto" in x.lower()) for x in g)]
    unidades.sort(key=lambda g: (round(min(polys[x].centroid.y for x in g) / 200), min(polys[x].centroid.x for x in g)))
    out = {}
    for n, g in enumerate(unidades, 1):
        for x in g:
            out[x] = f"Unidade {n}"
    return out
