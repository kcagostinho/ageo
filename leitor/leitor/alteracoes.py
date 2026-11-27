"""Alterações de projeto decididas pelo cliente e aplicadas sobre a leitura do PDF.

Arquivo da obra: obras/<obra>/alteracoes.json. Exemplo (cozinha aberta para a sala, sem porta):

    {"remover_paredes": [
        {"descricao": "Parede com porta entre a cozinha/A.S. e a sala: acesso aberto, sem porta",
         "entre": ["Cozinha/Á.S.", "Sala Estar/Jantar"], "com_porta": true, "comprimento_max_m": 2.0,
         "data": "2026-11-27", "origem": "decisão do proprietário"}]}

A regra vale para todos os pavimentos e unidades. Para cada parede removida:
  - sai a parede e os vãos dela; as etiquetas L × H desses vãos saem da contagem de esquadrias;
  - a faixa de piso da parede (sem o que é de outras paredes) vai metade para cada ambiente, e a
    divisa vira contorno aberto (sem parede, sem rodapé);
  - as paredes que encostavam nela têm o encontro recalculado (L vira ponta livre, T-passante
    vira emenda contínua);
  - a área esperada do ambiente passa a ser o rótulo do arquiteto + a área acrescentada.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import shapely
from shapely.geometry import LineString, Point, Polygon


def carregar(pasta_obra: Path) -> dict:
    arq = pasta_obra / "alteracoes.json"
    return json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}


def _nome(lado: str) -> str:
    return lado.split(" · ")[-1]


def _seleciona(p: dict, regra: dict) -> bool:
    entre = set(regra.get("entre", []))
    nomes = {_nome(x) for x in p["lado_a"] + p["lado_b"]}
    if entre and not entre <= nomes:
        return False
    if regra.get("com_porta") and not any(y["tipo"] == "porta" for y in p["vaos"]):
        return False
    if regra.get("comprimento_max_m") is not None and p["comprimento_m"] > regra["comprimento_max_m"]:
        return False
    if regra.get("ids") and p["id"] not in regra["ids"]:
        return False
    return True


def _encontro(q: dict, x: float, y: float, outras: list[dict], m: float) -> str:
    """Mesma regra de paredes._no, com as paredes do modelo (eixo e espessura nominais)."""
    tq = q["espessura_m"] / m
    chegam = passam = colinear = 0
    for r in outras:
        if r is q:
            continue
        e = r["eixo"]
        tr = r["espessura_m"] / m
        if Point(x, y).distance(LineString([e[:2], e[2:]])) > max(tr, tq) / 2 + 1:
            continue
        tol = max(tr, tq) / 2 + 1
        ao = x if r["o"] == "h" else y
        a_, b_ = (e[0], e[2]) if r["o"] == "h" else (e[1], e[3])
        ponta = abs(ao - a_) < tol or abs(ao - b_) < tol
        if r["o"] == q["o"]:
            colinear += 1
        elif ponta:
            chegam += 1
        else:
            passam += 1
    if passam:
        return "X" if colinear else "T"
    if colinear and chegam:
        return "X" if chegam >= 2 else "T-passante"
    if chegam >= 2:
        return "T"
    if chegam == 1:
        return "L"
    return "continua" if colinear else "livre"


def aplicar(dados: dict, alt: dict) -> list[dict]:
    """Aplica as alterações em 'dados' (antes dos quantitativos, paginação e insumos). Devolve o registro."""
    regras = alt.get("remover_paredes", [])
    if not regras:
        return []
    registro = []
    m_vista = {v["id"]: v["m_por_pt"] for v in dados["vistas"]}
    remover = [(p, r) for p in dados["paredes"] for r in regras if _seleciona(p, r)]
    ids_rem = {p["id"] for p, _ in remover}
    vaos_rem = {y["vao"] for p, _ in remover for y in p["vaos"]}
    por_vao = {x["id"]: x for x in dados["vaos"]}
    for p, regra in remover:
        vid, m = p["vista"], m_vista[p["vista"]]
        e = p["eixo"]
        eixo = LineString([e[:2], e[2:]])
        t = p["espessura_m"] / m
        # faixa de piso liberada: a parede menos o que pertence às outras paredes
        outras = [q for q in dados["paredes"] if q["vista"] == vid and q["id"] not in ids_rem and q["tipo"] != "muro"]
        faixa = eixo.buffer(t / 2, cap_style="flat")
        if outras:
            faixa = faixa.difference(shapely.union_all([LineString([q["eixo"][:2], q["eixo"][2:]])
                                                        .buffer(q["espessura_m"] / m / 2, cap_style="flat") for q in outras]))
        # metade para cada lado do eixo
        ux, uy = (e[2] - e[0]), (e[3] - e[1])
        L = math.hypot(ux, uy) or 1e-9
        nx, ny = -uy / L * t, ux / L * t
        lado1 = Polygon([(e[0], e[1]), (e[2], e[3]), (e[2] + nx, e[3] + ny), (e[0] + nx, e[1] + ny)])
        metades = [faixa.intersection(lado1), faixa.difference(lado1)]
        ambs = []
        for nome_lado in p["lado_a"] + p["lado_b"]:
            un, nome = (nome_lado.split(" · ") + [None])[:2] if " · " in nome_lado else (None, nome_lado)
            for i, a in enumerate(dados["ambientes"]):
                if a["vista"] == vid and a["nome"] == nome and (un is None or a.get("unidade") == un) and a["poligono"]:
                    ambs.append(i)
        acrescimos = {}
        # dono de cada metade: o ambiente que divide mais borda com ela (não o mais próximo: nas pontas
        # empata). Decidido antes de mexer nos polígonos, senão a 1ª metade "puxa" a 2ª.
        donos = []
        for meia in metades:
            if meia.is_empty or meia.area * m * m < 1e-4 or not ambs:
                continue
            i = max(ambs, key=lambda k: Polygon(dados["ambientes"][k]["poligono"]).boundary.intersection(meia.buffer(0.5)).length)
            donos.append((meia, i))
        for meia, i in donos:
            a = dados["ambientes"][i]
            P = Polygon(a["poligono"], a.get("furos") or []).buffer(0)
            novo = shapely.union_all([P, meia]).buffer(0.05, join_style="mitre").buffer(-0.05, join_style="mitre")
            if novo.geom_type != "Polygon":
                novo = max(novo.geoms, key=lambda g: g.area)
            novo = novo.simplify(0.01)
            ganho = (novo.area - P.area) * m * m
            borda = novo.exterior
            aberto = borda.intersection(eixo.buffer(0.6, cap_style="flat")).length * m
            a["poligono"] = [(round(x, 2), round(y, 2)) for x, y in novo.exterior.coords]
            a["furos"] = [[(round(x, 2), round(y, 2)) for x, y in h.coords] for h in novo.interiors]
            a["area_m2"] = novo.area * m * m
            a["area_piso_m2"] = a["area_teto_m2"] = a["area_m2"]
            a["perimetro_m"] = novo.exterior.length * m
            a["sem_parede_m"] = (a.get("sem_parede_m") or 0) + aberto
            a["perimetro_parede_m"] = max(a["perimetro_m"] - a["sem_parede_m"], 0)
            a["vaos"] = [x for x in a.get("vaos", []) if x not in vaos_rem]
            a["alteracao_area_m2"] = round(a.get("alteracao_area_m2", 0) + ganho, 4)
            esperado = (a["area_rotulo_m2"] or 0) + a["alteracao_area_m2"]
            if esperado:
                a["divergencia_pct"] = round((a["area_m2"] / esperado - 1) * 100, 2)
            nota = f"Alteração de projeto: {regra.get('descricao', 'parede removida')} (+{ganho:.3f} m² de piso, divisa aberta)."
            if nota not in (a.get("observacao") or ""):
                a["observacao"] = ((a.get("observacao") or "") + " " + nota).strip()
            acrescimos[a["nome"]] = round(acrescimos.get(a["nome"], 0) + ganho, 4)
        # etiquetas dos vãos removidos
        etiquetas = []
        for y in p["vaos"]:
            xv = por_vao.get(y["vao"], {})
            xy = xv.get("etiqueta_xy")
            if xy:
                for k, et in enumerate(dados["esquadrias"]):
                    if et["vista"] == vid and et["xy"] == xy:
                        etiquetas.append(dados["esquadrias"].pop(k))
                        break
        registro.append({"vista": vid, "pavimento": p["pavimento"], "parede": p["id"], "tipo": p["tipo"],
                         "comprimento_m": p["comprimento_m"], "lados": p["lado_a"] + p["lado_b"],
                         "vaos": [(y["vao"], y["tipo"], y["largura_m"]) for y in p["vaos"]],
                         "etiquetas": [f'{et["tipo"]} {et["largura_m"]:.2f}×{et["altura_m"]:.2f}' for et in etiquetas],
                         "piso_acrescido_m2": acrescimos, "regra": regra.get("descricao", "")})
    # tira paredes e vãos; recalcula o encontro das paredes que encostavam nas removidas
    removidas = [p for p, _ in remover]
    for a in dados["ambientes"]:
        if a.get("vaos"):
            a["vaos"] = [x for x in a["vaos"] if x not in vaos_rem]
    dados["paredes"] = [p for p in dados["paredes"] if p["id"] not in ids_rem]
    dados["vaos"] = [x for x in dados["vaos"] if x["id"] not in vaos_rem]
    for p in removidas:
        m = m_vista[p["vista"]]
        eixo = LineString([p["eixo"][:2], p["eixo"][2:]])
        resto = [q for q in dados["paredes"] if q["vista"] == p["vista"]]
        for q in resto:
            for lado, (x, y) in (("a", q["eixo"][:2]), ("b", q["eixo"][2:])):
                if Point(x, y).distance(eixo) <= (q["espessura_m"] + p["espessura_m"]) / m / 2 + 1:
                    q["encontros"][lado] = _encontro(q, x, y, resto, m)
    return registro
