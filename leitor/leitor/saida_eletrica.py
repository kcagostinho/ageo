"""Abas da planilha para a elétrica: resumo por pavimento × lista do projetista, pontos, eletrodutos, quadros de
carga × planta e orçamento SINAPI."""
from __future__ import annotations

from collections import Counter

from openpyxl.styles import Font, PatternFill

ORDEM_PAV = ["Sub-Solo", "Pavimento Térreo", "1ºPavimento", "2ºPavimento", "3ºPavimento", "4ºPavimento", "5ºPavimento"]
NOME = {"tomada_baixa": "Tomada baixa (0,30 m)", "tomada_media": "Tomada média (1,10 m)", "tomada_alta": "Ponto/tomada alta (2,20 m)",
        "interruptor": "Interruptor", "sensor": "Sensor de presença", "arandela": "Arandela", "luminaria": "Luminária de teto",
        "quadro": "Quadro (QD/QM)", "cx": "Caixa de passagem", "forca": "Ponto de força", "entrada": "Entrada de serviço"}


def abas(wb, dados, cabecalho):
    ele = dados.get("eletrica")
    if not ele:
        return
    from .eletrica import _contagens, ITENS_LISTA
    import re
    verde, amarelo = PatternFill("solid", fgColor="E1F5EE"), PatternFill("solid", fgColor="FAEEDA")
    pl = {r["pavimento"]: r for r in ele["plantas"]}
    pavs = [p for p in ORDEM_PAV if p in pl]
    # --- resumo: lista × modelo por pavimento
    ws = wb.create_sheet("Elétrica")
    cabecalho(ws, ["Item", "Pavimento", "Lista do projetista", "Modelo", "Diferença", "Situação"], [46, 18, 16, 12, 12, 12])
    r = 2
    for pav in pavs:
        c = _contagens(pl[pav])
        itens = ele["listas"].get(pav, [])
        linhas = []
        for rx, chave, nome in ITENS_LISTA:
            q = sum(x["qtd"] for x in itens if re.search(rx, x["item"]) and x["un"] == "pç")
            if q or c.get(chave):
                linhas.append((nome, q, c.get(chave, 0)))
        for w in sorted({int(m.group(1)) for x in itens if x["sub"] and x["sub"].startswith("Luminária sobrepor")
                         for m in [re.match(r"(\d+)", x["item"])] if m}):
            q = sum(x["qtd"] for x in itens if x["sub"] and x["sub"].startswith("Luminária sobrepor") and x["item"].startswith(str(w)))
            linhas.append((f"Luminária {w} W", q, c.get(f"luminária {w} W", 0)))
        for nome, q, m in linhas:
            ws.append([nome, pav, q, m, m - q, "ok" if abs(m - q) < 0.01 else "conferir"])
            ws.cell(row=r, column=6).fill = verde if abs(m - q) < 0.01 else amarelo
            r += 1
    r += 1
    ws.cell(row=r, column=1, value="Eletrodutos por bitola (metros)").font = Font(bold=True, size=12, color="0F6E56")
    r += 1
    for i, t in enumerate(["Bitola", "Pavimento", "Lista do projetista", "Modelo 3D (centro a centro, com descidas e prumadas)"], 1):
        ws.cell(row=r, column=i, value=t).font = Font(bold=True)
    r += 1
    m3d = Counter()
    for t in ele["rede3d"]["trechos"]:
        m3d[(t[2], t[3])] += t[4]
    for pav in pavs:
        lst = {x["item"].rstrip('"'): x["qtd"] for x in ele["listas"].get(pav, []) if (x["grupo"] or "").startswith("Eletroduto")}
        for b in sorted(set(lst) | {d for (p, d) in m3d if p == pav}):
            ws.append([f'{b}"', pav, lst.get(b), round(m3d.get((pav, b), 0), 2)])
            r += 1
    r += 1
    ws.cell(row=r, column=1, value=("Contagens: pontos lidos nas plantas × itens da lista de materiais de cada folha. Eletrodutos: o modelo 3D mede "
                                    "de centro a centro das caixas e põe as prumadas inteiras; a conferência mede também como o projetista "
                                    "(desenho + descida do forro ao topo da caixa), aba Conferência.")).font = Font(italic=True)
    # --- pontos
    ws = wb.create_sheet("Elétrica - pontos")
    cabecalho(ws, ["Pavimento", "Tipo", "Detalhe", "Nome", "Quadro", "Circuito", "Potência (W)", "Comando", "Altura do piso (m)", "x (m)", "y (m)"],
              [18, 26, 30, 10, 10, 10, 12, 10, 14, 10, 10])
    from .eletrica import conv_modelo
    for pav in pavs:
        rr = pl[pav]
        cv = conv_modelo(dados, rr["vista"])
        for p in rr["pontos"]:
            x, y = cv(p["xy"])
            ws.append([pav, NOME.get(p["tipo"], p["tipo"]), p["sub"], p.get("nome"), p.get("quadro"), p.get("circuito"), p.get("pot"),
                       p.get("comando"), "teto" if p["tipo"] == "luminaria" else p["h"], round(x, 3), round(y, 3)])
    # --- eletrodutos do modelo
    ws = wb.create_sheet("Elétrica - eletrodutos")
    cabecalho(ws, ["Id", "Tipo", "Pavimento", "Bitola", "Comprimento (m)", "Eixo", "Onde", "Fonte"], [10, 14, 18, 8, 14, 8, 12, 90])
    for t in ele["rede3d"]["trechos"]:
        ws.append([t[0], t[1], t[2], f'{t[3]}"', t[4], "vertical" if t[6] == "v" else "horizontal", t[7], t[5]])
    # --- quadros de carga × planta
    ws = wb.create_sheet("Elétrica - quadros")
    cabecalho(ws, ["Quadro", "Circuito", "Descrição", "Esquema", "Tensão", "Potência (W)", "Fases", "Seção (mm²)", "Disjuntor (A)",
                   "Pontos na tabela", "Pontos na planta", "Situação"], [10, 9, 34, 10, 12, 12, 8, 11, 12, 30, 30, 12])
    pts = Counter()
    for rr in ele["plantas"]:
        for p in rr["pontos"]:
            if p.get("quadro") and p["tipo"] not in ("cx", "quadro", "entrada", "interruptor", "sensor"):
                w = p.get("pot") or (100 if p["tipo"] in ("luminaria", "tomada_baixa") else None)
                pts[(p["quadro"], p.get("circuito"), w)] += 1
    r = 2
    for nome in sorted(ele["quadros"], key=lambda k: (k[:2], int(re.sub(r"\D", "", k) or 0))):
        for c in ele["quadros"][nome]["circuitos"]:
            tab = {int(w): k for w, k in list(c["il"].items()) + list(c["to"].items())}     # no obra.json a chave vira texto
            try:
                n = int(c["n"])
            except (TypeError, ValueError):
                n = None
            mod = {w: k for (q, ci, w), k in pts.items() if q == nome and ci == n} if n is not None else {}
            fmt = lambda d: " · ".join(f"{k}× {w} W" for w, k in sorted(d.items(), key=lambda kv: kv[0] or 0)) or "—"
            igual = n is None or not nome.startswith("QD") or tab == mod
            ws.append([nome, c["n"], c["desc"], c["esquema"], c["v"], c["w"], c["fases"], c["secao"], c["disj"], fmt(tab),
                       fmt(mod) if nome.startswith("QD") else "—", "ok" if igual else "conferir"])
            ws.cell(row=r, column=12).fill = verde if igual else amarelo
            r += 1
    # --- orçamento
    o = ele.get("orcamento")
    if not o:
        return
    ws = wb.create_sheet("Elétrica (orçamento)")
    cabecalho(ws, ["Grupo", "Item", "SINAPI", "Descrição SINAPI", "Un", "Quantidade", "Preço unitário (R$)", "Custo (R$)", "Nota"],
              [24, 58, 10, 70, 6, 12, 14, 14, 40])
    r = 2
    for L in o["linhas"]:
        ws.append([L["grupo"], L["item"], str(L["sinapi"]), L["descr"], L["un"], L["qtd"], L["preco"], None, L.get("nota") or ""])
        ws.cell(row=r, column=8, value=f"=F{r}*G{r}")
        for c in (6, 7, 8):
            ws.cell(row=r, column=c).number_format = "#,##0.00"
        r += 1
    fim = r - 1
    r += 1
    for g in dict.fromkeys(L["grupo"] for L in o["linhas"]):
        ws.cell(row=r, column=2, value=f"Subtotal · {g}")
        ws.cell(row=r, column=8, value=f'=SUMIF(A2:A{fim},"{g}",H2:H{fim})').number_format = "#,##0.00"
        r += 1
    ws.cell(row=r, column=2, value="Total elétrica (custo direto, sem BDI)").font = Font(bold=True)
    c = ws.cell(row=r, column=8, value=f"=SUM(H2:H{fim})")
    c.number_format, c.font = "#,##0.00", Font(bold=True)
    r += 2
    ws.cell(row=r, column=1, value=f"SINAPI {o['mes']} {o['uf']}, {'com' if o['desonerado'] else 'sem'} desoneração.").font = Font(italic=True)
    for p in o["premissas"]:
        r += 1
        ws.cell(row=r, column=1, value=f"• {p}")
    if o.get("nao_achou"):
        r += 1
        ws.cell(row=r, column=1, value=f"• Sem preço SINAPI: {', '.join(o['nao_achou'])}")
