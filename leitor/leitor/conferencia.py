"""Conferência automática do modelo contra o projeto, a cada leitura.

Cada verificação devolve uma linha (grupo, item, resultado, ok?). O que não fecha aparece
no terminal e na aba "Conferência" da planilha. Verificações:
  - ambientes: área medida × rótulo do arquiteto;
  - esquadrias: cada etiqueta L × H do projeto tem um vão no modelo, por pavimento e tipo
    (portas de elevador não têm etiqueta e são contadas à parte);
  - varandas: um vão de varanda por ambiente de varanda;
  - vãos soltos: todo vão está numa parede;
  - pavimentos repetidos: ambientes, quantitativos, vãos, paredes e paginação idênticos à referência;
  - escala: escala única do documento.
"""
from __future__ import annotations

from collections import Counter

VARANDA = ("varanda", "gourmet", "sacada", "terraço")


def _assinaturas(dados: dict, vid: str, titulo: str) -> dict:
    fam = dados["premissas"].get("familia", "39")
    pg = dados.get("paginacao", {}).get(fam, {}).get("por_pavimento", {}).get(titulo, {})
    return {
        "ambientes": sorted((a["nome"], round(a["area_m2"] or 0, 3), round(a["perimetro_m"] or 0, 3))
                            for a in dados["ambientes"] if a["vista"] == vid),
        "quantitativos": sorted((q["ambiente"], round(q["rodape_m"], 2), round(q["parede_liquida_m2"], 2), round(q["teto_m2"], 2),
                                 q["n_portas"], q["n_janelas"]) for q in dados["quantitativos"] if q["vista"] == vid),
        "vãos": sorted((x["tipo"], round(x["largura_m"], 3), x.get("altura_m"), x.get("peitoril_m"))
                       for x in dados["vaos"] if x["vista"] == vid),
        "paredes": sorted((p["tipo"], round(p["comprimento_m"], 3),
                           tuple(sorted((y["tipo"], round(y["largura_m"], 3)) for y in p["vaos"])))
                          for p in dados["paredes"] if p["vista"] == vid),
        "paginação": sorted((k, round(v, 4)) for k, v in pg.items()),
    }


def checar(dados: dict) -> list[tuple[str, str, str, bool]]:
    out = []
    vistas = dados["vistas"]
    # ambientes × rótulos
    st = Counter(a["status"] for a in dados["ambientes"])
    out.append(("Ambientes", "Área medida × rótulo do arquiteto (até 2%)", f"{st.get('ok', 0)} de {len(dados['ambientes'])} conferidos",
                st.get("ok", 0) == len(dados["ambientes"])))
    for v in vistas:
        vid, t = v["id"], v["titulo"]
        et = Counter((e["tipo"]) for e in dados["esquadrias"] if e["vista"] == vid)
        sem = [e for e in dados["esquadrias"] if e["vista"] == vid and not e.get("casada", True)]
        vs = [x for x in dados["vaos"] if x["vista"] == vid]
        mi = [x for x in dados.get("muros_inclinados", []) if x["vista"] == vid and x.get("vao")]
        n_porta = sum(1 for x in vs if x["tipo"] == "porta") + sum(1 for x in mi if x["vao"]["tipo"] == "porta")
        n_jan = sum(1 for x in vs if x["tipo"] == "janela") + sum(1 for x in mi if x["vao"]["tipo"] == "janela")
        n_elev = sum(1 for x in vs if x["tipo"] == "porta" and not x.get("etiqueta") and
                     (x.get("elevador") or "Elevador" in x.get("ambientes", [])))
        n_sem_et = sum(1 for x in vs if x["tipo"] in ("porta", "janela") and not x.get("etiqueta")) - n_elev
        ok = not sem and n_sem_et == 0 and et["porta"] == n_porta - n_elev and et["janela"] == n_jan
        txt = (f"etiquetas: {et['porta']} portas, {et['janela']} janelas · modelo: {n_porta} portas"
               + (f" (+{n_elev} de elevador, sem etiqueta)" if n_elev else "") + f", {n_jan} janelas")
        if sem:
            txt += " · sem vão: " + ", ".join(f"{e['tipo']} {e['largura_m']:.2f}×{e['altura_m']:.2f}" for e in sem)
        if n_sem_et:
            txt += f" · {n_sem_et} vão(s) sem etiqueta"
        out.append(("Esquadrias", t, txt.replace(".", ","), ok))
        n_var = sum(1 for a in dados["ambientes"] if a["vista"] == vid and any(k in a["nome"].lower() for k in VARANDA))
        v_var = sum(1 for x in vs if x["tipo"] == "varanda")
        if n_var or v_var:
            out.append(("Varandas", t, f"{n_var} ambientes de varanda · {v_var} vãos de varanda", n_var == v_var))
        ids = {y["vao"] for p in dados["paredes"] if p["vista"] == vid for y in p["vaos"]}
        soltos = [x["id"] for x in vs if x["id"] not in ids]
        out.append(("Vãos", t, "todos numa parede" if not soltos else "fora de parede: " + ", ".join(soltos), not soltos))
    # pavimentos repetidos
    por_titulo = {v["titulo"]: v for v in vistas}
    for v in vistas:
        ref = v.get("repete")
        if not ref or ref not in por_titulo:
            continue
        a, b = _assinaturas(dados, v["id"], v["titulo"]), _assinaturas(dados, por_titulo[ref]["id"], ref)
        dif = [k for k in a if a[k] != b[k]]
        out.append(("Pavimentos repetidos", f"{v['titulo']} = {ref}",
                    "ambientes, quantitativos, vãos, paredes e paginação idênticos" if not dif else "diferem: " + ", ".join(dif),
                    not dif))
    ms = {round(v["m_por_pt"], 9) for v in vistas}
    out.append(("Escala", "Escala única do documento", f"{len(ms)} escala(s) em {len(vistas)} vistas", len(ms) == 1))
    return out


def aba(wb, linhas, cabecalho):
    from openpyxl.styles import Font, PatternFill
    ws = wb.create_sheet("Conferência")
    cabecalho(ws, ["Grupo", "Item", "Resultado", "Situação"], [22, 30, 90, 12])
    verde, amarelo = PatternFill("solid", fgColor="E1F5EE"), PatternFill("solid", fgColor="FAEEDA")
    for r, (g, item, res, ok) in enumerate(linhas, 2):
        ws.cell(row=r, column=1, value=g)
        ws.cell(row=r, column=2, value=item)
        ws.cell(row=r, column=3, value=res)
        c = ws.cell(row=r, column=4, value="ok" if ok else "conferir")
        c.fill = verde if ok else amarelo
        c.font = Font(bold=not ok)
    n = len(linhas) + 3
    ws.cell(row=n, column=1, value=("Conferência automática do modelo contra o próprio projeto (rótulos, etiquetas, ambientes). "
                                    "Divergências do projeto em si ficam em docs/pontos-para-o-arquiteto.md.")).font = Font(italic=True)
    return ws
