"""Costura do 3D das instalações: pontas de tubo soltas ligadas ao tubo mais perto do mesmo sistema.

O 3D é reconstruído de desenhos 2D (isométricos fora de escala na horizontal, plantas sem altura), então
sobram pontas soltas: a altura do barrilete, do térreo e dos coletores é premissa, e muitos tubos verticais
só existem no isométrico (sem posição). Esta etapa é só visual:
  1. pontas a até 5 cm umas das outras vão para o mesmo ponto;
  2. cada ponta solta (que não é ponto de consumo nem subida a aparelho) liga no tubo mais perto do mesmo
     sistema, com percurso ortogonal (vertical + horizontal), dentro de um raio curto;
  3. as ligações entram com a marca "ligação do 3D" e não somam no quantitativo nem no preço.

Linhas (coordenadas do modelo, z absoluto): [x, y, z, x, y, z, dn, indice_na_lista, sistema].
"""
from __future__ import annotations

import math


def _dps(P, A, B):
    """Distância ponto-segmento em 3D e o ponto mais perto."""
    v = [B[i] - A[i] for i in range(3)]
    w = [P[i] - A[i] for i in range(3)]
    L2 = sum(x * x for x in v)
    t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, sum(v[i] * w[i] for i in range(3)) / L2))
    Q = [A[i] + t * v[i] for i in range(3)]
    return math.dist(P, Q), Q, t


def costurar(por_pav: dict, lista: list, terminal, raio_h=0.6, raio_v=3.6, tol=0.03, juntar=0.05) -> dict:
    """por_pav[pav]["t"]: linhas (z absoluto). terminal(sistema, linha, ponta) -> True se a ponta termina de
    propósito. Acrescenta as ligações nas linhas e na lista; devolve um resumo por sistema."""
    resumo = {}
    sistemas = sorted({(r[8] if len(r) > 8 else 0) for v in por_pav.values() for r in v["t"]})
    for sy in sistemas:
        segs = [(pav, r) for pav, v in por_pav.items() for r in v["t"] if (r[8] if len(r) > 8 else 0) == sy]
        # 1. pontas muito perto: mesmo ponto
        pontas = [(k, e) for k in range(len(segs)) for e in (0, 1)]
        P = lambda k, e: [segs[k][1][3 * e], segs[k][1][3 * e + 1], segs[k][1][3 * e + 2]]
        juntadas = 0
        for i, (k, e) in enumerate(pontas):
            A = P(k, e)
            for k2, e2 in pontas[i + 1:]:
                if k2 == k:
                    continue
                B = P(k2, e2)
                d = math.dist(A, B)
                if tol < d <= juntar:
                    M = [(A[j] + B[j]) / 2 for j in range(3)]
                    for kk, ee in ((k, e), (k2, e2)):
                        segs[kk][1][3 * ee:3 * ee + 3] = [round(x, 3) for x in M]
                    juntadas += 1
                    A = M
        # 2. pontas soltas
        def solta(k, e):
            A = P(k, e)
            return not any(j != k and _dps(A, P(j, 0), P(j, 1))[0] <= tol for j in range(len(segs)))
        soltas = [(k, e) for k in range(len(segs)) for e in (0, 1) if solta(k, e) and not terminal(sy, segs[k][1], e)]
        ligadas, ficou = 0, 0
        feitas = set()
        novas = []
        for k, e in soltas:
            if (k, e) in feitas:
                continue
            A, O = P(k, e), P(k, 1 - e)
            d = [A[i] - O[i] for i in range(3)]
            n = math.sqrt(sum(x * x for x in d)) or 1.0
            d = [x / n for x in d]
            vertical = abs(d[2]) > 0.9
            melhor = None
            for j in range(len(segs)):
                if j == k:
                    continue
                _, Q, t = _dps(A, P(j, 0), P(j, 1))
                dh = math.hypot(Q[0] - A[0], Q[1] - A[1])
                dv = abs(Q[2] - A[2])
                if dh > raio_h or dv > (raio_v if vertical or dh < 0.1 else 0.8):
                    continue
                if dh + dv < tol:
                    continue
                frente = sum((Q[i] - A[i]) * d[i] for i in range(3))
                nota = dh + 0.3 * dv + (0.3 if frente < -0.05 else 0.0) - (0.15 if t in (0.0, 1.0) else 0.0)
                if melhor is None or nota < melhor[0]:
                    melhor = (nota, j, Q, t)
            if not melhor:
                ficou += 1
                continue
            _, j, Q, t = melhor
            pav, r = segs[k]
            dn = r[6]
            # percurso ortogonal: segue a direção do próprio tubo primeiro
            if abs(Q[2] - A[2]) < 0.01 or math.hypot(Q[0] - A[0], Q[1] - A[1]) < 0.01:
                trechos = [(A, Q)]
            elif vertical:
                C = [A[0], A[1], Q[2]]
                trechos = [(A, C), (C, Q)]
            else:
                C = [Q[0], Q[1], A[2]]
                trechos = [(A, C), (C, Q)]
            comp = sum(math.dist(a, b) for a, b in trechos)
            lista.append([f"LIG-{len(lista):04d}", "ligação", pav, dn, round(comp, 2),
                          "ligação do 3D entre tubos lidos de vistas diferentes (só visual: não entra no quantitativo nem no preço)",
                          "v" if vertical else "h", "ligação do 3D", "es" if sy == 1 else "af"])
            for a, b in trechos:
                novas.append((pav, [round(a[0], 3), round(a[1], 3), round(a[2], 3), round(b[0], 3), round(b[1], 3), round(b[2], 3),
                                    dn, len(lista) - 1, sy]))
            feitas.add((k, e))
            if t in (0.0, 1.0):
                feitas.add((j, 0 if t == 0.0 else 1))
            ligadas += 1
        for pav, linha in novas:
            por_pav[pav]["t"].append(linha)
        resumo["esgoto" if sy == 1 else "água fria"] = {"juntadas": juntadas, "soltas": len(soltas), "ligadas": ligadas, "ficaram": ficou}
    return resumo
