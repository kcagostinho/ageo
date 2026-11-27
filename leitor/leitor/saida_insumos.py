"""Aba 'Insumos (B3)': base medida no modelo × coeficiente × (1 + perda), com fórmulas."""
from __future__ import annotations

from openpyxl.styles import Font, PatternFill


def aba(wb, ins: dict, cabecalho):
    ws = wb.create_sheet("Insumos (B3)")
    cols = ["Grupo", "Insumo", "Unid.", "Base (o que foi medido)", "Base", "Unid. base", "Coeficiente", "Unid. coef.",
            "Perda", "Quantidade", "Observação"]
    cabecalho(ws, cols, [24, 44, 7, 40, 12, 12, 12, 12, 8, 13, 60])
    amarelo = PatternFill("solid", fgColor="FFF8E1")
    grupo_ant = None
    r = 2
    for g, insumo, un, base_d, base, ub, coef, uc, perda, nota in ins["linhas"]:
        vals = [g if g != grupo_ant else "", insumo, un, base_d, round(base, 3), ub, coef, uc, perda,
                (f"=ROUNDUP(E{r}*G{r}*(1+I{r}),0)" if un == "un" else f"=E{r}*G{r}*(1+I{r})"), nota]
        for col, v in enumerate(vals, 1):
            c = ws.cell(row=r, column=col, value=v)
            if col == 5:
                c.number_format = "#,##0.00"
            elif col == 7:
                c.number_format = "0.#####"
                c.fill = amarelo
            elif col == 9:
                c.number_format = "0%"
                c.fill = amarelo
            elif col == 10:
                c.number_format = "#,##0.00" if un not in ("un",) else "#,##0"
                c.font = Font(bold=True)
        if g != grupo_ant:
            ws.cell(row=r, column=1).font = Font(bold=True)
        grupo_ant = g
        r += 1
    ws.freeze_panes = "C2"
    r += 1
    pav = ", ".join(ins["pavimentos"])
    notas = [
        f"Família de bloco: {ins['familia']} (escolhida). Alvenaria contada nos pavimentos {pav}. Térreo e subsolo (sob a transição) "
        "e muros ficam fora da alvenaria até o engenheiro definir.",
        "Coeficiente e perda (amarelo) são editáveis: a Quantidade recalcula. A Base vem do modelo de paredes e da paginação "
        "(para mudar a base, rode o leitor de novo).",
        "Argamassa: (5 fiadas/m × largura dos cordões × junta) + (12,5 juntas verticais/m² × 0,19 m × cordões × junta).",
        "Graute: canaleta 14 cm ≈ 0,0135 m³/m; canaleta 9 cm ≈ 0,0075 m³/m; furo vertical do bloco 14×19×39 ≈ 0,013 m³/m.",
        "Aço (kg/m): Ø6,3 = 0,245 · Ø8 = 0,395 · Ø10 = 0,617 · Ø12,5 = 0,963. Pontos verticais e bitolas são estimativa até o cálculo estrutural.",
        "Revestimentos: fundo preparador + gesso por dentro (sem gesso onde há cerâmica; elevador e garagens fora); "
        "pintura projetada direto no bloco na fachada, nas paredes das varandas e na platibanda.",
        "Ainda não incluído: pintura interna sobre o gesso, impermeabilização, contrapiso e pisos, estrutura de transição, "
        "caixa d'água e casa de máquinas.",
    ]
    ws.cell(row=r, column=1, value="Notas").font = Font(bold=True)
    for i, t in enumerate(notas, r + 1):
        ws.cell(row=i, column=1, value=t).font = Font(italic=True)
