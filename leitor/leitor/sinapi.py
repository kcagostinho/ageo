"""SINAPI (Caixa): baixa o relatório mensal e extrai uma UF num JSON pequeno.

Arquivo da Caixa (formato a partir de 2025): SINAPI-AAAA-MM-formato-xlsx.zip, com
'SINAPI_Referência_AAAA_MM.xlsx' dentro. Abas usadas:
  ISD / ICD   preço dos insumos sem / com desoneração (uma coluna por UF)
  CSD / CCD   custo das composições sem / com desoneração (custo e %AS por UF)
  Analítico   itens de cada composição (insumo ou composição auxiliar + coeficiente)

O site da Caixa responde primeiro com um redirecionamento que grava o cookie 'security';
por isso o download guarda cookies.
"""
from __future__ import annotations

import http.cookiejar
import json
import re
import urllib.request
import zipfile
from pathlib import Path

URL = "https://www.caixa.gov.br/Downloads/sinapi-relatorios-mensais/SINAPI-{mes}-formato-xlsx.zip"
UA = "Mozilla/5.0 (X11; Linux x86_64) leitor-de-projetos"


def _abrir(url: str, timeout=120):
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    op.addheaders = [("User-Agent", UA)]
    return op.open(url, timeout=timeout)


def baixar(mes: str, pasta: Path) -> Path:
    """mes = 'AAAA-MM'. Devolve o caminho do xlsx de referência (baixa só se faltar)."""
    pasta.mkdir(parents=True, exist_ok=True)
    zp = pasta / f"SINAPI-{mes}.zip"
    if not zp.exists():
        with _abrir(URL.format(mes=mes), timeout=600) as r, open(zp, "wb") as f:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
    with zipfile.ZipFile(zp) as z:
        nome = next(n for n in z.namelist() if "Refer" in n and n.endswith(".xlsx"))
        destino = pasta / f"SINAPI_Referencia_{mes.replace('-', '_')}.xlsx"
        if not destino.exists():
            destino.write_bytes(z.read(nome))
    return destino


def ultimo_mes(ate: str, tentativas: int = 6) -> str | None:
    """Mês mais recente publicado, a partir de 'ate' (AAAA-MM) para trás."""
    a, m = map(int, ate.split("-"))
    for _ in range(tentativas):
        mes = f"{a:04d}-{m:02d}"
        try:
            req = urllib.request.Request(URL.format(mes=mes), method="HEAD")
            jar = http.cookiejar.CookieJar()
            op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
            op.addheaders = [("User-Agent", UA)]
            with op.open(req, timeout=60) as r:
                if r.status == 200:
                    return mes
        except Exception:
            pass
        m -= 1
        if m == 0:
            a, m = a - 1, 12
    return None


def _codigo(v):
    """O código das composições vem numa fórmula HYPERLINK(...; 104658)."""
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str):
        n = re.findall(r"(\d+)\)\s*$", v) or re.findall(r"\d+", v)
        return int(n[-1]) if n else None
    return None


def extrair(xlsx: Path, uf: str = "SP") -> dict:
    """Lê o xlsx da Caixa e devolve só a UF pedida:
    {mes, uf, insumos: {cod: [descr, un, preco_sd, preco_cd, classe]},
     composicoes: {cod: [descr, un, custo_sd, custo_cd, grupo]},
     analitico: {cod: [[tipo, cod_item, coef], ...]}}"""
    import openpyxl
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=False)
    mes = None
    out = {"uf": uf, "insumos": {}, "composicoes": {}, "analitico": {}}

    def num(v):
        return float(v) if isinstance(v, (int, float)) else None

    for aba, k in (("ISD", 2), ("ICD", 3)):
        ws = wb[aba]
        col = None
        for i, r in enumerate(ws.iter_rows(values_only=True)):
            if mes is None and r and r[0] == "Mês de Referência:":
                mes = r[1]
            if col is None:
                if r and r[0] == "Classificação":
                    col = list(r).index(uf)
                continue
            cod = _codigo(r[1])
            if cod is None:
                continue
            reg = out["insumos"].setdefault(cod, [r[2], r[3], None, None, r[0]])
            reg[k] = num(r[col])
    for aba, k in (("CSD", 2), ("CCD", 3)):
        ws = wb[aba]
        col = None
        for r in ws.iter_rows(values_only=True):
            if col is None:
                if r and r[0] is None and uf in r:
                    col = list(r).index(uf)      # linha das UFs logo acima do cabeçalho
                continue
            if r[0] == "Grupo":
                continue
            cod = _codigo(r[1])
            if cod is None:
                continue
            reg = out["composicoes"].setdefault(cod, [r[2], r[3], None, None, r[0]])
            reg[k] = num(r[col])
    ws = wb["Analítico"]
    cab = False
    for r in ws.iter_rows(values_only=True):
        if not cab:
            cab = bool(r) and r[0] == "Grupo"
            continue
        cod = _codigo(r[1])
        if cod is None:
            continue
        if r[2] in ("INSUMO", "COMPOSICAO"):
            out["analitico"].setdefault(cod, []).append([r[2][0], _codigo(r[3]), num(r[6])])
    out["mes"] = mes
    return out


def carregar(mes: str, pasta: Path, uf: str = "SP") -> dict:
    """JSON da UF em cache; baixa e extrai na primeira vez."""
    js = pasta / f"sinapi_{uf}_{mes.replace('-', '_')}.json"
    if js.exists():
        return json.loads(js.read_text(encoding="utf-8"))
    d = extrair(baixar(mes, pasta), uf)
    js.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return d


def buscar(d: dict, *termos: str, onde: str = "insumos", nao: tuple = ()) -> list:
    """Busca por termos (todos presentes, sem acento-sensível) nas descrições."""
    import unicodedata
    f = lambda s: unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()
    ts = [f(t) for t in termos]
    ns = [f(t) for t in nao]
    return [(int(c), *v) for c, v in d[onde].items()
            if all(t in f(v[0]) for t in ts) and not any(n in f(v[0]) for n in ns)]
