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


def _composicao(sin, termos, ctx_ordem):
    """Composição SINAPI com os termos, preferindo o tipo de trecho na ordem dada."""
    cands = buscar(sin, *termos, onde="composicoes")
    if not cands:
        return None
    for ctx in ctx_ordem:
        if ctx is None:
            sem = [c for c in cands if not any(k in c[1].upper().replace("Ç", "C").replace("Ã", "A") for k in ("RAMAL", "PRUMADA", "RESERVA", "DRENO"))]
            if sem:
                return sem[0]
            continue
        cs = [c for c in cands if ctx in c[1].upper().replace("Ç", "C").replace("Ã", "A").replace("Í", "I")]
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
        na_col = c and math.dist(cn["p"][:2], c) * m_tipo < 0.03 and cn["cod"] in NA_COLUNA
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
