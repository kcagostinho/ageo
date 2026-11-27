"""Abas da B4: 'Preços (B4)', 'Orçamento (B4)' e 'Custo por pavimento (B4)', com fórmulas.

- Preços: premissas (desoneração, BDI, fator da canaleta J, fbk por pavimento) e a lista de
  referências SINAPI. A coluna Cotação (amarela) substitui o SINAPI quando preenchida.
- Orçamento: quantidade (ligada à aba Insumos (B3)) × preço usado.
- Custo por pavimento: custo de cada linha × fração do rateio (a fração vem do modelo).
"""
from __future__ import annotations

from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

AMARELO = PatternFill("solid", fgColor="FFF8E1")
CINZA = PatternFill("solid", fgColor="EEF3F1")
RS = '#,##0.00'
B3 = "'Insumos (B3)'"


def _pav_curto(p):
    return p.replace("Pavimento ", "").replace("ºPavimento", "º pav.")


def abas(wb, dados: dict, cabecalho):
    orc = dados["orcamento"]
    ins = dados["insumos"]
    prem = orc["premissas"]

    # ------------------------------------------------------------ Preços (B4)
    ws = wb.create_sheet("Preços (B4)")
    for col, w in zip("ABCDEFGHIJK", [16, 62, 8, 34, 12, 12, 12, 10, 13, 13, 60]):
        ws.column_dimensions[col].width = w
    ws["A1"] = f"Preços — SINAPI {orc['mes']} · {orc['uf']} (Caixa)"
    ws["A1"].font = Font(bold=True, size=13)
    itens = [("Desonerado? (Sim/Não)", "Sim" if prem["desonerado"] else "Não", None),
             ("BDI sobre o custo direto", prem["bdi"], "0%"),
             ("Fator da canaleta J sobre a canaleta U", prem["fator_canaleta_j"], "0.00")]
    for i, (t, v, fmt) in enumerate(itens, 2):
        ws.cell(row=i, column=1, value=t)
        c = ws.cell(row=i, column=2, value=v)
        c.fill = AMARELO
        if fmt:
            c.number_format = fmt
    dv = DataValidation(type="list", formula1='"Sim,Não"', allow_blank=False)
    ws.add_data_validation(dv)
    dv.add("B2")
    # fbk por pavimento
    pavs = list(orc["fbk"].keys())
    r0 = 7
    ws.cell(row=r0, column=1, value="fbk por pavimento (até o projeto estrutural)").font = Font(bold=True)
    for j, t in enumerate(("Pavimento", "fbk (MPa)", "Peças estruturais", "Bloco 14×19×39 (R$)", "Fator"), 1):
        ws.cell(row=r0 + 1, column=j, value=t).font = Font(bold=True)
    t0 = r0 + 2 + len(pavs) + 2                      # início da tabela fbk → preço
    t1 = t0 + 1 + len(orc["fbk_tabela"]) - 1
    for i, p in enumerate(pavs):
        r = r0 + 2 + i
        ws.cell(row=r, column=1, value=p)
        c = ws.cell(row=r, column=2, value=orc["fbk"][p])
        c.fill = AMARELO
        ws.cell(row=r, column=3, value=orc["n_est"][p]).number_format = "#,##0"
        ws.cell(row=r, column=4, value=f"=VLOOKUP(B{r},$A${t0 + 1}:$E${t1},5,FALSE)").number_format = RS
        ws.cell(row=r, column=5, value=f"=D{r}/VLOOKUP(4.5,$A${t0 + 1}:$E${t1},5,FALSE)").number_format = "0.000"
    rf = r0 + 2 + len(pavs) - 1
    ws["A5"] = "Fator médio de fbk (aplicado às peças estruturais)"
    ws["B5"] = f"=SUMPRODUCT(C{r0 + 2}:C{rf},E{r0 + 2}:E{rf})/SUM(C{r0 + 2}:C{rf})"
    ws["B5"].number_format = "0.000"
    ws.cell(row=t0 - 1, column=1, value="Bloco 14×19×39 por fbk (SINAPI)").font = Font(bold=True)
    for j, t in enumerate(("fbk (MPa)", "Código", "Sem desoneração", "Com desoneração", "Usado"), 1):
        ws.cell(row=t0, column=j, value=t).font = Font(bold=True)
    for i, (f, cod, sd, cd) in enumerate(orc["fbk_tabela"], t0 + 1):
        ws.cell(row=i, column=1, value=f)
        ws.cell(row=i, column=2, value=cod)
        ws.cell(row=i, column=3, value=sd).number_format = RS
        ws.cell(row=i, column=4, value=cd).number_format = RS
        ws.cell(row=i, column=5, value=f'=IF($B$2="Sim",D{i},C{i})').number_format = RS
    # referências
    h = t1 + 3
    cols = ["ID", "Descrição", "Unid.", "Fonte", "Código SINAPI", "Sem desoneração", "Com desoneração", "Fator",
            "Cotação (R$)", "Preço usado", "Observação"]
    for j, t in enumerate(cols, 1):
        c = ws.cell(row=h, column=j, value=t)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="0F6E56")
    linha_ref = {}
    for i, (rid, p) in enumerate(orc["precos"].items(), h + 1):
        linha_ref[rid] = i
    for rid, p in orc["precos"].items():
        i = linha_ref[rid]
        ws.cell(row=i, column=1, value=rid)
        ws.cell(row=i, column=2, value=p["descr"])
        ws.cell(row=i, column=3, value=p["un"])
        ws.cell(row=i, column=4, value=p["fonte"])
        if p["tipo"] == "D":
            b = linha_ref[p["cod"]]
            fat = "$B$4" if rid in ("J14", "MJ14") else p["fator"]
            ws.cell(row=i, column=6, value=f"=F{b}*H{i}").number_format = RS
            ws.cell(row=i, column=7, value=f"=G{b}*H{i}").number_format = RS
            ws.cell(row=i, column=8, value=f"={fat}" if isinstance(fat, str) else fat).number_format = "0.000"
        else:
            ws.cell(row=i, column=5, value=p["cod"])
            ws.cell(row=i, column=6, value=round(p["sd"], 4)).number_format = RS
            ws.cell(row=i, column=7, value=round(p["cd"], 4)).number_format = RS
        ws.cell(row=i, column=9).fill = AMARELO
        ws.cell(row=i, column=9).number_format = RS
        mult = "*$B$5" if p["fbk"] else ""
        ws.cell(row=i, column=10, value=f'=IF(ISNUMBER(I{i}),I{i},IF($B$2="Sim",G{i},F{i}){mult})').number_format = RS
        ws.cell(row=i, column=10).font = Font(bold=True)
        ws.cell(row=i, column=11, value=("Peça estrutural: × fator médio de fbk. " if p["fbk"] else "") + (p["obs"] or ""))
    fim_ref = h + len(orc["precos"])
    nota = fim_ref + 2
    for k, t in enumerate([
        "Amarelo = editável. Cotação preenchida substitui o SINAPI daquela linha (sem o fator de fbk).",
        "Mão de obra (MO_E, MO_V): pedreiro, servente e equipamento da composição SINAPI de alvenaria; blocos e argamassa vêm da paginação.",
        "Composições completas (graute, armação, revestimentos) já incluem material, mão de obra e perdas do SINAPI.",
        f"Fonte: SINAPI {orc['mes']}, {orc['uf']}, relatório de referência da Caixa (insumos, composições e analítico).",
    ], nota):
        ws.cell(row=k, column=1, value=t).font = Font(italic=True)
    ws.freeze_panes = None
    ref_rng = f"'Preços (B4)'!$A${h + 1}:$J${fim_ref}"

    # ------------------------------------------------------------ Orçamento (B4)
    oc = wb.create_sheet("Orçamento (B4)")
    cabecalho(oc, ["Grupo", "Serviço / insumo", "Unid.", "Quantidade", "Origem da quantidade", "Preço unit. (R$)", "Custo (R$)",
                   "% do total", "Ref. preço", "Observação"], [22, 46, 7, 12, 46, 13, 15, 9, 10, 60])
    b3row = {nome: 2 + i for nome, i in orc["b3_idx"].items()}
    n = len(orc["linhas"])
    tot_cel = f"$G${n + 3}"
    ant = None
    for r, L in enumerate(orc["linhas"], 2):
        qf = L["qf"]
        if qf[0] == "B3":
            rr = b3row[qf[1]]
            if qf[2] == "com":
                f, orig = f"={B3}!J{rr}", f"B3: {qf[1]} (com perda)"
            else:
                f, orig = f"={B3}!E{rr}*{B3}!G{rr}", f"B3: {qf[1]} (base × coef., sem perda)"
        elif qf[0] == "soma":
            f = "=" + "+".join(f"{B3}!E{b3row[nm]}*{B3}!G{b3row[nm]}" for nm, _ in qf[1] if nm in b3row)
            orig = "B3: " + " + ".join(nm for nm, _ in qf[1])
        else:
            chave = qf[1]
            if chave == "area_estrutural":
                f, orig = f"={B3}!E{b3row['Argamassa — alvenaria estrutural']}", "B3: área líquida de parede estrutural"
            elif chave == "area_vedacao":
                f, orig = f"={B3}!E{b3row['Argamassa — vedação']}", "B3: área líquida de parede de vedação"
            else:
                f, orig = round(L["qtd"], 3), "Tetos da aba Quantitativos, por faixa de área do ambiente"
        vals = [L["grupo"] if L["grupo"] != ant else "", L["item"], L["un"], f, orig,
                f"=VLOOKUP(I{r},{ref_rng},10,FALSE)", f"=D{r}*F{r}", f"=IF({tot_cel}=0,0,G{r}/{tot_cel})", L["ref"], L["obs"]]
        for col, v in enumerate(vals, 1):
            c = oc.cell(row=r, column=col, value=v)
            if col == 4:
                c.number_format = "#,##0" if L["un"] == "un" else "#,##0.00"
            elif col in (6, 7):
                c.number_format = RS
            elif col == 8:
                c.number_format = "0.0%"
        if L["grupo"] != ant:
            oc.cell(row=r, column=1).font = Font(bold=True)
        ant = L["grupo"]
    # resumo
    t = n + 3
    oc.cell(row=t, column=2, value="Custo direto").font = Font(bold=True)
    oc.cell(row=t, column=7, value=f"=SUM(G2:G{n + 1})").number_format = RS
    oc.cell(row=t, column=7).font = Font(bold=True)
    oc.cell(row=t + 1, column=2, value="BDI")
    oc.cell(row=t + 1, column=6, value="='Preços (B4)'!B3").number_format = "0%"
    oc.cell(row=t + 1, column=7, value=f"=G{t}*F{t + 1}").number_format = RS
    oc.cell(row=t + 2, column=2, value="Total com BDI").font = Font(bold=True)
    oc.cell(row=t + 2, column=7, value=f"=G{t}+G{t + 1}").number_format = RS
    oc.cell(row=t + 2, column=7).font = Font(bold=True)
    r = t + 4
    oc.cell(row=r, column=1, value="Por grupo").font = Font(bold=True)
    grupos = list(dict.fromkeys(L["grupo"] for L in orc["linhas"]))
    # SUMIF por grupo precisa do grupo em todas as linhas: coluna auxiliar oculta (K)
    for rr, L in enumerate(orc["linhas"], 2):
        oc.cell(row=rr, column=11, value=L["grupo"])
    oc.column_dimensions["K"].hidden = True
    for k, g in enumerate(grupos, r + 1):
        oc.cell(row=k, column=2, value=g)
        oc.cell(row=k, column=7, value=f'=SUMIF($K$2:$K${n + 1},B{k},$G$2:$G${n + 1})').number_format = RS
        oc.cell(row=k, column=8, value=f"=IF({tot_cel}=0,0,G{k}/{tot_cel})").number_format = "0.0%"
    r = r + len(grupos) + 2
    cub = orc.get("cub")
    area_orc = orc["area_orc"]
    linhas_ref = [
        ("Área construída considerada (pavimentos acima do subsolo) — m²", round(area_orc, 2), "#,##0.00",
         "Ambientes cobertos + projeção das paredes"),
        ("Custo direto por m² (R$/m²)", f"=IF(G{r}=0,0,G{t}/G{r})", RS, ""),
    ]
    if cub:
        pc = cub["padroes"].get(cub["padrao"], {})
        sd, cd = pc.get("sd"), pc.get("cd") or pc.get("sd")
        linhas_ref += [
            (f"CUB {cub['padrao']} {cub['mes']} — SindusCon-SP (R$/m²)", f"=IF('Preços (B4)'!$B$2=\"Sim\",{cd},{sd})", RS,
             "Residencial multifamiliar padrão normal; sem/com desoneração conforme a aba Preços"),
            ("Área construída total, com subsolo (m²)", round(orc["area_total"], 2), "#,##0.00", ""),
            ("Custo de referência do prédio pelo CUB (R$)", f"=G{r + 2}*G{r + 3}", RS,
             "Ordem de grandeza: o CUB não inclui fundações, elevadores, projetos, impostos nem terreno"),
            ("Alvenaria + revestimentos (B4) em % do CUB do prédio", f"=IF(G{r + 4}=0,0,G{t}/G{r + 4})", "0.0%", ""),
            ("B4 por m² em % do CUB/m²", f"=IF(G{r + 2}=0,0,G{r + 1}/G{r + 2})", "0.0%", ""),
        ]
    for k, (txt, v, fmt, obs) in enumerate(linhas_ref, r):
        oc.cell(row=k, column=2, value=txt)
        c = oc.cell(row=k, column=7, value=v)
        c.number_format = fmt
        oc.cell(row=k, column=10, value=obs)
    r = r + len(linhas_ref) + 1
    notas = [
        "Quantidade: material contado (blocos, canaletas, argamassa, tela) usa a quantidade da B3 com perda; serviços com composição "
        "SINAPI completa usam a base medida sem perda (o coeficiente do SINAPI já tem perda).",
        "Preço unitário vem da aba Preços (B4): troque desoneração, BDI, fbk ou preencha a Cotação e tudo recalcula.",
        "Fora deste orçamento: estrutura de concreto (subsolo, térreo, transição), lajes, pisos, impermeabilização, pintura interna "
        "sobre o gesso, esquadrias, instalações, cobertura e caixa d'água.",
    ]
    for k, txt in enumerate(notas, r):
        oc.cell(row=k, column=1, value=txt).font = Font(italic=True)

    # ------------------------------------------------------------ Custo por pavimento (B4)
    pp = wb.create_sheet("Custo por pavimento (B4)")
    ordem = [v["titulo"] for v in dados["vistas"]] + ["Cobertura"]
    usados = [p for p in ordem if any(L["partes"].get(p) for L in orc["linhas"])]
    cabecalho(pp, ["Grupo", "Serviço / insumo"] + [_pav_curto(p) for p in usados] + ["Total"],
              [22, 46] + [13] * len(usados) + [15])
    ant = None
    for r, L in enumerate(orc["linhas"], 2):
        pp.cell(row=r, column=1, value=L["grupo"] if L["grupo"] != ant else "")
        if L["grupo"] != ant:
            pp.cell(row=r, column=1).font = Font(bold=True)
        ant = L["grupo"]
        pp.cell(row=r, column=2, value=L["item"])
        for j, p in enumerate(usados, 3):
            fr = L["partes"].get(p, 0)
            c = pp.cell(row=r, column=j, value=f"='Orçamento (B4)'!$G${r}*{fr:.9f}" if fr else 0)
            c.number_format = RS
        L_ = get_column_letter(2 + len(usados))
        pp.cell(row=r, column=3 + len(usados), value=f"=SUM(C{r}:{L_}{r})").number_format = RS
    t = n + 2
    pp.cell(row=t, column=2, value="Total").font = Font(bold=True)
    areas = orc["areas"]
    pp.cell(row=t + 1, column=2, value="Área construída (m²)")
    pp.cell(row=t + 2, column=2, value="R$/m² do pavimento")
    for j in range(3, 4 + len(usados)):
        L_ = get_column_letter(j)
        c = pp.cell(row=t, column=j, value=f"=SUM({L_}2:{L_}{n + 1})")
        c.number_format = RS
        c.font = Font(bold=True)
        if j < 3 + len(usados):
            a = areas.get(usados[j - 3])
            pp.cell(row=t + 1, column=j, value=round(a, 2) if a else None).number_format = "#,##0.00"
            pp.cell(row=t + 2, column=j, value=f'=IF(ISNUMBER({L_}{t + 1}),{L_}{t}/{L_}{t + 1},"")').number_format = RS
    pp.cell(row=t + 4, column=1, value=(
        "Cada linha do orçamento é rateada pelos elementos do modelo (peças da paginação por parede, área de parede, faces dos "
        "ambientes, tetos, fachada). A fração de cada pavimento é fixa; o valor acompanha o custo da aba Orçamento (B4).")).font = Font(italic=True)
    pp.freeze_panes = "C2"
    return ["Orçamento (B4)", "Preços (B4)", "Custo por pavimento (B4)"]
