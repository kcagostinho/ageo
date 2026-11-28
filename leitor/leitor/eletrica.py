"""Projeto elétrico: pontos, eletrodutos, quadros e alimentadores lidos das plantas; lista de materiais e quadros
de carga lidos das tabelas.

O PDF não tem camadas e é todo preto. Separação pela espessura do traço (medida no projeto-piloto):
  - 0,84 pt: eletrodutos (curvas entre os pontos, interrompidas nos símbolos), prumadas e setas;
  - 0,57 pt: símbolos (caixinha de 5,8 pt na parede, triângulos das tomadas, círculos dos interruptores e das
    luminárias, quadro) e tracinhos da fiação;
  - 0,15 pt: arquitetura de fundo (usada para registrar a planta sobre o modelo).
Simbologia (legenda de cada prancha):
  - luminária de teto: círculo de ~32 pt; arandela: meia-lua de 30 pt com traço reto;
  - tomada: triângulo de ~20×24 pt — vazado = universal 2P+T a 0,30 m; meio cheio = 2P+T 10 A a 1,10 m;
    cheio = 2P+T 20 A a 2,20 m (com "CHG" é o ponto do chuveiro, com placa cega);
  - interruptor: círculo de 13,5 pt a 1,10 m — hachurado = paralelo, com traço = 2 teclas; dois círculos juntos =
    2 simples + 1 paralelo (3 teclas); sensor de presença a 2,20 m;
  - quadro de distribuição: retângulo de 10,8 × 32,6 pt meio cheio, a 1,50 m;
  - caixa de passagem 100×100×80: quadrado com X (CXnn); prumadas com seta e bolinha;
  - térreo: caixas de medição (QMnn, ampulheta, 1,60 m), entrada de serviço (ALx), alimentadores pontilhados
    (AL → QM e QM → caixa da prumada → QD), tomada 20 A do portão (círculo com M/1F, 0,30 m);
  - ponto de força do elevador: círculo com potência ≥ 1000 W e "ELM" (F+N+T a 0,30 m).
Saída (ler_eletrica): plantas registradas, prumadas, alimentadores, listas, quadros de carga, rede 3D e conferência.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from pathlib import Path

import pymupdf

W_ELET, W_SIMB, W_ARQ = 0.84, 0.57, 0.15
# alturas dos pontos acima do piso, pela legenda de cada planta (m)
ALTURAS = {"tomada_baixa": 0.30, "tomada_media": 1.10, "tomada_alta": 2.20, "chuveiro": 2.20, "interruptor": 1.10,
           "sensor": 2.20, "quadro": 1.50, "medicao": 1.60, "forca": 0.30, "entrada": 1.60,
           "arandela": 2.00}            # arandela: premissa (a legenda não dá a altura)
# premissas do 3D (não estão no projeto)
Z_LAJE = 0.075          # eletroduto cheio (teto): no meio da laje de 15 cm acima do pé-direito
Z_PISO = -0.05          # eletroduto pontilhado (alimentador): no piso (contrapiso/laje de baixo)
H_CX = 2.00             # caixa de passagem da prumada: altura acima do piso (premissa: é a altura que fecha os
                        # eletrodutos de 2" e 3" do térreo com a lista do projetista)
NOMES_PLANTA = {"1ºPavimento": "1ºPavimento", "2ºPavimento": "2ºPavimento", "3ºPavimento": "3ºPavimento",
                "4ºPavimento": "4ºPavimento", "5ºPavimento": "5ºPavimento", "Térreo": "Pavimento Térreo", "Subsolo": "Sub-Solo"}


def _w(d):
    return round(d.get("width") or 0, 2)


def _pts(d, R):
    """Pontos do traçado (curvas pelos pontos de controle extremos e médios) em coordenadas exibidas."""
    out = []
    for it in d["items"]:
        if it[0] == "l":
            seg = [it[1] * R, it[2] * R]
        elif it[0] == "c":
            p0, p1, p2, p3 = (it[k] * R for k in range(1, 5))
            seg = []
            for t in (0, 0.25, 0.5, 0.75, 1):
                u = 1 - t
                seg.append(pymupdf.Point(u ** 3 * p0.x + 3 * u * u * t * p1.x + 3 * u * t * t * p2.x + t ** 3 * p3.x,
                                         u ** 3 * p0.y + 3 * u * u * t * p1.y + 3 * u * t * t * p2.y + t ** 3 * p3.y))
        elif it[0] == "qu":
            q = it[1]
            seg = [q.ul * R, q.ur * R, q.lr * R, q.ll * R, q.ul * R]
        elif it[0] == "re":
            r = it[1] * R
            seg = [r.tl, r.tr, r.br, r.bl, r.tl]
        else:
            continue
        for p in seg:
            if not out or math.dist(out[-1], (p.x, p.y)) > 0.01:
                out.append((p.x, p.y))
    return out


def textos(pg):
    """Spans com centro e caixa em coordenadas exibidas."""
    R = pg.rotation_matrix
    out = []
    for b in pg.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            dx, dy = l.get("dir", (1, 0))
            dv = pymupdf.Point(dx, dy) * R - pymupdf.Point(0, 0) * R          # direção da escrita na folha exibida
            for s in l["spans"]:
                t = s["text"].strip()
                if not t:
                    continue
                r = pymupdf.Rect(s["bbox"]) * R
                o = pymupdf.Point(s["origin"]) * R                                  # linha de base (alinha as tabelas)
                out.append({"t": t, "r": (r.x0, r.y0, r.x1, r.y1), "c": ((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2), "size": round(s["size"], 1),
                            "dir": (round(dv.x, 4), round(dv.y, 4)), "o": (o.x, o.y)})
    return out


def desenhos(pg):
    R = pg.rotation_matrix
    out = []
    for d in pg.get_drawings():
        r = d["rect"] * R
        out.append({"tipo": d["type"], "w": _w(d), "its": "".join(it[0] for it in d["items"]), "r": (r.x0, r.y0, r.x1, r.y1),
                    "pts": _pts(d, R)})
    return out


def dentro(c, r, folga=0.0):
    return r[0] - folga <= c[0] <= r[2] + folga and r[1] - folga <= c[1] <= r[3] + folga


def centro(r):
    return ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)


def dist_ps(p, a, b):
    vx, vy = b[0] - a[0], b[1] - a[1]
    L2 = vx * vx + vy * vy
    t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / L2))
    return math.dist(p, (a[0] + t * vx, a[1] + t * vy))


def comprimento(pts):
    return sum(math.dist(a, b) for a, b in zip(pts[:-1], pts[1:]))


# ----------------------------------------------------------------------------------------------
# Planta: região, símbolos, eletrodutos e alimentadores
# ----------------------------------------------------------------------------------------------
def _tam(d):
    return d["r"][2] - d["r"][0], d["r"][3] - d["r"][1]


def regiao(tx, dr):
    """Região da planta na folha (à esquerda dos quadros de carga / da lista) e o que fica fora (legenda)."""
    tits = [t for t in tx if t["t"] in NOMES_PLANTA and t["size"] > 20]
    if not tits:
        return None, None, []
    tit = tits[0]
    circ = [t["r"][0] for t in tx if t["t"] == "Circuito"]
    lm = [t["r"][0] for t in tx if t["t"].startswith("Lista de Materiais")]
    x1 = min(circ) - 25 if circ else min(lm) - 130          # sem quadros na folha: antes da moldura da lista
    reg = (30, 30, x1, tit["r"][3] + 10)
    excl = []
    leg = next((t for t in tx if t["t"].startswith("Legenda -")), None)
    if leg and dentro(leg["c"], reg):
        fr = [d["r"] for d in dr if d["tipo"] == "s" and dentro(leg["c"], d["r"]) and (d["r"][2] - d["r"][0]) < 900 and (d["r"][3] - d["r"][1]) > 100]
        if fr:
            excl.append(min(fr, key=lambda r: (r[2] - r[0]) * (r[3] - r[1])))
    excl.append(tuple(v + d for v, d in zip(tit["r"], (-80, -30, 260, 60))))       # título da planta e escala
    return NOMES_PLANTA[tit["t"]], reg, excl


def _quadrado(d, lado=(4.8, 6.8)):
    w, h = _tam(d)
    if not (d["tipo"] == "s" and d["w"] == W_SIMB and lado[0] < w < lado[1] and lado[0] < h < lado[1] and len(d["pts"]) >= 4):
        return False
    x0, y0, x1, y1 = d["r"]
    cantos = {(abs(px - x0) < 0.6, abs(py - y0) < 0.6) for px, py in d["pts"]
              if min(abs(px - x0), abs(px - x1)) < 0.6 and min(abs(py - y0), abs(py - y1)) < 0.6}
    return len(cantos) >= 4


def simbolos(D):
    """Pontos da planta: caixas na parede (tomadas, interruptores, arandelas), luminárias de teto, sensores,
    quadros e caixas de passagem."""
    linhas = [d for d in D if d["tipo"] == "s" and d["w"] == W_SIMB and d["its"] == "l"]
    fills = [d for d in D if d["tipo"] == "fs"]
    circ14 = [d for d in D if d["tipo"] == "s" and d["its"] == "cccc" and d["w"] == W_SIMB and 12 < _tam(d)[0] < 16]
    circ32 = [d for d in D if d["tipo"] == "s" and d["its"] == "cccc" and d["w"] == W_SIMB and 27 < _tam(d)[0] < 37]
    meias = [d for d in D if d["tipo"] == "s" and d["its"] == "cc" and 28 < max(_tam(d)) < 34 and 13 < min(_tam(d)) < 18]
    tracos = [d for d in D if d["tipo"] == "s" and d["w"] == W_SIMB and 15 < max(_tam(d)) < 27 and d["its"] in ("l", "ll", "lll")]
    caixas = []
    for d in D:
        if _quadrado(d):
            c = centro(d["r"])
            if not any(math.dist(c, b) < 2 for b in caixas):
                caixas.append(c)

    def classifica(b, S):
        ref = S or b
        dv = None if S is None else ((S[0] - b[0]) / (math.dist(S, b) or 1), (S[1] - b[1]) / (math.dist(S, b) or 1))

        def frente(p, lo=2, hi=28):
            if dv is None:
                return math.dist(p, b) < 30
            v = (p[0] - ref[0], p[1] - ref[1])
            L = math.hypot(*v)
            return lo <= L <= hi and (v[0] * dv[0] + v[1] * dv[1]) / (L or 1) > 0.5
        c_ = [d for d in circ14 if dentro(ref, d["r"], 2.5)]
        m_ = [d for d in meias if dentro(ref, d["r"], 2.5)]
        fs_ = [x for x in fills if frente(centro(x["r"]))]
        fmax = max(fs_, key=lambda x: _tam(x)[0] * _tam(x)[1], default=None)
        g_ = [d for d in circ32 if S is not None and dentro(ref, d["r"], 2.5)]
        if g_ and not c_:
            return "tomada_baixa", "20 A (motor)", centro(g_[0]["r"])
        if c_:
            cs = []
            for d in circ14:                          # círculos vizinhos (2 interruptores); concêntricos contam uma vez
                c = centro(d["r"])
                if any(math.dist(c, centro(x["r"])) < 16 for x in c_) and not any(math.dist(c, centro(x["r"])) < 3 for x in cs):
                    cs.append(d)
            hach = [sum(1 for x in fills if dentro(centro(x["r"]), c["r"], 0.5)) >= 4 for c in cs]
            traco = [any(dentro(centro(l["r"]), c["r"], 0.5) and abs(math.dist(l["pts"][0], l["pts"][-1]) - _tam(c)[1]) < 2.5 for l in linhas) for c in cs]
            if len(cs) >= 2:
                sub = "2 simples + paralelo (3 teclas)"
            elif hach[0]:
                sub = "paralelo 1 tecla"
            elif traco[0]:
                sub = "simples 2 teclas"
            else:
                sub = "simples 1 tecla"
            return "interruptor", sub, centro(cs[0]["r"])
        if m_:
            return "arandela", "", centro(m_[0]["r"])
        if fmax is not None and min(_tam(fmax)) > 15:
            return "tomada_alta", "", centro(fmax["r"])
        if fmax is not None and min(_tam(fmax)) > 8:
            return "tomada_media", "", centro(fmax["r"])
        tr = [d for d in tracos if frente(centro(d["r"]))]
        if tr:
            return "tomada_baixa", "", centro(tr[0]["r"])
        return None, "", ref
    pontos = []
    for b in caixas:
        hs = [l for l in linhas if min(math.dist(b, p) for p in (l["pts"][0], l["pts"][-1])) < 4.6 and 6 < comprimento(l["pts"]) < 45]
        cands = []
        for l in sorted(hs, key=lambda l: -comprimento(l["pts"])):
            p0, p1 = l["pts"][0], l["pts"][-1]
            cands.append(p1 if math.dist(b, p0) < math.dist(b, p1) else p0)
        cands.append(None)
        res = (None, "", b)
        for S in cands:
            res = classifica(b, S)
            if res[0]:
                break
        pontos.append({"tipo": res[0] or "?", "sub": res[1], "xy": b, "simb": res[2]})
    # luminárias de teto (o círculo grande da tomada do motor não conta)
    for d in circ32:
        c = centro(d["r"])
        if not any((p["tipo"] == "luminaria" or p["sub"] == "20 A (motor)") and math.dist(p.get("simb") if p["tipo"] != "luminaria" else p["xy"], c) < 3 for p in pontos):
            pontos.append({"tipo": "luminaria", "sub": "teto", "xy": c, "simb": c, "raio": _tam(d)[0] / 2})
    # sensores de presença: meia-lua sem caixinha, com a placa de 4 × 30 pt na parede
    placas = [d for d in D if d["tipo"] == "s" and d["w"] == W_SIMB and d["its"] in ("lll", "llll") and 3 < min(_tam(d)) < 6 and 27 < max(_tam(d)) < 34]
    for m in meias:
        if any(p["tipo"] == "arandela" and dentro(p["simb"], m["r"], 3) for p in pontos):
            continue
        pl = min(placas, key=lambda d: math.dist(centro(d["r"]), centro(m["r"])), default=None)
        if pl is not None and math.dist(centro(pl["r"]), centro(m["r"])) < 30:
            pontos.append({"tipo": "sensor", "sub": "presença", "xy": centro(pl["r"]), "simb": centro(m["r"]), "rect": pl["r"]})
    # quadros (retângulo 10,8 × 32,6 meio cheio) e caixas de medição (ampulheta)
    for d in D:
        w, h = _tam(d)
        if d["tipo"] == "s" and d["w"] == W_SIMB and d["its"].startswith("qu") and 8 < min(w, h) < 14 and 28 < max(w, h) < 38:
            pontos.append({"tipo": "quadro", "sub": "", "xy": centro(d["r"]), "simb": centro(d["r"]), "rect": d["r"]})
    # caixas de passagem: quadrado de ~29,5 pt com X
    for d in D:
        w, h = _tam(d)
        if d["tipo"] == "s" and d["w"] == W_SIMB and d["its"] == "lllll" and 26 < w < 33 and 26 < h < 33:
            c = centro(d["r"])
            if not any(p["tipo"] == "cx" and math.dist(p["xy"], c) < 3 for p in pontos):
                pontos.append({"tipo": "cx", "sub": "100x100x80", "xy": c, "simb": c, "rect": d["r"]})
    return pontos


def eletrodutos(D, excl_r=()):
    """Traços de 0,84 pt (eletrodutos). As setas e bolinhas das prumadas (dentro das caixas de passagem) ficam fora."""
    out = []
    for d in D:
        if d["tipo"] != "s" or d["w"] != W_ELET or len(d["pts"]) < 2:
            continue
        w, h = _tam(d)
        if d["its"] == "cccc" and max(w, h) < 14:
            continue                                  # bolinha da prumada
        if any(dentro(centro(d["r"]), r, 1) for r in excl_r) and max(w, h) < 32:
            continue                                  # seta da prumada dentro da caixa de passagem
        L = comprimento(d["pts"])
        if L < 4:
            continue
        out.append({"pts": d["pts"], "L": L})
    return out


def ligacoes_curtas(D, P):
    """Trecho curto de traço fino entre duas caixinhas vizinhas (tomadas lado a lado): é eletroduto."""
    cx = [p["xy"] for p in P if p["tipo"] not in ("luminaria", "quadro", "cx", "sensor")]
    placas = [p["rect"] for p in P if p["tipo"] == "sensor"]
    out = []
    for d in D:
        if d["tipo"] != "s" or d["w"] != W_SIMB or d["its"] != "l" or len(d["pts"]) < 2:
            continue
        a, b = d["pts"][0], d["pts"][-1]
        L = math.dist(a, b)
        if L < 6 or L > 60:
            continue
        ia = [k for k, c in enumerate(cx) if math.dist(a, c) < 4.6]
        ib = [k for k, c in enumerate(cx) if math.dist(b, c) < 4.6]
        pa = [k for k, r in enumerate(placas) if dentro(a, r, 2)]
        pb = [k for k, r in enumerate(placas) if dentro(b, r, 2)]
        if (ia and ib and ia[0] != ib[0]) or (ia and pb) or (pa and ib):
            out.append({"pts": [a, b], "L": L, "curto": True})
    return out


def _simplifica(pts, tol=0.35):
    """Douglas-Peucker: tira os pontinhos alinhados, mantém o traçado (curvas incluídas)."""
    if len(pts) < 3:
        return list(pts)
    a, b = pts[0], pts[-1]
    k, dm = 0, -1.0
    for i in range(1, len(pts) - 1):
        d = dist_ps(pts[i], a, b)
        if d > dm:
            k, dm = i, d
    if dm <= tol:
        return [a, b]
    return _simplifica(pts[:k + 1], tol)[:-1] + _simplifica(pts[k:], tol)


def _quinas(c, ang=60.0, k=3):
    """Parte a sequência onde ela vira mais que `ang` graus (fim de uma curva e começo de outra no mesmo ponto)."""
    if len(c) < 2 * k + 2:
        return [c]
    cand = []
    for i in range(k, len(c) - k):
        ax, ay = c[i][0] - c[i - k][0], c[i][1] - c[i - k][1]
        bx, by = c[i + k][0] - c[i][0], c[i + k][1] - c[i][1]
        na, nb = math.hypot(ax, ay), math.hypot(bx, by)
        if na < 1e-6 or nb < 1e-6:
            continue
        cos = max(-1.0, min(1.0, (ax * bx + ay * by) / (na * nb)))
        g = math.degrees(math.acos(cos))
        if g > ang:
            cand.append((i, g))
    cortes, grupo = [], []
    for i, g in cand:                          # um corte por quina: o ponto de maior giro de cada grupo
        if grupo and i - grupo[-1][0] > 1:
            cortes.append(max(grupo, key=lambda x: x[1])[0])
            grupo = []
        grupo.append((i, g))
    if grupo:
        cortes.append(max(grupo, key=lambda x: x[1])[0])
    out, a = [], 0
    for i in cortes:
        out.append(c[a:i + 1])
        a = i
    out.append(c[a:])
    return [x for x in out if len(x) > 1]


def pontilhados(D, passo=3.0, minimo=20, nos=()):
    """Alimentadores desenhados com pontinhos (traços de comprimento zero). O PDF desenha os pontinhos na ordem do
    traçado, então cada curva é a sequência de pontinhos consecutivos a menos de um passo; isso atravessa os
    cruzamentos sem trocar de curva. A sequência é partida onde vira de repente (duas curvas desenhadas em seguida
    que se encontram num ponto, como na entrada de serviço) e duas pontas que se encontram sozinhas (sem uma
    terceira ali) são emendadas; onde três ou mais pontas se encontram é um nó (quadro, entrada): não emenda."""
    seq = [d["pts"][0] for d in D if d["tipo"] == "s" and d["its"] == "l" and _tam(d)[0] < 0.3 and _tam(d)[1] < 0.3 and d["pts"]]
    cad = []
    for q in seq:
        if cad and math.dist(cad[-1][-1], q) <= passo:
            cad[-1].append(q)
        else:
            cad.append([q])
    cad = [x for c in cad for x in _quinas(c)]
    mudou = True
    while mudou:
        mudou = False
        pontas = [(k, e, cad[k][-1 if e else 0]) for k in range(len(cad)) for e in (0, 1)]
        for k, e, q in pontas:
            junto = [(k2, e2) for k2, e2, q2 in pontas if (k2, e2) != (k, e) and math.dist(q, q2) <= passo]
            if len(junto) != 1 or junto[0][0] == k or any(dentro(q, r, 6) for r in nos):
                continue
            k2, e2 = junto[0]
            q2 = cad[k2][-1 if e2 else 0]
            if sum(1 for k3, e3, q3 in pontas if (k3, e3) not in ((k, e), (k2, e2)) and math.dist(q2, q3) <= passo):
                continue                       # a outra ponta também está num nó
            A = cad[k] if e else cad[k][::-1]          # A termina na ponta
            B = cad[k2] if not e2 else cad[k2][::-1]   # B começa na ponta
            cad[k] = A + B
            cad.pop(k2)
            mudou = True
            break
    out = []
    for c in cad:
        if len(c) < minimo:
            continue
        out.append({"pts": _simplifica(c), "L": comprimento(c)})
    return out


RX_NUM = re.compile(r"^\d{1,2}$")
RX_POT = re.compile(r"^\d{2,5}$")
RX_LET = re.compile(r"^[a-z]{1,3}$")
RX_LAB = re.compile(r"^(2PT|CHG|ELM|ARC\d+|POR|M|1F)$")


def anotar(P, T, raio=55.0):
    """Textos dos símbolos (corpo ≥ 19): circuito, potência, comando (letras) e rótulo (2PT, CHG, ARC…).
    Casamento global pelo mais perto: cada símbolo recebe no máximo um texto de cada tipo (o interruptor pode ter
    várias letras, uma por tecla); assim duas tomadas lado a lado não disputam o mesmo número."""
    aceita = {"luminaria": ("num", "pot", "let"), "arandela": ("num", "pot", "let"), "interruptor": ("let",), "sensor": ("let",),
              "tomada_baixa": ("num", "pot", "lab"), "tomada_media": ("num", "pot", "lab"), "tomada_alta": ("num", "pot", "lab"),
              "forca": ("num", "pot", "lab"), "?": ("num", "pot", "lab")}
    toks = []
    for t in T:
        if t["size"] < 19:
            continue
        for tok in t["t"].split():
            m = re.match(r"^(2PT)(\d+)$", tok)
            for x in ([m.group(1), m.group(2)] if m else [tok]):
                if RX_LAB.match(x):
                    k = "lab"
                elif RX_NUM.match(x) and int(x) <= 40:
                    k = "num"
                elif RX_POT.match(x):
                    k = "pot"
                elif RX_LET.match(x):
                    k = "let"
                else:
                    continue
                toks.append((x, k, t["c"]))
    pares = sorted((math.dist(p["simb"], c), it, ip) for it, (x, k, c) in enumerate(toks) for ip, p in enumerate(P)
                   if k in aceita.get(p["tipo"], ()) and math.dist(p["simb"], c) < raio)
    usado, tem = set(), defaultdict(set)
    txt = defaultdict(lambda: defaultdict(list))
    for d, it, ip in pares:
        x, k, c = toks[it]
        if it in usado:
            continue
        multi = k == "let" and P[ip]["tipo"] == "interruptor"
        if k in tem[ip] and not multi:
            continue
        usado.add(it)
        tem[ip].add(k)
        txt[ip][k].append(x)
    for ip, p in enumerate(P):
        tx = txt[ip]
        p["circuito"] = int(tx["num"][0]) if tx["num"] else None
        p["pot"] = int(tx["pot"][0]) if tx["pot"] else None
        p["comando"] = "".join(sorted(set("".join(tx["let"])))) or None
        p["rotulo"] = " ".join(tx["lab"]) or None
        if p["tipo"] == "interruptor" and p["sub"].startswith("paralelo") and p["comando"] and len(p["comando"]) >= 2:
            p["sub"] = f"paralelo {len(p['comando'])} teclas"
    return P


def rede(P, EL, PT):
    """Liga cada ponta de eletroduto ao ponto onde chega. Devolve as ligações e as pontas soltas.
    Empate (a ponta encosta em duas caixas vizinhas, como na fileira de quadros de medição): fica a caixa que está
    à frente, no sentido em que o eletroduto chega."""
    def no(q, alim=False, ante=None):
        cands = []
        for i, p in enumerate(P):
            if "raio" in p:                       # luminária de teto e ponto de força desenhado como círculo
                d = math.dist(q, p["xy"]) - p["raio"]
                lim = 16
            elif p["tipo"] in ("quadro", "cx", "entrada"):
                r = p["rect"]
                d = 0 if dentro(q, r) else min(dist_ps(q, a, b) for a, b in (((r[0], r[1]), (r[2], r[1])), ((r[2], r[1]), (r[2], r[3])),
                                                                              ((r[2], r[3]), (r[0], r[3])), ((r[0], r[3]), (r[0], r[1]))))
                lim = (18 if alim else 15) if p["tipo"] == "cx" else 9
            elif p["tipo"] == "sensor":
                d = min(math.dist(q, p["xy"]) - 15, math.dist(q, p["simb"]) - 15)
                lim = 9
            else:
                # chega na caixinha ou no próprio símbolo (triângulo da tomada, círculo do interruptor)
                d = min(math.dist(q, p["xy"]) - 3, math.dist(q, p["simb"]) - 14)
                lim = 7
            if d <= lim:
                cands.append((d, i))
        if not cands:
            return None
        d0 = min(cands)[0]
        empate = [(d, i) for d, i in cands if d <= d0 + 1.5]
        if len(empate) > 1 and ante is not None:
            vx, vy = q[0] - ante[0], q[1] - ante[1]
            nv = math.hypot(vx, vy) or 1.0

            def frente(i):
                c = P[i]["xy"]
                wx, wy = c[0] - q[0], c[1] - q[1]
                return (vx * wx + vy * wy) / (nv * (math.hypot(wx, wy) or 1.0))
            return max(empate, key=lambda x: frente(x[1]))[1]
        return min(cands)[1]
    lig, soltas = [], []
    for k, e in enumerate(EL + PT):
        alim = k >= len(EL)
        a = no(e["pts"][0], alim, e["pts"][1])
        b = no(e["pts"][-1], alim, e["pts"][-2])
        lig.append((a, b))
        for q, n in ((e["pts"][0], a), (e["pts"][-1], b)):
            if n is None:
                soltas.append((k, q))
    return lig, soltas


# ----------------------------------------------------------------------------------------------
# Leitura completa: todas as plantas, registradas sobre a arquitetura
# ----------------------------------------------------------------------------------------------
RX_DIAM = re.compile(r'ø\s*([\d.,/ ]+)"')
AFAST_ROT = 8.3         # afastamento do rótulo de bitola ao seu eletroduto (pt), medido no feixe do térreo
POL = {'1/2': 0.5, '3/4': 0.75, '1': 1.0, '1.1/4': 1.25, '1.1/2': 1.5, '2': 2.0, '2.1/2': 2.5, '3': 3.0, '4': 4.0}


def _linhas_arq(D):
    from .hidraulica import _linhas_eixo
    pls = [d["pts"] for d in D if d["tipo"] == "s" and d["w"] == W_ARQ and len(d["pts"]) > 1]
    return _linhas_eixo(pls, minimo=30)


def _rotulos_diam(T):
    out = []
    for t in T:
        for m in RX_DIAM.finditer(t["t"].replace(" ", "")):
            v = m.group(1).strip()
            if v in POL:
                out.append((v, t["c"], t.get("dir", (1, 0))))
    return out


def _diametros(rd, tubos_pts, n_ramais, lim=20.0):
    """Rótulos ø → eletrodutos. Custo de um rótulo num traço: quanto a distância foge do afastamento padrão do
    projetista (8,3 pt, ou em cima do traço) + desalinhamento (o rótulo é escrito paralelo ao traço) + lado (o texto
    fica pendurado embaixo do traço: rótulo entre dois traços paralelos é do de cima) + tipo (bitola de
    alimentador, ≥ 1.1/2", prefere o pontilhado; de ramal, o cheio).
    Casamento ótimo um a um (no feixe de alimentadores do térreo há um rótulo por traço e os rótulos ficam entre
    traços vizinhos); rótulo que sobra vai para o traço mais barato se ele estiver sem rótulo ou com a mesma bitola.
    Devolve {índice do eletroduto: diâmetro}."""
    import numpy as np
    from scipy.optimize import linear_sum_assignment
    if not rd or not tubos_pts:
        return {}
    C = np.full((len(rd), len(tubos_pts)), 1e6)
    for il, (v, c, dv) in enumerate(rd):
        grande = POL[v] >= 1.5
        for k, pts in enumerate(tubos_pts):
            pena = 10.0 if (k >= n_ramais) != grande else 0.0
            for a, b in zip(pts[:-1], pts[1:]):
                d = dist_ps(c, a, b)
                if d > lim:
                    continue
                L = math.dist(a, b) or 1
                sen = abs(((b[0] - a[0]) * dv[1] - (b[1] - a[1]) * dv[0]) / L)
                t = max(0.0, min(1.0, ((c[0] - a[0]) * (b[0] - a[0]) + (c[1] - a[1]) * (b[1] - a[1])) / (L * L)))
                wx, wy = c[0] - (a[0] + t * (b[0] - a[0])), c[1] - (a[1] + t * (b[1] - a[1]))
                lado = 6.0 if d > 2.5 and wx * dv[1] - wy * dv[0] > 0 else 0.0
                C[il, k] = min(C[il, k], min(abs(d - AFAST_ROT), d) + 30 * sen + pena + lado)
    # colunas extras: o rótulo pode ficar sem traço (custo alto, só se não houver traço livre razoável)
    nada = np.full((len(rd), len(rd)), 40.0)
    lin, col = linear_sum_assignment(np.hstack([C, nada]))
    out, sobra = {}, []
    for il, k in zip(lin, col):
        if k < len(tubos_pts) and C[il, k] < 1e5:
            out[int(k)] = rd[il][0]
        else:
            sobra.append(il)
    for il in sobra:
        k = int(np.argmin(C[il]))
        if C[il, k] < 1e5 and out.get(k, rd[il][0]) == rd[il][0]:
            out[k] = rd[il][0]
    return out


def _nomes(P, T):
    """QDxx / QMxx / CXxx / ALx mais perto de cada quadro e caixa de passagem (texto de corpo ~11)."""
    rot = []
    for t in T:
        if t["size"] < 10:
            continue
        ws = t["t"].split()
        if not all(re.fullmatch(r"(QD|QM|CX|AL)\d+", w) for w in ws):
            continue
        dx, dy = t.get("dir", (1, 0))
        L = abs(dx) * (t["r"][2] - t["r"][0]) + abs(dy) * (t["r"][3] - t["r"][1])     # comprimento no sentido da escrita
        for k, w in enumerate(ws):              # posição de cada nome ao longo do texto, no sentido da escrita
            u = -L / 2 + L * (k + 0.5) / len(ws)
            rot.append({"t": w, "c": (t["c"][0] + dx * u, t["c"][1] + dy * u)})
    usados = set()
    for tipo, pref in (("quadro", ("QD", "QM", "AL")), ("cx", ("CX",))):
        pares = sorted((math.dist(p["xy"], t["c"]), ip, it) for ip, p in enumerate(P) if p["tipo"] == tipo
                       for it, t in enumerate(rot) if t["t"].startswith(pref) and math.dist(p["xy"], t["c"]) < (120 if tipo == "cx" else 80))
        feito = set()
        for d, ip, it in pares:
            if ip in feito or it in usados:
                continue
            P[ip]["nome"] = rot[it]["t"]
            feito.add(ip)
            usados.add(it)


def _setas_ao_quadro(D, P):
    """Fileira de caixas de passagem encostada num quadro (térreo: CX24/25/26 sobre o QD22): as setas das prumadas
    ligam as caixas da fileira entre si e no quadro. Cada caixa dessa fileira liga no quadro por um eletroduto curto
    (o caminho pelas setas). Fileira cujas setas não chegam num quadro (sobe/desce nos andares) é só símbolo."""
    cx = [i for i, p in enumerate(P) if p["tipo"] == "cx"]
    qd = [i for i, p in enumerate(P) if p["tipo"] == "quadro"]
    viz = defaultdict(list)
    for d in D:
        if d["tipo"] != "s" or d["w"] != W_ELET or d["its"] not in ("ll", "llll") or len(d["pts"]) < 2:
            continue
        base = d["pts"][0]
        ib = next((i for i in cx if math.dist(P[i]["xy"], base) < 3), None)
        if ib is None:
            continue
        tip = max(d["pts"], key=lambda q: math.dist(q, base))
        L = math.dist(tip, base)
        if not 20 < L < 40:
            continue
        alvo = next((i for i in qd if dentro(tip, P[i]["rect"], 3)), None)
        if alvo is None:
            alvo = next((i for i in cx if i != ib and dentro(tip, P[i]["rect"], 1)), None)
        if alvo is not None:
            viz[ib].append((alvo, L, tip))
            viz[alvo].append((ib, L, tip))
    out = []
    for ib in cx:
        if ib not in viz:
            continue
        dist, ant, fila = {ib: 0.0}, {ib: None}, [ib]
        while fila:                                 # caminho mais curto pelas setas até um quadro
            k = min(fila, key=lambda x: dist[x])
            fila.remove(k)
            if P[k]["tipo"] == "quadro":
                cam, j = [], k
                while j is not None:
                    cam.append(P[j]["xy"])
                    j = ant[j]
                out.append({"pts": cam[::-1], "L": dist[k], "seta": True})
                break
            for j, L, _ in viz[k]:
                if j not in dist or dist[k] + L < dist[j]:
                    dist[j], ant[j] = dist[k] + L, k
                    fila.append(j)
    return out


def altura(p):
    """Altura do ponto acima do piso (m), pela legenda; None = no teto (luminária) ou a definir (caixa de passagem)."""
    t, nome = p["tipo"], p.get("nome") or ""
    if t == "quadro":
        return ALTURAS["medicao"] if nome.startswith("QM") else ALTURAS["quadro"]
    if t == "forca":
        return ALTURAS["forca"]
    if t in ("luminaria", "cx"):
        return None
    return ALTURAS.get(t, ALTURAS["tomada_baixa"])


def ler_planta(pg, dados, log=print):
    import numpy as np
    from .hidraulica import linhas_paredes_modelo, registrar
    tx, dr = textos(pg), desenhos(pg)
    pav, reg, excl = regiao(tx, dr)
    if not pav:
        return None
    na = lambda c: dentro(c, reg) and not any(dentro(c, x, 2) for x in excl)
    D = [d for d in dr if na(centro(d["r"]))]
    T = [t for t in tx if na(t["c"])]
    va = next(v for v in dados["vistas"] if v["titulo"] == pav)
    rh, rv = linhas_paredes_modelo(dados, va["id"])
    hh, hv = _linhas_arq(D)
    s, txx, tyy, info = registrar(rh, rv, hh, hv, escalas=np.arange(0.47, 0.53, 0.0002))
    m = s * va["m_por_pt"]
    conv = lambda p: [round(s * p[0] + txx, 3), round(s * p[1] + tyy, 3)]
    P = simbolos(D)
    anotar(P, T)
    _nomes(P, [t for t in tx if dentro(t["c"], reg)])         # nomes junto ao título também (QM3, QM7)
    for p in P:                                  # círculo grande com potência de força (motor do elevador) não é luminária
        if p["tipo"] == "luminaria" and (p.get("pot") or 0) >= 1000:
            p["tipo"], p["sub"] = "forca", "motor do elevador" if any(t["t"] == "ELM" and math.dist(t["c"], p["xy"]) < 90 for t in T) else "ponto de força"
    # entrada de serviço (ALx): retângulo de ~17 × 42 pt com o círculo e a seta, ao lado do nome
    for t in tx:
        if re.fullmatch(r"AL\d+", t["t"]) and dentro(t["c"], reg):
            rs = [d["r"] for d in D if d["tipo"] == "s" and d["its"] == "qu" and 14 < min(_tam(d)) < 22 and 36 < max(_tam(d)) < 50
                  and math.dist(centro(d["r"]), t["c"]) < 70]
            if rs:
                r = min(rs, key=lambda r: math.dist(centro(r), t["c"]))
                P.append({"tipo": "entrada", "sub": "entrada de serviço aérea", "xy": centro(r), "simb": centro(r), "rect": r,
                          "nome": t["t"], "circuito": None, "pot": None, "comando": None, "rotulo": None})
    cxr = [p["rect"] for p in P if p["tipo"] == "cx"]
    EL = eletrodutos(D, cxr) + ligacoes_curtas(D, P) + _setas_ao_quadro(D, P)
    PT = pontilhados(D, nos=[p["rect"] for p in P if p["tipo"] in ("quadro", "cx", "entrada")])
    lig, soltas = rede(P, EL, PT)
    # alimentador que chega na fileira de caixas de passagem: o desenho não deixa claro em qual das caixas
    # vizinhas ele entra; vale a numeração do projeto (QMn / QDn sobe pela CXn, como em todos os andares)
    por_nome = {p.get("nome"): i for i, p in enumerate(P) if p.get("nome")}
    renomeados = []
    for k in range(len(EL), len(EL) + len(PT)):
        a, b = lig[k]
        for x, y, lado in ((a, b, 1), (b, a, 0)):
            if x is None or y is None or P[x]["tipo"] != "quadro" or P[y]["tipo"] != "cx":
                continue
            n = re.sub(r"\D", "", P[x].get("nome") or "")
            certo = por_nome.get(f"CX{n}")
            if not n or certo is None or certo == y:
                continue
            q = PT[k - len(EL)]["pts"][-1 if lado else 0]
            r = P[certo]["rect"]
            if math.dist(q, (min(max(q[0], r[0]), r[2]), min(max(q[1], r[1]), r[3]))) < 35:
                renomeados.append((P[x]["nome"], P[y]["nome"], P[certo]["nome"]))
                lig[k] = (a, certo) if lado else (certo, b)
    rd = _rotulos_diam(T)
    dm = _diametros(rd, [e["pts"] for e in EL + PT], len(EL))
    tubos = []
    for k, e in enumerate(EL + PT):
        alim = k >= len(EL)
        diam = dm.get(k, "1.1/2" if alim else "3/4")
        tubos.append({"pts": [conv(q) for q in e["pts"]], "L": round(e["L"] * m, 3), "diam": diam,
                      "tipo": "alimentador" if alim else ("curto" if e.get("curto") else ("seta" if e.get("seta") else "ramal")), "a": lig[k][0], "b": lig[k][1]})
    # prumadas: caixas de passagem com bolinha (o eletroduto atravessa o andar)
    bol = [centro(d["r"]) for d in D if d["tipo"] == "s" and d["w"] == W_ELET and d["its"] == "cccc" and _tam(d)[0] < 14]
    for p in P:
        if p["tipo"] == "cx":
            p["prumada"] = any(dentro(b, p["rect"], 1) for b in bol)
            p["diam"] = min(((math.dist(c, p["xy"]), v) for v, c, _ in rd), default=(99, "1.1/2"))[1] if p["prumada"] else None
    # apartamento / quadro de cada ponto: componente da rede que contém o quadro
    viz = defaultdict(set)
    for a, b in lig:
        if a is not None and b is not None:
            viz[a].add(b)
            viz[b].add(a)
    dono = {}
    for iq, q in enumerate(P):
        if q["tipo"] != "quadro":
            continue
        pilha, vistos = [iq], {iq}
        while pilha:
            k = pilha.pop()
            for j in viz[k]:
                if j in vistos or P[j]["tipo"] in ("quadro", "cx", "entrada"):
                    continue
                vistos.add(j)
                pilha.append(j)
        for j in vistos - {iq}:
            dono.setdefault(j, q.get("nome") or f"Q{iq}")
    pontos = []
    for i, p in enumerate(P):
        if p["tipo"] == "tomada_alta" and (p.get("rotulo") or "").startswith("CHG"):
            p["sub"] = "chuveiro"
        if p["sub"] == "20 A (motor)" and "POR" in (p.get("rotulo") or ""):
            p["sub"] = "20 A (motor do portão)"
        h = altura(p)
        pontos.append({"i": i, "tipo": p["tipo"], "sub": p["sub"], "xy": conv(p["xy"]), "h": h, "circuito": p.get("circuito"),
                       "pot": p.get("pot"), "comando": p.get("comando"), "rotulo": p.get("rotulo"), "nome": p.get("nome"),
                       "quadro": dono.get(i), "prumada": p.get("prumada"), "diam": p.get("diam")})
    log(f"  planta {pav} (pág. {pg.number + 1}): registro {s:.5f} ({info['rms_pt'] * va['m_por_pt'] * 1000 if info['rms_pt'] else 0:.1f} mm), "
        f"{len(pontos)} pontos, {len(tubos)} eletrodutos ({sum(t['L'] for t in tubos):.1f} m), {len(soltas)} pontas soltas")
    return {"pavimento": pav, "pagina": pg.number + 1, "vista": va["id"], "escala": round(s, 5), "m_por_pt": m, "reg": [s, txx, tyy],
            "pela_numeracao": renomeados,
            "rms_mm": round(info["rms_pt"] * va["m_por_pt"] * 1000, 1) if info["rms_pt"] else None,
            "pontos": pontos, "tubos": tubos, "soltas": [[k, conv(q)] for k, q in soltas]}


# ----------------------------------------------------------------------------------------------
# O prédio: plantas juntas, prumadas, alimentadores (QM → QD) e o quadro de cada ponto
# ----------------------------------------------------------------------------------------------
def conv_modelo(dados, vista):
    """Coordenadas da vista (pt do PDF arquitetônico) → modelo (m, origem no centro do elevador), como no 3D."""
    from shapely.geometry import Polygon
    v = next(x for x in dados["vistas"] if x["id"] == vista)
    el = next(a for a in dados["ambientes"] if a["vista"] == vista and a["nome"] == "Elevador" and a["poligono"])
    c, m = Polygon(el["poligono"]).centroid, v["m_por_pt"]
    return lambda p: (round(p[0] * m - c.x * m, 4), round(p[1] * m - c.y * m, 4))


def _desloca(r, dx, dy):
    for p in r["pontos"]:
        p["xy"] = [round(p["xy"][0] + dx, 3), round(p["xy"][1] + dy, 3)]
    for t in r["tubos"]:
        t["pts"] = [[round(q[0] + dx, 3), round(q[1] + dy, 3)] for q in t["pts"]]
    r["soltas"] = [[k, [round(q[0] + dx, 3), round(q[1] + dy, 3)]] for k, q in r["soltas"]]
    s, tx, ty = r["reg"]
    r["reg"] = [s, tx + dx, ty + dy]


def corrigir_registro(plantas, dados, log=print, tol=0.10):
    """As prumadas (caixas de passagem com o mesmo nome) têm de ficar uma em cima da outra. Planta cujas caixas
    estão todas deslocadas do mesmo tanto em relação aos outros andares teve o registro preso num padrão
    repetido (ex.: a hachura do piso do subsolo): corrige a translação pelas prumadas."""
    import statistics as st
    pos = defaultdict(dict)
    for k, r in enumerate(plantas):
        cv = conv_modelo(dados, r["vista"])
        for p in r["pontos"]:
            if p["tipo"] == "cx" and p.get("nome"):
                pos[p["nome"]][k] = cv(p["xy"])
    out = {}
    for k, r in enumerate(plantas):
        dd = []
        for nome, por in pos.items():
            if k in por and len(por) > 1:
                ox = st.median(v[0] for j, v in por.items() if j != k)
                oy = st.median(v[1] for j, v in por.items() if j != k)
                dd.append((ox - por[k][0], oy - por[k][1]))
        if len(dd) < 3:
            continue
        mx, my = st.median(x for x, _ in dd), st.median(y for _, y in dd)
        if math.hypot(mx, my) < tol:
            continue
        juntos = sum(1 for x, y in dd if math.hypot(x - mx, y - my) < 0.05)
        if juntos < 0.6 * len(dd):
            log(f"  ! {r['pavimento']}: prumadas desalinhadas ({mx:+.2f}, {my:+.2f}) m sem padrão claro; registro mantido")
            continue
        m = next(v["m_por_pt"] for v in dados["vistas"] if v["id"] == r["vista"])
        _desloca(r, mx / m, my / m)
        r["correcao_m"] = [round(mx, 3), round(my, 3)]
        out[r["pavimento"]] = r["correcao_m"]
        log(f"  {r['pavimento']}: registro corrigido pelas prumadas em ({mx:+.3f}, {my:+.3f}) m ({juntos} de {len(dd)} caixas concordam)")
    return out


def montar_predio(plantas, dados, log=print):
    """Prumadas, alimentadores QM → QD e o quadro de cada ponto, no prédio todo."""
    import statistics as st
    from .hidraulica import niveis_do_modelo
    niv = niveis_do_modelo(dados)
    pd = dados["premissas"]["pe_direito_m"]
    ordem = sorted(plantas, key=lambda r: niv[r["pavimento"]])
    # --- prumadas: caixas de passagem com o mesmo nome (sem nome: a de mesma posição)
    grupos = defaultdict(list)
    sem = []
    for r in ordem:
        cv = conv_modelo(dados, r["vista"])
        for i, p in enumerate(r["pontos"]):
            if p["tipo"] == "cx":
                (grupos[p["nome"]] if p.get("nome") else sem).append((r["pavimento"], i, cv(p["xy"]), p))
    for pav, i, xy, p in sem:
        alvo = min(grupos, key=lambda n: min(math.dist(xy, q[2]) for q in grupos[n]), default=None)
        if alvo and min(math.dist(xy, q[2]) for q in grupos[alvo]) < 0.10 and pav not in [q[0] for q in grupos[alvo]]:
            p["nome"] = alvo
            grupos[alvo].append((pav, i, xy, p))
        else:
            nome = f"CX-{len(grupos) + 1}"
            p["nome"] = nome
            grupos[nome].append((pav, i, xy, p))
    prumadas = []
    tub = {r["pavimento"]: r["tubos"] for r in ordem}
    for nome, mem in grupos.items():
        mem.sort(key=lambda q: niv[q[0]])
        xy = (st.median(q[2][0] for q in mem), st.median(q[2][1] for q in mem))
        desvio = max(math.dist(xy, q[2]) for q in mem)
        # bitola da prumada: a do alimentador que sai dela para o QD acima do andar mais baixo (no térreo chegam os de 2" e
        # 3" dos medidores, que só vão até a caixa); prumada das áreas comuns: o rótulo ø ao lado das caixas
        acima = Counter(t["diam"] for pav, i, _, _ in mem[1:] for t in tub[pav] if i in (t["a"], t["b"]) and t["tipo"] == "alimentador")
        diam = acima.most_common(1) or Counter(q[3].get("diam") for q in mem[1:] if q[3].get("diam")).most_common(1) \
            or Counter(q[3].get("diam") for q in mem if q[3].get("diam")).most_common(1)
        prumadas.append({"nome": nome, "xy": [round(xy[0], 3), round(xy[1], 3)], "pavs": [q[0] for q in mem],
                         "desvio_m": round(desvio, 3), "atravessa": all(q[3].get("prumada") for q in mem[1:-1]),
                         "diam": diam[0][0] if diam else None})
    # --- grafo do prédio: nós (pavimento, índice do ponto); arestas = eletrodutos e trechos de prumada
    viz = defaultdict(list)            # nó -> [(vizinho, ("t", pav, k) | ("v", nome))]
    for r in ordem:
        for k, t in enumerate(r["tubos"]):
            if t["a"] is not None and t["b"] is not None:
                A, B = (r["pavimento"], t["a"]), (r["pavimento"], t["b"])
                viz[A].append((B, ("t", r["pavimento"], k)))
                viz[B].append((A, ("t", r["pavimento"], k)))
    for nome, mem in grupos.items():
        mem.sort(key=lambda q: niv[q[0]])
        for a, b in zip(mem[:-1], mem[1:]):
            A, B = (a[0], a[1]), (b[0], b[1])
            viz[A].append((B, ("v", nome)))
            viz[B].append((A, ("v", nome)))
    pt = {(r["pavimento"], i): p for r in ordem for i, p in enumerate(r["pontos"])}
    # --- alimentadores: de cada QD até um QM, só por eletroduto pontilhado e prumada
    tubo = lambda e: next(r for r in ordem if r["pavimento"] == e[1])["tubos"][e[2]]
    alimentadores = []
    for no_, p in pt.items():
        if p["tipo"] != "quadro" or not (p.get("nome") or "").startswith("QD"):
            continue
        ant = {no_: None}
        fila = [no_]
        achou = None
        while fila and not achou:
            k = fila.pop(0)
            for j, e in viz[k]:
                if j in ant:
                    continue
                if e[0] == "t" and tubo(e)["tipo"] != "alimentador":
                    continue
                q = pt[j]
                if q["tipo"] == "quadro":
                    if (q.get("nome") or "").startswith("QM"):
                        ant[j] = (k, e)
                        achou = j
                        break
                    continue
                if q["tipo"] != "cx":
                    continue
                ant[j] = (k, e)
                fila.append(j)
        cam, Lh, prum = [], 0.0, []
        if achou:
            k = achou
            while ant[k]:
                k0, e = ant[k]
                cam.append(e)
                if e[0] == "t":
                    Lh += tubo(e)["L"]
                elif e[1] not in prum:
                    prum.append(e[1])
                k = k0
        alimentadores.append({"qd": p["nome"], "pav": no_[0], "qm": pt[achou]["nome"] if achou else None,
                              "L_planta": round(Lh, 2), "prumadas": prum,
                              "trechos": [list(e) for e in cam]})
    # --- quadro de cada ponto ainda sem dono (áreas comuns): rede a partir de QD21/QD22, passando pelas prumadas
    #     (o alimentador do apartamento chega na caixa da prumada, mas o quadro de medição bloqueia: não vaza)
    comuns = [no_ for no_, p in pt.items() if p["tipo"] == "quadro" and (p.get("nome") or "").startswith("QD")]
    alcance = defaultdict(set)
    for no_ in comuns:
        nome = pt[no_]["nome"]
        vistos, fila = {no_}, [no_]
        while fila:
            k = fila.pop()
            for j, e in viz[k]:
                if j in vistos or pt[j]["tipo"] == "quadro":
                    continue
                vistos.add(j)
                fila.append(j)
        for j in vistos - {no_}:
            alcance[j].add(nome)
    for no_, nomes in alcance.items():
        p = pt[no_]
        if p["tipo"] not in ("cx", "quadro") and not p.get("quadro"):
            p["quadro"] = sorted(nomes)[0] if len(nomes) == 1 else "/".join(sorted(nomes))
    return {"niveis": niv, "pe_direito": pd, "prumadas": sorted(prumadas, key=lambda x: (len(x["nome"]), x["nome"])),
            "alimentadores": sorted(alimentadores, key=lambda a: int(re.sub(r"\D", "", a["qd"]) or 0))}


# ----------------------------------------------------------------------------------------------
# Tabelas do projetista: lista de materiais (por folha) e quadros de carga
# ----------------------------------------------------------------------------------------------
RX_QTD = re.compile(r"^([\d.]+)\s*(pç|m)$")
NOMES_LISTA = {"5ºPavimento": "5ºPavimento", "4ºPavimento": "4ºPavimento", "3ºPavimento": "3ºPavimento", "2ºPavimento": "2ºPavimento",
               "1ºPavimento": "1ºPavimento", "Térreo": "Pavimento Térreo", "Subsolo": "Sub-Solo"}


def _linhas_base(ts, tol=2.5):
    """Agrupa textos pela linha de base (y da origem)."""
    out = []
    for t in sorted(ts, key=lambda t: t["o"][1]):
        if out and abs(out[-1][0] - t["o"][1]) <= tol:
            out[-1][1].append(t)
        else:
            out.append([t["o"][1], [t]])
    return [(y, sorted(l, key=lambda t: t["r"][0])) for y, l in out]


def ler_lista(pg, tx=None):
    """Lista de Materiais da folha: [{grupo, sub, item, qtd, un}] e o pavimento."""
    tx = tx or textos(pg)
    tit = next((t for t in tx if t["t"].startswith("Lista de Materiais - ")), None)
    if not tit:
        return None, []
    pav = NOMES_LISTA.get(tit["t"].split(" - ", 1)[1].strip())
    x0 = tit["c"][0] - 232          # borda esquerda da moldura da lista (o título fica centrado nela)
    fim = min([t["r"][1] for t in tx if t["r"][1] > tit["r"][3] and t["r"][0] > x0 - 20
               and (t["t"].startswith("Legenda -") or t["t"] == "PROJETO ELÉTRICO")] or [pg.rect.width])
    ts = [t for t in tx if t["r"][0] > x0 and tit["r"][3] < t["o"][1] < fim and abs(t["dir"][0] - 1) < 1e-3]
    xs = sorted(round(t["r"][0]) for t in ts if not RX_QTD.match(t["t"]) and t["r"][0] < tit["r"][0])
    cat_x = min(xs) if xs else x0
    itens, grupo, sub = [], None, None
    for y, l in _linhas_base(ts):
        eq = lambda t: RX_QTD.match(t["t"]) and t["r"][0] > cat_x + 250        # quantidade: só na coluna da direita
        q = [t for t in l if eq(t)]
        txt = " ".join(t["t"] for t in l if not eq(t)).strip()
        ind = min((t["r"][0] for t in l if not eq(t)), default=None)
        if not q:
            if ind is None:
                continue
            if ind < cat_x + 4:
                grupo, sub = txt, None
            else:
                sub = txt if sub is None or not itens or itens[-1]["sub"] != sub else txt
            continue
        m = RX_QTD.match(q[-1]["t"])
        itens.append({"grupo": grupo, "sub": sub, "item": txt, "qtd": float(m.group(1)), "un": m.group(2)})
    return pav, itens


def _num(v):
    try:
        return float(v.replace(",", "."))
    except (ValueError, AttributeError):
        return None


def ler_quadros_carga(pg, tx=None):
    """Quadros de Cargas da folha: {nome: {"circuitos": [...], "total": {...}}}. Colunas pelo cabeçalho de cada
    tabela; as potências unitárias (60, 100, 150 W de iluminação; 100, 600, 2600 W... de tomadas) viram contagens."""
    tx = tx or textos(pg)
    hz = [t for t in tx if abs(t["dir"][0] - 1) < 1e-3]
    tits = [t for t in hz if re.match(r"Quadro de Cargas \((\w+)\)", t["t"])]
    out = {}
    for tit in tits:
        nome = re.match(r"Quadro de Cargas \((\w+)\)", tit["t"]).group(1)
        cab = min((t for t in hz if t["t"] == "Circuito" and 0 < t["r"][1] - tit["r"][3] < 25 and 0 < tit["c"][0] - t["c"][0] < 900),
                  key=lambda t: abs(t["r"][1] - tit["r"][3]) + 0.1 * abs(tit["c"][0] - t["c"][0]), default=None)
        if cab is None:
            continue
        linha_cab = [t for t in hz if abs(t["o"][1] - cab["o"][1]) < 3 and t["r"][0] >= cab["r"][0] - 5]
        dvt = [t for t in linha_cab if t["t"] == "dV total"]
        xr = (cab["r"][0] - 10, (min(dvt, key=lambda t: t["r"][0] - cab["r"][0])["r"][2] if dvt else cab["r"][0] + 1150) + 10)
        linha_cab = [t for t in linha_cab if t["r"][0] <= xr[1]]
        unid = [t for t in hz if 8 < t["o"][1] - cab["o"][1] < 22 and xr[0] <= t["c"][0] <= xr[1]]
        x_il = next((t["c"][0] for t in linha_cab if t["t"].startswith("Iluminação")), None)
        x_to = next((t["c"][0] for t in linha_cab if t["t"].startswith("Tomadas")), None)
        cols = []
        for t in linha_cab:
            if t["t"].startswith(("Iluminação", "Tomadas")):
                continue
            cols.append((t["c"][0], t["t"]))
        for t in unid:
            if re.fullmatch(r"\d+", t["t"]) and x_il is not None:
                tipo = "il" if (x_to is None or abs(t["c"][0] - x_il) < abs(t["c"][0] - x_to)) else "to"
                cols.append((t["c"][0], f"{tipo}{t['t']}"))
        # chaves com o mesmo nome (Pot. total. VA e W): a da esquerda é VA
        vistos = Counter()
        cols.sort()
        cols2 = []
        for x, k in cols:
            vistos[k] += 1
            cols2.append((x, k if vistos[k] == 1 else k + " (W)"))
        cols = cols2
        y0 = max(t["o"][1] for t in unid) if unid else cab["o"][1] + 12
        prox = [t["r"][1] for t in tits if t is not tit and t["r"][1] > tit["r"][3] and abs(t["c"][0] - tit["c"][0]) < 300]
        prox += [t["r"][1] for t in hz if t["t"].startswith("Quadro de Demanda") and t["r"][1] > tit["r"][3]
                 and xr[0] - 50 < t["c"][0] < xr[1] + 50]
        y1 = min(prox or [pg.rect.height])
        corpo = [t for t in hz if y0 + 2 < t["o"][1] < y1 and xr[0] <= t["c"][0] <= xr[1]]
        x_circ = next(x for x, k in cols if k == "Circuito")
        ancoras = sorted((t for t in corpo if abs(t["c"][0] - x_circ) < 40 and t["r"][0] < x_circ + 40
                          and (re.fullmatch(r"\d+|[a-z]{1,2}|TOTAL|Q[DM]\d+|QD\d+", t["t"]))), key=lambda t: t["o"][1])
        linhas = [{"_y": a["o"][1], "Circuito": a["t"]} for a in ancoras]
        if not linhas:
            continue
        for t in corpo:
            if any(t is a for a in ancoras):
                continue
            L = min(linhas, key=lambda l: abs(l["_y"] - t["o"][1]))
            if abs(L["_y"] - t["o"][1]) > 8:
                continue
            x, k = min(cols, key=lambda c: abs(c[0] - t["c"][0]))
            if k == "Circuito":
                k = "Descrição"
            L[k] = (L[k] + " " + t["t"]) if k in L else t["t"]
        circ, total, atual = [], None, None
        for L in linhas:
            L.pop("_y")
            c = L["Circuito"]
            if c == "TOTAL":
                total = L
                break
            if re.fullmatch(r"[a-z]{1,2}", c) and atual is not None:
                atual.setdefault("comandos", []).append(L)
                continue
            atual = L
            circ.append(L)
        out[nome] = {"circuitos": circ, "total": total}
    return out


def resumo_circuito(c):
    """Campos úteis de uma linha do quadro de cargas."""
    il = {int(k[2:]): int(_num(v) or 0) for k, v in c.items() if k.startswith("il") and _num(v)}
    to = {int(k[2:]): int(_num(v) or 0) for k, v in c.items() if k.startswith("to") and _num(v)}
    return {"n": c.get("Circuito"), "desc": c.get("Descrição"), "esquema": c.get("Esquema"), "v": c.get("V"),
            "il": il, "to": to, "va": _num(c.get("Pot. total.")), "w": _num(c.get("Pot. total. (W)")), "fases": c.get("Fases"),
            "secao": _num(c.get("Seção")), "disj": _num(c.get("Disj")), "in": _num(c.get("In'")),
            "dv": _num(c.get("dV total")), "comandos": [x.get("Circuito") for x in c.get("comandos", [])]}


# ----------------------------------------------------------------------------------------------
# Rede 3D: eletrodutos na laje (traço cheio) e no piso (pontilhado), descidas nas paredes até as caixas,
# prumadas nas caixas de passagem. Tudo ligado: cada ponta vai para o centro da caixa onde chega.
# ----------------------------------------------------------------------------------------------
DIAMS = ["3/4", "1", "1.1/2", "2", "3", "1/2", "1.1/4", "2.1/2", "4"]
TIPOS_PT = ["tomada_baixa", "tomada_media", "tomada_alta", "interruptor", "sensor", "arandela", "luminaria", "quadro", "medicao",
            "entrada", "cx", "forca"]


def rede_3d(ele, dados):
    niv, pd = ele["niveis"], ele["pe_direito"]
    pr_xy = {p["nome"]: p["xy"] for p in ele["prumadas"]}
    pr_pavs = {p["nome"]: p["pavs"] for p in ele["prumadas"]}
    trechos, pontos, por_pav = [], [], defaultdict(lambda: {"t": [], "p": []})
    alcance = defaultdict(list)                        # prumada -> alturas que ela precisa alcançar

    def add(pav, pts, diam, tipo, local, origem, contar=True):
        """Um eletroduto (polilinha 3D) = um registro; cada segmento vira uma linha do 3D apontando para ele.
        O comprimento é o do traçado; o desenho 3D usa o traçado simplificado (2 cm de tolerância nas curvas)."""
        L = sum(math.dist(a, b) for a, b in zip(pts[:-1], pts[1:]))
        if L < 0.005:
            return
        if len(pts) > 2 and len({round(p[2], 4) for p in pts}) == 1:          # traçado horizontal: simplifica em planta
            z = pts[0][2]
            pts = [(x, y, z) for x, y in _simplifica([(p[0], p[1]) for p in pts], 0.02)]
        segs = [(a, b) for a, b in zip(pts[:-1], pts[1:]) if math.dist(a, b) >= 0.002]
        v = all(abs(a[2] - b[2]) > 0.9 * math.dist(a, b) for a, b in segs)
        trechos.append([f"EL-{len(trechos) + 1:05d}", tipo, pav, diam, round(L, 3), origem, "v" if v else "h", local, contar])
        for a, b in segs:
            por_pav[pav]["t"].append([round(a[0], 3), round(a[1], 3), round(a[2], 3), round(b[0], 3), round(b[1], 3), round(b[2], 3),
                                      DIAMS.index(diam) if diam in DIAMS else 0, len(trechos) - 1])

    for r in ele["plantas"]:
        pav = r["pavimento"]
        z0, h_pd = niv[pav], pd.get(pav, 2.6)
        z_teto, z_piso = z0 + h_pd + Z_LAJE, z0 + Z_PISO
        cv = conv_modelo(dados, r["vista"])
        P = r["pontos"]
        xy, zp = [], []
        for p in P:
            q = pr_xy[p["nome"]] if p["tipo"] == "cx" and p.get("nome") in pr_xy and len(pr_pavs[p["nome"]]) > 1 else cv(p["xy"])
            xy.append(q)
            if p["tipo"] == "luminaria":
                zp.append(z_teto)                          # caixa octogonal dentro da laje; a luminária fica no forro
            elif p["tipo"] == "cx":
                zp.append(z0 + H_CX)
            else:
                zp.append(z0 + (p["h"] if p["h"] is not None else ALTURAS["tomada_baixa"]))
            k = "medicao" if p["tipo"] == "quadro" and (p.get("nome") or "").startswith("QM") else p["tipo"]
            pontos.append([pav, p["tipo"], p["sub"], p.get("circuito"), p.get("quadro"), p.get("pot"), p.get("comando"), p.get("nome"),
                           round(zp[-1] - z0, 2)])
            por_pav[pav]["p"].append([round(q[0], 3), round(q[1], 3), round(zp[-1], 3), TIPOS_PT.index(k) if k in TIPOS_PT else 0,
                                      len(pontos) - 1])
            if p["tipo"] == "cx" and p.get("nome") in pr_xy and len(pr_pavs[p["nome"]]) > 1:
                alcance[p["nome"]].append((pav, zp[-1]))
        for k, t in enumerate(r["tubos"]):
            a, b = t["a"], t["b"]
            if t["tipo"] == "alimentador":
                z, local = z_piso, "piso"
            elif t["tipo"] == "curto":
                z, local = min(zp[a], zp[b]), "parede"
            elif t["tipo"] == "seta":
                z, local = zp[b] if P[b]["tipo"] == "quadro" else zp[a], "parede"
            else:
                z, local = z_teto, "laje"
            pts = [cv(q) for q in t["pts"]]
            if a is not None:
                pts[0] = xy[a]
            if b is not None:
                pts[-1] = xy[b]
            origem = f"planta {pav} (pág. {r['pagina']}): eletroduto {'pontilhado (piso)' if local == 'piso' else 'cheio'} ø{t['diam']}\""
            add(pav, [(u[0], u[1], z) for u in pts], t["diam"], t["tipo"], local, origem)
            for i in (a, b):                               # descida/subida na parede até a caixa
                if i is None:
                    continue
                p = P[i]
                if p["tipo"] == "luminaria" and local == "laje":
                    continue                               # caixa octogonal na própria laje
                if abs(zp[i] - z) > 0.005:
                    add(pav, [(xy[i][0], xy[i][1], z), (xy[i][0], xy[i][1], zp[i])], t["diam"], "descida", "parede",
                        f"{'subida' if zp[i] > z else 'descida'} na parede até {p.get('nome') or p['tipo'].replace('_', ' ')} "
                        f"({zp[i] - z0:.2f} m do piso); altura pela legenda" + ("" if p["tipo"] != "arandela" else " (arandela: premissa 2,00 m)"))
    # prumadas: vertical na posição das caixas de passagem, de caixa a caixa (os eletrodutos de cada andar sobem ou
    # descem na parede até a caixa, como nos outros pontos)
    ordem = sorted(niv.items(), key=lambda kv: kv[1])
    for p in ele["prumadas"]:
        zs = [z for _, z in alcance.get(p["nome"], [])]
        if len(p["pavs"]) < 2 or not zs:
            continue
        lo, hi = min(zs), max(zs)
        diam = p.get("diam") or "1.1/2"
        x, y = p["xy"]
        for k, (pav, zf) in enumerate(ordem):
            z1 = ordem[k + 1][1] if k + 1 < len(ordem) else 1e9
            a_, b_ = max(lo, zf), min(hi, z1)
            if b_ - a_ > 0.005:
                add(pav, [(x, y, a_), (x, y, b_)], diam, "prumada", "prumada",
                    f"prumada {p['nome']} (caixas de passagem de {p['pavs'][0]} a {p['pavs'][-1]})")
    return {"trechos": trechos, "pontos": pontos, "por_pav": dict(por_pav), "diams": DIAMS, "tipos": TIPOS_PT}


def soltas_3d(r3d, tol=0.01):
    """Peças soltas no 3D (prédio inteiro): pontas de eletroduto que não encostam em outro eletroduto nem numa
    caixa, e caixas/pontos que nenhum eletroduto toca. Devolve (pontas soltas, pontos soltos) com exemplos."""
    import numpy as np
    from scipy.spatial import cKDTree
    segs = [(t[0:3], t[3:6], pav) for pav, v in r3d["por_pav"].items() for t in v["t"]]
    pts = [(p[0:3], pav, p[4]) for pav, v in r3d["por_pav"].items() for p in v["p"]]
    if not segs:
        return [], []
    A = np.array([a for a, _, _ in segs], float)
    B = np.array([b for _, b, _ in segs], float)
    AB = B - A
    L2 = (AB * AB).sum(1)
    L2[L2 < 1e-12] = 1.0

    def dist_segs(q):
        t = np.clip(((q - A) * AB).sum(1) / L2, 0, 1)
        return np.linalg.norm(A + t[:, None] * AB - q, axis=1)
    ends = np.vstack([A, B])
    dono = np.concatenate([np.arange(len(segs))] * 2)
    arv = cKDTree(ends)
    P = np.array([q for q, _, _ in pts], float) if pts else np.zeros((0, 3))
    arv_p = cKDTree(P) if len(P) else None
    soltas = []
    for i, q in enumerate(ends):
        if any(dono[j] != dono[i] for j in arv.query_ball_point(q, tol)):
            continue
        if arv_p is not None and arv_p.query(q)[0] < tol:
            continue
        d = dist_segs(q)
        d[dono[i]] = 1e9
        if d.min() < tol:
            continue
        soltas.append((segs[dono[i]][2], [round(float(x), 2) for x in q]))
    soltos = [(pav, r3d["pontos"][i][1], r3d["pontos"][i][7]) for q, pav, i in pts if dist_segs(np.array(q, float)).min() >= tol]
    return soltas, soltos


# ----------------------------------------------------------------------------------------------
# Conferência: modelo × lista de materiais × quadros de carga
# ----------------------------------------------------------------------------------------------
def _contagens(r):
    """Quantidades do modelo de um pavimento nos termos da lista de materiais."""
    c = Counter()
    for p in r["pontos"]:
        t, sub = p["tipo"], p["sub"] or ""
        if t == "tomada_baixa":
            c["tomada 20A" if sub.startswith("20 A") else "tomada universal"] += 1
        elif t == "tomada_media":
            c["tomada 10A"] += 1
        elif t == "tomada_alta":
            c["placa cega" if sub == "chuveiro" else "tomada 20A"] += 1
        elif t == "interruptor":
            c["interruptor " + sub] += 1
        elif t == "sensor":
            c["sensor"] += 1
        elif t == "arandela":
            c["arandela"] += 1
        elif t == "luminaria":
            c[f"luminária {p.get('pot') or 100} W"] += 1
        elif t == "cx":
            c["caixa de passagem"] += 1
        elif t == "quadro":
            c["caixa de medição" if (p.get("nome") or "").startswith("QM") else "quadro de distribuição"] += 1
        elif t == "forca":
            c["ponto de força"] += 1
    c["caixa 4x2"] = c["tomada universal"] + c["tomada 10A"] + c["tomada 20A"] + c["placa cega"] + c["sensor"] + \
        sum(v for k, v in c.items() if k.startswith("interruptor"))
    c["caixa 4x4"] = c["ponto de força"]
    c["caixa octogonal"] = c["arandela"] + sum(v for k, v in c.items() if k.startswith("luminária"))
    return c


# item da lista de materiais -> chave das contagens do modelo
ITENS_LISTA = [
    (r"^4x2\"$", "caixa 4x2", "Caixa PVC 4×2\""), (r"^4x4\"$", "caixa 4x4", "Caixa PVC 4×4\""), (r"^3x3\"$", "caixa octogonal", "Caixa octogonal 3×3\""),
    (r"^100x100x80", "caixa de passagem", "Caixa de passagem 100×100×80"),
    (r"Tomada universal", "tomada universal", "Tomada universal 2P+T 10 A (0,30 m)"),
    (r"Tomada hexagonal .*10A", "tomada 10A", "Tomada 2P+T 10 A (1,10 m)"),
    (r"Tomada hexagonal .*20A", "tomada 20A", "Tomada 2P+T 20 A (ar-condicionado e portões)"),
    (r"^Placa cega", "placa cega", "Ponto do chuveiro (placa cega)"),
    (r"2 simples & paralela", "interruptor 2 simples + paralelo (3 teclas)", "Interruptor 2 simples + paralelo"),
    (r"paralel[ao] - 1 tecla", "interruptor paralelo 1 tecla", "Interruptor paralelo 1 tecla"),
    (r"paralel[ao] - 2 teclas", "interruptor paralelo 2 teclas", "Interruptor paralelo 2 teclas"),
    (r"simples - 1 tecla", "interruptor simples 1 tecla", "Interruptor simples 1 tecla"),
    (r"simples - 2 teclas", "interruptor simples 2 teclas", "Interruptor simples 2 teclas"),
    (r"1200W resistivo", "sensor", "Sensor de presença"),
]


def conferir(ele):
    out = []
    G = "Elétrica"
    pl = {r["pavimento"]: r for r in ele["plantas"]}
    # registro e pontas
    rms = max((r["rms_mm"] or 0) for r in ele["plantas"])
    cor = ele.get("correcoes") or {}
    out.append((G, "Plantas elétricas sobre a arquitetura (registro)",
                f"{len(pl)} plantas, escala {min(r['escala'] for r in ele['plantas']):.4f}–{max(r['escala'] for r in ele['plantas']):.4f}, "
                f"maior resíduo {rms:.1f} mm" + "".join(f"; {k}: corrigido pelas prumadas em {math.hypot(*v):.2f} m (a hachura do piso enganou o encaixe)"
                                                         for k, v in cor.items()), rms < 10))
    soltas = sum(len(r["soltas"]) for r in ele["plantas"])
    out.append((G, "Pontas de eletroduto soltas", f"{soltas} pontas sem caixa em {sum(len(r['tubos']) for r in ele['plantas'])} eletrodutos", soltas == 0))
    sem = []
    for r in ele["plantas"]:
        lig = Counter(x for t in r["tubos"] for x in (t["a"], t["b"]) if x is not None)
        sem += [f"{r['pavimento']}: {p.get('nome') or p['tipo']}" for i, p in enumerate(r["pontos"]) if not lig[i] and not (p["tipo"] == "cx")]
    out.append((G, "Pontos sem eletroduto", f"{len(sem)}" + (": " + ", ".join(sem[:6]) if sem else " (caixas de prumada só atravessadas não contam)"), not sem))
    cx_vazia = [f"{r['pavimento']} {p['nome']}" for r in ele["plantas"] for i, p in enumerate(r["pontos"])
                if p["tipo"] == "cx" and not p.get("prumada") and not any(i in (t["a"], t["b"]) for t in r["tubos"])]
    if cx_vazia:
        out.append((G, "Caixa de passagem sem eletroduto e sem prumada", ", ".join(cx_vazia) + ": está na lista, mas nada chega nela; a prumada "
                    "foi levada até ela no 3D", False))
    if ele.get("rede3d"):
        s3, p3 = soltas_3d(ele["rede3d"])
        out.append((G, "3D: nada solto (eletroduto encosta em eletroduto ou caixa; toda caixa tem eletroduto)",
                    f"{sum(len(v['t']) for v in ele['rede3d']['por_pav'].values())} trechos no 3D; {len(s3)} pontas soltas, {len(p3)} pontos soltos"
                    + (": " + ", ".join(f"{a} {b} {c or ''}".strip() for a, b, c in p3[:6]) if p3 else ""), not s3 and not p3))
    sq = [f"{r['pavimento']}: {p['tipo']}" for r in ele["plantas"] for p in r["pontos"] if p["tipo"] not in ("cx", "quadro", "entrada") and not p.get("quadro")]
    out.append((G, "Quadro de cada ponto (pela rede, atravessando as prumadas)", f"{sum(1 for r in ele['plantas'] for p in r['pontos'] if p.get('quadro'))} pontos com quadro; "
                f"{len(sq)} sem", not sq))
    desv = max(p["desvio_m"] for p in ele["prumadas"])
    out.append((G, "Prumadas: caixas de passagem uma sobre a outra", f"{len(ele['prumadas'])} prumadas; maior desvio entre andares {desv * 1000:.0f} mm", desv < 0.02))
    # alimentadores
    al = ele["alimentadores"]
    ok_al = [a for a in al if a["qm"] and re.sub(r"\D", "", a["qm"]) == re.sub(r"\D", "", a["qd"])]
    pn = [x for r in ele["plantas"] for x in r.get("pela_numeracao", [])]
    out.append((G, "Alimentadores: cada QD chega no QM de mesmo número", f"{len(ok_al)} de {len(al)} (QM → caixa da prumada → QD)"
                + (f"; no térreo {len(pn)} chegam entre duas caixas vizinhas e valeu a numeração ({', '.join(f'{a}→{c}' for a, _, c in pn)})" if pn else ""),
                len(ok_al) == len(al)))
    # lista de materiais × modelo
    for pav, itens in ele["listas"].items():
        r = pl.get(pav)
        if not r:
            continue
        c = _contagens(r)
        dif, n = [], 0
        for rx, chave, nome in ITENS_LISTA:
            q = sum(x["qtd"] for x in itens if re.search(rx, x["item"]) and x["un"] == "pç")
            m = c.get(chave, 0)
            if q == 0 and m == 0:
                continue
            n += 1
            if abs(q - m) > 0.01:
                dif.append(f"{nome}: lista {q:g}, modelo {m}")
        lum = {int(re.match(r"(\d+)", x["item"]).group(1)): x["qtd"] for x in itens if x["sub"] and x["sub"].startswith("Luminária sobrepor")}
        for w, q in lum.items():
            n += 1
            if abs(q - c.get(f"luminária {w} W", 0)) > 0.01:
                dif.append(f"Luminária {w} W: lista {q:g}, modelo {c.get(f'luminária {w} W', 0)}")
        ar = sum(x["qtd"] for x in itens if x["sub"] == "Arandela")
        if ar or c["arandela"]:
            n += 1
            if abs(ar - c["arandela"]) > 0.01:
                dif.append(f"Arandela: lista {ar:g}, modelo {c['arandela']}")
        qd = sum(x["qtd"] for x in itens if (x["grupo"] or "").startswith("Quadro distrib"))
        if qd or c["quadro de distribuição"]:
            n += 1
            if abs(qd - c["quadro de distribuição"]) > 0.01:
                dif.append(f"Quadro de distribuição: lista {qd:g}, modelo {c['quadro de distribuição']}")
        med = sum(x["qtd"] for x in itens if (x["sub"] or "").startswith("Unidade consumidora"))
        if med:
            n += 1
            if abs(med - c["caixa de medição"]) > 0.01:
                dif.append(f"Caixas de medição individuais: lista {med:g} (21 bifásicas, 1 monofásica, 1 trifásica), planta {c['caixa de medição']} (QM1–QM22)")
        out.append((G, f"Pontos e peças × lista de materiais ({pav})", f"{n - len(dif)} de {n} itens iguais" + ("; " + "; ".join(dif) if dif else ""), not dif))
    # quadros de carga × pontos da planta
    pts_qd = defaultdict(list)
    for r in ele["plantas"]:
        for p in r["pontos"]:
            if p.get("quadro") and p["tipo"] not in ("cx", "quadro", "entrada", "interruptor", "sensor"):
                pts_qd[p["quadro"]].append(p)
    dif_q, nq = [], 0
    for nome, q in sorted(ele["quadros"].items(), key=lambda kv: (kv[0][:2], int(re.sub(r"\D", "", kv[0]) or 0))):
        if not nome.startswith("QD"):
            continue
        nq += 1
        tab = Counter()
        for c in q["circuitos"]:
            for w, k in c["il"].items():
                tab[(int(c["n"]), w)] += k
            for w, k in c["to"].items():
                tab[(int(c["n"]), w)] += k
        mod = Counter()
        for p in pts_qd.get(nome, []):
            w = p.get("pot") or (100 if p["tipo"] in ("luminaria", "tomada_baixa") else None)
            mod[(p.get("circuito"), w)] += 1
        if tab != mod:
            falta = tab - mod
            sobra = mod - tab
            dif_q.append(f"{nome}: " + ", ".join([f"circ. {c} {w} W falta {k}" for (c, w), k in falta.items()] +
                                                 [f"circ. {c} {w} W a mais {k}" for (c, w), k in sobra.items()]))
    out.append((G, "Pontos por circuito e potência × quadros de carga", f"{nq - len(dif_q)} de {nq} quadros iguais ponto a ponto"
                + ("; " + "; ".join(dif_q[:4]) if dif_q else ""), not dif_q))
    # comandos: cada letra de luminária tem um interruptor/sensor com a mesma letra no mesmo quadro
    sem_cmd = []
    for r in ele["plantas"]:
        tem = defaultdict(set)
        for p in r["pontos"]:
            if p["tipo"] in ("interruptor", "sensor") and p.get("comando"):
                tem[p.get("quadro")].update(p["comando"])
        for p in r["pontos"]:
            if p["tipo"] in ("luminaria", "arandela") and p.get("comando"):
                falta = set(p["comando"]) - tem[p.get("quadro")]
                if falta:
                    sem_cmd.append(f"{r['pavimento']} {p.get('quadro')} '{''.join(sorted(falta))}'")
    out.append((G, "Comandos: luminária × interruptor (letra no mesmo quadro)", f"{len(sem_cmd)} letras sem interruptor" + (": " + ", ".join(sem_cmd[:6]) if sem_cmd else ""),
                not sem_cmd))
    # andares-tipo e apartamentos iguais
    assin = {}
    for r in ele["plantas"]:
        if r["pavimento"].endswith("ºPavimento"):
            por = defaultdict(Counter)
            for p in r["pontos"]:
                if (p.get("quadro") or "").startswith("QD") and p["quadro"] != "QD22":
                    por[p["quadro"]][(p["tipo"], p["sub"], p.get("circuito"), p.get("pot"))] += 1
            assin[r["pavimento"]] = [tuple(sorted(v.items(), key=str)) for _, v in sorted(por.items())]
    aps = {a for v in assin.values() for a in v}
    out.append((G, "Apartamentos iguais (pontos por circuito)", f"{sum(len(v) for v in assin.values())} apartamentos em {len(assin)} andares: "
                + ("todos com os mesmos pontos, circuito a circuito" if len(aps) == 1 else f"{len(aps)} composições diferentes"), len(aps) == 1))
    # bitola diferente para o mesmo circuito em apartamentos espelhados (rótulo faltando)
    diam_c = defaultdict(Counter)
    for r in ele["plantas"]:
        for t in r["tubos"]:
            for x, y in ((t["a"], t["b"]), (t["b"], t["a"])):
                if x is None or y is None:
                    continue
                q, p = r["pontos"][x], r["pontos"][y]
                if q["tipo"] == "quadro" and (q.get("nome") or "").startswith("QD") and q["nome"] not in ("QD21", "QD22") and p.get("circuito"):
                    diam_c[(p["circuito"], p["tipo"], p["sub"])][(t["diam"], q["nome"])] += 1
    div = []
    for k, v in diam_c.items():
        ds = sorted({d for d, _ in v}, key=lambda d: POL.get(d, 0))
        if len(ds) > 1:
            partes = []
            for d in ds:
                qs = sorted({q for dd, q in v if dd == d}, key=lambda s: int(s[2:]))
                partes.append(f"ø{d}\" em {len(qs)} ({', '.join(qs)})")
            div.append(f"circuito {k[0]} ({k[2] or k[1].replace('_', ' ')}): " + "; ".join(partes))
    out.append((G, "Bitola igual para o mesmo circuito em todos os apartamentos",
                "igual em todos" if not div else "; ".join(div) + ". O desenho não traz o rótulo ø nesses apartamentos: o modelo segue o desenho "
                "(3/4\", bitola padrão); confirmar com o projetista", not div))
    # eletrodutos × lista, medindo como o projetista (comprimento desenhado + descidas do forro ao topo da caixa)
    pd = ele["pe_direito"]
    soma_l, soma_m = Counter(), Counter()
    for pav, itens in ele["listas"].items():
        r = pl.get(pav)
        if not r:
            continue
        lst = {x["item"].rstrip('"'): x["qtd"] for x in itens if (x["grupo"] or "").startswith("Eletroduto PVC flex")}
        q = Counter()
        for t in r["tubos"]:
            q[t["diam"]] += t["L"]
            for i in (t["a"], t["b"]):
                if i is None or t["tipo"] == "seta":
                    continue
                p = r["pontos"][i]
                if p["tipo"] == "luminaria" or t["tipo"] == "curto" or (p["tipo"] == "cx" and t["tipo"] != "alimentador"):
                    continue
                h = H_CX if p["tipo"] == "cx" else (p["h"] if p["h"] is not None else ALTURAS["tomada_baixa"])
                q[t["diam"]] += (h + 0.05 - 0.05) if t["tipo"] == "alimentador" else (pd.get(pav, 2.6) - h - 0.05)
        d34 = lst.get("3/4", 0)
        if d34:
            e = q["3/4"] / d34 - 1
            nota = "" if abs(e) < 0.03 else (" — nos andares-tipo a mesma medida bate (±0,3%); a diferença aqui são trechos que a lista conta e "
                                              "a planta não desenha (provável: descidas às caixas de passagem e pé-direito maior no programa do "
                                              "projetista). O orçamento usa a lista")
            out.append((G, f"Eletroduto 3/4\" × lista ({pav})", f"modelo {q['3/4']:.1f} m × lista {d34:.1f} m ({e * 100:+.1f}%), medindo como o projetista: "
                        "comprimento desenhado + descida do forro até o topo da caixa" + nota, abs(e) < 0.03))
        for d in [x for x in lst if x not in ("3/4",)]:
            soma_l[d] += lst[d]
        for d, v in q.items():
            if d != "3/4":
                soma_m[d] += v
    # bitolas maiores (alimentadores, prumadas, 1"): no prédio todo, com as prumadas do 3D
    for t in ele.get("rede3d", {}).get("trechos", []):
        if t[1] == "prumada" and t[8]:
            soma_m[t[3]] += t[4]
    for d in sorted(set(soma_l) | set(soma_m), key=lambda d: POL.get(d, 0)):
        if d not in soma_l:
            continue
        e = soma_m[d] / soma_l[d] - 1 if soma_l[d] else 0
        out.append((G, f"Eletroduto {d}\" × lista (prédio)", f"modelo {soma_m[d]:.1f} m (desenho + descidas + prumadas) × lista {soma_l[d]:.1f} m ({e * 100:+.1f}%)"
                    + ("" if abs(e) < 0.05 else "; a lista do projetista conta prumadas e chegadas aos quadros de outro jeito: o orçamento usa a lista"),
                    abs(e) < 0.05))
    return out


def ler_eletrica(pdf, dados, log=print):
    """Projeto elétrico inteiro: plantas, prédio (prumadas e alimentadores), tabelas, rede 3D e conferência."""
    doc = pymupdf.open(str(pdf))
    plantas, listas, quadros = [], {}, {}
    for pg in doc:
        tx = textos(pg)
        r = ler_planta(pg, dados, log)
        if r:
            plantas.append(r)
        pav, itens = ler_lista(pg, tx)
        if pav:
            listas[pav] = itens
        for k, v in ler_quadros_carga(pg, tx).items():
            quadros[k] = {"pagina": pg.number + 1, "circuitos": [resumo_circuito(c) for c in v["circuitos"]], "total": v["total"]}
    corr = corrigir_registro(plantas, dados, log)
    ele = {"pdf": Path(str(pdf)).name, "plantas": plantas, "listas": listas, "quadros": quadros, "correcoes": corr}
    ele.update(montar_predio(plantas, dados, log))
    ele["rede3d"] = rede_3d(ele, dados)
    ele["conferencia"] = conferir(ele)
    log(f"  elétrica: {sum(len(r['pontos']) for r in plantas)} pontos, {len(ele['prumadas'])} prumadas, {len(ele['alimentadores'])} alimentadores, "
        f"{len(quadros)} quadros de carga, {len(listas)} listas; conferência {sum(1 for c in ele['conferencia'] if c[3])}/{len(ele['conferencia'])}")
    return ele
