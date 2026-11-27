"""Abas da planilha para a água fria: resumo × tabela do projetista, por coluna e andar, trechos e leitura."""
from __future__ import annotations

from collections import Counter, defaultdict

from openpyxl.styles import Alignment, Font, PatternFill

UNIDADE_TIPO = {"A": "Unidade 3", "B": "Unidade 4", "C": "Unidade 1", "D": "Unidade 2"}
ORDEM_PAV = ["Sub-Solo", "Pavimento Térreo", "1ºPavimento", "2ºPavimento", "3ºPavimento", "4ºPavimento", "5ºPavimento", "Cobertura"]


def _titulo(ws, r, texto):
    c = ws.cell(row=r, column=1, value=texto)
    c.font = Font(bold=True, size=12, color="0F6E56")
    return r + 1


def _linha_cab(ws, r, titulos):
    for i, t in enumerate(titulos, 1):
        c = ws.cell(row=r, column=i, value=t)
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="E1F5EE")
        c.alignment = Alignment(wrap_text=True)
    return r + 1


def abas(wb, dados, cabecalho):
    af = (dados.get("hidraulica") or {}).get("agua_fria")
    if not af:
        return
    tab = af.get("tabela_projetista") or {"tubos": {}, "conexoes": {}, "registros": {}}
    # ------------------------------------------------------------ resumo
    ws = wb.create_sheet("Água fria")
    cabecalho(ws, ["Item", "Modelo", "Tabela do projetista", "Diferença", "Observação"], [44, 14, 18, 14, 70])
    r = 2
    r = _titulo(ws, r, f"Tubos por diâmetro (m) — fonte: {af['pdf']}")
    comp = (af.get("complemento") or {}).get("trechos", [])
    tot, por_grupo = Counter(), defaultdict(Counter)
    for t in af["trechos"] + af["curtos"]:
        tot[int(t["dn"])] += t["L"]
        por_grupo["Prumadas dos apartamentos"][int(t["dn"])] += t["L"]
    for t in comp:
        tot[int(t["dn"])] += t["L"]
        por_grupo[t["grupo"]][int(t["dn"])] += t["L"]
    i0 = r
    for dn in sorted(set(tot) | {int(k) for k in tab["tubos"]}):
        m_, t_ = round(tot.get(dn, 0), 2), tab["tubos"].get(str(dn))
        ws.cell(row=r, column=1, value=f"Tubo PVC soldável marrom DN{dn}")
        ws.cell(row=r, column=2, value=m_).number_format = "#,##0.00"
        if t_ is not None:
            ws.cell(row=r, column=3, value=t_).number_format = "#,##0.00"
            ws.cell(row=r, column=4, value=f"=B{r}-C{r}").number_format = "#,##0.00;-#,##0.00"
        ws.cell(row=r, column=5, value=" · ".join(f"{g}: {v[dn]:.2f}".replace(".", ",") for g, v in por_grupo.items() if v.get(dn)))
        r += 1
    ws.cell(row=r, column=1, value="Total").font = Font(bold=True)
    for col in (2, 3, 4):
        L = ws.cell(row=r, column=col).column_letter
        ws.cell(row=r, column=col, value=f"=SUM({L}{i0}:{L}{r - 1})").number_format = "#,##0.00;-#,##0.00"
        ws.cell(row=r, column=col).font = Font(bold=True)
    r += 2
    ws.cell(row=r, column=1, value=(
        "Cada tubo uma vez. Prumadas dos apartamentos: isométricos de coluna (rótulo repetido no mesmo tubo conta uma vez; tubo sem "
        "rótulo num andar herda o do mesmo tubo noutro andar). Barrilete, térreo e subsolo: horizontais pela planta; verticais pela "
        "vista (planta ou isométrico) que mais os mostra; horizontais que só o isométrico rotula, no que passa da planta; colunas que "
        "atravessam o prédio (alimentação, extravasor, AF-13) uma vez.")).alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
    ws.row_dimensions[r].height = 60
    r += 2
    r = _titulo(ws, r, "Conexões e registros (unidades)")
    r = _linha_cab(ws, r, ["Código · peça", "Modelo", "Tabela do projetista", "Diferença", ""])
    cod_m = Counter(c["cod"] for c in af["conexoes"])
    for cs in ((af.get("complemento") or {}).get("codigos_plantas") or {}).values():
        cod_m.update(cs)
    descr = {k: v for k, v in {**tab.get("conexoes", {}), **tab.get("registros", {})}.items()}
    for k in sorted(set(cod_m) | set(descr)):
        d = descr.get(k) or []
        ws.cell(row=r, column=1, value=f"{k} · " + (d[0]["descricao"] if d else ""))
        ws.cell(row=r, column=2, value=cod_m.get(k, 0))
        if d:
            ws.cell(row=r, column=3, value=sum(x["qtd"] for x in d))
            ws.cell(row=r, column=4, value=f"=B{r}-C{r}")
        r += 1
    # ------------------------------------------------------------ por coluna e andar
    pc = wb.create_sheet("Água fria por coluna")
    dns = sorted({int(t["dn"]) for t in af["trechos"] + af["curtos"]})
    cabecalho(pc, ["Coluna", "Isométrico", "Unidade", "Pavimento", *[f"DN{d} (m)" for d in dns], "Total (m)", "Conexões", "Registros"],
              [10, 26, 12, 18, *[11] * len(dns), 11, 11, 11])
    g = defaultdict(Counter)
    orig = {}
    for t in af["trechos"] + af["curtos"]:
        g[(t["col"], t["pav"])][int(t["dn"])] += t["L"]
        orig[t["col"]] = t["origem"].split(" (")[0]
    con = Counter((c["col"], c["pav"], int(c["cod"]) >= 70) for c in af["conexoes"])
    r = 2
    for (col, pav) in sorted(g, key=lambda k: (k[0], ORDEM_PAV.index(k[1]) if k[1] in ORDEM_PAV else 99)):
        tipo = orig.get(col, "")
        letra = tipo.split(" - ")[0].replace("Tipo ", "") if tipo.startswith("Tipo ") else ""
        vals = [round(g[(col, pav)].get(d, 0), 2) for d in dns]
        pc.append([col, tipo, UNIDADE_TIPO.get(letra, ""), pav, *vals, None, con.get((col, pav, False), 0), con.get((col, pav, True), 0)])
        c1, c2 = pc.cell(row=r, column=5).column_letter, pc.cell(row=r, column=4 + len(dns)).column_letter
        pc.cell(row=r, column=5 + len(dns), value=f"=SUM({c1}{r}:{c2}{r})")
        for k in range(5, 6 + len(dns)):
            pc.cell(row=r, column=k).number_format = "#,##0.00"
        r += 1
    pc.cell(row=r, column=1, value="Total").font = Font(bold=True)
    for k in range(5, 8 + len(dns)):
        L = pc.cell(row=r, column=k).column_letter
        pc.cell(row=r, column=k, value=f"=SUM({L}2:{L}{r - 1})").font = Font(bold=True)
        pc.cell(row=r, column=k).number_format = "#,##0.00" if k < 6 + len(dns) else "0"
    # ------------------------------------------------------------ trechos
    tr = wb.create_sheet("Água fria trechos")
    cabecalho(tr, ["Trecho", "Coluna", "Pavimento", "DN", "Comprimento (m)", "Sentido", "Parede (auditoria)", "Tipo da parede",
                   "Ambientes", "Altura início (m)", "Altura fim (m)", "Fonte", "Rótulo ligado por"],
              [12, 9, 16, 6, 14, 11, 14, 13, 44, 12, 12, 34, 14])
    au = {x["id"]: x for x in (af.get("auditoria") or {}).get("trechos", [])}
    niv = af["niveis"]
    for t in af["trechos"]:
        a = au.get(t["id"], {})
        z0 = niv.get(t["pav"], 0)
        tr.append([t["id"], t["col"], t["pav"], int(t["dn"]), t["L"], "vertical" if a.get("vertical") else "horizontal",
                   a.get("parede") or "—", a.get("tipo_parede") or "fora de parede", ", ".join(a.get("ambientes") or []),
                   round(t["a"][2] - z0, 3), round(t["b"][2] - z0, 3), t["origem"], t["como"]])
    for t in af["curtos"]:
        tr.append(["—", t["col"], t["pav"], int(t["dn"]), t["L"], "curto", "—", "—", "", None, None, t["origem"],
                   "tubo curto entre conexões (sem traço próprio no desenho)"])
    for n, t in enumerate(comp, 1):
        zz = niv.get(t["pav"], 0)
        tr.append([f"{t['grupo'][:3].upper()}-{n:03d}", t["grupo"], t["pav"], int(t["dn"]), t["L"],
                   {"h": "horizontal", "v": "vertical"}.get(t["eixo"], "—"), "—", "—", "",
                   round(t["a"][2] - zz, 3) if t.get("a") else None, round(t["b"][2] - zz, 3) if t.get("b") else None,
                   t["origem"], f"{t['como']} · altura: {t['altura']}"])
    # ------------------------------------------------------------ leitura (como foi lido)
    le = wb.create_sheet("Água fria leitura")
    cabecalho(le, ["Item", "Valor", "Detalhe"], [40, 22, 90])
    r = 2
    r = _titulo(le, r, "Isométricos de prumada")
    for i in af["isometricos"]:
        res = max(abs(v) for v in i["residuos_piso_m"].values()) * 1000
        le.append([f"{i['titulo']} (pág. {i['pagina']})", i["coluna"],
                   f"escala {i['k']:.1f} pt/m · pisos {', '.join(i['pisos'])} (desvio máx. {res:.1f} mm) · eixo horizontal "
                   f"{'%.3f' % i['f_planta'] if i.get('f_planta') else '—'} pela planta ({i['f_h']:.3f} pelos rótulos) · "
                   f"{i['n_trechos']} trechos, {len(i['repetidos'])} rótulos repetidos" + (f" · {'; '.join(i['avisos'])}" if i["avisos"] else "")])
        r += 1
    r = le.max_row + 2
    r = _titulo(le, r, "Plantas registradas sobre a arquitetura")
    for p in af["plantas"]:
        le.append([f"{p['pavimento']} (pág. {p['pagina']})", f"escala {p['escala']:.5f}",
                   f"vista {p['vista_arq']} · deslocamento {p['desloc']} pt · erro médio {p['rms_mm']} mm · {p['baloes']} balões de coluna"])
    r = le.max_row + 2
    r = _titulo(le, r, "Colunas (posição pela mediana dos balões dos andares tipo)")
    for c in af["colunas"]:
        d = af["direcoes"].get(c["id"], {})
        dire = ", ".join(sorted({v["u"] for v in d.values()})) or "—"
        le.append([c["id"], f"desvio máx. {max(c['desvio_mm'].values()):.0f} mm" if c["desvio_mm"] else "—",
                   f"diâmetros por andar: {', '.join(f'{k}: {v}' for k, v in c['diametros'].items() if v)} · ramal para {dire}"])
    if af["avisos"]:
        r = le.max_row + 2
        r = _titulo(le, r, "Avisos")
        for a in af["avisos"]:
            le.append(["", "", a])
    r = le.max_row + 2
    r = _titulo(le, r, "No topo dos isométricos (cobertura): fica para o barrilete")
    cob = Counter((t.get("col"), t.get("dn"), t.get("L"), t.get("cod")) for t in af["cobertura_nos_isometricos"])
    for (col, dn, L, cod), n in sorted(cob.items(), key=lambda kv: str(kv[0])):
        le.append([col, f"DN{dn} {L} m" if dn else f"conexão {cod}", f"{n}×"])
    fon = (af.get("complemento") or {}).get("fontes") or []
    if fon:
        r = le.max_row + 2
        r = _titulo(le, r, "Barrilete, térreo e subsolo: fontes lidas")
        for f in fon:
            le.append([f["fonte"], f"{f['horizontais']} horiz. · {f['verticais']} vert.", f"{f['repetidos']} rótulos repetidos no mesmo tubo"])
    for row in le.iter_rows(min_row=2):
        row[2].alignment = Alignment(wrap_text=True, vertical="top")


def aba_orcamento(wb, dados, cabecalho):
    af = (dados.get("hidraulica") or {}).get("agua_fria") or {}
    o = af.get("orcamento")
    if not o:
        return
    ws = wb.create_sheet("Instalações (B4)")
    cabecalho(ws, ["Grupo", "Item", "SINAPI", "Descrição SINAPI", "Un", "Quantidade", "Preço unitário (R$)", "Custo (R$)"],
              [20, 58, 10, 70, 6, 12, 14, 14])
    r = 2
    ini = {}
    for L in o["linhas"]:
        ini.setdefault(L["grupo"], r)
        ws.append([L["grupo"], L["item"], str(L["sinapi"]), L["descr"], L["un"], L["qtd"], L["preco"], None])
        ws.cell(row=r, column=8, value=f"=F{r}*G{r}")
        for c in (6, 7, 8):
            ws.cell(row=r, column=c).number_format = "#,##0.00"
        r += 1
    fim = r - 1
    r += 1
    for g in ini:
        ws.cell(row=r, column=2, value=f"Subtotal · {g}").font = Font(bold=True)
        ws.cell(row=r, column=8, value=f'=SUMIF(A2:A{fim},"{g}",H2:H{fim})').number_format = "#,##0.00"
        r += 1
    ws.cell(row=r, column=2, value="Total água fria (custo direto, sem BDI)").font = Font(bold=True)
    c = ws.cell(row=r, column=8, value=f"=SUM(H2:H{fim})")
    c.number_format = "#,##0.00"
    c.font = Font(bold=True)
    r += 2
    ws.cell(row=r, column=1, value=f"SINAPI {o['mes']} {o['uf']}, {'com' if o['desonerado'] else 'sem'} desoneração. Quantidades do modelo (aba Água fria).").font = Font(italic=True)
    for p in o["premissas"]:
        r += 1
        ws.cell(row=r, column=1, value="• " + p)
