"""Paginação estimada da alvenaria, fiada a fiada, para comparar famílias de bloco.

Estimativa de orçamento — a paginação executiva é do projeto de alvenaria estrutural. Regras:
- Paredes colineares e contíguas, de mesmo tipo, formam uma "linha de parede" contínua.
- Canto em L: as linhas se alternam (horizontais passam nas fiadas ímpares, verticais nas pares);
  a que passa vai até a face externa (+t/2), a outra para na face interna (−t/2).
- Encontro em T: a parede que chega para na face da outra (−t/2). Em fiadas alternadas, se as duas
  forem estruturais, entra o bloco especial de amarração T da família, centrado no encontro.
- Família 39 com bloco de 14 cm: canto em L usa o bloco 14×19×34 na ponta que passa.
- Vãos: altura de alvenaria arredondada para a fiada de cima (porta 2,10 → vão de 2,20).
  Verga (canaleta) na fiada acima do vão; contraverga (canaleta) na fiada abaixo do peitoril;
  ambas com transpasse de cada lado.
- Estrutural: última fiada inteira em canaleta (cinta de respaldo): J na fachada, U nas internas.
  Vedação: última fiada em bloco comum, com encunhamento.
- Amarração junto a vão ou ponta livre: fiadas pares começam com meio bloco.
- Sobra fora do módulo (acima da tolerância) → corte/compensador, contado à parte.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict

FAMILIAS = {
    "29": {"nome": "Família 29 (14×19×29, módulo 15)", "passo": 30, "L": None, "T": ("14×19×44", 45),
           "inteiro": "14×19×29", "meio": "14×19×14"},
    "39": {"nome": "Família 39 (14×19×39, módulo 20)", "passo": 40, "L": ("14×19×34", 35), "T": ("14×19×54", 55),
           "inteiro": "14×19×39", "meio": "14×19×19"},
}
VEDACAO = {"nome": "Vedação 9×19×39", "passo": 40, "L": None, "T": None, "inteiro": "9×19×39", "meio": "9×19×19"}

PREMISSAS = {
    "fiada_cm": 20, "junta_cm": 1, "tolerancia_cm": 1.5, "transpasse_verga_cm": 30,
    "meia_espessura_parede_cm": 7.5,
}


def linhas_de_parede(paredes: list[dict], m_por_pt: float) -> list[dict]:
    """Une segmentos colineares e contíguos de mesmo tipo numa linha de parede."""
    linhas = []
    grupos = defaultdict(list)
    for p in paredes:
        if p["tipo"] not in ("estrutural", "vedação"):
            continue
        e = p["eixo"]
        c = e[1] if p["o"] == "h" else e[0]
        a, b = (e[0], e[2]) if p["o"] == "h" else (e[1], e[3])
        grupos[(p["o"], p["tipo"])].append((c, a, b, p))
    for (o, tipo), itens in grupos.items():
        itens.sort(key=lambda x: (x[0], x[1]))
        usados = [False] * len(itens)
        for i, (c, a, b, p) in enumerate(itens):
            if usados[i]:
                continue
            usados[i] = True
            cadeia = [(a, b, p)]
            fim = b
            mudou = True
            while mudou:
                mudou = False
                for j, (c2, a2, b2, p2) in enumerate(itens):
                    if not usados[j] and abs(c2 - c) <= 1.5 and abs(a2 - fim) <= 2.0:
                        cadeia.append((a2, b2, p2))
                        fim = b2
                        usados[j] = mudou = True
            ini = cadeia[0][0]
            vaos = []
            for a2, b2, p2 in cadeia:
                for v in p2["vaos"]:
                    vaos.append({**v, "u0_cm": (a2 - ini) * m_por_pt * 100 + v["inicio_m"] * 100})
            linhas.append({
                "id": cadeia[0][2]["id"] + ("+" if len(cadeia) > 1 else ""), "o": o, "tipo": tipo, "c": c,
                "ini": ini, "fim": fim, "comprimento_cm": (fim - ini) * m_por_pt * 100,
                "fachada": any(x[2]["fachada"] for x in cadeia),
                "ponta_a": cadeia[0][2]["encontros"]["a"], "ponta_b": cadeia[-1][2]["encontros"]["b"],
                "segmentos": [x[2]["id"] for x in cadeia], "vaos": vaos,
            })
    # encontros em T no meio de cada linha (parede estrutural que chega nela)
    for L in linhas:
        L["ts"] = []
        if L["tipo"] != "estrutural":
            continue
        for p in paredes:
            if p["tipo"] != "estrutural" or p["o"] == L["o"]:
                continue
            e = p["eixo"]
            for lado, (x, y) in (("a", e[:2]), ("b", e[2:])):
                if p["encontros"][lado] not in ("T", "X"):
                    continue
                perp, ao_longo = (y, x) if L["o"] == "h" else (x, y)
                if abs(perp - L["c"]) <= 3 and L["ini"] + 3 < ao_longo < L["fim"] - 3:
                    L["ts"].append((ao_longo - L["ini"]) * 0 + (ao_longo - L["ini"]))
        L["ts"] = sorted({round(t * m_por_pt * 100, 1) for t in L["ts"]})
    return linhas


def _preencher(ini, fim, fam, fiada_par, borda_esq, tol, pecas, cont, borda_dir="canto"):
    """Preenche [ini, fim] (cm) com inteiros, meio e corte. borda_esq: 'vao'/'livre' pede amarração."""
    P = fam["passo"]
    r = fim - ini
    x = ini
    if r <= tol:
        return
    if fiada_par and borda_esq in ("vao", "livre") and r >= P / 2 - tol:
        pecas.append((x, P / 2, "meio")); cont[fam["meio"]] += 1
        x += P / 2; r -= P / 2
    n = int((r + tol) // P)
    for _ in range(n):
        pecas.append((x, P, "inteiro")); cont[fam["inteiro"]] += 1
        x += P
    r = fim - x
    if r >= P / 2 - tol:
        pecas.append((x, P / 2, "meio")); cont[fam["meio"]] += 1
        x += P / 2; r = fim - x
    if r > tol:
        pecas.append((x, r, "corte")); cont["cortes (peças)"] += 1; cont["cortes (cm)"] += r
        if "vao" in (borda_esq, borda_dir):
            cont["cortes junto a vão"] += 1
        else:
            cont["cortes em trecho corrido"] += 1


def _canaletas(ini, fim, fam, tipo_can, tol, pecas, cont):
    P = fam["passo"]
    larg = fam["inteiro"].split("×")[0]
    nome = f"canaleta {tipo_can} {larg}×19×{P - 1}"
    meia = f"meia canaleta {tipo_can} {larg}×19×{P // 2 - 1}"
    x, r = ini, fim - ini
    n = int((r + tol) // P)
    for _ in range(n):
        pecas.append((x, P, tipo_can)); cont[nome] += 1; x += P
    r = fim - x
    if r >= P / 2 - tol:
        pecas.append((x, P / 2, tipo_can)); cont[meia] += 1; x += P / 2; r = fim - x
    if r > tol:
        pecas.append((x, r, tipo_can)); cont[nome] += 1; cont["cortes (peças)"] += 1; cont["cortes (cm)"] += r


def paginar_linha(L: dict, familia: str, pe_direito_m: float, prem=PREMISSAS, guardar=False):
    fam = FAMILIAS[familia] if L["tipo"] == "estrutural" else VEDACAO
    h, tol, tr = prem["fiada_cm"], prem["tolerancia_cm"], prem["transpasse_verga_cm"]
    meia_t = prem["meia_espessura_parede_cm"]
    n = round(pe_direito_m * 100 / h)
    comp = L["comprimento_cm"]
    cont = Counter()
    fiadas = []
    # vãos em cm: (u0, u1, base, topo)
    vaos = []
    for v in L["vaos"]:
        w = v["largura_m"] * 100
        if v["tipo"] == "porta":
            base, topo = 0, math.ceil((v.get("altura_m") or 2.10) * 100 / h - 1e-6) * h
        else:
            pe = (v.get("peitoril_m") or 1.0) * 100
            base = math.floor(pe / h + 1e-6) * h
            topo = math.ceil((pe + (v.get("altura_m") or 1.2) * 100) / h - 1e-6) * h
        vaos.append((v["u0_cm"], v["u0_cm"] + w, base, topo, v["tipo"]))
    for k in range(n):
        par = k % 2 == 1
        z0 = k * h
        pecas: list = []
        # pontas
        lim = []
        for lado, tipo in (("a", L["ponta_a"]), ("b", L["ponta_b"])):
            if tipo == "L":
                passa = (L["o"] == "h") == (k % 2 == 0)
                ext = meia_t if passa else -meia_t
            elif tipo in ("T", "X"):
                passa, ext = False, -meia_t
            else:
                passa, ext = False, 0.0
            lim.append((ext, passa, tipo))
        ini, fim = -lim[0][0], comp + lim[1][0]
        # bloqueios nesta fiada: vãos, vergas/contravergas, blocos especiais
        bloq = []   # (u0, u1, tipo)
        for u0, u1, base, topo, tp in vaos:
            if base <= z0 < topo:
                bloq.append((u0, u1, "vao"))
            elif z0 == topo and not (L["tipo"] == "estrutural" and k == n - 1):
                bloq.append((max(u0 - tr, ini), min(u1 + tr, fim), "verga"))
            elif tp == "janela" and z0 == base - h:
                bloq.append((max(u0 - tr, ini), min(u1 + tr, fim), "contraverga"))
        respaldo = L["tipo"] == "estrutural" and k == n - 1
        if respaldo:
            _canaletas(ini, fim, fam, "J" if L["fachada"] else "U", tol, pecas, cont)
        else:
            # especiais: L (fam. 39) na ponta que passa; T em fiadas pares
            if fam.get("L"):
                nomeL, pL = fam["L"]
                if lim[0][1] and lim[0][2] == "L":
                    pecas.append((ini, pL, "especial")); cont[nomeL] += 1; ini += pL
                if lim[1][1] and lim[1][2] == "L":
                    pecas.append((fim - pL, pL, "especial")); cont[nomeL] += 1; fim -= pL
            if fam.get("T") and par:
                nomeT, pT = fam["T"]
                for t in L.get("ts", []):
                    if not any(b0 - 1 <= t <= b1 + 1 for b0, b1, _ in bloq):
                        bloq.append((t - pT / 2, t + pT / 2, "especial"))
                        cont[nomeT] += 1
            bloq.sort()
            # funde sobreposições
            fund = []
            for b in bloq:
                if fund and b[0] <= fund[-1][1]:
                    a0, a1, t0 = fund[-1]
                    fund[-1] = (a0, max(a1, b[1]), t0 if t0 != "vao" else "vao")
                else:
                    fund.append(b)
            x, borda = ini, "livre" if L["ponta_a"] == "livre" else "canto"
            for b0, b1, tp in fund:
                b0, b1 = max(b0, ini), min(b1, fim)
                if b1 <= b0:
                    continue
                _preencher(x, b0, fam, par, borda, tol, pecas, cont, borda_dir="vao" if tp == "vao" else "canto")
                if tp in ("verga", "contraverga"):
                    _canaletas(b0, b1, fam, "U", tol, pecas, cont)
                    cont[f"{tp}s (m)"] += (b1 - b0) / 100
                elif tp == "especial":
                    pecas.append((b0, b1 - b0, "especial"))
                else:
                    pecas.append((b0, b1 - b0, "vao"))
                x, borda = b1, ("vao" if tp == "vao" else "canto")
            _preencher(x, fim, fam, par, borda, tol, pecas, cont)
        if guardar:
            fiadas.append([(round(a, 1), round(w, 1), t) for a, w, t in pecas])
    cont["linhas fechadas sem corte"] += 1 if cont["cortes (peças)"] == 0 else 0
    # ajuste de modulação: quanto o comprimento da 1ª fiada teria de mudar para fechar
    # em múltiplo de meio bloco (sem contar vãos)
    passo = fam["passo"] / 2
    run0 = comp + sum((meia_t if ((L["o"] == "h") and t == "L") else (-meia_t if t in ("L", "T", "X") else 0.0))
                      for t in (L["ponta_a"], L["ponta_b"]))
    resto = run0 % passo
    cont["ajuste de modulação (cm)"] += min(resto, passo - resto)
    cont["linhas que fecham no módulo"] += 1 if min(resto, passo - resto) <= tol else 0
    return cont, fiadas


def paginar(dados: dict, familia: str, guardar_vista: str | None = None):
    """Paginação de todas as linhas de parede, por pavimento. Devolve (contagem por pavimento, linhas)."""
    pd = dados["premissas"]["pe_direito_m"]
    m = {v["id"]: v["m_por_pt"] for v in dados["vistas"]}
    por_pav, detalhes = {}, []
    for v in dados["vistas"]:
        ps = [p for p in dados["paredes"] if p["vista"] == v["id"]]
        linhas = linhas_de_parede(ps, m[v["id"]])
        tot = Counter()
        for L in linhas:
            cont, fiadas = paginar_linha(L, familia, pd.get(v["titulo"], 2.6), guardar=(v["id"] == guardar_vista))
            cont["linhas"] += 1
            tot.update(cont)
            if v["id"] == guardar_vista:
                detalhes.append({**{k: L[k] for k in ("id", "o", "tipo", "fachada", "ponta_a", "ponta_b", "ts", "segmentos")},
                                 "eixo": [L["ini"], L["c"], L["fim"], L["c"]] if L["o"] == "h" else [L["c"], L["ini"], L["c"], L["fim"]],
                                 "comprimento_cm": round(L["comprimento_cm"], 1), "fiadas": fiadas,
                                 "cortes": cont["cortes (peças)"], "contagem": dict(cont)})
        if linhas:
            por_pav[v["titulo"]] = tot
    return por_pav, detalhes
