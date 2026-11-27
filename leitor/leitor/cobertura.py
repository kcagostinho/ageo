"""Elementos para o 3D-3 que não são ambientes: cobertura (parapeito, platibanda, telhados,
calhas, reservatórios) e muros inclinados (divisa/arrimo), lidos direto das camadas do PDF.

Alturas da cobertura (cortes): laje de cobertura sobre o último pavimento; parapeito 1,20 m;
caixa d'água com platibanda de 4,00 m, laje do reservatório a 1,35 m (1,20 + 0,15) e
reservatórios de 5.000 L; telhados de fibrocimento com i = 10% descendo para as calhas.
"""
from __future__ import annotations

import math

from .ingestao import Pagina
from .vistas import encontrar_vistas

ALTURAS = {"parapeito_m": 1.20, "platibanda_m": 4.00, "laje_reservatorio_m": 1.35, "reservatorio_h_m": 1.60,
           "inclinacao": 0.10, "telhado_folga_m": 0.20, "muro_m": 2.20}


def _ang(s):
    return math.atan2(s[3] - s[1], s[2] - s[0])


def pares_paralelos(segs, m_por_pt, t_min=0.07, t_max=0.35, so_inclinados=False):
    """Eixos de parede a partir de pares de linhas paralelas (qualquer ângulo): devolve
    [(x0, y0, x1, y1, espessura_m)] em pt."""
    lin = []
    for s in segs:
        L = math.hypot(s[2] - s[0], s[3] - s[1])
        if L * m_por_pt < 0.3:
            continue
        a = _ang(s)
        if so_inclinados and abs(math.sin(2 * a)) < 0.05:
            continue
        lin.append((s, a, L))
    out = []
    usados = set()
    for i, (s, a, L) in enumerate(lin):
        ux, uy = math.cos(a), math.sin(a)
        nx, ny = -uy, ux
        melhor = None
        for j, (r, b, M) in enumerate(lin):
            if j == i or abs(math.sin(a - b)) > 0.02:
                continue
            d = (r[0] - s[0]) * nx + (r[1] - s[1]) * ny          # distância entre as retas
            if not (t_min <= abs(d) * m_por_pt <= t_max):
                continue
            # sobreposição das projeções ao longo de s
            p = sorted([(r[0] - s[0]) * ux + (r[1] - s[1]) * uy, (r[2] - s[0]) * ux + (r[3] - s[1]) * uy])
            lo, hi = max(0.0, p[0]), min(L, p[1])
            if (hi - lo) * m_por_pt < 0.3:
                continue
            if melhor is None or abs(d) < abs(melhor[0]):
                melhor = (d, j, lo, hi)
        if not melhor:
            continue
        d, j, lo, hi = melhor
        chave = (min(i, j), max(i, j))
        if chave in usados:
            continue
        usados.add(chave)
        cx, cy = s[0] + nx * d / 2, s[1] + ny * d / 2
        out.append((cx + ux * lo, cy + uy * lo, cx + ux * hi, cy + uy * hi, abs(d) * m_por_pt))
    return out


def muros_inclinados(pag: Pagina, caixa, m_por_pt):
    c = (caixa[0] - 20, caixa[1] - 20, caixa[2] + 20, caixa[3] + 20)
    segs = [s[2:6] for s in pag.segmentos if s[0] == "A-WALL"
            and c[0] <= s[2] <= c[2] and c[1] <= s[3] <= c[3]]
    return pares_paralelos(segs, m_por_pt, so_inclinados=True)


def _grupos_y(segs, tol=4.0):
    """Agrupa linhas da hachura do telhado por faixa vertical (y0, y1) parecida."""
    grupos = []
    for s in segs:
        y0, y1 = min(s[1], s[3]), max(s[1], s[3])
        for g in grupos:
            if abs(g["y0"] - y0) <= tol and abs(g["y1"] - y1) <= tol:
                g["x0"] = min(g["x0"], s[0], s[2]); g["x1"] = max(g["x1"], s[0], s[2]); g["n"] += 1
                break
        else:
            grupos.append({"y0": y0, "y1": y1, "x0": min(s[0], s[2]), "x1": max(s[0], s[2]), "n": 1})
    return [g for g in grupos if g["n"] >= 5]


def _circulos(segs, tol=3.0):
    """Agrupa traços próximos (círculos tracejados) e devolve (cx, cy, r) de cada grupo."""
    grupos = []
    for s in segs:
        for g in grupos:
            if g["x0"] - tol <= s[0] <= g["x1"] + tol and g["y0"] - tol <= s[1] <= g["y1"] + tol:
                g["x0"] = min(g["x0"], s[0], s[2]); g["x1"] = max(g["x1"], s[0], s[2])
                g["y0"] = min(g["y0"], s[1], s[3]); g["y1"] = max(g["y1"], s[1], s[3]); g["n"] += 1
                break
        else:
            grupos.append({"x0": min(s[0], s[2]), "x1": max(s[0], s[2]), "y0": min(s[1], s[3]), "y1": max(s[1], s[3]), "n": 1})
    # junta grupos que se tocam (o tracejado parte o círculo em pedaços)
    mudou = True
    while mudou:
        mudou = False
        for a in grupos:
            for b in grupos:
                if a is not b and a["x0"] - tol <= b["x1"] and b["x0"] - tol <= a["x1"] and a["y0"] - tol <= b["y1"] and b["y0"] - tol <= a["y1"]:
                    a["x0"], a["x1"] = min(a["x0"], b["x0"]), max(a["x1"], b["x1"])
                    a["y0"], a["y1"] = min(a["y0"], b["y0"]), max(a["y1"], b["y1"]); a["n"] += b["n"]
                    grupos.remove(b); mudou = True; break
            if mudou:
                break
    out = []
    for g in grupos:
        w, h = g["x1"] - g["x0"], g["y1"] - g["y0"]
        if g["n"] >= 8 and w > 20 and abs(w - h) < 0.15 * w:
            out.append(((g["x0"] + g["x1"]) / 2, (g["y0"] + g["y1"]) / 2, (w + h) / 4))
    return out


def _reservatorios(tracej, caixa, k):
    """k círculos tracejados dentro da caixa d'água: k-médias nos pontos médios dos traços,
    começando com centros espaçados ao longo do lado maior da caixa."""
    pts = [((s[0] + s[2]) / 2, (s[1] + s[3]) / 2) for s in tracej
           if caixa[0] <= (s[0] + s[2]) / 2 <= caixa[2] and caixa[1] <= (s[1] + s[3]) / 2 <= caixa[3]]
    if k <= 0 or len(pts) < 4 * k:
        return []
    x0, y0, x1, y1 = caixa
    horiz = (x1 - x0) >= (y1 - y0)
    cen = [((x0 + (i + 0.5) * (x1 - x0) / k, (y0 + y1) / 2) if horiz else ((x0 + x1) / 2, y0 + (i + 0.5) * (y1 - y0) / k)) for i in range(k)]
    for _ in range(30):
        grupos = [[] for _ in cen]
        for p in pts:
            i = min(range(k), key=lambda j: (p[0] - cen[j][0]) ** 2 + (p[1] - cen[j][1]) ** 2)
            grupos[i].append(p)
        cen = [(sum(q[0] for q in g) / len(g), sum(q[1] for q in g) / len(g)) if g else c for g, c in zip(grupos, cen)]
    out = []
    for (cx, cy), g in zip(cen, grupos):
        if len(g) >= 4:
            r = sum(math.hypot(q[0] - cx, q[1] - cy) for q in g) / len(g)
            out.append((cx, cy, r))
    return out


def ler_cobertura(paginas: list[Pagina]):
    """Procura a vista 'Cobertura' e devolve os elementos em pt + escala, ou None."""
    for pag in paginas:
        for v in encontrar_vistas(pag):
            if "cobertura" not in v.titulo.lower():
                continue
            from .escala import calibrar
            cal = calibrar(pag, v.caixa)
            m = cal.m_por_pt if cal else v.m_por_pt_nominal
            c = (v.caixa[0] - 15, v.caixa[1] - 15, v.caixa[2] + 15, v.caixa[3] + 15)
            dentro = lambda s: c[0] <= s[2] <= c[2] and c[1] <= s[3] <= c[3]
            paredes = [s[2:6] for s in pag.segmentos if s[0] == "A-WALL" and dentro(s)]
            hach = [s[2:6] for s in pag.segmentos if s[0] == "A-ROOF-PATT" and dentro(s)]
            borda = [s[2:6] for s in pag.segmentos if s[0] == "A-ROOF" and dentro(s)]
            tracej = [s[2:6] for s in pag.segmentos if s[0] == "A-FLOR-OVHD" and dentro(s)]
            eixos = pares_paralelos(paredes, m, t_min=0.07, t_max=0.30)
            xs = [x for s in paredes for x in (s[0], s[2])]
            ys = [y for s in paredes for y in (s[1], s[3])]
            caixa_ext = (min(xs), min(ys), max(xs), max(ys))
            telhados = []
            for g in _grupos_y([s for s in hach if abs(s[0] - s[2]) < 0.5] or hach):
                # calha = borda (A-ROOF) mais próxima de uma das extremidades da faixa
                lado = None
                for b in borda:
                    yb = (b[1] + b[3]) / 2
                    for nome, y in (("y0", g["y0"]), ("y1", g["y1"])):
                        if abs(yb - y) < 4 and min(b[0], b[2]) < g["x1"] and max(b[0], b[2]) > g["x0"]:
                            lado = nome
                telhados.append({**g, "calha": lado or "y1"})
            # nº de reservatórios escrito na planta ("4 RESERVATÓRIOS ...")
            k = 0
            for w in pag.palavras:
                if "RESERVAT" in w[4].upper() and c[0] <= w[0] <= c[2] and c[1] <= w[1] <= c[3]:
                    ant = [x for x in pag.palavras if (x[5], x[6]) == (w[5], w[6]) and x[2] <= w[0] + 1 and x[4].isdigit()]
                    if ant:
                        k = int(max(ant, key=lambda x: x[2])[4]); break
            menor = min(telhados, key=lambda t: (t["x1"] - t["x0"]) * (t["y1"] - t["y0"])) if telhados else None
            circ = _reservatorios(tracej, (menor["x0"] - 10, menor["y0"] - 10, menor["x1"] + 10, menor["y1"] + 10), k) if menor else []
            return {"m_por_pt": m, "caixa": caixa_ext, "paredes": eixos, "telhados": telhados, "reservatorios": circ,
                    "pagina": pag.numero, "titulo": v.titulo}
    return None
