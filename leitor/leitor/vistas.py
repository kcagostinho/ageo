"""Localiza as vistas de cada prancha (plantas, cortes…) e lê título e escala nominal."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .ingestao import Pagina

PT_EM_M = 0.0254 / 72  # 1 pt no papel, em metros


@dataclass
class Vista:
    pagina: int
    titulo: str
    escala: int                      # 50 para 1:50
    caixa: tuple[float, float, float, float]

    @property
    def m_por_pt_nominal(self) -> float:
        return PT_EM_M * self.escala


def _linhas_texto(pag: Pagina):
    linhas: dict[tuple[int, int], list] = {}
    for w in pag.palavras:
        linhas.setdefault((w[5], w[6]), []).append(w)
    out = []
    for ws in linhas.values():
        ws.sort(key=lambda w: w[0])
        out.append((min(w[0] for w in ws), min(w[1] for w in ws), max(w[2] for w in ws), max(w[3] for w in ws),
                    " ".join(w[4] for w in ws)))
    return out


def _agrupar(caixas, folga):
    caixas = [list(c) for c in caixas]
    mudou = True
    while mudou:
        mudou = False
        res = []
        for c in caixas:
            for r in res:
                if c[0] - folga <= r[2] and r[0] - folga <= c[2] and c[1] - folga <= r[3] and r[1] - folga <= c[3]:
                    r[0], r[1], r[2], r[3] = min(r[0], c[0]), min(r[1], c[1]), max(r[2], c[2]), max(r[3], c[3])
                    mudou = True
                    break
            else:
                res.append(c)
        caixas = res
    return [tuple(c) for c in caixas]


def encontrar_vistas(pag: Pagina, camada_base: str = "A-WALL", folga: float = 40.0) -> list[Vista]:
    caixas = [(min(s[2], s[4]), min(s[3], s[5]), max(s[2], s[4]), max(s[3], s[5]))
              for s in pag.segmentos if s[0] == camada_base]
    grupos = [g for g in _agrupar(caixas, folga) if (g[2] - g[0]) * (g[3] - g[1]) > 100 * 100]
    linhas = _linhas_texto(pag)
    escalas = [(l, int(m.group(1))) for l in linhas if (m := re.fullmatch(r"1\s*:\s*(\d+)", l[4]))]
    vistas = []
    for g in grupos:
        # rótulo de escala logo abaixo da vista, sobreposto horizontalmente
        cand = [(l[1] - g[3], l, esc) for l, esc in escalas
                if l[1] >= g[3] - 5 and l[1] - g[3] < 1000 and l[0] < g[2] and l[2] > g[0]]
        if not cand:
            continue
        _, l, esc = min(cand, key=lambda c: c[0])
        # título: linha de texto imediatamente acima do rótulo de escala
        tit = [t for t in linhas if 0 < l[1] - t[3] < 25 and abs(t[0] - l[0]) < 80 and t is not l]
        titulo = min(tit, key=lambda t: l[1] - t[3])[4] if tit else "?"
        vistas.append(Vista(pag.numero, titulo, esc, g))
    return sorted(vistas, key=lambda v: (v.caixa[1] // 300, v.caixa[0]))
