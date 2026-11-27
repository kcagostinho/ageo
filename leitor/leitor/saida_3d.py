"""Visualizador 3D (three.js) — etapa 3D-1: andares, ambientes clicáveis, paredes por tipo com vãos.

Gera um HTML único (three.js embutido, sem internet). Coordenadas da cena em metros:
X = direita da planta, Z = para baixo na planta, Y = para cima. Cada andar é alinhado pelo centro do
elevador (o mesmo em todos os pavimentos) e posto na altura lida dos cortes.
"""
from __future__ import annotations

import html
import json
import math
import unicodedata
from pathlib import Path

import shapely
from shapely.geometry import Polygon, LineString

VENDOR = Path(__file__).parent / "vendor" / "three-0.160.0-orbit.min.js"


def _sa(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def _acabamento(nome: str, tipo: str) -> str:
    n = _sa(nome)
    if tipo == "externa":
        return "Pintura projetada direto no bloco (premissa)"
    if tipo in ("garagem", "técnico"):
        return "—"
    if "banheiro" in n or "lavabo" in n:
        return "Cerâmica até o teto (premissa) · teto: fundo preparador + gesso"
    if "cozinha" in n or "a.s." in n or "servico" in n:
        return "Cerâmica até 1,50 m (premissa) + fundo preparador + gesso acima · teto: gesso"
    return "Fundo preparador + gesso (paredes e teto)"


def _r(v, n=3):
    return round(float(v), n)


COD = {"inteiro": 0, "meio": 1, "especial": 2, "J": 3, "U": 4, "corte": 5, "enchimento": 6, "cruzamento": 8, "vao": 9}


def montar(dados: dict) -> dict:
    from .quantitativos import classificar
    from . import paginacao as PG
    from .insumos import pontos_verticais_xy
    familia = dados["premissas"].get("familia", "39")
    _, det_todas = PG.paginar(dados, familia, guardar_todas=True)
    vistas = [v for v in dados["vistas"] if any(a["vista"] == v["id"] for a in dados["ambientes"])]
    pd = dados["premissas"]["pe_direito_m"]
    laje = 0.15
    # níveis: térreo = 0; subsolo abaixo; tipos acima (pé-direito + laje)
    nomes = [v["titulo"] for v in vistas]
    i_ter = next((i for i, t in enumerate(nomes) if "térreo" in t.lower() or "terreo" in t.lower()), 0)
    z = {}
    acc = 0.0
    for i in range(i_ter, len(vistas)):
        z[nomes[i]] = acc
        acc += pd.get(nomes[i], 2.6) + laje
    acc = 0.0
    for i in range(i_ter - 1, -1, -1):
        acc -= pd.get(nomes[i], 2.6) + laje
        z[nomes[i]] = acc
    qidx = {q["indice_ambiente"]: q for q in dados["quantitativos"]}
    vao_por_id = {x["id"]: x for x in dados.get("vaos", [])}
    from .cobertura import ALTURAS
    pag39 = dados.get("paginacao", {}).get(dados["premissas"].get("familia", "39"), {}).get("por_pavimento", {})
    orc = dados.get("orcamento")
    rat = {k: {int(i): x for i, x in v.items()} for k, v in (orc or {}).get("rateio", {}).items()}

    def custo(chave):
        d = rat.get(chave)
        if not d:
            return {}
        return {"c": _r(sum(d.values()), 2), "cx": [[i, _r(x, 2)] for i, x in sorted(d.items(), key=lambda kv: -kv[1]) if x >= 0.005]}

    # instalações (água fria): coordenadas no sistema do 1º pavimento (os tipos são cópias alinhadas) -> modelo
    hid = (dados.get("hidraulica") or {}).get("agua_fria")
    hid_out, hid_por_pav = None, {}
    if hid:
        v1 = next((v for v in dados["vistas"] if v["titulo"] == "1ºPavimento"), None)
        el1 = v1 and next((a for a in dados["ambientes"] if a["vista"] == v1["id"] and a["nome"] == "Elevador" and a["poligono"]), None)
        if el1:
            m1, c1 = v1["m_por_pt"], Polygon(el1["poligono"]).centroid
            cvh = lambda x, y: (_r(x * m1 - c1.x * m1), _r(y * m1 - c1.y * m1))
            lista = []
            for i, t in enumerate(hid["trechos"]):
                lista.append([t["id"], t["col"], t["pav"], t["dn"], t["L"], t["origem"], t.get("eixo") or "", t.get("como") or ""])
                hid_por_pav.setdefault(t["pav"], {"t": [], "c": []})["t"].append(
                    [*cvh(*t["a"][:2]), t["a"][2], *cvh(*t["b"][:2]), t["b"][2], t["dn"], i])
            for c in hid["conexoes"]:
                hid_por_pav.setdefault(c["pav"], {"t": [], "c": []})["c"].append([*cvh(*c["p"][:2]), c["p"][2], int(c["cod"]), c["col"]])
            # barrilete, térreo e subsolo (planta) e colunas do prédio (alimentação, extravasor, AF-13)
            convs = {}
            for v in dados["vistas"]:
                elv = next((a for a in dados["ambientes"] if a["vista"] == v["id"] and a["nome"] == "Elevador" and a["poligono"]), None)
                if elv:
                    cc, mm = Polygon(elv["poligono"]).centroid, v["m_por_pt"]
                    convs[v["id"]] = (lambda cc, mm: (lambda x, y: (_r(x * mm - cc.x * mm), _r(y * mm - cc.y * mm))))(cc, mm)
            comp = (hid.get("complemento") or {}).get("trechos", [])
            for n, t in enumerate(comp, 1):
                if not t.get("a"):
                    continue
                cv = convs.get(t.get("vista"), cvh)
                lista.append([f"{t['grupo'][:3].upper()}-{n:03d}", t["grupo"], t["pav"], t["dn"], t["L"], t["origem"], t.get("eixo") or "",
                              f"altura por premissa ({t['altura']})"])
                hid_por_pav.setdefault(t["pav"], {"t": [], "c": []})["t"].append([*cv(*t["a"][:2]), t["a"][2], *cv(*t["b"][:2]), t["b"][2], t["dn"], len(lista) - 1])
            colxy = {c["id"]: c["xy"] for c in hid["colunas"]}
            longas = sorted((t for t in comp if t.get("como") == "coluna"), key=lambda t: (-t["dn"], -t["L"]))
            topo_res = hid["niveis"]["Cobertura"] + 1.35 + 1.60
            alvo = [("AL", 32, topo_res), ("EXTRAV.", 32, topo_res), ("AF-13", 25, hid["niveis"]["Cobertura"] + 0.10)]
            niv = sorted(hid["niveis"].items(), key=lambda kv: kv[1])
            for nome, dn, topo in alvo:
                t = next((x for x in longas if x["dn"] == dn and not x.get("_usado")), None)
                if not t or nome not in colxy:
                    continue
                t["_usado"] = True
                base = max(topo - t["L"], hid["niveis"].get("Sub-Solo", -2.75) + 0.20)
                lista.append([nome, nome, "prédio", t["dn"], t["L"], t["origem"], "v", "coluna: posição pelo balão das plantas, extremos por premissa"])
                x, y = cvh(*colxy[nome])
                for k, (pav, zf) in enumerate(niv):
                    z1 = niv[k + 1][1] if k + 1 < len(niv) else 1e9
                    a_, b_ = max(base, zf), min(topo, z1)
                    if b_ - a_ > 0.01:
                        hid_por_pav.setdefault(pav, {"t": [], "c": []})["t"].append([x, y, _r(a_), x, y, _r(b_), t["dn"], len(lista) - 1])
            tab = hid.get("tabela_projetista") or {}
            cod = {k: v[0]["descricao"] for k, v in {**tab.get("conexoes", {}), **tab.get("registros", {})}.items() if v}
            hid_out = {"trechos": lista, "cod": cod, "tab": {str(k): v for k, v in (tab.get("tubos") or {}).items()},
                       "curtos": [[t["col"], t["pav"], t["dn"], t["L"]] for t in hid.get("curtos", [])],
                       "colunas": [[c["id"], *cvh(*c["xy"])] for c in hid["colunas"]], "pdf": hid.get("pdf"),
                       "escopo": "prumadas dos apartamentos, barrilete, térreo, subsolo e colunas do prédio",
                       "sempos": [[t["grupo"], t["pav"], t["dn"], t["L"], t["origem"]] for t in comp if not t.get("a") and not t.get("_usado")],
                       "codpl": (hid.get("complemento") or {}).get("codigos_plantas") or {},
                       "orc": hid.get("orcamento") and {"total": hid["orcamento"]["total"], "grupos": hid["orcamento"]["grupos"],
                                                        "mes": hid["orcamento"]["mes"], "custo": hid["orcamento"]["por_trecho"]}}
    andares = []
    esc_vista = {e["vista"]: e for e in dados.get("escadas", [])}
    pegada_ant = None                                  # projeção da escada do andar de baixo (furo nesta laje)
    for ordem, v in enumerate(vistas):
        m = v["m_por_pt"]
        ambs = [(i, a) for i, a in enumerate(dados["ambientes"]) if a["vista"] == v["id"] and a["poligono"]]
        el = next((a for _, a in ambs if a["nome"] == "Elevador"), None)
        if el is None:
            continue
        c = Polygon(el["poligono"]).centroid
        ox, oy = c.x * m, c.y * m
        conv = lambda p: [_r(p[0] * m - ox), _r(p[1] * m - oy)]

        amb_out, polys_m = [], []
        for i, a in ambs:
            q = qidx.get(i, {})
            tipo = classificar(a["nome"])
            poly = [conv(p) for p in a["poligono"]]
            furos = [[conv(p) for p in h] for h in (a.get("furos") or [])]
            polys_m.append((a["nome"], Polygon(poly, furos).buffer(0)))
            amb_out.append({
                "nome": a["nome"], "unidade": a.get("unidade") or "", "tipo": tipo, "poly": poly, "furos": furos,
                "rot": conv(a["rotulo_xy"]), "area": a["area_m2"], "rotulo": a["area_rotulo_m2"], "dif": a["divergencia_pct"],
                "piso": a["area_piso_m2"], "perim": a["perimetro_m"],
                "teto": q.get("teto_m2"), "rodape": q.get("rodape_m"), "parede": q.get("parede_liquida_m2"),
                "portas": q.get("n_portas"), "janelas": q.get("n_janelas"), "acab": _acabamento(a["nome"], tipo),
                "obs": q.get("observacao") or a.get("observacao") or "",
                **custo(f"amb|{i}"),
            })

        par_out, caixas = [], []
        for p in dados["paredes"]:
            if p["vista"] != v["id"]:
                continue
            e = p["eixo"]
            a_, b_ = conv(e[:2]), conv(e[2:])
            vaos = []
            for x in p["vaos"]:
                w = x["largura_m"]
                if x["tipo"] == "porta":
                    base, topo = 0.0, x.get("altura_m") or 2.10
                else:
                    base = x.get("peitoril_m") or 1.0
                    topo = base + (x.get("altura_m") or 1.2)
                # tipo de esquadria para o 3D
                if x["tipo"] == "porta":
                    if w >= 2.5:
                        kind = "portao"
                    elif vao_por_id.get(x["vao"], {}).get("por_vidro"):
                        kind = "vidro"
                    elif vao_por_id.get(x["vao"], {}).get("elevador") or any("Elevador" in l for l in p["lado_a"] + p["lado_b"]):
                        kind = "elevador"
                    else:
                        kind = "madeira"
                else:
                    kind = "gradil" if x["tipo"] == "varanda" else "janela"
                vaos.append([x["tipo"], _r(x["inicio_m"]), _r(w), _r(base, 2), _r(topo, 2), kind])
            par_out.append({"id": p["id"], "tipo": p["tipo"], "fachada": p["fachada"], "a": a_, "b": b_,
                            "t": p["espessura_m"], "comp": p["comprimento_m"], "enc": [p["encontros"]["a"], p["encontros"]["b"]],
                            "la": p["lado_a"], "lb": p["lado_b"], "motivo": p["motivo"], "vaos": vaos, **custo(f"par|{p['id']}")})
            if p["tipo"] != "muro":
                caixas.append(LineString([a_, b_]).buffer(p["espessura_m"] / 2, cap_style="square"))

        # muros inclinados (pares de linhas em ângulo): entram inteiros e substituem os pedaços picados
        incl = [mi for mi in dados.get("muros_inclinados", []) if mi["vista"] == v["id"]]
        if incl:
            eixos = []
            for n_, mi in enumerate(incl, 1):
                a_, b_ = conv(mi["eixo"][:2]), conv(mi["eixo"][2:])
                eixos.append(LineString([a_, b_]))
                termo = "terreo" in _sa(v["titulo"])
                vaos_mi = []
                if mi.get("vao"):                          # porta/portão que ocupa a lacuna do muro
                    q = mi["vao"]
                    base = 0.0 if q["tipo"] == "porta" else (q.get("peitoril_m") or 1.0)
                    kind = "portao" if q["tipo"] == "porta" else "janela"
                    vaos_mi = [[q["tipo"], 0.0, _r(eixos[-1].length), _r(base, 2), _r(base + (q.get("altura_m") or 2.1), 2), kind]]
                par_out.append({"id": f"{v['id']}-MI{n_}", "tipo": "muro" if termo else "a definir", "fachada": True,
                                "a": a_, "b": b_, "t": mi["espessura_m"], "comp": round(eixos[-1].length, 3), "enc": ["—", "—"],
                                "la": ["—"], "lb": ["—"], "vaos": vaos_mi,
                                "h": ALTURAS["muro_m"] if termo else None,
                                "motivo": "muro inclinado (divisa)" + (f", altura assumida {ALTURAS['muro_m']:.2f} m" if termo else ", arrimo do subsolo a definir")})
            def picado(x):
                if x["comp"] > 0.8 or x["tipo"] not in ("muro", "a definir", "concreto") or "-MI" in x["id"]:
                    return False
                meio = LineString([x["a"], x["b"]]).interpolate(0.5, normalized=True)
                return any(e.distance(meio) < 0.35 for e in eixos)
            par_out[:] = [x for x in par_out if not picado(x)]

        # escada que sobe deste andar: degraus, patamar e corrimãos (altura do espelho = desnível ÷ nº de espelhos)
        esc = esc_vista.get(v["id"])
        pegada, escada_out = None, None
        if esc and esc.get("sobe") and esc.get("degraus"):
            prox = nomes[ordem + 1] if ordem + 1 < len(nomes) else None
            dz = (z[prox] - z[v["titulo"]]) if prox else pd.get(v["titulo"], 2.6) + laje
            hh = dz / esc["n_espelhos"]
            pegada = Polygon([conv(q) for q in esc["pegada"]]).buffer(0)
            escada_out = {"h": _r(hh, 4), "N": esc["n_espelhos"], "dz": _r(dz, 3), "destino": prox, "ambiente": esc["ambiente"],
                          "lances": len(esc["lances"]), "piso": esc["piso_m"], "largura": esc["largura_m"], "anot": esc.get("anotacoes") or {},
                          "degraus": [[k, [conv(q) for q in pol]] for k, pol in esc["degraus"]],
                          "patamares": [[k, [conv(q) for q in pol]] for k, pol in esc["patamares"]],
                          "corrimaos": [{"a": conv(c["a"]), "b": conv(c["b"]), "z0": c["z0"], "z1": c["z1"], "dentro": c["dentro"]}
                                        for c in esc["corrimaos"]]}
        # piso do ambiente da escada: só a parte em nível (sem os lances deste andar e o vão da escada de baixo)
        corte_esc = [g for g in (pegada, pegada_ant) if g is not None and not g.is_empty]
        if corte_esc:
            for x in amb_out:
                if not x["nome"].lower().startswith("escada"):
                    continue
                resto = Polygon(x["poly"], x["furos"]).buffer(0).difference(shapely.union_all(corte_esc))
                partes = [g for g in getattr(resto, "geoms", [resto]) if g.geom_type == "Polygon" and g.area > 0.05]
                if partes:
                    g = max(partes, key=lambda q: q.area).simplify(0.005)
                    x["poly"] = [[_r(a), _r(b)] for a, b in g.exterior.coords][:-1]
                    x["furos"] = [[[_r(a), _r(b)] for a, b in h.coords][:-1] for h in g.interiors]
                    rp = g.representative_point()
                    x["rot"] = [_r(rp.x), _r(rp.y)]
        # laje: contorno do andar (ambientes + paredes), com furo no elevador e sobre os lances da escada de baixo
        corpo = shapely.union_all([g for _, g in polys_m if not g.is_empty] + caixas).buffer(0.03, join_style="mitre").buffer(-0.03, join_style="mitre")
        furos_laje = [g for n, g in polys_m if n == "Elevador"]
        if ordem != i_ter and ordem > 0 and furos_laje:
            corpo = corpo.difference(shapely.union_all(furos_laje))
        if ordem > 0 and pegada_ant is not None:
            corpo = corpo.difference(pegada_ant)
        pegada_ant = pegada
        laje_out = []
        for g in getattr(corpo, "geoms", [corpo]):
            if g.geom_type != "Polygon" or g.area < 1:
                continue
            g = g.simplify(0.01)
            laje_out.append({"ext": [[_r(x), _r(y)] for x, y in g.exterior.coords][:-1],
                             "furos": [[[_r(x), _r(y)] for x, y in h.coords][:-1] for h in g.interiors]})

        # resumo do andar
        def soma(tipo, campo):
            return sum(x[campo] for x in par_out if x["tipo"] == tipo)
        pdv = pd.get(v["titulo"], 2.6)
        def liq(tipo):
            return sum(x["comp"] * pdv - sum(y[2] * (y[4] - y[3]) for y in x["vaos"]) for x in par_out if x["tipo"] == tipo)
        pg = pag39.get(v["titulo"], {})
        blocos_est = sum(val for k, val in pg.items() if k.startswith(("14×", "canaleta J 14", "meia canaleta J 14", "canaleta U 14", "meia canaleta U 14")))
        blocos_ved = sum(val for k, val in pg.items() if k.startswith(("9×", "canaleta U 9", "meia canaleta U 9")))
        resumo = [
            ["Ambientes", f"{len(amb_out)}"],
            ["Piso (soma dos ambientes)", f"{sum(x['piso'] or 0 for x in amb_out):,.2f} m²"],
            ["Parede estrutural", f"{soma('estrutural', 'comp'):,.1f} m · {liq('estrutural'):,.1f} m² líquidos"],
            ["Parede de vedação", f"{soma('vedação', 'comp'):,.1f} m · {liq('vedação'):,.1f} m² líquidos"],
        ]
        if soma("a definir", "comp"):
            resumo.append(["Parede a definir (sob a transição)", f"{soma('a definir', 'comp'):,.1f} m"])
        n_portas = sum(1 for x in par_out for y in x["vaos"] if y[0] == "porta")
        n_jan = sum(1 for x in par_out for y in x["vaos"] if y[0] == "janela")
        n_var = sum(1 for x in par_out for y in x["vaos"] if y[0] == "varanda")
        resumo.append(["Vãos nas paredes", f"{n_portas} portas · {n_jan} janelas" + (f" · {n_var} varandas" if n_var else "")])
        if blocos_est:
            resumo.append(["Blocos estruturais (fam. 39)", f"{blocos_est:,.0f} peças"])
            resumo.append(["Blocos de vedação (9 cm)", f"{blocos_ved:,.0f} peças"])
        c_andar = sum(x.get("c", 0) for x in par_out) + sum(x.get("c", 0) for x in amb_out)
        if c_andar:
            resumo.append(["Custo B4 (alvenaria + revestimentos)", f"R$ {c_andar:,.2f}"])
        # paginação bloco a bloco (só andares com paredes estruturais/vedação definidas)
        pag = None
        linhas = [x for x in det_todas if x["vista"] == v["id"]]
        if linhas:
            pl = []
            for x in linhas:
                e = x["eixo"]
                cont = {k: round(val, 2) for k, val in x["contagem"].items()
                        if k.startswith(("14×", "9×", "canaleta", "meia canaleta", "cortes (peças)", "vergas (m)", "contravergas (m)", "cinta"))}
                pl.append({"id": x["id"], "tipo": x["tipo"], "fachada": x["fachada"], "a": conv(e[:2]), "b": conv(e[2:]),
                           "comp": x["comprimento_cm"], "pontas": [x["ponta_a"], x["ponta_b"]], "nseg": len(x["segmentos"]),
                           "cont": cont, "f": [[[_r(u, 1), _r(w, 1), COD.get(t, 0)] for u, w, t in fiada] for fiada in x["fiadas"]]})
            ps = [p for p in dados["paredes"] if p["vista"] == v["id"]]
            pag = {"familia": familia, "linhas": pl, "graute": [conv((x, y)) + [k] for x, y, k in pontos_verticais_xy(ps, m)]}
        hp = hid_por_pav.get(v["titulo"])
        hid_andar = None
        if hp:
            zz = z[v["titulo"]]
            # [x, altura acima do piso do andar, profundidade] como o three.js (y para cima)
            hid_andar = {"t": [[a, _r(c - zz), b, d, _r(f - zz), e, dn, i] for a, b, c, d, e, f, dn, i in hp["t"]],
                         "c": [[a, _r(c - zz), b, k, col] for a, b, c, k, col in hp["c"]]}
            tot = {}
            for x in hp["t"]:
                tot[x[6]] = tot.get(x[6], 0) + hid_out["trechos"][x[7]][4] * (1 if hid_out["trechos"][x[7]][2] != "prédio" else 0)
            resumo.append(["Água fria (tubos com posição)", " · ".join(f"DN{k} {val:,.2f} m" for k, val in sorted(tot.items()))])
        andares.append({"id": v["id"], "nome": v["titulo"], "ordem": ordem, "z": _r(z[v["titulo"]], 2), "pd": pdv, "pag": pag, "hid": hid_andar,
                        "ambientes": amb_out, "paredes": par_out, "laje": laje_out, "escada": escada_out,
                        "resumo": [[k, val.replace(",", "X").replace(".", ",").replace("X", ".")] for k, val in resumo]})

    # cobertura: um "andar" a mais sobre o último pavimento, alinhado pelo contorno da fachada
    cb = dados.get("cobertura_pdf")
    if cb and andares:
        topo = andares[-1]
        ext = [pt for x in topo["paredes"] if x["fachada"] for pt in (x["a"], x["b"])]
        if ext:
            t2 = 0.075
            bx0, by0 = min(q[0] for q in ext) - t2, min(q[1] for q in ext) - t2
            bx1, by1 = max(q[0] for q in ext) + t2, max(q[1] for q in ext) + t2
            mc = cb["m_por_pt"]
            cx0, cy0, cx1, cy1 = cb["caixa"]
            dx = (bx0 + bx1) / 2 - (cx0 + cx1) / 2 * mc
            dy = (by0 + by1) / 2 - (cy0 + cy1) / 2 * mc
            cv = lambda x, y: [_r(x * mc + dx), _r(y * mc + dy)]
            zc = _r(topo["z"] + topo["pd"] + 0.15, 2)
            menor = min(cb["telhados"], key=lambda t: (t["x1"] - t["x0"]) * (t["y1"] - t["y0"])) if cb["telhados"] else None
            def na_caixa_dagua(x0, y0, x1, y1):
                if not menor:
                    return False
                f = 0.35 / mc
                return all(menor["x0"] - f <= x <= menor["x1"] + f and menor["y0"] - f <= y <= menor["y1"] + f for x, y in ((x0, y0), (x1, y1)))
            par_c = []
            for n_, (x0, y0, x1, y1, t) in enumerate(cb["paredes"], 1):
                plat = na_caixa_dagua(x0, y0, x1, y1)
                a_, b_ = cv(x0, y0), cv(x1, y1)
                par_c.append({"id": f"COB-{n_:02d}", "tipo": "parapeito", "fachada": not plat, "a": a_, "b": b_, "t": t,
                              "comp": _r(math.hypot(b_[0] - a_[0], b_[1] - a_[1])), "enc": ["—", "—"], "la": ["—"], "lb": ["—"], "vaos": [],
                              "h": ALTURAS["platibanda_m"] if plat else ALTURAS["parapeito_m"],
                              "motivo": f"platibanda da caixa d'água (h={ALTURAS['platibanda_m']:.2f} m)" if plat else f"parapeito (h={ALTURAS['parapeito_m']:.2f} m)"})
            d_pl = rat.get("cob|platibanda")
            par_pl = [x for x in par_c if x["h"] == ALTURAS["parapeito_m"]]
            L_pl = sum(x["comp"] for x in par_pl)
            if d_pl and L_pl:
                for x in par_pl:
                    f = x["comp"] / L_pl
                    x["cx"] = [[i, _r(v * f, 2)] for i, v in sorted(d_pl.items(), key=lambda kv: -kv[1])]
                    x["c"] = _r(sum(v for _, v in x["cx"]), 2)
            telh = []
            for t in cb["telhados"]:
                caixa_d = t is menor
                prof = (t["y1"] - t["y0"]) * mc
                sobe = ALTURAS["inclinacao"] * prof
                baixo = (ALTURAS["platibanda_m"] - 0.10 - sobe) if caixa_d else ALTURAS["telhado_folga_m"]
                telh.append({"p0": cv(t["x0"], t["y0"]), "p1": cv(t["x1"], t["y1"]), "calha": t["calha"], "zb": _r(baixo, 2),
                             "za": _r(baixo + sobe, 2), "cx": caixa_d,
                             "area": _r((t["x1"] - t["x0"]) * mc * prof * math.sqrt(1 + ALTURAS["inclinacao"] ** 2), 2)})
            res = [cv(x, y) + [_r(r * mc, 2)] for x, y, r in cb["reservatorios"]]
            laje_c = [{"ext": L["ext"], "furos": []} for L in topo["laje"]]
            laje_res = None
            if menor:
                q0, q1 = cv(menor["x0"], menor["y0"]), cv(menor["x1"], menor["y1"])
                laje_res = [q0, q1]
            area_tel = sum(t["area"] for t in telh)
            resumo_c = [["Telhado de fibrocimento (i = 10%)", f"{area_tel:,.2f} m²"],
                        ["Parapeito (h = 1,20 m)", f"{sum(x['comp'] for x in par_c if x['h'] == ALTURAS['parapeito_m']):,.2f} m"],
                        ["Platibanda da caixa d'água (h = 4,00 m)", f"{sum(x['comp'] for x in par_c if x['h'] == ALTURAS['platibanda_m']):,.2f} m"],
                        ["Reservatórios", f"{len(res)} × 5,000 L"],  # a troca abaixo vira 5.000
                        ["Alturas", "cortes da prancha 5; reservatórios e telhado da caixa d'água simplificados"]]
            if d_pl:
                resumo_c.append(["Custo B4 (pintura da platibanda)", f"R$ {sum(d_pl.values()):,.2f}"])
            hpc = hid_por_pav.get("Cobertura")
            hid_cob = None
            if hpc:
                hid_cob = {"t": [[a, _r(c - zc), b, d, _r(f - zc), e, dn, i] for a, b, c, d, e, f, dn, i in hpc["t"]],
                           "c": [[a, _r(c - zc), b, k, col] for a, b, c, k, col in hpc["c"]]}
                tot = {}
                for x in hpc["t"]:
                    if hid_out["trechos"][x[7]][2] != "prédio":
                        tot[x[6]] = tot.get(x[6], 0) + hid_out["trechos"][x[7]][4]
                resumo_c.append(["Água fria (barrilete, tubos com posição)", " · ".join(f"DN{k} {val:,.2f} m" for k, val in sorted(tot.items()))])
            andares.append({"id": "cobertura", "nome": "Cobertura", "ordem": len(andares), "z": zc, "pd": ALTURAS["platibanda_m"], "pag": None, "hid": hid_cob,
                            "ambientes": [], "paredes": par_c, "laje": laje_c,
                            "cob": {"telhados": telh, "reservatorios": res, "laje_res": laje_res, "z_laje_res": ALTURAS["laje_reservatorio_m"],
                                    "h_res": ALTURAS["reservatorio_h_m"]},
                            "resumo": [[k, val.replace(",", "X").replace(".", ",").replace("X", ".")] for k, val in resumo_c]})

    obra = []
    ins = dados.get("insumos")
    if ins:
        for g, insumo, un, _, base, _, coef, _, perda, _ in ins["linhas"]:
            if any(k in insumo for k in ("Bloco 14", "Bloco 9", "Argamassa", "Graute", "Aço", "Gesso liso", "Pintura projetada direto")):
                q = base * coef * (1 + perda)
                obra.append([insumo, (f"{q:,.0f}" if un == "un" else f"{q:,.1f}").replace(",", "X").replace(".", ",").replace("X", ".") + f" {un}"])
    orc3d = None
    if orc:
        gr = {}
        for L in orc["linhas"]:
            gr[L["grupo"]] = gr.get(L["grupo"], 0) + L["custo"]
        cub = orc.get("cub")
        orc3d = {"mes": orc["mes"], "uf": orc["uf"], "deson": orc["premissas"]["desonerado"], "total": _r(orc["total"], 2),
                 "linhas": [[L["grupo"], L["item"], L["un"], _r(L["qtd"], 2), _r(L["preco"], 2), _r(L["custo"], 2)] for L in orc["linhas"]],
                 "grupos": [[g, _r(v, 2)] for g, v in gr.items()], "area": _r(orc["area_orc"], 2),
                 "areas": {k: _r(v, 2) for k, v in orc["areas"].items()},
                 "cub": cub and {"padrao": cub["padrao"], "mes": cub["mes"], "valor": cub["valor"], "ref": _r(cub["custo_ref"], 2)}}
    return {"obra": dados["obra"], "doc": dados["documento"], "gerado": dados["gerado_em"], "andares": andares, "resumoObra": obra,
            "orc": orc3d, "hid": hid_out}


def gerar(dados: dict, destino: Path):
    modelo = montar(dados)
    js = VENDOR.read_text(encoding="utf-8").replace("</script", "<\\/script")
    payload = json.dumps(modelo, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    txt = (MODELO.replace("__THREE__", js).replace("__DADOS__", payload)
           .replace("__OBRA__", html.escape(modelo["obra"])))
    destino.write_text(txt, encoding="utf-8")


MODELO = r"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Modelo 3D</title>
<style>
:root{--bg:#F3F2EE;--card:rgba(255,255,255,.94);--bd:rgba(0,0,0,.1);--tx:#1A1A1A;--mut:#5F5E5A;--dim:#888780;--acc:#0F6E56;--chip:#fff}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#17181A;--card:rgba(36,36,34,.94);--bd:rgba(255,255,255,.12);--tx:#F5F5F2;--mut:#B4B2A9;--dim:#888780;--acc:#5DCAA5;--chip:#2C2C2A}}
:root[data-theme=dark]{--bg:#17181A;--card:rgba(36,36,34,.94);--bd:rgba(255,255,255,.12);--tx:#F5F5F2;--mut:#B4B2A9;--dim:#888780;--acc:#5DCAA5;--chip:#2C2C2A}
*{box-sizing:border-box}html,body{margin:0;height:100%;background:var(--bg);color:var(--tx);font:13px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;overflow:hidden}
#c{position:fixed;inset:0;width:100%;height:100%;display:block;touch-action:none}
.top{position:fixed;left:0;right:354px;top:0;padding:10px 12px;display:flex;flex-direction:column;gap:6px;pointer-events:none;z-index:2}
.row{display:flex;gap:6px;overflow-x:auto;pointer-events:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch}.row::-webkit-scrollbar{display:none}
.tit{font-weight:600;font-size:14px;pointer-events:auto;text-shadow:0 1px 0 var(--bg)}
.chip{flex:none;border:1px solid var(--bd);background:var(--chip);color:var(--tx);border-radius:999px;padding:5px 11px;font:inherit;cursor:pointer;white-space:nowrap}
.chip[aria-pressed=true]{background:var(--acc);border-color:var(--acc);color:#fff}
.chip.f[aria-pressed=false]{opacity:.55}
.chip i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;vertical-align:0}
.painel{position:fixed;right:12px;top:118px;bottom:12px;width:330px;background:var(--card);border:1px solid var(--bd);border-radius:14px;overflow:auto;z-index:2;backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px)}
.sec{padding:12px 14px;border-bottom:1px solid var(--bd)}.sec:last-child{border-bottom:0}
.sec h3{margin:0 0 6px;font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.4px;font-weight:600}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}td{padding:3px 0;vertical-align:top}td.k{color:var(--mut);padding-right:8px;width:48%}
.big{font-size:15px;font-weight:600;margin-bottom:2px}.mut{color:var(--mut)}
.ctl{display:flex;align-items:center;gap:8px;margin:6px 0}.ctl input[type=range]{flex:1}
.handle{display:none}
@media (max-width:760px){
 .top{right:0}
 .painel{left:0;right:0;top:auto;bottom:0;width:auto;max-height:42vh;border-radius:16px 16px 0 0;transition:max-height .2s}
 .painel.min{max-height:52px;overflow:hidden}
 .handle{display:block;width:100%;border:0;background:none;padding:8px 0 2px;cursor:pointer}.handle span{display:block;margin:0 auto;width:40px;height:5px;border-radius:3px;background:var(--dim)}
}
.grad{height:10px;border-radius:5px;margin:4px 0 2px;background:linear-gradient(90deg,#F5EBCC,#EDB240,#CC402B,#5C1412)}
.esc{display:flex;justify-content:space-between;color:var(--mut);font-size:12px;font-variant-numeric:tabular-nums}
.bar{height:6px;border-radius:3px;background:var(--acc);opacity:.75;margin-top:3px}
select{font:inherit;color:var(--tx);background:var(--chip);border:1px solid var(--bd);border-radius:8px;padding:3px 6px}
.tip{position:fixed;pointer-events:none;background:#1A1A1A;color:#fff;font-size:12px;padding:5px 8px;border-radius:6px;display:none;z-index:3}
</style></head><body>
<canvas id="c"></canvas>
<div class="top">
 <div class="tit">__OBRA__ · modelo 3D</div>
 <div class="row" id="andares"></div>
 <div class="row" id="modos"></div>
 <div class="row" id="filtros"></div>
</div>
<div class="painel" id="painel">
 <button class="handle" id="handle" aria-label="Recolher painel"><span></span></button>
 <div class="sec" id="info"><h3>Seleção</h3><div class="mut">Toque ou clique num ambiente ou numa parede.</div></div>
 <div class="sec"><h3>Visualização</h3>
  <div class="ctl"><span>Afastar andares</span><input type="range" id="explode" min="0" max="4" step="0.1" value="0"></div>
  <div class="ctl"><label><input type="checkbox" id="cortev"> Corte vertical</label><select id="eixov" disabled><option value="x">transversal</option><option value="z">longitudinal</option></select><input type="range" id="posv" min="0.02" max="0.98" step="0.01" value="0.5" disabled></div>
  <div class="ctl"><label><input type="checkbox" id="corte"> Cortar a</label><input type="range" id="altcorte" min="0.3" max="2.6" step="0.05" value="1.2" disabled><span id="altv">1,20 m</span></div>
  <div class="row" id="cams" style="flex-wrap:wrap"></div>
 </div>
 <div class="sec" id="resumo"></div>
 <div class="sec" id="legenda"></div>
</div>
<div class="tip" id="tip"></div>
<script>__THREE__</script>
<script>
"use strict";
const D=__DADOS__;
const COR_PAREDE={"estrutural":0xC0392B,"vedação":0x2E86C1,"a definir":0xE8A317,"concreto":0x7B7B7B,"muro":0x9A6B2F,"parapeito":0xB9B4A8};
const COR_AMB={"seca":0xE9E1CF,"molhada":0x9FD3E6,"externa":0xB9E0A5,"circulação":0xD9D2E9,"garagem":0xCFCFCF,"técnico":0x8C8C8C};
const NOME_AMB={"seca":"seco (salas, quartos)","molhada":"molhado","externa":"varanda","circulação":"circulação","garagem":"garagem","técnico":"técnico"};
const SEL=0xFFD400,SELRGB=(()=>{const c=new THREE.Color(SEL);return [c.r,c.g,c.b]})();
const brl=v=>"R$ "+nf(v,2);
// rampa sequencial do mapa de calor (claro = barato, escuro = caro) e cinza para "sem custo"
const RAMPA=[[0,[0.96,0.92,0.80]],[0.35,[0.93,0.70,0.25]],[0.7,[0.80,0.25,0.17]],[1,[0.36,0.08,0.07]]],SEMCUSTO=[0.84,0.83,0.80];
function rampa(t){t=Math.max(0,Math.min(1,t));for(let i=1;i<RAMPA.length;i++){const [a,ca]=RAMPA[i-1],[b,cb]=RAMPA[i];if(t<=b){const u=(t-a)/(b-a);return ca.map((x,k)=>x+(cb[k]-x)*u)}}return RAMPA[RAMPA.length-1][1]}
// custo de cada andar (paredes + ambientes), usado no mapa "por andar"
D.andares.forEach(A=>{A.custo=A.paredes.reduce((s,p)=>s+(p.c||0),0)+A.ambientes.reduce((s,a)=>s+(a.c||0),0)});
const COR_DN={20:0x7FC8F8,25:0x2E86C1,32:0x1B4F9C,40:0x17A589,50:0x0B3D6B},OD_DN={20:0.020,25:0.025,32:0.032,40:0.040,50:0.050};
const raioDN=dn=>Math.max((OD_DN[dn]||0.025)*0.8,0.014);
const COR_REG=0xC0392B,COR_CON=0x5D6D7E;
const COR_PECA={0:0xD9D6CC,1:0xB4AE9E,2:0x8E7CC3,3:0xE08A1E,4:0xF2B24C,5:0x262626,6:0x8F8A80};
const COR_PECA_VED={0:0xB9CFE4,1:0x8EAFCF,3:0xE08A1E,4:0xF2B24C,5:0x262626,6:0x8F8A80};
const NOME_PECA=[["inteiro 14×19×39",0xD9D6CC],["meio 14×19×19",0xB4AE9E],["amarração 34/54",0x8E7CC3],["canaleta J (cinta fachada)",0xE08A1E],
 ["canaleta U (cinta, verga, contraverga)",0xF2B24C],["corte/compensador",0x262626],["enchimento de argamassa (< 5 cm)",0x8F8A80],["vedação 9 cm",0xB9CFE4],["graute vertical",0x1F4E8C]];
const nf=(n,d=2)=>n==null?"—":Number(n).toLocaleString("pt-BR",{minimumFractionDigits:d,maximumFractionDigits:d});
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

// ---------- cena
const canvas=document.getElementById("c");
const renderer=new THREE.WebGLRenderer({canvas,antialias:true});
renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));
renderer.localClippingEnabled=true;
const scene=new THREE.Scene();
const corFundo=()=>getComputedStyle(document.documentElement).getPropertyValue("--bg").trim()||"#F3F2EE";
scene.background=new THREE.Color(corFundo());
const camera=new THREE.PerspectiveCamera(45,1,0.1,800);
const controls=new OrbitControls(camera,canvas);controls.enableDamping=true;controls.dampingFactor=0.1;controls.screenSpacePanning=true;
scene.add(new THREE.HemisphereLight(0xffffff,0x8a8a80,1.1));
const sol=new THREE.DirectionalLight(0xffffff,1.1);sol.position.set(30,60,20);scene.add(sol);
const plano=new THREE.Plane(new THREE.Vector3(0,-1,0),1e6);
const planoV=new THREE.Plane(new THREE.Vector3(-1,0,0),1e6);

function caixa(pos,cor,cx,cy,cz,ax,az,L,H,T,idx,lista){
 // caixa orientada: centro (cx,cy,cz), eixo horizontal (ax,az), comprimento L, altura H, espessura T
 const nx=-az,nz=ax,hl=L/2,hh=H/2,ht=T/2;
 const P=(u,v,w)=>[cx+ax*u*hl+nx*w*ht,cy+v*hh,cz+az*u*hl+nz*w*ht];
 const f=[[[1,-1,-1],[1,1,-1],[1,1,1],[1,-1,1]],[[-1,-1,1],[-1,1,1],[-1,1,-1],[-1,-1,-1]],[[-1,1,-1],[-1,1,1],[1,1,1],[1,1,-1]],
  [[-1,-1,1],[-1,-1,-1],[1,-1,-1],[1,-1,1]],[[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]],[[1,-1,-1],[-1,-1,-1],[-1,1,-1],[1,1,-1]]];
 for(const q of f){const p=q.map(x=>P(...x));for(const k of [0,1,2,0,2,3]){pos.push(...p[k]);cor.push(...lista);idx.push(0)}}
}
function pedacos(L,H,vaos){
 // decompõe a elevação (L × H) menos os vãos em retângulos [u0,u1,z0,z1]
 const cortes=[0,L];vaos.forEach(v=>{cortes.push(Math.max(0,Math.min(L,v[1])),Math.max(0,Math.min(L,v[1]+v[2])))});
 const us=[...new Set(cortes.map(x=>+x.toFixed(3)))].sort((a,b)=>a-b),out=[];
 for(let i=0;i<us.length-1;i++){const a=us[i],b=us[i+1];if(b-a<0.005)continue;
  const tampa=vaos.filter(v=>v[1]<=a+0.003&&v[1]+v[2]>=b-0.003).map(v=>[Math.max(0,v[3]),Math.min(H,v[4])]).sort((x,y)=>x[0]-y[0]);
  let z=0;for(const [z0,z1] of tampa){if(z0>z+0.005)out.push([a,b,z,z0]);z=Math.max(z,z1)}if(H>z+0.005)out.push([a,b,z,H])}
 // junta faixas vizinhas com a mesma altura
 const j=[];for(const r of out){const p=j.find(s=>Math.abs(s[1]-r[0])<0.004&&Math.abs(s[2]-r[2])<0.004&&Math.abs(s[3]-r[3])<0.004);if(p)p[1]=r[1];else j.push(r.slice())}
 return j;
}
const andares=[],pick=[];
D.andares.forEach((A,ia)=>{
 const g=new THREE.Group();g.userData={A,ia};scene.add(g);
 const mats=[];const mat=o=>{const m=new THREE.MeshLambertMaterial(Object.assign({side:THREE.DoubleSide,clippingPlanes:[plano,planoV]},o));m.userData.op=o.opacity??1;mats.push(m);return m};
 // laje (sob o piso)
 A.laje.forEach(L=>{const s=new THREE.Shape(L.ext.map(p=>new THREE.Vector2(p[0],-p[1])));
  L.furos.forEach(h=>s.holes.push(new THREE.Path(h.map(p=>new THREE.Vector2(p[0],-p[1])))));
  const geo=new THREE.ExtrudeGeometry(s,{depth:0.15,bevelEnabled:false});geo.rotateX(-Math.PI/2);
  const me=new THREE.Mesh(geo,mat({color:0xBDB9AF}));me.position.y=-0.15;me.userData.laje=true;g.add(me)});
 // ambientes
 const ambs=[];A.ambientes.forEach((a,k)=>{const s=new THREE.Shape(a.poly.map(p=>new THREE.Vector2(p[0],-p[1])));
  a.furos.forEach(h=>s.holes.push(new THREE.Path(h.map(p=>new THREE.Vector2(p[0],-p[1])))));
  const geo=new THREE.ShapeGeometry(s);geo.rotateX(-Math.PI/2);
  const me=new THREE.Mesh(geo,mat({color:COR_AMB[a.tipo]||0xdddddd,polygonOffset:true,polygonOffsetFactor:-1}));me.position.y=0.006;
  me.userData={tipo:"amb",a,A};g.add(me);ambs.push(me);pick.push(me)});
 // paredes: uma malha por (tipo, fachada), com mapa triângulo → parede
 const grupos={};
 A.paredes.forEach((p,ip)=>{const k=p.tipo+"|"+(p.fachada?"ext":"int");(grupos[k]=grupos[k]||[]).push(ip)});
 const paredes=[];
 Object.entries(grupos).forEach(([k,lista])=>{
  const pos=[],cor=[],idx=[],tri=[];const [tipo]=k.split("|");const c=new THREE.Color(COR_PAREDE[tipo]||0x999999);const rgb=[c.r,c.g,c.b];
  const faixas={};
  lista.forEach(ip=>{const p=A.paredes[ip];const dx=p.b[0]-p.a[0],dz=p.b[1]-p.a[1],L=Math.hypot(dx,dz)||1e-6,ax=dx/L,az=dz/L;
   const ini=pos.length/3;
   pedacos(L,p.h||A.pd,p.vaos).forEach(([u0,u1,z0,z1])=>{const um=(u0+u1)/2;
    caixa(pos,cor,p.a[0]+ax*um,(z0+z1)/2,p.a[1]+az*um,ax,az,u1-u0,z1-z0,Math.max(p.t,0.05),idx,rgb)});
   const n=(pos.length/3-ini)/3;for(let t=0;t<n;t++)tri.push(ip);faixas[ip]=[ini,pos.length/3-ini]});
  const geo=new THREE.BufferGeometry();geo.setAttribute("position",new THREE.Float32BufferAttribute(pos,3));
  geo.setAttribute("color",new THREE.Float32BufferAttribute(cor,3));geo.computeVertexNormals();
  const me=new THREE.Mesh(geo,mat({vertexColors:true}));me.userData={tipo:"par",tipoParede:tipo,fachada:k.endsWith("ext"),tri,faixas,A,base:rgb};
  g.add(me);paredes.push(me);pick.push(me)});
 // paginação: blocos instanciados (uma malha por tipo de parede × fachada × bloco/canaleta)
 const pecas=[],grauteM=[];
 if(A.pag){
  const caixaU=new THREE.BoxGeometry(1,1,1),lista={};
  A.pag.linhas.forEach((L,il)=>L.f.forEach((fi,k)=>fi.forEach(([u,w,c])=>{if(c>=8)return;
   const key=L.tipo+"|"+(L.fachada?"ext":"int")+"|"+(c===3||c===4?"can":"blo");(lista[key]=lista[key]||[]).push([il,k,u,w,c])})));
  const q=new THREE.Quaternion(),Y=new THREE.Vector3(0,1,0),M=new THREE.Matrix4(),pos=new THREE.Vector3(),esc_=new THREE.Vector3(),col=new THREE.Color();
  Object.entries(lista).forEach(([key,arr])=>{
   const [tipo,fach,cat]=key.split("|");const me=new THREE.InstancedMesh(caixaU,mat({}),arr.length);
   const linha=new Int32Array(arr.length),base=new Float32Array(arr.length*3);
   arr.forEach(([il,k,u,w,c],i)=>{const L=A.pag.linhas[il],dx=L.b[0]-L.a[0],dz=L.b[1]-L.a[1],LL=Math.hypot(dx,dz)||1e-6,ax=dx/LL,az=dz/LL;
    const um=(u+w/2)/100;pos.set(L.a[0]+ax*um,k*0.2+0.105,L.a[1]+az*um);q.setFromAxisAngle(Y,Math.atan2(-az,ax));
    esc_.set(Math.max(w/100-0.01,0.01),0.19,tipo==="vedação"?0.09:0.14);M.compose(pos,q,esc_);me.setMatrixAt(i,M);
    col.setHex((tipo==="vedação"?COR_PECA_VED:COR_PECA)[c]??0xcccccc);me.setColorAt(i,col);base.set([col.r,col.g,col.b],i*3);linha[i]=il});
   me.instanceMatrix.needsUpdate=true;me.instanceColor.needsUpdate=true;me.computeBoundingSphere();
   me.userData={tipo:"pec",tipoParede:tipo,fachada:fach==="ext",cat,linha,base,A};me.visible=false;g.add(me);pecas.push(me);pick.push(me)});
  // pontos de graute vertical
  const cil=new THREE.CylinderGeometry(0.045,0.045,1,10),gm=new THREE.InstancedMesh(cil,mat({color:0x1F4E8C}),A.pag.graute.length);
  A.pag.graute.forEach(([x,z],i)=>{M.compose(new THREE.Vector3(x,A.pd/2,z),new THREE.Quaternion(),new THREE.Vector3(1,A.pd+0.02,1));gm.setMatrixAt(i,M)});
  gm.instanceMatrix.needsUpdate=true;gm.computeBoundingSphere();gm.visible=false;g.add(gm);grauteM.push(gm);
 }
 // esquadrias: vidro, caixilho, porta de madeira, portão/elevador, gradil da varanda
 const esq=[];
 {const caixaE=new THREE.BoxGeometry(1,1,1),it={vidro:[],caixilho:[],madeira:[],metal:[],gradil:[]};
  A.paredes.forEach(p=>{if(!p.vaos.length)return;const dx=p.b[0]-p.a[0],dz=p.b[1]-p.a[1],LL=Math.hypot(dx,dz)||1e-6,ax=dx/LL,az=dz/LL,ang=Math.atan2(-az,ax);
   const put=(k,u,y,w,h,t)=>it[k].push([p.a[0]+ax*u,y,p.a[1]+az*u,ang,w,h,t]);
   p.vaos.forEach(([tipo,u0,w,b0,b1,kind])=>{const uc=u0+w/2,h=b1-b0,yc=(b0+b1)/2;
    if(kind==="janela"||kind==="vidro"){put("vidro",uc,yc,w-0.06,h-0.06,0.02);
     put("caixilho",uc,b1-0.025,w,0.05,0.07);put("caixilho",uc,b0+0.025,w,0.05,0.07);put("caixilho",u0+0.025,yc,0.05,h,0.07);put("caixilho",u0+w-0.025,yc,0.05,h,0.07);
     if(w>=1.0)put("caixilho",uc,yc,0.04,h,0.06)}
    else if(kind==="madeira"){put("madeira",uc,h/2,w-0.08,h-0.03,0.035);put("caixilho",u0+0.02,h/2,0.04,h,Math.min(p.t,0.15));put("caixilho",u0+w-0.02,h/2,0.04,h,Math.min(p.t,0.15));put("caixilho",uc,h-0.02,w,0.04,Math.min(p.t,0.15))}
    else if(kind==="portao"||kind==="elevador"){put("metal",uc,h/2,w-0.04,h-0.02,0.05)}
    else if(kind==="gradil"){const yt=1.10;put("gradil",uc,yt,w,0.05,0.05);put("gradil",uc,b0+0.04,w,0.04,0.04);
     const n=Math.max(2,Math.round(w/0.11));for(let i=1;i<n;i++)put("gradil",u0+i*w/n,(b0+yt)/2,0.02,yt-b0,0.02)}})});
  const COR_ESQ={vidro:[0x9CC8E8,0.35],caixilho:[0x8A8F96,1],madeira:[0xA9784A,1],metal:[0x7D8288,1],gradil:[0x3B3D40,1]};
  const M=new THREE.Matrix4(),q=new THREE.Quaternion(),Y=new THREE.Vector3(0,1,0);
  Object.entries(it).forEach(([k,arr])=>{if(!arr.length)return;const [cor,op]=COR_ESQ[k];
   const me=new THREE.InstancedMesh(caixaE,mat({color:cor,transparent:op<1,opacity:op,depthWrite:op>=1}),arr.length);
   arr.forEach(([x,y,z,a,w,h,t],i)=>{q.setFromAxisAngle(Y,a);M.compose(new THREE.Vector3(x,y,z),q,new THREE.Vector3(Math.max(w,0.01),Math.max(h,0.01),t));me.setMatrixAt(i,M)});
   me.instanceMatrix.needsUpdate=true;me.computeBoundingSphere();me.userData={esq:true};g.add(me);esq.push(me)});
 }
 // escada: cada piso é um bloco (espelho + 12 cm de laje por baixo), patamar com 12 cm; corrimão a 0,88 m e guarda-corpo a 1,10 m
 const escM=[];
 if(A.escada){const E=A.escada,h=E.h,esp=0.12,mE=mat({color:0xC9C4B8});mE.userData.base=0xC9C4B8;
  const bloco=(poly,z0,z1)=>{const s=new THREE.Shape(poly.map(p=>new THREE.Vector2(p[0],-p[1])));
   const geo=new THREE.ExtrudeGeometry(s,{depth:Math.max(z1-z0,0.01),bevelEnabled:false});geo.rotateX(-Math.PI/2);
   const me=new THREE.Mesh(geo,mE);me.position.y=z0;me.userData={tipo:"esc",E,A,mat:mE};g.add(me);escM.push(me);pick.push(me)};
  E.degraus.forEach(([k,poly])=>bloco(poly,Math.max(0,(k-1)*h-esp),k*h));
  E.patamares.forEach(([k,poly])=>bloco(poly,k*h-esp,k*h));
  const pecas_=[];const add=(a,b)=>pecas_.push([a,b]);
  E.corrimaos.forEach(c=>{const za=c.z0*h,zb=c.z1*h,P=(t,y)=>[c.a[0]+(c.b[0]-c.a[0])*t,za+(zb-za)*t+y,c.a[1]+(c.b[1]-c.a[1])*t];
   add(P(0,0.88),P(1,0.88));
   if(c.dentro){add(P(0,1.10),P(1,1.10));const L=Math.hypot(c.b[0]-c.a[0],c.b[1]-c.a[1]),n=Math.max(2,Math.round(L/0.28));
    for(let i=0;i<=n;i++){const t=(i+0.5)/(n+1),q=P(t,0);add([q[0],q[1]-0.02,q[2]],[q[0],q[1]+1.10,q[2]])}}});
  const im=new THREE.InstancedMesh(new THREE.BoxGeometry(1,1,1),mat({color:0x3B3D40}),pecas_.length),M=new THREE.Matrix4(),X=new THREE.Vector3(1,0,0);
  pecas_.forEach(([a,b],i)=>{const va=new THREE.Vector3(...a),vb=new THREE.Vector3(...b),d=vb.clone().sub(va),L=d.length();
   M.compose(va.clone().add(vb).multiplyScalar(0.5),new THREE.Quaternion().setFromUnitVectors(X,d.normalize()),new THREE.Vector3(L,0.035,0.035));im.setMatrixAt(i,M)});
  im.instanceMatrix.needsUpdate=true;im.computeBoundingSphere();g.add(im);escM.push(im);
 }
 // água fria: tubos (cilindros por DN) e conexões/registros
 const hidM=[];
 if(A.hid){const cil=new THREE.CylinderGeometry(1,1,1,12),M=new THREE.Matrix4(),Yv=new THREE.Vector3(0,1,0),porDN={};
  A.hid.t.forEach(r=>{(porDN[r[6]]=porDN[r[6]]||[]).push(r)});
  Object.entries(porDN).forEach(([dn,arr])=>{const rr=raioDN(+dn),me=new THREE.InstancedMesh(cil,mat({color:COR_DN[dn]||0x2E86C1}),arr.length),ids=new Int32Array(arr.length);
   arr.forEach((r,i)=>{const a=new THREE.Vector3(r[0],r[1],r[2]),b=new THREE.Vector3(r[3],r[4],r[5]),d=b.clone().sub(a),L=Math.max(d.length(),0.004);
    M.compose(a.clone().add(b).multiplyScalar(0.5),new THREE.Quaternion().setFromUnitVectors(Yv,d.normalize()),new THREE.Vector3(rr,L,rr));me.setMatrixAt(i,M);ids[i]=r[7]});
   me.instanceMatrix.needsUpdate=true;me.computeBoundingSphere();me.userData={tipo:"hid",ids,A,raio:rr};me.visible=false;g.add(me);hidM.push(me);pick.push(me)});
  const sph=new THREE.SphereGeometry(1,12,8);
  [[A.hid.c.filter(c=>c[3]<70),COR_CON,0.024],[A.hid.c.filter(c=>c[3]>=70),COR_REG,0.034]].forEach(([arr,cor,r])=>{if(!arr.length)return;
   const me=new THREE.InstancedMesh(sph,mat({color:cor}),arr.length);
   arr.forEach((c,i)=>{M.compose(new THREE.Vector3(c[0],c[1],c[2]),new THREE.Quaternion(),new THREE.Vector3(r,r,r));me.setMatrixAt(i,M)});
   me.instanceMatrix.needsUpdate=true;me.computeBoundingSphere();me.userData={tipo:"con",arr,A,raio:r};me.visible=false;g.add(me);hidM.push(me);pick.push(me)});
 }
 // cobertura: telhados (fibrocimento i=10%), calhas, laje e reservatórios da caixa d'água
 if(A.cob){
  const listras=()=>{const cv=document.createElement("canvas");cv.width=64;cv.height=8;const c=cv.getContext("2d");c.fillStyle="#D3D0C8";c.fillRect(0,0,64,8);
   c.fillStyle="#A9A69E";for(let i=0;i<64;i+=8)c.fillRect(i,0,3,8);const t=new THREE.CanvasTexture(cv);t.wrapS=t.wrapT=THREE.RepeatWrapping;return t};
  A.cob.telhados.forEach(T=>{const [x0,z0]=T.p0,[x1,z1]=T.p1,baixoZ0=T.calha==="y0",y0=baixoZ0?T.zb:T.za,y1=baixoZ0?T.za:T.zb;
   const geo=new THREE.BufferGeometry();
   geo.setAttribute("position",new THREE.Float32BufferAttribute([x0,y0,z0,x1,y0,z0,x1,y1,z1,x0,y0,z0,x1,y1,z1,x0,y1,z1],3));
   geo.setAttribute("uv",new THREE.Float32BufferAttribute([0,0,1,0,1,1,0,0,1,1,0,1],2));geo.computeVertexNormals();
   const tx=listras();tx.repeat.set(Math.abs(x1-x0)/0.18,1);
   const me=new THREE.Mesh(geo,mat(T.cx?{map:tx,transparent:true,opacity:0.45,depthWrite:false}:{map:tx}));me.userData.cob=true;g.add(me);
   if(!T.cx){const zc=baixoZ0?z0:z1,cal=new THREE.Mesh(new THREE.BoxGeometry(Math.abs(x1-x0),0.12,0.25),mat({color:0x9AA0A6}));cal.position.set((x0+x1)/2,T.zb-0.05,zc);g.add(cal)}});
  if(A.cob.laje_res){const [p0,p1]=A.cob.laje_res;const lr=new THREE.Mesh(new THREE.BoxGeometry(Math.abs(p1[0]-p0[0]),0.15,Math.abs(p1[1]-p0[1])),mat({color:0xBDB9AF}));
   lr.position.set((p0[0]+p1[0])/2,A.cob.z_laje_res-0.075,(p0[1]+p1[1])/2);g.add(lr)}
  A.cob.reservatorios.forEach(([x,z,r])=>{const corp=new THREE.Mesh(new THREE.CylinderGeometry(r*0.94,r,A.cob.h_res,32),mat({color:0x2F6DB5}));
   corp.position.set(x,A.cob.z_laje_res+A.cob.h_res/2,z);g.add(corp);
   const tampa=new THREE.Mesh(new THREE.SphereGeometry(r*0.94,28,8,0,Math.PI*2,0,Math.PI/2),mat({color:0x2F6DB5}));tampa.scale.y=0.22;tampa.position.set(x,A.cob.z_laje_res+A.cob.h_res,z);g.add(tampa)});
 }
 andares.push({g,A,mats,ambs,paredes,pecas,grauteM,esq,escM,hidM,rotulos:null});
});

// ---------- estado e interface
const S={andar:-1,modo:"paredes",filt:{"estrutural":true,"vedação":true,"a definir":true,"concreto":true,"muro":false,"ext":true,"int":true,"laje":true,"cintas":false,"graute":true,"esq":true,"agua":false},explode:0,corte:false,alt:1.2,cortev:false,eixov:"x",posv:0.5,sel:null,metrica:"parede"};
const el=id=>document.getElementById(id);
function chips(id,itens,ativo,cb,cls=""){const r=el(id);r.innerHTML="";itens.forEach(([v,t,cor])=>{const b=document.createElement("button");b.className="chip "+cls;
 b.innerHTML=(cor!=null?`<i style="background:#${cor.toString(16).padStart(6,"0")}"></i>`:"")+esc(t);b.setAttribute("aria-pressed",ativo(v));b.onclick=()=>{cb(v);atualizar()};r.appendChild(b)})}
function ui(){
 chips("andares",[[-1,"Todos"],...D.andares.map((A,i)=>[i,A.nome.replace("Pavimento ","").replace("ºPavimento","º pav.")])],v=>v===S.andar,v=>{S.andar=v;S.sel=null;enquadrar(false)});
 chips("modos",[["paredes","Paredes"],["paginacao","Paginação (blocos)"],["ambientes","Ambientes"],...(D.orc?[["custo","Custo (B4)"]]:[]),...(D.hid?[["inst","Instalações"]]:[])],v=>v===S.modo,v=>{S.modo=v;if(S.sel)limparSel()});
 const fs=[["estrutural","Estrutural",COR_PAREDE["estrutural"]],["vedação","Vedação",COR_PAREDE["vedação"]],["a definir","A definir",COR_PAREDE["a definir"]],
  ["concreto","Pilares/concreto",COR_PAREDE["concreto"]],["muro","Muros",COR_PAREDE["muro"]],["ext","Externas"],["int","Internas"],["laje","Lajes"],["esq","Esquadrias",0x9CC8E8]];
 if(D.hid&&S.modo!=="inst")fs.push(["agua","Água fria",COR_DN[25]]);
 if(S.modo==="paginacao")fs.splice(5,0,["cintas","Destacar cintas, vergas e contravergas",0xF2B24C],["graute","Pontos de graute",0x1F4E8C]);
 chips("filtros",fs,v=>S.filt[v],v=>S.filt[v]=!S.filt[v],"f");
}
function atualizar(){
 ui();
 const ii=S.andar;
 andares.forEach((F,i)=>{const acima=ii>=0&&i>ii,abaixo=ii>=0&&i<ii;
  F.g.visible=!acima;F.g.position.y=F.A.z+i*S.explode;
  F.mats.forEach(m=>{const b=m.userData.op??1;m.transparent=abaixo||b<1;m.opacity=abaixo?0.12*b:b;m.depthWrite=!(abaixo||b<1)});
  const blocos=S.modo==="paginacao"&&F.pecas.length>0;
  F.paredes.forEach(me=>{const u=me.userData;me.visible=S.filt[u.tipoParede]!==false&&S.filt[u.fachada?"ext":"int"]
    &&!(blocos&&(u.tipoParede==="estrutural"||u.tipoParede==="vedação"));
   const fantasma=S.modo==="ambientes"||S.modo==="inst";
   me.material.transparent=abaixo||fantasma;me.material.opacity=abaixo?0.12:(S.modo==="inst"?0.07:(fantasma?0.18:1));me.material.depthWrite=!(abaixo||fantasma)});
  F.hidM.forEach(me=>{me.visible=S.modo==="inst"||S.filt.agua;me.material.transparent=abaixo;me.material.opacity=abaixo?0.25:1});
  F.pecas.forEach(me=>{const u=me.userData;me.visible=blocos&&S.filt[u.tipoParede]!==false&&S.filt[u.fachada?"ext":"int"];
   const apagado=S.filt.cintas&&u.cat==="blo";me.material.transparent=abaixo||apagado;me.material.opacity=abaixo?0.12:(apagado?0.1:1);me.material.depthWrite=!(abaixo||apagado)});
  F.grauteM.forEach(me=>{me.visible=blocos&&S.filt.graute&&S.filt.estrutural});
  F.esq.forEach(me=>{me.visible=S.filt.esq&&S.modo!=="ambientes"&&S.modo!=="inst"});
  F.ambs.forEach(me=>{me.material.color.setHex(S.modo==="ambientes"||me===S.sel?.obj?(me===S.sel?.obj?SEL:COR_AMB[me.userData.a.tipo]):0xE4E1D8)});
  F.g.children.forEach(c=>{if(c.userData.cob&&!abaixo){const t=S.modo==="inst";c.material.transparent=t||c.material.userData.op<1;c.material.opacity=t?0.12:(c.material.userData.op??1);c.material.depthWrite=!t}});
  F.g.children.forEach(c=>{if(c.userData.laje){c.visible=S.filt.laje;if(S.modo==="inst"&&!abaixo){c.material.transparent=true;c.material.opacity=0.3;c.material.depthWrite=false}
   else if(!abaixo){c.material.transparent=false;c.material.opacity=1;c.material.depthWrite=true}}});
 });
 // corte horizontal no andar selecionado (ou no térreo em "Todos")
 const ref=ii>=0?andares[ii]:andares.find(F=>/t[ée]rreo/i.test(F.A.nome))||andares[0];
 plano.constant=S.corte?ref.g.position.y+S.alt:1e6;
 // corte vertical: plano transversal (X) ou longitudinal (Z) numa posição do prédio
 if(S.cortev){const B=new THREE.Box3();andares.forEach(F=>{if(F.g.visible)B.expandByObject(F.g)});
  if(S.eixov==="x"){planoV.normal.set(-1,0,0);planoV.constant=B.min.x+S.posv*(B.max.x-B.min.x)}
  else{planoV.normal.set(0,0,-1);planoV.constant=B.min.z+S.posv*(B.max.z-B.min.z)}}
 else planoV.constant=1e6;
 pintar();rotulos();resumo();legenda();
}
function valorParede(A,p){if(!p.c)return null;if(S.metrica==="m2"){const ar=p.comp*(p.h||A.pd);return ar>0?p.c/ar:null}
 if(S.metrica==="andar")return A.custo||null;return p.c}
let ESCALA=[0,1];
function escala(){const vs=[];andares.forEach((F,i)=>{if(S.andar>=0&&i!==S.andar)return;F.A.paredes.forEach(p=>{const v=valorParede(F.A,p);if(v>0)vs.push(v)})});
 if(!vs.length)return [0,1];vs.sort((a,b)=>a-b);if(S.metrica==="andar")return [Math.min(...vs)*0.9,Math.max(...vs)];
 const q=f=>vs[Math.min(vs.length-1,Math.floor(f*(vs.length-1)))];return [q(0.02),q(0.98)]}
function corDe(u,ip){if(S.modo!=="custo")return u.base;const v=valorParede(u.A,u.A.paredes[ip]);if(!(v>0))return SEMCUSTO;
 const [a,b]=ESCALA;return rampa(b>a?(v-a)/(b-a):1)}
function pintar(){const key=S.modo+"|"+S.metrica+"|"+S.andar;if(key===S._pint)return;S._pint=key;if(S.modo==="custo")ESCALA=escala();
 andares.forEach(F=>F.paredes.forEach(me=>{const u=me.userData,c=me.geometry.attributes.color;
  Object.entries(u.faixas).forEach(([ip,[ini,n]])=>{const col=(S.sel&&S.sel.tipo==="par"&&S.sel.obj===me&&S.sel.ip===+ip)?SELRGB:corDe(u,+ip);
   for(let k=ini;k<ini+n;k++)c.setXYZ(k,col[0],col[1],col[2])});c.needsUpdate=true}))}
function rotulos(){
 andares.forEach(F=>{if(F.rotulos){F.g.remove(F.rotulos);F.rotulos=null}});
 if(S.andar<0)return;const F=andares[S.andar];const gr=new THREE.Group();
 F.A.ambientes.forEach(a=>{if(a.tipo==="técnico"&&a.nome!=="Elevador")return;
  const cv=document.createElement("canvas"),ctx=cv.getContext("2d"),t=a.nome,fs=44;ctx.font=`600 ${fs}px -apple-system,Segoe UI,Arial`;
  const w=Math.ceil(ctx.measureText(t).width)+28;cv.width=w;cv.height=fs+24;ctx.font=`600 ${fs}px -apple-system,Segoe UI,Arial`;
  ctx.fillStyle="rgba(255,255,255,.85)";ctx.beginPath();ctx.roundRect?ctx.roundRect(0,0,w,cv.height,14):ctx.rect(0,0,w,cv.height);ctx.fill();
  ctx.fillStyle="#1A1A1A";ctx.textBaseline="middle";ctx.fillText(t,14,cv.height/2+2);
  const sp=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(cv),depthTest:false,transparent:true}));
  const h=0.32;sp.scale.set(h*w/cv.height,h,1);sp.position.set(a.rot[0],F.A.pd*0.55,a.rot[1]);sp.renderOrder=10;gr.add(sp)});
 F.g.add(gr);F.rotulos=gr;
}
function resumoCusto(){
 const O=D.orc,ref=`SINAPI ${esc(O.mes)} ${esc(O.uf)}, ${O.deson?"com":"sem"} desoneração`;
 const lin=(k,v,b)=>`<tr><td class="k">${esc(k)}</td><td>${v}${b!=null?`<div class="bar" style="width:${Math.max(2,b*100).toFixed(1)}%"></div>`:""}</td></tr>`;
 if(S.andar>=0){const A=D.andares[S.andar],F=andares[S.andar],g={};
  [...A.paredes,...A.ambientes].forEach(x=>(x.cx||[]).forEach(([il,v])=>{const k=O.linhas[il][0];g[k]=(g[k]||0)+v}));
  const ar=O.areas[A.nome],gs=Object.entries(g).sort((a,b)=>b[1]-a[1]),mx=gs.length?gs[0][1]:1;
  return `<h3>${esc(A.nome)} · custo B4</h3><div class="big">${brl(A.custo)}</div><div class="mut">${ar?brl(A.custo/ar)+"/m² de área construída · ":""}${(100*A.custo/O.total).toLocaleString("pt-BR",{maximumFractionDigits:1})}% da obra</div><table style="margin-top:6px">`
   +gs.map(([k,v])=>lin(k,brl(v),v/mx)).join("")+"</table>"}
 const soma=D.andares.reduce((s,A)=>s+A.custo,0),mx=Math.max(...D.andares.map(A=>A.custo));
 let h=`<h3>Orçamento B4 · alvenaria e revestimentos</h3><div class="big">${brl(O.total)}</div><div class="mut">${ref} · ${brl(O.total/O.area)}/m² (${nf(O.area,0)} m² acima do subsolo)</div>`;
 if(O.cub)h+=`<div class="mut">CUB ${esc(O.cub.padrao)} ${esc(O.cub.mes)}: ${brl(O.cub.valor)}/m² · B4 = ${(100*O.total/O.cub.ref).toLocaleString("pt-BR",{maximumFractionDigits:1})}% do custo do prédio pelo CUB</div>`;
 h+=`<table style="margin-top:8px">`+O.grupos.map(([k,v])=>lin(k,brl(v))).join("")+`</table><h3 style="margin-top:10px">Por andar</h3><table>`
  +D.andares.filter(A=>A.custo>0).map(A=>lin(A.nome,brl(A.custo),A.custo/mx)).join("")+"</table>";
 const ok=Math.abs(soma-O.total)<1;
 h+=`<div class="mut" style="margin-top:6px">Soma dos elementos no modelo: ${brl(soma)} ${ok?"= total do orçamento ✓":"(difere do orçamento)"}</div>`;
 return h}
function resumoHid(){
 const H=D.hid,tot={},n={};let L0=0;
 const ok=t=>S.andar<0||t[2]===D.andares[S.andar].nome;
 H.trechos.forEach(t=>{if(!ok(t))return;tot[t[3]]=(tot[t[3]]||0)+t[4];n[t[3]]=(n[t[3]]||0)+1});
 H.curtos.forEach(t=>{if(S.andar>=0&&t[1]!==D.andares[S.andar].nome)return;tot[t[2]]=(tot[t[2]]||0)+t[3]});
 let sp=0;(H.sempos||[]).forEach(t=>{if(S.andar>=0&&t[1]!==D.andares[S.andar].nome)return;tot[t[2]]=(tot[t[2]]||0)+t[3];sp+=t[3]});
 const dns=Object.keys(tot).map(Number).sort((a,b)=>a-b),soma=dns.reduce((s,k)=>s+tot[k],0);
 let h=`<h3>Água fria · ${S.andar<0?"prédio":esc(D.andares[S.andar].nome)}</h3><div class="big">${nf(soma)} m de tubo</div><div class="mut">${esc(H.escopo)} · cada tubo uma vez (rótulo repetido no mesmo tubo conta uma vez)${sp>0?` · ${nf(sp)} m de verticais do barrilete/térreo entram só no quantitativo (sem posição no 3D)`:""}</div><table style="margin-top:6px">`;
 h+=dns.map(k=>`<tr><td class="k"><i style="display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;background:#${(COR_DN[k]||0).toString(16).padStart(6,"0")}"></i>DN${k}</td><td>${nf(tot[k])} m${S.andar<0&&H.tab[k]!=null?` <span class="mut">(tabela do projetista, prédio todo: ${nf(H.tab[k])} m)</span>`:""}</td></tr>`).join("")+"</table>";
 const cs={};D.andares.forEach((A,i)=>{if(!A.hid||(S.andar>=0&&i!==S.andar))return;A.hid.c.forEach(c=>{const k=String(c[3]).padStart(2,"0");cs[k]=(cs[k]||0)+1})});
 Object.entries(H.codpl||{}).forEach(([pav,c])=>{if(S.andar>=0&&pav!==D.andares[S.andar].nome)return;Object.entries(c).forEach(([k,n])=>{cs[k]=(cs[k]||0)+n})});
 if(S.andar<0&&H.orc)h+=`<h3 style="margin-top:10px">Custo SINAPI ${esc(H.orc.mes)} (custo direto)</h3><div class="big">${brl(H.orc.total)}</div><table>`+Object.entries(H.orc.grupos).map(([g,v])=>`<tr><td class="k">${esc(g)}</td><td>${brl(v)}</td></tr>`).join("")+"</table>";
 const ks=Object.keys(cs).sort();if(ks.length)h+=`<h3 style="margin-top:10px">Conexões e registros</h3><table>`+ks.map(k=>`<tr><td class="k">${esc(k)} · ${esc(H.cod[k]||"")}</td><td>${cs[k]}</td></tr>`).join("")+"</table>";
 return h}
function resumo(){
 if(S.modo==="custo"&&D.orc){el("resumo").innerHTML=resumoCusto();return}
 if(S.modo==="inst"&&D.hid){el("resumo").innerHTML=resumoHid();return}
 if(S.andar>=0){const A=D.andares[S.andar];el("resumo").innerHTML=`<h3>${esc(A.nome)} · pé-direito ${nf(A.pd)} m · nível ${nf(A.z)} m</h3><table>`+A.resumo.map(([k,v])=>`<tr><td class="k">${esc(k)}</td><td>${esc(v)}</td></tr>`).join("")+"</table>"}
 else el("resumo").innerHTML=`<h3>Obra · principais insumos (família 39)</h3><table>`+D.resumoObra.map(([k,v])=>`<tr><td class="k">${esc(k)}</td><td>${esc(v)}</td></tr>`).join("")+"</table>";
}
function legenda(){
 if(S.modo==="custo"){const [a,b]=ESCALA,u=S.metrica==="m2"?"/m²":"";
  el("legenda").innerHTML=`<h3>Mapa de calor do custo</h3><div class="ctl"><select id="metrica" aria-label="Métrica do mapa">
   <option value="parede">por parede (R$)</option><option value="m2">por m² de parede (R$/m²)</option><option value="andar">por andar (R$)</option></select></div>
   <div class="grad"></div><div class="esc"><span>${brl(a)}${u}</span><span>${brl(b)}${u}</span></div>
   <div style="margin-top:6px"><i style="display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:5px;vertical-align:-1px;background:rgb(${SEMCUSTO.map(x=>Math.round(x*255)).join(",")})"></i>sem custo na B4 (concreto, muros, subsolo)</div>
   <div class="mut" style="margin-top:6px">Clique numa parede ou num ambiente para ver de onde vem o custo. Escala do 2º ao 98º percentil.</div>`;
  const s=el("metrica");s.value=S.metrica;s.onchange=e=>{S.metrica=e.target.value;atualizar()};return}
 if(S.modo==="inst"){el("legenda").innerHTML="<h3>Legenda</h3>"+[...Object.entries(COR_DN).map(([k,c])=>["DN"+k,c]),["conexão",COR_CON],["registro",COR_REG]]
  .map(([t,c])=>`<span style="display:inline-flex;align-items:center;margin:0 10px 4px 0"><i style="display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:5px;background:#${c.toString(16).padStart(6,"0")}"></i>${esc(t)}</span>`).join("")
  +`<div class="mut" style="margin-top:6px">Posição: coluna pelo balão da planta, ramal ao longo da parede pela planta e alturas pelo isométrico de cada prumada (cotas de piso). Diâmetro do tubo engrossado para aparecer. Paredes em transparência.</div>`;return}
 const it=S.modo==="ambientes"?Object.entries(COR_AMB).map(([k,c])=>[NOME_AMB[k],c]):S.modo==="paginacao"?NOME_PECA:Object.entries(COR_PAREDE).map(([k,c])=>[k,c]);
 el("legenda").innerHTML="<h3>Legenda</h3>"+it.map(([t,c])=>`<span style="display:inline-flex;align-items:center;margin:0 10px 4px 0"><i style="display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:5px;background:#${c.toString(16).padStart(6,"0")}"></i>${esc(t)}</span>`).join("")
  +(S.modo==="paginacao"?'<div class="mut" style="margin-top:6px">Blocos do 1º ao 5º pavimento (família 39). Térreo e subsolo continuam como volume "a definir".</div>':"")
  +`<div class="mut" style="margin-top:6px">Arraste para girar, pinça/roda para zoom, dois dedos (ou botão direito) para mover.</div>`;
}
// ---------- seleção
function limparSel(){
 if(!S.sel)return;const s=S.sel;
 if(s.tipo==="par"){const u=s.obj.userData,[ini,n]=u.faixas[s.ip],c=s.obj.geometry.attributes.color,col=corDe(u,s.ip);for(let k=ini;k<ini+n;k++)c.setXYZ(k,...col);c.needsUpdate=true}
 if(s.tipo==="esc"){s.mat.color.setHex(s.mat.userData.base)}
 if(s.tipo==="hidsel"){s.hl.parent&&s.hl.parent.remove(s.hl);s.hl.material.dispose()}
 if(s.tipo==="lin"){s.F.pecas.forEach(me=>{const u=me.userData,col=new THREE.Color();for(let i=0;i<u.linha.length;i++)if(u.linha[i]===s.il){col.setRGB(u.base[i*3],u.base[i*3+1],u.base[i*3+2]);me.setColorAt(i,col)}me.instanceColor.needsUpdate=true})}
 S.sel=null;
}
function selecionar(hit){
 limparSel();
 const o=hit.object,u=o.userData;
 if(u.tipo==="par"){const ip=u.tri[hit.faceIndex];const p=u.A.paredes[ip];const [ini,n]=u.faixas[ip],c=o.geometry.attributes.color,y=new THREE.Color(SEL);
  for(let k=ini;k<ini+n;k++)c.setXYZ(k,y.r,y.g,y.b);c.needsUpdate=true;S.sel={tipo:"par",obj:o,ip};
  const vs=p.vaos.map(v=>`${v[0]} ${nf(v[2])}×${nf(v[4]-v[3])}`+(v[0]!=="porta"?` (peitoril ${nf(v[3])})`:"")).join("; ")||"—";
  el("info").innerHTML=`<h3>Parede · ${esc(u.A.nome)}</h3><div class="big">${esc(p.id)} · ${esc(p.tipo)}</div><div class="mut">${esc(p.motivo)}</div><table>
  <tr><td class="k">Comprimento (eixo)</td><td>${nf(p.comp)} m</td></tr><tr><td class="k">Espessura</td><td>${nf(p.t)} m</td></tr>
  <tr><td class="k">Altura</td><td>${nf(u.A.pd)} m · ${Math.round(u.A.pd/0.2)} fiadas</td></tr>
  <tr><td class="k">Fachada</td><td>${p.fachada?"sim (externa)":"não (interna)"}</td></tr><tr><td class="k">Encontros</td><td>${esc(p.enc.join(" / "))}</td></tr>
  <tr><td class="k">Lado A</td><td>${esc(p.la.join(", "))}</td></tr><tr><td class="k">Lado B</td><td>${esc(p.lb.join(", "))}</td></tr>
  <tr><td class="k">Vãos</td><td>${esc(vs)}</td></tr></table>`+blocoCusto(p,p.comp*(p.h||u.A.pd),"m² de parede",u.A);
 }else if(u.tipo==="pec"){const il=u.linha[hit.instanceId],F=andares.find(x=>x.A===u.A),L=u.A.pag.linhas[il],y=new THREE.Color(SEL);
  F.pecas.forEach(me=>{const v=me.userData;for(let i=0;i<v.linha.length;i++)if(v.linha[i]===il)me.setColorAt(i,y);me.instanceColor.needsUpdate=true});
  S.sel={tipo:"lin",F,il,obj:o};
  const nomes=[["14×19×39","inteiro 14×19×39"],["14×19×19","meio 14×19×19"],["14×19×34","amarração L 14×19×34"],["14×19×54","amarração T 14×19×54"],
   ["canaleta J 14×19×39","canaleta J"],["meia canaleta J 14×19×19","meia canaleta J"],["canaleta U 14×19×39","canaleta U"],["meia canaleta U 14×19×19","meia canaleta U"],
   ["9×19×39","inteiro 9×19×39"],["9×19×19","meio 9×19×19"],["canaleta U 9×19×39","canaleta U 9"],["meia canaleta U 9×19×19","meia canaleta U 9"],
   ["cortes (peças)","cortes/compensadores"],["cinta de respaldo (m)","cinta de respaldo (m)"],["vergas (m)","vergas (m)"],["contravergas (m)","contravergas (m)"]];
  const linhas=nomes.filter(([k])=>L.cont[k]).map(([k,t])=>`<tr><td class="k">${esc(t)}</td><td>${nf(L.cont[k],k.includes("(m)")?2:0)}</td></tr>`).join("");
  el("info").innerHTML=`<h3>Parede (paginação) · ${esc(u.A.nome)}</h3><div class="big">${esc(L.id)} · ${esc(L.tipo)}</div>
  <div class="mut">${nf(L.comp/100)} m pelo eixo · ${L.f.length} fiadas · pontas ${esc(L.pontas.join(" / "))}${L.nseg>1?` · ${L.nseg} trechos colineares`:""}${L.fachada?" · fachada":""}</div>
  <table style="margin-top:6px">${linhas}</table><div style="margin-top:8px;overflow-x:auto">${elevacao(L)}</div>`;
 }else if(u.tipo==="esc"){const E=u.E;u.mat.color.setHex(SEL);S.sel={tipo:"esc",obj:o,mat:u.mat};
  const bl=(2*E.h+E.piso)*100,pt=E.patamares.map(([k])=>`${k}º espelho (+${nf(k*E.h)} m)`).join(", ")||"—",an=E.anot||{};
  el("info").innerHTML=`<h3>Escada · ${esc(u.A.nome)}</h3><div class="big">${esc(E.ambiente)}</div><div class="mut">sobe para ${esc(E.destino||"—")} · ${E.lances} lances</div><table>
  <tr><td class="k">Desnível (cortes)</td><td>${nf(E.dz)} m</td></tr><tr><td class="k">Espelhos</td><td>${E.N} × ${nf(E.h*100,1)} cm</td></tr>
  <tr><td class="k">Piso (pisada)</td><td>${nf(E.piso*100,0)} cm</td></tr><tr><td class="k">Largura do lance</td><td>${nf(E.largura)} m</td></tr>
  <tr><td class="k">Patamar</td><td>${esc(pt)}</td></tr><tr><td class="k">Blondel (2e + p)</td><td>${nf(bl,1)} cm</td></tr>
  ${an.espelho_m?`<tr><td class="k">Anotado na planta</td><td>e = ${nf(an.espelho_m*100,0)} cm${an.piso_m?` · p = ${nf(an.piso_m*100,0)} cm`:""}${an.largura_m?` · L = ${nf(an.largura_m)} m`:""}</td></tr>`:""}</table>
  <div class="mut" style="margin-top:6px">Espelho calculado pelo desnível dos cortes ÷ nº de espelhos.${an.espelho_m&&Math.abs(an.espelho_m*E.N-E.dz)>0.03?` A planta anota ${nf(an.espelho_m*100,0)} cm (${E.N} × ${nf(an.espelho_m*100,0)} = ${nf(an.espelho_m*E.N)} m), diferente do corte: conferir com o arquiteto.`:""}
  ${bl<63||bl>64?` NBR 9077 pede 63 a 64 cm na fórmula de Blondel e espelho de 16 a 18 cm: conferir.`:""}</div>`;
 }else if(u.tipo==="hid"||u.tipo==="con"){const M=new THREE.Matrix4();o.getMatrixAt(hit.instanceId,M);
  const hl=new THREE.Mesh(o.geometry,new THREE.MeshBasicMaterial({color:SEL,depthTest:false,transparent:true,opacity:0.9}));
  const p=new THREE.Vector3(),q=new THREE.Quaternion(),e=new THREE.Vector3();M.decompose(p,q,e);
  if(u.tipo==="hid")e.set(e.x*1.7,e.y,e.z*1.7);else e.multiplyScalar(1.5);hl.position.copy(p);hl.quaternion.copy(q);hl.scale.copy(e);hl.renderOrder=20;
  o.parent.add(hl);S.sel={tipo:"hidsel",obj:o,hl};
  if(u.tipo==="hid"){const T=D.hid.trechos[u.ids[hit.instanceId]];const [id,col,pav,dn,L,orig,eixo,como]=T;
   el("info").innerHTML=`<h3>Água fria · ${esc(pav)}</h3><div class="big">Tubo DN${dn} · ${nf(L)} m</div><div class="mut">${esc(id)} · coluna ${esc(col)} · ${eixo==="v"?"vertical":"horizontal"}</div><table>
   <tr><td class="k">Diâmetro</td><td>DN${dn} mm (PVC soldável marrom)</td></tr><tr><td class="k">Comprimento</td><td>${nf(L)} m (rótulo do projeto)</td></tr>
   ${(()=>{const r=u.A.hid.t.find(x=>x[7]===u.ids[hit.instanceId]);if(!r)return "";const a=Math.min(r[1],r[4]),b=Math.max(r[1],r[4]);
    return `<tr><td class="k">Altura do piso</td><td>${Math.abs(b-a)<0.01?nf(a):nf(a)+" a "+nf(b)} m</td></tr>`})()}
   <tr><td class="k">Fonte</td><td>${esc(orig)}</td></tr><tr><td class="k">Rótulo ligado por</td><td>${como==="chamada"?"linha de chamada":como==="perto"?"proximidade":esc(como)}</td></tr>
   ${D.hid.orc&&D.hid.orc.custo[id]!=null?`<tr><td class="k">Custo (SINAPI ${esc(D.hid.orc.mes)})</td><td>${brl(D.hid.orc.custo[id])} (tubo instalado)</td></tr>`:""}</table>`}
  else{const c=u.arr[hit.instanceId],k=String(c[3]).padStart(2,"0");
   el("info").innerHTML=`<h3>Água fria · ${esc(u.A.nome)}</h3><div class="big">${c[3]>=70?"Registro":"Conexão"} ${esc(k)}</div><div class="mut">coluna ${esc(c[4])}</div><table>
   <tr><td class="k">Peça (tabela do projeto)</td><td>${esc(D.hid.cod[k]||"—")}</td></tr><tr><td class="k">Altura</td><td>${nf(c[1])} m do piso</td></tr></table>`}
 }else if(u.tipo==="amb"){const a=u.a;S.sel={tipo:"amb",obj:o};
  el("info").innerHTML=`<h3>Ambiente · ${esc(u.A.nome)}</h3><div class="big">${esc(a.nome)}</div><div class="mut">${esc(a.unidade||NOME_AMB[a.tipo]||"")}</div><table>
  <tr><td class="k">Área medida</td><td>${nf(a.area)} m² (rótulo ${nf(a.rotulo)} m², ${a.dif==null?"—":(a.dif>0?"+":"")+nf(a.dif,1)+"%"})</td></tr>
  ${a.piso&&Math.abs(a.piso-a.area)>0.01?`<tr><td class="k">Piso total</td><td>${nf(a.piso)} m²</td></tr>`:""}
  <tr><td class="k">Perímetro</td><td>${nf(a.perim)} m</td></tr><tr><td class="k">Teto</td><td>${nf(a.teto)} m²</td></tr>
  <tr><td class="k">Rodapé</td><td>${nf(a.rodape)} m</td></tr><tr><td class="k">Parede líquida</td><td>${nf(a.parede)} m²</td></tr>
  <tr><td class="k">Portas / janelas</td><td>${a.portas??"—"} / ${a.janelas??"—"}</td></tr><tr><td class="k">Acabamento</td><td>${esc(a.acab)}</td></tr></table>`
  +(a.obs?`<div class="mut" style="margin-top:6px">${esc(a.obs)}</div>`:"")+blocoCusto(a,a.teto,"m² de teto",u.A);
 }
 if(window.innerWidth<=760)el("painel").classList.remove("min");
 atualizar();
}
function blocoCusto(x,area,unid,A){
 if(!D.orc||!x.c)return "";const O=D.orc;
 const it=(x.cx||[]).slice(0,10).map(([il,v])=>{const L=O.linhas[il];return `<tr><td class="k">${esc(L[1])}<div class="mut" style="font-size:11px">${esc(L[0])}</div></td><td>${brl(v)}</td></tr>`}).join("");
 return `<h3 style="margin-top:12px">Custo (B4)</h3><div class="big">${brl(x.c)}</div><div class="mut">${area>0?brl(x.c/area)+"/"+esc(unid)+" · ":""}${A.custo?(100*x.c/A.custo).toLocaleString("pt-BR",{maximumFractionDigits:1})+"% do andar":""}</div>
  <table style="margin-top:4px">${it}</table>${(x.cx||[]).length>10?`<div class="mut">+ ${x.cx.length-10} itens menores</div>`:""}`}
function elevacao(L){
 const n=L.f.length,H=20;let x0=0,x1=L.comp;L.f.forEach(f=>f.forEach(([u,w])=>{x0=Math.min(x0,u);x1=Math.max(x1,u+w)}));
 const esc_=Math.max(0.35,Math.min(1.4,290/(x1-x0))),W=(x1-x0)*esc_+4,Ht=n*H*esc_+4;
 const cor={0:"#D9D6CC",1:"#B4AE9E",2:"#8E7CC3",3:"#E08A1E",4:"#F2B24C",5:"#262626",6:"#8F8A80"},corV={0:"#B9CFE4",1:"#8EAFCF",3:"#E08A1E",4:"#F2B24C",5:"#262626",6:"#8F8A80"};
 let r="";L.f.forEach((f,k)=>{const y=Ht-2-(k+1)*H*esc_;f.forEach(([u,w,c])=>{const x=2+(u-x0)*esc_;
  r+=c===8?`<rect x="${x+0.3}" y="${y+0.3}" width="${Math.max(w*esc_-0.6,0.3)}" height="${H*esc_-0.6}" fill="#E4E1D8"><title>parede que cruza</title></rect>`
   :c===9?`<rect x="${x}" y="${y}" width="${w*esc_}" height="${H*esc_}" fill="none" stroke="#999" stroke-dasharray="2 2"/>`
   :`<rect x="${x+0.3}" y="${y+0.3}" width="${Math.max(w*esc_-0.6,0.3)}" height="${H*esc_-0.6}" fill="${(L.tipo==="vedação"?corV:cor)[c]||"#ccc"}"/>`})});
 return `<svg width="${W}" height="${Ht}" viewBox="0 0 ${W} ${Ht}" style="display:block;background:#fff;border-radius:6px">${r}</svg>`;
}
const ray=new THREE.Raycaster(),ptr=new THREE.Vector2();let down=null;
canvas.addEventListener("pointerdown",e=>{down=[e.clientX,e.clientY]});
canvas.addEventListener("pointerup",e=>{if(!down||Math.hypot(e.clientX-down[0],e.clientY-down[1])>6)return;
 const r=canvas.getBoundingClientRect();ptr.set((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1);ray.setFromCamera(ptr,camera);
 const alvo=pick.filter(o=>{let p=o;while(p){if(!p.visible)return false;p=p.parent}const ia=o.parent.userData.ia;
  if(S.andar>=0&&ia!==S.andar)return false;if(o.userData.tipo==="par"&&(S.modo==="ambientes"||S.modo==="inst"))return false;
  if(S.modo==="inst"&&(o.userData.tipo==="amb"||o.userData.tipo==="esc"))return false;
  if(o.userData.tipo==="pec"&&S.filt.cintas&&o.userData.cat==="blo")return false;return true});
 const hs=ray.intersectObjects(alvo,false).filter(h=>(!S.corte||h.point.y<=plano.constant+1e-3)&&planoV.distanceToPoint(h.point)>=-1e-3);
 if(hs.length)selecionar(hs[0]);else{limparSel();el("info").innerHTML='<h3>Seleção</h3><div class="mut">Toque ou clique num ambiente, numa parede ou num tubo.</div>';atualizar()}});
// ---------- câmera
function caixaVisivel(){const b=new THREE.Box3();andares.forEach((F,i)=>{if(S.andar<0||i===S.andar)b.expandByObject(F.g)});return b}
function enquadrar(anim,vista="iso"){
 // distância para a esfera envolvente caber no menor campo de visão (vale para tela em pé ou deitada)
 const b=caixaVisivel(),c=b.getCenter(new THREE.Vector3()),R=b.getBoundingSphere(new THREE.Sphere()).radius;
 const vf=THREE.MathUtils.degToRad(camera.fov),hf=2*Math.atan(Math.tan(vf/2)*camera.aspect),dist=R/Math.sin(Math.min(vf,hf)/2)*1.02;
 const dir={iso:[0.62,0.55,0.68],planta:[0,1,0.0001],cima:[0,0.22,-1],baixo:[0,0.22,1],esq:[-1,0.22,0],dir:[1,0.22,0]}[vista];
 const v=new THREE.Vector3(...dir).normalize().multiplyScalar(dist);
 camera.position.copy(c).add(v);controls.target.copy(c);camera.near=Math.max(0.05,dist/500);camera.far=dist*10;camera.updateProjectionMatrix();controls.update();
}
el("cams").innerHTML="";[["iso","Isométrica"],["planta","Planta"],["cima","Lado de cima"],["baixo","Lado de baixo"],["esq","Lado esquerdo"],["dir","Lado direito"]].forEach(([v,t])=>{
 const b=document.createElement("button");b.className="chip";b.textContent=t;b.title="Lados como na planta 2D";b.onclick=()=>enquadrar(false,v);el("cams").appendChild(b)});
el("explode").oninput=e=>{S.explode=+e.target.value;atualizar()};
el("corte").onchange=e=>{S.corte=e.target.checked;el("altcorte").disabled=!S.corte;atualizar()};
el("cortev").onchange=e=>{S.cortev=e.target.checked;el("eixov").disabled=el("posv").disabled=!S.cortev;atualizar()};
el("eixov").onchange=e=>{S.eixov=e.target.value;atualizar()};
el("posv").oninput=e=>{S.posv=+e.target.value;atualizar()};
el("altcorte").oninput=e=>{S.alt=+e.target.value;el("altv").textContent=nf(S.alt)+" m";atualizar()};
el("handle").onclick=()=>el("painel").classList.toggle("min");
function redim(){const w=window.innerWidth,h=window.innerHeight;renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix()}
window.addEventListener("resize",redim);
matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change",()=>{scene.background=new THREE.Color(corFundo())});
if(window.innerWidth<=760)el("painel").classList.add("min");
redim();atualizar();enquadrar(false);
(function loop(){requestAnimationFrame(loop);controls.update();renderer.render(scene,camera)})();
</script></body></html>"""
