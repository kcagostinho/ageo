"""B4 — preço da alvenaria e dos revestimentos com o SINAPI (Caixa) e rateio do custo pelos
elementos do modelo (paredes, ambientes, cobertura) para o 3D-4.

Como cada item é preçado:
  - material contado no modelo (blocos, canaletas, argamassa, tela): quantidade da B3 (com perda)
    × preço do insumo SINAPI;
  - mão de obra da alvenaria: área líquida × (pedreiro + servente + equipamento) tirados da
    composição SINAPI de alvenaria, sem os materiais (que já vêm da paginação);
  - graute, armação, encunhamento e revestimentos: quantidade medida (sem perda, porque o
    coeficiente SINAPI já tem perda) × custo da composição SINAPI completa.

O rateio usa um "direcionador" por linha (peças da paginação, área de parede, faces dos
ambientes, área de teto...). A soma do que vai para cada elemento é igual ao total da linha.
"""
from __future__ import annotations

import math
import unicodedata
from collections import defaultdict

# blocos 14×19×39 por fbk (SINAPI): o fbk de cada pavimento muda o preço de todas as peças estruturais
FBK_INTEIRO = {4.5: 25070, 6: 34571, 8: 34573, 10: 34568, 12: 34569, 14: 34570, 16: 37107}

# referências de preço: id → (tipo, código, descrição curta, fator, fbk?, observação)
#   tipo: "I" insumo · "C" composição completa · "MO" só mão de obra + equipamento da composição
#         "D" derivado de outra referência (código = id da base) × fator
REFS = {
    "B14":   ("I", 25070, "Bloco de concreto estrutural 14×19×39, fbk 4,5 MPa", 1, True, ""),
    "M14":   ("I", 38589, "Meio bloco estrutural 14×19×19, fbk 4,5 MPa", 1, True, ""),
    "L14":   ("I", 38591, "Bloco estrutural 14×19×34 (amarração L), fbk 4,5 MPa", 1, True, ""),
    "T14":   ("D", "B14", "Bloco 14×19×54 (amarração T)", 54 / 39, True, "Sem preço no SINAPI: proporcional ao comprimento (54/39 do inteiro). Cotar."),
    "U14":   ("I", 38597, "Canaleta estrutural 14×19×39, fbk 4,5 MPa", 1, True, ""),
    "MU14":  ("I", 38595, "Meia canaleta estrutural 14×19×19, fbk 4,5 MPa", 1, True, ""),
    "J14":   ("D", "U14", "Canaleta J 14×19×39", 1, True, "Sem preço no SINAPI: igual à canaleta U × fator da canaleta J (Premissas). Cotar."),
    "MJ14":  ("D", "MU14", "Meia canaleta J 14×19×19", 1, True, "Sem preço no SINAPI: igual à meia canaleta U × fator da canaleta J. Cotar."),
    "B9":    ("I", 650, "Bloco de vedação de concreto 9×19×39 (classe C)", 1, False, ""),
    "M9":    ("I", 34764, "Meio bloco de vedação 9×19×19 (classe C)", 1, False, ""),
    "MU9":   ("I", 658, "Canaleta de concreto 9×19×19 (classe C)", 1, False, ""),
    "U9":    ("D", "MU9", "Canaleta 9×19×39", 2, False, "Sem preço no SINAPI: 2 × canaleta 9×19×19. Cotar."),
    "ARG_E": ("C", 87286, "Argamassa 1:1:6 (cimento, cal, areia), betoneira", 1, False, "A mesma da composição SINAPI de alvenaria estrutural"),
    "ARG_V": ("C", 87292, "Argamassa 1:2:8 (cimento, cal, areia), betoneira", 1, False, "A mesma da composição SINAPI de alvenaria de vedação"),
    "TELA":  ("D", "TELA_M", "Tela de aço galvanizada 50×7,5 cm (peça de 0,50 m)", 0.5, False, ""),
    "TELA_M": ("I", 34557, "Tela de aço soldada galvanizada para alvenaria, 50×7,5 cm (por m)", 1, False, ""),
    "MO_E":  ("MO", 89453, "Mão de obra + equipamento: alvenaria estrutural de blocos de concreto 14×19×39 (palheta)", 1, False,
              "Pedreiro e servente da composição SINAPI; blocos e argamassa entram pela paginação"),
    "MO_V":  ("MO", 103316, "Mão de obra + equipamento: alvenaria de vedação de blocos de concreto 9×19×39", 1, False,
              "Pedreiro e servente da composição SINAPI; blocos, argamassa e tela entram pela paginação"),
    "ENC":   ("C", 93200, "Fixação (encunhamento) com argamassa aplicada com bisnaga", 1, False, ""),
    "GR_C":  ("C", 89995, "Grauteamento de cinta superior ou verga, fgk 20 MPa", 1, False, ""),
    "GR_V":  ("C", 89993, "Grauteamento vertical, fgk 20 MPa", 1, False, ""),
    "A_C10": ("C", 89998, "Armação de cinta, Ø10,0 mm", 1, False, ""),
    "A_V8":  ("C", 89999, "Armação de verga e contraverga, Ø8,0 mm", 1, False, ""),
    "A_P10": ("C", 89996, "Armação vertical, Ø10,0 mm", 1, False, ""),
    "A_V63": ("C", 107138, "Armação de verga e contraverga, Ø6,3 mm", 1, False, ""),
    "FP_P":  ("C", 88485, "Fundo selador acrílico em parede, uma demão (fundo preparador)", 1, False, "Equivalente ao fundo preparador especificado. Cotar o produto."),
    "FP_T":  ("C", 88484, "Fundo selador acrílico em teto, uma demão (fundo preparador)", 1, False, "Equivalente ao fundo preparador especificado. Cotar o produto."),
    "GS_P":  ("C", 87418, "Gesso desempenado em paredes, 0,5 cm, manual", 1, False, ""),
    "GS_T1": ("C", 87413, "Gesso desempenado em teto, ambiente < 5 m², 0,5 cm", 1, False, ""),
    "GS_T2": ("C", 87412, "Gesso desempenado em teto, ambiente 5 a 10 m², 0,5 cm", 1, False, ""),
    "GS_T3": ("C", 87411, "Gesso desempenado em teto, ambiente > 10 m², 0,5 cm", 1, False, ""),
    "CHAP":  ("C", 87879, "Chapisco em alvenaria interna, traço 1:3", 1, False, "Base para cerâmica (premissa)"),
    "EMB":   ("C", 87557, "Emboço industrializado projetado, paredes internas, 10 mm", 1, False, "Base para cerâmica (premissa)"),
    "CER_I": ("C", 87273, "Cerâmica esmaltada 33×45 cm na altura inteira da parede", 1, False, "Formato a confirmar no memorial"),
    "CER_M": ("C", 87275, "Cerâmica esmaltada 33×45 cm a meia altura da parede", 1, False, "Formato a confirmar no memorial"),
    "SEL_F": ("C", 88411, "Fundo selador acrílico, fachada com vãos, edifício de múltiplos pavimentos", 1, False, ""),
    "PIN_F": ("C", 88416, "Tinta texturizada acrílica, fachada com vãos, uma cor", 1, False,
              "SINAPI só tem aplicação manual; a pintura projetada direto no bloco deve ser cotada com a empreiteira"),
    "SEL_S": ("C", 88414, "Fundo selador acrílico, superfícies internas da sacada", 1, False, ""),
    "PIN_S": ("C", 88421, "Tinta texturizada acrílica, superfícies internas da sacada, uma cor", 1, False, ""),
    "SEL_C": ("C", 88412, "Fundo selador acrílico, panos cegos de fachada", 1, False, ""),
    "PIN_C": ("C", 88417, "Tinta texturizada acrílica, panos cegos de fachada, uma cor", 1, False, ""),
}

# linhas do orçamento: (grupo, item, unidade, quantidade, ref, direcionador, observação)
#   quantidade: ("B3", nome do insumo na B3, "com"|"sem" perda)  ou  ("calc", chave)  ou  ("soma", [(nome, "sem"), ...])
G_E, G_V, G_G, G_A, G_RI, G_RE = ("Alvenaria estrutural", "Alvenaria de vedação", "Graute", "Armação",
                                   "Revestimento interno", "Revestimento externo")
LINHAS = [
    (G_E, "Bloco 14×19×39", "un", ("B3", "Bloco 14×19×39", "com"), "B14", "pc:14×19×39", ""),
    (G_E, "Meio bloco 14×19×19", "un", ("B3", "Meio bloco 14×19×19", "com"), "M14", "pc:14×19×19", ""),
    (G_E, "Bloco de amarração L 14×19×34", "un", ("B3", "Bloco de amarração L 14×19×34", "com"), "L14", "pc:14×19×34", ""),
    (G_E, "Bloco de amarração T 14×19×54", "un", ("B3", "Bloco de amarração T 14×19×54", "com"), "T14", "pc:14×19×54", ""),
    (G_E, "Canaleta J 14×19×39", "un", ("B3", "Canaleta J 14×19×39", "com"), "J14", "pc:canaleta J 14×19×39", ""),
    (G_E, "Meia canaleta J 14×19×19", "un", ("B3", "Meia canaleta J 14×19×19", "com"), "MJ14", "pc:meia canaleta J 14×19×19", ""),
    (G_E, "Canaleta U 14×19×39", "un", ("B3", "Canaleta U 14×19×39", "com"), "U14", "pc:canaleta U 14×19×39", ""),
    (G_E, "Meia canaleta U 14×19×19", "un", ("B3", "Meia canaleta U 14×19×19", "com"), "MU14", "pc:meia canaleta U 14×19×19", ""),
    (G_E, "Blocos para cortes/compensadores", "un", ("B3", "Blocos para cortes/compensadores", "com"), "B14", "pc:cortes (peças)",
     "Inclui os cortes das paredes de vedação (contados como bloco 14)"),
    (G_E, "Argamassa de assentamento", "m³", ("B3", "Argamassa — alvenaria estrutural", "com"), "ARG_E", "area:estrutural", ""),
    (G_E, "Mão de obra de assentamento", "m²", ("calc", "area_estrutural"), "MO_E", "area:estrutural", "Área líquida (sem vãos)"),
    (G_V, "Bloco 9×19×39", "un", ("B3", "Bloco 9×19×39", "com"), "B9", "pc:9×19×39", ""),
    (G_V, "Meio bloco 9×19×19", "un", ("B3", "Meio bloco 9×19×19", "com"), "M9", "pc:9×19×19", ""),
    (G_V, "Canaleta U 9×19×39", "un", ("B3", "Canaleta U 9×19×39", "com"), "U9", "pc:canaleta U 9×19×39", ""),
    (G_V, "Meia canaleta U 9×19×19", "un", ("B3", "Meia canaleta U 9×19×19", "com"), "MU9", "pc:meia canaleta U 9×19×19", ""),
    (G_V, "Argamassa de assentamento", "m³", ("B3", "Argamassa — vedação", "com"), "ARG_V", "area:vedação", ""),
    (G_V, "Tela de amarração vedação × estrutural", "un", ("B3", "Tela/grampo de amarração vedação × estrutural", "com"), "TELA", "mistos", ""),
    (G_V, "Mão de obra de assentamento", "m²", ("calc", "area_vedacao"), "MO_V", "area:vedação", "Área líquida (sem vãos)"),
    (G_V, "Encunhamento (fixação na laje)", "m", ("B3", "Encunhamento das paredes de vedação", "sem"), "ENC", "comp:vedação", ""),
    (G_G, "Cinta de respaldo", "m³", ("B3", "Graute — cinta de respaldo", "sem"), "GR_C", "m:cinta", ""),
    (G_G, "Vergas e contravergas (estrutural)", "m³", ("B3", "Graute — vergas e contravergas (estrutural)", "sem"), "GR_C", "m:vg_est",
     "Contraverga com o custo de verga (SINAPI separa; diferença pequena)"),
    (G_G, "Pontos verticais", "m³", ("B3", "Graute — pontos verticais", "sem"), "GR_V", "pontos", ""),
    (G_G, "Vergas e contravergas (vedação)", "m³", ("B3", "Graute — vergas e contravergas (vedação)", "sem"), "GR_C", "m:vg_ved", ""),
    (G_A, "Cintas Ø10", "kg", ("B3", "Aço Ø10 — cintas", "sem"), "A_C10", "m:cinta", "Corte, dobra e montagem"),
    (G_A, "Vergas e contravergas Ø8 (estrutural)", "kg", ("B3", "Aço Ø8 — vergas e contravergas (estrutural)", "sem"), "A_V8", "m:vg_est", ""),
    (G_A, "Pontos verticais Ø10", "kg", ("B3", "Aço Ø10 — pontos verticais", "sem"), "A_P10", "pontos", ""),
    (G_A, "Vergas e contravergas Ø6,3 (vedação)", "kg", ("B3", "Aço Ø6,3 — vergas e contravergas (vedação)", "sem"), "A_V63", "m:vg_ved", ""),
    (G_RI, "Fundo preparador — paredes", "m²", ("B3", "Gesso liso — paredes", "sem"), "FP_P", "f:gesso", ""),
    (G_RI, "Gesso liso — paredes (5 mm)", "m²", ("B3", "Gesso liso — paredes", "sem"), "GS_P", "f:gesso", ""),
    (G_RI, "Fundo preparador — tetos", "m²", ("B3", "Gesso liso — tetos", "sem"), "FP_T", "t:todos", ""),
    (G_RI, "Gesso liso — tetos de ambientes < 5 m²", "m²", ("calc", "teto_1"), "GS_T1", "t:1", "Espessura 0,5 cm (a B3 usa 3 mm; menor composição SINAPI)"),
    (G_RI, "Gesso liso — tetos de ambientes de 5 a 10 m²", "m²", ("calc", "teto_2"), "GS_T2", "t:2", ""),
    (G_RI, "Gesso liso — tetos de ambientes > 10 m²", "m²", ("calc", "teto_3"), "GS_T3", "t:3", ""),
    (G_RI, "Chapisco sob a cerâmica", "m²", ("soma", [("Cerâmica de parede — banheiros (até o teto)", "sem"),
                                                     ("Cerâmica de parede — cozinhas/A.S. (até 1,50 m)", "sem")]), "CHAP", "f:cer",
     "Premissa: cerâmica sobre emboço"),
    (G_RI, "Emboço 10 mm sob a cerâmica", "m²", ("soma", [("Cerâmica de parede — banheiros (até o teto)", "sem"),
                                                         ("Cerâmica de parede — cozinhas/A.S. (até 1,50 m)", "sem")]), "EMB", "f:cer",
     "Premissa: cerâmica sobre emboço"),
    (G_RI, "Cerâmica — banheiros (altura inteira)", "m²", ("B3", "Cerâmica de parede — banheiros (até o teto)", "sem"), "CER_I", "f:ban", ""),
    (G_RI, "Cerâmica — cozinhas/A.S. (até 1,50 m)", "m²", ("B3", "Cerâmica de parede — cozinhas/A.S. (até 1,50 m)", "sem"), "CER_M", "f:coz", ""),
    (G_RE, "Fundo selador — fachadas", "m²", ("B3", "Pintura projetada direto no bloco — fachadas", "sem"), "SEL_F", "fachada", ""),
    (G_RE, "Pintura texturizada — fachadas", "m²", ("B3", "Pintura projetada direto no bloco — fachadas", "sem"), "PIN_F", "fachada", ""),
    (G_RE, "Fundo selador — paredes das varandas", "m²", ("B3", "Pintura projetada — paredes das varandas", "sem"), "SEL_S", "f:var", ""),
    (G_RE, "Pintura texturizada — paredes das varandas", "m²", ("B3", "Pintura projetada — paredes das varandas", "sem"), "PIN_S", "f:var", ""),
    (G_RE, "Fundo selador — platibanda", "m²", ("B3", "Pintura projetada — platibanda", "sem"), "SEL_C", "platibanda", ""),
    (G_RE, "Pintura texturizada — platibanda", "m²", ("B3", "Pintura projetada — platibanda", "sem"), "PIN_C", "platibanda", ""),
]

PREMISSAS = {"desonerado": False, "bdi": 0.0, "fator_canaleta_j": 1.0, "padrao_cub": "R8-N"}


def fbk_padrao(pavimentos: list[str]) -> dict:
    """Até o projeto estrutural: 8 MPa nos dois primeiros pavimentos de alvenaria, 6 no terceiro, 4,5 acima."""
    return {p: (8 if i < 2 else 6 if i == 2 else 4.5) for i, p in enumerate(pavimentos)}


def _sem_acento(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def _cat_ambiente(nome: str, tipo: str) -> str | None:
    """Mesma regra da B3: banheiro → cerâmica até o teto; cozinha/A.S. → cerâmica até 1,50 m; varanda → pintura."""
    if tipo in ("garagem", "técnico"):
        return None
    if tipo == "externa":
        return "var"
    n = _sem_acento(nome)
    if "banheiro" in n or "lavabo" in n or "wc" in n:
        return "ban"
    if "cozinha" in n or "a.s." in n or "servico" in n:
        return "coz"
    return "gesso"


# ---------------------------------------------------------------- preços
def _custo_mo(sin, cod, k):
    """Mão de obra + equipamento de uma composição (k = 2 sem desoneração, 3 com)."""
    C = sin["composicoes"]
    tot = 0.0
    for t, item, coef in sin["analitico"].get(str(cod), []):
        if t != "C" or coef is None:
            continue
        reg = C.get(str(item))
        if not reg:
            continue
        d = reg[0].upper()
        if "COM ENCARGOS COMPLEMENTARES" in d or " CHP " in f" {d} " or " CHI " in f" {d} " or "- CHP" in d or "- CHI" in d:
            tot += coef * (reg[k] or 0)
    return tot


def precos(sin: dict, prem: dict) -> dict:
    """id → {descr, un, tipo, cod, sd, cd, fator, fbk, obs, fonte}."""
    I, C = sin["insumos"], sin["composicoes"]
    out = {}
    def um(rid):
        if rid in out:
            return out[rid]
        tipo, cod, descr, fator, fbk, obs = REFS[rid]
        if rid in ("J14", "MJ14"):
            fator = prem.get("fator_canaleta_j", 1.0)
        if tipo == "I":
            r = I[str(cod)]
            sd, cd, un, fonte = r[2], r[3], r[1], f"SINAPI insumo {cod}"
        elif tipo == "C":
            r = C[str(cod)]
            sd, cd, un, fonte = r[2], r[3], r[1], f"SINAPI composição {cod}"
        elif tipo == "MO":
            r = C[str(cod)]
            sd, cd, un, fonte = _custo_mo(sin, cod, 2), _custo_mo(sin, cod, 3), r[1], f"SINAPI composição {cod} (só mão de obra e equipamento)"
        else:
            b = um(cod)
            sd, cd, un = b["sd"] * fator, b["cd"] * fator, b["un"]
            fonte = f"derivado de {cod} × {fator:.3g}".replace(".", ",")
        out[rid] = {"id": rid, "descr": descr, "un": (un or "").lower(), "tipo": tipo, "cod": cod, "sd": sd, "cd": cd,
                    "fator": fator, "fbk": fbk, "obs": obs, "fonte": fonte}
        return out[rid]
    for rid in REFS:
        um(rid)
    return out


def fbk_tabela(sin: dict) -> list:
    I = sin["insumos"]
    return [[f, cod, I[str(cod)][2], I[str(cod)][3]] for f, cod in sorted(FBK_INTEIRO.items())]


# ---------------------------------------------------------------- direcionadores
def _seg_dist(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy or 1e-9
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def direcionadores(dados: dict, familia: str, det: list, fator_pav: dict) -> dict:
    """{chave: {elemento: valor}}; elemento = ("par", id) | ("amb", índice) | ("cob", "platibanda")."""
    from .insumos import pontos_verticais_xy
    from .quantitativos import classificar
    pd = dados["premissas"]["pe_direito_m"]
    pav_alv = list(dados["paginacao"][familia]["por_pavimento"].keys())
    vpav = {v["id"]: v["titulo"] for v in dados["vistas"]}
    m = {v["id"]: v["m_por_pt"] for v in dados["vistas"]}
    W = {p["id"]: p for p in dados["paredes"]}
    D = defaultdict(lambda: defaultdict(float))
    vao_area = lambda p: sum(v["largura_m"] * (v.get("altura_m") or 2.1) for v in p["vaos"])
    vao_larg = lambda p: sum(v["largura_m"] for v in p["vaos"])

    # peças e metros da paginação: linha → trechos (paredes) pelo comprimento; vergas pelos vãos
    for L in det:
        segs = [W[s] for s in L["segmentos"] if s in W]
        if not segs:
            continue
        tl = sum(s["comprimento_m"] for s in segs) or 1.0
        tv = sum(vao_larg(s) for s in segs)
        f = fator_pav.get(vpav[L["vista"]], 1.0) if L["tipo"] == "estrutural" else 1.0
        c = L["contagem"]
        vals = {k: v for k, v in c.items() if k.startswith(("14×", "9×", "canaleta", "meia canaleta")) or k == "cortes (peças)"}
        vg = {"vg_est": c.get("vergas estrutural (m)", 0) + c.get("contravergas estrutural (m)", 0),
              "vg_ved": c.get("vergas vedação (m)", 0) + c.get("contravergas vedação (m)", 0)}
        for s in segs:
            sh = s["comprimento_m"] / tl
            shv = vao_larg(s) / tv if tv > 0 else sh
            el = ("par", s["id"])
            for k, v in vals.items():
                D["pc:" + k][el] += v * sh * (f if L["tipo"] == "estrutural" else 1.0)
            D["m:cinta"][el] += c.get("cinta de respaldo (m)", 0) * sh
            for k, v in vg.items():
                D["m:" + k][el] += v * shv

    for p in dados["paredes"]:
        pav = p["pavimento"]
        h = pd.get(pav, 2.6)
        el = ("par", p["id"])
        liq = p["comprimento_m"] * h - vao_area(p)
        if pav in pav_alv and p["tipo"] in ("estrutural", "vedação"):
            D["area:" + p["tipo"]][el] += max(liq, 0)
            if p["tipo"] == "vedação":
                D["comp:vedação"][el] += p["comprimento_m"]
                n = sum(1 for k in ("a", "b") if p["encontros"][k] in ("L", "T", "X"))
                if n:
                    D["mistos"][el] += n
        if pav.lower().startswith("sub"):
            continue
        # fachada (pintura): pé-direito + borda da laje, menos vãos
        if p["fachada"] and p["tipo"] not in ("muro", "concreto"):
            D["fachada"][el] += max(p["comprimento_m"] * (h + 0.15) - vao_area(p), 0)
        # faces internas: cada lado vai para os ambientes que ele separa
        for lado in (p["lado_a"], p["lado_b"]):
            nomes = [x for x in lado if x != "exterior"]
            if not nomes:
                continue
            face = max(liq, 0) / len(nomes)
            for nome in nomes:
                cat = _cat_ambiente(nome, classificar(nome))
                if cat is None:
                    continue
                if cat == "coz":
                    portas = sum(v["largura_m"] for v in p["vaos"] if v["tipo"] == "porta")
                    baixo = min(face, max(p["comprimento_m"] - portas, 0) * 1.5 / len(nomes))
                    D["f:coz"][el] += baixo
                    D["f:cer"][el] += baixo
                    D["f:gesso"][el] += face - baixo
                elif cat == "ban":
                    D["f:ban"][el] += face
                    D["f:cer"][el] += face
                else:
                    D["f:" + cat][el] += face

    # pontos de graute vertical → parede estrutural mais próxima
    for v in dados["vistas"]:
        if v["titulo"] not in pav_alv:
            continue
        ps = [p for p in dados["paredes"] if p["vista"] == v["id"]]
        est = [p for p in ps if p["tipo"] == "estrutural"]
        for x, y, _ in pontos_verticais_xy(ps, m[v["id"]]):
            q = min(est, key=lambda p: _seg_dist((x, y), p["eixo"][:2], p["eixo"][2:]), default=None)
            if q:
                D["pontos"][("par", q["id"])] += 1

    # tetos: ambientes internos (mesma regra da B3) por faixa de área (composições SINAPI)
    qidx = {q["indice_ambiente"]: q for q in dados["quantitativos"]}
    for i, a in enumerate(dados["ambientes"]):
        q = qidx.get(i)
        if not q or q["tipo"] in ("garagem", "técnico", "externa") or q["pavimento"].lower().startswith("sub"):
            continue
        t = q["teto_m2"] or 0
        if t <= 0:
            continue
        faixa = 1 if a["area_m2"] < 5 else 2 if a["area_m2"] <= 10 else 3
        D[f"t:{faixa}"][("amb", i)] += t
        D["t:todos"][("amb", i)] += t
    D["platibanda"][("cob", "platibanda")] = 1.0
    return D


def area_construida(dados: dict) -> dict:
    """Área construída aproximada de cada pavimento (m²): ambientes cobertos (a área medida já
    desconta a parte descoberta da garagem) + projeção das paredes (comprimento × espessura)."""
    out = {}
    for v in dados["vistas"]:
        amb = sum(a["area_m2"] for a in dados["ambientes"] if a["vista"] == v["id"])
        par = sum(p["comprimento_m"] * p["espessura_m"] for p in dados["paredes"] if p["vista"] == v["id"] and p["tipo"] != "muro")
        if amb:
            out[v["titulo"]] = amb + par
    return out


# ---------------------------------------------------------------- cálculo
def calcular(dados: dict, sin: dict, cub: dict | None = None, prem: dict | None = None, fbk: dict | None = None) -> dict:
    from . import paginacao as PG
    prem = {**PREMISSAS, **(prem or {})}
    ins = dados["insumos"]
    familia = ins["familia"]
    k = 3 if prem["desonerado"] else 2
    P = precos(sin, prem)
    por_pav = dados["paginacao"][familia]["por_pavimento"]
    pav_alv = list(por_pav.keys())
    fbk = {**fbk_padrao(pav_alv), **(fbk or {})}
    I = sin["insumos"]
    base_fbk = I[str(FBK_INTEIRO[4.5])][k]
    fator_pav = {p: I[str(FBK_INTEIRO[fbk[p]])][k] / base_fbk for p in pav_alv}
    n_est = {p: sum(v for kk, v in c.items() if kk.startswith(("14×", "canaleta J 14", "meia canaleta J 14", "canaleta U 14", "meia canaleta U 14")))
             for p, c in por_pav.items()}
    fator_medio = sum(n_est[p] * fator_pav[p] for p in pav_alv) / max(sum(n_est.values()), 1)

    b3 = {l[1]: l for l in ins["linhas"]}
    b3_idx = {l[1]: i for i, l in enumerate(ins["linhas"])}

    def q_b3(nome, perda):
        l = b3[nome]
        q = l[4] * l[6]
        if perda == "com":
            q *= 1 + l[8]
            if l[2] == "un":
                q = math.ceil(q - 1e-9)
        return q

    # quantidades calculadas aqui (não estão na B3 com esse recorte)
    teto = defaultdict(float)
    qidx = {q["indice_ambiente"]: q for q in dados["quantitativos"]}
    for i, a in enumerate(dados["ambientes"]):
        q = qidx.get(i)
        if not q or q["tipo"] in ("garagem", "técnico", "externa") or q["pavimento"].lower().startswith("sub"):
            continue
        teto[1 if a["area_m2"] < 5 else 2 if a["area_m2"] <= 10 else 3] += q["teto_m2"] or 0
    calc = {"area_estrutural": ins["indicadores"]["area_estrutural_m2"], "area_vedacao": ins["indicadores"]["area_vedacao_m2"],
            "teto_1": teto[1], "teto_2": teto[2], "teto_3": teto[3]}

    linhas = []
    for g, item, un, qf, ref, dirk, obs in LINHAS:
        if qf[0] == "B3":
            if qf[1] not in b3:
                continue
            qtd = q_b3(qf[1], qf[2])
        elif qf[0] == "soma":
            qtd = sum(q_b3(n, p) for n, p in qf[1] if n in b3)
        else:
            qtd = calc[qf[1]]
        pr = P[ref][["", "", "sd", "cd"][k]]
        if P[ref]["fbk"]:
            pr *= fator_medio
        linhas.append({"grupo": g, "item": item, "un": un, "qtd": qtd, "qf": qf, "ref": ref, "preco": pr, "custo": qtd * pr,
                       "dir": dirk, "obs": obs or P[ref]["obs"]})

    # rateio
    _, det = PG.paginar(dados, familia, guardar_todas=True)
    D = direcionadores(dados, familia, det, fator_pav)
    par_pav = {p["id"]: p["pavimento"] for p in dados["paredes"]}
    amb_pav = {i: a["pavimento"] for i, a in enumerate(dados["ambientes"])}
    rateio = defaultdict(dict)                    # elemento → {índice da linha: R$}
    nao_rateado = 0.0
    for il, L in enumerate(linhas):
        d = D.get(L["dir"], {})
        tot = sum(d.values())
        L["partes"] = {}
        if tot <= 0 or L["custo"] == 0:
            nao_rateado += L["custo"]
            continue
        for el, v in d.items():
            val = L["custo"] * v / tot
            if val:
                rateio[el][il] = val
                pav = par_pav.get(el[1]) if el[0] == "par" else amb_pav.get(el[1]) if el[0] == "amb" else "Cobertura"
                L["partes"][pav] = L["partes"].get(pav, 0) + v / tot

    total = sum(L["custo"] for L in linhas)
    areas = area_construida(dados)
    pavs_orc = [v["titulo"] for v in dados["vistas"] if not v["titulo"].lower().startswith("sub")]
    area_orc = sum(areas.get(p, 0) for p in pavs_orc)
    area_total = sum(areas.values())
    cub_ref = None
    if cub:
        pc = cub["padroes"].get(prem["padrao_cub"]) or {}
        v = pc.get("cd" if prem["desonerado"] else "sd") or pc.get("sd")
        if v:
            cub_ref = {"padrao": prem["padrao_cub"], "mes": cub["mes"], "valor": v, "fonte": cub["fonte"],
                       "custo_ref": v * area_total, "padroes": cub["padroes"]}
    return {
        "mes": sin["mes"], "uf": sin["uf"], "premissas": prem, "fbk": fbk, "fator_pav": fator_pav, "fator_medio": fator_medio,
        "n_est": n_est, "fbk_tabela": fbk_tabela(sin), "precos": P, "linhas": linhas, "b3_idx": b3_idx,
        "rateio": {f"{a}|{b}": v for (a, b), v in rateio.items()}, "nao_rateado": nao_rateado,
        "total": total, "areas": areas, "area_orc": area_orc, "pavs_orc": pavs_orc, "area_total": area_total, "cub": cub_ref,
    }
