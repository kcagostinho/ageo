"""Pé-direito por pavimento, lido da corrente de cotas verticais dos cortes.

Nos cortes, a corrente vertical alterna pé-direito e espessura de laje (ex.: 2,60 | 0,15 | 2,80 ...).
De baixo para cima, os valores acima de 2,0 m são os pés-direitos dos pavimentos, na ordem
subsolo → térreo → tipos. O resultado é premissa: vai para a planilha, onde pode ser editado.
"""
from __future__ import annotations

import re

from .ingestao import Pagina
from .vistas import encontrar_vistas

NUM = re.compile(r"^\d{1,2},\d{2}$")


def correntes_verticais(pag: Pagina, caixa, folga=40.0, min_cotas=8):
    """Colunas de cotas com texto vertical, de baixo para cima."""
    ws = [w for w in pag.palavras if caixa[0] - folga < w[0] < caixa[2] + folga and caixa[1] - folga < w[1] < caixa[3] + folga
          and (w[3] - w[1]) > (w[2] - w[0]) and NUM.match(w[4])]
    cols: dict[int, list] = {}
    for w in ws:
        cols.setdefault(round(w[0] / 5), []).append(w)
    out = []
    for lst in cols.values():
        if len(lst) >= min_cotas:
            out.append([float(w[4].replace(",", ".")) for w in sorted(lst, key=lambda w: -w[1])])
    return out


def ler_pe_direito(paginas: list[Pagina], pavimentos: list[str]) -> tuple[dict[str, float], str]:
    """pavimentos: títulos das plantas de baixo para cima. Devolve ({pavimento: PD}, fonte)."""
    melhor, fonte = None, ""
    for pag in paginas:
        for v in encontrar_vistas(pag):
            if "corte" not in v.titulo.lower():
                continue
            for cad in correntes_verticais(pag, v.caixa):
                pds = [x for x in cad if 2.0 <= x <= 6.0]
                if len(pds) >= len(pavimentos) and (melhor is None or len(cad) > len(melhor)):
                    melhor, fonte = cad, f"{v.titulo} (prancha {pag.numero}), cotas verticais"
    if melhor is None:
        return {}, ""
    pds = [x for x in melhor if 2.0 <= x <= 6.0]
    return {p: pds[i] for i, p in enumerate(pavimentos)}, fonte
