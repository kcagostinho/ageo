"""Fase 1 — medição: lê o PDF do projeto arquitetônico e gera obra.json, medicao.xlsx e conferencia.html.

Uso:
    python medir.py caminho/do/projeto.pdf --obra "Nome da obra" --saida obras/<obra>/saida
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import pymupdf
from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

sys.path.insert(0, str(Path(__file__).parent))
from leitor.ambientes import detectar, PREMISSA_VARANDA   # noqa: E402
from leitor.pe_direito import ler_pe_direito   # noqa: E402
from leitor import quantitativos as Q          # noqa: E402
from leitor import paredes as PAR              # noqa: E402
from leitor import saida_paredes as SP         # noqa: E402
from leitor import paginacao as PG             # noqa: E402
from leitor import saida_paginacao as SPG      # noqa: E402
from leitor import insumos as INS              # noqa: E402
from leitor import saida_insumos as SINS       # noqa: E402
from leitor import saida_3d as S3D             # noqa: E402
from leitor import cobertura as COB            # noqa: E402
from leitor import sinapi as SIN               # noqa: E402
from leitor import cub as CUB                  # noqa: E402
from leitor import orcamento as ORC            # noqa: E402
from leitor import saida_orcamento as SORC     # noqa: E402
from leitor import escada as ESC               # noqa: E402
from leitor import repeticao as REP            # noqa: E402
from leitor import conferencia as CONF         # noqa: E402
from leitor import alteracoes as ALT           # noqa: E402
from dataclasses import replace as dc_replace  # noqa: E402
from shapely.geometry import Polygon as _Poly   # noqa: E402
from leitor.escala import calibrar             # noqa: E402
from leitor.esquadrias import ler_esquadrias   # noqa: E402
from leitor.ingestao import extrair            # noqa: E402
from leitor.vistas import encontrar_vistas     # noqa: E402

STATUS_TXT = {"ok": "Conferido", "conferir": "Conferir", "divergente": "Divergente",
              "rotulos_juntos": "Rótulos juntos", "sem_poligono": "Sem polígono"}


def _trecho_de_muro_inclinado(p: dict, eixos: list, m: float) -> bool:
    """Parede curta (≤ 0,80 m) de tipo muro/a definir/concreto com o meio a menos de 35 cm do eixo
    de um muro inclinado — mesma regra que o 3D usa para trocar os degraus pelo muro inteiro."""
    if p["comprimento_m"] > 0.8 or p["tipo"] not in ("muro", "a definir", "concreto"):
        return False
    e = p["eixo"]
    mx, my = (e[0] + e[2]) / 2, (e[1] + e[3]) / 2
    for x0, y0, x1, y1 in eixos:
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy or 1e-9
        t = max(0.0, min(1.0, ((mx - x0) * dx + (my - y0) * dy) / L2))
        if ((mx - x0 - t * dx) ** 2 + (my - y0 - t * dy) ** 2) ** 0.5 * m < 0.35:
            return True
    return False


def _vaos_em_muros_inclinados(muros: list, esquadrias: list, usadas: set, m_vista: dict) -> set:
    """Uma etiqueta de porta/portão que não achou vão e tem a mesma largura (±10 cm) da lacuna entre
    dois trechos alinhados de um muro inclinado, a até 3 m dela, vira um trecho de muro com o vão
    ocupando toda a lacuna. Devolve os índices das etiquetas usadas."""
    import math as _m
    novas, novos = set(), []
    for vid, m in m_vista.items():
        ms = [x for x in muros if x["vista"] == vid]
        lacunas = []
        for i, a in enumerate(ms):
            for b in ms[i + 1:]:
                ea, eb = a["eixo"], b["eixo"]
                ua = (ea[2] - ea[0], ea[3] - ea[1]); ub = (eb[2] - eb[0], eb[3] - eb[1])
                la, lb = _m.hypot(*ua), _m.hypot(*ub)
                if abs(ua[0] * ub[0] + ua[1] * ub[1]) / max(la * lb, 1e-9) < 0.97:
                    continue
                # pontas mais próximas dos dois trechos
                pa = min(((ea[0], ea[1]), (ea[2], ea[3])), key=lambda q: min(_m.dist(q, eb[:2]), _m.dist(q, eb[2:])))
                pb = min(((eb[0], eb[1]), (eb[2], eb[3])), key=lambda q: _m.dist(q, pa))
                g = _m.dist(pa, pb) * m
                # a lacuna tem de seguir a direção do muro
                if g < 0.5 or abs((pb[0] - pa[0]) * ua[1] - (pb[1] - pa[1]) * ua[0]) / la * m > 0.10:
                    continue
                lacunas.append((pa, pb, g, a["espessura_m"]))
        for pa, pb, g, esp in lacunas:
            meio = ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)
            cands = [(_m.dist(e["xy"], meio) * m, i) for i, e in enumerate(esquadrias)
                     if i not in usadas and i not in novas and e["vista"] == vid and abs(e["largura_m"] - g) <= 0.10]
            cands = [c for c in cands if c[0] <= 3.0]
            if not cands:
                continue
            _, i = min(cands)
            e = esquadrias[i]
            novas.add(i)
            novos.append({"vista": vid, "eixo": [round(pa[0], 2), round(pa[1], 2), round(pb[0], 2), round(pb[1], 2)],
                          "espessura_m": esp, "vao": {"tipo": e["tipo"], "largura_m": e["largura_m"], "altura_m": e["altura_m"],
                                                       "peitoril_m": e["peitoril_m"]}})
    muros.extend(novos)
    return novas


def medir(pdf: Path, saida: Path, obra: str, familia: str = "39") -> dict:
    paginas = extrair(pdf, cache_dir=saida.parent / "_cache")
    vistas_out, ambientes_out, esquadrias_out, vaos_out, paredes_out, muros_incl = [], [], [], [], [], []
    escadas_out = []
    # 1ª passada: calibra todas as vistas, fixa uma escala única por escala nominal e
    # encaixa os pavimentos repetidos nas coordenadas do primeiro igual (ver repeticao.py)
    lista = []
    for pag in paginas:
        for v in encontrar_vistas(pag):
            lista.append([pag, v, calibrar(pag, v.caixa), None])
    m_doc = REP.escala_unica([(v.m_por_pt_nominal, cal.m_por_pt if cal else None, cal.n_cotas if cal else 0) for _, v, cal, _ in lista])
    refs = []
    for item in lista:
        pag, v = item[0], item[1]
        orig, sig = REP.assinatura(pag, v.caixa)
        T, ref = (0.0, 0.0), None
        if len(sig) >= 50:
            for pr, vr, origr, sigr in refs:
                if REP.semelhanca(sig, sigr) >= 0.98:
                    T, ref = (orig[0] - origr[0], orig[1] - origr[1]), (pr, vr)
                    break
            else:
                refs.append((pag, v, orig, sig))
        copia, caixa, _ = REP.copia_alinhada(pag, v.caixa, ref[0] if ref else None, ref[1].caixa if ref else None, T)
        item[0], item[1] = copia, dc_replace(v, caixa=caixa)
        item[3] = (ref[1].titulo if ref else None, T)
    for pag, v, cal, (repete, desloc) in lista:
        m_v = cal.m_por_pt if cal else None
        m_d = m_doc.get(round(v.m_por_pt_nominal, 9))
        if m_d and (m_v is None or abs(m_v / m_d - 1) < 0.003):
            m = m_d
        else:
            m = m_v or v.m_por_pt_nominal
        vs: list = []
        ctx: dict = {}
        ambs = detectar(pag, v.caixa, m, v.titulo, vaos_saida=vs, contexto=ctx)
        esqs = ler_esquadrias(pag, v.caixa)
        if not ambs and not esqs:
            continue
        # áreas de terreno (locação) não são delimitadas por parede: ficam fora desta fase
        if ambs and all(a.status in ("rotulos_juntos", "sem_poligono") for a in ambs):
            continue
        vid = f"p{pag.numero}-{len(vistas_out) + 1}"
        for x in vs:
            x.update(vista=vid, pavimento=v.titulo)
        vaos_out.extend(vs)
        vistas_out.append({
            "id": vid, "pagina": pag.numero, "titulo": v.titulo, "escala_nominal": v.escala,
            "caixa": [round(x, 2) for x in v.caixa],
            "m_por_pt_nominal": v.m_por_pt_nominal,
            "m_por_pt": m, "m_por_pt_vista": m_v, "calibrada": bool(cal), "repete": repete,
            "desloc": [round(desloc[0], 4), round(desloc[1], 4)],
            "n_cotas": cal.n_cotas if cal else 0, "dispersao_pct": cal.desvio_pct if cal else None,
        })
        for x0, y0, x1, y1, t in COB.muros_inclinados(pag, v.caixa, m):
            muros_incl.append({"vista": vid, "eixo": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)], "espessura_m": round(t, 3)})
        # modelo de paredes ("BIM de alvenaria")
        ad = [{"nome": a.nome, "poligono": a.poligono, "furos": a.furos, "rotulo_xy": a.rotulo_xy,
               "_rotulo": f"A{i:02d} · {a.nome}"} for i, a in enumerate(ambs)]
        unidades = PAR.agrupar_unidades(ad, ctx["vaos"], m)
        pws = PAR.extrair(ctx, ad, v.titulo, m, vid)
        PAR.classificar(pws, unidades, tem_unidades=bool(unidades))
        nome_lado = {x["_rotulo"]: (f'{unidades[x["_rotulo"]]} · ' if x["_rotulo"] in unidades else "") + x["nome"] for x in ad}
        incl = [mi["eixo"] for mi in muros_incl if mi["vista"] == vid]
        for pw in pws:
            d_ = pw.__dict__.copy()
            d_["lado_a"] = [nome_lado.get(l, l) for l in pw.lado_a]
            d_["lado_b"] = [nome_lado.get(l, l) for l in pw.lado_b]
            d_["vista"] = vid
            # trechos curtos que são o muro inclinado picado em degraus (o 3D usa o muro inteiro):
            # no térreo viram muro, para não entrarem como fachada na pintura nem no orçamento
            if incl and _trecho_de_muro_inclinado(d_, incl, m):
                d_["trecho_muro_inclinado"] = True
                if "sub" in v.titulo.lower():
                    d_["motivo"] = "trecho do muro inclinado (arrimo a definir)"
                else:
                    d_["tipo"], d_["fachada"], d_["motivo"] = "muro", False, "trecho do muro inclinado (divisa)"
            paredes_out.append(d_)
        for i, a in enumerate(ambs):
            ambientes_out.append({
                "unidade": unidades.get(f"A{i:02d} · {a.nome}"),
                "vista": vid, "pavimento": v.titulo, "pagina": pag.numero, "nome": a.nome,
                "area_rotulo_m2": a.area_rotulo_m2,
                "area_m2": round(a.area_m2, 3) if a.area_m2 is not None else None,
                "area_piso_m2": round(a.area_piso_m2, 3) if a.area_piso_m2 is not None else None,
                "perimetro_m": round(a.perimetro_m, 3) if a.perimetro_m is not None else None,
                "divergencia_pct": round(a.divergencia_pct, 2) if a.divergencia_pct is not None else None,
                "area_teto_m2": round(a.area_teto_m2, 3) if a.area_teto_m2 is not None else None,
                "perimetro_parede_m": round(a.perimetro_parede_m, 3) if a.perimetro_parede_m is not None else None,
                "sem_parede_m": round(a.sem_parede_m, 3) if a.sem_parede_m is not None else None,
                "vaos": a.vaos,
                "status": a.status, "observacao": a.observacao,
                "poligono": a.poligono, "furos": a.furos, "rotulo_xy": [round(x, 2) for x in a.rotulo_xy],
            })
        # escada: degraus, patamar e corrimão lidos da numeração dos pisos (para o 3D)
        for a in ambs:
            if a.poligono and a.nome.lower().startswith("escada"):
                g = ESC.ler(pag, a.poligono, m) or {"sobe": False}
                escadas_out.append({"vista": vid, "ambiente": a.nome, "anotacoes": ESC.anotacoes(pag, _Poly(a.poligono)), **g})
        for e in esqs:
            esquadrias_out.append({"vista": vid, "pavimento": v.titulo, "tipo": e.tipo,
                                   "largura_m": e.largura_m, "altura_m": e.altura_m,
                                   "peitoril_m": e.peitoril_m, "xy": [round(e.x, 2), round(e.y, 2)]})
    # ordem natural dos pavimentos: subsolo, térreo, 1º, 2º…
    def nivel(t):
        t = t.lower()
        if "sub" in t:
            return -1
        if "térreo" in t or "terreo" in t:
            return 0
        n = "".join(ch for ch in t.split("º")[0] if ch.isdigit())
        return int(n) if n else 99
    vistas_out.sort(key=lambda v: nivel(v["titulo"]))
    ordem = {v["id"]: i for i, v in enumerate(vistas_out)}
    ambientes_out.sort(key=lambda a: ordem[a["vista"]])
    esquadrias_out.sort(key=lambda e: ordem[e["vista"]])
    vaos_out.sort(key=lambda x: ordem[x["vista"]])
    paredes_out.sort(key=lambda x: ordem[x["vista"]])
    # vão ↔ etiqueta (altura e peitoril)
    m_vista = {v["id"]: v["m_por_pt"] for v in vistas_out}
    usadas = Q.casar_etiquetas(vaos_out, esquadrias_out, m_vista)
    # portas e portões em muro inclinado: a etiqueta que sobrou cabe na lacuna entre dois trechos do muro
    usadas |= _vaos_em_muros_inclinados(muros_incl, esquadrias_out, usadas, m_vista)
    for i, e in enumerate(esquadrias_out):
        e["casada"] = i in usadas
    sobra = [e for e in esquadrias_out if not e["casada"]]
    if sobra:
        print("atenção: etiquetas sem vão no modelo:", ", ".join(f'{e["pavimento"]} {e["tipo"]} {e["largura_m"]:.2f}×{e["altura_m"]:.2f}' for e in sobra))
    por_id = {x["id"]: x for x in vaos_out}
    for pw in paredes_out:
        for vv in pw["vaos"]:
            x = por_id.get(vv["vao"], {})
            vv.update(altura_m=x.get("altura_m"), peitoril_m=x.get("peitoril_m"))
    # alterações de projeto decididas pelo cliente (obras/<obra>/alteracoes.json)
    tmp = {"vistas": vistas_out, "paredes": paredes_out, "vaos": vaos_out, "ambientes": ambientes_out, "esquadrias": esquadrias_out}
    registro_alt = ALT.aplicar(tmp, ALT.carregar(saida.parent))
    paredes_out, vaos_out = tmp["paredes"], tmp["vaos"]
    if registro_alt:
        print(f"alterações de projeto: {len(registro_alt)} paredes removidas "
              f"({sum(len(r['vaos']) for r in registro_alt)} vãos, {sum(len(r['etiquetas']) for r in registro_alt)} etiquetas)")
    # ajustes manuais de classificação (baixados da página paredes.html)
    arq_aj = saida.parent / "ajustes_paredes.json"
    if arq_aj.exists():
        aj = json.loads(arq_aj.read_text())
        for pw in paredes_out:
            if pw["id"] in aj:
                pw["tipo"], pw["motivo"] = aj[pw["id"]], "ajuste manual"
    # pé-direito: dos cortes; um premissas.json ao lado da saída pode sobrescrever
    pavs = [v["titulo"] for v in vistas_out]
    pd, fonte = ler_pe_direito(paginas, pavs)
    pd = {p: pd.get(p) for p in pavs}
    fontes = {p: fonte if pd[p] else "" for p in pavs}
    arq = saida.parent / "premissas.json"
    if arq.exists():
        for p, val in json.loads(arq.read_text()).get("pe_direito_m", {}).items():
            pd[p], fontes[p] = val, "premissas.json"
    for p in pavs:
        if not pd[p]:
            pd[p], fontes[p] = 2.60, "padrão (não encontrado nos cortes)"
    dados = {"obra": obra, "documento": pdf.name, "gerado_em": date.today().isoformat(),
             "vistas": vistas_out, "ambientes": ambientes_out, "esquadrias": esquadrias_out, "vaos": vaos_out,
             "paredes": paredes_out, "muros_inclinados": muros_incl, "cobertura_pdf": COB.ler_cobertura(paginas),
             "escadas": escadas_out, "alteracoes": registro_alt,
             "premissas": {"pe_direito_m": pd, "fonte_pe_direito": fontes,
                           "altura_padrao_m": Q.PADRAO_ALTURA, "varanda": PREMISSA_VARANDA}}
    dados["quantitativos"] = Q.calcular(dados, pd)
    # paginação estimada, famílias 29 e 39 (detalhe bloco a bloco do primeiro pavimento-tipo)
    v_tipo = next((v["id"] for v in vistas_out if "1º" in v["titulo"]), None)
    dados["paginacao"] = {"vista_detalhe": v_tipo}
    for fam in ("29", "39"):
        por, det = PG.paginar(dados, fam, guardar_vista=v_tipo)
        tit = next(v["titulo"] for v in vistas_out if v["id"] == v_tipo) if v_tipo else None
        area = sum(p["comprimento_m"] * pd.get(p["pavimento"], 2.6) - sum(x["largura_m"] * (x.get("altura_m") or 2.1) for x in p["vaos"])
                   for p in paredes_out if p["vista"] == v_tipo and p["tipo"] == "estrutural")
        dados["paginacao"][fam] = {"por_pavimento": {k: dict(v) for k, v in por.items()}, "detalhes": det,
                                   "area_estrutural_tipo_m2": area}
    dados["premissas"]["familia"] = familia
    if v_tipo:
        dados["insumos"] = INS.calcular(dados, familia)
    return dados


PASTA_PRECOS = Path(__file__).parent / "obras" / "_sinapi"


def orcamento(dados: dict, saida: Path, mes: str | None = None, desonerado: bool | None = None) -> dict | None:
    """B4: SINAPI (mês pedido, ou o último publicado) + CUB. Premissas da obra em premissas.json
    (chave "orcamento": desonerado, bdi, fator_canaleta_j, padrao_cub, fbk por pavimento)."""
    if not dados.get("insumos"):
        return None
    if not mes:
        hoje = date.today().strftime("%Y-%m")
        try:
            mes = SIN.ultimo_mes(hoje, tentativas=3)
        except Exception:
            mes = None
        if not mes:                                   # sem rede: o mais recente em cache
            cache = sorted(PASTA_PRECOS.glob("sinapi_SP_*.json"))
            mes = cache[-1].stem[-7:].replace("_", "-") if cache else None
    if not mes:
        print("B4: SINAPI indisponível (sem rede e sem cache); orçamento não gerado.")
        return None
    sin = SIN.carregar(mes, PASTA_PRECOS)
    cb = CUB.carregar(PASTA_PRECOS)
    arq = saida.parent / "premissas.json"
    po = json.loads(arq.read_text()).get("orcamento", {}) if arq.exists() else {}
    prem = {k: po[k] for k in ("desonerado", "bdi", "fator_canaleta_j", "padrao_cub") if k in po}
    if desonerado is not None:
        prem["desonerado"] = desonerado
    return ORC.calcular(dados, sin, cb, prem, po.get("fbk"))


# ---------------------------------------------------------------- planilha
def _cabecalho(ws, titulos, larguras):
    for i, (t, w) in enumerate(zip(titulos, larguras), 1):
        c = ws.cell(row=1, column=i, value=t)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="0F6E56")
        c.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    ws.row_dimensions[1].height = 32


def planilha(dados: dict, destino: Path):
    wb = Workbook()
    leia = wb.active
    leia.title = "Leia-me"
    linhas = [
        (f"Medição — {dados['obra']}", True),
        (f"Documento: {dados['documento']} · gerado em {dados['gerado_em']}", False),
        ("", False),
        ("Como foi medido", True),
        ("• Áreas e perímetros calculados pela geometria vetorial do PDF (camadas do CAD: paredes, esquadrias, soleiras), não estimados por IA.", False),
        ("• Escala calibrada pelas cotas (aba Calibração): uma escala única para o documento, porque o PDF raramente sai exatamente na escala nominal. Pavimentos repetidos usam as coordenadas do primeiro igual.", False),
        ("• Vãos de porta e janela fechados no alinhamento das faces da parede (como o CAD faz). Passagens sem porta não separam ambientes.", False),
        ("• Cada ambiente é conferido contra a área escrita no rótulo do arquiteto.", False),
        ("", False),
        ("Status", True),
        ("Conferido: diferença até 2% · Conferir: 2% a 10% · Divergente: acima de 10%.", False),
        ("Garagens: o rótulo do arquiteto mede só a parte coberta; a coluna 'Piso total' traz a área inteira do piso.", False),
        ("", False),
        ("", False),
        ("Quantitativos por ambiente (abas Quantitativos e Resumo quantitativos)", True),
        ("• Piso = área do ambiente. Teto = área coberta (nas garagens, só o trecho sob a projeção do pavimento-tipo).", False),
        ("• Rodapé = contorno junto a parede − larguras das portas.", False),
        ("• Parede bruta = contorno junto a parede × pé-direito. Trechos sem parede (guarda-corpo, lado aberto da garagem) ficam de fora.", False),
        ("• Vãos = largura × altura de cada porta e janela do contorno (altura pela etiqueta da planta). Parede líquida = bruta − vãos.", False),
        ("• Parede de um ambiente = face voltada para ele; paredes entre dois ambientes aparecem uma vez em cada lado.", False),
        ("• O critério de desconto de vãos do SINAPI (ex.: não descontar vãos pequenos) será aplicado na EAP; aqui ficam bruta e líquida.", False),
        ("• Pé-direito lido dos cortes (aba Premissas, editável).", False),
        ("", False),
        ("Orçamento da alvenaria e dos revestimentos — B4 (abas Orçamento, Preços e Custo por pavimento)", True),
        ("• Preços do SINAPI (Caixa), São Paulo, mês de referência na aba Preços (B4). Desoneração, BDI, fbk por pavimento e cotações são editáveis.", False),
        ("• Blocos, canaletas, argamassa e tela: quantidade da paginação (aba Insumos (B3)) × preço do insumo SINAPI.", False),
        ("• Mão de obra da alvenaria: área líquida × pedreiro + servente da composição SINAPI (sem os materiais, que vêm da paginação).", False),
        ("• Graute, armação, encunhamento e revestimentos: composição SINAPI completa × quantidade medida.", False),
        ("• Conferência: custo por m² e comparação com o CUB do SindusCon-SP no fim da aba Orçamento (B4).", False),
        ("", False),
        ("Fora desta fase: áreas de terreno (planta de locação), estrutura de concreto, pisos, instalações e esquadrias.", False),
    ]
    for i, (t, b) in enumerate(linhas, 1):
        leia.cell(row=i, column=1, value=t).font = Font(bold=b, size=13 if i == 1 else 11)
    leia.column_dimensions["A"].width = 120

    ws = wb.create_sheet("Ambientes")
    _cabecalho(ws, ["Pavimento", "Prancha", "Ambiente", "Área rótulo (m²)", "Área medida (m²)", "Diferença",
                    "Piso total (m²)", "Perímetro (m)", "Status", "Observação"],
               [18, 9, 26, 14, 14, 11, 14, 13, 14, 60])
    for r, a in enumerate(dados["ambientes"], 2):
        ws.cell(row=r, column=1, value=a["pavimento"])
        ws.cell(row=r, column=2, value=a["pagina"])
        ws.cell(row=r, column=3, value=a["nome"])
        ws.cell(row=r, column=4, value=a["area_rotulo_m2"]).number_format = "0.00"
        ws.cell(row=r, column=5, value=a["area_m2"]).number_format = "0.00"
        ws.cell(row=r, column=6, value=f'=IF(AND(ISNUMBER(D{r}),ISNUMBER(E{r}),D{r}>0),E{r}/D{r}-1,"")').number_format = "+0.0%;-0.0%;0.0%"
        ws.cell(row=r, column=7, value=a["area_piso_m2"]).number_format = "0.00"
        ws.cell(row=r, column=8, value=a["perimetro_m"]).number_format = "0.00"
        ws.cell(row=r, column=9, value=STATUS_TXT.get(a["status"], a["status"]))
        ws.cell(row=r, column=10, value=a["observacao"])
    n = len(dados["ambientes"]) + 1
    ws.auto_filter.ref = f"A1:J{n}"
    for txt, cor in (("Conferido", "E1F5EE"), ("Conferir", "FAEEDA"), ("Divergente", "F9D7D7")):
        ws.conditional_formatting.add(f"I2:I{n}", CellIsRule(operator="equal", formula=[f'"{txt}"'], fill=PatternFill("solid", fgColor=cor)))

    rs = wb.create_sheet("Resumo")
    _cabecalho(rs, ["Pavimento", "Ambientes", "Conferidos", "Área rótulos (m²)", "Área medida (m²)", "Piso total (m²)"],
               [20, 12, 12, 16, 16, 16])
    pavs = list(dict.fromkeys(a["pavimento"] for a in dados["ambientes"]))
    for i, pv in enumerate(pavs, 2):
        rs.cell(row=i, column=1, value=pv)
        rs.cell(row=i, column=2, value=f'=COUNTIF(Ambientes!$A:$A,A{i})')
        rs.cell(row=i, column=3, value=f'=COUNTIFS(Ambientes!$A:$A,A{i},Ambientes!$I:$I,"Conferido")')
        for col, src in ((4, "D"), (5, "E"), (6, "G")):
            rs.cell(row=i, column=col, value=f'=SUMIF(Ambientes!$A:$A,A{i},Ambientes!${src}:${src})').number_format = "#,##0.00"
    t = len(pavs) + 2
    rs.cell(row=t, column=1, value="Total").font = Font(bold=True)
    for col in range(2, 7):
        L = get_column_letter(col)
        c = rs.cell(row=t, column=col, value=f"=SUM({L}2:{L}{t - 1})")
        c.font = Font(bold=True)
        if col >= 4:
            c.number_format = "#,##0.00"

    es = wb.create_sheet("Esquadrias")
    _cabecalho(es, ["Pavimento", "Tipo", "Largura (m)", "Altura (m)", "Peitoril (m)", "Qtd", "Área de vão (m²)",
                    "Soleira/peitoril (m)"], [18, 10, 12, 12, 12, 8, 16, 18])
    cont = Counter((e["pavimento"], e["tipo"], e["largura_m"], e["altura_m"], e["peitoril_m"]) for e in dados["esquadrias"])
    ordem = {p: i for i, p in enumerate(pavs)}
    r = 2
    for (pv, tp, L, H, P), q in sorted(cont.items(), key=lambda kv: (ordem.get(kv[0][0], 99), kv[0][1], kv[0][2], kv[0][3])):
        for col, val in enumerate((pv, tp, L, H, P, q), 1):
            c = es.cell(row=r, column=col, value=val)
            if col in (3, 4, 5):
                c.number_format = "0.00"
        es.cell(row=r, column=7, value=f"=C{r}*D{r}*F{r}").number_format = "0.00"
        es.cell(row=r, column=8, value=f"=C{r}*F{r}").number_format = "0.00"
        r += 1
    fim = r - 1
    r += 1
    es.cell(row=r, column=1, value="Total da obra por tipo e dimensão").font = Font(bold=True)
    r += 1
    for col, t in enumerate(("Tipo", "Largura (m)", "Altura (m)", "Peitoril (m)", "Qtd", "Área de vão (m²)", "Soleira/peitoril (m)"), 2):
        es.cell(row=r, column=col, value=t).font = Font(bold=True)
    r += 1
    tipos = sorted({(tp, L, H, P) for (_, tp, L, H, P) in cont}, key=lambda k: (k[0], k[1], k[2]))
    for tp, L, H, P in tipos:
        es.cell(row=r, column=2, value=tp)
        es.cell(row=r, column=3, value=L).number_format = "0.00"
        es.cell(row=r, column=4, value=H).number_format = "0.00"
        es.cell(row=r, column=5, value=P).number_format = "0.00"
        es.cell(row=r, column=6, value=f'=SUMIFS($F$2:$F${fim},$B$2:$B${fim},B{r},$C$2:$C${fim},C{r},$D$2:$D${fim},D{r})')
        es.cell(row=r, column=7, value=f"=C{r}*D{r}*F{r}").number_format = "0.00"
        es.cell(row=r, column=8, value=f"=C{r}*F{r}").number_format = "0.00"
        r += 1

    # premissas
    pr = wb.create_sheet("Premissas")
    _cabecalho(pr, ["Pavimento", "Pé-direito (m)", "Fonte"], [20, 14, 60])
    for i, p in enumerate(dados["premissas"]["pe_direito_m"], 2):
        pr.cell(row=i, column=1, value=p)
        c = pr.cell(row=i, column=2, value=dados["premissas"]["pe_direito_m"][p])
        c.number_format = "0.00"
        c.fill = PatternFill("solid", fgColor="FFF8E1")
        pr.cell(row=i, column=3, value=dados["premissas"]["fonte_pe_direito"][p])
    j = len(dados["premissas"]["pe_direito_m"]) + 3
    pr.cell(row=j, column=1, value="Altura assumida quando o vão não tem etiqueta na planta").font = Font(bold=True)
    for k, (t, h) in enumerate(dados["premissas"]["altura_padrao_m"].items(), j + 1):
        pr.cell(row=k, column=1, value=t)
        pr.cell(row=k, column=2, value=h).number_format = "0.00"
    vr = dados["premissas"]["varanda"]
    pr.cell(row=j + 4, column=1, value="Varanda (guarda-corpo em mureta)").font = Font(bold=True)
    pr.cell(row=j + 5, column=1, value="Altura da mureta (m)")
    pr.cell(row=j + 5, column=2, value=vr["peitoril_m"]).number_format = "0.00"
    pr.cell(row=j + 6, column=1, value="Topo da abertura (m)")
    pr.cell(row=j + 6, column=2, value=vr["topo_m"]).number_format = "0.00"
    pr.cell(row=j + 7, column=1, value=vr["fonte"])
    pr.cell(row=j + 9, column=1, value="Células em amarelo são editáveis: a aba Quantitativos recalcula sozinha.").font = Font(italic=True)

    # quantitativos por ambiente
    qt = wb.create_sheet("Quantitativos")
    cols = ["Pavimento", "Ambiente", "Tipo", "Pé-direito (m)", "Piso (m²)", "Teto (m²)", "Perímetro (m)",
            "Contorno c/ parede (m)", "Contorno s/ parede (m)", "Portas (un)", "Larg. portas (m)", "Rodapé (m)",
            "Parede bruta (m²)", "Janelas (un)", "Vãos portas+janelas (m²)", "Parede líquida (m²)", "Observação"]
    _cabecalho(qt, cols, [16, 22, 11, 11, 10, 10, 11, 12, 12, 9, 11, 10, 12, 9, 13, 12, 70])
    for r, q in enumerate(dados["quantitativos"], 2):
        vals = [q["pavimento"], q["ambiente"], q["tipo"], f"=VLOOKUP(A{r},Premissas!$A:$B,2,FALSE)",
                q["piso_m2"], q["teto_m2"], q["perimetro_m"], q["perimetro_parede_m"], q["sem_parede_m"],
                q["n_portas"], q["larg_portas_m"], f"=MAX(H{r}-K{r},0)", f"=H{r}*D{r}", q["n_janelas"],
                q["area_vaos_m2"], f"=M{r}-O{r}", q["observacao"]]
        for col, val in enumerate(vals, 1):
            c = qt.cell(row=r, column=col, value=val)
            if col in (4, 5, 6, 7, 8, 9, 11, 12, 13, 15, 16):
                c.number_format = "0.00"
    nq = len(dados["quantitativos"]) + 1
    qt.auto_filter.ref = f"A1:Q{nq}"

    # resumo dos quantitativos
    rq = wb.create_sheet("Resumo quantitativos")
    _cabecalho(rq, ["Tipo de ambiente", "Ambientes", "Piso (m²)", "Teto (m²)", "Rodapé (m)", "Parede bruta (m²)",
                    "Vãos (m²)", "Parede líquida (m²)"], [22, 11, 13, 13, 13, 16, 12, 17])
    fonte = {"Piso (m²)": "E", "Teto (m²)": "F", "Rodapé (m)": "L", "Parede bruta (m²)": "M", "Vãos (m²)": "O", "Parede líquida (m²)": "P"}
    def bloco(lin0, chave_col, chaves, titulo):
        rq.cell(row=lin0, column=1, value=titulo).font = Font(bold=True)
        for i, k in enumerate(chaves, lin0 + 1):
            rq.cell(row=i, column=1, value=k)
            rq.cell(row=i, column=2, value=f'=COUNTIF(Quantitativos!${chave_col}:${chave_col},A{i})')
            for col, L in enumerate(fonte.values(), 3):
                rq.cell(row=i, column=col, value=f'=SUMIF(Quantitativos!${chave_col}:${chave_col},A{i},Quantitativos!${L}:${L})').number_format = "#,##0.00"
        t = lin0 + len(chaves) + 1
        rq.cell(row=t, column=1, value="Total").font = Font(bold=True)
        for col in range(2, 9):
            L = get_column_letter(col)
            c = rq.cell(row=t, column=col, value=f"=SUM({L}{lin0 + 1}:{L}{t - 1})")
            c.font = Font(bold=True)
            if col > 2:
                c.number_format = "#,##0.00"
        return t + 2
    tipos = [t for t in ("seca", "molhada", "externa", "circulação", "garagem", "técnico")
             if any(q["tipo"] == t for q in dados["quantitativos"])]
    lin = bloco(2, "C", tipos, "Por tipo de ambiente")
    bloco(lin, "A", list(dict.fromkeys(q["pavimento"] for q in dados["quantitativos"])), "Por pavimento")
    rq.cell(row=1, column=1).value = "Agrupamento"

    ca = wb.create_sheet("Calibração")
    _cabecalho(ca, ["Prancha", "Vista", "Escala nominal", "mm/pt nominal", "mm/pt pelas cotas da vista", "mm/pt usado (documento)",
                    "Diferença do usado p/ nominal", "Cotas usadas", "Dispersão", "Geometria"],
               [9, 22, 14, 14, 18, 18, 16, 12, 11, 44])
    for i, v in enumerate(dados["vistas"], 2):
        ca.cell(row=i, column=1, value=v["pagina"])
        ca.cell(row=i, column=2, value=v["titulo"])
        ca.cell(row=i, column=3, value=f"1:{v['escala_nominal']}")
        ca.cell(row=i, column=4, value=v["m_por_pt_nominal"] * 1000).number_format = "0.00000"
        mv = v.get("m_por_pt_vista", v["m_por_pt"] if v["calibrada"] else None)
        ca.cell(row=i, column=5, value=mv * 1000 if mv else None).number_format = "0.00000"
        ca.cell(row=i, column=6, value=v["m_por_pt"] * 1000).number_format = "0.00000"
        ca.cell(row=i, column=7, value=f"=F{i}/D{i}-1").number_format = "+0.000%;-0.000%"
        ca.cell(row=i, column=8, value=v["n_cotas"])
        ca.cell(row=i, column=9, value=(v["dispersao_pct"] or 0) / 100).number_format = "0.00%"
        ca.cell(row=i, column=10, value=f"repete o {v['repete']} (mesmas linhas de parede)" if v.get("repete") else "própria")
    k = len(dados["vistas"]) + 3
    for j, txt in enumerate([
        "Escala única: o PDF tem um só fator de exportação. Cada vista é calibrada pelas cotas, e a escala usada é a mediana "
        "ponderada das vistas (as cotas são arredondadas ao centímetro e, sozinhas, variam até 0,02%).",
        "Pavimentos repetidos: quando as linhas de parede de uma vista coincidem com as de outra (≥ 98% a menos de 0,15 pt), "
        "a vista usa as coordenadas da primeira. Assim andares iguais dão as mesmas áreas, paredes e paginação; "
        "o que muda de verdade (ex.: escada do último andar) é lido da própria vista.",
    ], k):
        ca.cell(row=j, column=1, value=txt).font = Font(italic=True)
    SP.abas(wb, dados, _cabecalho)
    if dados.get("paginacao", {}).get("vista_detalhe"):
        SPG.abas(wb, dados, _cabecalho)
    if dados.get("insumos"):
        SINS.aba(wb, dados["insumos"], _cabecalho)
    if dados.get("orcamento"):
        SORC.abas(wb, dados, _cabecalho)
    CONF.aba(wb, CONF.checar(dados), _cabecalho)
    ordem_abas = ["Leia-me", "Conferência", "Resumo", "Orçamento (B4)", "Insumos (B3)", "Preços (B4)", "Custo por pavimento (B4)", "Resumo quantitativos", "Resumo paredes", "Paginação", "Quantitativos", "Paredes",
                  "Paginação por parede", "Ambientes", "Esquadrias", "Premissas", "Calibração"]
    ordem_abas = [n for n in ordem_abas if n in wb.sheetnames]
    wb._sheets = [wb[n] for n in ordem_abas]
    wb.save(destino)


# ---------------------------------------------------------------- página de conferência
def pagina_conferencia(dados: dict, pdf: Path, destino: Path):
    doc = pymupdf.open(str(pdf))
    vistas = []
    for v in dados["vistas"]:
        x0, y0, x1, y1 = v["caixa"]
        x0, y0, x1, y1 = x0 - 15, y0 - 15, x1 + 15, y1 + 15
        ddx, ddy = v.get("desloc") or (0, 0)          # andar repetido: dados no sistema da referência
        pix = doc[v["pagina"] - 1].get_pixmap(matrix=pymupdf.Matrix(1.6, 1.6), clip=pymupdf.Rect(x0 + ddx, y0 + ddy, x1 + ddx, y1 + ddy),
                                               colorspace=pymupdf.csGRAY)
        img = base64.b64encode(pix.tobytes("png")).decode()
        qidx = {q["indice_ambiente"]: q for q in dados["quantitativos"]}
        ambs = [dict(a, q=qidx.get(i)) for i, a in enumerate(dados["ambientes"]) if a["vista"] == v["id"]]
        vaos_v = [{"r": x["retangulo"], "t": x["tipo"], "l": x["largura_m"], "h": x.get("altura_m")}
                  for x in dados["vaos"] if x["vista"] == v["id"]]
        esqs = Counter(f'{e["tipo"]} {e["largura_m"]:.2f}×{e["altura_m"]:.2f}'.replace(".", ",")
                       for e in dados["esquadrias"] if e["vista"] == v["id"])
        vistas.append({"id": v["id"], "titulo": v["titulo"], "caixa": [x0, y0, x1 - x0, y1 - y0], "img": img,
                       "escala": v["m_por_pt"], "nominal": v["m_por_pt_nominal"], "cotas": v["n_cotas"],
                       "ambientes": [{**{k: a[k] for k in ("nome", "area_rotulo_m2", "area_m2", "area_piso_m2", "perimetro_m",
                                                           "divergencia_pct", "status", "observacao", "poligono", "furos")},
                                      "q": a["q"] and {k: a["q"][k] for k in ("rodape_m", "parede_liquida_m2", "teto_m2", "pe_direito_m",
                                                                              "n_portas", "n_janelas")}}
                                     for a in ambs],
                       "vaos": vaos_v,
                       "esquadrias": sorted(esqs.items())})
    tot = len(dados["ambientes"])
    ok = sum(a["status"] == "ok" for a in dados["ambientes"])
    piso = sum(a["area_piso_m2"] or 0 for a in dados["ambientes"])
    dif_esc = (dados["vistas"][0]["m_por_pt"] / dados["vistas"][0]["m_por_pt_nominal"] - 1) * 100 if dados["vistas"] else 0
    n_esq = Counter(e["tipo"] for e in dados["esquadrias"])
    html_txt = MODELO.replace("__DADOS__", json.dumps(vistas, ensure_ascii=False)) \
        .replace("__OBRA__", html.escape(dados["obra"])) \
        .replace("__DOC__", html.escape(dados["documento"])) \
        .replace("__DATA__", dados["gerado_em"]) \
        .replace("__KPI_AMB__", f"{ok}/{tot}") \
        .replace("__KPI_PISO__", f"{piso:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")) \
        .replace("__KPI_ESC__", f"{dif_esc:+.1f}%".replace(".", ",")) \
        .replace("__KPI_ESQ__", f"{n_esq.get('porta', 0)} portas · {n_esq.get('janela', 0)} janelas")
    destino.write_text(html_txt, encoding="utf-8")


MODELO = r"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Conferência de Medição</title>
<style>
:root{--bg:#FAFAF7;--card:#fff;--elev:#F1EFE8;--bd:rgba(0,0,0,.1);--tx:#1A1A1A;--mut:#5F5E5A;--dim:#888780;
--ok:#0F6E56;--okbg:#E1F5EE;--warn:#8A5A00;--warnbg:#FAEEDA;--bad:#A32020;--badbg:#F9D7D7;--acc:#0F6E56}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#1A1A1A;--card:#242422;--elev:#2C2C2A;--bd:rgba(255,255,255,.12);
--tx:#F5F5F2;--mut:#B4B2A9;--dim:#888780;--ok:#5DCAA5;--okbg:#04342C;--warn:#FAC775;--warnbg:#412402;--bad:#F09595;--badbg:#4A1515;--acc:#5DCAA5}}
:root[data-theme=dark]{--bg:#1A1A1A;--card:#242422;--elev:#2C2C2A;--bd:rgba(255,255,255,.12);--tx:#F5F5F2;--mut:#B4B2A9;--dim:#888780;
--ok:#5DCAA5;--okbg:#04342C;--warn:#FAC775;--warnbg:#412402;--bad:#F09595;--badbg:#4A1515;--acc:#5DCAA5}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}
.wrap{max-width:1280px;margin:0 auto;padding:16px}
h1{font-size:18px;margin:0 0 2px;font-weight:600}.sub{color:var(--mut);font-size:12px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:14px 0}
.kpi{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:10px 12px}
.kpi .l{font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.3px}.kpi .v{font-size:20px;font-weight:600;font-variant-numeric:tabular-nums}
.kpi .h{font-size:11px;color:var(--dim)}
.tabs{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:10px}
.tab{border:1px solid var(--bd);background:var(--card);color:var(--tx);border-radius:8px;padding:6px 12px;font:inherit;font-size:13px;cursor:pointer}
.tab[aria-selected=true]{background:var(--acc);border-color:var(--acc);color:#fff}
.grid{display:grid;grid-template-columns:minmax(0,1fr) 380px;gap:12px;align-items:start}
.card{background:var(--card);border:1px solid var(--bd);border-radius:12px;overflow:hidden}
.plan{position:relative;background:#fff}
.plan svg{display:block;width:100%;height:auto}
.plan polygon,.plan path.amb{stroke-width:1.2;cursor:pointer;transition:fill-opacity .15s}
.plan .amb:hover,.plan .amb.sel{fill-opacity:.55!important;stroke-width:2.5}
.tip{position:absolute;pointer-events:none;background:#1A1A1A;color:#fff;font-size:12px;padding:6px 8px;border-radius:6px;display:none;white-space:nowrap;z-index:2}
.side{padding:12px}.side h2{font-size:13px;margin:0 0 8px;color:var(--mut);text-transform:uppercase;letter-spacing:.4px}
table{width:100%;border-collapse:collapse;font-size:12.5px;font-variant-numeric:tabular-nums}
th{text-align:left;color:var(--mut);font-weight:500;border-bottom:1px solid var(--bd);padding:5px 4px}
td{border-bottom:1px solid var(--bd);padding:5px 4px}td.n,th.n{text-align:right}
tr.row{cursor:pointer}tr.row:hover,tr.row.sel{background:var(--elev)}
.chip{display:inline-block;font-size:11px;padding:1px 7px;border-radius:999px;font-weight:500}
.chip.ok{background:var(--okbg);color:var(--ok)}.chip.conferir{background:var(--warnbg);color:var(--warn)}.chip.divergente,.chip.rotulos_juntos,.chip.sem_poligono{background:var(--badbg);color:var(--bad)}
.obs{font-size:11.5px;color:var(--mut);margin-top:10px;line-height:1.4}
.esq{margin-top:14px}.esq li{font-size:12.5px;margin:2px 0}.esq ul{padding-left:18px;margin:4px 0}
.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;color:var(--mut);margin:8px 0 0}
.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:4px;vertical-align:-2px}
.foot{color:var(--dim);font-size:11.5px;margin-top:14px}
@media (max-width:900px){.grid{grid-template-columns:1fr}.kpis{grid-template-columns:repeat(2,1fr)}}
</style></head><body><div class="wrap">
<h1>Conferência de medição · __OBRA__</h1>
<div class="sub">__DOC__ · gerado em __DATA__ · medição pela geometria do PDF, conferida contra os rótulos do arquiteto</div>
<div class="kpis">
<div class="kpi"><div class="l">Ambientes conferidos</div><div class="v">__KPI_AMB__</div><div class="h">diferença até 2% do rótulo</div></div>
<div class="kpi"><div class="l">Soma das áreas</div><div class="v">__KPI_PISO__ m²</div><div class="h">todos os ambientes, garagens inteiras</div></div>
<div class="kpi"><div class="l">Escala real × 1:50</div><div class="v">__KPI_ESC__</div><div class="h">calibrada pelas cotas</div></div>
<div class="kpi"><div class="l">Esquadrias</div><div class="v" style="font-size:16px">__KPI_ESQ__</div><div class="h">pelas etiquetas da planta</div></div>
</div>
<div class="tabs" role="tablist" id="tabs"></div>
<div class="grid">
<div class="card"><div class="plan" id="plan"><div class="tip" id="tip"></div></div></div>
<div class="card side"><h2 id="vt"></h2><table><thead><tr><th>Ambiente</th><th class="n">Rótulo</th><th class="n">Medido</th><th class="n">Dif.</th><th></th></tr></thead><tbody id="tb"></tbody></table>
<div class="obs" id="obs"></div><div class="esq" id="esq"></div>
<div class="legend"><span><i style="background:#1D9E75"></i>conferido</span><span><i style="background:#E8A317"></i>conferir</span><span><i style="background:#D64545"></i>divergente</span><span><i style="background:#C2610C"></i>vão de porta</span><span><i style="background:#1E66C8"></i>vão de janela</span></div>
</div></div>
<div class="foot">Áreas em m². Rótulo = área escrita na planta pelo arquiteto. Clique num ambiente (na planta ou na tabela) para destacá-lo.</div>
</div>
<script>
const V=__DADOS__;
const COR={ok:"#1D9E75",conferir:"#E8A317",divergente:"#D64545",rotulos_juntos:"#D64545",sem_poligono:"#D64545"};
const TXT={ok:"ok",conferir:"conferir",divergente:"divergente",rotulos_juntos:"rótulos juntos",sem_poligono:"sem polígono"};
const f2=n=>n==null?"—":n.toLocaleString("pt-BR",{minimumFractionDigits:2,maximumFractionDigits:2});
const fp=n=>n==null?"—":(n>0?"+":"")+n.toLocaleString("pt-BR",{minimumFractionDigits:1,maximumFractionDigits:1})+"%";
const tabs=document.getElementById("tabs"),plan=document.getElementById("plan"),tip=document.getElementById("tip");
let atual=0;
function pathOf(a){const r=p=>"M"+p.map(q=>q[0]+","+q[1]).join("L")+"Z";return r(a.poligono)+(a.furos||[]).map(r).join("")}
function mostrar(i){
 atual=i;[...tabs.children].forEach((b,k)=>b.setAttribute("aria-selected",k===i));
 const v=V[i],[x,y,w,h]=v.caixa;
 plan.querySelectorAll("svg").forEach(s=>s.remove());
 const NS="http://www.w3.org/2000/svg",svg=document.createElementNS(NS,"svg");
 svg.setAttribute("viewBox",`${x} ${y} ${w} ${h}`);
 const im=document.createElementNS(NS,"image");im.setAttribute("href","data:image/png;base64,"+v.img);
 im.setAttribute("x",x);im.setAttribute("y",y);im.setAttribute("width",w);im.setAttribute("height",h);svg.appendChild(im);
 v.ambientes.forEach((a,k)=>{if(!a.poligono.length)return;const p=document.createElementNS(NS,"path");
  p.setAttribute("d",pathOf(a));p.setAttribute("fill",COR[a.status]);p.setAttribute("fill-opacity",".28");p.setAttribute("fill-rule","evenodd");
  p.setAttribute("stroke",COR[a.status]);p.setAttribute("class","amb");p.dataset.k=k;
  p.addEventListener("mousemove",e=>{const r=plan.getBoundingClientRect();tip.style.display="block";
   tip.innerHTML=`<b>${a.nome}</b><br>medido ${f2(a.area_m2)} m² · rótulo ${f2(a.area_rotulo_m2)} m²<br>perímetro ${f2(a.perimetro_m)} m`+(a.area_piso_m2&&Math.abs(a.area_piso_m2-a.area_m2)>.01?`<br>piso total ${f2(a.area_piso_m2)} m²`:"")
    +(a.q?`<br>rodapé ${f2(a.q.rodape_m)} m · parede líquida ${f2(a.q.parede_liquida_m2)} m²<br>${a.q.n_portas} porta(s), ${a.q.n_janelas} janela(s) · PD ${f2(a.q.pe_direito_m)} m`:"");
   tip.style.left=Math.min(e.clientX-r.left+12,r.width-220)+"px";tip.style.top=(e.clientY-r.top+12)+"px"});
  p.addEventListener("mouseleave",()=>tip.style.display="none");p.addEventListener("click",()=>sel(k));svg.appendChild(p)});
 (v.vaos||[]).forEach(o=>{const r=document.createElementNS(NS,"rect"),[a,b,c,d]=o.r;
  r.setAttribute("x",a);r.setAttribute("y",b);r.setAttribute("width",Math.max(c-a,1.5));r.setAttribute("height",Math.max(d-b,1.5));
  r.setAttribute("fill",o.t==="porta"?"#C2610C":"#1E66C8");r.setAttribute("fill-opacity",".75");r.setAttribute("pointer-events","none");svg.appendChild(r)});
 plan.appendChild(svg);
 document.getElementById("vt").textContent=v.titulo+" · "+v.ambientes.length+" ambientes";
 document.getElementById("tb").innerHTML=v.ambientes.map((a,k)=>`<tr class="row" data-k="${k}"><td>${a.nome}</td><td class="n">${f2(a.area_rotulo_m2)}</td><td class="n">${f2(a.area_m2)}</td><td class="n">${fp(a.divergencia_pct)}</td><td><span class="chip ${a.status}">${TXT[a.status]}</span></td></tr>`).join("");
 document.querySelectorAll("tr.row").forEach(r=>r.addEventListener("click",()=>sel(+r.dataset.k)));
 const obs=v.ambientes.filter(a=>a.observacao).map(a=>`<b>${a.nome}:</b> ${a.observacao}`);
 document.getElementById("obs").innerHTML=`Escala desta vista: 1:${(v.escala/0.0254*72).toFixed(1).replace(".",",")} (${v.cotas} cotas conferidas).`+(obs.length?"<br>"+obs.join("<br>"):"");
 document.getElementById("esq").innerHTML=v.esquadrias.length?"<b>Esquadrias</b><ul>"+v.esquadrias.map(([k,q])=>`<li>${q} × ${k}</li>`).join("")+"</ul>":"";
}
function sel(k){document.querySelectorAll(".amb").forEach(p=>p.classList.toggle("sel",+p.dataset.k===k));
 document.querySelectorAll("tr.row").forEach(r=>r.classList.toggle("sel",+r.dataset.k===k))}
V.forEach((v,i)=>{const b=document.createElement("button");b.className="tab";b.role="tab";b.textContent=v.titulo;b.onclick=()=>mostrar(i);tabs.appendChild(b)});
mostrar(0);
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--obra", default="Obra")
    ap.add_argument("--saida", type=Path, required=True)
    ap.add_argument("--familia", default="39", choices=["29", "39"], help="família do bloco estrutural (padrão 39)")
    ap.add_argument("--sinapi", help="mês de referência do SINAPI, AAAA-MM (padrão: o último publicado)")
    ap.add_argument("--desonerado", action="store_true", default=None, help="usar preços com desoneração")
    ap.add_argument("--sem-preco", action="store_true", help="não gerar o orçamento (B4)")
    a = ap.parse_args()
    a.saida.mkdir(parents=True, exist_ok=True)
    dados = medir(a.pdf, a.saida, a.obra, a.familia)
    if not a.sem_preco:
        try:
            orc = orcamento(dados, a.saida, a.sinapi, a.desonerado)
        except Exception as e:                        # o orçamento não pode derrubar a medição
            print("B4: orçamento não gerado:", e)
            orc = None
        if orc:
            dados["orcamento"] = orc
            rs = f"{orc['total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            print(f"B4: SINAPI {orc['mes']} {orc['uf']}, custo direto R$ {rs}")
    (a.saida / "obra.json").write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    planilha(dados, a.saida / "medicao.xlsx")
    pagina_conferencia(dados, a.pdf, a.saida / "conferencia.html")
    SP.pagina(dados, a.pdf, a.saida / "paredes.html")
    if dados.get("paginacao", {}).get("vista_detalhe"):
        SPG.pagina(dados, a.pdf, a.saida / "paginacao.html")
    S3D.gerar(dados, a.saida / "modelo3d.html")
    conf = CONF.checar(dados)
    falhas = [c for c in conf if not c[3]]
    print(f"conferência: {len(conf) - len(falhas)} de {len(conf)} verificações ok")
    for g, item, res, _ in falhas:
        print(f"  CONFERIR {g} · {item}: {res}")
    st = Counter(x["status"] for x in dados["ambientes"])
    print(f"{len(dados['vistas'])} vistas, {len(dados['ambientes'])} ambientes {dict(st)}, {len(dados['esquadrias'])} esquadrias, "
          f"{len(dados['paredes'])} paredes {dict(Counter(p['tipo'] for p in dados['paredes']))}")
    print("saída:", a.saida)


if __name__ == "__main__":
    main()
