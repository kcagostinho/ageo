"""B3 — insumos da alvenaria e dos revestimentos, a partir do modelo de paredes, da paginação
(família escolhida) e dos quantitativos por ambiente.

Cada linha = base medida no modelo × coeficiente × (1 + perda). Coeficientes e perdas são
premissas editáveis na planilha (o cálculo vira fórmula lá).
"""
from __future__ import annotations

import math
from collections import Counter

from .paginacao import FAMILIAS, VEDACAO

# premissas padrão (editáveis na planilha)
P = {
    "perda_bloco": 0.05, "perda_canaleta": 0.05, "perda_argamassa": 0.15, "perda_graute": 0.10, "perda_aco": 0.10,
    "perda_revest": 0.10,
    # argamassa: 2 cordões nas faces do bloco, junta de 1 cm, juntas verticais preenchidas
    "cordao_estrutural_m": 0.06, "cordao_vedacao_m": 0.05, "junta_m": 0.01,
    # graute
    "graute_canaleta14_m3_m": 0.0135, "graute_canaleta9_m3_m": 0.0075, "graute_furo_m3_m": 0.013, "furos_por_ponto": 1,
    # aço (kg/m: Ø6,3 0,245 · Ø8 0,395 · Ø10 0,617 · Ø12,5 0,963)
    "cinta_barras": 2, "cinta_kg_m": 0.617, "verga_barras": 2, "verga_kg_m": 0.395,
    "vertical_barras": 1, "vertical_kg_m": 0.617, "transpasse_m": 0.40,
    "verga_ved_barras": 2, "verga_ved_kg_m": 0.245,
    # amarração vedação × estrutural
    "tela_a_cada_fiadas": 2,
    # revestimentos
    "gesso_parede_mm": 5, "gesso_teto_mm": 3, "gesso_kg_m2_mm": 1.1,
    "ceramica_banheiro_altura_m": None,      # None = até o teto
    "ceramica_cozinha_altura_m": 1.50,
    "laje_m": 0.15, "platibanda_m": 1.20, "platibanda_faces": 2,
}


def _pontos_verticais(paredes: list[dict], m_por_pt: float) -> tuple[int, int]:
    """Pontos de graute vertical nas paredes estruturais: encontros (L/T/X, contados uma vez),
    pontas livres e as duas laterais de cada vão. Devolve (pontos, encontros vedação×estrutural)."""
    est = [p for p in paredes if p["tipo"] == "estrutural"]
    ved = [p for p in paredes if p["tipo"] == "vedação"]
    pontas = []
    for p in est:
        e = p["eixo"]
        for lado, (x, y) in (("a", e[:2]), ("b", e[2:])):
            pontas.append((x, y, p["o"], p["encontros"][lado]))
    # agrupa pontas próximas: cada grupo é um nó
    nos = []
    for x, y, o, tp in pontas:
        for n in nos:
            if abs(n["x"] - x) <= 4 and abs(n["y"] - y) <= 4:
                n["os"].add(o); n["tipos"].append(tp); break
        else:
            nos.append({"x": x, "y": y, "os": {o}, "tipos": [tp]})
    encontros = sum(1 for n in nos if len(n["os"]) == 2 or any(t in ("T", "X") for t in n["tipos"]))
    livres = sum(1 for n in nos if n["tipos"] == ["livre"])
    jambas = 2 * sum(len(p["vaos"]) for p in est)
    # vedação que chega em estrutural (precisa de tela/grampo)
    mistos = 0
    for p in ved:
        e = p["eixo"]
        for lado, (x, y) in (("a", e[:2]), ("b", e[2:])):
            if p["encontros"][lado] not in ("L", "T", "X"):
                continue
            for q in est:
                f = q["eixo"]
                if q["o"] == "h" and min(f[0], f[2]) - 3 <= x <= max(f[0], f[2]) + 3 and abs(y - f[1]) <= 6:
                    mistos += 1; break
                if q["o"] == "v" and min(f[1], f[3]) - 3 <= y <= max(f[1], f[3]) + 3 and abs(x - f[0]) <= 6:
                    mistos += 1; break
    return encontros + livres + jambas, mistos


def calcular(dados: dict, familia: str = "39") -> dict:
    fam = FAMILIAS[familia]
    pd = dados["premissas"]["pe_direito_m"]
    pag = dados["paginacao"][familia]["por_pavimento"]
    m = {v["id"]: v["m_por_pt"] for v in dados["vistas"]}
    pav_alv = list(pag.keys())                       # pavimentos paginados (estrutural/vedação)
    tot = Counter()
    for c in pag.values():
        tot.update(c)
    Pp = fam["passo"]

    # áreas líquidas de parede por tipo (comprimento pelo eixo × pé-direito − vãos)
    def area(tipo, pavs):
        a = 0.0
        for p in dados["paredes"]:
            if p["tipo"] == tipo and p["pavimento"] in pavs:
                a += p["comprimento_m"] * pd.get(p["pavimento"], 2.6) - sum(
                    v["largura_m"] * (v.get("altura_m") or 2.1) for v in p["vaos"])
        return a
    a_est, a_ved = area("estrutural", pav_alv), area("vedação", pav_alv)
    L_ved = sum(p["comprimento_m"] for p in dados["paredes"] if p["tipo"] == "vedação" and p["pavimento"] in pav_alv)

    pontos, mistos = 0, 0
    for v in dados["vistas"]:
        if v["titulo"] not in pav_alv:
            continue
        a, b = _pontos_verticais([p for p in dados["paredes"] if p["vista"] == v["id"]], m[v["id"]])
        pontos += a; mistos += b
    alt_media = sum(pd.get(t, 2.6) for t in pav_alv) / max(len(pav_alv), 1)
    fiadas = round(alt_media / 0.20)

    # revestimentos por ambiente (quantitativos já trazem parede líquida e teto)
    gesso_par = gesso_teto = cer_ban = cer_coz = pint_varanda = 0.0
    for q in dados["quantitativos"]:
        if q["tipo"] in ("garagem", "técnico") or q["pavimento"].lower().startswith("sub"):
            continue
        nome = q["ambiente"].lower()
        liq = q["parede_liquida_m2"]
        if q["tipo"] == "externa":
            pint_varanda += liq
            continue
        gesso_teto += q["teto_m2"]
        if "banheiro" in nome or "lavabo" in nome or "wc" in nome:
            h = P["ceramica_banheiro_altura_m"]
            c = liq if h is None else min(liq, q["perimetro_parede_m"] * h)
            cer_ban += c; gesso_par += liq - c
        elif "cozinha" in nome or "á.s." in nome or "serviço" in nome:
            h = P["ceramica_cozinha_altura_m"]
            c = min(liq, q["perimetro_parede_m"] * h - q["larg_portas_m"] * h)
            cer_coz += c; gesso_par += liq - c
        else:
            gesso_par += liq

    # fachada: paredes com um lado para o exterior (tipos + térreo), altura do pavimento + borda da laje
    fach = vaos_fach = 0.0
    per_topo = 0.0
    ult = pav_alv[-1] if pav_alv else None
    for p in dados["paredes"]:
        if not p["fachada"] or p["tipo"] in ("muro", "concreto") or p["pavimento"].lower().startswith("sub"):
            continue
        h = pd.get(p["pavimento"], 2.6) + P["laje_m"]
        fach += p["comprimento_m"] * h
        vaos_fach += sum(v["largura_m"] * (v.get("altura_m") or 2.1) for v in p["vaos"])
        if p["pavimento"] == ult:
            per_topo += p["comprimento_m"]
    platib = per_topo * P["platibanda_m"] * P["platibanda_faces"]

    g = lambda k: tot.get(k, 0)
    est = "Estrutural 14 cm (fam. " + familia + ")"
    linhas = [
        # grupo, insumo, unid, base descr, base, unid base, coef, unid coef, perda, nota
        (est, f"Bloco {fam['inteiro']}", "un", "paginação", g(fam["inteiro"]), "un", 1, "", P["perda_bloco"], ""),
        (est, f"Meio bloco {fam['meio']}", "un", "paginação", g(fam["meio"]), "un", 1, "", P["perda_bloco"], ""),
        (est, f"Bloco de amarração L {fam['L'][0]}", "un", "paginação", g(fam["L"][0]), "un", 1, "", P["perda_bloco"], "Cantos"),
        (est, f"Bloco de amarração T {fam['T'][0]}", "un", "paginação", g(fam["T"][0]), "un", 1, "", P["perda_bloco"],
         f"{g('amarração T sem bloco especial (junto a vão)'):.0f} encontros T junto a vão ficam com grampo/tela"),
        (est, f"Canaleta J 14×19×{Pp - 1}", "un", "paginação", g(f"canaleta J 14×19×{Pp - 1}"), "un", 1, "", P["perda_canaleta"], "Cinta de respaldo na fachada"),
        (est, f"Meia canaleta J 14×19×{Pp // 2 - 1}", "un", "paginação", g(f"meia canaleta J 14×19×{Pp // 2 - 1}"), "un", 1, "", P["perda_canaleta"], ""),
        (est, f"Canaleta U 14×19×{Pp - 1}", "un", "paginação", g(f"canaleta U 14×19×{Pp - 1}"), "un", 1, "", P["perda_canaleta"], "Cinta interna, vergas, contravergas"),
        (est, f"Meia canaleta U 14×19×{Pp // 2 - 1}", "un", "paginação", g(f"meia canaleta U 14×19×{Pp // 2 - 1}"), "un", 1, "", P["perda_canaleta"], ""),
        (est, "Blocos para cortes/compensadores", "un", "cortes na paginação", g("cortes (peças)"), "peças", 1, "bloco/peça", 0,
         "Cai muito se portas/janelas forem moduladas"),
        ("Vedação 9 cm", f"Bloco {VEDACAO['inteiro']}", "un", "paginação", g(VEDACAO["inteiro"]), "un", 1, "", P["perda_bloco"], ""),
        ("Vedação 9 cm", f"Meio bloco {VEDACAO['meio']}", "un", "paginação", g(VEDACAO["meio"]), "un", 1, "", P["perda_bloco"], ""),
        ("Vedação 9 cm", "Canaleta U 9×19×39", "un", "paginação", g("canaleta U 9×19×39"), "un", 1, "", P["perda_canaleta"], "Vergas e contravergas"),
        ("Vedação 9 cm", "Meia canaleta U 9×19×19", "un", "paginação", g("meia canaleta U 9×19×19"), "un", 1, "", P["perda_canaleta"], ""),
        ("Argamassa de assentamento", "Argamassa — alvenaria estrutural", "m³", "área líquida de parede estrutural", a_est, "m²",
         round(5 * P["cordao_estrutural_m"] * P["junta_m"] + 12.5 * 0.19 * P["cordao_estrutural_m"] * P["junta_m"], 5), "m³/m²",
         P["perda_argamassa"], "2 cordões de 3 cm, junta 1 cm, juntas verticais preenchidas"),
        ("Argamassa de assentamento", "Argamassa — vedação", "m³", "área líquida de parede de vedação", a_ved, "m²",
         round(5 * P["cordao_vedacao_m"] * P["junta_m"] + 12.5 * 0.19 * P["cordao_vedacao_m"] * P["junta_m"], 5), "m³/m²",
         P["perda_argamassa"], "2 cordões de 2,5 cm, junta 1 cm"),
        ("Graute", "Graute — cinta de respaldo", "m³", "cinta de respaldo", g("cinta de respaldo (m)"), "m", P["graute_canaleta14_m3_m"], "m³/m", P["perda_graute"], ""),
        ("Graute", "Graute — vergas e contravergas (estrutural)", "m³", "vergas + contravergas em parede estrutural",
         g("vergas estrutural (m)") + g("contravergas estrutural (m)"), "m", P["graute_canaleta14_m3_m"], "m³/m", P["perda_graute"], "Inclui cinta das muretas das varandas"),
        ("Graute", "Graute — pontos verticais", "m³", f"{pontos} pontos × {alt_media:.2f} m", pontos * alt_media, "m de furo",
         P["graute_furo_m3_m"] * P["furos_por_ponto"], "m³/m", P["perda_graute"],
         "Cantos, encontros, pontas livres e laterais de vãos (1 furo cada) — o cálculo estrutural define os pontos"),
        ("Graute", "Graute — vergas e contravergas (vedação)", "m³", "vergas + contravergas em vedação",
         g("vergas vedação (m)") + g("contravergas vedação (m)"), "m", P["graute_canaleta9_m3_m"], "m³/m", P["perda_graute"], ""),
        ("Aço", "Aço Ø10 — cintas", "kg", "cinta de respaldo", g("cinta de respaldo (m)"), "m", P["cinta_barras"] * P["cinta_kg_m"], "kg/m",
         P["perda_aco"], "2 barras Ø10"),
        ("Aço", "Aço Ø8 — vergas e contravergas (estrutural)", "kg", "vergas + contravergas em parede estrutural",
         g("vergas estrutural (m)") + g("contravergas estrutural (m)"), "m", P["verga_barras"] * P["verga_kg_m"], "kg/m", P["perda_aco"], "2 barras Ø8"),
        ("Aço", "Aço Ø10 — pontos verticais", "kg", f"{pontos} pontos × ({alt_media:.2f} + {P['transpasse_m']:.2f} m de transpasse)",
         pontos * (alt_media + P["transpasse_m"]), "m", P["vertical_barras"] * P["vertical_kg_m"], "kg/m", P["perda_aco"], "1 barra Ø10 por ponto"),
        ("Aço", "Aço Ø6,3 — vergas e contravergas (vedação)", "kg", "vergas + contravergas em vedação",
         g("vergas vedação (m)") + g("contravergas vedação (m)"), "m", P["verga_ved_barras"] * P["verga_ved_kg_m"], "kg/m", P["perda_aco"], "2 barras Ø6,3"),
        ("Amarração e fixação", "Tela/grampo de amarração vedação × estrutural", "un", f"{mistos} encontros × {fiadas} fiadas",
         mistos, "encontros", math.floor(fiadas / P["tela_a_cada_fiadas"]), "un/encontro", P["perda_revest"], "1 tela a cada 2 fiadas"),
        ("Amarração e fixação", "Encunhamento das paredes de vedação", "m", "comprimento das paredes de vedação", L_ved, "m", 1, "", 0.05,
         "Argamassa expansiva ou espuma (definir)"),
        ("Revestimento interno", "Fundo preparador (paredes + tetos)", "m²", "área de gesso em paredes e tetos", gesso_par + gesso_teto, "m²", 1, "", P["perda_revest"], ""),
        ("Revestimento interno", "Gesso liso — paredes", "m²", "parede líquida dos ambientes (sem cerâmica)", gesso_par, "m²", 1, "", P["perda_revest"], ""),
        ("Revestimento interno", "Gesso liso — tetos", "m²", "teto dos ambientes internos", gesso_teto, "m²", 1, "", P["perda_revest"], ""),
        ("Revestimento interno", "Gesso em pó — paredes", "kg", f"gesso em paredes, {P['gesso_parede_mm']} mm", gesso_par, "m²",
         P["gesso_parede_mm"] * P["gesso_kg_m2_mm"], "kg/m²", P["perda_revest"], "Consumo ~1,1 kg/m² por mm (confirmar com fornecedor)"),
        ("Revestimento interno", "Gesso em pó — tetos", "kg", f"gesso em tetos, {P['gesso_teto_mm']} mm", gesso_teto, "m²",
         P["gesso_teto_mm"] * P["gesso_kg_m2_mm"], "kg/m²", P["perda_revest"], ""),
        ("Revestimento interno", "Cerâmica de parede — banheiros (até o teto)", "m²", "parede líquida dos banheiros", cer_ban, "m²", 1, "", P["perda_revest"],
         "Premissa: altura da cerâmica ainda não informada"),
        ("Revestimento interno", "Cerâmica de parede — cozinhas/A.S. (até 1,50 m)", "m²", "contorno × 1,50 m − portas", cer_coz, "m²", 1, "", P["perda_revest"],
         "Premissa: altura da cerâmica ainda não informada"),
        ("Revestimento externo", "Pintura projetada direto no bloco — fachadas", "m²", "fachada (pavimento + borda da laje) − vãos",
         fach - vaos_fach, "m²", 1, "", P["perda_revest"], "Térreo incluso; subsolo fora"),
        ("Revestimento externo", "Pintura projetada — paredes das varandas", "m²", "parede líquida das varandas gourmet", pint_varanda, "m²", 1, "",
         P["perda_revest"], "Premissa: mesmo acabamento da fachada"),
        ("Revestimento externo", "Pintura projetada — platibanda", "m²", f"perímetro do topo × {P['platibanda_m']:.2f} m × {P['platibanda_faces']} faces",
         platib, "m²", 1, "", P["perda_revest"], "Caixa d'água e casa de máquinas a confirmar"),
    ]
    return {"familia": familia, "pavimentos": pav_alv, "premissas": P, "linhas": linhas,
            "indicadores": {"area_estrutural_m2": a_est, "area_vedacao_m2": a_ved, "pontos_verticais": pontos,
                            "encontros_mistos": mistos, "fachada_bruta_m2": fach, "vaos_fachada_m2": vaos_fach}}
