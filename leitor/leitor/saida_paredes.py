"""Saídas do modelo de paredes: abas da planilha e página de revisão (paredes.html)."""
from __future__ import annotations

import base64
import html
import json

import pymupdf
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

TIPOS = ["estrutural", "vedação", "concreto", "muro", "a definir"]
PADRAO_ALT = {"porta": 2.10, "janela": 1.20, "varanda": 1.60}


def _vaos_m2(pw):
    return sum(v["largura_m"] * (v.get("altura_m") or PADRAO_ALT[v["tipo"]]) for v in pw["vaos"])


def abas(wb, dados, cabecalho):
    ws = wb.create_sheet("Paredes")
    cols = ["ID", "Pavimento", "Tipo (editável)", "Motivo da classificação", "Comprimento (m)", "Espessura (m)",
            "Pé-direito (m)", "Fiadas (20 cm)", "Área bruta (m²)", "Vãos (un)", "Vãos (m²)", "Área líquida (m²)",
            "Fachada", "Encontro início", "Encontro fim", "Lado A", "Lado B"]
    cabecalho(ws, cols, [12, 16, 15, 44, 13, 12, 12, 11, 13, 9, 10, 14, 9, 13, 13, 40, 40])
    amarelo = PatternFill("solid", fgColor="FFF8E1")
    for r, pw in enumerate(dados["paredes"], 2):
        vals = [pw["id"], pw["pavimento"], pw["tipo"], pw["motivo"], pw["comprimento_m"], pw["espessura_m"],
                f"=VLOOKUP(B{r},Premissas!$A:$B,2,FALSE)", f"=ROUND(G{r}/0.2,0)", f"=E{r}*G{r}",
                len(pw["vaos"]), round(_vaos_m2(pw), 3), f"=I{r}-K{r}", "sim" if pw["fachada"] else "não",
                pw["encontros"]["a"], pw["encontros"]["b"], ", ".join(pw["lado_a"]), ", ".join(pw["lado_b"])]
        for col, val in enumerate(vals, 1):
            c = ws.cell(row=r, column=col, value=val)
            if col in (5, 6, 7, 9, 11, 12):
                c.number_format = "0.00"
        ws.cell(row=r, column=3).fill = amarelo
    n = len(dados["paredes"]) + 1
    dv = DataValidation(type="list", formula1='"' + ",".join(TIPOS) + '"', allow_blank=False)
    ws.add_data_validation(dv)
    dv.add(f"C2:C{n}")
    ws.auto_filter.ref = f"A1:Q{n}"

    rs = wb.create_sheet("Resumo paredes")
    grupos = [("estrutural", "Estrutural"), ("vedação", "Vedação"), ("a definir", "A definir"), ("muro", "Muro"), ("concreto", "Concreto")]
    cab = ["Pavimento"]
    for _, t in grupos[:3]:
        cab += [f"{t}: comprimento (m)", f"{t}: área líquida (m²)"]
    cab += ["Muro: comprimento (m)", "Concreto: comprimento (m)", "Fachada: área bruta (m²)"]
    cabecalho(rs, cab, [18] + [15] * (len(cab) - 1))
    pavs = list(dict.fromkeys(pw["pavimento"] for pw in dados["paredes"]))
    for i, pv in enumerate(pavs, 2):
        rs.cell(row=i, column=1, value=pv)
        col = 2
        for chave, _ in grupos[:3]:
            rs.cell(row=i, column=col, value=f'=SUMIFS(Paredes!$E:$E,Paredes!$B:$B,$A{i},Paredes!$C:$C,"{chave}")').number_format = "#,##0.00"
            rs.cell(row=i, column=col + 1, value=f'=SUMIFS(Paredes!$L:$L,Paredes!$B:$B,$A{i},Paredes!$C:$C,"{chave}")').number_format = "#,##0.00"
            col += 2
        rs.cell(row=i, column=col, value=f'=SUMIFS(Paredes!$E:$E,Paredes!$B:$B,$A{i},Paredes!$C:$C,"muro")').number_format = "#,##0.00"
        rs.cell(row=i, column=col + 1, value=f'=SUMIFS(Paredes!$E:$E,Paredes!$B:$B,$A{i},Paredes!$C:$C,"concreto")').number_format = "#,##0.00"
        rs.cell(row=i, column=col + 2, value=f'=SUMIFS(Paredes!$I:$I,Paredes!$B:$B,$A{i},Paredes!$M:$M,"sim")').number_format = "#,##0.00"
    t = len(pavs) + 2
    rs.cell(row=t, column=1, value="Total").font = Font(bold=True)
    for col in range(2, len(cab) + 1):
        L = get_column_letter(col)
        c = rs.cell(row=t, column=col, value=f"=SUM({L}2:{L}{t - 1})")
        c.font = Font(bold=True)
        c.number_format = "#,##0.00"
    rs.cell(row=t + 2, column=1, value=(
        "Área líquida = comprimento pelo eixo × pé-direito − vãos. Comprimento pelo eixo conta os encontros "
        "(cantos e T) uma vez. Mude o Tipo na aba Paredes e este resumo recalcula.")).font = Font(italic=True)
    rs.cell(row=t + 3, column=1, value=(
        "Fachada: área bruta das paredes com um lado para o exterior (sem platibanda e sem a borda das lajes).")).font = Font(italic=True)


def pagina(dados, pdf, destino):
    doc = pymupdf.open(str(pdf))
    pd = dados["premissas"]["pe_direito_m"]
    vistas = []
    for v in dados["vistas"]:
        x0, y0, x1, y1 = v["caixa"]
        x0, y0, x1, y1 = x0 - 15, y0 - 15, x1 + 15, y1 + 15
        ddx, ddy = v.get("desloc") or (0, 0)          # andar repetido: dados no sistema da referência
        pix = doc[v["pagina"] - 1].get_pixmap(matrix=pymupdf.Matrix(1.4, 1.4), clip=pymupdf.Rect(x0 + ddx, y0 + ddy, x1 + ddx, y1 + ddy),
                                               colorspace=pymupdf.csGRAY)
        ps = []
        for pw in dados["paredes"]:
            if pw["vista"] != v["id"]:
                continue
            e = pw["eixo"]
            ps.append({"id": pw["id"], "tipo": pw["tipo"], "motivo": pw["motivo"], "c": pw["comprimento_m"],
                       "t": pw["espessura_m"], "e": e, "r": [round(e[0] - v["caixa"][0], 1), round(e[1] - v["caixa"][1], 1),
                                                           round(e[2] - v["caixa"][0], 1), round(e[3] - v["caixa"][1], 1)],
                       "enc": pw["encontros"], "la": pw["lado_a"], "lb": pw["lado_b"], "f": pw["fachada"],
                       "vaos": [[x["tipo"], x["inicio_m"], x["largura_m"], x.get("altura_m") or PADRAO_ALT[x["tipo"]], x.get("peitoril_m")]
                                for x in pw["vaos"]]})
        vistas.append({"id": v["id"], "titulo": v["titulo"], "caixa": [x0, y0, x1 - x0, y1 - y0], "m": v["m_por_pt"],
                       "pd": pd.get(v["titulo"], 2.6), "img": base64.b64encode(pix.tobytes("png")).decode(), "paredes": ps})
    txt = MODELO.replace("__DADOS__", json.dumps(vistas, ensure_ascii=False)).replace("__OBRA__", html.escape(dados["obra"]))
    destino.write_text(txt, encoding="utf-8")


MODELO = r"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Modelo de Paredes</title>
<style>
:root{--bg:#FAFAF7;--card:#fff;--elev:#F1EFE8;--bd:rgba(0,0,0,.1);--tx:#1A1A1A;--mut:#5F5E5A;--dim:#888780;--acc:#0F6E56}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#1A1A1A;--card:#242422;--elev:#2C2C2A;--bd:rgba(255,255,255,.12);--tx:#F5F5F2;--mut:#B4B2A9;--dim:#888780;--acc:#5DCAA5}}
:root[data-theme=dark]{--bg:#1A1A1A;--card:#242422;--elev:#2C2C2A;--bd:rgba(255,255,255,.12);--tx:#F5F5F2;--mut:#B4B2A9;--dim:#888780;--acc:#5DCAA5}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}
.wrap{max-width:1320px;margin:0 auto;padding:16px}h1{font-size:18px;margin:0 0 2px;font-weight:600}.sub{color:var(--mut);font-size:12px;margin-bottom:12px}
.tabs{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:10px}
.tab{border:1px solid var(--bd);background:var(--card);color:var(--tx);border-radius:8px;padding:6px 12px;font:inherit;font-size:13px;cursor:pointer}
.tab[aria-selected=true]{background:var(--acc);border-color:var(--acc);color:#fff}
.grid{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:12px;align-items:start}
.card{background:var(--card);border:1px solid var(--bd);border-radius:12px;overflow:hidden}
.plan{position:relative;background:#fff}.plan svg{display:block;width:100%;height:auto}
.plan line.w{cursor:pointer;stroke-linecap:butt}.plan line.w:hover{stroke-opacity:1!important;filter:drop-shadow(0 0 2px #000)}
.tip{position:absolute;pointer-events:none;background:#1A1A1A;color:#fff;font-size:12px;padding:6px 8px;border-radius:6px;display:none;max-width:320px;z-index:2}
.side{padding:12px}.side h2{font-size:13px;margin:0 0 8px;color:var(--mut);text-transform:uppercase;letter-spacing:.4px}
table{width:100%;border-collapse:collapse;font-size:12.5px;font-variant-numeric:tabular-nums}
th{text-align:left;color:var(--mut);font-weight:500;border-bottom:1px solid var(--bd);padding:5px 4px}td{border-bottom:1px solid var(--bd);padding:5px 4px}
td.n,th.n{text-align:right}i.sw{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-2px}
.btns{display:flex;gap:6px;flex-wrap:wrap;margin-top:12px}
button.b{border:1px solid var(--bd);background:var(--elev);color:var(--tx);border-radius:8px;padding:6px 10px;font:inherit;font-size:12.5px;cursor:pointer}
button.b.pri{background:var(--acc);color:#fff;border-color:var(--acc)}
.note{font-size:11.5px;color:var(--mut);margin-top:10px;line-height:1.45}
label.chk{font-size:12.5px;display:flex;gap:6px;align-items:center;margin-top:10px}
@media (max-width:900px){.grid{grid-template-columns:1fr}}
</style></head><body><div class="wrap">
<h1>Modelo de paredes · __OBRA__</h1>
<div class="sub">Cada traço é uma parede (eixo e espessura reais). Clique numa parede para trocar o tipo; passe o mouse para ver comprimento, encontros, vãos e o que há de cada lado.</div>
<div class="tabs" id="tabs"></div>
<div class="grid">
<div class="card"><div class="plan" id="plan"><div class="tip" id="tip"></div></div></div>
<div class="card side"><h2 id="vt"></h2>
<table><thead><tr><th>Tipo</th><th class="n">Paredes</th><th class="n">Compr. (m)</th><th class="n">Área líq. (m²)</th></tr></thead><tbody id="tb"></tbody></table>
<h2 style="margin-top:16px">Prédio inteiro</h2>
<table><thead><tr><th>Tipo</th><th class="n">Compr. (m)</th><th class="n">Área líq. (m²)</th></tr></thead><tbody id="tt"></tbody></table>
<label class="chk"><input type="checkbox" id="rep" checked> Aplicar a mudança nos pavimentos iguais</label>
<div class="btns"><button class="b pri" id="baixar">Baixar ajustes</button><button class="b" id="desfazer">Desfazer ajustes</button></div>
<div class="note" id="nota"></div>
<div class="note">Área líquida = comprimento pelo eixo × pé-direito − vãos (portas e janelas). Paredes com traço tracejado branco foram ajustadas por você. Para levar os ajustes para a planilha, baixe o arquivo e me envie (ou salve como <b>ajustes_paredes.json</b> na pasta da obra).</div>
</div></div></div>
<script>
const V=__DADOS__;
const TIPOS=["estrutural","vedação","a definir","concreto","muro"];
const COR={"estrutural":"#C0392B","vedação":"#2471A3","a definir":"#E8A317","concreto":"#6B6B6B","muro":"#9A6B2F"};
let AJ={};try{AJ=JSON.parse(localStorage.getItem("ajustes_paredes")||"{}")}catch(e){}
const salvar=()=>{try{localStorage.setItem("ajustes_paredes",JSON.stringify(AJ))}catch(e){}};
const tipo=p=>AJ[p.id]||p.tipo;
const f2=n=>n.toLocaleString("pt-BR",{minimumFractionDigits:2,maximumFractionDigits:2});
const liq=(p,pd)=>p.c*pd-p.vaos.reduce((s,v)=>s+v[2]*v[3],0);
const tabs=document.getElementById("tabs"),plan=document.getElementById("plan"),tip=document.getElementById("tip");let atual=0;
function totais(){
 const t={};V.forEach(v=>v.paredes.forEach(p=>{const k=tipo(p);t[k]=t[k]||[0,0];t[k][0]+=p.c;t[k][1]+=liq(p,v.pd)}));
 document.getElementById("tt").innerHTML=TIPOS.filter(k=>t[k]).map(k=>`<tr><td><i class="sw" style="background:${COR[k]}"></i>${k}</td><td class="n">${f2(t[k][0])}</td><td class="n">${f2(t[k][1])}</td></tr>`).join("");
 const n=Object.keys(AJ).length;document.getElementById("nota").textContent=n?`${n} parede(s) ajustada(s).`:"Nenhum ajuste ainda: classificação automática.";
}
function mostrar(i){
 atual=i;[...tabs.children].forEach((b,k)=>b.setAttribute("aria-selected",k===i));
 const v=V[i],[x,y,w,h]=v.caixa,NS="http://www.w3.org/2000/svg";
 plan.querySelectorAll("svg").forEach(s=>s.remove());
 const svg=document.createElementNS(NS,"svg");svg.setAttribute("viewBox",`${x} ${y} ${w} ${h}`);
 const im=document.createElementNS(NS,"image");im.setAttribute("href","data:image/png;base64,"+v.img);
 im.setAttribute("x",x);im.setAttribute("y",y);im.setAttribute("width",w);im.setAttribute("height",h);im.setAttribute("opacity",".45");svg.appendChild(im);
 v.paredes.forEach(p=>{
  const [a,b,c,d]=p.e,L=document.createElementNS(NS,"line");
  L.setAttribute("x1",a);L.setAttribute("y1",b);L.setAttribute("x2",c);L.setAttribute("y2",d);
  L.setAttribute("stroke",COR[tipo(p)]);L.setAttribute("stroke-width",Math.max(p.t/v.m,2));L.setAttribute("stroke-opacity",".85");L.setAttribute("class","w");
  L.addEventListener("mousemove",e=>{const r=plan.getBoundingClientRect();tip.style.display="block";
   tip.innerHTML=`<b>${p.id}</b> · ${tipo(p)}<br>${f2(p.c)} m × ${f2(p.t)} m · fiadas ${Math.round(v.pd/0.2)}<br>encontros: ${p.enc.a} / ${p.enc.b}<br>lado A: ${p.la.join(", ")}<br>lado B: ${p.lb.join(", ")}`
    +(p.vaos.length?`<br>vãos: ${p.vaos.map(q=>`${q[0]} ${f2(q[2])}×${f2(q[3])}`).join("; ")}`:"")+`<br><span style="opacity:.7">${AJ[p.id]?"ajuste manual":p.motivo}</span>`;
   tip.style.left=Math.min(e.clientX-r.left+12,r.width-330)+"px";tip.style.top=(e.clientY-r.top+12)+"px"});
  L.addEventListener("mouseleave",()=>tip.style.display="none");
  L.addEventListener("click",()=>trocar(v,p));svg.appendChild(L);
  // vãos sobre a parede
  const ux=(c-a)/(p.c/v.m||1),uy=(d-b)/(p.c/v.m||1);
  p.vaos.forEach(q=>{const s0=q[1]/v.m,s1=(q[1]+q[2])/v.m,G=document.createElementNS(NS,"line");
   G.setAttribute("x1",a+ux*s0);G.setAttribute("y1",b+uy*s0);G.setAttribute("x2",a+ux*s1);G.setAttribute("y2",b+uy*s1);
   G.setAttribute("stroke","#fff");G.setAttribute("stroke-width",Math.max(p.t/v.m*0.55,1.2));G.setAttribute("stroke-opacity",q[0]==="porta"?".95":".6");G.setAttribute("pointer-events","none");svg.appendChild(G)});
  if(AJ[p.id]){const D=document.createElementNS(NS,"line");D.setAttribute("x1",a);D.setAttribute("y1",b);D.setAttribute("x2",c);D.setAttribute("y2",d);
   D.setAttribute("stroke","#fff");D.setAttribute("stroke-width",1.2);D.setAttribute("stroke-dasharray","4 3");D.setAttribute("pointer-events","none");svg.appendChild(D)}
 });
 plan.appendChild(svg);
 const t={};v.paredes.forEach(p=>{const k=tipo(p);t[k]=t[k]||[0,0,0];t[k][0]++;t[k][1]+=p.c;t[k][2]+=liq(p,v.pd)});
 document.getElementById("vt").textContent=`${v.titulo} · pé-direito ${f2(v.pd)} m`;
 document.getElementById("tb").innerHTML=TIPOS.filter(k=>t[k]).map(k=>`<tr><td><i class="sw" style="background:${COR[k]}"></i>${k}</td><td class="n">${t[k][0]}</td><td class="n">${f2(t[k][1])}</td><td class="n">${f2(t[k][2])}</td></tr>`).join("");
 totais();
}
function trocar(v,p){
 const novo=TIPOS[(TIPOS.indexOf(tipo(p))+1)%TIPOS.length];
 const alvo=[p];
 if(document.getElementById("rep").checked)V.forEach(o=>{if(o===v)return;o.paredes.forEach(q=>{if(q.r.every((z,k)=>Math.abs(z-p.r[k])<2.5))alvo.push(q)})});
 alvo.forEach(q=>{if(novo===q.tipo)delete AJ[q.id];else AJ[q.id]=novo});salvar();mostrar(atual);
}
document.getElementById("baixar").onclick=()=>{const b=new Blob([JSON.stringify(AJ,null,1)],{type:"application/json"}),a=document.createElement("a");
 a.href=URL.createObjectURL(b);a.download="ajustes_paredes.json";a.click()};
document.getElementById("desfazer").onclick=()=>{if(confirm("Desfazer todos os ajustes?")){AJ={};salvar();mostrar(atual)}};
V.forEach((v,i)=>{const b=document.createElement("button");b.className="tab";b.textContent=v.titulo;b.onclick=()=>mostrar(i);tabs.appendChild(b)});
mostrar(V.findIndex(v=>/1º/.test(v.titulo))>=0?V.findIndex(v=>/1º/.test(v.titulo)):0);
</script></body></html>"""
