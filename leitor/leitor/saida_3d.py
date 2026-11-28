"""Visualizador 3D (three.js) — etapa 3D-1: andares, ambientes clicáveis, paredes por tipo com vãos.

Gera um HTML único (three.js embutido, sem internet). Coordenadas da cena em metros:
X = direita da planta, Z = para baixo na planta, Y = para cima. Cada andar é alinhado pelo centro do
elevador (o mesmo em todos os pavimentos) e posto na altura lida dos cortes.
"""
from __future__ import annotations

import html
import json
import math
import re
import unicodedata
from collections import Counter
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
                    [*cvh(*t["a"][:2]), t["a"][2], *cvh(*t["b"][:2]), t["b"][2], t["dn"], i, 0])
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
                hid_por_pav.setdefault(t["pav"], {"t": [], "c": []})["t"].append([*cv(*t["a"][:2]), t["a"][2], *cv(*t["b"][:2]), t["b"][2], t["dn"], len(lista) - 1, 0])
            colxy = {c["id"]: c["xy"] for c in hid["colunas"]}
            usados_ = set()
            longas = sorted((t for t in comp if t.get("como") == "coluna"), key=lambda t: (-t["dn"], -t["L"]))
            topo_res = hid["niveis"]["Cobertura"] + 1.35 + 1.60
            alvo = [("AL", 32, topo_res), ("EXTRAV.", 32, topo_res), ("AF-13", 25, hid["niveis"]["Cobertura"] + 0.10)]
            niv = sorted(hid["niveis"].items(), key=lambda kv: kv[1])
            usados_ = set()                              # sem marcar os dados (montar pode rodar mais de uma vez)
            for nome, dn, topo in alvo:
                t = next((x for x in longas if x["dn"] == dn and id(x) not in usados_), None)
                if not t or nome not in colxy:
                    continue
                usados_.add(id(t))
                base = max(topo - t["L"], hid["niveis"].get("Sub-Solo", -2.75) + 0.20)
                lista.append([nome, nome, "prédio", t["dn"], t["L"], t["origem"], "v", "coluna: posição pelo balão das plantas, extremos por premissa"])
                x, y = cvh(*colxy[nome])
                for k, (pav, zf) in enumerate(niv):
                    z1 = niv[k + 1][1] if k + 1 < len(niv) else 1e9
                    a_, b_ = max(base, zf), min(topo, z1)
                    if b_ - a_ > 0.01:
                        hid_por_pav.setdefault(pav, {"t": [], "c": []})["t"].append([x, y, _r(a_), x, y, _r(b_), t["dn"], len(lista) - 1, 0])
            tab = hid.get("tabela_projetista") or {}
            cod = {k: v[0]["descricao"] for k, v in {**tab.get("conexoes", {}), **tab.get("registros", {})}.items() if v}
            hid_out = {"trechos": lista, "cod": cod, "tab": {str(k): v for k, v in (tab.get("tubos") or {}).items()},
                       "curtos": [[t["col"], t["pav"], t["dn"], t["L"]] for t in hid.get("curtos", [])],
                       "colunas": [[c["id"], *cvh(*c["xy"])] for c in hid["colunas"]], "pdf": hid.get("pdf"),
                       "escopo": "prumadas dos apartamentos, barrilete, térreo, subsolo e colunas do prédio",
                       "sempos": [[t["grupo"], t["pav"], t["dn"], t["L"], t["origem"]] for t in comp if not t.get("a") and id(t) not in usados_],
                       "codpl": (hid.get("complemento") or {}).get("codigos_plantas") or {},
                       "orc": hid.get("orcamento") and {"total": hid["orcamento"]["total"], "grupos": hid["orcamento"]["grupos"],
                                                        "mes": hid["orcamento"]["mes"], "custo": hid["orcamento"]["por_trecho"]}}
    es_h = (dados.get("hidraulica") or {}).get("esgoto")
    if es_h:
        from .esgoto import Z_RAMAL
        v1 = next((v for v in dados["vistas"] if v["titulo"] == "1ºPavimento"), None)
        el1 = v1 and next((a for a in dados["ambientes"] if a["vista"] == v1["id"] and a["nome"] == "Elevador" and a["poligono"]), None)
        if el1:
            m1, c1 = v1["m_por_pt"], Polygon(el1["poligono"]).centroid
            cve = lambda x, y: (_r(x * m1 - c1.x * m1), _r(y * m1 - c1.y * m1))
            convs_e = {}
            for v in dados["vistas"]:
                elv = next((a for a in dados["ambientes"] if a["vista"] == v["id"] and a["nome"] == "Elevador" and a["poligono"]), None)
                if elv:
                    cc, mm = Polygon(elv["poligono"]).centroid, v["m_por_pt"]
                    convs_e[v["id"]] = (lambda cc, mm: (lambda x, y: (_r(x * mm - cc.x * mm), _r(y * mm - cc.y * mm))))(cc, mm)
            if hid_out is None:
                hid_out = {"trechos": [], "cod": {}, "tab": {}, "curtos": [], "colunas": [], "pdf": None, "escopo": "", "sempos": [],
                           "codpl": {}, "orc": None}
            lista = hid_out["trechos"]
            niv = es_h["niveis"]
            for n, r in enumerate(es_h["ramais"], 1):
                zr = niv[r["pav"]] + Z_RAMAL
                lista.append([f"ES-{r['pav'][:2]}-{n:03d}", "ramal", r["pav"], r["dn"], r["L_desenho"],
                              f"planta {r['pav']}: posição e DN pela espessura do traço ({r['esp_m'] * 1000:.0f} mm)", "h",
                              "esgoto (quantitativo pelos isométricos; altura por premissa: sob a laje)", "es"])
                hid_por_pav.setdefault(r["pav"], {"t": [], "c": []})["t"].append(
                    [*cve(*r["a"]), round(zr, 3), *cve(*r["b"]), round(zr, 3), r["dn"], len(lista) - 1, 1])
            for n, e in enumerate(es_h.get("extras_3d", []), 1):
                lista.append([f"ES-{e['pav'][:2]}-x{n:03d}", "ramal", e["pav"], e["dn"],
                              round(abs(e["zb"] - e["za"]) + math.dist(e["a"], e["b"]) * m1, 2),
                              f"{e['papel']} (posição pela planta; altura por premissa)", "v" if e["a"] == e["b"] else "h",
                              "esgoto: peça do 3D (o quantitativo vem dos isométricos)", "es"])
                hid_por_pav.setdefault(e["pav"], {"t": [], "c": []})["t"].append(
                    [*cve(*e["a"]), round(e["za"], 3), *cve(*e["b"]), round(e["zb"], 3), e["dn"], len(lista) - 1, 1])
            for q in es_h.get("pecas_3d", []):
                hid_por_pav.setdefault(q["pav"], {"t": [], "c": []}).setdefault("p", []).append(
                    [*cve(*q["xy"]), round(q["z"], 3), (2 if q.get("forma") == "redonda" else 1) if q["tipo"] == "caixa" else 0,
                     q.get("lado") or 0, q.get("dn") or 0])
            ordem = sorted(niv.items(), key=lambda kv: kv[1])
            for c in es_h["colunas"]:
                dn = int(str(c.get("diametro") or "ø100").replace("ø", "") or 100)
                topo = niv["Cobertura"] + 0.30
                base = niv["Pavimento Térreo"] + (-0.40 if c["id"].startswith("TQ") else 0) if c["id"].startswith("TQ") else niv["1ºPavimento"] + Z_RAMAL
                lista.append([c["id"], c["id"], "prédio", dn, round(topo - base, 2), "balão da coluna nas plantas (posição); extremos por premissa", "v",
                              "tubo de queda" if c["id"].startswith("TQ") else "ventilação", "es"])
                x, y = cve(*c["xy"])
                for k, (pav, zf) in enumerate(ordem):
                    z1 = ordem[k + 1][1] if k + 1 < len(ordem) else 1e9
                    a_, b_ = max(base, zf), min(topo, z1)
                    if b_ - a_ > 0.01:
                        hid_por_pav.setdefault(pav, {"t": [], "c": []})["t"].append([x, y, _r(a_), x, y, _r(b_), dn, len(lista) - 1, 1])
            for n, t in enumerate(es_h["coletores"], 1):
                if not t.get("a"):
                    continue
                cv = convs_e.get(t.get("vista"), cve)
                lista.append([f"COL-{n:03d}", "coletor", t["pav"], t["dn"], t["L"], t["origem"], "h", "esgoto: altura por premissa", "es"])
                hid_por_pav.setdefault(t["pav"], {"t": [], "c": []})["t"].append(
                    [*cv(*t["a"][:2]), t["a"][2], *cv(*t["b"][:2]), t["b"][2], t["dn"], len(lista) - 1, 1])
            tot = {}
            for t in es_h["apartamentos"] + es_h["coletores"]:
                tot[t["dn"]] = tot.get(t["dn"], 0) + t["L"]
            o = es_h.get("orcamento")
            hid_out["es"] = {"tot": {str(k): _r(v, 2) for k, v in sorted(tot.items())},
                             "tab": {str(k): v for k, v in ((es_h.get("tabela_projetista") or {}).get("tubos") or {}).items()},
                             "orc": o and {"total": o["total"], "grupos": o["grupos"], "mes": o["mes"]}, "pdf": es_h["pdf"],
                             "con": sum(es_h["conexoes"].values())}
    # costura do 3D: liga as pontas soltas (só visual)
    if hid_out and hid_por_pav:
        from .rede3d import costurar
        pontos_uso = [(c[0], c[1], c[2]) for v in hid_por_pav.values() for c in v.get("c", []) if c[3] in (9, 10)]
        lst = hid_out["trechos"]

        def terminal(sy, r, e):
            P = (r[3 * e], r[3 * e + 1], r[3 * e + 2])
            outra_z = r[3 * (1 - e) + 2]
            ref = lst[r[7]]
            if sy == 0:
                if any(math.dist(P, q) < 0.06 for q in pontos_uso):
                    return True
                return ref[0] in ("AL", "EXTRAV.") and P[2] > outra_z          # topo no reservatório
            if "subida" in (ref[5] or "") and P[2] > outra_z:                    # sobe ao aparelho
                return True
            return str(ref[1]).startswith(("TQ", "V")) and P[2] > outra_z        # ventilação acima do telhado
        hid_out["costura"] = costurar(hid_por_pav, lst, terminal)
    # elétrica: a rede 3D já vem em coordenadas do modelo (m, origem no centro do elevador, z absoluto) e ligada
    # ponta a ponta (eletroduto -> descida -> caixa; prumadas de caixa a caixa)
    ele = dados.get("eletrica")
    ele_out, ele_por_pav = None, {}
    if ele and ele.get("rede3d"):
        r3 = ele["rede3d"]
        origens = list(dict.fromkeys(t[5] for t in r3["trechos"]))
        oi = {o: i for i, o in enumerate(origens)}
        ele_por_pav = r3["por_pav"]
        tot, tab = Counter(), Counter()
        for t in r3["trechos"]:
            tot[t[3]] += t[4]
        for itens in ele["listas"].values():
            for x in itens:
                if (x["grupo"] or "").startswith("Eletroduto"):
                    tab[x["item"].rstrip('"').strip()] += x["qtd"]
        o = ele.get("orcamento")
        ele_out = {"trechos": [[t[0], t[1], t[2], t[3], t[4], oi[t[5]], t[6], t[7], t[9] if len(t) > 9 else ""] for t in r3["trechos"]], "origens": origens,
                   "pontos": r3["pontos"], "diams": r3["diams"], "tipos": r3["tipos"], "pdf": ele.get("pdf"),
                   "tot": {k: _r(v, 2) for k, v in tot.items()}, "tab": {k: _r(v, 2) for k, v in tab.items()},
                   "orc": o and {"total": o["total"], "grupos": o["grupos"], "mes": o["mes"]}}
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
            hid_andar = {"t": [[a, _r(c - zz), b, d, _r(f - zz), e, dn, i, *sy] for a, b, c, d, e, f, dn, i, *sy in hp["t"]],
                         "c": [[a, _r(c - zz), b, k, col] for a, b, c, k, col in hp["c"]],
                         "p": [[a, _r(c - zz), b, tp, lado, dn] for a, b, c, tp, lado, dn in hp.get("p", [])]}
            tot = {}
            for x in hp["t"]:
                if (x[8] if len(x) > 8 else 0) == 0 and hid_out["trechos"][x[7]][1] != "ligação":
                    tot[x[6]] = tot.get(x[6], 0) + hid_out["trechos"][x[7]][4] * (1 if hid_out["trechos"][x[7]][2] != "prédio" else 0)
            if tot:
                resumo.append(["Água fria (tubos com posição)", " · ".join(f"DN{k} {val:,.2f} m" for k, val in sorted(tot.items()))])
        ep = ele_por_pav.get(v["titulo"])
        ele_andar = None
        if ep:
            zz = z[v["titulo"]]
            # [x, altura acima do piso do andar, profundidade] como o three.js (y para cima)
            r2 = lambda v: round(float(v), 2)                # centímetro basta para desenhar (a página fica leve)
            ele_andar = {"t": [[r2(a), r2(c - zz), r2(b), r2(d), r2(f - zz), r2(e), dm, i] for a, b, c, d, e, f, dm, i in ep["t"]],
                         "p": [[r2(a), r2(c - zz), r2(b), k, i] for a, b, c, k, i in ep["p"]]}
        andares.append({"id": v["id"], "nome": v["titulo"], "ordem": ordem, "z": _r(z[v["titulo"]], 2), "pd": pdv, "pag": pag, "hid": hid_andar,
                        "ele": ele_andar,
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
                hid_cob = {"t": [[a, _r(c - zc), b, d, _r(f - zc), e, dn, i, *sy] for a, b, c, d, e, f, dn, i, *sy in hpc["t"]],
                           "c": [[a, _r(c - zc), b, k, col] for a, b, c, k, col in hpc["c"]]}
                tot = {}
                for x in hpc["t"]:
                    if hid_out["trechos"][x[7]][2] != "prédio" and (x[8] if len(x) > 8 else 0) == 0 and hid_out["trechos"][x[7]][1] != "ligação":
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
            "orc": orc3d, "hid": hid_out, "ele": ele_out}


WEB = Path(__file__).parent / "web"


def _fmt(v, n=0):
    return f"{v:,.{n}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pranchas(nome):
    import re
    m = re.search(r"(\d+)_a_(\d+)", nome or "")
    return f"{m.group(1)} a {m.group(2)}" if m else None


# grupos da conferência -> disciplina (cor do material)
DISC_CONF = {"Água fria": "var(--m-af)", "Esgoto": "var(--m-es)", "Elétrica": "var(--m-ele)", "Geometria": "var(--m-cinza)", "Pavimentos repetidos": "var(--m-cinza)",
             "Paginação": "var(--m-cinza)"}
COR_GRUPO = [("estrutural", "var(--m-est)", "Alvenaria estrutural"), ("vedação", "var(--m-ved)", "Vedação"),
             ("graute", "var(--m-conc)", "Graute e armação"), ("armação", "var(--m-conc)", "Graute e armação"),
             ("revestimento", "var(--m-rev)", "Revestimentos")]


def painel(dados: dict, conf: list) -> dict:
    """Dados das telas da página da obra (visão geral, quantitativos, orçamento, conferência, documentos)."""
    from collections import Counter
    orc = dados.get("orcamento")
    hid = dados.get("hidraulica") or {}
    af, es = hid.get("agua_fria"), hid.get("esgoto")
    vistas_amb = {a["vista"] for a in dados["ambientes"]}
    titulos = [v["titulo"] for v in dados["vistas"] if v["id"] in vistas_amb]
    n_tipo = sum(1 for t in titulos if "ºPavimento" in t)
    partes = (["subsolo"] if any("sub" in t.lower() for t in titulos) else []) + (["térreo"] if any("rreo" in t for t in titulos) else []) \
        + ([f"{n_tipo} pavimentos-tipo"] if n_tipo else []) + (["cobertura"] if dados.get("cobertura_pdf") else [])
    escopo = (", ".join(partes[:-1]) + " e " + partes[-1] if len(partes) > 1 else "".join(partes)).capitalize()
    unid = len({(a["vista"], a["unidade"]) for a in dados["ambientes"] if a.get("unidade")})
    area = (orc or {}).get("area_total") or sum(a["area_m2"] or 0 for a in dados["ambientes"])
    ger = dados.get("gerado_em", "")[:10]
    ger = f"{ger[8:10]}/{ger[5:7]}/{ger[:4]}" if len(ger) == 10 else ger
    sinapi = f"SINAPI {orc['mes']} · {orc['uf']} · {'com' if orc['premissas']['desonerado'] else 'sem'} desoneração" if orc else "sem orçamento"
    # conferência por disciplina
    def disc_de(g):
        return DISC_CONF.get(g, "var(--m-arq)")
    conf_l = [[g, disc_de(g), item, res, bool(ok)] for g, item, res, ok in conf]
    def conta(cor):
        x = [c for c in conf_l if c[1] == cor]
        return [sum(1 for c in x if c[4]), len(x)] if x else None
    # totais
    t_b4 = orc["total"] if orc else 0
    t_af = (af or {}).get("orcamento", {}).get("total", 0) if af else 0
    t_es = (es or {}).get("orcamento", {}).get("total", 0) if es else 0
    ele = dados.get("eletrica")
    o_el = (ele or {}).get("orcamento")
    t_el = (o_el or {}).get("total", 0)
    total = t_b4 + t_af + t_es + t_el
    ins = dados.get("insumos") or {}
    q_ins = lambda L: L[4] * L[6] * (1 + L[8])
    blocos = sum(q_ins(L) for L in ins.get("linhas", []) if L[1].startswith(("Bloco 14", "Bloco 9")))
    n_ok = sum(1 for c in conf_l if c[4])
    feitas = [x for x, v in (("parte cinza", t_b4), ("hidráulica", t_af + t_es), ("elétrica", t_el)) if v]
    kpis = [["Custo medido", "R$ " + _fmt(total), (", ".join(feitas[:-1]) + " e " + feitas[-1]) if len(feitas) > 1 else "".join(feitas)],
            ["Por m² construído", "R$ " + _fmt(total / area, 2) if area else "—", f"{_fmt(area, 2)} m²"]]
    cub = (orc or {}).get("cub")
    if cub:
        kpis.append(["Do custo de referência", f"{100 * total / cub['custo_ref']:.1f}%".replace(".", ","), f"CUB {cub['padrao']} · R$ {_fmt(cub['custo_ref'] / 1e6, 2)} mi"])
    kpis.append(["Conferência", f"{n_ok} de {len(conf_l)}", "tudo conferido" if n_ok == len(conf_l) else
                 f"{len(conf_l) - n_ok} ponto{'s' if len(conf_l) - n_ok > 1 else ''} para conferir"])
    disc = [{"n": "Arquitetura", "cor": "var(--m-arq)", "orc": None, "conf": conta("var(--m-arq)"),
             "lido": f"{len(titulos)} plantas · {len(dados['ambientes'])} ambientes · {len(dados.get('esquadrias', []))} esquadrias"},
            {"n": "Parte cinza", "cor": "var(--m-cinza)", "orc": t_b4 or None, "conf": conta("var(--m-cinza)"),
             "lido": f"{len(dados['paredes'])} paredes · {_fmt(blocos)} blocos"}]
    quant, n_cx = [], 0
    if af:
        m = sum(t["L"] for t in af["trechos"] + af["curtos"] + (af.get("complemento") or {}).get("trechos", []))
        pecas = len(af["conexoes"]) + sum(sum(v.values()) for v in ((af.get("complemento") or {}).get("codigos_plantas") or {}).values())
        disc.append({"n": "Água fria", "cor": "var(--m-af)", "orc": t_af or None, "conf": conta("var(--m-af)"), "lido": f"{_fmt(m)} m de tubo · {_fmt(pecas)} peças"})
    if es:
        m = sum(t["L"] for t in es["apartamentos"] + es["coletores"])
        n_cx = sum(1 for q in es.get("pecas_3d", []) if q["tipo"] == "caixa")
        disc.append({"n": "Esgoto", "cor": "var(--m-es)", "orc": t_es or None, "conf": conta("var(--m-es)"),
                     "lido": f"{_fmt(m)} m de tubo · {_fmt(sum(es['conexoes'].values()))} peças · {n_cx} caixas"})
    if ele:
        n_pts = sum(1 for r in ele["plantas"] for p in r["pontos"] if p["tipo"] not in ("cx", "quadro", "entrada"))
        m_el = sum(t[4] for t in ele["rede3d"]["trechos"])
        n_qd = sum(1 for r in ele["plantas"] for p in r["pontos"] if p["tipo"] == "quadro" and (p.get("nome") or "").startswith("QD"))
        disc.append({"n": "Elétrica", "cor": "var(--m-ele)", "orc": t_el or None, "conf": conta("var(--m-ele)"),
                     "lido": f"{_fmt(n_pts)} pontos · {_fmt(m_el)} m de eletroduto · {n_qd} quadros"})
    disc += [{"n": "Incêndio", "cor": "var(--m-inc)", "na": True, "lido": "próximo"}]
    if not ele:
        disc.append({"n": "Elétrica", "cor": "var(--m-ele)", "na": True, "lido": "sem projeto"})
    # pontos para os projetistas
    pend = [{"t": item, "d": res, "onde": g, "nivel": "w"} for g, _, item, res, ok in conf_l if not ok]
    if es:
        soltas = [c for c in (es.get("auditoria") or {}).get("colunas", []) if not c.get("parede") and c["dn"] >= 75]
        if soltas:
            f = [c.get("folga_m") or 0 for c in soltas]
            pend.append({"t": "Tubos de queda DN75/100 soltos no ambiente", "nivel": "w", "onde": "Sanitário · Arquitetura",
                         "d": f"{len(soltas)} colunas a {min(f) * 100:.0f}–{max(f) * 100:.0f} cm da face da parede. Prever shaft ou enchimento."})
    n_es_inf = sum(len(i.get("inferidos", [])) for i in (es or {}).get("isometricos", []))
    n_af_t = sum(1 for t in (af or {}).get("trechos", []) if t.get("como") == "inferido")
    n_af_c = sum(1 for c in (af or {}).get("conexoes", []) if c.get("como") == "inferido")
    if n_es_inf + n_af_t + n_af_c:
        pend.append({"t": "Rótulos e etiquetas faltando em alguns andares", "nivel": "n", "onde": "Hidráulica",
                     "d": ", ".join(x for x in (f"{n_es_inf} peças de esgoto" if n_es_inf else "", f"{n_af_t} tubos de água fria" if n_af_t else "",
                                                f"{n_af_c} ponto(s) de consumo" if n_af_c else "") if x) + ". O modelo já conta essas peças."})
    # quantitativos
    qs = dados.get("quantitativos", [])
    esq = Counter(x["tipo"] for x in dados.get("esquadrias", []))
    quant.append(["Arquitetura", "var(--m-arq)", [
        ["Área dos ambientes (medida)", "m²", sum(a["area_m2"] or 0 for a in dados["ambientes"]), None, 2],
        ["Piso (garagens inteiras)", "m²", sum(a.get("area_piso_m2") or a["area_m2"] or 0 for a in dados["ambientes"]), None, 2],
        ["Teto", "m²", sum(q.get("teto_m2") or 0 for q in qs), None, 2],
        ["Parede para revestimento (líquida)", "m²", sum(q.get("parede_liquida_m2") or 0 for q in qs), None, 2],
        ["Rodapé", "m", sum(q.get("rodape_m") or 0 for q in qs), None, 2],
        ["Portas", "un", esq.get("porta", 0), None, 0], ["Janelas", "un", esq.get("janela", 0), None, 0]]])
    grupos = {}
    for L in ins.get("linhas", []):
        grupos.setdefault(L[0], []).append([L[1], L[2], round(q_ins(L), 2), None, 0 if L[2] == "un" else 1])
    for g, linhas in grupos.items():
        cor = "var(--m-rev)" if g.lower().startswith("revestimento") else "var(--m-cinza)"
        quant.append([f"Parte cinza · {g}" if cor != "var(--m-rev)" else g, cor, linhas])
    if af:
        tab = (af.get("tabela_projetista") or {})
        tt = {int(k): v for k, v in (tab.get("tubos") or {}).items()}
        q = Counter()
        for t in af["trechos"] + af["curtos"] + (af.get("complemento") or {}).get("trechos", []):
            q[int(t["dn"])] += t["L"]
        tc = sum(x["qtd"] for v in {**tab.get("conexoes", {}), **tab.get("registros", {})}.values() for x in v)
        pecas = len(af["conexoes"]) + sum(sum(v.values()) for v in ((af.get("complemento") or {}).get("codigos_plantas") or {}).values())
        quant.append(["Água fria", "var(--m-af)", [[f"Tubo PVC soldável DN{k}", "m", round(q.get(k, 0), 2), tt.get(k), 2] for k in sorted(set(q) | set(tt))]
                      + [["Conexões e registros", "un", pecas, tc or None, 0]]])
    if es:
        tab = (es.get("tabela_projetista") or {})
        tt = {int(k): v for k, v in (tab.get("tubos") or {}).items()}
        q = Counter()
        for t in es["apartamentos"] + es["coletores"]:
            q[int(t["dn"])] += t["L"]
        tc = sum(x["qtd"] for v in (tab.get("conexoes") or {}).values() for x in v)
        tcx = sum(x["qtd"] for x in tab.get("caixas", []) if "Sifonada" in x["descricao"] or "Ralo" in x["descricao"])
        quant.append(["Esgoto", "var(--m-es)", [[f"Tubo PVC esgoto DN{k}", "m", round(q.get(k, 0), 2), tt.get(k), 2] for k in sorted(set(q) | set(tt))]
                      + [["Conexões", "un", sum(es["conexoes"].values()), tc or None, 0], ["Caixas sifonadas e ralos", "un", n_cx, tcx or None, 0]]])
    if ele:
        from .eletrica import POL, _contagens
        cont, lst = Counter(), Counter()
        for r in ele["plantas"]:
            cont.update(_contagens(r))
        for itens in ele["listas"].values():
            for x in itens:
                lst[(x["grupo"] or "", x["sub"] or "", x["item"])] += x["qtd"]
        ql = lambda rx_g, rx_s=".*", rx_i=".*": sum(v for (g, s_, it), v in lst.items()
                                                    if re.search(rx_g, g) and re.search(rx_s, s_) and re.search(rx_i, it))
        tot_m = Counter()
        for t in ele["rede3d"]["trechos"]:
            tot_m[t[3]] += t[4]
        bit = sorted({x["item"].rstrip('"') for v in ele["listas"].values() for x in v if (x["grupo"] or "").startswith("Eletroduto PVC flex")},
                     key=lambda b: POL.get(b, 0))
        linhas_el = [[f"Eletroduto {b}\" (modelo 3D: centro a centro das caixas)", "m", round(tot_m.get(b, 0), 2),
                      round(ql("^Eletroduto PVC flex", ".*", "^" + re.escape(b) + '"'), 2), 1] for b in bit]
        sec = Counter()
        for (g, s_, it), v in lst.items():
            m_ = re.match(r"^([\d.]+) mm²", it)
            if g.startswith("Cabo") and m_:
                sec[float(m_.group(1))] += v
        from .eletrica import cabos
        cb = cabos(ele)
        cm = Counter()
        for (pav, sc, f), v in cb["andar"].items():
            cm[sc] += v
        for (sc, f), v in cb["prumadas"].items():
            cm[sc] += v
        linhas_el += [[f"Cabo {str(k).replace('.0', '').replace('.', ',')} mm² (modelo: fiação desenhada × eletroduto)", "m", round(cm.get(k, 0), 2),
                       round(v, 2), 1] for k, v in sorted(sec.items())]
        pares = [("Tomada universal 2P+T 10 A (0,30 m)", "tomada universal", ("^Dispositivo El", "S/ placa", "universal")),
                 ("Tomada 2P+T 10 A (1,10 m)", "tomada 10A", ("^Dispositivo El", "S/ placa", "hexagonal.*10A")),
                 ("Tomada 2P+T 20 A", "tomada 20A", ("^Dispositivo El", "S/ placa", "20A")),
                 ("Ponto do chuveiro (placa cega)", "placa cega", ("^Dispositivo El", ".*", "^Placa cega")),
                 ("Interruptores", None, ("^Dispositivo El", "Placa 2x4", "^Interruptor")),
                 ("Sensor de presença", "sensor", ("^Dispositivo de Comando",)),
                 ("Luminária de teto", None, ("^Lumin", "^Luminária sobrepor")),
                 ("Arandela", "arandela", ("^Lumin", "^Arandela")),
                 ("Caixa 4×2\"", "caixa 4x2", ("Acessórios p/ eletrodutos", "^Caixa PVC$", '^4x2"')),
                 ("Caixa octogonal 3×3\"", "caixa octogonal", ("Acessórios p/ eletrodutos", "octogonal")),
                 ("Caixa de passagem 100×100×80", "caixa de passagem", ("^Caixa de passagem",)),
                 ("Quadro de distribuição", "quadro de distribuição", ("^Quadro distrib",))]
        for nome, chave, rx in pares:
            if chave is None and nome.startswith("Interr"):
                m_ = sum(v for k, v in cont.items() if k.startswith("interruptor"))
            elif chave is None:
                m_ = sum(v for k, v in cont.items() if k.startswith("luminária"))
            else:
                m_ = cont.get(chave, 0)
            linhas_el.append([nome, "un", m_, ql(*rx), 0])
        quant.append(["Elétrica", "var(--m-ele)", linhas_el])
    # orçamento por etapa (01 parte cinza, 02 instalações hidráulicas, ...)
    orc_out = None
    if orc:
        precos = orc.get("precos") or {}
        def cor_de(g):
            gl = g.lower()
            return next(((c, t) for k, c, t in COR_GRUPO if k in gl), ("var(--m-cinza)", g))
        subs_b4, ordem = [], []
        for L in orc["linhas"]:
            if L["grupo"] not in ordem:
                ordem.append(L["grupo"])
        for k, g in enumerate(ordem, 1):
            cod_ = lambda L: str((precos.get(L.get("ref")) or {}).get("cod") or "")
            itens = [[L["item"], L["un"], round(L["qtd"], 3), round(L["preco"], 2), round(L["custo"], 2), cod_(L) if cod_(L).isdigit() else ""]
                     for L in orc["linhas"] if L["grupo"] == g]
            c, leg = cor_de(g)
            subs_b4.append({"cod": f"01.{k}", "n": g, "total": round(sum(L["custo"] for L in orc["linhas"] if L["grupo"] == g), 2),
                            "cor": c, "leg": leg, "itens": itens})
        etapas = [{"cod": "01", "n": "Parte cinza", "total": round(orc["total"], 2), "subs": subs_b4}]
        subs_h = []
        for nome, o, cor in (("Água fria", (af or {}).get("orcamento"), "var(--m-af)"), ("Esgoto", (es or {}).get("orcamento"), "var(--m-es)")):
            if not o:
                continue
            for g in dict.fromkeys(L["grupo"] for L in o["linhas"]):
                itens = [[L["item"], L["un"], round(L["qtd"], 3), round(L["preco"], 2), round(L["custo"], 2), str(L.get("sinapi") or "")]
                         for L in o["linhas"] if L["grupo"] == g]
                subs_h.append({"cod": f"02.{len(subs_h) + 1}", "n": f"{nome} · {g.lower()}", "total": round(sum(L["custo"] for L in o["linhas"] if L["grupo"] == g), 2),
                               "cor": cor, "leg": nome, "itens": itens})
        if subs_h:
            etapas.append({"cod": "02", "n": "Instalações hidráulicas", "total": round(t_af + t_es, 2), "subs": subs_h})
        if o_el:
            cod = f"{len(etapas) + 1:02d}"
            subs_e = []
            for g in dict.fromkeys(L["grupo"] for L in o_el["linhas"]):
                itens = [[L["item"], L["un"], round(L["qtd"], 3), round(L["preco"], 2), round(L["custo"], 2), str(L.get("sinapi") or "")]
                         for L in o_el["linhas"] if L["grupo"] == g]
                subs_e.append({"cod": f"{cod}.{len(subs_e) + 1}", "n": g, "total": round(sum(L["custo"] for L in o_el["linhas"] if L["grupo"] == g), 2),
                               "cor": "var(--m-ele)", "leg": "Elétrica", "itens": itens})
            etapas.append({"cod": cod, "n": "Instalações elétricas", "total": round(t_el, 2), "subs": subs_e})
        etapas += [{"cod": f"{len(etapas) + 1:02d}", "n": "Instalações de incêndio", "st": "a ler"}]
        if not o_el:
            etapas.append({"cod": f"{len(etapas) + 1:02d}", "n": "Instalações elétricas", "st": "sem projeto" if not ele else "sem preço"})
        orc_out = {"total": round(total, 2), "porm2": round(total / area, 2) if area else 0, "etapas": etapas,
                   "ref": f"{sinapi} · custo direto",
                   "nota": "Custo direto (sem BDI). As etapas seguem a ordem da obra; abra cada linha para ver os itens, as quantidades e os preços SINAPI."}
    # documentos e plantas
    docs = [["Projeto arquitetônico", _pranchas(dados.get("documento")), dados.get("documento"), "lido", True]]
    if af:
        docs.append(["Projeto de água fria", _pranchas(af.get("pdf")), af.get("pdf"), "lido", True])
    if es:
        docs.append(["Projeto sanitário", _pranchas(es.get("pdf")), es.get("pdf"), "lido", True])
    if ele:
        docs.append(["Projeto elétrico", _pranchas(ele.get("pdf")), ele.get("pdf"), "lido", True])
    docs += [["Projeto de incêndio", None, None, "próximo", False]]
    if not ele:
        docs.append(["Projeto elétrico", None, None, "não recebido", False])
    tem_pag = bool(dados.get("paginacao", {}).get("vista_detalhe"))
    plantas = [["Áreas", "conferencia.html"], ["Paredes", "paredes.html"]] + ([["Paginação", "paginacao.html"]] if tem_pag else [])
    arquivos = [["Planilha de medição e orçamento", "medicao.xlsx", "todas as tabelas, para abrir no Excel"],
                ["Conferência das áreas", "conferencia.html", "planta 2D: área medida × rótulo do arquiteto"],
                ["Paredes", "paredes.html", "planta 2D: tipo de cada parede"]] + \
               ([["Paginação", "paginacao.html", "planta 2D e elevações bloco a bloco"]] if tem_pag else []) + \
               [["Dados da leitura", "obra.json", "tudo o que foi lido, em JSON"]]
    return {"obra": dados["obra"], "sub": f"{unid} unidades · {_fmt(area)} m²" if unid else f"{_fmt(area)} m²", "escopo": escopo,
            "gerado": ger, "sinapi": sinapi, "kpis": kpis, "disc": disc, "pend": pend, "quant": quant, "orc": orc_out,
            "conf": conf_l, "docs": docs, "arquivos": arquivos, "plantas": plantas}


def gerar(dados: dict, destino: Path, conf: list | None = None):
    """Página única da obra (obra.html): visão geral, 3D, plantas, quantitativos, orçamento, conferência e documentos."""
    import base64
    import gzip
    if conf is None:
        from .conferencia import checar
        conf = checar(dados)
    modelo = montar(dados)
    app = painel(dados, conf)
    dump = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    logo = lambda f: "data:image/png;base64," + base64.b64encode((WEB / f).read_bytes()).decode()
    txt = (WEB / "obra.html").read_text(encoding="utf-8")
    # a ordem importa: os trechos de código entram antes dos dados (que podem conter qualquer texto)
    txt = (txt.replace("__CENA__", (WEB / "cena3d.js").read_text(encoding="utf-8"))
           .replace("__UI3D__", (WEB / "ui3d.js").read_text(encoding="utf-8"))
           .replace("__TELAS__", (WEB / "telas.js").read_text(encoding="utf-8"))
           .replace("__LOGO_B__", logo("ageo-logo-branco.png")).replace("__LOGO_A__", logo("ageo-logo-azul.png"))
           .replace("__TITULO__", html.escape(f"{dados['obra']} · AGEO")))
    # three.js e o modelo 3D comprimidos (gzip + base64): a página cai de ~2,2 MB para menos de 1 MB e abre em
    # visualizadores que mostram o código-fonte de arquivos grandes; o navegador descomprime (DecompressionStream)
    z = lambda t: base64.b64encode(gzip.compress(t.encode("utf-8"), 9)).decode("ascii")
    txt = txt.replace("__Z_THREE__", z(VENDOR.read_text(encoding="utf-8")))
    txt = txt.replace("__Z_DADOS__", z(json.dumps(modelo, ensure_ascii=False, separators=(",", ":"))))
    txt = txt.replace("const APP=__APP__;", "const APP=" + dump(app) + ";")
    destino.write_text(txt, encoding="utf-8")
