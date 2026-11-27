"""Esquadrias: lê as etiquetas 'L x H' (e peitoril, quando houver) desenhadas na planta."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from .ingestao import Pagina

NUM = re.compile(r"^\d{1,2},\d{2}$")


@dataclass
class Esquadria:
    tipo: str            # "porta" ou "janela"
    largura_m: float
    altura_m: float
    x: float
    y: float
    peitoril_m: float | None = None

    @property
    def chave(self) -> str:
        return f"{self.largura_m:.2f} x {self.altura_m:.2f}".replace(".", ",")


def ler_esquadrias(pag: Pagina, caixa, folga: float = 60.0) -> list[Esquadria]:
    """folga: etiquetas de janela de fachada costumam ficar do lado de fora da parede."""
    def dentro(w):
        return caixa[0] - folga <= w[0] <= caixa[2] + folga and caixa[1] - folga <= w[1] <= caixa[3] + folga
    linhas: dict[tuple[int, int], list] = {}
    for w in pag.palavras:
        if dentro(w):
            linhas.setdefault((w[5], w[6]), []).append(w)
    res = []
    for (b, l), ws in linhas.items():
        if [w[4] for w in ws] != ["x"]:
            continue
        x = ws[0]
        # números da etiqueta: na mesma altura do "x", um de cada lado
        cand = [w for (b2, _), ws2 in linhas.items() if b2 == b for w in ws2
                if NUM.match(w[4]) and abs((w[1] + w[3]) / 2 - (x[1] + x[3]) / 2) < 3 and abs(w[0] - x[0]) < 25]
        xc = (x[0] + x[2]) / 2
        esq = sorted((w for w in cand if (w[0] + w[2]) / 2 < xc), key=lambda w: -w[2])
        dir_ = sorted((w for w in cand if (w[0] + w[2]) / 2 > xc), key=lambda w: w[0])
        if not esq or not dir_:
            continue
        L, H = float(esq[0][4].replace(",", ".")), float(dir_[0][4].replace(",", "."))
        # peitoril: número sozinho logo abaixo da etiqueta, no mesmo bloco
        abaixo = [w for (b2, _), ws2 in linhas.items() if b2 == b and len(ws2) == 1 for w in ws2
                  if NUM.match(w[4]) and 0 < w[1] - x[3] < 6 and abs((w[0] + w[2]) / 2 - xc) < 10]
        peit = float(abaixo[0][4].replace(",", ".")) if abaixo else None
        res.append(Esquadria("porta" if H >= 2.0 else "janela", L, H, xc, (x[1] + x[3]) / 2, peit))
    return res


def resumo(esqs: list[Esquadria]) -> Counter:
    return Counter((e.tipo, e.chave + (f" / peitoril {e.peitoril_m:.2f}".replace(".", ",") if e.peitoril_m else ""))
                   for e in esqs)
