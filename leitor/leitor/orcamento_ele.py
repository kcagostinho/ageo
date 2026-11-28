"""Preço SINAPI das instalações elétricas.

Quantidades: a lista de materiais do projetista, folha por folha (é o levantamento dele, e a conferência mostra que
bate com o modelo: pontos, caixas e peças item a item; eletroduto 3/4" dos andares em ±0,3%). Cabos, disjuntores,
DPS e DR só existem na lista. O modelo entra onde o SINAPI separa por lugar ou altura:
  - eletroduto 3/4" e 1": metros da lista repartidos entre laje (trecho horizontal desenhado) e parede (descidas
    até as caixas) na proporção medida no modelo de cada andar;
  - caixa 4×2": baixa (0,30 m), média (1,10 m) ou alta (2,20 m) pela altura de cada ponto lido na planta;
  - tomada 20 A: alta (ar-condicionado, 2,20 m) ou baixa (portões, 0,30 m).
Sem composição no SINAPI: composição parecida com o material trocado (DERIVADAS) ou, em último caso, só o preço
do material (marcado). Substituições e premissas ficam em PREMISSAS e na nota de cada linha.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

PREMISSAS = [
    "Quantidades da lista de materiais do projetista (todas as folhas); o modelo só reparte eletroduto entre laje e "
    "parede, caixas 4×2\" por altura e tomadas de 20 A entre alta e baixa.",
    "Eletroduto leve na laje: composição de eletroduto corrugado reforçado (o SINAPI só tem a laje com o reforçado); "
    "na parede: corrugado comum.",
    "Eletroduto pesado 1.1/2\", 2\" e 3\" (alimentadores e prumadas): o SINAPI não tem corrugado de PVC nessas bitolas "
    "para circuitos; usado o corrugado de PEAD da mesma bitola (rede enterrada).",
    "Luminárias: o projeto pede luminária para lâmpada incandescente; essas lâmpadas saíram do mercado brasileiro "
    "(Portaria Interministerial 1.007/2010) e o SINAPI só tem LED: plafon circular LED 12/13 W no teto e arandela "
    "meia-lua LED 6 W na parede (plafonier, soquete e lâmpada da lista ficam dentro dessas composições).",
    "Disjuntores de 13 A: preço do de 16 A (o SINAPI não tem 13 A). 63 A e 70 A: composição de 50 A com o disjuntor "
    "de 63 A no lugar (70 A não existe no SINAPI).",
    "DR bipolar 80 A: composição do DR bipolar 63 A (maior do SINAPI). DPS 175 V 40 kA: preço do DPS 20 kA (a "
    "composição de 40 kA está sem preço em SP).",
    "Quadros de distribuição de PVC para 12 disjuntores: composição do quadro de PVC de 6 com o quadro trocado pelo de "
    "12/16 DIN com barramento terra/neutro (embutir) ou sem barramento (sobrepor).",
    "Caixa de passagem 100×100×80 mm de aço: caixa 4×4\" metálica alta (2,00 m) instalada em parede.",
    "Cabo de 25 mm²: composição do cabo de 16 mm² com o cabo trocado pelo de 25 mm² (450/750 V).",
    "Caixas de medição da CPFL, parafuso, isolador, poste e acessórios de uso geral: só material (SINAPI sem composição).",
]

# (regex no grupo/sub/item da lista) -> como orçar
ELETRODUTO = {
    ("leve", "3/4"): {"laje": 91845, "parede": 91854},
    ("leve", "1"): {"laje": 91847, "parede": 91856},
    ("pesado", "1.1/2"): 97667, ("pesado", "2"): 97668, ("pesado", "3"): 97669,
}
CABO = {"1.5": 91924, "2.5": 91926, "4": 91928, "16": 91934}
DERIVADAS = {
    # chave: (composição base, termo do insumo que sai, insumo que entra, descrição do item)
    "cabo25": (91934, "CABO DE COBRE", 39232, "Cabo de cobre flexível 25 mm² 450/750 V"),
    "bip63": (93666, "DISJUNTOR", 34628, "Disjuntor bipolar DIN 63 A"),
    "mono63": (93659, "DISJUNTOR", 34688, "Disjuntor monopolar DIN 63 A"),
    "qd_emb": (101876, "QUADRO", 39805, "Quadro de distribuição PVC de embutir, 12 disjuntores, barramento terra/neutro"),
    "qd_sob": (101876, "QUADRO", 39801, "Quadro de distribuição PVC de sobrepor, 12 disjuntores"),
}


def _comp(sin, codigo, k):
    c = sin["composicoes"].get(str(codigo))
    return (codigo, c[0], c[1], c[k]) if c and c[k] else None


def _ins(sin, codigo, k):
    c = sin["insumos"].get(str(codigo))
    return (codigo, c[0], c[1], c[k]) if c and c[k] else None


def _derivada(sin, chave, k):
    base, termo, entra, nome = DERIVADAS[chave]
    cb, ie = sin["composicoes"].get(str(base)), sin["insumos"].get(str(entra))
    if not cb or not ie:
        return None
    sai = next((x for x in sin["analitico"].get(str(base), []) if x[0] == "I"
                and termo in (sin["insumos"].get(str(x[1])) or [""])[0].upper()), None)
    if not sai:
        return None
    ps = sin["insumos"][str(sai[1])][k]
    preco = round(cb[k] - ps * sai[2] + ie[k] * sai[2], 2)
    return (f"{base}*", f"{nome} — composição {base} ({cb[0][:70]}…) com o insumo {sai[1]} trocado pelo {entra} "
            f"({ie[0][:70]})", cb[1], preco)


def _bitola(item):
    m = re.match(r'^\s*([\d./]+)"', item)
    return m.group(1) if m else None


def calcular(ele: dict, sin: dict, prem: dict, quant_modelo: dict) -> dict:
    """quant_modelo: {(pav, diam): {"laje": m, "parede": m}} medido no modelo (convenção do projetista)."""
    k = 3 if prem.get("desonerado") else 2
    linhas, nao_achou = [], []

    def add(grupo, item, c, qtd, nota=""):
        if qtd <= 0:
            return
        if not c:
            nao_achou.append(item)
            return
        codigo, descr, un, preco = c[0], c[1], c[2], c[3]
        linhas.append({"grupo": grupo, "item": item, "sinapi": codigo, "descr": descr, "un": str(un).lower(), "qtd": round(qtd, 2),
                       "preco": round(preco, 2), "custo": round(qtd * preco, 2), "nota": nota})

    comp = lambda c: _comp(sin, c, k)
    ins = lambda c: _ins(sin, c, k)
    # ---- somas da lista (todas as folhas) e contagens do modelo
    tot = Counter()
    eletr = defaultdict(lambda: Counter())          # (tipo, bitola) -> {pav: m}
    for pav, itens in ele["listas"].items():
        for x in itens:
            g, s, it = x["grupo"] or "", x["sub"] or "", x["item"]
            tot[(g, s, it)] += x["qtd"]
            if g.startswith("Eletroduto PVC flex"):
                eletr[("leve" if "leve" in s else "pesado", _bitola(it))][pav] += x["qtd"]
    q = lambda rx_g, rx_s=".*", rx_i=".*": sum(v for (g, s, it), v in tot.items()
                                              if re.search(rx_g, g) and re.search(rx_s, s) and re.search(rx_i, it))
    # ---- eletrodutos
    for (tipo, b), por in sorted(eletr.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")):
        alvo = ELETRODUTO.get((tipo, b))
        if alvo is None:
            nao_achou.append(f"eletroduto {tipo} {b}\"")
            continue
        if isinstance(alvo, dict):
            laje = parede = 0.0
            for pav, m in por.items():
                mm = quant_modelo.get((pav, b)) or {}
                s = (mm.get("laje", 0) + mm.get("parede", 0)) or 1.0
                f = mm.get("laje", 0) / s if mm else 0.5
                laje += m * f
                parede += m * (1 - f)
            add("Eletrodutos", f"Eletroduto corrugado {b}\" na laje", comp(alvo["laje"]), laje,
                "metros da lista × parte horizontal medida no modelo")
            add("Eletrodutos", f"Eletroduto corrugado {b}\" na parede (descidas)", comp(alvo["parede"]), parede,
                "metros da lista × parte vertical medida no modelo")
        else:
            add("Eletrodutos", f"Eletroduto pesado {b}\" (alimentadores e prumadas)", comp(alvo), sum(por.values()),
                "PEAD corrugado da mesma bitola (premissa)")
    rosca = {x["item"]: 0.0 for pav in ele["listas"] for x in ele["listas"][pav] if (x["grupo"] or "").startswith("Eletroduto PVC rosca")}
    for pav in ele["listas"]:
        for x in ele["listas"][pav]:
            if (x["grupo"] or "").startswith("Eletroduto PVC rosca"):
                rosca[x["item"]] += x["qtd"]
    for it, m in rosca.items():
        b = _bitola(it)
        add("Eletrodutos", f"Eletroduto PVC rígido roscável {b}\" (entrada de serviço)", comp(91870 if b == "1/2" else 93009), m)
    # ---- cabos (todas as cores de cada seção)
    sec = Counter()
    for (g, s, it), v in tot.items():
        if g.startswith("Cabo"):
            m = re.match(r"^([\d.]+) mm²", it)
            if m:
                sec[m.group(1)] += v
    for s_, m in sorted(sec.items(), key=lambda kv: float(kv[0])):
        c = comp(CABO[s_]) if s_ in CABO else (_derivada(sin, "cabo25", k) if s_ == "25" else None)
        add("Cabos", f"Cabo de cobre flexível {s_.replace('.', ',')} mm² 450/750 V (todas as cores)", c, m)
    # ---- caixas (altura pelo modelo)
    alt = Counter()
    for r in ele["plantas"]:
        for p in r["pontos"]:
            t = p["tipo"]
            if t in ("tomada_baixa",):
                alt["baixa"] += 1
            elif t in ("tomada_media", "interruptor"):
                alt["media"] += 1
            elif t in ("tomada_alta", "sensor"):
                alt["alta"] += 1
    n42 = q("Acessórios p/ eletrodutos", "^Caixa PVC$", r'^4x2"')
    soma = sum(alt.values()) or 1
    for h, cod, nome in (("baixa", 91941, "0,30 m"), ("media", 91940, "1,10–1,30 m"), ("alta", 91939, "2,00–2,20 m")):
        add("Caixas", f"Caixa 4×2\" PVC {h if h != 'media' else 'média'} ({nome})", comp(cod), n42 * alt[h] / soma,
            "quantidade da lista; altura de cada ponto pela planta")
    add("Caixas", "Caixa 4×4\" PVC baixa (ponto de força do elevador)", comp(91944), q("Acessórios p/ eletrodutos", "^Caixa PVC$", r'^4x4"'))
    add("Caixas", "Caixa octogonal 3×3\" PVC na laje", comp(91937), q("Acessórios p/ eletrodutos", "octogonal", r'^3x3"'))
    add("Caixas", "Caixa de passagem 100×100×80 mm (aço)", comp(92870), q("^Caixa de passagem"), "caixa 4×4\" metálica alta a 2,00 m (premissa)")
    # ---- tomadas, interruptores, sensores
    t20 = q("^Dispositivo El", "S/ placa", "20A")
    por_t20 = Counter()
    for r in ele["plantas"]:
        for p in r["pontos"]:
            if p["tipo"] == "tomada_alta" and p["sub"] != "chuveiro":
                por_t20["alta"] += 1
            elif p["tipo"] == "tomada_baixa" and (p["sub"] or "").startswith("20 A"):
                por_t20["baixa"] += 1
    s20 = sum(por_t20.values()) or 1
    TD = "Tomadas, interruptores e sensores"
    add(TD, "Tomada universal 2P+T 10 A baixa (0,30 m), com placa", comp(92000), q("^Dispositivo El", "S/ placa", "universal"))
    add(TD, "Tomada 2P+T 10 A média (1,10 m), com placa", comp(91996), q("^Dispositivo El", "S/ placa", "hexagonal.*10A"))
    add(TD, "Tomada 2P+T 20 A alta (ar-condicionado, 2,20 m), com placa", comp(91993), t20 * por_t20["alta"] / s20)
    add(TD, "Tomada 2P+T 20 A baixa (motor do portão, 0,30 m), com placa", comp(92001), t20 * por_t20["baixa"] / s20)
    add(TD, "Placa cega 4×2\" (ponto do chuveiro)", ins(38091), q("^Dispositivo El", ".*", "^Placa cega"), "só material")
    add(TD, "Interruptor simples 1 tecla, com placa", comp(91953), q("^Dispositivo El", ".*", "simples - 1 tecla"))
    add(TD, "Interruptor simples 2 teclas, com placa", comp(91959), q("^Dispositivo El", ".*", "simples - 2 teclas"))
    add(TD, "Interruptor paralelo 1 tecla, com placa", comp(91955), q("^Dispositivo El", ".*", "paralel[ao] - 1 tecla"))
    add(TD, "Interruptor paralelo 2 teclas, com placa", comp(91961), q("^Dispositivo El", ".*", "paralel[ao] - 2 teclas"))
    add(TD, "Interruptor 2 simples + 1 paralelo (3 teclas), com placa", comp(91965), q("^Dispositivo El", ".*", "2 simples & paralela"))
    add(TD, "Sensor de presença de parede (2,20 m)", comp(97596), q("^Dispositivo de Comando"))
    # ---- iluminação
    IL = "Iluminação"
    add(IL, "Luminária de teto (plafon LED no lugar da incandescente 100/150 W)", comp(103782), q("^Lumin", "^Luminária sobrepor"),
        "substitui luminária + plafonier + soquete + lâmpada incandescente da lista")
    add(IL, "Arandela (meia-lua LED no lugar da incandescente 60 W)", comp(97605), q("^Lumin", "^Arandela"),
        "substitui arandela + plafonier + soquete + lâmpada da lista")
    # ---- quadros e proteção
    QP = "Quadros e proteção"
    add(QP, "Quadro de distribuição PVC de embutir, 12 disjuntores", _derivada(sin, "qd_emb", k), q("^Quadro distrib.*embutir"))
    add(QP, "Quadro de distribuição PVC de sobrepor, 12 disjuntores (térreo)", _derivada(sin, "qd_sob", k), q("^Quadro distrib.*sobrepor"))
    for (g, s, it), v in sorted(tot.items(), key=lambda kv: kv[0]):
        if not g.startswith("Dispositivo de Prote"):
            continue
        a = re.match(r"^(\d+) A", it)
        if "Unipolar" in s and a:
            A = int(a.group(1))
            if A >= 63:
                add(QP, f"Disjuntor monopolar DIN {A} A", _derivada(sin, "mono63", k), v, "63 A no lugar de 70 A" if A == 70 else "")
            else:
                cod = {10: 93653, 13: 93654, 16: 93654, 20: 93655, 25: 93656, 32: 93657, 40: 93658, 50: 93659}.get(A)
                add(QP, f"Disjuntor monopolar DIN {A} A", comp(cod) if cod else None, v, "preço do 16 A" if A == 13 else "")
        elif "bipolar termomagn" in s and a:
            A = int(a.group(1))
            if A >= 63:
                add(QP, f"Disjuntor bipolar DIN {A} A", _derivada(sin, "bip63", k), v, "63 A no lugar de 70 A" if A == 70 else "")
            else:
                cod = {10: 93660, 16: 93661, 20: 93662, 25: 93663, 32: 93664, 40: 93665, 50: 93666}.get(A)
                add(QP, f"Disjuntor bipolar DIN {A} A", comp(cod) if cod else None, v)
        elif "surto" in s:
            add(QP, f"DPS {it}", comp(106027), v, "preço do DPS 20 kA (40 kA sem preço em SP)")
        elif "DR" in s:
            add(QP, f"Interruptor DR bipolar {it} 30 mA", comp(106030), v, "composição do DR bipolar 63 A")
    # ---- entrada de serviço e medição
    EN = "Entrada de serviço e medição"
    med = {"tipo L": ins(1068), "tipo IV": ins(1062), "tipo V": ins(1062), "tipo T": None}
    for (g, s, it), v in sorted(tot.items(), key=lambda kv: kv[0]):
        if g.startswith("Quadro de medição"):
            chave = next((c for c in med if c in it), None)
            add(EN, f"{it} (CPFL)", med.get(chave) if chave else None, v,
                "só material; caixa de medição de 1 medidor de aço (padrão da concessionária)" if chave in ("tipo IV", "tipo V") else "só material")
        elif g.startswith("Material p/ entrada"):
            if s.startswith("Armação"):
                add(EN, "Armação secundária 1 estribo com isolador", comp(101538), v)
            elif s.startswith("Isolador"):
                continue                                      # já está na armação secundária
            elif s.startswith("Haste"):
                add(EN, "Haste de aterramento (5/8\" × 3 m no SINAPI; projeto: 15 mm × 2,4 m)", comp(96985), v)
            elif s.startswith("Caixa inspe"):
                add(EN, "Caixa de inspeção do aterramento", comp(98111), v, "circular de polietileno Ø 0,30 m (SINAPI)")
            elif s.startswith("Poste"):
                add(EN, "Poste de concreto (SINAPI: 9 m; projeto: 7 m)", ins(5059), v, "só material")
            elif s.startswith("Parafuso"):
                add(EN, "Parafuso M16 × 150 mm cabeça quadrada", ins(441), v, "só material")
    # ---- acessórios
    AC = "Acessórios"
    for (g, s, it), v in sorted(tot.items(), key=lambda kv: kv[0]):
        b = _bitola(it)
        if g.startswith("Acessórios p/ eletrodutos"):
            if s.startswith("Curva 180"):
                add(AC, f"Curva 180° PVC roscável {b}\"", ins(39277 if b == "2" else 40409), v, "só material")
            elif s.startswith("Curva 90"):
                add(AC, f"Curva 90° PVC roscável {b}\"", comp(93020) if b == "2" else ins(1870), v, "" if b == "2" else "só material")
            elif s.startswith("Luva"):
                add(AC, f"Luva PVC roscável {b}\"", comp(93014) if b == "2" else ins(1901), v, "" if b == "2" else "só material")
            elif s.startswith(("Arruela", "Bucha")):
                nao_achou.append(f"{s} {it} ({v:g} pç; sem preço no SINAPI)")
        elif g.startswith("Acessórios uso geral"):
            if s.startswith("Fita isolante"):
                add(AC, "Fita isolante autofusão (rolo de 20 m)", (404, "FITA ISOLANTE DE BORRACHA AUTOFUSAO (20 M)", "UN",
                                                                    (sin["insumos"]["404"][k] or 0) * 20), v, "só material")
            elif s.startswith("Bucha de nylon"):
                add(AC, "Bucha de nylon S6", ins(4375), v, "só material")
            elif s.startswith("Arame"):
                add(AC, "Arame galvanizado 14 BWG", (43130, "ARAME GALVANIZADO 14 BWG (0,026 KG/M)", "M", (sin["insumos"]["43130"][k] or 0) * 0.026), v,
                    "só material")
            else:
                nao_achou.append(f"{s} {it} ({v:g} pç; sem preço no SINAPI)")
    total = round(sum(L["custo"] for L in linhas), 2)
    grupos = defaultdict(float)
    for L in linhas:
        grupos[L["grupo"]] += L["custo"]
    return {"mes": sin.get("mes"), "uf": sin.get("uf"), "desonerado": bool(prem.get("desonerado")), "linhas": linhas, "total": total,
            "grupos": {g: round(v, 2) for g, v in grupos.items()}, "nao_achou": nao_achou, "premissas": PREMISSAS}


def quant_projetista(ele: dict) -> dict:
    """Eletroduto por andar e bitola medido como o projetista, separado em laje (desenhado) e parede (descidas)."""
    pd = ele["pe_direito"]
    out = defaultdict(lambda: {"laje": 0.0, "parede": 0.0})
    for r in ele["plantas"]:
        pav = r["pavimento"]
        for t in r["tubos"]:
            if t["tipo"] in ("ramal", "curto", "seta"):
                out[(pav, t["diam"])]["laje" if t["tipo"] == "ramal" else "parede"] += t["L"]
                for i in (t["a"], t["b"]):
                    if i is None or t["tipo"] != "ramal":
                        continue
                    p = r["pontos"][i]
                    if p["tipo"] in ("luminaria", "cx"):
                        continue
                    h = p["h"] if p["h"] is not None else 0.30
                    out[(pav, t["diam"])]["parede"] += max(pd.get(pav, 2.6) - h - 0.05, 0)
    return dict(out)
