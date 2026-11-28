// ---------- 3D: resumo, legenda, seleção (ficha do elemento) e toque
function resumoCusto(){
 const O=D.orc,ref=`SINAPI ${esc(O.mes)} ${esc(O.uf)}, ${O.deson?"com":"sem"} desoneração`;
 const lin=(k,v,b)=>`<tr><td class="k">${esc(k)}</td><td>${v}${b!=null?`<div class="bar" style="width:${Math.max(2,b*100).toFixed(1)}%"></div>`:""}</td></tr>`;
 if(S.andar>=0){const A=D.andares[S.andar],g={};
  [...A.paredes,...A.ambientes].forEach(x=>(x.cx||[]).forEach(([il,v])=>{const k=O.linhas[il][0];g[k]=(g[k]||0)+v}));
  const ar=O.areas[A.nome],gs=Object.entries(g).sort((a,b)=>b[1]-a[1]),mx=gs.length?gs[0][1]:1;
  return `<h3>${esc(nomeAndar(S.andar))} · custo da alvenaria e revestimentos</h3><div class="big">${brl(A.custo)}</div><div class="mut">${ar?brl(A.custo/ar)+"/m² de área construída · ":""}${(100*A.custo/O.total).toLocaleString("pt-BR",{maximumFractionDigits:1})}% da obra</div><table>`
   +gs.map(([k,v])=>lin(k,brl(v),v/mx)).join("")+"</table>"}
 const soma=D.andares.reduce((s,A)=>s+A.custo,0),mx=Math.max(...D.andares.map(A=>A.custo));
 let h=`<h3>Prédio · alvenaria e revestimentos</h3><div class="big">${brl(O.total)}</div><div class="mut">${ref} · ${brl(O.total/O.area)}/m² (${nf(O.area,0)} m² acima do subsolo)</div>`;
 h+=`<table>`+O.grupos.map(([k,v])=>lin(k,brl(v))).join("")+`</table><h3 style="margin-top:14px">Por andar</h3><table>`
  +D.andares.filter(A=>A.custo>0).map(A=>lin(nomeAndar(D.andares.indexOf(A)),brl(A.custo),A.custo/mx)).join("")+"</table>";
 h+=`<div class="mut" style="margin-top:8px">Soma dos elementos do 3D: ${brl(soma)} ${Math.abs(soma-O.total)<1?"= total do orçamento":"(difere do orçamento)"}</div>`;
 return h}
function resumoHid(){
 const H=D.hid,tot={};const ok=t=>S.andar<0||t[2]===D.andares[S.andar].nome;
 H.trechos.forEach(t=>{if(t[8]==="es"||t[1]==="ligação"||!ok(t))return;tot[t[3]]=(tot[t[3]]||0)+t[4]});
 H.curtos.forEach(t=>{if(S.andar>=0&&t[1]!==D.andares[S.andar].nome)return;tot[t[2]]=(tot[t[2]]||0)+t[3]});
 let sp=0;(H.sempos||[]).forEach(t=>{if(S.andar>=0&&t[1]!==D.andares[S.andar].nome)return;tot[t[2]]=(tot[t[2]]||0)+t[3];sp+=t[3]});
 const dns=Object.keys(tot).map(Number).sort((a,b)=>a-b),soma=dns.reduce((s,k)=>s+tot[k],0);
 let h="";
 if(dns.length){h+=`<h3>Água fria · ${S.andar<0?"prédio":esc(nomeAndar(S.andar))}</h3><div class="big">${nf(soma)} m de tubo</div><div class="mut">Cada tubo uma vez.${sp>0?` ${nf(sp)} m de verticais do barrilete e do térreo entram só no quantitativo (sem posição no 3D).`:""}</div><table>`
  +dns.map(k=>`<tr><td class="k"><span class="dn"><i class="dot" style="background:${hx(COR_DN[k]||0x8A5636)}"></i>DN${k}</span></td><td>${nf(tot[k])} m${S.andar<0&&H.tab[k]!=null?` <span class="mut">· projetista ${nf(H.tab[k])} m</span>`:""}</td></tr>`).join("")+"</table>";
  if(S.andar<0&&H.orc)h+=`<h3 style="margin-top:14px">Custo da água fria (SINAPI ${esc(H.orc.mes)})</h3><div class="big">${brl(H.orc.total)}</div><table>`+Object.entries(H.orc.grupos).map(([g,v])=>`<tr><td class="k">${esc(g)}</td><td>${brl(v)}</td></tr>`).join("")+"</table>"}
 if(H.es){const E=H.es,dE=Object.keys(E.tot).sort((a,b)=>a-b),sE=dE.reduce((s,k)=>s+E.tot[k],0);
  h+=`<h3 style="margin-top:14px">Esgoto · prédio</h3><div class="big">${nf(sE)} m de tubo</div><div class="mut">Quantitativo pelos isométricos. No 3D, ramais pela planta de cada andar; tubos de queda e ventilações pelos balões.</div><table>`
   +dE.map(k=>`<tr><td class="k"><span class="dn"><i class="dot" style="background:${hx(COR_ES[k]||0xE4E1DA)}"></i>DN${k}</span></td><td>${nf(E.tot[k])} m${E.tab[k]!=null?` <span class="mut">· projetista ${nf(E.tab[k])} m</span>`:""}</td></tr>`).join("")+"</table>";
  if(E.orc)h+=`<div class="mut" style="margin-top:6px">Custo (SINAPI ${esc(E.orc.mes)}): <b>${brl(E.orc.total)}</b></div>`}
 return h}
function resumo(){
 let h;
 if(S.modo==="custo"&&D.orc)h=resumoCusto();
 else if(S.modo==="inst"&&D.hid)h=resumoHid();
 else if(S.andar>=0){const A=D.andares[S.andar];h=`<h3>Resumo do pavimento</h3><div class="big">${esc(nomeAndar(S.andar))}</div><div class="mut">pé-direito ${nf(A.pd)} m · nível ${nf(A.z)} m</div><table>`+A.resumo.map(([k,v])=>`<tr><td class="k">${esc(k)}</td><td>${esc(v)}</td></tr>`).join("")+"</table>"}
 else h=`<h3>Prédio · principais insumos</h3><div class="big">${esc(APP.obra)}</div><div class="mut">Toque num pavimento, numa parede, num ambiente ou num tubo para ver os dados.</div><table>`+D.resumoObra.map(([k,v])=>`<tr><td class="k">${esc(k)}</td><td>${esc(v)}</td></tr>`).join("")+"</table>";
 el("resumo").innerHTML=h}
function legenda(){
 const it=(c,t)=>`<div class="lgi"><i class="dot" style="background:${typeof c==="number"?hx(c):c}"></i>${esc(t)}</div>`;let h;
 if(S.modo==="custo"){const [a,b]=ESCALA,u=S.metrica==="m2"?"/m²":"";
  h=`<div class="lgt">Custo da alvenaria e revestimentos</div><select class="lg-met" aria-label="Métrica do mapa">${[["parede","por parede"],["m2","por m² de parede"],["andar","por andar"]].map(([v,t])=>`<option value="${v}"${S.metrica===v?" selected":""}>${t}</option>`).join("")}</select>
   <div class="grad"></div><div class="esc"><span>${brl(a)}${u}</span><span>${brl(b)}${u}</span></div>${it("rgb("+SEMCUSTO.map(x=>Math.round(x*255)).join(",")+")","sem custo (concreto, muros, subsolo)")}`}
 else if(S.modo==="inst"){h=`<div class="lgt">Instalações</div>`+(temAF?it(COR_DN[25],"Água fria · PVC soldável marrom")+it(COR_CON,"Conexão (joelho, tê)")+it(0xC9A227,"Ponto de consumo (bucha de latão)")+it(COR_REG,"Registro"):"")
   +(temES?it(COR_ES[100],"Esgoto · PVC branco")+it(0xF2F0EB,"Caixa sifonada e ralo"):"")+it(0xBDBAB4,"Paredes e lajes (contexto)")
   +`<div class="lgn">Espessura do tubo proporcional ao diâmetro, engrossada para aparecer.</div>`}
 else if(S.modo==="ambientes")h=`<div class="lgt">Uso dos ambientes</div>`+Object.entries(COR_AMB).map(([k,c])=>it(c,NOME_AMB[k])).join("");
 else if(S.modo==="paginacao")h=`<div class="lgt">Blocos (família 39)</div>`+NOME_PECA.map(([t,c])=>it(c,t)).join("")
   +`<label class="lgi"><input type="checkbox" class="lg-cintas"${S.filt.cintas?" checked":""}> Destacar cintas, vergas e contravergas</label><label class="lgi"><input type="checkbox" class="lg-graute"${S.filt.graute?" checked":""}> Pontos de graute</label>`;
 else h=`<div class="lgt">Material</div>`+it(COR_PAREDE["estrutural"],"Bloco de concreto estrutural (14)")+it(COR_PAREDE["vedação"],"Bloco de concreto de vedação (9)")+it(COR_PAREDE["a definir"],"Parede a definir")
   +it(COR_PAREDE["concreto"],"Concreto armado")+it(0xA9784A,"Porta (madeira)")+it(0x9CC8E8,"Janela (alumínio e vidro)")+it(SEL,"Selecionado");
 el("legend").innerHTML=h;el("legendM").innerHTML=h}
function peek(){const p=el("peek"),i=el("info");
 if(S.sel){const bigs=i.querySelectorAll(".big");el("pkA").textContent=bigs[0]?.textContent||"";el("pkB").textContent=i.querySelector("h3")?.textContent||"";
  const v=bigs[1]?.textContent||"";el("pkV").textContent=v.startsWith("R$")?v:"";p.classList.add("sel")}
 else{const r=el("resumo");el("pkA").textContent=r.querySelector(".big")?.textContent||"Resumo";el("pkB").textContent=r.querySelector("h3")?.textContent||"";el("pkV").textContent="";p.classList.remove("sel")}}
// seleção
function limparSel(){
 if(!S.sel)return;const s=S.sel;
 if(s.tipo==="par"){const u=s.obj.userData,[ini,n]=u.faixas[s.ip],c=s.obj.geometry.attributes.color,col=corDe(u,s.ip);for(let k=ini;k<ini+n;k++)c.setXYZ(k,...col);c.needsUpdate=true}
 if(s.tipo==="esc"){s.mat.color.setHex(s.mat.userData.base)}
 if(s.tipo==="hidsel"){s.hl.parent&&s.hl.parent.remove(s.hl);s.hl.material.dispose()}
 if(s.tipo==="lin"){s.F.pecas.forEach(me=>{const u=me.userData,col=new THREE.Color();for(let i=0;i<u.linha.length;i++)if(u.linha[i]===s.il){col.setRGB(u.base[i*3],u.base[i*3+1],u.base[i*3+2]);me.setColorAt(i,col)}me.instanceColor.needsUpdate=true})}
 S.sel=null;
}
function limpar(){limparSel();el("info").hidden=true;el("resumo").hidden=false}
function blocoCusto(x,area,unid,A){
 if(!D.orc||!x.c)return "";const O=D.orc;
 const it=(x.cx||[]).slice(0,10).map(([il,v])=>{const L=O.linhas[il];return `<tr><td class="k">${esc(L[1])}<div class="mut" style="font-size:11px">${esc(L[0])}</div></td><td>${brl(v)}</td></tr>`}).join("");
 return `<h3 style="margin-top:14px">Custo (alvenaria e revestimentos)</h3><div class="big">${brl(x.c)}</div><div class="mut">${area>0?brl(x.c/area)+"/"+esc(unid)+" · ":""}${A.custo?(100*x.c/A.custo).toLocaleString("pt-BR",{maximumFractionDigits:1})+"% do andar":""}</div>
  <table>${it}</table>${(x.cx||[]).length>10?`<div class="mut">+ ${x.cx.length-10} itens menores</div>`:""}`}
function elevacao(L){
 const n=L.f.length,H=20;let x0=0,x1=L.comp;L.f.forEach(f=>f.forEach(([u,w])=>{x0=Math.min(x0,u);x1=Math.max(x1,u+w)}));
 const esc_=Math.max(0.35,Math.min(1.4,280/(x1-x0))),W=(x1-x0)*esc_+4,Ht=n*H*esc_+4;
 const cor={0:"#D9D6CC",1:"#B4AE9E",2:"#8E7CC3",3:"#E08A1E",4:"#F2B24C",5:"#262626",6:"#8F8A80"},corV={0:"#B9CFE4",1:"#8EAFCF",3:"#E08A1E",4:"#F2B24C",5:"#262626",6:"#8F8A80"};
 let r="";L.f.forEach((f,k)=>{const y=Ht-2-(k+1)*H*esc_;f.forEach(([u,w,c])=>{const x=2+(u-x0)*esc_;
  r+=c===8?`<rect x="${x+0.3}" y="${y+0.3}" width="${Math.max(w*esc_-0.6,0.3)}" height="${H*esc_-0.6}" fill="#E4E1D8"><title>parede que cruza</title></rect>`
   :c===9?`<rect x="${x}" y="${y}" width="${w*esc_}" height="${H*esc_}" fill="none" stroke="#999" stroke-dasharray="2 2"/>`
   :`<rect x="${x+0.3}" y="${y+0.3}" width="${Math.max(w*esc_-0.6,0.3)}" height="${H*esc_-0.6}" fill="${(L.tipo==="vedação"?corV:cor)[c]||"#ccc"}"/>`})});
 return `<svg width="${W}" height="${Ht}" viewBox="0 0 ${W} ${Ht}" style="display:block;max-width:100%;height:auto;background:#fff;border:1px solid var(--line);border-radius:4px">${r}</svg>`}
function selecionar(hit){
 limparSel();
 const o=hit.object,u=o.userData;let h="";
 if(u.tipo==="par"){const ip=u.tri[hit.faceIndex];const p=u.A.paredes[ip];const [ini,n]=u.faixas[ip],c=o.geometry.attributes.color;
  for(let k=ini;k<ini+n;k++)c.setXYZ(k,...SELRGB);c.needsUpdate=true;S.sel={tipo:"par",obj:o,ip};
  const vs=p.vaos.map(v=>`${v[0]} ${nf(v[2])} × ${nf(v[4]-v[3])}`+(v[0]!=="porta"?` (peitoril ${nf(v[3])})`:"")).join("; ")||"—";
  const mat={"estrutural":"bloco de concreto 14","vedação":"bloco de concreto 9"}[p.tipo];
  h=`<h3>Parede · ${esc(nomeAndar(D.andares.indexOf(u.A)))}</h3><div class="big">${esc(p.id)} · ${esc(p.tipo)}</div><div class="mut">${mat?esc(mat)+" · ":""}${esc(p.motivo)}</div><table>
  <tr><td class="k">Comprimento (eixo)</td><td>${nf(p.comp)} m</td></tr><tr><td class="k">Espessura</td><td>${nf(p.t*100,0)} cm</td></tr>
  <tr><td class="k">Altura</td><td>${nf(p.h||u.A.pd)} m · ${Math.round((p.h||u.A.pd)/0.2)} fiadas</td></tr>
  <tr><td class="k">Fachada</td><td>${p.fachada?"sim":"não (interna)"}</td></tr><tr><td class="k">Encontros</td><td>${esc(p.enc.join(" · "))}</td></tr>
  <tr><td class="k">Lado A</td><td>${esc(p.la.join(", "))}</td></tr><tr><td class="k">Lado B</td><td>${esc(p.lb.join(", "))}</td></tr>
  <tr><td class="k">Vãos</td><td>${esc(vs)}</td></tr></table>`+blocoCusto(p,p.comp*(p.h||u.A.pd),"m² de parede",u.A);
 }else if(u.tipo==="pec"){const il=u.linha[hit.instanceId],F=andares.find(x=>x.A===u.A),L=u.A.pag.linhas[il],y=new THREE.Color(SEL);
  F.pecas.forEach(me=>{const v=me.userData;for(let i=0;i<v.linha.length;i++)if(v.linha[i]===il)me.setColorAt(i,y);me.instanceColor.needsUpdate=true});
  S.sel={tipo:"lin",F,il,obj:o};
  const nomes=[["14×19×39","inteiro 14×19×39"],["14×19×19","meio 14×19×19"],["14×19×34","amarração L 14×19×34"],["14×19×54","amarração T 14×19×54"],
   ["canaleta J 14×19×39","canaleta J"],["meia canaleta J 14×19×19","meia canaleta J"],["canaleta U 14×19×39","canaleta U"],["meia canaleta U 14×19×19","meia canaleta U"],
   ["9×19×39","inteiro 9×19×39"],["9×19×19","meio 9×19×19"],["canaleta U 9×19×39","canaleta U 9"],["meia canaleta U 9×19×19","meia canaleta U 9"],
   ["cortes (peças)","cortes/compensadores"],["cinta de respaldo (m)","cinta de respaldo (m)"],["vergas (m)","vergas (m)"],["contravergas (m)","contravergas (m)"]];
  h=`<h3>Paginação · ${esc(nomeAndar(D.andares.indexOf(u.A)))}</h3><div class="big">${esc(L.id)} · ${esc(L.tipo)}</div>
  <div class="mut">${nf(L.comp/100)} m pelo eixo · ${L.f.length} fiadas · pontas ${esc(L.pontas.join(" / "))}${L.nseg>1?` · ${L.nseg} trechos colineares`:""}${L.fachada?" · fachada":""}</div>
  <table>${nomes.filter(([k])=>L.cont[k]).map(([k,t])=>`<tr><td class="k">${esc(t)}</td><td>${nf(L.cont[k],k.includes("(m)")?2:0)}</td></tr>`).join("")}</table><div style="margin-top:10px;overflow-x:auto">${elevacao(L)}</div>`;
 }else if(u.tipo==="esc"){const E=u.E;u.mat.color.setHex(SEL);S.sel={tipo:"esc",obj:o,mat:u.mat};
  const bl=(2*E.h+E.piso)*100,pt=E.patamares.map(([k])=>`${k}º espelho (+${nf(k*E.h)} m)`).join(", ")||"—",an=E.anot||{};
  h=`<h3>Escada · ${esc(nomeAndar(D.andares.indexOf(u.A)))}</h3><div class="big">${esc(E.ambiente)}</div><div class="mut">sobe para ${esc(E.destino||"—")} · ${E.lances} lances</div><table>
  <tr><td class="k">Desnível (cortes)</td><td>${nf(E.dz)} m</td></tr><tr><td class="k">Espelhos</td><td>${E.N} × ${nf(E.h*100,1)} cm</td></tr>
  <tr><td class="k">Piso (pisada)</td><td>${nf(E.piso*100,0)} cm</td></tr><tr><td class="k">Largura do lance</td><td>${nf(E.largura)} m</td></tr>
  <tr><td class="k">Patamar</td><td>${esc(pt)}</td></tr><tr><td class="k">Blondel (2e + p)</td><td>${nf(bl,1)} cm</td></tr>
  ${an.espelho_m?`<tr><td class="k">Anotado na planta</td><td>e = ${nf(an.espelho_m*100,0)} cm${an.piso_m?` · p = ${nf(an.piso_m*100,0)} cm`:""}${an.largura_m?` · L = ${nf(an.largura_m)} m`:""}</td></tr>`:""}</table>
  <div class="mut" style="margin-top:6px">Espelho calculado pelo desnível dos cortes ÷ nº de espelhos.${an.espelho_m&&Math.abs(an.espelho_m*E.N-E.dz)>0.03?` A planta anota ${nf(an.espelho_m*100,0)} cm (${E.N} × ${nf(an.espelho_m*100,0)} = ${nf(an.espelho_m*E.N)} m), diferente do corte: conferir com o arquiteto.`:""}${bl<63||bl>64?" NBR 9077 pede 63 a 64 cm na fórmula de Blondel e espelho de 16 a 18 cm: conferir.":""}</div>`;
 }else if(u.tipo==="hid"||u.tipo==="con"){const M=new THREE.Matrix4();o.getMatrixAt(hit.instanceId,M);
  const hl=new THREE.Mesh(o.geometry,new THREE.MeshBasicMaterial({color:SEL,depthTest:false,transparent:true,opacity:0.9}));
  const p=new THREE.Vector3(),q=new THREE.Quaternion(),e=new THREE.Vector3();M.decompose(p,q,e);
  if(u.tipo==="hid")e.set(e.x*1.7,e.y,e.z*1.7);else e.multiplyScalar(1.5);hl.position.copy(p);hl.quaternion.copy(q);hl.scale.copy(e);hl.renderOrder=20;
  o.parent.add(hl);S.sel={tipo:"hidsel",obj:o,hl};
  if(u.tipo==="hid"&&D.hid.trechos[u.ids[hit.instanceId]][1]==="ligação"){const [id,col,pav,dn,L,orig]=D.hid.trechos[u.ids[hit.instanceId]];
   h=`<h3>${u.sys?"Esgoto":"Água fria"} · ${esc(pav)}</h3><div class="big">Ligação do 3D · DN${dn}</div><div class="mut">${nf(L)} m · ${esc(orig)}</div>`}
  else if(u.tipo==="hid"&&u.sys){const [id,col,pav,dn,L,orig,eixo,como]=D.hid.trechos[u.ids[hit.instanceId]];
   h=`<h3>Esgoto · ${esc(pav==="prédio"?"prédio":pav)}</h3><div class="big">${col==="ramal"?"Ramal":col==="coletor"?"Coletor":esc(col)} DN${dn}</div>
   <div class="mut">${esc(id)} · ${eixo==="v"?"vertical":"horizontal"} · ${nf(L)} m${col==="ramal"?" desenhados na planta":""}</div><table>
   <tr><td class="k">Material</td><td>PVC esgoto série normal (branco), DN${dn}</td></tr><tr><td class="k">Fonte</td><td>${esc(orig)}</td></tr>
   <tr><td class="k">Observação</td><td>${esc(como)}</td></tr></table>`}
  else if(u.tipo==="hid"){const [id,col,pav,dn,L,orig,eixo,como]=D.hid.trechos[u.ids[hit.instanceId]];
   const r=u.A.hid.t.find(x=>x[7]===u.ids[hit.instanceId]);const alt=r?(()=>{const a=Math.min(r[1],r[4]),b=Math.max(r[1],r[4]);return Math.abs(b-a)<0.01?nf(a):nf(a)+" a "+nf(b)})():null;
   h=`<h3>Água fria · ${esc(pav)}</h3><div class="big">Tubo DN${dn} · ${nf(L)} m</div><div class="mut">${esc(id)} · coluna ${esc(col)} · ${eixo==="v"?"vertical":"horizontal"}</div><table>
   <tr><td class="k">Material</td><td>PVC soldável marrom, DN${dn}</td></tr><tr><td class="k">Comprimento</td><td>${nf(L)} m (rótulo do projeto)</td></tr>
   ${alt?`<tr><td class="k">Altura do piso</td><td>${alt} m</td></tr>`:""}
   <tr><td class="k">Fonte</td><td>${esc(orig)}</td></tr><tr><td class="k">Rótulo ligado por</td><td>${como==="chamada"?"linha de chamada":como==="perto"?"proximidade":esc(como)}</td></tr></table>
   ${D.hid.orc&&D.hid.orc.custo[id]!=null?`<h3 style="margin-top:14px">Custo (SINAPI ${esc(D.hid.orc.mes)})</h3><div class="big">${brl(D.hid.orc.custo[id])}</div><div class="mut">tubo instalado</div>`:""}`}
  else{const c=u.arr[hit.instanceId],k=String(c[3]).padStart(2,"0"),tp=tipoPecaG(c[3]);
   h=`<h3>Água fria · ${esc(nomeAndar(D.andares.indexOf(u.A)))}</h3><div class="big">${{reg:"Registro",pto:"Ponto de consumo",luva:"Bucha ou luva",no:"Conexão"}[tp]} ${esc(k)}</div><div class="mut">coluna ${esc(c[4])}</div><table>
   <tr><td class="k">Peça (tabela do projeto)</td><td>${esc(D.hid.cod[k]||"—")}</td></tr><tr><td class="k">Altura</td><td>${nf(c[1])} m do piso</td></tr></table>`}
 }else if(u.tipo==="amb"){const a=u.a;S.sel={tipo:"amb",obj:o};
  h=`<h3>Ambiente · ${esc(nomeAndar(D.andares.indexOf(u.A)))}</h3><div class="big">${esc(a.nome)}</div><div class="mut">${esc(a.unidade||NOME_AMB[a.tipo]||"")}</div><table>
  <tr><td class="k">Área medida</td><td>${nf(a.area)} m² (rótulo ${nf(a.rotulo)} m², ${a.dif==null?"—":(a.dif>0?"+":"")+nf(a.dif,1)+"%"})</td></tr>
  ${a.piso&&Math.abs(a.piso-a.area)>0.01?`<tr><td class="k">Piso total</td><td>${nf(a.piso)} m²</td></tr>`:""}
  <tr><td class="k">Perímetro</td><td>${nf(a.perim)} m</td></tr><tr><td class="k">Teto</td><td>${nf(a.teto)} m²</td></tr>
  <tr><td class="k">Rodapé</td><td>${nf(a.rodape)} m</td></tr><tr><td class="k">Parede líquida</td><td>${nf(a.parede)} m²</td></tr>
  <tr><td class="k">Portas e janelas</td><td>${a.portas??"—"} · ${a.janelas??"—"}</td></tr><tr><td class="k">Acabamento</td><td>${esc(a.acab)}</td></tr></table>`
  +(a.obs?`<div class="mut" style="margin-top:6px">${esc(a.obs)}</div>`:"")+blocoCusto(a,a.teto,"m² de teto",u.A);
 }
 el("info").innerHTML=h+`<div style="margin-top:14px"><a class="lnk" data-limpar>Voltar ao resumo</a></div>`;
 el("info").hidden=false;el("resumo").hidden=true;
 atualizar();
}
document.addEventListener("click",e=>{if(e.target.closest("[data-limpar]")){e.preventDefault();limpar();atualizar();fechar()}});
const ray=new THREE.Raycaster(),ptr=new THREE.Vector2();let down=null;
canvas.addEventListener("pointerdown",e=>{down=[e.clientX,e.clientY]});
canvas.addEventListener("pointerup",e=>{if(!down||Math.hypot(e.clientX-down[0],e.clientY-down[1])>6)return;
 const r=canvas.getBoundingClientRect();ptr.set((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1);ray.setFromCamera(ptr,camera);
 const alvo=pick.filter(o=>{if(!vivo(o))return false;const ia=o.parent.userData.ia;
  if(S.andar>=0&&ia!==S.andar)return false;if(o.userData.tipo==="par"&&(S.modo==="ambientes"||S.modo==="inst"))return false;
  if(S.modo==="inst"&&(o.userData.tipo==="amb"||o.userData.tipo==="esc"))return false;
  if(o.userData.tipo==="pec"&&S.filt.cintas&&o.userData.cat==="blo")return false;return true});
 const hs=ray.intersectObjects(alvo,false).filter(h=>(!S.corte||h.point.y<=plano.constant+1e-3)&&planoV.distanceToPoint(h.point)>=-1e-3);
 if(hs.length)selecionar(hs[0]);else{limpar();atualizar()}});
