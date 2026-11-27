"""Saídas da paginação: abas da planilha (comparativo das famílias) e página com as elevações."""
from __future__ import annotations

import base64
import html
import json

import pymupdf
from openpyxl.styles import Alignment, Font, PatternFill

from .paginacao import FAMILIAS, VEDACAO, PREMISSAS


def _itens(fam_id: str):
    """Itens da comparação, na ordem da planilha: (grupo, descrição, chave na contagem por família)."""
    f = FAMILIAS[fam_id]
    P = f["passo"]
    it = [("Estrutural (14 cm)", "Bloco inteiro", f["inteiro"]),
          ("Estrutural (14 cm)", "Meio bloco", f["meio"]),
          ("Estrutural (14 cm)", "Bloco de amarração em L", f["L"][0] if f["L"] else None),
          ("Estrutural (14 cm)", "Bloco de amarração em T", f["T"][0] if f["T"] else None),
          ("Estrutural (14 cm)", "Canaleta J (cinta na fachada)", f"canaleta J 14×19×{P - 1}"),
          ("Estrutural (14 cm)", "Meia canaleta J", f"meia canaleta J 14×19×{P // 2 - 1}"),
          ("Estrutural (14 cm)", "Canaleta U (cinta interna, vergas, contravergas)", f"canaleta U 14×19×{P - 1}"),
          ("Estrutural (14 cm)", "Meia canaleta U", f"meia canaleta U 14×19×{P // 2 - 1}"),
          ("Vedação (9 cm)", "Bloco inteiro 9×19×39", VEDACAO["inteiro"]),
          ("Vedação (9 cm)", "Meio bloco 9×19×19", VEDACAO["meio"]),
          ("Vedação (9 cm)", "Canaleta U 9×19×39 (vergas, contravergas)", "canaleta U 9×19×39"),
          ("Vedação (9 cm)", "Meia canaleta U 9×19×19", "meia canaleta U 9×19×19"),
          ("Elementos", "Vergas (m)", "vergas (m)"),
          ("Elementos", "Contravergas (m)", "contravergas (m)"),
          ("Modulação", "Cortes/compensadores (peças)", "cortes (peças)"),
          ("Modulação", "   … junto a portas e janelas", "cortes junto a vão"),
          ("Modulação", "   … em trecho corrido de parede", "cortes em trecho corrido"),
          ("Modulação", "Juntas a prumo (bloco sobre bloco, sem amarração)", "juntas a prumo"),
          ("Modulação", "Linhas de parede que fecham no módulo", "linhas que fecham no módulo"),
          ("Modulação", "Linhas de parede (total)", "linhas")]
    return it


def abas(wb, dados, cabecalho):
    pag = dados["paginacao"]
    pavs = list(pag["29"]["por_pavimento"].keys())
    tipo1 = next((p for p in pavs if "1º" in p), pavs[0])
    ws = wb.create_sheet("Paginação")
    cabecalho(ws, ["Grupo", "Item", f"Fam. 29 · {tipo1}", f"Fam. 39 · {tipo1}", "Fam. 29 · obra", "Fam. 39 · obra",
                   "Peça fam. 29", "Peça fam. 39"], [20, 46, 16, 16, 15, 15, 22, 22])
    it29, it39 = _itens("29"), _itens("39")
    for r, ((g, desc, k29), (_, _, k39)) in enumerate(zip(it29, it39), 2):
        t29 = {k: sum(c.get(k, 0) for c in pag["29"]["por_pavimento"].values()) for k in (k29,) if k}
        t39 = {k: sum(c.get(k, 0) for c in pag["39"]["por_pavimento"].values()) for k in (k39,) if k}
        a = pag["29"]["por_pavimento"][tipo1].get(k29, 0) if k29 else None
        b = pag["39"]["por_pavimento"][tipo1].get(k39, 0) if k39 else None
        vals = [g, desc, a, b, t29.get(k29) if k29 else None, t39.get(k39) if k39 else None,
                k29 if k29 and "×" in k29 else ("—" if not k29 else ""), k39 if k39 and "×" in k39 else ("—" if not k39 else "")]
        for col, v in enumerate(vals, 1):
            c = ws.cell(row=r, column=col, value=round(v, 2) if isinstance(v, float) else v)
            if col in (3, 4, 5, 6):
                c.number_format = "#,##0" if "(m)" not in desc else "#,##0.0"
    n = len(it29) + 1
    # indicadores
    r = n + 2
    ws.cell(row=r, column=1, value="Indicadores (pavimento-tipo)").font = Font(bold=True)
    ind = []
    for fam in ("29", "39"):
        c = pag[fam]["por_pavimento"][tipo1]
        f = FAMILIAS[fam]
        est = sum(v for k, v in c.items() if k.startswith(("14×", "canaleta J 14", "meia canaleta J 14", "canaleta U 14", "meia canaleta U 14")))
        ind.append((est, pag[fam]["area_estrutural_tipo_m2"]))
    linhas_ind = [("Peças estruturais no pavimento-tipo (un)", ind[0][0], ind[1][0]),
                  ("Área líquida de parede estrutural (m²)", ind[0][1], ind[1][1]),
                  ("Peças estruturais por m²", ind[0][0] / ind[0][1], ind[1][0] / ind[1][1])]
    for i, (t, a, b) in enumerate(linhas_ind, r + 1):
        ws.cell(row=i, column=2, value=t)
        ws.cell(row=i, column=3, value=round(a, 2)).number_format = "#,##0.00"
        ws.cell(row=i, column=4, value=round(b, 2)).number_format = "#,##0.00"
    r = r + len(linhas_ind) + 2
    notas = [
        "Estimativa de orçamento. A paginação executiva é do projeto de alvenaria estrutural.",
        f"Premissas: fiada {PREMISSAS['fiada_cm']} cm; junta {PREMISSAS['junta_cm']} cm; tolerância de ajuste de junta ±{PREMISSAS['tolerancia_cm']} cm; "
        f"transpasse de verga/contraverga {PREMISSAS['transpasse_verga_cm']} cm de cada lado; vão de alvenaria arredondado para a fiada de cima.",
        "Estrutural: última fiada em canaleta (cinta de respaldo; J na fachada). Vedação: última fiada em bloco comum com encunhamento.",
        "Térreo e subsolo (sob a transição) e muros não entram na paginação: aparecem como 'a definir' na aba Paredes.",
        "Amarração: em cada trecho de cada fiada o leitor escolhe começar com bloco inteiro ou meio bloco, e deixar a sobra numa ou noutra ponta, "
        "para nenhuma junta vertical ficar a prumo com a fiada de baixo; blocos de amarração T e pontas de verga se deslocam alguns centímetros pelo mesmo motivo.",
        "Cortes = sobras fora do módulo (corte de bloco ou compensador). Junto a vão indica largura/posição de porta ou janela fora do módulo; "
        "em trecho corrido indica comprimento de parede fora do módulo.",
    ]
    for i, t in enumerate(notas, r):
        c = ws.cell(row=i, column=1, value=t)
        c.font = Font(italic=True)
    # por parede (pavimento-tipo)
    wp = wb.create_sheet("Paginação por parede")
    cabecalho(wp, ["Linha de parede", "Tipo", "Fachada", "Comprimento (m)", "Pontas", "Fam. 29: cortes", "Fam. 29: ajuste p/ módulo (cm)",
                   "Fam. 39: cortes", "Fam. 39: ajuste p/ módulo (cm)"], [16, 12, 9, 14, 14, 14, 18, 14, 18])
    d29 = {x["id"]: x for x in pag["29"]["detalhes"]}
    for i, x in enumerate(pag["39"]["detalhes"], 2):
        y = d29.get(x["id"], {"cortes": None, "contagem": {}})
        vals = [x["id"], x["tipo"], "sim" if x["fachada"] else "não", round(x["comprimento_cm"] / 100, 2), f'{x["ponta_a"]} / {x["ponta_b"]}',
                y["cortes"], round(y["contagem"].get("ajuste de modulação (cm)", 0), 1),
                x["cortes"], round(x["contagem"].get("ajuste de modulação (cm)", 0), 1)]
        for col, v in enumerate(vals, 1):
            wp.cell(row=i, column=col, value=v)
    wp.auto_filter.ref = f"A1:I{len(pag['39']['detalhes']) + 1}"


def pagina(dados, pdf, destino):
    pag = dados["paginacao"]
    v1 = next(v for v in dados["vistas"] if v["id"] == pag["vista_detalhe"])
    doc = pymupdf.open(str(pdf))
    x0, y0, x1, y1 = v1["caixa"]
    x0, y0, x1, y1 = x0 - 15, y0 - 15, x1 + 15, y1 + 15
    pix = doc[v1["pagina"] - 1].get_pixmap(matrix=pymupdf.Matrix(1.4, 1.4), clip=pymupdf.Rect(x0, y0, x1, y1), colorspace=pymupdf.csGRAY)
    resumo = {}
    for fam in ("29", "39"):
        it = _itens(fam)
        c = pag[fam]["por_pavimento"][v1["titulo"]]
        resumo[fam] = [[g, d, round(c.get(k, 0), 1) if k else None] for g, d, k in it]
    payload = {"titulo": v1["titulo"], "caixa": [x0, y0, x1 - x0, y1 - y0], "img": base64.b64encode(pix.tobytes("png")).decode(),
               "m": v1["m_por_pt"], "pd": dados["premissas"]["pe_direito_m"].get(v1["titulo"], 2.6),
               "fam": {f: {"nome": FAMILIAS[f]["nome"],
                           "linhas": [{k: x[k] for k in ("id", "tipo", "fachada", "eixo", "comprimento_cm", "fiadas", "cortes", "ponta_a", "ponta_b", "segmentos")}
                                      for x in pag[f]["detalhes"]]} for f in ("29", "39")},
               "resumo": resumo}
    txt = MODELO.replace("__DADOS__", json.dumps(payload, ensure_ascii=False)).replace("__OBRA__", html.escape(dados["obra"]))
    destino.write_text(txt, encoding="utf-8")


MODELO = r"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Paginação da Alvenaria</title>
<style>
:root{--bg:#FAFAF7;--card:#fff;--elev:#F1EFE8;--bd:rgba(0,0,0,.1);--tx:#1A1A1A;--mut:#5F5E5A;--dim:#888780;--acc:#0F6E56;--bloco:#D9D6CC;--meio:#EDEAE0;--esp:#8E7CC3;--can:#E39B3A;--ver:#C0392B;--corte:#1A1A1A}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#1A1A1A;--card:#242422;--elev:#2C2C2A;--bd:rgba(255,255,255,.12);--tx:#F5F5F2;--mut:#B4B2A9;--dim:#888780;--acc:#5DCAA5;--bloco:#7A776E;--meio:#A9A598;--corte:#FFFFFF}}
:root[data-theme=dark]{--bg:#1A1A1A;--card:#242422;--elev:#2C2C2A;--bd:rgba(255,255,255,.12);--tx:#F5F5F2;--mut:#B4B2A9;--dim:#888780;--acc:#5DCAA5;--bloco:#7A776E;--meio:#A9A598;--corte:#FFFFFF}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}
.wrap{max-width:1320px;margin:0 auto;padding:16px}h1{font-size:18px;margin:0 0 2px;font-weight:600}.sub{color:var(--mut);font-size:12px;margin-bottom:12px}
.seg{display:inline-flex;border:1px solid var(--bd);border-radius:8px;overflow:hidden;margin-bottom:10px}
.seg button{border:0;background:var(--card);color:var(--tx);padding:6px 14px;font:inherit;font-size:13px;cursor:pointer}
.seg button[aria-pressed=true]{background:var(--acc);color:#fff}
.grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:12px;align-items:start}
.card{background:var(--card);border:1px solid var(--bd);border-radius:12px;overflow:hidden}
.plan{background:#fff}.plan svg{display:block;width:100%;height:auto}.plan line{cursor:pointer}.plan line.sel{stroke:#000!important;stroke-opacity:1!important}
.pad{padding:12px}h2{font-size:13px;margin:0 0 8px;color:var(--mut);text-transform:uppercase;letter-spacing:.4px}
.elev{overflow-x:auto}.elev svg{display:block;min-width:100%}
table{width:100%;border-collapse:collapse;font-size:12.5px;font-variant-numeric:tabular-nums}
th{text-align:left;color:var(--mut);font-weight:500;border-bottom:1px solid var(--bd);padding:5px 4px}td{border-bottom:1px solid var(--bd);padding:4px}
td.n,th.n{text-align:right}tr.g td{color:var(--mut);font-size:11.5px;text-transform:uppercase;letter-spacing:.3px;padding-top:10px}
.leg{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;color:var(--mut);margin-top:8px}.leg i{display:inline-block;width:14px;height:10px;margin-right:4px;vertical-align:-1px;border:1px solid rgba(0,0,0,.2)}
.info{font-size:12.5px;color:var(--mut);margin:6px 0 8px}
@media (max-width:950px){.grid{grid-template-columns:1fr}}
</style></head><body><div class="wrap">
<h1>Paginação da alvenaria · __OBRA__</h1>
<div class="sub">Estimativa fiada a fiada para comparar famílias de bloco de concreto. Clique numa parede na planta para ver a elevação.</div>
<div class="seg" id="seg"><button data-f="29">Família 29</button><button data-f="39">Família 39</button></div>
<div class="grid">
<div class="card"><div class="plan" id="plan"></div></div>
<div class="card pad"><h2 id="et">Elevação</h2><div class="info" id="ei">Selecione uma parede na planta.</div><div class="elev" id="elev"></div>
<div class="leg"><span><i style="background:var(--bloco)"></i>inteiro</span><span><i style="background:var(--meio)"></i>meio</span><span><i style="background:var(--esp)"></i>amarração (L/T)</span><span><i style="background:var(--can)"></i>canaleta (cinta, verga, contraverga)</span><span><i style="background:var(--corte)"></i>corte/compensador</span><span><i style="background:transparent;border-style:dashed"></i>vão</span></div>
</div></div>
<div class="card pad" style="margin-top:12px"><h2 id="rt"></h2><table><thead><tr><th>Item</th><th class="n">Família 29</th><th class="n">Família 39</th></tr></thead><tbody id="rb"></tbody></table></div>
</div>
<script>
const D=__DADOS__;let fam="39",sel=null;
const COR={inteiro:"var(--bloco)",meio:"var(--meio)",especial:"var(--esp)",J:"var(--can)",U:"var(--can)",corte:"var(--corte)"};
const f0=n=>n==null?"—":n.toLocaleString("pt-BR",{maximumFractionDigits:1});
function planta(){
 const [x,y,w,h]=D.caixa,NS="http://www.w3.org/2000/svg",svg=document.createElementNS(NS,"svg");svg.setAttribute("viewBox",`${x} ${y} ${w} ${h}`);
 const im=document.createElementNS(NS,"image");im.setAttribute("href","data:image/png;base64,"+D.img);im.setAttribute("x",x);im.setAttribute("y",y);im.setAttribute("width",w);im.setAttribute("height",h);im.setAttribute("opacity",".45");svg.appendChild(im);
 D.fam[fam].linhas.forEach((L,i)=>{const l=document.createElementNS(NS,"line"),[a,b,c,d]=L.eixo;l.setAttribute("x1",a);l.setAttribute("y1",b);l.setAttribute("x2",c);l.setAttribute("y2",d);
  l.setAttribute("stroke",L.tipo==="estrutural"?"#C0392B":"#2471A3");l.setAttribute("stroke-width",L.tipo==="estrutural"?8:5);l.setAttribute("stroke-opacity",".7");
  if(sel===L.id)l.classList.add("sel");l.addEventListener("click",()=>{sel=L.id;desenhar()});svg.appendChild(l)});
 const p=document.getElementById("plan");p.innerHTML="";p.appendChild(svg);
}
function elevacao(){
 const L=D.fam[fam].linhas.find(l=>l.id===sel),box=document.getElementById("elev");
 if(!L){box.innerHTML="";return}
 const n=L.fiadas.length,H=20,NS="http://www.w3.org/2000/svg";
 let xmin=0,xmax=L.comprimento_cm;L.fiadas.forEach(f=>f.forEach(p=>{xmin=Math.min(xmin,p[0]);xmax=Math.max(xmax,p[0]+p[1])}));
 const esc=Math.max(0.6,Math.min(2.2,((box.clientWidth||600)-24)/(xmax-xmin)));
 const W=(xmax-xmin)*esc+20,Ht=n*H*esc+20,svg=document.createElementNS(NS,"svg");svg.setAttribute("viewBox",`0 0 ${W} ${Ht}`);svg.setAttribute("width",Math.max(W,300));
 L.fiadas.forEach((f,k)=>{const yy=Ht-10-(k+1)*H*esc;f.forEach(([u,w,t])=>{const r=document.createElementNS(NS,"rect");
  r.setAttribute("x",10+(u-xmin)*esc+0.5);r.setAttribute("y",yy+0.5);r.setAttribute("width",Math.max(w*esc-1,0.5));r.setAttribute("height",H*esc-1);
  if(t==="vao"){r.setAttribute("fill","none");r.setAttribute("stroke","var(--dim)");r.setAttribute("stroke-dasharray","3 2")}else{r.setAttribute("fill",COR[t]||"var(--bloco)");r.setAttribute("stroke","rgba(0,0,0,.25)")}
  const tt=document.createElementNS(NS,"title");tt.textContent=`${t} · ${w.toFixed(0)} cm`;r.appendChild(tt);svg.appendChild(r)})});
 box.innerHTML="";box.appendChild(svg);
 document.getElementById("et").textContent=`Elevação · ${L.id} (${L.tipo})`;
 document.getElementById("ei").textContent=`${(L.comprimento_cm/100).toFixed(2).replace(".",",")} m pelo eixo · ${n} fiadas · pontas ${L.ponta_a} / ${L.ponta_b} · ${L.cortes} corte(s) nesta família`;
}
function resumo(){
 document.getElementById("rt").textContent=`Comparação no ${D.titulo} (pavimentos-tipo são iguais)`;
 let g="",h="";D.resumo["29"].forEach((r,i)=>{const s=D.resumo["39"][i];if(r[0]!==g){g=r[0];h+=`<tr class="g"><td colspan="3">${g}</td></tr>`}
  h+=`<tr><td>${r[1]}</td><td class="n">${f0(r[2])}</td><td class="n">${f0(s[2])}</td></tr>`});document.getElementById("rb").innerHTML=h;
}
function desenhar(){document.querySelectorAll("#seg button").forEach(b=>b.setAttribute("aria-pressed",b.dataset.f===fam));planta();elevacao()}
document.querySelectorAll("#seg button").forEach(b=>b.onclick=()=>{fam=b.dataset.f;desenhar()});
sel=(D.fam[fam].linhas.filter(l=>l.tipo==="estrutural").sort((a,b)=>b.comprimento_cm-a.comprimento_cm)[0]||{}).id;
resumo();desenhar();
</script></body></html>"""
