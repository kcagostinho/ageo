"""Renderização rápida (Pillow) de uma região da prancha, colorindo camadas — para conferência."""
from __future__ import annotations

from PIL import Image, ImageDraw

from .ingestao import Pagina

CINZA = (215, 215, 215)


def renderizar(pag: Pagina, regiao: tuple[float, float, float, float], escala_px: float = 2.0,
               cores: dict[str, tuple[int, int, int]] | None = None, textos: bool = True,
               poligonos: list[tuple[list[tuple[float, float]], tuple[int, int, int, int]]] | None = None) -> Image.Image:
    x0, y0, x1, y1 = regiao
    W, H = int((x1 - x0) * escala_px), int((y1 - y0) * escala_px)
    img = Image.new("RGB", (W, H), "white")
    dr = ImageDraw.Draw(img, "RGBA")
    f = lambda x, y: ((x - x0) * escala_px, (y - y0) * escala_px)
    if poligonos:
        for pts, cor in poligonos:
            dr.polygon([f(*p) for p in pts], fill=cor, outline=cor[:3] + (255,))
    for lay, w, ax, ay, bx, by in pag.segmentos:
        if max(ax, bx) < x0 or min(ax, bx) > x1 or max(ay, by) < y0 or min(ay, by) > y1:
            continue
        cor = (cores or {}).get(lay, CINZA if cores else (0, 0, 0))
        dr.line([f(ax, ay), f(bx, by)], fill=cor, width=2 if cor != CINZA else 1)
    if textos:
        for wx0, wy0, wx1, wy1, *_ in pag.palavras:
            if wx1 < x0 or wx0 > x1 or wy1 < y0 or wy0 > y1:
                continue
            dr.rectangle([f(wx0, wy0), f(wx1, wy1)], outline=(255, 150, 0))
    return img
