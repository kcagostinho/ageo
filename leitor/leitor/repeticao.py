"""Escala única do documento e pavimentos repetidos (pavimento-tipo).

Dois problemas que faziam andares iguais darem números diferentes:

1. Escala: cada vista era calibrada pelas próprias cotas. Como as cotas são arredondadas
   ao centímetro, vistas do mesmo PDF saíam com escalas que diferem em até 0,02%. O PDF tem
   um único fator de exportação; aqui a escala de cada escala nominal (1:50, 1:100…) é a
   mediana ponderada (pelo nº de cotas) das vistas, e vale para todas as que ficam a menos
   de 0,3% dela.

2. Coordenadas: cada pavimento fica numa posição da folha e o PDF arredonda as coordenadas
   (±0,03 pt ≈ ±0,5 mm na obra). Isso basta para uma parede passar de 2,999 para 3,001 m e
   mudar a paginação. Quando as linhas de parede (A-WALL) de uma vista coincidem com as de
   outra já lida (mesma quantidade, ≥ 98% a menos de 0,15 pt depois de transladar), a vista é
   uma repetição: ela é lida numa cópia da folha transladada para cima da referência, e cada
   ponto que tem par na referência (mesma camada) recebe a coordenada exata dela. Assim toda a
   leitura (ambientes, paredes, paginação) vê os mesmos números. O que for diferente de verdade
   (ex.: a escada do último andar) fica como está. Os dados do andar ficam no sistema de
   coordenadas da referência; 'desloc' diz onde ele está na folha (para recortar a imagem).
"""
from __future__ import annotations

from collections import defaultdict

CAMADA = "A-WALL"
MARGEM = 15.0          # pt além da caixa da vista
TOL_CASAR = 0.15       # pt: linha "igual" entre vistas
TOL_AJUSTE = 0.12      # pt: ponto que recebe a coordenada da referência


def escala_unica(itens: list[tuple[float, float | None, int]]) -> dict:
    """itens: (m_nominal, m_calibrado ou None, nº de cotas). Devolve {m_nominal: m do documento}."""
    grupos = defaultdict(list)
    for nom, cal, n in itens:
        if cal:
            grupos[round(nom, 9)].append((cal, max(n, 1)))
    out = {}
    for nom, xs in grupos.items():
        xs.sort()
        meio, acc = sum(w for _, w in xs) / 2, 0
        for v, w in xs:
            acc += w
            if acc >= meio:
                out[nom] = v
                break
    return out


def _dentro(x, y, c, folga=MARGEM):
    return c[0] - folga <= x <= c[2] + folga and c[1] - folga <= y <= c[3] + folga


def assinatura(pag, caixa) -> tuple[tuple[float, float], list]:
    """Linhas de parede da vista relativas ao canto mínimo: (origem, [(ax, ay, bx, by)])."""
    segs = [s for s in pag.segmentos if s[0] == CAMADA and _dentro((s[2] + s[4]) / 2, (s[3] + s[5]) / 2, caixa, 5)]
    if not segs:
        return (0.0, 0.0), []
    ox = min(min(s[2], s[4]) for s in segs)
    oy = min(min(s[3], s[5]) for s in segs)
    out = []
    for s in segs:
        a, b = (s[2] - ox, s[3] - oy), (s[4] - ox, s[5] - oy)
        if b < a:
            a, b = b, a
        out.append((a[0], a[1], b[0], b[1]))
    return (ox, oy), out


def _grade(pontos, passo=0.5):
    g = defaultdict(list)
    for p in pontos:
        g[(int(p[0] // passo), int(p[1] // passo))].append(p)
    return g


def _vizinho(g, x, y, tol, passo=0.5):
    i, j = int(x // passo), int(y // passo)
    melhor, dm = None, tol
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            for p in g.get((i + di, j + dj), ()):
                d = max(abs(p[0] - x), abs(p[1] - y))
                if d <= dm:
                    melhor, dm = p, d
    return melhor


def semelhanca(a: list, b: list) -> float:
    """Fração das linhas de a que têm par em b (extremos a menos de TOL_CASAR)."""
    if not a or len(a) != len(b):
        return 0.0
    g = _grade([(s[0], s[1], s) for s in b])
    ok = 0
    for s in a:
        for di in (-1, 0, 1):
            achou = False
            for dj in (-1, 0, 1):
                for p in g.get((int(s[0] // 0.5) + di, int(s[1] // 0.5) + dj), ()):
                    t = p[2]
                    if max(abs(t[0] - s[0]), abs(t[1] - s[1]), abs(t[2] - s[2]), abs(t[3] - s[3])) <= TOL_CASAR:
                        achou = True
                        break
                if achou:
                    break
            if achou:
                ok += 1
                break
    return ok / len(a)


def copia_alinhada(pag, caixa, pag_ref=None, caixa_ref=None, T=(0.0, 0.0), margem: float = 80.0):
    """Cópia da folha só com o que está na vista (caixa + margem), transladada por −T para ficar
    sobre a vista de referência. Cada ponto que tem par na referência (mesma camada, a menos de
    TOL_AJUSTE) recebe a coordenada exata da referência. Sem referência, só recorta.
    Devolve (página, caixa para a leitura, nº de pontos ajustados)."""
    from .ingestao import Pagina
    dx, dy = -T[0], -T[1]
    grades = {}
    if pag_ref is not None:
        pts = defaultdict(list)
        for s in pag_ref.segmentos:
            if _dentro((s[2] + s[4]) / 2, (s[3] + s[5]) / 2, caixa_ref, margem):
                pts[s[0]] += [(s[2], s[3]), (s[4], s[5])]
        for c in pag_ref.curvas:
            if _dentro(c[1], c[2], caixa_ref, margem):
                pts["~" + c[0]] += [(c[k], c[k + 1]) for k in range(1, len(c) - 1, 2)]
        grades = {k: _grade(v) for k, v in pts.items()}
    n = 0

    def aj(camada, x, y):
        nonlocal n
        x, y = x + dx, y + dy
        g = grades.get(camada)
        if g:
            q = _vizinho(g, x, y, TOL_AJUSTE)
            if q is not None:
                n += q != (x, y)
                return q
        return x, y

    segs = []
    for s in pag.segmentos:
        if _dentro((s[2] + s[4]) / 2, (s[3] + s[5]) / 2, caixa, margem):
            a, b = aj(s[0], s[2], s[3]), aj(s[0], s[4], s[5])
            segs.append((s[0], s[1], a[0], a[1], b[0], b[1]))
    curvas = []
    for c in pag.curvas:
        if _dentro(c[1], c[2], caixa, margem):
            q = [aj("~" + c[0], c[k], c[k + 1]) for k in range(1, len(c) - 1, 2)]
            curvas.append((c[0], *[v for p in q for v in p]))
    palavras = [(w[0] + dx, w[1] + dy, w[2] + dx, w[3] + dy, *w[4:]) for w in pag.palavras
                if _dentro((w[0] + w[2]) / 2, (w[1] + w[3]) / 2, caixa, margem)]
    nova = Pagina(pag.numero, pag.largura, pag.altura, segs, palavras, curvas)
    caixa_leitura = caixa_ref if caixa_ref is not None else caixa
    return nova, caixa_leitura, n
