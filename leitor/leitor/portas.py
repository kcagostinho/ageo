"""Portas de giro: acha dobradiça, folha e posição fechada a partir do arco desenhado.

A folha na posição fechada (dobradiça → ponta do arco do lado da parede) é a "linha de apoio"
que fecha o vão, para que cada cômodo vire um polígono fechado.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .ingestao import Pagina


@dataclass
class Porta:
    dobradica: tuple[float, float]
    fechada: tuple[float, float]     # ponta da folha fechada (no alinhamento da parede)
    aberta: tuple[float, float]      # ponta da folha aberta (como desenhada)
    raio_pt: float


def _centro(p0, p1, p2, p3):
    """Centro do arco: cruzamento das normais nas pontas."""
    t0 = (p1[0] - p0[0], p1[1] - p0[1])
    t3 = (p3[0] - p2[0], p3[1] - p2[1])
    # normal em p0: p0 + a*(-t0y, t0x); normal em p3: p3 + b*(-t3y, t3x)
    n0, n3 = (-t0[1], t0[0]), (-t3[1], t3[0])
    det = n0[0] * (-n3[1]) - n0[1] * (-n3[0])
    if abs(det) < 1e-9:
        return None
    dx, dy = p3[0] - p0[0], p3[1] - p0[1]
    a = (dx * (-n3[1]) - dy * (-n3[0])) / det
    return (p0[0] + a * n0[0], p0[1] + a * n0[1])


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def encontrar_portas(pag: Pagina, caixa, camada: str = "A-DOOR") -> list[Porta]:
    def dentro(x, y):
        return caixa[0] <= x <= caixa[2] and caixa[1] <= y <= caixa[3]

    grupos: dict[tuple[int, int], list] = {}
    for c in pag.curvas:
        if c[0] != camada or not dentro(c[1], c[2]):
            continue
        p0, p1, p2, p3 = (c[1], c[2]), (c[3], c[4]), (c[5], c[6]), (c[7], c[8])
        ctr = _centro(p0, p1, p2, p3)
        if not ctr:
            continue
        r0, r3 = _dist(p0, ctr), _dist(p3, ctr)
        if r0 < 5 or abs(r0 - r3) > 0.05 * r0:
            continue
        grupos.setdefault((round(ctr[0]), round(ctr[1])), []).append((ctr, p0, p3, r0))

    folhas = [s for s in pag.segmentos if s[0] == camada and dentro(s[2], s[3])]
    folhas_ret = [s for s in pag.segmentos if s[0] in (camada, camada + "-FRAM") and dentro(s[2], s[3])]
    portas = []
    for itens in grupos.values():
        ctr = itens[0][0]
        r = sum(i[3] for i in itens) / len(itens)
        pontas = [p for i in itens for p in (i[1], i[2])]
        # extremos do arco: par de pontas com maior separação angular
        ang = lambda p: math.atan2(p[1] - ctr[1], p[0] - ctr[0])
        e1, e2 = max(((a, b) for a in pontas for b in pontas),
                     key=lambda ab: abs(math.remainder(ang(ab[0]) - ang(ab[1]), 2 * math.pi)))
        aberta = None
        for s in folhas:
            a, b = (s[2], s[3]), (s[4], s[5])
            for x, y in ((a, b), (b, a)):
                if _dist(x, ctr) < 1.5:
                    if _dist(y, e1) < 1.5:
                        aberta = e1
                    elif _dist(y, e2) < 1.5:
                        aberta = e2
        if aberta is None:
            # folha desenhada como retângulo fino (camada de batente/folha): procura um traço
            # paralelo à reta dobradiça→ponta, colado nela
            for e in (e1, e2):
                ux, uy = (e[0] - ctr[0]) / r, (e[1] - ctr[1]) / r
                for s in folhas_ret:
                    a_, b_ = (s[2], s[3]), (s[4], s[5])
                    L = _dist(a_, b_)
                    if L < 0.5 * r:
                        continue
                    vx, vy = (b_[0] - a_[0]) / L, (b_[1] - a_[1]) / L
                    if abs(abs(ux * vx + uy * vy) - 1) > 0.01:
                        continue
                    # distância do traço à reta dobradiça→ponta
                    d = abs((a_[0] - ctr[0]) * uy - (a_[1] - ctr[1]) * ux)
                    if d < 3.0 and min(_dist(a_, ctr), _dist(b_, ctr)) < 0.2 * r:
                        aberta = e
                        break
                if aberta is not None:
                    break
        if aberta is None:
            continue
        fechada = e2 if aberta is e1 else e1
        portas.append(Porta(ctr, fechada, aberta, r))
    return portas
