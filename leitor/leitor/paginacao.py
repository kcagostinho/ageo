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
- Amarração: em cada trecho, escolhe começar com inteiro ou meio bloco e deixar a sobra numa ou
  noutra ponta, para não haver junta a prumo com a fiada de baixo; se nenhuma arrumação padrão
  resolve, usa um compensador. Bloco T e pontas de verga se deslocam (até 20 cm) pelo mesmo motivo.
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
# junta a prumo: junta vertical a menos de PRUMO_CM da junta da fiada de baixo (bloco sobre bloco)
PRUMO_CM = 5.0
# corte mínimo: sobra menor que isso não vira pedaço de bloco; junta-se à peça vizinha
CORTE_MIN_CM = 5.0


def _sem_corte_pequeno(out, P, fim_lado="fim"):
    """Se a última peça é um corte menor que CORTE_MIN_CM, junta com a vizinha: meio + sobra vira um
    corte de P/2 + sobra; inteiro + sobra vira meio + corte de P/2 + sobra."""
    if len(out) < 2 or out[-1][2] != "corte" or out[-1][1] >= CORTE_MIN_CM:
        return out
    x, w, _ = out.pop()
    x0, w0, k0 = out.pop()
    if k0 == "meio":
        out.append((x0, w0 + w, "corte"))
    elif k0 == "int":
        out.append((x0, P / 2, "meio"))
        out.append((x0 + P / 2, w0 - P / 2 + w, "corte"))
    else:
        out.append((x0, w0 + w, "corte"))
    return out


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


def _encher(ini, fim, P, comeca_meio, tol):
    """Peças de um trecho [ini, fim]: ('int', 'meio', 'corte'). Começa com meio bloco se pedido."""
    out, x = [], ini
    if fim - ini <= tol:
        return out
    if comeca_meio and fim - x >= P / 2 - tol:
        out.append((x, P / 2, "meio")); x += P / 2
    n = int((fim - x + tol) // P)
    for _ in range(n):
        out.append((x, P, "int")); x += P
    if fim - x >= P / 2 - tol:
        out.append((x, P / 2, "meio")); x += P / 2
    if fim - x > tol:
        out.append((x, fim - x, "corte"))
    return _sem_corte_pequeno(out, P)


def _juntas(pecas):
    """Juntas verticais internas de uma fiada (encontro de duas peças vizinhas)."""
    pcs = sorted((p for p in pecas if p[2] not in ("vao", "cruzamento")), key=lambda p: p[0])
    return [b[0] for a, b in zip(pcs, pcs[1:]) if abs(a[0] + a[1] - b[0]) < 0.6]


def _melhor(ini, fim, P, tol, juntas_ant):
    """Escolhe a arrumação do trecho que não deixa junta a prumo com a fiada de baixo (amarração),
    depois a que gera menos cortes, depois a de maior defasagem. Opções: começar com bloco inteiro
    ou com meio bloco, e deixar a sobra (meio/corte) no fim ou no começo do trecho."""
    opcoes = []
    for cm in (False, True):
        if cm and fim - ini < P / 2 - tol:
            continue
        for espelho in (False, True):
            pcs = _encher(ini, fim, P, cm, tol)
            if espelho:     # mesma arrumação, preenchida da direita para a esquerda
                pcs = sorted(((ini + fim - (x + w), w, k) for x, w, k in pcs), key=lambda p_: p_[0])
            js = [b[0] for a, b in zip(pcs, pcs[1:])]
            if juntas_ant:
                dist = [min(abs(j_ - a) for a in juntas_ant) for j_ in js]
                alinhadas = sum(1 for d in dist if d < PRUMO_CM)
                dmin = min(dist) if dist else P
            else:
                alinhadas, dmin = 0, P
            cortes = sum(1 for p in pcs if p[2] == "corte")
            opcoes.append((alinhadas, cortes, -dmin, cm, espelho, pcs))
    if not opcoes:
        return []
    melhor = min(opcoes, key=lambda o: o[:5])
    if melhor[0] and juntas_ant:
        conta = lambda pcs: sum(1 for a, b in zip(pcs, pcs[1:]) if any(abs(b[0] - j_) < PRUMO_CM for j_ in juntas_ant))
        cands = [(melhor[0], melhor[1], melhor[5])]
        alt = _encher_amarrado(ini, fim, P, tol, juntas_ant)
        cands.append((conta(alt), sum(1 for p_ in alt if p_[2] == "corte"), alt))
        bus = _encher_busca(ini, fim, P, tol, juntas_ant)
        if bus:
            cands.append((conta(bus), sum(1 for p_ in bus if p_[2] == "corte"), bus))
        return min(cands, key=lambda c_: c_[:2])[2]
    return melhor[5]


def _encher_busca(ini, fim, P, tol, juntas_ant, passo=0.5):
    """Busca exaustiva (programação dinâmica em passos de 0,5 cm) da sequência de peças do trecho:
    inteiro, meio ou corte (de 5 cm a P - 5 cm, em múltiplos de 2,5 cm; o último corte fecha o trecho
    com qualquer medida ≥ 5 cm). Minimiza, nesta ordem: juntas a prumo, cortes, peças."""
    n = int(round((fim - ini) / passo))
    if n <= 0:
        return []
    inf = (10 ** 9,)
    melhor = [inf] * (n + 1)
    de = [None] * (n + 1)
    melhor[0] = (0, 0, 0)
    tam = [(int(round(P / passo)), "int", 0), (int(round(P / 2 / passo)), "meio", 0)]
    tam += [(int(round(c / passo)), "corte", 1) for c in [x * 2.5 for x in range(2, int(P / 2.5))] if CORTE_MIN_CM <= c <= P - CORTE_MIN_CM]
    k_tol = int(round(tol / passo))
    k_min = int(round(CORTE_MIN_CM / passo))

    def prumo(x):
        xc = ini + x * passo
        return 1 if any(abs(xc - a) < PRUMO_CM for a in juntas_ant) else 0

    for x in range(n + 1):
        if melhor[x] == inf:
            continue
        pr, ct, pc = melhor[x]
        if x and x < n:
            pass
        for w, k, c in tam:
            y = x + w
            if y > n + k_tol:
                continue
            fecha = abs(n - y) <= k_tol
            y2 = n if fecha else y
            if not fecha and n - y < k_min:
                continue                      # sobraria corte pequeno
            custo = (pr + (0 if fecha else prumo(y)), ct + c, pc + 1)
            if custo < melhor[y2]:
                melhor[y2], de[y2] = custo, (x, w if not fecha else n - x, k)
        r = n - x                             # fechar com um corte do tamanho exato
        if k_min <= r <= int(round((P - CORTE_MIN_CM) / passo)):
            custo = (pr, ct + 1, pc + 1)
            if custo < melhor[n]:
                melhor[n], de[n] = custo, (x, r, "corte")
    if melhor[n] == inf:
        return None
    out, y = [], n
    while y > 0:
        x, w, k = de[y]
        out.append((ini + x * passo, w * passo, k))
        y = x
    return out[::-1]


def _encher_amarrado(ini, fim, P, tol, juntas_ant):
    """Preenchimento guloso que evita junta a prumo peça a peça: tenta bloco inteiro, depois meio;
    se os dois caem sobre junta da fiada de baixo, usa um compensador (corte) que desloca o ritmo."""
    ok = lambda j_: all(abs(j_ - a) >= PRUMO_CM for a in juntas_ant)
    pcs, x = [], ini
    while fim - x > tol:
        resto = fim - x
        escolhido = None
        for w, k in ((P, "int"), (P / 2, "meio")):
            if w <= resto + tol and (abs(fim - (x + w)) <= tol or ok(x + w)):
                escolhido = (min(w, resto) if abs(fim - (x + w)) <= tol else w, k)
                break
        if escolhido is None:
            if resto < P / 2 - tol:
                escolhido = (resto, "corte")
            else:
                c = next((c for c in range(5, int(P / 2), 5) if ok(x + c) and (ok(x + c + P) or x + c + P >= fim - tol)), None)
                escolhido = (c, "corte") if c else ((P, "int") if P <= resto + tol else (P / 2, "meio"))
        w, k = escolhido
        pcs.append((x, w, k))
        x += w
    return _sem_corte_pequeno(pcs, P)


def _preencher(ini, fim, fam, juntas_ant, borda_esq, tol, pecas, cont, borda_dir="canto"):
    """Preenche [ini, fim] (cm) com inteiros, meio e corte, amarrado com a fiada de baixo.
    Trecho menor que CORTE_MIN_CM entre peças fixas não leva bloco: é enchimento de argamassa."""
    if tol < fim - ini < CORTE_MIN_CM:
        pecas.append((ini, fim - ini, "enchimento")); cont["enchimentos de argamassa (peças)"] += 1
        return
    for x, w, k in _melhor(ini, fim, fam["passo"], tol, juntas_ant):
        if k == "int":
            pecas.append((x, w, "inteiro")); cont[fam["inteiro"]] += 1
        elif k == "meio":
            pecas.append((x, w, "meio")); cont[fam["meio"]] += 1
        else:
            pecas.append((x, w, "corte")); cont["cortes (peças)"] += 1; cont["cortes (cm)"] += w
            if "vao" in (borda_esq, borda_dir):
                cont["cortes junto a vão"] += 1
            else:
                cont["cortes em trecho corrido"] += 1


def _canaletas(ini, fim, fam, tipo_can, tol, pecas, cont, juntas_ant=None):
    P = fam["passo"]
    larg = fam["inteiro"].split("×")[0]
    nome = f"canaleta {tipo_can} {larg}×19×{P - 1}"
    meia = f"meia canaleta {tipo_can} {larg}×19×{P // 2 - 1}"
    for x, w, k in _melhor(ini, fim, P, tol, juntas_ant or []):
        pecas.append((x, w, tipo_can))
        if k == "int":
            cont[nome] += 1
        elif k == "meio":
            cont[meia] += 1
        else:
            cont[nome] += 1; cont["cortes (peças)"] += 1; cont["cortes (cm)"] += w


def _acertar(pecas, folga=0.5):
    """Peças vizinhas com folga ou sobreposição de até 'folga' cm passam a se tocar exatamente
    (diferenças de arredondamento nas pontas de verga, bloco especial e preenchimento)."""
    pcs = sorted(pecas, key=lambda p: p[0])
    out = []
    for x, w, k in pcs:
        if out:
            x0, w0, k0 = out[-1]
            d_ = x - (x0 + w0)
            if 0 < abs(d_) <= folga:
                if k in ("vao", "cruzamento"):
                    out[-1] = (x0, x - x0, k0)          # a peça anterior se ajusta ao vão
                else:
                    x, w = x0 + w0, w + (x - (x0 + w0))
        out.append((x, w, k))
    return out


def _encostar(ocup, ini, fim):
    """Vergas e contravergas cuja ponta fica a menos de CORTE_MIN_CM da ponta da linha ou de outra
    ocupação são estendidas até ela (não sobra pedaço de bloco menor que 5 cm)."""
    ocup = sorted(ocup)
    out = []
    for i, (a, b, t) in enumerate(ocup):
        if t in ("verga", "contraverga"):
            esq = max([ini] + [o[1] for o in ocup[:i] if o[1] <= a])
            dir_ = min([fim] + [o[0] for o in ocup[i + 1:] if o[0] >= b])
            if 0 < a - esq < CORTE_MIN_CM:
                a = esq
            if 0 < dir_ - b < CORTE_MIN_CM:
                b = dir_
        out.append((a, b, t))
    return out


def _uniao(iv):
    out = []
    for a, b in sorted(iv):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def _uniao_tipada(iv, folga=0.0):
    """Une intervalos (a, b, tipo) que se sobrepõem ou ficam a menos de 'folga'; vale o tipo do primeiro."""
    out = []
    for a, b, t in sorted(iv):
        if out and a <= out[-1][1] + folga:
            out[-1] = (out[-1][0], max(out[-1][1], b), out[-1][2])
        else:
            out.append((a, b, t))
    return out


def _subtrair(iv, cortes):
    res = []
    for a, b in iv:
        pedacos = [(a, b)]
        for c0, c1 in cortes:
            novo = []
            for x0, x1 in pedacos:
                if c1 <= x0 or c0 >= x1:
                    novo.append((x0, x1))
                else:
                    if c0 > x0:
                        novo.append((x0, c0))
                    if c1 < x1:
                        novo.append((c1, x1))
            pedacos = novo
        res += [(x0, x1) for x0, x1 in pedacos if x1 - x0 > 0.5]
    return res


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
    juntas_ant: list = []
    ant: list = []
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
        # bloqueios nesta fiada, por prioridade: vãos > vergas/contravergas > blocos especiais
        vaos_k, elem = [], []
        for u0, u1, base, topo, tp in vaos:
            if base <= z0 < topo:
                vaos_k.append((u0, u1))
            elif z0 == topo and not (L["tipo"] == "estrutural" and k == n - 1):
                elem.append((u0 - tr, u1 + tr, "verga"))
            elif tp in ("janela", "varanda") and z0 == base - h:   # contraverga / cinta da mureta
                elem.append((u0 - tr, u1 + tr, "contraverga"))
        vaos_k = _uniao(vaos_k)
        # cruzamento em X: estrutural passa sempre sobre vedação; mesmo tipo alterna por fiada
        cruz = []
        for u_x, tipo_x in L.get("xs", []):
            if L["tipo"] != tipo_x:
                passa = L["tipo"] == "estrutural"
            else:
                passa = (L["o"] == "h") == (k % 2 == 0)
            if not passa:
                cruz.append((u_x - meia_t, u_x + meia_t, "cruzamento"))
        # pontas de verga/contraverga: transpasse mínimo de 30 cm; se a ponta cair sobre junta da
        # fiada de baixo, estende 5 a 20 cm para manter a amarração
        def _ponta(x, sentido):
            for d_ in (0, 5, 10, 15, 20):
                y = x + sentido * d_
                if all(abs(y - j_) >= PRUMO_CM for j_ in juntas_ant):
                    return y
            return x
        elem = [(_ponta(a, -1), _ponta(b, +1), t) for a, b, t in elem]
        # vergas/contravergas vizinhas (folga menor que um bloco) viram uma peça contínua;
        # nunca entram num vão desta fiada
        elem = _uniao_tipada(elem, folga=fam["passo"])
        elem = [(a, b, t) for a0, b0, t in elem for a, b in _subtrair([(a0, b0)], vaos_k)]
        respaldo = L["tipo"] == "estrutural" and k == n - 1
        if respaldo:
            x = ini
            for c0, c1, _ in sorted(cruz):
                _canaletas(x, c0, fam, "J" if L["fachada"] else "U", tol, pecas, cont, juntas_ant)
                pecas.append((c0, c1 - c0, "cruzamento"))
                x = c1
            _canaletas(x, fim, fam, "J" if L["fachada"] else "U", tol, pecas, cont, juntas_ant)
            cont["cinta de respaldo (m)"] += (fim - ini - sum(c1 - c0 for c0, c1, _ in cruz)) / 100
        else:
            # especiais: L (fam. 39) na ponta que passa
            if fam.get("L"):
                nomeL, pL = fam["L"]
                if lim[0][1] and lim[0][2] == "L":
                    pecas.append((ini, pL, "especial")); cont[nomeL] += 1; ini += pL
                if lim[1][1] and lim[1][2] == "L":
                    pecas.append((fim - pL, pL, "especial")); cont[nomeL] += 1; fim -= pL
            ocup = [(a, b, "vao") for a, b in vaos_k] + elem + cruz
            ocup = [(max(a, ini), min(b, fim), t) for a, b, t in ocup if min(b, fim) > max(a, ini)]
            ocup = _encostar(ocup, ini, fim)
            # T em fiadas pares: bloco especial centrado no encontro, só se não colidir com vão/verga
            if fam.get("T") and par:
                nomeT, pT = fam["T"]
                for t in L.get("ts", []):
                    pos = None
                    for d_ in (0, 5, -5, 10, -10, 15, -15, 20, -20):
                        a, b = t + d_ - pT / 2, t + d_ + pT / 2
                        lados_ok = all(not (0 < d2 < CORTE_MIN_CM) for d2 in
                                       [a - ini, fim - b] + [a - y1 for y0, y1, _ in ocup if y1 <= a] + [y0 - b for y0, y1, _ in ocup if y0 >= b])
                        if a >= ini and b <= fim and lados_ok and not any(a < y1 and b > y0 for y0, y1, _ in ocup):
                            if all(abs(a - j_) >= PRUMO_CM and abs(b - j_) >= PRUMO_CM for j_ in juntas_ant):
                                pos = (a, b); break
                            if pos is None and d_ == 0:
                                pos0 = (a, b)
                    pos = pos or locals().get("pos0")
                    if pos:
                        ocup.append((pos[0], pos[1], "especial")); cont[nomeT] += 1
                    else:
                        cont["amarração T sem bloco especial (junto a vão)"] += 1
                    pos0 = None
            ocup.sort()
            x, borda = ini, "livre" if L["ponta_a"] == "livre" else "canto"
            for b0, b1, tp in ocup:
                if b0 < x:          # segurança: nunca sobrepor peças
                    b0 = x
                if b1 <= b0:
                    continue
                _preencher(x, b0, fam, juntas_ant, borda, tol, pecas, cont, borda_dir="vao" if tp == "vao" else "canto")
                if tp in ("verga", "contraverga"):
                    _canaletas(b0, b1, fam, "U", tol, pecas, cont, juntas_ant)
                    cont[f"{tp}s (m)"] += (b1 - b0) / 100
                    cont[f"{tp}s {L['tipo']} (m)"] += (b1 - b0) / 100
                elif tp == "especial":
                    pecas.append((b0, b1 - b0, "especial"))
                elif tp == "cruzamento":
                    pecas.append((b0, b1 - b0, "cruzamento"))
                else:
                    pecas.append((b0, b1 - b0, "vao"))
                x, borda = b1, ("vao" if tp == "vao" else "canto")
            _preencher(x, fim, fam, juntas_ant, borda, tol, pecas, cont)
        pecas = _acertar(pecas)
        juntas_ant = _juntas(pecas)
        cont["juntas a prumo"] += sum(1 for j_ in juntas_ant if any(abs(j_ - a) < PRUMO_CM for a in ant)) if k else 0
        ant = juntas_ant
        if guardar:
            fiadas.append([(round(a, 1), round(round(a + w, 1) - round(a, 1), 1), t) for a, w, t in pecas])
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


def _cruzamentos(linhas: list[dict], m_por_pt: float, folga_pt: float = 6.0):
    """Linhas que se cruzam pelo meio (X): guarda em cada uma a posição (cm, a partir do início)
    e o tipo da outra. Encontros na ponta (L, T) já são tratados pelas pontas."""
    for L in linhas:
        L["xs"] = []
    for A in linhas:
        for B in linhas:
            if A["o"] != "h" or B["o"] != "v":
                continue
            if A["ini"] + folga_pt < B["c"] < A["fim"] - folga_pt and B["ini"] + folga_pt < A["c"] < B["fim"] - folga_pt:
                A["xs"].append(((B["c"] - A["ini"]) * m_por_pt * 100, B["tipo"]))
                B["xs"].append(((A["c"] - B["ini"]) * m_por_pt * 100, A["tipo"]))


def paginar(dados: dict, familia: str, guardar_vista: str | None = None, guardar_todas: bool = False):
    """Paginação de todas as linhas de parede, por pavimento. Devolve (contagem por pavimento, linhas).
    As peças bloco a bloco são guardadas para a vista 'guardar_vista' (ou para todas, com guardar_todas)."""
    pd = dados["premissas"]["pe_direito_m"]
    m = {v["id"]: v["m_por_pt"] for v in dados["vistas"]}
    por_pav, detalhes = {}, []
    for v in dados["vistas"]:
        ps = [p for p in dados["paredes"] if p["vista"] == v["id"]]
        linhas = linhas_de_parede(ps, m[v["id"]])
        _cruzamentos(linhas, m[v["id"]])
        guardar = guardar_todas or v["id"] == guardar_vista
        tot = Counter()
        for L in linhas:
            cont, fiadas = paginar_linha(L, familia, pd.get(v["titulo"], 2.6), guardar=guardar)
            cont["linhas"] += 1
            tot.update(cont)
            if guardar:
                detalhes.append({**{k: L[k] for k in ("id", "o", "tipo", "fachada", "ponta_a", "ponta_b", "ts", "xs", "segmentos")},
                                 "vista": v["id"],
                                 "eixo": [L["ini"], L["c"], L["fim"], L["c"]] if L["o"] == "h" else [L["c"], L["ini"], L["c"], L["fim"]],
                                 "comprimento_cm": round(L["comprimento_cm"], 1), "fiadas": fiadas,
                                 "cortes": cont["cortes (peças)"], "contagem": dict(cont)})
        if linhas:
            por_pav[v["titulo"]] = tot
    return por_pav, detalhes


def juntas_a_prumo(fiadas, tol_cm: float = PRUMO_CM) -> int:
    """Conta juntas verticais internas que caem a menos de tol_cm de uma junta da fiada de baixo
    (junta a prumo = bloco sobre bloco, sem amarração)."""
    def juntas(f):
        pcs = sorted((p for p in f if p[2] != "vao"), key=lambda p: p[0])
        return [b[0] for a, b in zip(pcs, pcs[1:]) if abs(a[0] + a[1] - b[0]) < 0.6]
    total = 0
    ant = None
    for f in fiadas:
        js = juntas(f)
        if ant is not None:
            total += sum(1 for j in js if any(abs(j - a) < tol_cm for a in ant))
        ant = js
    return total
