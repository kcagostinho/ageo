"""Esgoto sanitário: quantitativo pelos isométricos de prumada e de coletores, posição pelas plantas.

O PDF sanitário tem o mesmo jeito do de água fria (sem camadas, tubo = traço grosso preto, rótulo
"DNxx mm / L,LLm", código da conexão no círculo), mas os isométricos são perspectivas de verdade (os ramais
correm em duas direções no piso) e não estão em escala horizontal. Por isso:

  - quantitativo: rótulos dos isométricos, cada tubo uma vez (rótulo repetido no mesmo tubo, ou em pedaços
    alinhados do mesmo tubo, conta uma vez);
  - a parte de baixo de cada isométrico de apartamento (tubo de queda até o coletor, coletores) é a mesma das
    vistas "Coletores" e das plantas do térreo/subsolo: entra uma vez, no grupo dos coletores, com a regra
    da água fria (horizontais pela planta; verticais pela vista que mais os mostra; o que só o isométrico
    rotula, no que passa da planta);
  - posição no 3D: ramais pela planta de cada andar (o tubo é desenhado com o diâmetro real, então o DN sai
    da espessura do traço), tubos de queda e ventilações pelos balões TQ-xx / V-xx; altura por premissa
    (ramal sob a laje do andar; coletor sob a laje do térreo).
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pymupdf

from .hidraulica import (NOMES_PLANTA, _ang, _linhas_eixo, _unicos_por_tubo, balões, caixas_por_titulo, dentro,
                         ler_vista, limpo, linhas_finas, linhas_paredes_modelo, mascara_tubos, niveis_do_modelo,
                         plantas, pontos_marcados, registrar, render, rede_da_planta, segmentos, tabela_projetista,
                         textos, PPP)

OD = {40: 0.040, 50: 0.050, 75: 0.075, 100: 0.110, 150: 0.160}       # diâmetro externo (m), série normal
Z_RAMAL = -0.25                       # ramal do andar: sob a laje (forro do andar de baixo)
Z_COLETOR_TERREO, Z_COLETOR_SUBSOLO = -0.40, -0.30


def _dn_pela_espessura(esp_m):
    return min(OD, key=lambda d: abs(OD[d] - esp_m))


def ramais_da_planta(pg, caixa, T, m_pt, minimo_m=0.06, dn_max=100):
    """Tubos desenhados na planta (x, y na arquitetura), com o DN pela espessura do traço. As pontas vão até o
    centro da conexão (o símbolo da conexão interrompe o traço); traço mais grosso que o DN máximo do andar é
    símbolo (caixa sifonada, ralo), não tubo."""
    from scipy import ndimage
    from .hidraulica import ligar
    a = render(pg, caixa)
    segs, m, _ = segmentos(a, caixa)
    dt = ndimage.distance_transform_edt(m)
    s, tx_, ty_ = T
    out = []
    bons = [i for i, sg in enumerate(segs) if math.dist(*sg) * m_pt >= 0.04]
    pontas = ligar(segs, bons, raio=12.0, ponte=0.30 / m_pt)       # junção/luva: até 30 cm de vão na planta
    for i in bons:
        sg0 = segs[i]
        sg = tuple(tuple(p) for p in pontas.get(i, sg0))
        L = math.dist(*sg) * m_pt
        if L < minimo_m:
            continue
        xs = np.linspace(sg0[0][0], sg0[1][0], 12)[2:-2]
        ys = np.linspace(sg0[0][1], sg0[1][1], 12)[2:-2]
        vals = [dt[min(int(round((y - caixa[1]) * PPP)), dt.shape[0] - 1), min(int(round((x - caixa[0]) * PPP)), dt.shape[1] - 1)]
                for x, y in zip(xs, ys)]
        esp = 2 * float(np.median(vals)) / PPP * m_pt
        if esp < 0.03 or _dn_pela_espessura(esp) > dn_max:
            continue
        out.append({"dn": _dn_pela_espessura(esp), "esp_m": round(esp, 3), "L_desenho": round(L, 3),
                    "a": [round(s * sg[0][0] + tx_, 2), round(s * sg[0][1] + ty_, 2)],
                    "b": [round(s * sg[1][0] + tx_, 2), round(s * sg[1][1] + ty_, 2)]})
    return out


def caixas_da_planta(pg, caixa, T, m_pt, lado=(0.08, 0.21)):
    """Caixas sifonadas e ralos da planta: o símbolo tem um quadrado ('qu') de ~10 cm ou um círculo de ~15 cm
    (caixa redonda). Devolve centros (x, y na arquitetura) e o lado/diâmetro (m)."""
    R = pg.rotation_matrix
    s, tx_, ty_ = T
    achados = []
    for d in pg.get_drawings():
        its = d["items"]
        quadrado = len(its) == 1 and its[0][0] == "qu"
        redondo = len(its) >= 4 and all(it[0] == "c" for it in its)          # caixa sifonada redonda
        if not (quadrado or redondo):
            continue
        r = d["rect"] * R
        if not (caixa[0] <= r.x0 <= caixa[2] and caixa[1] <= r.y0 <= caixa[3]):
            continue
        w, h = r.width * m_pt, r.height * m_pt
        if lado[0] <= w <= lado[1] and abs(w - h) < 0.02:
            c = ((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)
            for a in achados:
                if math.dist(a[0], c) < 2.5:
                    a[1] = max(a[1], w)
                    break
            else:
                achados.append([c, w])
    return [{"xy": [round(s * c[0] + tx_, 2), round(s * c[1] + ty_, 2)], "lado_m": round(w, 3)} for c, w in achados]


def detalhar(ramais, caixas, colunas, m_pt, z_piso):
    """Peças do 3D de um andar: subida até o aparelho na ponta livre do ramal, ligação ao tubo de queda,
    conexões onde os ramais se encontram e caixas/ralos no piso. Devolve (tubos extras, peças)."""
    pontas = []
    for k, r in enumerate(ramais):
        pontas += [(tuple(r["a"]), k), (tuple(r["b"]), k)]
    z_r = z_piso + Z_RAMAL
    extras, pecas = [], []
    perto = lambda P, Q, d: math.dist(P, Q) * m_pt <= d
    usadas = set()
    for P, k in pontas:
        if (P, k) in usadas:
            continue
        juntas = [(Q, j) for Q, j in pontas if j != k and perto(P, Q, 0.06)]
        dn = ramais[k]["dn"]
        if juntas:                                     # encontro de ramais: junção / joelho
            usadas |= {(P, k)} | set(juntas)
            pecas.append({"tipo": "conexao", "xy": list(P), "z": round(z_r, 3), "dn": max([dn] + [ramais[j]["dn"] for _, j in juntas])})
            continue
        cx = next((c for c in caixas if perto(P, c["xy"], 0.25)), None)
        col = next((c for c in colunas if c["id"].startswith(("TQ", "V")) and perto(P, c["xy"], 0.35)), None)
        if col:                                        # chega no tubo de queda / ventilação
            extras.append({"dn": dn, "a": list(P), "b": list(col["xy"]), "za": z_r, "zb": z_r, "papel": f"ligação ao {col['id']}"})
            pecas.append({"tipo": "conexao", "xy": list(col["xy"]), "z": round(z_r, 3), "dn": max(dn, 75)})
        elif cx:                                       # sobe para a caixa sifonada / ralo
            extras.append({"dn": dn, "a": list(P), "b": list(P), "za": z_r, "zb": z_piso - 0.05, "papel": "subida à caixa/ralo"})
        else:                                          # ponta livre: subida ao aparelho
            topo = z_piso + (0.0 if dn >= 100 else 0.50)
            extras.append({"dn": dn, "a": list(P), "b": list(P), "za": z_r, "zb": topo,
                           "papel": "subida ao vaso (até o piso)" if dn >= 100 else "subida ao lavatório/pia/tanque (premissa 0,50 m)"})
            pecas.append({"tipo": "conexao", "xy": list(P), "z": round(z_r, 3), "dn": dn})
    for c in caixas:
        pecas.append({"tipo": "caixa", "xy": c["xy"], "z": round(z_piso, 3), "lado": c["lado_m"]})
    return extras, pecas


def caixas_e_ralos(tx) -> list[dict]:
    """Linhas das tabelas "Caixas e Ralos" e "Caixa de Gordura e Inspeção" (quantidade | Esgoto | descrição em
    uma ou duas linhas, sem código)."""
    import re
    sist = [t for t in tx if t["t"] == "Esgoto" and t["size"] < 14]
    out = []
    for t in sorted(sist, key=lambda t: (t["c"][0], t["c"][1])):
        y = t["c"][1]
        qtd = next((u for u in tx if abs(u["c"][1] - y) < 2 and t["r"][0] - 90 < u["c"][0] < t["r"][0] and re.match(r"^\d+$", u["t"])), None)
        desc = sorted((u for u in tx if abs(u["c"][1] - y) < 2 and t["r"][2] < u["c"][0] < t["r"][2] + 420), key=lambda u: u["c"][0])
        if not qtd or not desc:
            continue
        texto = " ".join(u["t"] for u in desc if not re.match(r"^\d{2}$", u["t"]) and u["t"] != "Série Normal")
        if any(re.match(r"^\d{2}$", u["t"]) for u in desc) or "Série Normal" in texto:   # conexão (tem código)
            continue
        # 2ª linha da célula (sem quantidade nem "Esgoto")
        prox = sorted((u for u in tx if 3 < u["c"][1] - y < 16 and t["r"][2] < u["c"][0] < t["r"][2] + 420), key=lambda u: u["c"][0])
        if prox and not any(abs(u["c"][1] - prox[0]["c"][1]) < 2 and u["t"] == "Esgoto" and abs(u["c"][0] - t["c"][0]) < 80 for u in tx):
            texto += " " + " ".join(u["t"] for u in prox)
        item = {"qtd": float(qtd["t"]), "descricao": texto.strip()}
        if item not in out:
            out.append(item)
    return out


def ler_esgoto(pdf, dados: dict, log=print) -> dict:
    doc = pymupdf.open(pdf)
    niveis = niveis_do_modelo(dados)
    vistas_arq = {v["titulo"]: v for v in dados["vistas"]}
    avisos = []
    # 1. isométricos (apartamentos e coletores) e tabela do projetista
    vistas, tabela = [], None
    for pg in doc:
        tx = textos(pg)
        if tabela is None:
            tb = tabela_projetista(tx)
            if tb["tubos"]:
                tabela = tb
                tabela["caixas"] = caixas_e_ralos(tx)
        cxs, excl, nomes = caixas_por_titulo(pg, tx)
        for cx, nome in zip(cxs, nomes):
            v = ler_vista(pg, cx, tx, excl)
            esc = (v["esc"] or 100) * 1.25
            uni, rep = _unicos_por_tubo(v["rotulos"], v["segs"], esc=esc)
            itens = [{"dn": ro["dn"], "L": ro["L"], "como": como, "y": ro["c"][1],
                      "vertical": j is not None and abs(abs(_ang(v["segs"][j])) - 90) < 3} for ro, j, como in uni if ro["L"]]
            t2 = [t for t in tx if dentro(t["c"], cx)]
            cols = sorted({t["t"].replace(" ", "") for t in t2 if t["t"].replace(" ", "").startswith(("TQ-", "V-"))})
            sem = sum(1 for x in v["rotulos"] if x[1] is None)
            vistas.append({"titulo": nome, "pagina": pg.number + 1, "itens": itens, "repetidos": rep, "sem_tubo": sem,
                           "rotulos": len(v["rotulos"]), "codigos": dict(Counter(t["t"] for t in v["codigos"])), "colunas": cols})
            tot = Counter()
            for x in itens:
                tot[x["dn"]] += x["L"]
            log(f"  isométrico {nome} (pág. {pg.number + 1}): {len(v['rotulos'])} rótulos, {rep} repetidos no mesmo tubo, "
                + ", ".join(f"DN{k} {q:.2f}" for k, q in sorted(tot.items())))
    # 2. plantas: registro, balões (TQ/V), ramais (tipo) e rede com rótulos (térreo/subsolo)
    plantas_out, pontos, ramais, redes, caixas_pav = [], defaultdict(dict), [], {}, {}
    for pg in doc:
        tx = textos(pg)
        for p in plantas(pg, tx, NOMES_PLANTA):
            cx = p["caixa"]
            fin = linhas_finas(pg, cx)
            hh, hv = _linhas_eixo(fin)
            va = vistas_arq.get(p["pavimento"], vistas_arq.get("5ºPavimento"))
            rh, rv = linhas_paredes_modelo(dados, va["id"])
            s, txx, tyy, info = registrar(rh, rv, hh, hv, escalas=np.arange(0.997, 1.0035, 0.0001))
            T = (s, txx, tyy)
            m_pt = va["m_por_pt"] * s
            bal = balões([t for t in tx if dentro(t["c"], cx)], fin, pontos=pontos_marcados(pg, cx, tam=8))
            for b in bal:
                if b["ponto"]:
                    X, Y = b["ponto"]
                    pontos[b["coluna"]][p["pavimento"]] = (s * X + txx, s * Y + tyy, b["diametro"])
            if p["pavimento"].endswith("ºPavimento"):
                for r in ramais_da_planta(pg, cx, T, m_pt):
                    ramais.append({**r, "pav": p["pavimento"], "vista": va["id"]})
                caixas_pav[p["pavimento"]] = caixas_da_planta(pg, cx, T, m_pt)
            elif p["pavimento"] in ("Pavimento Térreo", "Sub-Solo"):
                redes[p["pavimento"]] = {**rede_da_planta(pg, cx, T, m_pt), "vista": va["id"]}
            plantas_out.append({"pavimento": p["pavimento"], "pagina": pg.number + 1, "vista_arq": va["id"], "escala": round(s, 5),
                                "desloc": [round(txx, 2), round(tyy, 2)], "rms_mm": round(info["rms_pt"] * va["m_por_pt"] * 1000, 1) if info["rms_pt"] else None,
                                "baloes": len(bal)})
            log(f"  planta {p['pavimento']} (pág. {pg.number + 1}) -> {va['id']}: escala {s:.5f}, erro {plantas_out[-1]['rms_mm']} mm, {len(bal)} balões")
    # colunas (tubos de queda e ventilações): mediana dos andares tipo
    colunas = []
    m1 = vistas_arq["1ºPavimento"]["m_por_pt"]
    for c, d in sorted(pontos.items()):
        tipos = [v for k, v in d.items() if k.endswith("ºPavimento")]
        if not tipos:
            continue
        mx, my = float(np.median([v[0] for v in tipos])), float(np.median([v[1] for v in tipos]))
        desv = {k: round(math.dist(v[:2], (mx, my)) * m1 * 1000, 1) for k, v in d.items() if k.endswith("ºPavimento")}
        colunas.append({"id": c, "xy": [round(mx, 2), round(my, 2)], "desvio_mm": desv,
                        "diametro": Counter(v[2] for v in d.values()).most_common(1)[0][0]})
        fora = {k: v for k, v in desv.items() if v > 30}
        if fora:
            avisos.append(f"coluna {c}: balão fora da prumada em {fora} (mm) — usada a mediana")
    # detalhes do 3D por andar: subidas aos aparelhos, ligação ao tubo de queda, conexões, caixas e ralos
    extras_3d, pecas_3d = [], []
    for pav, cxs_ in caixas_pav.items():
        rs = [r for r in ramais if r["pav"] == pav]
        ex, pc = detalhar(rs, cxs_, colunas, m1, niveis[pav])
        extras_3d += [{**e, "pav": pav} for e in ex]
        pecas_3d += [{**q, "pav": pav} for q in pc]
    # 3. contagem, cada tubo uma vez
    col_views = [v for v in vistas if v["titulo"].startswith("Coletores")]
    apt_views = [v for v in vistas if not v["titulo"].startswith("Coletores")]
    no_coletor = set()
    for v in col_views:
        no_coletor |= {(x["dn"], x["L"]) for x in v["itens"]}
    for r in redes.values():
        no_coletor |= {(x["dn"], x["L"]) for x in r["horizontais"] + r["verticais"]}
    apartamentos, baixo_h, baixo_v = [], Counter(), Counter()
    def comodo(t):
        t = t.lower()
        return "banheiro" if "banheiro" in t else "cozinha" if "cozinha" in t else "gourmet" if "gourmet" in t else t
    for v in apt_views:
        c = Counter((x["dn"], x["L"]) for x in v["itens"])
        irmaos = set()                                  # o mesmo cômodo nos outros tipos
        for w in apt_views:
            if w is not v and comodo(w["titulo"]) == comodo(v["titulo"]):
                irmaos |= {(x["dn"], x["L"]) for x in w["itens"]}
        # parte de baixo do isométrico (tubo de queda até o coletor, coletores): abaixo do último tubo que se
        # repete andar a andar (o ramal do 1º pavimento)
        repet = [x["y"] for x in v["itens"] if c[(x["dn"], x["L"])] >= 4]
        y_corte = (max(repet) + 25) if repet else 1e9
        v["y_corte"], v["irmaos"] = y_corte, irmaos
        for x in v["itens"]:
            k = (x["dn"], x["L"])
            # vai para o grupo dos coletores: abaixo do corte, ou tubo próprio deste tipo (não está no mesmo cômodo dos
            # outros tipos) que a planta do térreo/subsolo ou a vista de coletores também mostra
            if c[k] < 4 and (x["y"] > y_corte or (k in no_coletor and k not in irmaos)):
                (baixo_v if x["vertical"] else baixo_h)[k] += 1
            else:
                apartamentos.append({"vista": v["titulo"], "dn": x["dn"], "L": x["L"], "vertical": x["vertical"], "como": x["como"]})
    plan_h = Counter((x["dn"], x["L"]) for r in redes.values() for x in r["horizontais"])
    plan_v = Counter((x["dn"], x["L"]) for r in redes.values() for x in r["verticais"])
    col_h, col_v = Counter(), Counter()
    for v in col_views:
        for x in v["itens"]:
            (col_v if x["vertical"] else col_h)[(x["dn"], x["L"])] += 1
    coletores = []
    for pav, r in redes.items():
        z = niveis["Pavimento Térreo"] + (Z_COLETOR_TERREO if pav == "Pavimento Térreo" else 0) + \
            (niveis["Sub-Solo"] + Z_COLETOR_SUBSOLO - niveis["Pavimento Térreo"] if pav == "Sub-Solo" else 0)
        for h in r["horizontais"]:
            coletores.append({"grupo": "Coletores", "pav": pav, "dn": h["dn"], "L": h["L"], "a": [*h["a"], round(z, 3)],
                              "b": [*h["b"], round(z, 3)], "vista": r["vista"], "eixo": "h", "origem": f"planta {pav}", "como": h["como"]})
    # a planta do térreo/subsolo rotula cada coletor uma vez: o que ela tem (horizontal ou vertical) vale como
    # está nela; os isométricos (que repetem rótulos e desenham o mesmo tubo em mais de uma vista) só
    # acrescentam o (DN, comprimento) que a planta não tem — o maior número de vezes numa fonte.
    plan_all = plan_h + plan_v
    # o trecho do tubo de queda até o térreo/subsolo pode já ter entrado pelo isométrico do apartamento (acima
    # do corte): os verticais da planta com o mesmo (DN, comprimento) de um tubo não repetido do apartamento
    # descontam esse tubo
    nao_rep = Counter()
    for v in apt_views:
        c = Counter((x["dn"], x["L"]) for x in v["itens"])
        for x in v["itens"]:
            k = (x["dn"], x["L"])
            if c[k] < 4 and x["y"] <= v["y_corte"] and not (k in no_coletor and k not in v["irmaos"]):
                nao_rep[k] += 1
    for k in list(plan_v):
        plan_v[k] = max(plan_v[k] - nao_rep.get(k, 0), 0)
    for k, n in sorted(plan_v.items()):
        for _ in range(n):
            coletores.append({"grupo": "Coletores", "pav": "Pavimento Térreo", "dn": k[0], "L": k[1], "eixo": "v",
                              "origem": "plantas térreo/subsolo (vertical)", "como": "vertical"})
    extra, fonte = Counter(), {}
    for nome, c in (("isométricos de coletores", col_h + col_v), ("isométricos dos apartamentos (parte de baixo)", baixo_h + baixo_v)):
        for k, n in c.items():
            if k not in plan_all and n > extra[k] + nao_rep.get(k, 0):
                extra[k], fonte[k] = n, nome
    for k, n in sorted(extra.items()):
        for _ in range(max(n - nao_rep.get(k, 0), 0)):
            coletores.append({"grupo": "Coletores", "pav": "Pavimento Térreo", "dn": k[0], "L": k[1], "eixo": "?",
                              "origem": fonte[k] + " (sem rótulo na planta)", "como": "só no isométrico"})
    # 4. conexões: códigos dos isométricos dos apartamentos + o maior entre coletores (vistas) e plantas
    cod_apt, cod_col, cod_pl = Counter(), Counter(), Counter()
    for v in apt_views:
        cod_apt.update(v["codigos"])
    for v in col_views:
        cod_col.update(v["codigos"])
    for r in redes.values():
        cod_pl.update(r["codigos"])
    # os isométricos dos apartamentos já desenham o trecho até os coletores, com as conexões; as vistas de
    # coletores e as plantas repetem as mesmas peças (somar dobraria as curvas). Conta pelos apartamentos.
    conexoes = Counter(cod_apt)
    q = Counter()
    for t in apartamentos + coletores:
        q[(("Apartamentos" if "vista" in t and "grupo" not in t else "Coletores"), t["dn"])] += t["L"]
    for (g, dn), val in sorted(q.items()):
        log(f"  {g}: DN{dn} {val:.2f} m")
    saida = {"pdf": Path(pdf).name, "niveis": niveis,
             "isometricos": [{k: v[k] for k in ("titulo", "pagina", "repetidos", "sem_tubo", "rotulos", "colunas", "codigos")} |
                             {"n_tubos": len(v["itens"])} for v in vistas],
             "plantas": plantas_out, "colunas": colunas, "apartamentos": apartamentos, "coletores": coletores,
             "ramais": ramais, "extras_3d": extras_3d, "pecas_3d": pecas_3d, "conexoes": dict(conexoes), "conexoes_aptos": dict(cod_apt),
             "conexoes_coletores": {k: max(cod_col.get(k, 0), cod_pl.get(k, 0)) for k in set(cod_col) | set(cod_pl)},
             "tabela_projetista": tabela, "avisos": avisos}
    saida["auditoria"] = auditar(saida, dados)
    return limpo(saida)


def auditar(es: dict, dados: dict) -> dict:
    """Tubos de queda e ventilações × alvenaria: onde cada coluna passa (parede estrutural/vedação, shaft ou
    canto do ambiente). DN75/100 não cabe num bloco de 14 cm nem de 9 cm: precisa de shaft ou enchimento."""
    from shapely.geometry import LineString, Point, Polygon
    v1 = next(v for v in dados["vistas"] if v["titulo"] == "1ºPavimento")
    m = v1["m_por_pt"]
    paredes = [p for p in dados["paredes"] if p["vista"] == v1["id"]]
    ambs = [(a["nome"], a.get("unidade"), Polygon(a["poligono"]).buffer(0)) for a in dados["ambientes"] if a["vista"] == v1["id"] and a["poligono"]]
    out, conflitos = [], []
    for c in es["colunas"]:
        P = Point(c["xy"])
        dn = int(str(c.get("diametro") or "ø0").replace("ø", "") or 0)
        par = [(p, P.distance(LineString([p["eixo"][:2], p["eixo"][2:]])) * m) for p in paredes]
        dentro_ = [(p, d) for p, d in par if d <= p["espessura_m"] / 2]
        perto = sorted(((p, d - p["espessura_m"] / 2) for p, d in par if d > p["espessura_m"] / 2), key=lambda x: x[1])[:1]
        amb = sorted((g.distance(P) * m, n, u) for n, u, g in ambs)[:1]
        reg = {"coluna": c["id"], "dn": dn, "ambiente": f"{amb[0][2] + ' · ' if amb and amb[0][2] else ''}{amb[0][1]}" if amb else "—"}
        if dentro_:
            p = dentro_[0][0]
            reg.update(local=f"dentro da parede {p['id']} ({p['tipo']}, {p['espessura_m'] * 100:.0f} cm)", parede=p["id"], tipo_parede=p["tipo"])
            if (dn / 1000 + 0.01) > p["espessura_m"] - 0.04 or p["tipo"] == "estrutural":
                conflitos.append({**reg, "conflito": f"{c['id']} ø{dn} dentro da parede {p['tipo']} {p['id']} de {p['espessura_m'] * 100:.0f} cm "
                                                     "(não cabe no bloco: precisa de shaft ou enchimento)"})
        else:
            dist = perto[0][1] if perto else None
            reg.update(local=f"no ambiente, a {dist * 100:.0f} cm da face da parede {perto[0][0]['id']}" if perto else "no ambiente",
                       parede=None, tipo_parede=None, folga_m=round(dist, 3) if dist is not None else None)
        out.append(reg)
    return {"colunas": out, "conflitos": conflitos}


def _comodo(t):
    t = t.lower()
    return "banheiro" if "banheiro" in t else "cozinha" if "cozinha" in t else "gourmet" if "gourmet" in t else t


def conferir(es: dict) -> list[tuple[str, str, str, bool]]:
    G = "Esgoto"
    out = []
    isos = es["isometricos"]
    n = sum(i["rotulos"] for i in isos)
    sem = sum(i["sem_tubo"] for i in isos)
    out.append((G, "Rótulos DN/comprimento ligados a um tubo", f"{n - sem} de {n} rótulos em {len(isos)} isométricos", sem <= 0.01 * n))
    out.append((G, "Rótulo repetido no mesmo tubo (contado uma vez)", f"{sum(i['repetidos'] for i in isos)} rótulos", True))
    por = defaultdict(Counter)
    for t in es["apartamentos"]:
        por[t["vista"]][t["dn"]] += t["L"]
    for comodo in ("banheiro", "gourmet", "cozinha"):
        vs = {k: v for k, v in por.items() if _comodo(k) == comodo}
        if not vs:
            continue
        tot = {k: sum(v.values()) for k, v in vs.items()}
        amp = max(tot.values()) - min(tot.values())
        media = sum(tot.values()) / len(tot)
        out.append((G, f"{comodo.capitalize()}: tipos A a D (acima do coletor)",
                    ", ".join(f"{k.split(' - ')[0][5:]} {v:.2f} m" for k, v in sorted(tot.items())) + f": diferença {amp:.2f} m",
                    amp <= 0.12 * media))
    desv = {c["id"]: max(c["desvio_mm"].values()) for c in es["colunas"] if c["desvio_mm"]}
    ruins = {k: v for k, v in desv.items() if v > 30}
    out.append((G, "Tubos de queda e ventilações no prumo",
                f"{len(desv)} colunas; " + ("todas até 30 mm" if not ruins else
                                            f"balão de um andar aponta para outro ponto em {', '.join(sorted(ruins))} (usada a mediana dos andares)"),
                len(ruins) <= 3))
    rms = max((p["rms_mm"] or 0) for p in es["plantas"])
    out.append((G, "Plantas registradas sobre a arquitetura", f"{len(es['plantas'])} plantas; maior erro médio {rms:.1f} mm", rms < 10))
    tab = (es.get("tabela_projetista") or {}).get("tubos") or {}
    if tab:
        q = Counter()
        for t in es["apartamentos"] + es["coletores"]:
            q[int(t["dn"])] += t["L"]
        tm, tt = sum(q.values()), sum(tab.values())
        out.append((G, "Tubos: modelo × tabela do projetista",
                    f"{tm:.2f} m × {tt:.2f} m ({tm / tt - 1:+.1%}) · " + ", ".join(f"DN{k} {q.get(int(k), 0) - v:+.2f} m" for k, v in sorted(tab.items(), key=lambda kv: int(kv[0]))),
                    abs(tm / tt - 1) < 0.03))
        tc = {k: sum(x["qtd"] for x in v) for k, v in (es["tabela_projetista"].get("conexoes") or {}).items()}
        iguais = [k for k in tc if es["conexoes"].get(k, 0) == tc[k]]
        dif = {k: int(es["conexoes"].get(k, 0) - tc[k]) for k in tc if es["conexoes"].get(k, 0) != tc[k]}
        out.append((G, "Conexões: modelo × tabela do projetista",
                    f"{len(iguais)} de {len(tc)} códigos iguais; diferenças: " + ", ".join(f"{k} {v:+d}" for k, v in sorted(dif.items())),
                    sum(abs(v) for v in dif.values()) <= 0.05 * sum(tc.values())))
    au = es.get("auditoria") or {}
    nc = len(au.get("conflitos", []))
    soltas = [c for c in au.get("colunas", []) if not c.get("parede") and c["dn"] >= 75]
    out.append((G, "Tubos de queda × alvenaria",
                f"{nc} colunas dentro de parede onde não cabem; {len(soltas)} tubos de queda DN75/100 no ambiente, junto à parede "
                f"(prever shaft ou enchimento)", nc == 0))
    return out
