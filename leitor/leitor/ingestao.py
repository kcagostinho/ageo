"""Ingestão: extrai do PDF vetorial os traços (por camada do CAD) e os textos com coordenadas.

Todas as coordenadas saem na orientação em que a prancha é vista (rotação da página
já aplicada), em pontos PDF (1 pt = 1/72 pol = 0,3528 mm no papel).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf


@dataclass
class Pagina:
    numero: int                     # 1-based
    largura: float
    altura: float
    # cada segmento: (camada, espessura, x0, y0, x1, y1)
    segmentos: list[tuple[str, float, float, float, float, float]] = field(default_factory=list)
    # cada palavra: (x0, y0, x1, y1, texto, bloco, linha)
    palavras: list[tuple[float, float, float, float, str, int, int]] = field(default_factory=list)
    # curvas de Bézier originais (para achar arcos de porta): (camada, x0, y0, x1, y1, x2, y2, x3, y3)
    curvas: list[tuple] = field(default_factory=list)

    def camadas(self) -> dict[str, int]:
        cont: dict[str, int] = {}
        for s in self.segmentos:
            cont[s[0]] = cont.get(s[0], 0) + 1
        return dict(sorted(cont.items(), key=lambda kv: -kv[1]))


def _bezier(p0, p1, p2, p3, n: int = 8):
    pts = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
        pts.append((a * p0.x + b * p1.x + c * p2.x + d * p3.x,
                    a * p0.y + b * p1.y + c * p2.y + d * p3.y))
    return pts


def extrair_pagina(pdf: str | Path, indice: int) -> Pagina:
    doc = pymupdf.open(str(pdf))
    pg = doc[indice]
    m = pg.rotation_matrix
    pag = Pagina(numero=indice + 1, largura=pg.rect.width, altura=pg.rect.height)

    def add(lay, w, pts):
        pts = [pymupdf.Point(p) * m for p in pts]
        for a, b in zip(pts, pts[1:]):
            if abs(a.x - b.x) + abs(a.y - b.y) > 1e-6:
                pag.segmentos.append((lay, round(w, 2), round(a.x, 3), round(a.y, 3), round(b.x, 3), round(b.y, 3)))

    for dr in pg.get_drawings():
        lay = dr.get("layer") or ""
        w = dr.get("width") or 0.0
        for it in dr["items"]:
            op = it[0]
            if op == "l":
                add(lay, w, [it[1], it[2]])
            elif op == "c":
                add(lay, w, _bezier(*it[1:5]))
                q = [pymupdf.Point(p) * m for p in it[1:5]]
                pag.curvas.append((lay, *[round(v, 3) for pt in q for v in (pt.x, pt.y)]))
            elif op == "qu":
                q = it[1]
                add(lay, w, [q.ul, q.ur, q.lr, q.ll, q.ul])
            elif op == "re":
                r = it[1]
                add(lay, w, [r.tl, r.tr, r.br, r.bl, r.tl])

    for x0, y0, x1, y1, txt, blk, lin, _ in pg.get_text("words"):
        r = pymupdf.Rect(x0, y0, x1, y1) * m
        pag.palavras.append((round(r.x0, 3), round(r.y0, 3), round(r.x1, 3), round(r.y1, 3), txt, blk, lin))
    return pag


def extrair(pdf: str | Path, cache_dir: str | Path | None = None) -> list[Pagina]:
    """Extrai todas as páginas; guarda em cache JSON para as próximas execuções."""
    pdf = Path(pdf)
    cache = Path(cache_dir) / f"{pdf.stem}.ingestao.v2.json" if cache_dir else None
    if cache and cache.exists() and cache.stat().st_mtime >= pdf.stat().st_mtime:
        dados = json.loads(cache.read_text())
        return [Pagina(**{**p, "segmentos": [tuple(s) for s in p["segmentos"]],
                          "palavras": [tuple(w) for w in p["palavras"]],
                          "curvas": [tuple(c) for c in p.get("curvas", [])]}) for p in dados]
    paginas = [extrair_pagina(pdf, i) for i in range(pymupdf.open(str(pdf)).page_count)]
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps([p.__dict__ for p in paginas]))
    return paginas
