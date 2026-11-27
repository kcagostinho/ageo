"""Conferência automática do modelo contra o projeto, a cada leitura.

Cada verificação devolve uma linha (grupo, item, resultado, ok?). O que não fecha aparece
no terminal e na aba "Conferência" da planilha. Verificações:
  - ambientes: área medida × rótulo do arquiteto;
  - esquadrias: cada etiqueta L × H do projeto tem um vão no modelo, por pavimento e tipo
    (portas de elevador não têm etiqueta e são contadas à parte);
  - varandas: um vão de varanda por ambiente de varanda;
  - vãos soltos: todo vão está numa parede;
  - pavimentos repetidos: ambientes, quantitativos, vãos, paredes e paginação idênticos à referência;
  - escala: escala única do documento;
  - geometria, por pavimento: ambientes sobrepostos, parede sobre ambiente (faixa > 1 cm), parede sem
    comprimento, vão fora da parede ou mais alto que o pé-direito, vãos sobrepostos;
  - paginação bloco a bloco, por pavimento: peças sobrepostas na mesma parede e entre paredes (cantos,
    T e cruzamentos), lacunas sem bloco, cortes menores que 5 cm e juntas a prumo (desencontro < 5 cm).
"""
from __future__ import annotations

import math
from collections import Counter

import shapely
from shapely.geometry import LineString, Polygon

ESP_BLOCO = {"estrutural": 0.14, "vedação": 0.09}

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


def geometria(dados: dict) -> dict:
    """{pavimento: Counter de problemas de ambientes, paredes e vãos}."""
    pd = dados["premissas"]["pe_direito_m"]
    out = {}
    for v in dados["vistas"]:
        m, c = v["m_por_pt"], Counter()
        h = pd.get(v["titulo"], 2.6)
        polys = [(a, Polygon(a["poligono"], a.get("furos") or []).buffer(0)) for a in dados["ambientes"]
                 if a["vista"] == v["id"] and a["poligono"]]
        for i, (a, P) in enumerate(polys):
            for b, Q in polys[i + 1:]:
                if P.intersection(Q).area * m * m > 0.005:
                    c["ambientes sobrepostos"] += 1
        for p in dados["paredes"]:
            if p["vista"] != v["id"]:
                continue
            if p["comprimento_m"] < 0.05:
                c["paredes sem comprimento"] += 1
                continue
            for y in p["vaos"]:
                if y["inicio_m"] < -0.02 or y["inicio_m"] + y["largura_m"] > p["comprimento_m"] + 0.02:
                    c["vãos fora da parede"] += 1
                topo = (y.get("peitoril_m") or 0) + (y.get("altura_m") or 0) if y["tipo"] == "janela" else (y.get("altura_m") or 0)
                if topo > h + 0.001:
                    c["vãos mais altos que o pé-direito"] += 1
            vs = sorted(p["vaos"], key=lambda y: y["inicio_m"])
            c["vãos sobrepostos"] += sum(1 for a, b in zip(vs, vs[1:]) if b["inicio_m"] < a["inicio_m"] + a["largura_m"] - 0.01)
            if p["tipo"] == "muro" or "sobre porta" in p.get("motivo", "") or p.get("trecho_muro_inclinado"):
                continue
            e = p["eixo"]
            W = LineString([e[:2], e[2:]]).buffer(p["espessura_m"] / m / 2, cap_style="flat")
            Lp = math.hypot(e[2] - e[0], e[3] - e[1])
            ux, uy = (e[2] - e[0]) / Lp, (e[3] - e[1]) / Lp
            for y in p["vaos"]:          # aberturas até o piso: a parede está acima delas
                if y["tipo"] in ("porta", "varanda"):
                    s0, s1 = y["inicio_m"] / m, (y["inicio_m"] + y["largura_m"]) / m
                    W = W.difference(LineString([(e[0] + ux * s0, e[1] + uy * s0), (e[0] + ux * s1, e[1] + uy * s1)])
                                     .buffer(p["espessura_m"] / m, cap_style="flat"))
            for a, P in polys:
                ar = W.intersection(P).area * m * m
                if ar > 0 and ar / p["comprimento_m"] > 0.01:
                    c["paredes sobre ambiente (> 1 cm)"] += 1
        out[v["titulo"]] = c
    return out


def paginacao(dados: dict, prumo_cm: float = 5.0, corte_min_cm: float = 5.0) -> dict:
    """{pavimento: Counter} da paginação refeita bloco a bloco, em planta, fiada a fiada."""
    from . import paginacao as PG
    fam = dados["premissas"].get("familia", "39")
    if not dados.get("paginacao", {}).get(fam):
        return {}
    _, det = PG.paginar(dados, fam, guardar_todas=True)
    V = {v["id"]: v for v in dados["vistas"]}
    out = {}
    for vid in sorted({L["vista"] for L in det}):
        v = V[vid]; m = v["m_por_pt"]
        linhas = [L for L in det if L["vista"] == vid]
        c = Counter()
        n_f = max(len(L["fiadas"]) for L in linhas)
        for k in range(n_f):
            rects = []
            for L in linhas:
                if k >= len(L["fiadas"]):
                    continue
                e = L["eixo"]; ax, ay, bx, by = e[0] * m, e[1] * m, e[2] * m, e[3] * m
                Lm = math.hypot(bx - ax, by - ay); ux, uy = (bx - ax) / Lm, (by - ay) / Lm
                f = sorted(L["fiadas"][k], key=lambda q: q[0])
                for a, b in zip(f, f[1:]):
                    if b[0] < a[0] + a[1] - 0.05:
                        c["peças sobrepostas na mesma parede"] += 1
                    elif b[0] > a[0] + a[1] + 0.5:
                        c["lacunas sem bloco"] += 1
                for u, w, t in f:
                    if t in ("vao", "cruzamento"):
                        continue
                    c["peças"] += 1
                    if t != "enchimento" and w < corte_min_cm - 1e-6:
                        c["cortes menores que 5 cm"] += 1
                    u0, u1 = u / 100, (u + w - 1) / 100
                    rects.append((L["id"], LineString([(ax + ux * u0, ay + uy * u0), (ax + ux * u1, ay + uy * u1)])
                                  .buffer(ESP_BLOCO[L["tipo"]] / 2, cap_style="flat")))
            arv = shapely.STRtree([r for _, r in rects])
            for i, (lid, R) in enumerate(rects):
                for j in arv.query(R, predicate="intersects"):
                    if j > i and rects[j][0] != lid and R.intersection(rects[j][1]).area > 0.0002:
                        c["blocos sobrepostos entre paredes"] += 1
        for L in linhas:
            def juntas(f):
                ab = [(u, u + w) for u, w, t in f if t in ("vao", "cruzamento")]
                fim = max(u + w for u, w, _ in f)
                return [u + w for u, w, t in f if t not in ("vao", "cruzamento") and u + w < fim - 0.5
                        and not any(a - 0.5 <= u + w <= b + 0.5 for a, b in ab)]
            for k in range(len(L["fiadas"]) - 1):
                ja, jb = juntas(L["fiadas"][k]), juntas(L["fiadas"][k + 1])
                c["juntas verticais"] += len(ja)
                c["juntas a prumo (< 5 cm)"] += sum(1 for x in ja if any(abs(x - y) < prumo_cm - 1e-6 for y in jb))
        out[v["titulo"]] = c
    return out


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
    for t_, c in geometria(dados).items():
        prob = {k: n for k, n in c.items() if n}
        out.append(("Geometria", t_, "sem ambientes ou paredes sobrepostos, sem vão fora de parede" if not prob else
                    " · ".join(f"{k}: {n}" for k, n in prob.items()), not prob))
    for t_, c in paginacao(dados).items():
        prob = {k: n for k, n in c.items() if n and k not in ("peças", "juntas verticais")}
        mil = lambda n: f"{n:,}".replace(",", ".")
        txt = (f"{mil(c['peças'])} peças e {mil(c['juntas verticais'])} juntas conferidas: sem sobreposição, sem lacuna, "
               f"sem corte < 5 cm e sem junta a prumo")
        out.append(("Paginação", t_, txt if not prob else " · ".join(f"{k}: {n}" for k, n in prob.items()), not prob))
    alt = dados.get("alteracoes") or []
    if alt:
        regras = sorted({r["regra"] for r in alt})
        for rg in regras:
            rs = [r for r in alt if r["regra"] == rg]
            out.append(("Alterações de projeto", rg[:90],
                        f"{len(rs)} paredes removidas em {len({r['pavimento'] for r in rs})} pavimentos · "
                        f"{sum(len(r['vaos']) for r in rs)} vãos e {sum(len(r['etiquetas']) for r in rs)} etiquetas fora da contagem · "
                        f"+{sum(sum(r['piso_acrescido_m2'].values()) for r in rs):.2f} m² de piso".replace(".", ","), True))
    ms = {round(v["m_por_pt"], 9) for v in vistas}
    out.append(("Escala", "Escala única do documento", f"{len(ms)} escala(s) em {len(vistas)} vistas", len(ms) == 1))
    af = (dados.get("hidraulica") or {}).get("agua_fria")
    if af:
        from .hidraulica import conferir
        out += conferir(af)
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
