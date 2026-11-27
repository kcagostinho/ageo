"""Água fria (e base para o esgoto): leitura dos isométricos e plantas de um PDF hidráulico sem camadas.

O PDF não tem camadas do CAD: todo traço fino tem 0,15 pt e os tubos são polígonos pretos
preenchidos. A leitura é pela imagem:
  - tubos = traço grosso preto: render em cinza, abertura morfológica (some texto, cota e linha fina),
    esqueleto, grafo, trechos retos (Ramer-Douglas-Peucker);
  - cada rótulo "DNxx mm / L,LLm" vai para o trecho pela chamada (linha fina que sai do rótulo e
    termina no tubo) ou pelo mais perto, sem aceitar um trecho desenhado bem maior que o rótulo;
  - o código da conexão (círculo com 2 dígitos) vai para a ponta de trecho mais próxima.

Isométrico de coluna (um por prumada: banheiro, cozinha/Á.S., varanda gourmet) é uma elevação
oblíqua EM ESCALA: a vertical e o eixo horizontal da parede saem com a mesma escala (pt/m), dada pelas
cotas de altura dos pontos ("0,20", "1,40"...: o tique de baixo é o piso). Por isso a posição ao
longo da parede (s) e a altura (z) de cada ponto saem do próprio desenho.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pymupdf
from skimage.morphology import disk, opening, skeletonize

PPP = 4.0  # px por pt


def render(pg, caixa, ppp=PPP):
    x0, y0, x1, y1 = caixa
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(ppp, ppp), clip=pymupdf.Rect(x0, y0, x1, y1),
                        colorspace=pymupdf.csGRAY, alpha=False)
    a = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
    return a


def mascara_tubos(a, r=2):
    preto = a < 110
    return opening(preto, disk(r))


def textos(pg, caixa=None):
    """Spans em coordenadas exibidas (com a rotação da página)."""
    R = pg.rotation_matrix
    out = []
    for b in pg.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                t = s["text"].strip()
                if not t:
                    continue
                r = pymupdf.Rect(s["bbox"]) * R
                if caixa and not (caixa[0] <= r.x0 and r.x1 <= caixa[2] and caixa[1] <= r.y0 and r.y1 <= caixa[3]):
                    continue
                out.append({"t": t, "r": (r.x0, r.y0, r.x1, r.y1), "c": ((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2),
                            "size": s["size"]})
    return out


VIZ = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def grafo(sk):
    """Nós (pontas e junções) e caminhos de pixels entre eles."""
    sk = sk.astype(bool)
    H, W = sk.shape
    pts = set(zip(*np.nonzero(sk)))

    def viz(p):
        y, x = p
        return [(y + dy, x + dx) for dy, dx in VIZ if (y + dy, x + dx) in pts]

    grau = {p: len(viz(p)) for p in pts}
    nos = {p for p, g in grau.items() if g != 2}
    visit = set()
    caminhos = []
    for n in nos:
        for q in viz(n):
            if (n, q) in visit:
                continue
            cam = [n, q]
            visit.add((n, q))
            prev, cur = n, q
            while cur not in nos:
                nx = [r for r in viz(cur) if r != prev and r not in cam[-3:]]
                if not nx:
                    break
                prev, cur = cur, nx[0]
                cam.append(cur)
            visit.add((cam[-1], cam[-2]))
            caminhos.append(cam)
    # laços sem nó (anel isolado): ignorados
    return nos, caminhos


def rdp(pts, eps):
    pts = np.asarray(pts, float)
    if len(pts) < 3:
        return pts
    a, b = pts[0], pts[-1]
    ab = b - a
    L = np.hypot(*ab)
    if L < 1e-9:
        d = np.hypot(*(pts - a).T)
    else:
        v = pts - a
        d = np.abs(ab[0] * v[:, 1] - ab[1] * v[:, 0]) / L
    i = int(np.argmax(d))
    if d[i] > eps:
        return np.vstack([rdp(pts[: i + 1], eps)[:-1], rdp(pts[i:], eps)])
    return np.vstack([a, b])


def segmentos(a, caixa, ppp=PPP, eps=1.5, minimo_pt=2.0):
    m = mascara_tubos(a)
    sk = skeletonize(m)
    _, cams = grafo(sk)
    x0, y0 = caixa[0], caixa[1]
    segs = []
    for cam in cams:
        p = rdp([(x, y) for y, x in cam], eps)
        for (xa, ya), (xb, yb) in zip(p[:-1], p[1:]):
            A = (x0 + xa / ppp, y0 + ya / ppp)
            B = (x0 + xb / ppp, y0 + yb / ppp)
            if math.dist(A, B) >= minimo_pt:
                segs.append((A, B))
    return segs, m, sk


def angulo(s):
    (xa, ya), (xb, yb) = s
    ang = math.degrees(math.atan2(yb - ya, xb - xa)) % 180
    return ang


RX_DN = re.compile(r"^DN\s*(\d+)\s*mm$")
RX_L = re.compile(r"^(\d+),(\d+)\s*m$")
RX_COD = re.compile(r"^\d{2}$")


def linhas_finas(pg, caixa):
    """Polilinhas de traço fino (chamadas, cotas, contorno de laje) em coordenadas exibidas."""
    R = pg.rotation_matrix
    cx = pymupdf.Rect(*caixa)
    out = []
    for d in pg.get_drawings():
        if d["type"] != "s":
            continue
        r = d["rect"] * R
        if r.x1 < cx.x0 or r.x0 > cx.x1 or r.y1 < cx.y0 or r.y0 > cx.y1:   # (Rect.intersects falha em linha reta: retângulo vazio)
            continue
        pts = []
        for it in d["items"]:
            if it[0] != "l":
                pts = []
                continue
            p, q = it[1] * R, it[2] * R
            if pts and math.dist(pts[-1], (p.x, p.y)) < 0.05:
                pts.append((q.x, q.y))
            else:
                if len(pts) >= 2:
                    out.append(pts)
                pts = [(p.x, p.y), (q.x, q.y)]
        if len(pts) >= 2:
            out.append(pts)
    return out


def dist_ps(p, s):
    (ax, ay), (bx, by) = s
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy
    t = 0 if L2 < 1e-12 else max(0, min(1, ((p[0] - ax) * vx + (p[1] - ay) * vy) / L2))
    return math.hypot(p[0] - ax - t * vx, p[1] - ay - t * vy)


def dist_rs(r, s, n=9):
    """Distância aproximada retângulo-segmento (amostra o segmento)."""
    (ax, ay), (bx, by) = s
    best = 1e9
    for k in range(n + 1):
        x, y = ax + (bx - ax) * k / n, ay + (by - ay) * k / n
        dx = max(r[0] - x, 0, x - r[2])
        dy = max(r[1] - y, 0, y - r[3])
        best = min(best, math.hypot(dx, dy))
    for x, y in ((r[0], r[1]), (r[2], r[1]), (r[0], r[3]), (r[2], r[3])):
        best = min(best, dist_ps((x, y), s))
    return best


def rotulos(tx):
    """Pares 'DNxx mm' + 'L,LLm' (o comprimento logo abaixo do DN)."""
    dns = [t for t in tx if RX_DN.match(t["t"])]
    ls = [t for t in tx if RX_L.match(t["t"])]
    usados = set()
    out = []
    for d in dns:
        cand = [(abs(l["c"][0] - d["c"][0]) + abs(l["c"][1] - d["c"][1] - 7) , i) for i, l in enumerate(ls)
                if i not in usados and abs(l["c"][0] - d["c"][0]) < 6 and 2 < l["c"][1] - d["c"][1] < 12]
        if not cand:
            out.append({"dn": int(RX_DN.match(d["t"]).group(1)), "L": None, "r": d["r"], "c": d["c"]})
            continue
        _, i = min(cand)
        usados.add(i)
        l = ls[i]
        mL = RX_L.match(l["t"])
        r = (min(d["r"][0], l["r"][0]), d["r"][1], max(d["r"][2], l["r"][2]), l["r"][3])
        out.append({"dn": int(RX_DN.match(d["t"]).group(1)), "L": float(f"{mL.group(1)}.{mL.group(2)}"),
                    "r": r, "c": ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)})
    sobra = [ls[i] for i in range(len(ls)) if i not in usados]
    return out, sobra


def casar_rotulos(rots, segs, finas, folga=3.0, perto=4.0, raio=24.0, esc=134.0):
    """Rótulo -> trecho. Custo = distância (pela chamada, se houver: linha fina que sai do rótulo e
    termina no tubo) + penalidade quando o desenho é bem maior que o comprimento do rótulo (o rótulo de
    um tubinho não pode ir para o tubo comprido ao lado). Devolve [(rotulo, idx_seg, como, dist)]."""
    def pena(ro, s):
        Ld = math.dist(*s)
        # rótulo de tubo longo não vai para um pedacinho de conexão (< 4 pt) se houver tubo de verdade perto
        miudo = 6 if (ro["L"] or 0) >= 1.0 and Ld < 4 else 0
        if not ro["L"] or not esc:
            return miudo
        maximo = ro["L"] * esc * 1.06 + 3
        return miudo + (0 if Ld <= maximo else 4 + (Ld - maximo) / 4)

    res = []
    for ro in rots:
        r = ro["r"]
        rx = (r[0] - folga, r[1] - folga, r[2] + folga, r[3] + folga)
        cands = []
        for pl in finas:
            for ponta, outra in ((pl[0], pl[-1]), (pl[-1], pl[0])):
                if not (rx[0] <= ponta[0] <= rx[2] and rx[1] <= ponta[1] <= rx[3]):
                    continue
                if rx[0] <= outra[0] <= rx[2] and rx[1] <= outra[1] <= rx[3]:
                    continue
                for j, s in enumerate(segs):
                    d = dist_ps(outra, s)
                    if d <= perto:
                        cands.append((d + pena(ro, s), j, "chamada", d))
        for j, s in enumerate(segs):
            d = dist_rs(r, s)
            if d <= raio:
                cands.append((d + 2.5 + pena(ro, s), j, "perto", d))
        if cands:
            c, j, como, d = min(cands)
            res.append((ro, j, como, d))
        else:
            res.append((ro, None, "sem tubo", None))
    return res


def regioes_tabela(tx, folga=(70, 40, 60, 8)):
    """Retângulos das tabelas do projetista (linhas com descrição de material)."""
    linhas = [t for t in tx if re.search(r"TIGRE|Sold[aá]vel|Quantidade|Descri", t["t"]) and len(t["t"]) > 6]
    if not linhas:
        return []
    # agrupa por proximidade
    grupos = []
    for t in sorted(linhas, key=lambda t: (t["r"][0], t["r"][1])):
        r = t["r"]
        for g in grupos:
            if r[0] < g[2] + 40 and r[2] > g[0] - 40 and r[1] < g[3] + 40 and r[3] > g[1] - 40:
                g[0], g[1], g[2], g[3] = min(g[0], r[0]), min(g[1], r[1]), max(g[2], r[2]), max(g[3], r[3])
                break
        else:
            grupos.append(list(r))
    return [(g[0] - folga[0], g[1] - folga[1], g[2] + folga[2], g[3] + folga[3]) for g in grupos]


def vistas(pg, ppp=1.5, altura_min=250):
    """Isométricos da folha: faixas verticais de tubo (traço grosso)."""
    from skimage.measure import label, regionprops
    from skimage.morphology import footprint_rectangle
    a = np.frombuffer((p := pg.get_pixmap(matrix=pymupdf.Matrix(ppp, ppp), colorspace=pymupdf.csGRAY,
                                          alpha=False)).samples, np.uint8).reshape(p.h, p.w)
    m = opening(a < 110, footprint_rectangle((3, 3)))
    lab = label(m, connectivity=2)
    caixas = []
    for rp in regionprops(lab):
        y0, x0, y1, x1 = rp.bbox
        caixas.append((x0 / ppp, y0 / ppp, x1 / ppp, y1 / ppp))
    # junta componentes que se sobrepõem em x (a mesma coluna de isométrico)
    caixas.sort()
    faixas = []
    for c in caixas:
        if faixas and c[0] <= faixas[-1][2] + 15:
            f = faixas[-1]
            faixas[-1] = (f[0], min(f[1], c[1]), max(f[2], c[2]), max(f[3], c[3]))
        else:
            faixas.append(c)
    return [f for f in faixas if f[3] - f[1] >= altura_min]


def caixas_vistas(pg, tx, margem=70):
    faixas = vistas(pg)
    tabs = regioes_tabela(tx)
    carimbo = [t["r"] for t in tx if t["t"].startswith("CUIDADOS DE EXECU")]
    excl = list(tabs) + [(c[0] - 5, c[1] - 12, 1e5, 1e5) for c in carimbo]
    out = []
    for k, f in enumerate(faixas):
        x0 = f[0] - margem if k == 0 else (faixas[k - 1][2] + f[0]) / 2
        x1 = f[2] + margem if k == len(faixas) - 1 else (f[2] + faixas[k + 1][0]) / 2
        out.append((x0, f[1] - 40, x1, f[3] + 40))
    return out, excl


def dentro(c, r):
    return r[0] <= c[0] <= r[2] and r[1] <= c[1] <= r[3]


def ler_vista(pg, caixa, tx_pag, excl, finas=None):
    tx = [t for t in tx_pag if dentro(t["c"], caixa) and not any(dentro(t["c"], e) for e in excl)]
    a = render(pg, caixa)
    segs, m, sk = segmentos(a, caixa)
    rots, sobra = rotulos(tx)
    if finas is None:
        finas = linhas_finas(pg, caixa)
    res = casar_rotulos(rots, segs, finas, esc=None)
    razoes = sorted(math.dist(*segs[j]) / ro["L"] for ro, j, c, d in res if j is not None and ro["L"] and ro["L"] >= 0.9)
    esc = razoes[int(len(razoes) * 0.8)] if len(razoes) >= 4 else None
    if esc:
        res = casar_rotulos(rots, segs, finas, esc=esc)
    cods = [t for t in tx if RX_COD.match(t["t"]) and t["size"] < 9]
    titulo = [t["t"] for t in tx if t["size"] > 14 and len(t["t"]) > 3]
    return {"caixa": caixa, "esc": esc, "segs": segs, "rotulos": res, "sobra_L": sobra, "codigos": cods, "titulo": titulo}


# ----------------------------------------------------------------------------------------------
# Isométrico de coluna (elevação oblíqua em escala)
# ----------------------------------------------------------------------------------------------
RX_COTA = re.compile(r"^(\d),(\d\d)$")
RX_COLUNA = re.compile(r"^(AF|AL|EXT\w*|TQ|TG|TS|V|VP|CV)\s*-?\s*(\d+)$", re.I)
PAVS_TIPO = ["5ºPavimento", "4ºPavimento", "3ºPavimento", "2ºPavimento", "1ºPavimento", "Pavimento Térreo"]


def cotas_altura(tx, finas, k_min=60.0, k_max=200.0):
    """Cotas verticais "0,20", "1,40"...: linha vertical fina com dois tiques a 45°. Devolve
    [{valor, x, y_baixo, y_cima, k}] (k = pt por metro do desenho)."""
    vl = [pl for pl in finas if len(pl) == 2 and abs(pl[0][0] - pl[1][0]) < 0.2 and abs(pl[0][1] - pl[1][1]) > 8]
    ticks = [pl[1] for pl in finas if len(pl) == 3 and abs(abs(pl[0][0] - pl[1][0]) - abs(pl[0][1] - pl[1][1])) < 0.8
             and 2 < math.dist(pl[0], pl[1]) < 8]
    out = []
    for t in tx:
        m = RX_COTA.match(t["t"])
        if not m:
            continue
        val = float(f"{m.group(1)}.{m.group(2)}")
        if val <= 0:
            continue
        cands = []
        for p, q in vl:
            x = p[0]
            y0, y1 = sorted((p[1], q[1]))
            if abs(x - t["c"][0]) > 10 or not (y0 <= t["c"][1] <= y1):
                continue
            tk = sorted(y for xt, y in ticks if abs(xt - x) < 0.4 and y0 - 0.5 <= y <= y1 + 0.5)
            for a, b in zip(tk, tk[1:]):
                if a - 1 <= t["c"][1] <= b + 1 and k_min <= (b - a) / val <= k_max:
                    cands.append((abs(t["c"][0] - x), {"valor": val, "x": x, "y_baixo": b, "y_cima": a, "k": (b - a) / val}))
        if cands:
            out.append(min(cands, key=lambda c: c[0])[1])
    return out


def _mediana_pond(pares):
    pares = sorted(pares)
    tot = sum(w for _, w in pares)
    acc = 0.0
    for v, w in pares:
        acc += w
        if acc >= tot / 2:
            return v
    return pares[-1][0] if pares else 0.0


def _ang(s):
    """Ângulo do trecho em graus, normalizado para (-90, 90]."""
    a = angulo(s)
    return a - 180 if a > 90 else a


def _intersecao(s1, s2):
    (x1, y1), (x2, y2) = s1
    (x3, y3), (x4, y4) = s2
    d = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(d) < 1e-9:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / d
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))


def ligar(segs, idx, raio=10.0):
    """Leva as pontas dos trechos ao centro da conexão: joelho/tê = cruzamento dos eixos; luva/registro
    (trechos alinhados) = ponto médio; ponta que encosta no meio de outro trecho = projeção nele.
    Devolve {i: [A, B]} com as pontas ajustadas."""
    pontas = {i: [list(segs[i][0]), list(segs[i][1])] for i in idx}
    for i in idx:
        for e in (0, 1):
            P = segs[i][e]
            melhor = None
            for j in idx:
                if j == i:
                    continue
                for f in (0, 1):
                    Q = segs[j][f]
                    d = math.dist(P, Q)
                    if d > raio:
                        continue
                    da = abs(_ang(segs[i]) - _ang(segs[j]))
                    da = min(da, 180 - da)
                    if da < 10:   # alinhados: luva, registro
                        X = ((P[0] + Q[0]) / 2, (P[1] + Q[1]) / 2)
                    else:
                        X = _intersecao(segs[i], segs[j])
                        if X is None or math.dist(X, P) > raio or math.dist(X, Q) > raio:
                            continue
                    if melhor is None or d < melhor[0]:
                        melhor = (d, X)
                # ponta no meio de outro trecho (tê com a coluna contínua no desenho)
                d = dist_ps(P, segs[j])
                if d <= 6 and min(math.dist(P, segs[j][0]), math.dist(P, segs[j][1])) > raio:
                    (ax, ay), (bx, by) = segs[j]
                    vx, vy = bx - ax, by - ay
                    t = ((P[0] - ax) * vx + (P[1] - ay) * vy) / (vx * vx + vy * vy)
                    X = (ax + t * vx, ay + t * vy)
                    if melhor is None or d < melhor[0]:
                        melhor = (d, X)
            if melhor:
                pontas[i][e] = list(melhor[1])
    return pontas


def niveis_do_modelo(dados: dict) -> dict:
    """Nível do piso de cada pavimento no modelo (térreo = 0), como no 3D: pé-direito + laje 0,15."""
    pd = dados["premissas"]["pe_direito_m"]
    nomes = [v["titulo"] for v in dados["vistas"]]
    i_ter = next((i for i, t in enumerate(nomes) if "rreo" in t), 0)
    z, acc = {}, 0.0
    for i in range(i_ter, len(nomes)):
        z[nomes[i]] = round(acc, 3)
        acc += pd.get(nomes[i], 2.6) + 0.15
    z["Cobertura"] = round(acc, 3)
    acc = 0.0
    for i in range(i_ter - 1, -1, -1):
        acc -= pd.get(nomes[i], 2.6) + 0.15
        z[nomes[i]] = round(acc, 3)
    return z


def ler_coluna(pg, caixa, tx_pag, excl, niveis: dict, pavs=PAVS_TIPO):
    """Isométrico de uma prumada. Devolve trechos e conexões com (s, z): s = distância ao longo da parede a
    partir do eixo da coluna (m), z = nível no prédio (m, térreo = 0)."""
    tx = [t for t in tx_pag if dentro(t["c"], caixa) and not any(dentro(t["c"], e) for e in excl)]
    finas = linhas_finas(pg, caixa)
    v = ler_vista(pg, caixa, tx_pag, excl, finas=finas)
    segs = v["segs"]
    cotas = cotas_altura(tx, finas)
    avisos = []
    if cotas:
        k = sorted(c["k"] for c in cotas)[len(cotas) // 2]
        disp = max(abs(c["k"] / k - 1) for c in cotas)
        if disp > 0.01:
            avisos.append(f"escala das cotas varia {disp:.1%}")
    else:
        k = (v["esc"] or 120) * 1.04
        avisos.append("sem cotas de altura: escala estimada pelos rótulos")
    # eixo horizontal (direção da parede) e coluna
    hs = [(_ang(s), math.dist(*s)) for s in segs if abs(_ang(s)) < 15 and math.dist(*s) > 6]
    alfa = _mediana_pond(hs) if hs else 0.0
    tipo = {}
    for i, s in enumerate(segs):
        a = _ang(s)
        tipo[i] = "v" if abs(abs(a) - 90) < 2.5 else ("h" if abs(a - alfa) < 2.0 else "x")
    verts = [i for i in tipo if tipo[i] == "v"]
    col = max(verts, key=lambda i: math.dist(*segs[i]))
    Xc = (segs[col][0][0] + segs[col][1][0]) / 2
    sa, ca = math.sin(math.radians(alfa)), math.cos(math.radians(alfa))

    def s_de(X):
        return (X - Xc) / (k * ca)

    # pisos: o tique de baixo de cada cota é o piso; agrupa por andar (de cima para baixo)
    y0s = sorted(c["y_baixo"] - s_de(c["x"]) * k * sa for c in cotas)
    grupos = []
    for y in y0s:
        if grupos and y - grupos[-1][-1] < 0.08 * k:
            grupos[-1].append(y)
        else:
            grupos.append([y])
    pisos = [(pavs[n] if n < len(pavs) else f"?{n}", sum(g) / len(g), len(g), max(g) - min(g)) for n, g in enumerate(grupos)]
    if not pisos:
        raise ValueError("isométrico sem cotas de piso")
    ref = pisos[-1]                                         # andar mais baixo = referência
    if len(pisos) >= 2:
        # escala pela distância entre os pisos (muitos tiques, mais firme que uma cota só); as cotas conferem
        k_pisos = (pisos[-1][1] - pisos[0][1]) / (niveis[pisos[0][0]] - niveis[pisos[-1][0]])
        if abs(k_pisos / k - 1) > 0.005:
            avisos.append(f"escala pelos pisos {k_pisos:.2f} pt/m difere das cotas ({k:.2f})")
        k = k_pisos
    Yref, zref = ref[1], niveis[ref[0]]
    residuos = {nome: round((Yref - (zp := niveis[nome] - zref) * k - y0) / k, 4) for nome, y0, _, _ in pisos}

    def sz(P):
        X, Y = P
        s = s_de(X)
        return round(s, 4), round(zref + (Yref + s * k * sa - Y) / k, 4)

    idx = [i for i in tipo if tipo[i] in ("v", "h")]
    pontas = ligar(segs, idx)
    # rótulos -> trechos (um por tubo desenhado; rótulo repetido no mesmo tubo conta uma vez)
    por_seg = defaultdict(list)
    for ro, j, como, d in v["rotulos"]:
        por_seg[j].append((ro, como))
    trechos, repetidos = [], []
    for j, lst in por_seg.items():
        if j is None:
            for ro, como in lst:
                trechos.append({"dn": ro["dn"], "L": ro["L"], "geo": None, "como": como, "rotulo_xy": ro["c"]})
            continue
        Ld = math.dist(*segs[j]) / k
        dono = min(lst, key=lambda rc: abs((rc[0]["L"] or 0) - Ld))
        vistos = set()
        for ro, como in sorted(lst, key=lambda rc: rc is not dono):
            chave = (ro["dn"], ro["L"])
            if chave in vistos:
                repetidos.append({"dn": ro["dn"], "L": ro["L"], "rotulo_xy": ro["c"]})
                continue
            vistos.add(chave)
            geo = None
            if (ro, como) is dono or ro is dono[0]:
                A, B = pontas.get(j, segs[j])
                geo = (sz(A), sz(B))
            trechos.append({"dn": ro["dn"], "L": ro["L"], "geo": geo, "eixo": tipo[j], "seg": j, "como": como,
                            "desenho_m": round(Ld, 3), "rotulo_xy": ro["c"],
                            "junto_de": None if geo else j})
    # o eixo horizontal da vista oblíqua não sai exatamente em escala (0,98 a 1,09 conforme a vista):
    # fator pela razão desenho (centro a centro) / rótulo dos ramais horizontais
    # inclinação de Theil-Sen de (centro a centro) × rótulo: a folga das conexões (constante) não entra
    hz = [(t["L"], abs(t["geo"][1][0] - t["geo"][0][0])) for t in trechos
          if t["geo"] and t.get("eixo") == "h" and t["L"] and t["L"] >= 0.15 and max(t["geo"][0][1], t["geo"][1][1]) < niveis.get("Cobertura", 1e9)]
    incl = sorted((d2 - d1) / (L2 - L1) for i, (L1, d1) in enumerate(hz) for L2, d2 in hz[i + 1:] if abs(L2 - L1) >= 0.3)
    longos = sorted(d / L for L, d in hz if L >= 0.8)
    f_h = incl[len(incl) // 2] if len(incl) >= 3 else (longos[len(longos) // 2] if longos else 1.0)
    if not 0.8 < f_h < 1.25:
        avisos.append(f"fator horizontal fora do esperado ({f_h:.3f}); mantido 1")
        f_h = 1.0
    for t in trechos:
        if t["geo"]:
            t["geo"] = tuple((round(a / f_h, 4), b) for a, b in t["geo"])
        else:
            sr, zr = sz(t["rotulo_xy"])
            t["z_rotulo"] = zr
    # tubo desenhado sem rótulo (o projetista não rotulou em todos os andares). Texto grande (título da
    # vista) que passa na abertura morfológica não é tubo.
    titulos_r = [t["r"] for t in tx if t["size"] > 12]
    def no_titulo(i):
        (xa, ya), (xb, yb) = segs[i]
        return any(r[0] - 4 <= (xa + xb) / 2 <= r[2] + 4 and r[1] - 4 <= (ya + yb) / 2 <= r[3] + 4 for r in titulos_r)
    # abaixo de 8 cm desenhados é pedaço de símbolo de conexão/registro, não tubo
    sem_rotulo = [i for i in idx if i not in por_seg and math.dist(*segs[i]) / k >= 0.08 and not no_titulo(i)]
    inferidos, sem_inferencia = [], []
    rel = lambda z: z - niveis[pav_de(z, niveis)]
    for i in sem_rotulo:
        A, B = pontas.get(i, segs[i])
        (s0, z0), (s1, z1) = sz(A), sz(B)
        s0, s1 = s0 / f_h, s1 / f_h
        Ld = math.dist(*segs[i]) / k
        # 1) rótulo curto sem traço próprio logo ao lado: é deste tubo
        perto = [t for t in trechos if t["geo"] is None and t["L"] and math.dist(t["rotulo_xy"], ((A[0] + B[0]) / 2, (A[1] + B[1]) / 2)) < 30
                 and abs(t["L"] - (Ld + 0.065)) < 0.08]
        if perto:
            t = min(perto, key=lambda t: abs(t["L"] - (Ld + 0.065)))
            t.update(geo=((s0, z0), (s1, z1)), eixo=tipo[i], seg=i, desenho_m=round(Ld, 3), junto_de=None)
            t.pop("z_rotulo", None)
            continue
        # 2) o mesmo tubo, rotulado em outro andar da mesma vista (mesma posição relativa ao piso)
        iguais = Counter()
        for t in trechos:
            if not t["geo"] or t.get("eixo") != tipo[i]:
                continue
            (a0, b0), (a1, b1) = t["geo"]
            for (p0, q0), (p1, q1) in ((((a0, b0), (a1, b1))), (((a1, b1), (a0, b0)))):
                if abs(p0 - s0) < 0.04 and abs(p1 - s1) < 0.04 and abs(rel(q0) - rel(z0)) < 0.04 and abs(rel(q1) - rel(z1)) < 0.04 \
                        and pav_de(q0, niveis) != pav_de(z0, niveis):
                    iguais[(t["dn"], t["L"])] += 1
        if iguais:
            (dn, L), n = iguais.most_common(1)[0]
            inferidos.append({"dn": dn, "L": L, "geo": ((s0, z0), (s1, z1)), "eixo": tipo[i], "seg": i, "como": "inferido",
                              "desenho_m": round(Ld, 3), "rotulo_xy": ((A[0] + B[0]) / 2, (A[1] + B[1]) / 2), "junto_de": None,
                              "nota": f"sem rótulo neste andar; igual ao mesmo tubo rotulado em {n} outro(s) andar(es)"})
        else:
            sem_inferencia.append(i)
    trechos += inferidos
    sem_rotulo = sem_inferencia
    # conexões: código no círculo -> ponta ajustada mais próxima
    nos = [(tuple(P), i) for i, pp in pontas.items() for P in pp]
    conexoes = []
    for c in v["codigos"]:
        if not nos:
            break
        P, i = min(nos, key=lambda n: math.dist(n[0], c["c"]))
        d = math.dist(P, c["c"])
        sp, zp = sz(P) if d < 18 else sz(c["c"])
        conexoes.append({"cod": c["t"], "xy": c["c"], "no": (round(sp / f_h, 4), zp), "dist": round(d, 1)})
    colunas = [t["t"] for t in tx if RX_COLUNA.match(t["t"].replace(" ", ""))]
    return {"titulo": (v["titulo"] or ["?"])[0], "pagina": pg.number + 1, "caixa": caixa, "k": k, "alfa": alfa, "Xc": Xc, "f_h": f_h,
            "pisos": pisos, "residuos_piso_m": residuos, "trechos": trechos, "repetidos": repetidos,
            "sem_rotulo": [(i, round(math.dist(*segs[i]) / k, 3), tipo[i]) for i in sem_rotulo],
            "conexoes": conexoes, "colunas": colunas, "avisos": avisos, "segs": segs, "tipo": tipo}


# ----------------------------------------------------------------------------------------------
# Plantas: colunas (balões AF-xx) e registro sobre o modelo arquitetônico
# ----------------------------------------------------------------------------------------------
def pontos_marcados(pg, caixa, tam=3.5):  # noqa: D401
    """Centros dos pontinhos pretos (marca da coluna na ponta da chamada do balão)."""
    R = pg.rotation_matrix
    out = []
    for d in pg.get_drawings():
        if d["type"] not in ("f", "fs"):
            continue
        r = d["rect"] * R
        if r.width < tam and r.height < tam and caixa[0] <= r.x0 <= caixa[2] and caixa[1] <= r.y0 <= caixa[3]:
            out.append(((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2))
    return out


def balões(tx, finas, raio=(11.0, 19.0), pontos=None):
    """Balão de coluna ("AF-07" sobre "ø20") e a ponta da chamada (o ponto da coluna na planta). Com 'pontos'
    (marcas pretas), vale a chamada que termina numa marca; senão, a que sai mais exatamente do círculo."""
    out = []
    for t in tx:
        nome = t["t"].replace(" ", "")
        if not (RX_COLUNA.match(nome) or nome.upper().startswith(("AL", "EXTRAV"))):
            continue
        if len(nome) > 9:
            continue
        diam = next((u for u in tx if u["t"].startswith("ø") and abs(u["c"][0] - t["c"][0]) < 8 and 3 < u["c"][1] - t["c"][1] < 12), None)
        cx, cy = t["c"][0], (t["c"][1] + diam["c"][1]) / 2 if diam else t["c"][1] + 3.5
        melhor = None
        for pl in finas:
            for a, b in ((pl[0], pl[-1]), (pl[-1], pl[0])):
                da = math.dist(a, (cx, cy))
                if raio[0] <= da <= raio[1] and math.dist(b, (cx, cy)) > raio[1] + 3:
                    marca = 0 if pontos and any(math.dist(b, q) < 2.0 for q in pontos) else 1
                    nota = (marca, abs(da - 14))
                    if melhor is None or nota < melhor[3]:
                        melhor = (da, b, pl, nota)
        out.append({"coluna": nome, "diametro": diam["t"] if diam else None, "centro": (cx, cy),
                    "ponto": melhor[1] if melhor else None, "chamada": melhor[2] if melhor else None})
    return out


def _linhas_eixo(pls, minimo=20.0):
    """Trechos horizontais e verticais de polilinhas: [(coordenada, inicio, fim, comprimento)]."""
    hs, vs = [], []
    for pl in pls:
        for a, b in zip(pl[:-1], pl[1:]):
            L = math.dist(a, b)
            if L < minimo:
                continue
            if abs(a[1] - b[1]) < 0.05:
                hs.append((a[1], min(a[0], b[0]), max(a[0], b[0]), L))
            elif abs(a[0] - b[0]) < 0.05:
                vs.append((a[0], min(a[1], b[1]), max(a[1], b[1]), L))
    return hs, vs


def registrar(ref_h, ref_v, hid_h, hid_v, escalas=None, passo=0.5):
    """Acha s, tx, ty com ref ≈ s·hid + t, por votação: posições das linhas verticais (x) e horizontais
    (y) das paredes. Devolve (s, tx, ty, nota) — nota = fração do comprimento que casou."""
    import numpy as np
    if escalas is None:
        escalas = np.arange(0.95, 1.05, 0.0005)
    rx = np.array([c for c, *_ in ref_v]); rwx = np.array([L for *_, L in ref_v])
    ry = np.array([c for c, *_ in ref_h]); rwy = np.array([L for *_, L in ref_h])
    hx = np.array([c for c, *_ in hid_v]); hwx = np.array([L for *_, L in hid_v])
    hy = np.array([c for c, *_ in hid_h]); hwy = np.array([L for *_, L in hid_h])

    def pico(r, rw, h, hw, s):
        t = (r[:, None] - s * h[None, :]).ravel()
        w = np.minimum(rw[:, None], hw[None, :]).ravel()
        b = np.round(t / passo).astype(np.int64)
        u, inv = np.unique(b, return_inverse=True)
        acc = np.bincount(inv, weights=w)
        k = int(np.argmax(acc))
        # soma da vizinhança (±1 caixa) para robustez
        return acc[k], u[k] * passo
    melhor = None
    for s in escalas:
        ax, tx = pico(rx, rwx, hx, hwx, s)
        ay, ty = pico(ry, rwy, hy, hwy, s)
        nota = ax + ay
        if melhor is None or nota > melhor[0]:
            melhor = (nota, s, tx, ty)
    nota, s, tx, ty = melhor
    # refina: mínimos quadrados com as linhas casadas (até 1 pt)
    def pares(r, h, t):
        out = []
        for c in h:
            d = np.abs(r - (s * c + t))
            i = int(np.argmin(d))
            if d[i] < 1.0:
                out.append((c, r[i]))
        return out
    px, py = pares(rx, hx, tx), pares(ry, hy, ty)
    if len(px) > 5 and len(py) > 5:
        A = []; B = []
        for c, r in px:
            A.append([c, 1, 0]); B.append(r)
        for c, r in py:
            A.append([c, 0, 1]); B.append(r)
        sol, *_ = np.linalg.lstsq(np.array(A), np.array(B), rcond=None)
        s, tx, ty = (float(v) for v in sol)
        res = np.array(B) - np.array(A) @ sol
        rms = float(np.sqrt((res ** 2).mean()))
    else:
        rms = None
    total = rwx.sum() + rwy.sum()
    return s, tx, ty, {"casado": round(float(nota / total), 3), "pares": (len(px), len(py)), "rms_pt": rms}


def linhas_paredes_modelo(dados, vista):
    """Faces das paredes do modelo (coordenadas do PDF arquitetônico)."""
    m = next(v["m_por_pt"] for v in dados["vistas"] if v["id"] == vista)
    hs, vs = [], []
    for p in dados["paredes"]:
        if p["vista"] != vista:
            continue
        e = p["eixo"]
        t = p["espessura_m"] / m / 2
        L = math.dist(e[:2], e[2:])
        if p["o"] == "h":
            for d in (-t, t):
                hs.append((e[1] + d, min(e[0], e[2]), max(e[0], e[2]), L))
        else:
            for d in (-t, t):
                vs.append((e[0] + d, min(e[1], e[3]), max(e[1], e[3]), L))
    return hs, vs


def plantas(pg, tx, nomes, folga=25.0, altura_max=1300.0):
    """Regiões das plantas da folha: o aglomerado de linhas finas de parede logo acima de cada título.
    nomes: {texto do título: nome do pavimento no modelo}."""
    import numpy as np
    from skimage.measure import label, regionprops
    from skimage.morphology import dilation, footprint_rectangle
    W, H_ = pg.rect.width, pg.rect.height
    esc = 0.25                                    # 4 pt por pixel
    hs, vs = _linhas_eixo(linhas_finas(pg, (0, 0, W, H_)), minimo=15)
    hs = [x for x in hs if x[3] < 1100]           # sem a moldura da folha
    vs = [x for x in vs if x[3] < 1100]
    out = []
    for t in tx:
        if t["t"] not in nomes or t["size"] < 12:
            continue
        topo, base = t["r"][1] - altura_max, t["r"][1] - 4
        img = np.zeros((int(H_ * esc) + 2, int(W * esc) + 2), bool)
        for y, a, b, _ in hs:
            if topo < y < base:
                img[int(y * esc), int(a * esc):int(b * esc) + 1] = True
        for x, a, b, _ in vs:
            a, b = max(a, topo), min(b, base)
            if b > a:
                img[int(a * esc):int(b * esc) + 1, int(x * esc)] = True
        img = dilation(img, footprint_rectangle((int(folga * esc) * 2 + 1, int(folga * esc) * 2 + 1)))
        melhor = None
        for rp in regionprops(label(img)):
            if rp.area * 16 < 150 * 150:
                continue
            y0, x0, y1, x1 = (v / esc for v in rp.bbox)
            if x0 - 5 <= t["c"][0] <= x1 + 5:
                d = t["r"][1] - y1
                if melhor is None or d < melhor[0]:
                    melhor = (d, (x0 + folga - 5, y0 + folga - 5, x1 - folga + 5, min(y1 - folga + 5, base)))
        if melhor:
            out.append({"titulo": t["t"], "pavimento": nomes[t["t"]], "caixa": melhor[1]})
    return out


DIRECOES = {"+x": (1.0, 0.0), "-x": (-1.0, 0.0), "+y": (0.0, 1.0), "-y": (0.0, -1.0)}


def corridas(mascara, caixa, P, m_pt, maximo_m=6.0, ppp=PPP, lado_px=3, lacuna_pt=7.0):
    """Quanto o tubo da planta corre a partir do ponto P em cada direção (m)."""
    out = {}
    for nome, (dx, dy) in DIRECOES.items():
        L, ultimo, falha = 0.0, 0.0, 0.0
        while L * m_pt < maximo_m:
            x = int(round((P[0] + dx * L - caixa[0]) * ppp))
            y = int(round((P[1] + dy * L - caixa[1]) * ppp))
            ok = 0 <= y < mascara.shape[0] and 0 <= x < mascara.shape[1] and \
                mascara[max(0, y - lado_px):y + lado_px + 1, max(0, x - lado_px):x + lado_px + 1].any()
            if ok:
                ultimo, falha = L, 0.0
            else:
                falha += 0.5
                if falha > lacuna_pt:
                    break
            L += 0.5
        out[nome] = ultimo * m_pt
    return out


def escolher_direcao(run: dict, smin: float, smax: float):
    """Direção da planta que corresponde a +s do isométrico: a que melhor explica as corridas do tubo."""
    opostos = {"+x": "-x", "-x": "+x", "+y": "-y", "-y": "+y"}
    mais, menos = max(smax, 0.0), max(-smin, 0.0)
    notas = sorted((abs(run[u] - mais) + abs(run[opostos[u]] - menos), u) for u in DIRECOES)
    return notas[0][1], notas[0][0], notas


# ----------------------------------------------------------------------------------------------
# Tabelas do projetista
# ----------------------------------------------------------------------------------------------
def _num(t):
    t = t.strip().replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def tabela_projetista(tx):
    """Tabelas 'Conexões', 'Registros e Válvulas' e 'Tubos Rígidos' da folha (a primeira que aparecer)."""
    linhas = defaultdict(list)
    for t in tx:
        linhas[round(t["c"][1] * 2) / 2].append(t)
    out = {"tubos": {}, "conexoes": {}, "registros": {}}
    usados = set()
    for t in tx:
        d = t["t"]
        if not (("TIGRE" in d or "Hidrômetro" in d or d.startswith(("Tubo Soldável", "Tubo Série"))) and len(d) > 12):
            continue
        row = [u for u in tx if abs(u["c"][1] - t["c"][1]) < 2.0 and abs(u["c"][0] - t["c"][0]) < 600]
        esq = sorted((u for u in row if t["r"][0] - 170 < u["c"][0] < t["r"][0]), key=lambda u: -u["c"][0])
        dir_ = sorted((u for u in row if u["c"][0] > t["r"][2]), key=lambda u: u["c"][0])
        if d.startswith(("Tubo Soldável", "Tubo Série")):
            dn = next((_num(u["t"].replace("mm", "")) for u in dir_ if "mm" in u["t"]), None)
            L = next((_num(u["t"]) for u in esq if _num(u["t"]) is not None), None)
            if dn and L is not None and int(dn) not in out["tubos"]:
                out["tubos"][int(dn)] = L
            continue
        qtd = next((_num(u["t"]) for u in esq if _num(u["t"]) is not None), None)
        cod = next((u["t"] for u in dir_ if RX_COD.match(u["t"])), None)
        if qtd is None or not cod:
            continue
        chave = (cod, d)
        if chave in usados:
            continue
        usados.add(chave)
        grupo = "registros" if int(cod) >= 70 else "conexoes"
        out[grupo].setdefault(cod, []).append({"qtd": qtd, "descricao": d})
    return out


# ----------------------------------------------------------------------------------------------
# Montagem: isométricos de coluna + plantas -> rede no modelo
# ----------------------------------------------------------------------------------------------
NOMES_PLANTA = {"Sub-Solo": "Sub-Solo", "Subsolo": "Sub-Solo", "Pavimento Térreo": "Pavimento Térreo", "1ºPavimento": "1ºPavimento",
                "2ºPavimento": "2ºPavimento", "3ºPavimento": "3ºPavimento", "4ºPavimento": "4ºPavimento",
                "5ºPavimento": "5ºPavimento", "Cobertura": "Cobertura"}


def pav_de(z, niveis):
    cands = [(zz, n) for n, zz in niveis.items() if zz <= z + 0.02]
    return max(cands)[1] if cands else min((zz, n) for n, zz in niveis.items())[1]


def ler_agua_fria(pdf, dados: dict, log=print) -> dict:
    import numpy as np
    doc = pymupdf.open(pdf)
    niveis = niveis_do_modelo(dados)
    vistas_arq = {v["titulo"]: v for v in dados["vistas"]}
    ref_tipo = next(v["id"] for v in dados["vistas"] if v["titulo"] == "1ºPavimento")
    avisos = []
    # 1. isométricos de coluna e tabelas
    isos, tabela = [], None
    textos_pag = {}
    for pg in doc:
        tx = textos_pag[pg.number] = textos(pg)
        if tabela is None:
            tb = tabela_projetista(tx)
            if tb["tubos"]:
                tabela = tb
        if not any(t["t"].startswith("Tipo ") and t["size"] > 14 for t in tx):
            continue
        cxs, excl = caixas_vistas(pg, tx)
        for cx in cxs:
            r = ler_coluna(pg, cx, tx, excl, niveis)
            cols = sorted(set(c.replace(" ", "") for c in r["colunas"]))
            r["coluna"] = cols[0] if len(cols) == 1 else (cols[0] if cols else "?")
            if len(cols) != 1:
                avisos.append(f"{r['titulo']}: colunas no isométrico {cols}")
            isos.append(r)
            log(f"  isométrico {r['titulo']} ({r['coluna']}): {len(r['trechos'])} trechos, {len(r['repetidos'])} rótulos repetidos, "
                f"pisos {len(r['pisos'])}, escala {r['k']:.1f} pt/m, fator horizontal {r['f_h']:.3f}")
    # 2. plantas: registro sobre a arquitetura, pontos das colunas, máscara dos tubos
    plantas_out, pontos = [], defaultdict(dict)        # pontos[col][pav] = (x, y) na arquitetura
    mascaras = {}
    for pg in doc:
        tx = textos_pag[pg.number]
        for p in plantas(pg, tx, NOMES_PLANTA):
            cx = p["caixa"]
            fin = linhas_finas(pg, cx)
            hh, hv = _linhas_eixo(fin)
            va = vistas_arq.get(p["pavimento"], vistas_arq.get("5ºPavimento"))
            rh, rv = linhas_paredes_modelo(dados, va["id"])
            s, txx, tyy, info = registrar(rh, rv, hh, hv, escalas=np.arange(0.997, 1.0035, 0.0001))
            T = (s, txx, tyy)
            bal = balões([t for t in tx if dentro(t["c"], cx)], fin, pontos=pontos_marcados(pg, cx))
            for b in bal:
                if b["ponto"]:
                    X, Y = b["ponto"]
                    pontos[b["coluna"]][p["pavimento"]] = (s * X + txx, s * Y + tyy, b["diametro"], (X, Y))
            if p["pavimento"] in niveis and p["pavimento"] != "Cobertura":
                mascaras[p["pavimento"]] = (pg.number, cx, T)
            plantas_out.append({"pavimento": p["pavimento"], "pagina": pg.number + 1, "vista_arq": va["id"], "escala": round(s, 5),
                                "desloc": [round(txx, 2), round(tyy, 2)], "casado": info["casado"], "pares": info["pares"],
                                "rms_mm": round(info["rms_pt"] * va["m_por_pt"] * 1000, 1) if info["rms_pt"] else None,
                                "baloes": len(bal)})
            log(f"  planta {p['pavimento']} (pág. {pg.number + 1}) -> {va['id']}: escala {s:.5f}, "
                f"erro {plantas_out[-1]['rms_mm']} mm, {len(bal)} balões")
    # 3. colunas: posição = mediana entre os andares tipo (todos no sistema do 1º pavimento)
    colunas = {}
    for c, d in pontos.items():
        tipos = [v for k, v in d.items() if k.endswith("ºPavimento") or k == "Cobertura"]
        if not tipos:
            continue
        mx = float(np.median([v[0] for v in tipos])); my = float(np.median([v[1] for v in tipos]))
        desv = {k: round(math.dist((v[0], v[1]), (mx, my)) * vistas_arq["1ºPavimento"]["m_por_pt"] * 1000, 1)
                for k, v in d.items() if k.endswith("ºPavimento") or k == "Cobertura"}
        colunas[c] = {"id": c, "xy": [round(mx, 2), round(my, 2)], "vista": ref_tipo, "desvio_mm": desv,
                      "diametros": {k: v[2] for k, v in d.items()}, "outros": {k: [round(v[0], 2), round(v[1], 2)] for k, v in d.items()
                                                                                  if not (k.endswith("ºPavimento") or k == "Cobertura")}}
        fora = {k: v for k, v in desv.items() if v > 30}
        if fora:
            avisos.append(f"coluna {c}: balão fora da prumada em {fora} (mm) — usada a mediana")
    # 4. trechos no modelo
    m_tipo = vistas_arq["1ºPavimento"]["m_por_pt"]
    renders = {}
    trechos, curtos, conexoes, cobertura, direcoes = [], [], [], [], {}
    for r in isos:
        c = r["coluna"]
        if c not in colunas:
            avisos.append(f"{r['titulo']}: coluna {c} sem posição na planta")
            continue
        C = colunas[c]["xy"]
        # direção do ramal por andar; escala horizontal calibrada pela planta (alcance do ramal × tubo da planta)
        dir_pav, calib = {}, []
        for pav in {pav_de((t["geo"][0][1] + t["geo"][1][1]) / 2, niveis) for t in r["trechos"] if t["geo"]}:
            hs = [t for t in r["trechos"] if t["geo"] and t.get("eixo") in ("h", "x")
                  and pav_de((t["geo"][0][1] + t["geo"][1][1]) / 2, niveis) == pav]
            if not hs or pav not in mascaras:
                continue
            smin = min(min(g[0][0], g[1][0]) for g in (t["geo"] for t in hs))
            smax = max(max(g[0][0], g[1][0]) for g in (t["geo"] for t in hs))
            pn, cx, T = mascaras[pav]
            if pav not in renders:
                renders[pav] = mascara_tubos(render(doc[pn], cx))
            ponto = pontos[c].get(pav)
            P = ponto[3] if ponto else ((C[0] - T[1]) / T[0], (C[1] - T[2]) / T[0])
            run = corridas(renders[pav], cx, P, m_tipo * T[0])
            u, erro, notas = escolher_direcao(run, smin, smax)
            dir_pav[pav] = (DIRECOES[u], u, round(erro, 3), round(notas[1][0] - erro, 3))
            opostos = {"+x": "-x", "-x": "+x", "+y": "-y", "-y": "+y"}
            alcance, corre = (smax, run[u]) if smax >= -smin else (-smin, run[opostos[u]])
            if alcance > 0.25 and corre > 0.2:
                calib.append(alcance / (corre + 0.015))
        # os andares tipo são iguais: direção da maioria quando a do andar não é clara (margem < 0,20 m)
        if dir_pav:
            maioria = Counter(v[1] for v in dir_pav.values()).most_common(1)[0][0]
            for k, v in list(dir_pav.items()):
                if v[1] != maioria and v[3] < 0.20:
                    avisos.append(f"{c} {k}: direção do ramal {v[1]} trocada pela dos outros andares ({maioria}), margem {v[3]:.2f} m")
                    dir_pav[k] = (DIRECOES[maioria], maioria, v[2], v[3])
        direcoes[c] = {k: {"u": v[1], "erro_m": float(v[2]), "margem_m": float(v[3])} for k, v in dir_pav.items()}
        g = sorted(calib)[len(calib) // 2] if calib else 1.0
        if calib and 0.85 < g < 1.15:
            r["f_planta"] = round(g * r["f_h"], 4)
            for t in r["trechos"]:
                if t["geo"]:
                    t["geo"] = tuple((round(a / g, 4), b) for a, b in t["geo"])
            for cn in r["conexoes"]:
                cn["no"] = (round(cn["no"][0] / g, 4), cn["no"][1])
        else:
            r["f_planta"] = None
            if calib:
                avisos.append(f"{r['titulo']}: escala horizontal pela planta fora do esperado ({g:.3f}); mantida a dos rótulos")
        u_padrao = next(iter(dir_pav.values()))[0] if dir_pav else (1.0, 0.0)

        def ponto3(s, z):
            pav = pav_de(z, niveis)
            u = dir_pav.get(pav, (u_padrao,))[0]
            return [round(C[0] + s * u[0] / m_tipo, 2), round(C[1] + s * u[1] / m_tipo, 2), round(z, 3)]
        n = 0
        for t in r["trechos"]:
            base = {"col": c, "dn": t["dn"], "L": t["L"], "origem": f"{r['titulo']} (pág. {r['pagina']})", "como": t["como"]}
            if t["geo"]:
                (s0, z0), (s1, z1) = t["geo"]
                zm = (z0 + z1) / 2
                pav = pav_de(zm, niveis)
                if pav == "Cobertura" or min(z0, z1) >= niveis["Cobertura"] - 0.01:
                    cobertura.append({**base, "pav": "Cobertura", "s": [s0, s1], "z": [z0, z1]})
                    continue
                n += 1
                trechos.append({**base, "id": f"{c}-{n:03d}", "pav": pav, "eixo": t.get("eixo"),
                                "a": ponto3(s0, z0), "b": ponto3(s1, z1), "desenho_m": t.get("desenho_m")})
            else:
                zr = t.get("z_rotulo")
                pav = pav_de(zr, niveis) if zr is not None else "?"
                if pav == "Cobertura":
                    cobertura.append({**base, "pav": pav})
                    continue
                curtos.append({**base, "pav": pav})
        for cn in r["conexoes"]:
            s, z = cn["no"]
            pav = pav_de(z, niveis)
            if pav == "Cobertura":
                cobertura.append({"col": c, "cod": cn["cod"], "pav": pav, "origem": r["titulo"]})
                continue
            conexoes.append({"col": c, "cod": cn["cod"], "pav": pav, "p": ponto3(s, z), "origem": f"{r['titulo']} (pág. {r['pagina']})"})
    saida = {"pdf": Path(pdf).name, "niveis": niveis, "isometricos": [
                {k: r.get(k) for k in ("titulo", "pagina", "coluna", "k", "alfa", "f_h", "f_planta", "residuos_piso_m", "avisos")}
                | {"pisos": [p[0] for p in r["pisos"]], "n_trechos": len(r["trechos"]), "repetidos": r["repetidos"],
                   "sem_rotulo": r["sem_rotulo"]} for r in isos],
            "plantas": plantas_out, "colunas": list(colunas.values()), "direcoes": direcoes,
            "trechos": trechos, "curtos": curtos, "conexoes": conexoes, "cobertura_nos_isometricos": cobertura,
            "tabela_projetista": tabela, "avisos": avisos}
    saida["auditoria"] = auditar(saida, dados)
    log("  barrilete, térreo, subsolo e colunas do prédio:")
    saida["complemento"] = complementar(doc, dados, saida, log=lambda t: log("  " + t))
    return limpo(saida)


# ----------------------------------------------------------------------------------------------
# Auditoria: tubos × alvenaria e ambientes
# ----------------------------------------------------------------------------------------------
def auditar(af: dict, dados: dict) -> dict:
    """Para cada trecho dos apartamentos (sistema do 1º pavimento, paredes do andar tipo):
      - horizontal dentro de parede estrutural = rasgo horizontal (NBR 16868: só com previsão no projeto
        estrutural) -> conflito; dentro de parede de vedação = rasgo em vedação (ok, prever no orçamento);
      - vertical dentro de parede estrutural: passa pelo furo do bloco; conflito se cair num ponto de graute
        (encontro, ponta ou lateral de vão: o furo fica cheio de concreto);
      - horizontal que cruza a faixa de verga/contraverga de um vão (canaleta grauteada) -> conflito;
      - coluna: em parede, shaft ou aparente.
    Devolve {"trechos": [...por trecho...], "resumo": {...}, "conflitos": [...]}."""
    from shapely.geometry import LineString, Point, Polygon
    from .insumos import pontos_verticais_xy
    v1 = next(v for v in dados["vistas"] if v["titulo"] == "1ºPavimento")
    m = v1["m_por_pt"]
    paredes = [p for p in dados["paredes"] if p["vista"] == v1["id"]]
    faixas = []
    for p in paredes:
        e = p["eixo"]
        L = LineString([e[:2], e[2:]])
        faixas.append((p, L, L.buffer(p["espessura_m"] / m / 2 + 0.01 / m, cap_style="flat")))
    graute = [Point(x, y) for x, y, _ in pontos_verticais_xy(paredes, m)]
    ambs = [(a["nome"], a.get("unidade"), Polygon(a["poligono"]).buffer(0)) for a in dados["ambientes"]
            if a["vista"] == v1["id"] and a["poligono"]]
    pd = dados["premissas"]["pe_direito_m"].get("1ºPavimento", 2.6)
    out, conflitos = [], []
    for t in af["trechos"]:
        if t["pav"] not in ("1ºPavimento", "2ºPavimento", "3ºPavimento", "4ºPavimento", "5ºPavimento"):
            continue
        a, b = t["a"], t["b"]
        z0 = af["niveis"][t["pav"]]
        seg = LineString([a[:2], b[:2]])
        vertical = seg.length * m < 0.02
        reg = {"id": t["id"], "col": t["col"], "pav": t["pav"], "dn": t["dn"], "L": t["L"], "vertical": vertical}
        if vertical:
            P = Point(a[:2])
            dentro = [(p, f) for p, L, f in faixas if f.contains(P)]
            reg["parede"] = dentro[0][0]["id"] if dentro else None
            reg["tipo_parede"] = dentro[0][0]["tipo"] if dentro else None
            g = min((P.distance(q) * m for q in graute), default=9)
            reg["graute_m"] = round(g, 3)
            if dentro and dentro[0][0]["tipo"] == "estrutural" and g < 0.10:
                conflitos.append({**reg, "conflito": f"tubo vertical a {g * 100:.0f} cm de ponto de graute da parede {dentro[0][0]['id']}"})
        else:
            emb = []
            for p, L, f in faixas:
                inter = seg.intersection(f).length
                if inter > 0.6 * seg.length and inter * m > 0.05:
                    emb.append(p)
            reg["parede"] = emb[0]["id"] if emb else None
            reg["tipo_parede"] = emb[0]["tipo"] if emb else None
            zm = (a[2] + b[2]) / 2 - z0
            if emb and emb[0]["tipo"] == "estrutural":
                conflitos.append({**reg, "conflito": f"tubo horizontal embutido na parede estrutural {emb[0]['id']} a {zm:.2f} m do piso (rasgo horizontal)"})
            # verga/contraverga dos vãos da parede: faixa da canaleta sobre o vão (e sob a janela)
            for p in emb:
                for vv in p["vaos"]:
                    topo = (vv.get("altura_m") or 2.1) + (0 if vv["tipo"] == "porta" else (vv.get("peitoril_m") or 1.0))
                    base = 0 if vv["tipo"] == "porta" else (vv.get("peitoril_m") or 1.0)
                    for zc, nome in ((topo, "verga"), (base, "contraverga")):
                        if nome == "contraverga" and vv["tipo"] == "porta":
                            continue
                        if zc - 0.02 <= zm <= zc + 0.21:
                            conflitos.append({**reg, "conflito": f"tubo horizontal na altura da {nome} do vão de {vv['largura_m']:.2f} m da parede {p['id']}"})
        # ambiente onde está o tubo (ou os dois lados da parede)
        P = seg.interpolate(0.5, normalized=True)
        perto = sorted((g.distance(P) * m, n, u) for n, u, g in ambs)
        reg["ambientes"] = [f"{u + ' · ' if u else ''}{n}" for d, n, u in perto if d < 0.20][:2]
        out.append(reg)
    from collections import Counter as _C
    resumo = {
        "horizontais": sum(1 for r in out if not r["vertical"]),
        "horizontais em estrutural": sum(1 for r in out if not r["vertical"] and r["tipo_parede"] == "estrutural"),
        "horizontais em vedação": sum(1 for r in out if not r["vertical"] and r["tipo_parede"] == "vedação"),
        "horizontais fora de parede": sum(1 for r in out if not r["vertical"] and not r["tipo_parede"]),
        "verticais": sum(1 for r in out if r["vertical"]),
        "verticais em estrutural": sum(1 for r in out if r["vertical"] and r["tipo_parede"] == "estrutural"),
        "verticais em vedação": sum(1 for r in out if r["vertical"] and r["tipo_parede"] == "vedação"),
        "verticais fora de parede": sum(1 for r in out if r["vertical"] and not r["tipo_parede"]),
        "conflitos": len(conflitos), "tipos de conflito": dict(_C(c["conflito"].split(" a ")[0].split(" embutido")[0] for c in conflitos)),
    }
    return {"trechos": out, "resumo": resumo, "conflitos": conflitos}


# ----------------------------------------------------------------------------------------------
# Conferência automática e saída limpa (JSON)
# ----------------------------------------------------------------------------------------------
def limpo(o):
    """Converte para tipos do Python (numpy, tuplas, chaves int) — JSON."""
    if isinstance(o, dict):
        return {str(k): limpo(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [limpo(v) for v in o]
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.integer):
        return int(o)
    return o


def _comodo(titulo):
    t = titulo.lower()
    return "banheiro" if "banheiro" in t else "cozinha" if "cozinha" in t else "gourmet" if ("gourmet" in t or "goumert" in t) else t


def conferir(af: dict) -> list[tuple[str, str, str, bool]]:
    out = []
    G = "Água fria"
    isos = af["isometricos"]
    res = max(abs(v) for i in isos for v in i["residuos_piso_m"].values()) * 1000
    out.append((G, "Isométricos: pisos × níveis da arquitetura",
                f"{len(isos)} isométricos de coluna, {sum(len(i['pisos']) for i in isos)} pisos pelas cotas; maior desvio {res:.1f} mm", res < 5))
    sem = [t for t in af["trechos"] + af["curtos"] if t.get("como") == "sem tubo"]
    n_rot = len(af["trechos"]) + len(af["curtos"]) + len(af["cobertura_nos_isometricos"]) + sum(len(i["repetidos"]) for i in isos)
    out.append((G, "Rótulos DN/comprimento ligados a um tubo", f"{n_rot - len(sem)} de {n_rot} rótulos", not sem))
    rep = sum(len(i["repetidos"]) for i in isos)
    out.append((G, "Rótulo repetido no mesmo tubo (contado uma vez)",
                f"{rep} rótulos: o trecho da coluna entre andares aparece rotulado nos dois andares do isométrico", True))
    # tipos A-D iguais andar a andar (mesmo cômodo)
    por = defaultdict(lambda: defaultdict(Counter))
    for t in af["trechos"] + af["curtos"]:
        tit = t["origem"].split(" (")[0]
        por[(_comodo(tit), t["pav"])][tit][(t["dn"], t["L"])] += 1
    for comodo in ("banheiro", "gourmet"):
        chaves = [k for k in por if k[0] == comodo and k[1].endswith("ºPavimento")]
        dif = [k[1] for k in chaves if len({tuple(sorted(c.items())) for c in por[k].values()}) > 1]
        out.append((G, f"{comodo.capitalize()}: tipos A a D iguais andar a andar",
                    "iguais nos 5 andares" if not dif else f"diferem em {', '.join(sorted(dif))} (conferir no isométrico)", not dif))
    # cozinhas: o tipo C é outro desenho (a coluna AF-09 desce até o térreo); A, B e D comparadas no total
    tot = defaultdict(Counter)
    for t in af["trechos"] + af["curtos"]:
        tit = t["origem"].split(" (")[0]
        if _comodo(tit) == "cozinha" and t["pav"].endswith("ºPavimento"):
            tot[tit][(t["dn"], t["L"])] += 1
    nomes = [n for n in tot if "Tipo C" not in n]
    if nomes:
        somas = {n: sum(L * q for (_, L), q in tot[n].items()) for n in nomes}
        amp = max(somas.values()) - min(somas.values())
        out.append((G, "Cozinha: tipos A, B e D (1º ao 5º)",
                    f"total de tubo {', '.join(f'{n[5]} {v:.2f} m' for n, v in sorted(somas.items()))}: diferença {amp:.2f} m "
                    f"(tubos curtos de 0,06 a 0,18 m sem rótulo em alguns andares do projeto; o C serve também o térreo)", amp < 0.5))
    desv = {c["id"]: max(c["desvio_mm"].values()) for c in af["colunas"] if c["desvio_mm"]}
    ruins = {k: v for k, v in desv.items() if v > 30}
    out.append((G, "Colunas no prumo (balões das plantas dos andares)",
                f"{len(desv)} colunas; maior desvio {max(desv.values()):.0f} mm" if not ruins else
                f"fora: {', '.join(f'{k} {v / 1000:.2f} m' for k, v in ruins.items())} (balão com chamada para outro ponto; usada a mediana)", not ruins))
    rms = max((p["rms_mm"] or 0) for p in af["plantas"])
    out.append((G, "Plantas registradas sobre a arquitetura", f"{len(af['plantas'])} plantas; maior erro médio {rms:.1f} mm", rms < 10))
    banh = [i for i in isos if _comodo(i["titulo"]) == "banheiro" and i.get("f_planta")]
    dif_f = max((abs(i["f_planta"] / i["f_h"] - 1) for i in banh), default=0)
    out.append((G, "Escala horizontal do isométrico: planta × rótulos", f"banheiros: diferença máxima {dif_f:.1%}", dif_f < 0.03))
    tab = (af.get("tabela_projetista") or {}).get("tubos") or {}
    comp = (af.get("complemento") or {}).get("trechos", [])
    if tab and comp:
        q = Counter()
        for t in af["trechos"] + af["curtos"] + comp:
            q[int(t["dn"])] += t["L"]
        tot_m, tot_t = sum(q.values()), sum(tab.values())
        difs = ", ".join(f"DN{k} {q.get(int(k), 0) - v:+.2f} m" for k, v in sorted(tab.items(), key=lambda kv: int(kv[0])))
        out.append((G, "Tubos: modelo × tabela do projetista",
                    f"{tot_m:.2f} m × {tot_t:.2f} m ({tot_m / tot_t - 1:+.1%}) · {difs}", abs(tot_m / tot_t - 1) < 0.02))
        cods = Counter(c["cod"] for c in af["conexoes"])
        for cs in (af["complemento"].get("codigos_plantas") or {}).values():
            cods.update(cs)
        tb = {k: sum(x["qtd"] for x in v) for k, v in {**af["tabela_projetista"]["conexoes"], **af["tabela_projetista"]["registros"]}.items()}
        iguais = [k for k in tb if cods.get(k, 0) == tb[k]]
        dif = {k: cods.get(k, 0) - tb[k] for k in tb if cods.get(k, 0) != tb[k]}
        out.append((G, "Conexões e registros: modelo × tabela do projetista",
                    f"{len(iguais)} de {len(tb)} códigos iguais; diferenças: " + ", ".join(f"{k} {int(v):+d}" for k, v in sorted(dif.items())),
                    len(iguais) >= 0.6 * len(tb)))
    au = af.get("auditoria")
    if au:
        r = au["resumo"]
        out.append((G, "Tubos × alvenaria estrutural",
                    f"{r['horizontais']} horizontais ({r['horizontais em vedação']} em vedação, {r['horizontais em estrutural']} em estrutural) · "
                    f"{r['verticais']} verticais ({r['verticais em vedação']} em vedação, {r['verticais em estrutural']} em estrutural) · "
                    f"{r['conflitos']} conflitos (rasgo horizontal em estrutural, graute, verga/contraverga)", r["conflitos"] == 0))
    return out


# ----------------------------------------------------------------------------------------------
# Barrilete, alimentação, extravasor, térreo e subsolo: plantas (horizontais) + isométricos (verticais)
# ----------------------------------------------------------------------------------------------
def _colineares(s1, s2, tol=1.5):
    a1, a2 = _ang(s1), _ang(s2)
    da = abs(a1 - a2)
    if min(da, 180 - da) > 3:
        return False
    return dist_ps(s2[0], (s1[0], (s1[0][0] + (s1[1][0] - s1[0][0]) * 50, s1[0][1] + (s1[1][1] - s1[0][1]) * 50))) < tol * 3 and \
        abs(((s2[0][0] - s1[0][0]) * -(s1[1][1] - s1[0][1]) + (s2[0][1] - s1[0][1]) * (s1[1][0] - s1[0][0])) / max(math.dist(*s1), 1e-9)) < tol


def _unicos_por_tubo(casa, segs, esc=None):
    """Um trecho por tubo: rótulo repetido no mesmo tubo desenhado conta uma vez. Com 'esc' (pt/m), dois
    rótulos iguais em pedaços colineares do mesmo tubo (o esqueleto quebra o tubo onde outra linha cruza)
    também contam uma vez, se os pedaços juntos cabem no comprimento do rótulo."""
    vistos, out, rep = {}, [], 0
    for ro, j, como, d in casa:
        if j is None:
            out.append((ro, j, como))
            continue
        chave = (ro["dn"], ro["L"])
        dup = False
        for jj in vistos.get(chave, []):
            if jj == j:
                dup = True
            elif esc and _colineares(segs[jj], segs[j]):
                pts = [*segs[jj], *segs[j]]
                vx, vy = segs[jj][1][0] - segs[jj][0][0], segs[jj][1][1] - segs[jj][0][1]
                n = math.hypot(vx, vy) or 1e-9
                proj = [((x - pts[0][0]) * vx + (y - pts[0][1]) * vy) / n for x, y in pts]
                if max(proj) - min(proj) <= ro["L"] * esc * 1.1 + 10:
                    dup = True
            if dup:
                break
        if dup:
            rep += 1
            continue
        vistos.setdefault(chave, []).append(j)
        out.append((ro, j, como))
    return out, rep


def rede_da_planta(pg, caixa, T, m_pt_planta):
    """Tubos de uma planta (x, y na arquitetura) com rótulo. Tubo desenhado bem mais curto que o rótulo
    é vertical (ou quase): vai para a lista de verticais."""
    esc = 1.0 / m_pt_planta                            # pt por metro na planta
    tx = [t for t in textos(pg) if dentro(t["c"], caixa)]
    a = render(pg, caixa)
    segs, _, _ = segmentos(a, caixa)
    rots, _ = rotulos(tx)
    casa = casar_rotulos(rots, segs, linhas_finas(pg, caixa), esc=esc)
    uni, rep = _unicos_por_tubo(casa, segs, esc=esc)
    s, tx_, ty_ = T
    conv = lambda P: [round(s * P[0] + tx_, 2), round(s * P[1] + ty_, 2)]
    horiz, vert = [], []
    for ro, j, como in uni:
        Ld = math.dist(*segs[j]) / esc if j is not None else 0.0
        item = {"dn": ro["dn"], "L": ro["L"], "como": como, "rotulo": conv(ro["c"]), "desenho_m": round(Ld, 3)}
        if j is not None and Ld >= 0.6 * ro["L"] - 0.05:
            item.update(a=conv(segs[j][0]), b=conv(segs[j][1]))
            horiz.append(item)
        else:
            vert.append(item)
    cods = Counter(t["t"] for t in tx if RX_COD.match(t["t"]) and t["size"] < 9)
    return {"horizontais": horiz, "verticais": vert, "repetidos": rep, "codigos": dict(cods)}


def verticais_do_isometrico(pg, caixa, excl):
    """Rótulos dos tubos verticais de um isométrico verdadeiro (barrilete, salão), um por tubo."""
    v = ler_vista(pg, caixa, textos(pg), excl)
    uni, rep = _unicos_por_tubo(v["rotulos"], v["segs"], esc=(v["esc"] or 100) * 1.25)
    out = []
    for ro, j, como in uni:
        if j is None:
            continue
        out.append({"dn": ro["dn"], "L": ro["L"], "como": como, "vertical": abs(abs(_ang(v["segs"][j])) - 90) < 3})
    return out, v["titulo"], rep


def complementar(doc, dados, af, log=print):
    """Acrescenta à rede o que não está nas prumadas dos apartamentos: barrilete (planta da cobertura),
    térreo e subsolo (plantas), alimentação e extravasor, e os tubos verticais que só aparecem nos
    isométricos (descidas do barrilete, salão de festas, hidrômetro). Cada tubo uma vez:
      - horizontais: planta (rótulo repetido no mesmo tubo conta uma vez);
      - verticais: o maior número de vezes que o mesmo (DN, comprimento) aparece numa fonte
        (planta ou isométrico), por andar/sistema — o mesmo tubo aparece em mais de uma vista."""
    vistas_arq = {v["titulo"]: v for v in dados["vistas"]}
    niveis = af["niveis"]
    extra, fontes = [], []
    planas = {}
    for p in af["plantas"]:
        if p["pavimento"] not in ("Cobertura", "Pavimento Térreo", "Sub-Solo"):
            continue
        pg = doc[p["pagina"] - 1]
        cx = next(q["caixa"] for q in plantas(pg, textos(pg), NOMES_PLANTA) if q["pavimento"] == p["pavimento"])
        va = vistas_arq.get(p["pavimento"], vistas_arq["5ºPavimento"])
        r = rede_da_planta(pg, cx, (p["escala"], *p["desloc"]), va["m_por_pt"] * p["escala"])
        r["vista"] = va["id"]
        planas[p["pavimento"]] = r
        fontes.append({"fonte": f"planta {p['pavimento']} (pág. {p['pagina']})", "horizontais": len(r["horizontais"]),
                       "verticais": len(r["verticais"]), "repetidos": r["repetidos"], "codigos": r["codigos"]})
    # isométricos verdadeiros (barrilete, salão de festas, hidrômetro)
    iso_vert, iso_hor = {}, {}
    for pg in doc:
        tx = textos(pg)
        tits = [t["t"] for t in tx if t["size"] > 14 and (t["t"].startswith("Barrilete") or t["t"] in ("Salão de Festas", "Hidrômetro"))]
        if not tits:
            continue
        tabs = regioes_tabela(tx)
        carimbo = [t["r"] for t in tx if t["t"].startswith("CUIDADOS DE EXECU")]
        excl = list(tabs) + [(c[0] - 5, c[1] - 12, 1e5, 1e5) for c in carimbo]
        for t in tx:
            if t["size"] > 14 and t["t"] in tits:
                # a vista é a folha toda menos tabelas e carimbo; no salão/hidrômetro, cada um no seu lado
                if t["t"] == "Hidrômetro":
                    cx = (0, t["r"][1] - 520, t["r"][2] + 120, t["r"][3])
                elif t["t"] == "Salão de Festas":
                    cx = (420, 60, pg.rect.width - 40, t["r"][3])
                else:
                    cx = (40, 40, pg.rect.width - 40, pg.rect.height - 40)
                todos, titulo, rep = verticais_do_isometrico(pg, cx, excl)
                iso_vert[t["t"]] = [x for x in todos if x["vertical"]]
                iso_hor[t["t"]] = [x for x in todos if not x["vertical"]]
                fontes.append({"fonte": f"isométrico {t['t']} (pág. {pg.number + 1})", "horizontais": len(iso_hor[t["t"]]),
                               "verticais": len(iso_vert[t["t"]]), "repetidos": rep})
    # Contagem, cada tubo uma vez (rótulo repetido no mesmo tubo já saiu em cada vista):
    #  A. horizontais: os da planta, com posição;
    #  B. verticais (< 3 m): o maior número de vezes que o (DN, comprimento) aparece como vertical numa vista
    #     (planta ou isométrico) do grupo;
    #  C. horizontais que só o isométrico mostra: o que passa do que a planta já tem (horizontal ou vertical);
    #  D. colunas que atravessam o prédio (>= 3 m: alimentação, extravasor, AF-13): uma vez no prédio, se
    #     ainda não entraram pelas prumadas dos apartamentos ou pela planta.
    ja_aptos = Counter((t["dn"], t["L"]) for t in af["trechos"] + af["curtos"])
    todos_planas = Counter((x["dn"], x["L"]) for r in planas.values() for x in r["horizontais"] + r["verticais"])
    hor_planas = Counter((x["dn"], x["L"]) for r in planas.values() for x in r["horizontais"])
    grupos = {"Cobertura": (["Cobertura"], [k for k in iso_vert if k.startswith("Barrilete")]),
              "Térreo e subsolo": (["Pavimento Térreo", "Sub-Solo"], [k for k in iso_vert if k in ("Salão de Festas", "Hidrômetro")])}
    longas, fonte_longa = set(), {}
    for nome, lst in [(f"planta {k}", v["verticais"]) for k, v in planas.items()] + \
                     [(f"isométrico {k}", v) for k, v in iso_vert.items()] + [(f"isométrico {k}", v) for k, v in iso_hor.items()]:
        for x in lst:
            k = (x["dn"], x["L"])
            if x["L"] >= 3.0 and not ja_aptos.get(k) and not hor_planas.get(k) and k not in longas:
                longas.add(k)
                fonte_longa[k] = nome
    for g, (pls, isos) in grupos.items():
        plan_all = Counter((x["dn"], x["L"]) for p in pls if p in planas for x in planas[p]["horizontais"] + planas[p]["verticais"])
        # A
        for pav in pls:
            r = planas.get(pav)
            if not r:
                continue
            # premissa: barrilete 10 cm sobre a laje; térreo a 2,50 m (forro); subsolo sob a laje do térreo
            z = {"Cobertura": niveis["Cobertura"] + 0.10, "Pavimento Térreo": niveis["Pavimento Térreo"] + 2.50}.get(pav, niveis["Pavimento Térreo"] - 0.30)
            for h in r["horizontais"]:
                extra.append({"grupo": g, "pav": pav, "dn": h["dn"], "L": h["L"], "a": [*h["a"], round(z, 3)], "b": [*h["b"], round(z, 3)],
                              "vista": r["vista"], "eixo": "h", "origem": f"planta {pav}", "como": h["como"], "altura": "premissa"})
        # B
        vert, fonte_v = Counter(), {}
        fontes_v = [(f"planta {p}", Counter((x["dn"], x["L"]) for x in planas[p]["verticais"])) for p in pls if p in planas] + \
                   [(f"isométrico {k}", Counter((x["dn"], x["L"]) for x in iso_vert.get(k, []))) for k in isos]
        for nome, c in fontes_v:
            for k, n in c.items():
                if k[1] < 3.0 and n > vert[k]:
                    vert[k], fonte_v[k] = n, nome
        if g == "Cobertura":                     # descida da coluna sob o barrilete: já está na prumada
            for k in list(vert):
                if k[1] in (0.61, 0.62):
                    vert[k] -= min(vert[k], ja_aptos.get(k, 0))
        for k, n in sorted(vert.items()):
            for _ in range(n):
                extra.append({"grupo": g, "pav": pls[0], "dn": k[0], "L": k[1], "eixo": "v", "origem": fonte_v[k], "como": "vertical",
                              "altura": "sem posição (quantitativo)"})
        # C
        so_iso, fonte_h = Counter(), {}
        for k_ in isos:
            c_ = Counter((x["dn"], x["L"]) for x in iso_hor.get(k_, []))
            for k, n in c_.items():
                if k[1] >= 3.0:
                    continue
                falta = n - plan_all.get(k, 0) - vert.get(k, 0)
                if falta > so_iso[k]:
                    so_iso[k], fonte_h[k] = falta, f"isométrico {k_}"
        for k, n in sorted(so_iso.items()):
            for _ in range(n):
                extra.append({"grupo": g, "pav": pls[0], "dn": k[0], "L": k[1], "eixo": "h", "origem": fonte_h[k] + " (sem rótulo na planta)",
                              "como": "só no isométrico", "altura": "sem posição (quantitativo)"})
    # D
    for k in sorted(longas):
        # coluna do prédio = vertical que atravessa andares (>= 10 m: alimentação, extravasor, AF-13)
        no_barrilete = k[1] < 10 and ("Cobertura" in fonte_longa[k] or "Barrilete" in fonte_longa[k])
        extra.append({"grupo": "Cobertura" if no_barrilete else "Colunas do prédio", "pav": "Cobertura" if no_barrilete else "Sub-Solo",
                      "dn": k[0], "L": k[1], "eixo": "v", "origem": fonte_longa[k], "como": "coluna" if not no_barrilete else "vertical",
                      "altura": "sem posição (quantitativo)"})
    q = Counter()
    for t in extra:
        q[(t["grupo"], t["dn"])] += t["L"]
    for (g, dn), v in sorted(q.items()):
        log(f"  {g}: DN{dn} {v:.2f} m")
    return {"trechos": extra, "fontes": fontes, "codigos_plantas": {k: v["codigos"] for k, v in planas.items()}}


def caixas_por_titulo(pg, tx, prefixos=("Tipo ", "Coletores"), margem=70):
    """Vistas da folha agrupadas pelo título (o desenho de uma vista pode ter vários pedaços de tubo
    separados). Cada faixa de tubo vai para o título mais perto na horizontal (abaixo dela)."""
    faixas = vistas(pg, altura_min=60)
    tits = [t for t in tx if t["size"] > 14 and t["t"].startswith(prefixos)]
    tabs = regioes_tabela(tx)
    carimbo = [t["r"] for t in tx if t["t"].startswith("CUIDADOS DE EXECU")]
    excl = list(tabs) + [(c[0] - 5, c[1] - 12, 1e5, 1e5) for c in carimbo]
    if not tits:
        return [], excl, []
    grupos = defaultdict(list)
    for f in faixas:
        cx_ = (f[0] + f[2]) / 2
        if any(dentro((cx_, (f[1] + f[3]) / 2), e) for e in excl):
            continue
        cands = [t for t in tits if t["r"][1] > f[1]]           # título abaixo do topo da faixa
        if not cands:
            continue
        def dx(t):
            return 0.0 if f[0] <= t["c"][0] <= f[2] else min(abs(t["c"][0] - f[0]), abs(t["c"][0] - f[2]))
        t = min(cands, key=lambda t: (dx(t), t["r"][1] - f[3]))
        if dx(t) < 400:
            grupos[id(t)].append(f)
    caixas, nomes = [], []
    ordem = sorted((t for t in tits if id(t) in grupos), key=lambda t: t["c"][0])
    uni = []
    for t in ordem:
        fs = grupos[id(t)]
        uni.append([min(f[0] for f in fs), min(f[1] for f in fs), max(f[2] for f in fs), max(max(f[3] for f in fs), t["r"][3])])
    for k, (t, u) in enumerate(zip(ordem, uni)):
        x0 = u[0] - margem if k == 0 else max(u[0] - margem, (uni[k - 1][2] + u[0]) / 2)
        x1 = u[2] + margem if k == len(uni) - 1 else min(u[2] + margem, (u[2] + uni[k + 1][0]) / 2)
        caixas.append((x0, u[1] - 40, x1, u[3] + 10))
        nomes.append(t["t"])
    return caixas, excl, nomes
