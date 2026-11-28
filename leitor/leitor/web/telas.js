// ---------- telas de dados (visão geral, quantitativos, orçamento, conferência, documentos, plantas, guia)
const brl0=v=>"R$ "+nf(v,0);
const pct=p=>p==null?"":`<div class="pct">${nf(p,1)}%<b><i style="width:${Math.min(100,p)}%"></i></b></div>`;
// linhas que abrem e fecham (g > c > cc)
function nivel(tr){return tr.classList.contains("g")||tr.classList.contains("tot")?0:tr.classList.contains("c")?1:2}
function alternar(tr){const lv=nivel(tr),abre=!tr.classList.contains("open");tr.classList.toggle("open",abre);
 let n=tr.nextElementSibling,paiAberto=false;
 while(n){const l=nivel(n);if(l<=lv)break;
  if(!abre)n.style.display="none";
  else if(l===lv+1){n.style.display="";paiAberto=n.classList.contains("open")}
  else n.style.display=paiAberto?"":"none";
  n=n.nextElementSibling}}
// visão geral
(function(){
 el("gSub").textContent=APP.escopo;
 let h=`<div class="kpis">`+APP.kpis.map(([l,v,s])=>`<div class="kpi"><div class="l">${esc(l)}</div><div class="v">${esc(v)}</div><div class="s">${esc(s)}</div></div>`).join("")+`</div>`;
 h+=`<h2>Disciplinas</h2><table class="t"><thead><tr><th>Disciplina</th><th class="hide-sm">Projeto lido</th><th class="r">Orçamento</th><th>Conferência</th></tr></thead><tbody>`
  +APP.disc.map(d=>`<tr${d.na?' class="na"':""}><td><span class="dn"><span class="dot" style="background:${d.cor}${d.na?";opacity:.45":""}"></span>${esc(d.n)}</span></td><td class="hide-sm">${esc(d.lido)}</td>`
   +`<td class="r${d.orc==null?" diff":""}">${d.orc==null?"—":brl0(d.orc)}</td><td>${d.conf?`<span class="status${d.conf[0]<d.conf[1]?" w":""}"><i></i>${d.conf[0]===d.conf[1]?"ok":d.conf[0]+" de "+d.conf[1]}</span>`:'<span class="status n"><i></i>—</span>'}</td></tr>`).join("")+`</tbody></table>`;
 if(APP.pend.length)h+=`<h2>Pontos para os projetistas</h2><div class="list">`+APP.pend.map(p=>`<div class="it"><span class="status ${p.nivel}"><i></i></span><div><div>${esc(p.t)}</div><div class="d">${esc(p.d)}</div></div><span class="wh">${esc(p.onde)}</span></div>`).join("")+`</div>`;
 el("gBody").innerHTML=h})();
// quantitativos
el("tqb").innerHTML=APP.quant.map(([g,cor,linhas])=>`<tr class="g x open"><td colspan="5"><span class="gl"><span class="car">${CAR}</span><span class="dot" style="background:${cor}"></span>${esc(g)}</span></td></tr>`
 +linhas.map(([n,u,m,p,c])=>{const d=p==null?null:m-p,z=d!=null&&Math.abs(d)<0.5*Math.pow(10,-c);
  return `<tr class="c${p==null?" semp":""}"><td class="it">${esc(n)}</td><td class="un">${esc(u)}</td><td class="r mod" data-un="${esc(u)}">${nf(m,c)}</td><td class="r proj diff">${p==null?"—":nf(p,c)}</td>`
   +`<td class="r dif diff${z?" ok":""}">${d==null?"—":z?"0":(d>0?"+":"−")+nf(Math.abs(d),c)}</td></tr>`}).join("")).join("");
// orçamento
(function(){const O=APP.orc;if(!O){el("oBody").innerHTML='<div class="note">Orçamento não gerado nesta leitura.</div>';return}
 el("oSub").textContent=O.ref;
 const subs=O.etapas.flatMap(e=>e.subs||[]);
 let h=`<div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap"><div style="font-size:24px;font-weight:600" class="num">${brl(O.total)}</div><div class="diff">medido até agora · ${brl(O.porm2)}/m² construído</div></div>`;
 h+=`<div class="stack">`+subs.map(s=>`<i style="width:${(100*s.total/O.total).toFixed(2)}%;background:${s.cor}" title="${esc(s.n)}"></i>`).join("")+`</div>`;
 const leg={};subs.forEach(s=>{leg[s.cor]=leg[s.cor]||s.leg});
 h+=`<div class="leg">`+Object.entries(leg).map(([c,t])=>`<span><i class="dot" style="background:${c}"></i>${esc(t)}</span>`).join("")+`</div>`;
 h+=`<h2>Por etapa</h2><table class="t" id="to"><thead><tr><th>Etapa</th><th class="r hide-sm">Qtd</th><th class="r hide-sm">Preço unit.</th><th class="r">Custo (R$)</th><th class="r hide-sm">%</th></tr></thead><tbody>`;
 O.etapas.forEach(e=>{
  if(!e.subs){h+=`<tr class="g na"><td><span class="gl"><span class="car" style="visibility:hidden">${CAR}</span><span class="mono">${e.cod}</span> ${esc(e.n)}</span></td><td class="hide-sm"></td><td class="hide-sm"></td><td class="r">${esc(e.st)}</td><td class="hide-sm"></td></tr>`;return}
  h+=`<tr class="g x open"><td><span class="gl"><span class="car">${CAR}</span><span class="mono">${e.cod}</span> ${esc(e.n)}</span></td><td class="hide-sm"></td><td class="hide-sm"></td><td class="r">${nf(e.total)}</td><td class="r hide-sm">${pct(100*e.total/O.total)}</td></tr>`;
  e.subs.forEach(s=>{h+=`<tr class="c x"><td><span class="gl"><span class="car">${CAR}</span><span class="mono">${s.cod}</span> ${esc(s.n)}</span></td><td class="hide-sm"></td><td class="hide-sm"></td><td class="r">${nf(s.total)}</td><td class="r hide-sm">${pct(100*s.total/O.total)}</td></tr>`;
   s.itens.forEach(([n,u,q,p,c,cod])=>{h+=`<tr class="cc" style="display:none"><td>${esc(n)}<span class="sub">${nf(q,q%1?2:0)} ${esc(u)} × ${brl(p)}${cod?" · SINAPI "+esc(cod):""}</span>${cod?`<span class="mono hide-sm" style="color:var(--faint);margin-left:6px">${esc(cod)}</span>`:""}</td>`
    +`<td class="r hide-sm">${nf(q,q%1?2:0)} ${esc(u)}</td><td class="r hide-sm">${nf(p)}</td><td class="r">${nf(c)}</td><td class="hide-sm"></td></tr>`})})});
 h+=`<tr class="tot"><td>Total medido</td><td class="hide-sm"></td><td class="hide-sm"></td><td class="r">${nf(O.total)}</td><td class="r hide-sm">100%</td></tr></tbody></table>`;
 h+=`<p class="note">${esc(O.nota)}</p>`;
 el("oBody").innerHTML=h})();
// conferência
(function(){const G={};APP.conf.forEach(c=>{(G[c[0]]=G[c[0]]||{disc:c[1],it:[]}).it.push(c)});
 let h=`<table class="t"><thead><tr><th>Grupo</th><th class="r">Verificações</th><th>Situação</th></tr></thead><tbody>`;
 Object.entries(G).forEach(([g,x])=>{const ok=x.it.filter(c=>c[4]).length,n=x.it.length;
  h+=`<tr class="g x"><td><span class="gl"><span class="car">${CAR}</span><span class="dot" style="background:${x.disc}"></span>${esc(g)}</span></td><td class="r">${n}</td><td><span class="status${ok<n?" w":""}"><i></i>${ok===n?"ok":(n-ok)+" para conferir"}</span></td></tr>`;
  x.it.forEach(c=>{h+=`<tr class="c" style="display:none"><td>${esc(c[2])}<span class="sub" style="display:block">${esc(c[3])}</span></td><td></td><td><span class="status${c[4]?"":" w"}"><i></i>${c[4]?"ok":"conferir"}</span></td></tr>`})});
 h+=`</tbody></table>`;
 const pend=APP.conf.filter(c=>!c[4]);
 if(pend.length)h+=`<h2>Para conferir</h2><div class="list">`+pend.map(c=>`<div class="it"><span class="status w"><i></i></span><div><div>${esc(c[2])}</div><div class="d">${esc(c[3])}</div></div><span class="wh">${esc(c[0])}</span></div>`).join("")+`</div>`;
 el("cBody").innerHTML=h})();
// documentos
el("dBody").innerHTML=`<table class="t"><thead><tr><th>Projeto</th><th>Pranchas</th><th>Situação</th></tr></thead><tbody>`
 +APP.docs.map(([n,p,arq,st,ok])=>`<tr${ok?"":' class="na"'}><td>${esc(n)}${arq?`<span class="sub" style="display:block">${esc(arq)}</span>`:""}</td><td>${esc(p||"—")}</td><td><span class="status${ok?"":" n"}"><i></i>${esc(st)}</span></td></tr>`).join("")+`</tbody></table>`
 +`<h2>Arquivos desta leitura</h2><div class="list">`+APP.arquivos.map(([n,href,d])=>`<div class="it"><span class="status n"><i></i></span><div><div><a class="lnk" href="${esc(href)}"${/\.(xlsx|json)$/.test(href)?" download":""}>${esc(n)}</a></div><div class="d">${esc(d)}</div></div><span class="wh mono">${esc(href)}</span></div>`).join("")+`</div>`;
// plantas (as páginas 2D da leitura, uma por aba)
el("pTabs").innerHTML=APP.plantas.map(([n,href])=>`<button role="tab" data-planta="${esc(href)}">${esc(n)}</button>`).join("");
function planta(href){if(!href)return;S.planta=href;$$("#pTabs button").forEach(b=>b.setAttribute("aria-selected",b.dataset.planta===href));
 const f=el("pFrame");if(f.getAttribute("src")!==href)f.setAttribute("src",href)}
// guia visual
(function(){const sw=(n,c,m)=>`<div class="sw"><b style="background:${c}"></b><div>${esc(n)}${m?`<span>${esc(m)}</span>`:""}<code>${c}</code></div></div>`;
 el("guBody").innerHTML=`<div class="gsec"><h3>Marca</h3><div class="logos"><div style="background:var(--brand);border-color:var(--brand)"><img src="__LOGO_B__" alt="AGEO"></div><div style="background:#fff"><img src="__LOGO_A__" alt="AGEO"></div></div></div>
 <div class="gsec"><h3>Como usar a cor</h3><ul class="regras">
  <li><b>Azul AGEO</b>: marca, navegação e ações (item ativo, botão principal, pavimento selecionado, links).</li>
  <li><b>Laranja AGEO</b>, pouco, como no logo: marcador do item ativo, pendências e o elemento selecionado no 3D.</li>
  <li><b>Disciplinas na cor do material que vai para a obra</b>: bloco de concreto, PVC marrom, PVC branco, tubo vermelho de incêndio, eletroduto amarelo.</li>
  <li>O resto é neutro: fundo claro, linhas finas no lugar de sombra, cantos de 4 px. Fonte IBM Plex Sans; números alinhados.</li></ul></div>
 <div class="gsec"><h3>Cores da marca</h3><div class="sws">${sw("Azul AGEO","#1C48A4","Shark Blue")+sw("Azul escuro","#163A85")+sw("Azul claro","#EDF1FA")+sw("Laranja AGEO","#EB6D4E","Lava Orange")+sw("Laranja texto","#C4502F")}</div></div>
 <div class="gsec"><h3>Disciplinas · cor do material</h3><div class="sws">${sw("Arquitetura","#4A4F54","grafite")+sw("Bloco estrutural","#8E8A83","bloco de concreto 14")+sw("Bloco de vedação","#D3CFC7","bloco de concreto 9")
  +sw("Concreto armado","#B4B0A9","lajes e pilares")+sw("Revestimento","#CDBFA8","argamassa")+sw("Água fria","#8A5636","PVC soldável marrom")+sw("Esgoto","#EEECE7","PVC esgoto branco")+sw("Incêndio","#B3261E","tubo vermelho")+sw("Elétrica","#E3B505","eletroduto amarelo")}</div></div>
 <div class="gsec"><h3>Neutros e situação</h3><div class="sws">${sw("Fundo","#FAFAF8")+sw("Superfície","#FFFFFF")+sw("Linha","#E4E2DD")+sw("Texto","#1D1C1A")+sw("Texto secundário","#67655F")+sw("Conferido","#3E7A55")+sw("Atenção","#EB6D4E")}</div></div>`})();
