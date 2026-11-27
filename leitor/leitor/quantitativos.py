"""Quantitativos por ambiente a partir da medição: piso, teto, rodapé, parede bruta e líquida.

Regras (premissas, editáveis na planilha):
- Piso = área do polígono. Teto = área coberta (nas garagens, só a parte sob a projeção).
- Rodapé = contorno junto a parede − larguras das portas do ambiente.
- Parede bruta = contorno junto a parede × pé-direito (trechos sem parede, como guarda-corpo, ficam de fora).
- Vãos = soma de largura × altura das portas e janelas no contorno (altura pela etiqueta da planta).
- Parede líquida = bruta − vãos (critério de desconto de vãos fica para a EAP/SINAPI).
"""
from __future__ import annotations

import math
import unicodedata

PADRAO_ALTURA = {"porta": 2.10, "janela": 1.20, "varanda": 1.60}


def _sem_acento(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def classificar(nome: str) -> str:
    n = _sem_acento(nome)
    if any(k in n for k in ("elevador", "shaft", "poco")):
        return "técnico"
    if any(k in n for k in ("banheiro", "lavabo", "wc", "cozinha", "a.s.", "servico", "lavanderia")):
        return "molhada"
    if any(k in n for k in ("gourmet", "varanda", "sacada", "terraco")):
        return "externa"
    if "garagem" in n or "vaga" in n:
        return "garagem"
    if any(k in n for k in ("hall", "circula", "corredor", "escada")):
        return "circulação"
    return "seca"


def casar_etiquetas(vaos: list[dict], esquadrias: list[dict], m_por_pt: dict[str, float]):
    """Liga cada vão à etiqueta (L x H) mais próxima do mesmo tipo e mesma largura."""
    usadas = set()
    for v in sorted(vaos, key=lambda v: v["largura_m"]):
        if v["tipo"] == "varanda":      # altura e peitoril vêm da premissa da varanda
            v.setdefault("etiqueta", True)
            continue
        m = m_por_pt[v["vista"]]
        cands = []
        for i, e in enumerate(esquadrias):
            if i in usadas or e["vista"] != v["vista"] or e["tipo"] != v["tipo"]:
                continue
            if abs(e["largura_m"] - v["largura_m"]) > 0.06:
                continue
            d = math.dist(e["xy"], v["centro"]) * m
            if d <= 3.0:
                cands.append((d, i))
        if cands:
            _, i = min(cands)
            usadas.add(i)
            e = esquadrias[i]
            v.update(altura_m=e["altura_m"], peitoril_m=e["peitoril_m"], etiqueta=True)
        else:
            v.update(altura_m=PADRAO_ALTURA[v["tipo"]], peitoril_m=None, etiqueta=False)


def calcular(dados: dict, pe_direito: dict[str, float], pd_padrao: float = 2.60) -> list[dict]:
    vaos = {v["id"]: v for v in dados["vaos"]}
    linhas = []
    for idx, a in enumerate(dados["ambientes"]):
        if a["area_piso_m2"] is None:
            continue
        tipo = classificar(a["nome"])
        portas = [vaos[i] for i in a.get("vaos", []) if vaos[i]["tipo"] == "porta"]
        janelas = [vaos[i] for i in a.get("vaos", []) if vaos[i]["tipo"] == "janela"]
        varandas = [vaos[i] for i in a.get("vaos", []) if vaos[i]["tipo"] == "varanda"]
        obs = []
        if tipo == "técnico":
            obs.append("Poço de elevador: não recebe acabamento de piso/parede.")
        if "escada" in a["nome"].lower():
            obs.append("Piso = projeção horizontal; degraus (piso + espelho) a quantificar à parte.")
        if a["sem_parede_m"] and a["sem_parede_m"] > 0.3:
            obs.append(f"{a['sem_parede_m']:.2f} m de contorno sem parede (passagem ou lado aberto).")
        for v in varandas:
            obs.append(f"Abertura da varanda {v['largura_m']:.2f} × {v['altura_m']:.2f} m (mureta de {v['peitoril_m']:.2f} m + gradil) descontada da parede.")
        if tipo == "garagem":
            obs.append("Contorno da garagem = muros/arrimo: altura e acabamento a confirmar.")
        if any(not v["etiqueta"] for v in portas + janelas):
            obs.append("Vão sem etiqueta na planta: altura padrão assumida.")
        if a.get("observacao"):
            obs.append(a["observacao"])
        pdm = pe_direito.get(a["pavimento"], pd_padrao)
        vaos_m2 = sum(v["largura_m"] * v["altura_m"] for v in portas + janelas + varandas)
        linhas.append({
            "indice_ambiente": idx, "vista": a["vista"],
            "pavimento": a["pavimento"], "ambiente": a["nome"], "tipo": tipo,
            "rodape_m": round(max(a["perimetro_parede_m"] - sum(v["largura_m"] for v in portas), 0), 3),
            "parede_bruta_m2": round(a["perimetro_parede_m"] * pdm, 3),
            "parede_liquida_m2": round(a["perimetro_parede_m"] * pdm - vaos_m2, 3),
            "pe_direito_m": pe_direito.get(a["pavimento"], pd_padrao),
            "piso_m2": round(a["area_piso_m2"], 3), "teto_m2": round(a.get("area_teto_m2") or a["area_piso_m2"], 3),
            "perimetro_m": round(a["perimetro_m"], 3), "perimetro_parede_m": round(a["perimetro_parede_m"], 3),
            "sem_parede_m": round(a["sem_parede_m"], 3),
            "n_portas": len(portas), "larg_portas_m": round(sum(v["largura_m"] for v in portas), 3),
            "n_janelas": len(janelas),
            "area_vaos_m2": round(vaos_m2, 3),
            "observacao": " ".join(obs),
        })
    return linhas
