"""CUB/m² do SindusCon-SP (calculado com a FGV), para conferir a ordem de grandeza do orçamento.

Fonte: página https://sindusconsp.com.br/servicos/cub/ (mês corrente, R8-N sem e com desoneração)
e a planilha 'Cub-Serie-Historica-<Mês>-<aa>.xlsx' ligada nela (todos os padrões, sem desoneração).
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import urllib.request
from pathlib import Path

PAGINA = "https://sindusconsp.com.br/servicos/cub/"
UA = "Mozilla/5.0 (X11; Linux x86_64) leitor-de-projetos"
# ordem das colunas da série histórica (R$/m², sem desoneração)
PADROES = ["R1-B", "PP-4B", "R8-B", "PIS", "R1-N", "PP4-N", "R8-N", "R16-N", "R1-A", "R8-A", "R16-A", "CAL-8N"]


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def _num(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def ler_pagina(txt: str) -> dict:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", txt, flags=re.S)
    s = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)))
    out = {}
    m = re.search(r"(\w+) (\d{4}) - R\$/m² Sem desoneração \. R8-N ([\d.,]+).*?Com desoneração \. R8-N ([\d.,]+)", s)
    if m:
        out = {"mes_nome": m.group(1), "ano": int(m.group(2)), "R8-N": {"sd": _num(m.group(3)), "cd": _num(m.group(4))}}
    x = re.search(r'href="([^"]*Cub-Serie-Historica[^"]*\.xlsx)"', txt)
    if x:
        out["serie_url"] = x.group(1)
    return out


def ler_serie(xlsx: Path) -> tuple[str, dict]:
    """Última linha mensal da tabela de R$/m² (12 padrões) da série histórica."""
    import openpyxl
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    ult = None
    for r in wb.worksheets[0].iter_rows(values_only=True):
        if isinstance(r[0], dt.datetime) and all(isinstance(v, (int, float)) and v > 300 for v in r[1:13]):
            if ult is None or r[0] >= ult[0]:
                ult = r
        elif ult is not None and isinstance(r[0], dt.datetime):
            break                                    # acabou o primeiro bloco (R$/m²)
    if ult is None:
        return "", {}
    return ult[0].strftime("%m/%Y"), {p: round(float(v), 2) for p, v in zip(PADROES, ult[1:13])}


def carregar(pasta: Path) -> dict | None:
    """{mes, padroes: {nome: {sd, cd?}}, fonte}. Usa o cache da pasta se a rede falhar."""
    pasta.mkdir(parents=True, exist_ok=True)
    cache = pasta / "cub_sinduscon_sp.json"
    try:
        pag = ler_pagina(_get(PAGINA).decode("utf-8", "ignore"))
        padroes, mes = {}, ""
        if pag.get("serie_url"):
            xl = pasta / Path(pag["serie_url"]).name
            if not xl.exists():
                xl.write_bytes(_get(pag["serie_url"]))
            mes, sd = ler_serie(xl)
            padroes = {k: {"sd": v} for k, v in sd.items()}
        if "R8-N" in pag:
            padroes.setdefault("R8-N", {}).update(pag["R8-N"])
        if not padroes:
            raise ValueError("CUB não encontrado na página")
        d = {"mes": mes or f"{pag.get('mes_nome', '')}/{pag.get('ano', '')}", "padroes": padroes,
             "fonte": "SindusCon-SP/FGV (" + PAGINA + ")"}
        cache.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        return d
    except Exception:
        if cache.exists():
            return json.loads(cache.read_text(encoding="utf-8"))
        return None
