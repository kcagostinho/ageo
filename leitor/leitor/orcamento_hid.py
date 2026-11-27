"""Preço SINAPI da água fria: tubos por DN e tipo de trecho, conexões e registros por código do projeto.

O SINAPI separa a composição pelo tipo de trecho, porque a produtividade muda muito:
  - prumada (coluna vertical entre andares);
  - ramal de distribuição (barrilete, alimentação, térreo/subsolo);
  - ramal ou sub-ramal (dentro do apartamento, até o ponto de consumo).
Cada trecho do modelo vai para um desses; cada conexão, pelo lugar onde está (na coluna = prumada).
Premissas da escolha das peças em PECAS (registro de gaveta cromado = latão com canopla cromada; registro de
chuveiro PVC = registro de pressão PVC soldável; hidrômetro DN 1" 7 m³/h).
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict

from .sinapi import buscar

SUB, DIST, PRU, RES = "RAMAL OU SUB-RAMAL", "RAMAL DE DISTRIBUICAO", "PRUMADA", "RESERVACAO PREDIAL"
NOME_CTX = {SUB: "ramal/sub-ramal (apartamento)", DIST: "ramal de distribuição", PRU: "prumada", RES: "reservação (barrilete)"}

# código do projeto -> termos da descrição SINAPI (sem o tipo de trecho)
PECAS = {
    "01": ("BUCHA DE REDUCAO, CURTA, PVC, SOLDAVEL, DN 25 X 20 MM",),
    "02": ("BUCHA DE REDUCAO, CURTA, PVC, SOLDAVEL, DN 32 X 25 MM",),
    "03": ("BUCHA DE REDUCAO, PVC, SOLDAVEL, DN 40MM X 32MM",),
    "04": ("BUCHA DE REDUCAO, CURTA, PVC, SOLDAVEL, DN 50 X 40 MM",),
    "05": ("JOELHO 90 GRAUS, PVC, SOLDAVEL, DN 20MM,",),
    "06": ("JOELHO 90 GRAUS, PVC, SOLDAVEL, DN 25MM,",),
    "07": ("JOELHO 90 GRAUS, PVC, SOLDAVEL, DN 32MM,",),
    "08": ("JOELHO 90 GRAUS, PVC, SOLDAVEL, DN 50MM,",),
    "09": ("JOELHO 90 GRAUS COM BUCHA DE LATAO, PVC, SOLDAVEL, DN 20MM, X 1/2",),
    "10": ("JOELHO 90 GRAUS COM BUCHA DE LATAO, PVC, SOLDAVEL, DN 25MM, X 1/2",),
    "11": ("TE DE REDUCAO, PVC, SOLDAVEL, DN 25MM X 20MM",),
    "12": ("TE DE REDUCAO, PVC, SOLDAVEL, DN 32MM X 25MM",),
    "13": ("TE, PVC, SOLDAVEL, DN 20MM,",),
    "14": ("TE, PVC, SOLDAVEL, DN 25MM,",),
    "15": ("TE, PVC, SOLDAVEL, DN 32MM,",),
    "16": ("TE, PVC, SOLDAVEL, DN 40MM,",),
    "17": ("TE, PVC, SOLDAVEL, DN 50MM,",),
    "70": ("HIDROMETRO DN 1\", 7 M",),
    "71": ("REGISTRO DE PRESSAO, PVC, SOLDAVEL, VOLANTE SIMPLES, DN 20 MM",),
    "72": ("REGISTRO DE PRESSAO, PVC, SOLDAVEL, VOLANTE SIMPLES, DN 25 MM",),
    "73": ("REGISTRO DE GAVETA BRUTO, LATAO, ROSCAVEL, 1/2\", COM ACABAMENTO E CANOPLA CROMADOS",),
    "74": ("REGISTRO DE GAVETA BRUTO, LATAO, ROSCAVEL, 3/4\", COM ACABAMENTO E CANOPLA CROMADOS",),
    "75": ("REGISTRO DE ESFERA, PVC, SOLDAVEL, COM VOLANTE, DN 25 MM",),
    "76": ("REGISTRO DE ESFERA, PVC, SOLDAVEL, COM VOLANTE, DN 32 MM",),
    "77": ("REGISTRO DE ESFERA, PVC, SOLDAVEL, COM VOLANTE, DN 50 MM",),
}
# sem composição no SINAPI: derivada de uma parecida, trocando o insumo (composição base, insumo sai, insumo entra)
DERIVADAS = {"09": (90373, 20147, 3515)}     # joelho c/ bucha de latão 20 × 1/2" a partir do 25 × 1/2" (ramal/sub-ramal)
NA_COLUNA = {"01", "02", "11", "12", "14"}          # peças que ficam no eixo da coluna (prumada)
NO_RESERVATORIO = {"03", "04", "08", "15", "16", "17", "77"}


def _sa(t):
    import unicodedata
    return unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().upper()


def _composicao(sin, termos, ctx_ordem):
    """Composição SINAPI com os termos, preferindo o tipo de trecho na ordem dada."""
    cands = buscar(sin, *termos, onde="composicoes")
    if not cands:
        return None
    for ctx in ctx_ordem:
        if ctx is None:
            sem = [c for c in cands if not any(k in _sa(c[1]) for k in ("RAMAL", "PRUMADA", "RESERVA", "DRENO", "SUBCOLETOR"))]
            if sem:
                return sem[0]
            continue
        cs = [c for c in cands if ctx in _sa(c[1])]
        if cs:
            return cs[0]
    cs = [c for c in cands if "DRENO" not in c[1].upper()]
    return (cs or cands)[0]


ORDEM = {SUB: [SUB, DIST, PRU, None], DIST: [DIST, SUB, PRU, None], PRU: [PRU, DIST, SUB, None],
         RES: [RES, DIST, PRU, SUB, None]}


def _ctx_trecho(t, colunas_xy, m_tipo):
    g = t.get("grupo")
    if g == "Colunas do prédio":
        return PRU
    if g == "Cobertura":
        return DIST
    if g == "Térreo e subsolo":
        return SUB if int(t["dn"]) == 20 else DIST
    c = colunas_xy.get(t.get("col"))
    if c and t.get("a") and t.get("b"):
        if all(math.dist(p[:2], c) * m_tipo < 0.03 for p in (t["a"], t["b"])) and abs(t["a"][2] - t["b"][2]) > 0.3:
            return PRU
    return SUB


def calcular(af: dict, sin: dict, prem: dict, m_tipo: float) -> dict:
    k = 3 if prem.get("desonerado") else 2
    colunas_xy = {c["id"]: c["xy"] for c in af["colunas"]}
    comp = (af.get("complemento") or {}).get("trechos", [])
    linhas, nao_achou = [], []
    # tubos
    tubos = Counter()
    por_trecho = {}
    for t in af["trechos"] + af["curtos"] + comp:
        ctx = _ctx_trecho(t, colunas_xy, m_tipo)
        tubos[(ctx, int(t["dn"]))] += t["L"]
    precos_tubo = {}
    for (ctx, dn), q in sorted(tubos.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        c = _composicao(sin, ("TUBO, PVC, SOLDAVEL, DE %dMM" % dn,), ORDEM[ctx])
        if not c:
            nao_achou.append(f"tubo DN{dn} ({NOME_CTX[ctx]})")
            continue
        precos_tubo[(ctx, dn)] = c[k + 1]
        linhas.append({"grupo": "Tubos", "item": f"Tubo PVC soldável DN{dn} · {NOME_CTX[ctx]}", "sinapi": c[0], "descr": c[1],
                       "un": c[2].lower(), "qtd": round(q, 2), "preco": c[k + 1], "custo": round(q * c[k + 1], 2)})
    for t in af["trechos"]:
        ctx = _ctx_trecho(t, colunas_xy, m_tipo)
        if (ctx, int(t["dn"])) in precos_tubo:
            por_trecho[t["id"]] = round(t["L"] * precos_tubo[(ctx, int(t["dn"]))], 2)
    # conexões e registros
    pecas = Counter()
    for cn in af["conexoes"]:
        c = colunas_xy.get(cn["col"])
        na_col = c and math.dist(cn["p"][:2], c) * m_tipo < 0.20 and cn["cod"] in NA_COLUNA     # tê da coluna (o nó pode cair na boca do ramal)
        pecas[(cn["cod"], PRU if na_col else SUB)] += 1
    for pav, cods in ((af.get("complemento") or {}).get("codigos_plantas") or {}).items():
        for cod, n in cods.items():
            ctx = (RES if cod in NO_RESERVATORIO else DIST) if pav == "Cobertura" else (SUB if pav == "Pavimento Térreo" else DIST)
            pecas[(cod, ctx)] += n
    for (cod, ctx), n in sorted(pecas.items()):
        termos = PECAS.get(cod)
        c = _composicao(sin, termos, ORDEM[ctx]) if termos else None
        if not c and cod in DERIVADAS:
            base, sai, entra = DERIVADAS[cod]
            cb, ia, ib = sin["composicoes"].get(str(base)), sin["insumos"].get(str(sai)), sin["insumos"].get(str(entra))
            coef = next((x[2] for x in sin["analitico"].get(str(base), []) if x[0] == "I" and x[1] == sai), 1.0)
            if cb and ia and ib:
                preco = round(cb[k] - ia[k] * coef + ib[k] * coef, 2)
                c = (f"{base}*", f"{ib[0]} — preço da composição {base} ({cb[0][:60]}...) trocando o insumo {sai} pelo {entra}",
                     "UN", None, None)
                c = (c[0], c[1], c[2], preco, preco)
        if not c:
            nao_achou.append(f"código {cod} ({NOME_CTX[ctx]})")
            continue
        grupo = "Registros e hidrômetro" if int(cod) >= 70 else "Conexões"
        linhas.append({"grupo": grupo, "item": f"{cod} · " + c[1].split(" - ")[0].split(", INSTALAD")[0].title()[:70] + f" · {NOME_CTX[ctx]}",
                       "sinapi": c[0], "descr": c[1], "un": c[2].lower(), "qtd": n, "preco": c[k + 1], "custo": round(n * c[k + 1], 2),
                       "codigo": cod})
    total = round(sum(L["custo"] for L in linhas), 2)
    por_grupo = defaultdict(float)
    for L in linhas:
        por_grupo[L["grupo"]] += L["custo"]
    return {"mes": sin.get("mes"), "uf": sin.get("uf"), "desonerado": bool(prem.get("desonerado")), "linhas": linhas, "total": total,
            "grupos": {g: round(v, 2) for g, v in por_grupo.items()}, "por_trecho": por_trecho, "nao_achou": nao_achou,
            "premissas": ["Registro de gaveta cromado (73/74): SINAPI de latão com acabamento e canopla cromados (não há de PVC).",
                          "Registro de chuveiro PVC (71/72): registro de pressão PVC soldável, volante simples.",
                          "Hidrômetro (70): DN 1\" 7 m³/h; em geral fornecido pela concessionária — conferir.",
                          "Tipo de trecho: coluna vertical = prumada; barrilete, alimentação, térreo e subsolo = ramal de distribuição; "
                          "dentro do apartamento e pontos do salão (DN20) = ramal/sub-ramal.",
                          "Conexões das verticais do barrilete e do salão que só aparecem nos isométricos ficam de fora (diferença na aba Água fria)."]}


# ----------------------------------------------------------------------------------------------
# Esgoto
# ----------------------------------------------------------------------------------------------
RAMAL_ES, PRUMADA_ES, SUBCOL = "RAMAL DE DESCARGA OU RAMAL DE ESGOTO", "PRUMADA DE ESGOTO SANITARIO OU VENTILACAO", "SUBCOLETOR AEREO"
NOME_CTX_ES = {RAMAL_ES: "ramal de descarga/esgoto (apartamento)", PRUMADA_ES: "tubo de queda / ventilação", SUBCOL: "subcoletor (térreo/subsolo)"}
ORDEM_ES = {RAMAL_ES: [RAMAL_ES, PRUMADA_ES, SUBCOL, None], PRUMADA_ES: [PRUMADA_ES, RAMAL_ES, SUBCOL, None],
            SUBCOL: [SUBCOL, PRUMADA_ES, RAMAL_ES, None]}
# caixas e ralos (quantidade da tabela do projetista): termo da descrição -> (tipo, código SINAPI, observação)
CAIXAS = [("Quadrados Brancos 100", "C", 89707, "caixa sifonada 100 mm (SINAPI 100×100×50)"),
          ("Redondos Brancos 150", "C", 89708, "caixa sifonada 150 mm (SINAPI 150×185×75)"),
          ("Caixa de Gordura", "C", 98110, "caixa de gordura PVC (SINAPI pequena, 19 L)"),
          ("Caixa de Inspeção", "I", 41474, "caixa de inspeção PVC 300×300 com tampa (só material)"),
          ("Prolongamento p/ Caixa Sifonada 100", "I", 11735, "prolongamento 100 mm (só material)"),
          ("Prolongamento p/ Caixa Sifonada 150", "I", 11738, "prolongamento 150×200 mm (só material)"),
          ("Ralo Quadrado", "C", 89710, "ralo seco PVC 100×40")]


def _termos_conexao_esgoto(descr):
    import re
    d = descr.upper().replace("º", "").replace("°", "")
    nums = [int(x) for x in re.findall(r"(\d+)\s*(?:X|MM)", d)]
    if not nums:
        return None
    dn = " X ".join(str(n) for n in nums[:2]) + " MM"
    base = ", PVC, SERIE NORMAL, ESGOTO PREDIAL, DN " + dn
    if d.startswith("JOELHO 45"):
        return ("JOELHO 45 GRAUS" + base,)
    if d.startswith("JOELHO 90"):
        return ("JOELHO 90 GRAUS" + base,)
    if d.startswith("CURVA 90") and "LONGA" in d:
        return ("CURVA LONGA 90 GRAUS" + base,)
    if d.startswith("JUN") and "SIMPLES" in d:
        return ("JUNCAO SIMPLES" + base,)
    if d.startswith("LUVA SIMPLES"):
        return ("LUVA SIMPLES" + base,)
    if d.startswith("TÊ") or d.startswith("TE "):
        return ("TE" + base,)
    if d.startswith("ADAPTADOR") and "VASO" in d:
        return ("JOELHO 90 GRAUS, PVC, SERIE NORMAL, ESGOTO PREDIAL, DN 100 MM",)   # sem composição: usa a do joelho 100
    return None


def calcular_esgoto(es: dict, sin: dict, prem: dict) -> dict:
    k = 3 if prem.get("desonerado") else 2
    linhas, nao_achou = [], []
    tubos = Counter()
    for t in es["apartamentos"]:
        ctx = PRUMADA_ES if t.get("vertical") and t["L"] >= 2.0 else RAMAL_ES
        tubos[(ctx, int(t["dn"]))] += t["L"]
    for t in es["coletores"]:
        ctx = PRUMADA_ES if t.get("eixo") == "v" and t["L"] >= 2.0 else SUBCOL
        tubos[(ctx, int(t["dn"]))] += t["L"]
    for (ctx, dn), q in sorted(tubos.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        c = _composicao(sin, ("TUBO PVC, SERIE NORMAL, ESGOTO PREDIAL, DN %d MM" % dn,), ORDEM_ES[ctx])
        if not c:
            nao_achou.append(f"tubo DN{dn} ({NOME_CTX_ES[ctx]})")
            continue
        linhas.append({"grupo": "Tubos", "item": f"Tubo PVC esgoto série normal DN{dn} · {NOME_CTX_ES[ctx]}", "sinapi": c[0], "descr": c[1],
                       "un": c[2].lower(), "qtd": round(q, 2), "preco": c[k + 1], "custo": round(q * c[k + 1], 2)})
    tab = (es.get("tabela_projetista") or {}).get("conexoes") or {}
    for origem, cods, ctx in (("apartamentos", es.get("conexoes") or {}, RAMAL_ES),):
        for cod, n in sorted(cods.items()):
            if not n:
                continue
            descr = (tab.get(cod) or [{}])[0].get("descricao")
            termos = _termos_conexao_esgoto(descr) if descr else None
            c = _composicao(sin, termos, ORDEM_ES[ctx]) if termos else None
            maior = ""
            if not c and termos and " X " in termos[0]:          # sem a redução no SINAPI: a peça igual de bitola maior
                import re as _re
                t0 = _re.sub(r"DN (\d+) X \d+ MM", r"DN \1 X \1 MM", termos[0])
                c = _composicao(sin, (t0,), ORDEM_ES[ctx])
                maior = " (sem a redução no SINAPI: peça igual de bitola maior)" if c else ""
            if not c:
                nao_achou.append(f"código {cod} ({descr or 'sem descrição'})")
                continue
            nota = (" (preço do joelho 90° DN100: não há composição do adaptador)" if descr.upper().startswith("ADAPTADOR") else "") + maior
            linhas.append({"grupo": "Conexões", "item": f"{cod} · {descr.split(',')[0]} · {NOME_CTX_ES[ctx]}{nota}", "sinapi": c[0],
                           "descr": c[1], "un": c[2].lower(), "qtd": n, "preco": c[k + 1], "custo": round(n * c[k + 1], 2), "codigo": cod})
    for it in (es.get("tabela_projetista") or {}).get("caixas", []):
        alvo = next((x for x in CAIXAS if x[0].upper() in it["descricao"].upper()), None)
        if not alvo:
            nao_achou.append(it["descricao"][:60])
            continue
        _, tipo, cod, obs = alvo
        r = (sin["composicoes"] if tipo == "C" else sin["insumos"]).get(str(cod))
        if not r:
            nao_achou.append(it["descricao"][:60])
            continue
        linhas.append({"grupo": "Caixas e ralos", "item": f"{it['descricao'].split(',')[0][:60]} · {obs} · quantidade do projetista",
                       "sinapi": cod, "descr": r[0], "un": (r[1] or "").lower(), "qtd": it["qtd"], "preco": r[k],
                       "custo": round(it["qtd"] * r[k], 2)})
    total = round(sum(L["custo"] for L in linhas), 2)
    por_grupo = defaultdict(float)
    for L in linhas:
        por_grupo[L["grupo"]] += L["custo"]
    return {"mes": sin.get("mes"), "uf": sin.get("uf"), "desonerado": bool(prem.get("desonerado")), "linhas": linhas, "total": total,
            "grupos": {g: round(v, 2) for g, v in por_grupo.items()}, "nao_achou": nao_achou,
            "premissas": ["Tubo de queda e ventilação (vertical ≥ 2 m) = prumada; ramais dos apartamentos = ramal de descarga/esgoto; "
                          "coletores do térreo/subsolo = subcoletor aéreo.",
                          "Conexões: as dos isométricos dos apartamentos, que já desenham o trecho até os coletores (as vistas de "
                          "coletores repetem as mesmas peças); preço de ramal.",
                          "Junção 100×50 e tê 75×50: sem composição no SINAPI; usada a peça igual de bitola maior (100×100, 75×75).",
                          "Adaptador de saída de vaso (01): sem composição no SINAPI; preço do joelho 90° DN100 do ramal.",
                          "Caixas sifonadas, de gordura, de inspeção, prolongamentos e ralos: quantidade da tabela do projetista "
                          "(o leitor ainda não conta esses símbolos no desenho). Caixa de inspeção e prolongamentos: só material."]}
