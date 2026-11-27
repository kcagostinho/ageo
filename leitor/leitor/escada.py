"""Escadas: degraus, patamares e corrimãos lidos da planta, para o 3D.

O desenho de cada pavimento traz a numeração dos degraus (1, 2, … N) no lance que sobe dele
("Acima"); o último número é a chegada no andar de cima. A leitura:
  1. números inteiros dentro do polígono do ambiente "Escada…" = centro de cada piso;
  2. números seguidos e alinhados formam um lance (passo = profundidade do piso);
  3. largura do lance: do eixo até a parede (raio no polígono do ambiente) e, do lado do
     outro lance, até a metade da distância entre os eixos;
  4. o último número de um lance seguido por outro lance vira patamar: começa na borda de
     trás desse piso e vai até a parede, na largura toda da escada;
  5. o número N (o maior) é o piso do andar de cima: não é desenhado.
A altura do espelho vem do 3D (desnível entre os andares ÷ N), não da anotação da planta.
"""
from __future__ import annotations

import math
import re

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from .ingestao import Pagina


def _num(s):
    return float(s.replace(",", "."))


def anotacoes(pag: Pagina, poly: Polygon) -> dict:
    """'e=0,16m', 'p=0,28m', 'L=1,20m' escritos dentro da escada (em m)."""
    out = {}
    for w in pag.palavras:
        mt = re.fullmatch(r"([eEpPlL])=(\d+,\d+)m?", w[4])
        if mt and poly.buffer(30).contains(Point((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)):
            out[{"e": "espelho_m", "p": "piso_m", "l": "largura_m"}[mt.group(1).lower()]] = _num(mt.group(2))
    return out


def _raio(poly: Polygon, o, d, lim):
    """Distância de o, na direção d, até a borda do polígono (máx. lim)."""
    seg = LineString([o, (o[0] + d[0] * lim, o[1] + d[1] * lim)])
    x = seg.intersection(poly.exterior)
    if x.is_empty:
        return lim
    pts = [g for g in getattr(x, "geoms", [x])]
    return min(Point(o).distance(p) for p in pts)


def ler(pag: Pagina, poligono: list, m_por_pt: float, palavras_extra: tuple = ()) -> dict | None:
    """Geometria da escada que sobe deste pavimento, em pt da página. None se não houver."""
    poly = Polygon(poligono).buffer(0)
    if poly.is_empty:
        return None
    nums = {}
    textos = []
    for w in pag.palavras:
        c = Point((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)
        if not poly.buffer(1).contains(c):
            continue
        textos.append(w[4])
        if re.fullmatch(r"\d{1,2}", w[4]):
            nums.setdefault(int(w[4]), (c.x, c.y))
    if 1 not in nums or len(nums) < 4:            # o lance que sobe começa no degrau 1
        return None
    N = max(nums)
    ks = sorted(nums)
    # lances: números seguidos, mesma direção, passo parecido
    lances, atual = [], [ks[0]]
    for a, b in zip(ks, ks[1:]):
        va = (nums[b][0] - nums[a][0], nums[b][1] - nums[a][1])
        ok = b == a + 1
        if ok and len(atual) >= 2:
            p0 = nums[atual[-2]]
            vp = (nums[a][0] - p0[0], nums[a][1] - p0[1])
            la, lp = math.hypot(*va), math.hypot(*vp)
            cos = (va[0] * vp[0] + va[1] * vp[1]) / max(la * lp, 1e-9)
            ok = cos > 0.95 and 0.7 < la / max(lp, 1e-9) < 1.3
        if ok:
            atual.append(b)
        else:
            lances.append(atual)
            atual = [b]
    lances.append(atual)
    lances = [L for L in lances if len(L) >= 2]
    if not lances:
        return None
    info = []
    for L in lances:
        a, b = nums[L[0]], nums[L[-1]]
        dx, dy = b[0] - a[0], b[1] - a[1]
        comp = math.hypot(dx, dy)
        u = (dx / comp, dy / comp)
        passo = comp / (len(L) - 1)
        info.append({"ks": L, "u": u, "n": (-u[1], u[0]), "passo": passo,
                     "eixo": ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)})
    lim = 2.0 / m_por_pt
    for i, F in enumerate(info):
        lados = []
        for sgn in (1, -1):
            d = (F["n"][0] * sgn, F["n"][1] * sgn)
            r = _raio(poly, F["eixo"], d, lim)
            for j, G in enumerate(info):                # outro lance paralelo desse lado: metade da distância
                if j == i or abs(F["u"][0] * G["u"][0] + F["u"][1] * G["u"][1]) < 0.95:
                    continue
                sep = (G["eixo"][0] - F["eixo"][0]) * d[0] + (G["eixo"][1] - F["eixo"][1]) * d[1]
                if sep > 0:
                    r = min(r, sep / 2)
            lados.append(min(r, 1.5 / m_por_pt))
        F["lat"] = lados                                # [lado +n, lado −n]

    def ret(c, u, n, a0, a1, l0, l1):
        """retângulo: ao longo de u de a0 a a1, ao longo de n de −l1 a +l0 (pt)."""
        P = lambda s, t: (c[0] + u[0] * s + n[0] * t, c[1] + u[1] * s + n[1] * t)
        return [P(a0, -l1), P(a1, -l1), P(a1, l0), P(a0, l0)]

    degraus, patamares, corrimaos = [], [], []
    for i, F in enumerate(info):
        u, n, p = F["u"], F["n"], F["passo"]
        ultimo = F["ks"][-1]
        tem_seguinte = i + 1 < len(info)
        for k in F["ks"]:
            if k == N:                                   # chegada no andar de cima
                continue
            if k == ultimo and tem_seguinte:             # vira patamar
                continue
            degraus.append([k, ret(nums[k], u, n, -p / 2, p / 2, F["lat"][0], F["lat"][1])])
        if tem_seguinte:
            c = nums[ultimo]
            ini = (c[0] - u[0] * p / 2, c[1] - u[1] * p / 2)
            meia = Polygon(ret(ini, u, n, 0, 2 * lim, lim, lim))   # do início do último piso até a parede
            pat = poly.intersection(meia)
            if not pat.is_empty:
                g = max(getattr(pat, "geoms", [pat]), key=lambda x: x.area)
                patamares.append([ultimo, [list(q) for q in g.exterior.coords][:-1]])
        # corrimão do lado de dentro (o lado com outro lance) e da parede
        k0 = F["ks"][0]
        k1 = F["ks"][-1] if F["ks"][-1] != N else F["ks"][-2]
        if k1 == ultimo and tem_seguinte:
            k1 = F["ks"][-2] if len(F["ks"]) > 2 else k1
        for lado, sgn in ((0, 1), (1, -1)):
            off = F["lat"][lado] - 0.04 / m_por_pt
            a = (nums[k0][0] - u[0] * p / 2 + n[0] * sgn * off, nums[k0][1] - u[1] * p / 2 + n[1] * sgn * off)
            b = (nums[k1][0] + u[0] * p / 2 + n[0] * sgn * off, nums[k1][1] + u[1] * p / 2 + n[1] * sgn * off)
            dentro = any(j != i and abs(F["u"][0] * G["u"][0] + F["u"][1] * G["u"][1]) > 0.95
                         and ((G["eixo"][0] - F["eixo"][0]) * n[0] + (G["eixo"][1] - F["eixo"][1]) * n[1]) * sgn > 0
                         for j, G in enumerate(info))
            # altura: linha dos bocéis (piso k0 na frente, piso k1 + 1 no fim)
            corrimaos.append({"a": list(a), "b": list(b), "z0": k0, "z1": k1 + 1, "dentro": dentro})
    pegada = unary_union([Polygon(q) for _, q in degraus] + [Polygon(q) for _, q in patamares]).buffer(0.5).buffer(-0.5).simplify(0.3)
    return {
        "n_espelhos": N, "lances": [F["ks"] for F in info],
        "piso_m": round(sum(F["passo"] for F in info) / len(info) * m_por_pt, 3),
        "largura_m": round(sum(F["lat"][0] + F["lat"][1] for F in info) / len(info) * m_por_pt, 3),
        "degraus": degraus, "patamares": patamares, "corrimaos": corrimaos,
        "pegada": [list(q) for q in pegada.exterior.coords][:-1] if pegada.geom_type == "Polygon" else
                  [list(q) for q in max(pegada.geoms, key=lambda x: x.area).exterior.coords][:-1],
        "sobe": "Acima" in textos or 1 in nums,
    }
