"""Calibração de escala pelas cotas: compara o valor escrito em cada cota com o comprimento desenhado."""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass

from .ingestao import Pagina

NUM = re.compile(r"^\d{1,3},\d{2}$")


@dataclass
class Calibracao:
    m_por_pt: float
    n_cotas: int
    desvio_pct: float          # dispersão (MAD relativa) entre as cotas usadas
    amostras: list[tuple[str, float, float]]  # (texto, valor_m, comprimento_pt)


def _dentro(x, y, caixa):
    return caixa[0] <= x <= caixa[2] and caixa[1] <= y <= caixa[3]


def calibrar(pag: Pagina, caixa, camada: str = "A-ANNO-DIMS-50", nominal: float | None = None) -> Calibracao | None:
    finas = [s for s in pag.segmentos if s[0] == camada and s[1] < 0.5
             and _dentro((s[2] + s[4]) / 2, (s[3] + s[5]) / 2, caixa)]
    # tiques de cota (traços grossos inclinados); cada um costuma vir em duas metades
    # que se encontram exatamente sobre a linha de cota
    ticks = [s for s in pag.segmentos if s[0] == camada and s[1] >= 0.9 and _dentro(s[2], s[3], caixa)]
    # cotas de porta/janela ("0,80 x 2,10") não são cotas lineares
    linhas_x = {(w[5], w[6]) for w in pag.palavras if w[4] == "x"}
    amostras = []
    for w in pag.palavras:
        if not NUM.match(w[4]) or (w[5], w[6]) in linhas_x or not _dentro(w[0], w[1], caixa):
            continue
        valor = float(w[4].replace(",", "."))
        if valor <= 0:
            continue
        cx, cy = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
        horizontal = (w[2] - w[0]) > (w[3] - w[1])
        # linha de cota paralela ao texto, a poucos pontos dele, passando pelo centro do texto
        melhor = None
        for s in finas:
            if horizontal and abs(s[3] - s[5]) < 0.05:
                d, a, b, t = s[3] - cy, min(s[2], s[4]), max(s[2], s[4]), cx
            elif not horizontal and abs(s[2] - s[4]) < 0.05:
                d, a, b, t = s[2] - cx, min(s[3], s[5]), max(s[3], s[5]), cy
            else:
                continue
            if 0.5 < abs(d) < 10 and a <= t <= b and (melhor is None or abs(d) < abs(melhor[0])):
                melhor = (d, s)
        if not melhor:
            continue
        s = melhor[1]
        pos = set()
        for k in ticks:
            # interseção do tique com a linha de cota
            if horizontal:
                L, u0, v0, u1, v1, lo, hi = s[3], k[3], k[2], k[5], k[4], min(s[2], s[4]), max(s[2], s[4])
            else:
                L, u0, v0, u1, v1, lo, hi = s[2], k[2], k[3], k[4], k[5], min(s[3], s[5]), max(s[3], s[5])
            if min(u0, u1) - 0.05 <= L <= max(u0, u1) + 0.05 and abs(u1 - u0) > 1e-6:
                v = v0 + (L - u0) * (v1 - v0) / (u1 - u0)
                if lo - 0.5 <= v <= hi + 0.5:
                    pos.add(round(v, 2))
        pos = sorted(pos)
        t = cx if horizontal else cy
        par = [(a, b) for a, b in zip(pos, pos[1:]) if a < t < b and b - a > 1]
        if par:
            a, b = par[0]
            amostras.append((w[4], valor, b - a))
    if not amostras:
        return None
    razoes = [v / L for _, v, L in amostras]
    med = statistics.median(razoes)
    boas = [(t, v, L) for t, v, L in amostras if abs(v / L - med) / med < 0.02]
    razoes = [v / L for _, v, L in boas]
    med = statistics.median(razoes)
    mad = statistics.median(abs(r - med) for r in razoes) / med * 100
    return Calibracao(med, len(boas), mad, boas)
