// cores do material na obra: bloco de concreto (estrutural mais escuro, vedação mais claro), concreto armado
const COR_PAREDE={"estrutural":0xB2AEA7,"vedação":0xDCD8D0,"a definir":0xCCC6B9,"concreto":0xBFBCB6,"muro":0xC6C0B5,"parapeito":0xC9C5BD};
const COR_AMB={"seca":0xE3D7C1,"molhada":0xA9BFCB,"externa":0xB7C2A2,"circulação":0xD3CCC2,"garagem":0xBDBAB4,"técnico":0x9C9993};
const NOME_AMB={"seca":"seco (salas, quartos)","molhada":"molhado","externa":"varanda","circulação":"circulação","garagem":"garagem","técnico":"técnico"};
const SEL=0xEB6D4E,SELRGB=(()=>{const c=new THREE.Color(SEL);return [c.r,c.g,c.b]})();
const brl=v=>"R$ "+nf(v,2);
// rampa sequencial do mapa de calor (claro = barato, escuro = caro) e cinza para "sem custo"
const RAMPA=[[0,[0.96,0.92,0.80]],[0.35,[0.93,0.70,0.25]],[0.7,[0.80,0.25,0.17]],[1,[0.36,0.08,0.07]]],SEMCUSTO=[0.84,0.83,0.80];
function rampa(t){t=Math.max(0,Math.min(1,t));for(let i=1;i<RAMPA.length;i++){const [a,ca]=RAMPA[i-1],[b,cb]=RAMPA[i];if(t<=b){const u=(t-a)/(b-a);return ca.map((x,k)=>x+(cb[k]-x)*u)}}return RAMPA[RAMPA.length-1][1]}
// custo de cada andar (paredes + ambientes), usado no mapa "por andar"
D.andares.forEach(A=>{A.custo=A.paredes.reduce((s,p)=>s+(p.c||0),0)+A.ambientes.reduce((s,a)=>s+(a.c||0),0)});
const COR_DN={20:0x94603F,25:0x8A5636,32:0x7E4E31,40:0x73472D,50:0x684029},OD_DN={20:0.020,25:0.025,32:0.032,40:0.040,50:0.050};
const raioDN=dn=>Math.max((OD_DN[dn]||0.025)*0.8,0.014);
const COR_ES={40:0xF0EEE9,50:0xEAE7E1,75:0xE4E1DA,100:0xDDDAD2,150:0xD6D2C9},OD_ES={40:0.040,50:0.050,75:0.075,100:0.110,150:0.160};
const raioES=dn=>Math.max((OD_ES[dn]||0.1)*0.6,0.016);
const COR_REG=0xC0392B,COR_CON=0x6B4027;
// elétrica: eletroduto corrugado leve (amarelo) e pesado (laranja); diâmetro externo pela bitola, engrossado para aparecer
const COR_ELE=0xE3B505,COR_ELE_P=0xD9822B,OD_ELE=[0.025,0.032,0.050,0.063,0.090,0.020,0.040,0.075,0.110];
const raioEle=d=>Math.max((OD_ELE[d]||0.025)*0.7,0.012);
const CUBO=new THREE.BoxGeometry(1,1,1),DISCO=new THREE.CylinderGeometry(0.5,0.5,1,20);
const FORMA_ELE={tomada_baixa:{cor:0xF4F1EA,s:[0.09,0.07,0.09]},tomada_media:{cor:0xF4F1EA,s:[0.09,0.07,0.09]},tomada_alta:{cor:0xE9E2D2,s:[0.09,0.07,0.09]},
 interruptor:{cor:0xFFFFFF,s:[0.09,0.09,0.09]},sensor:{cor:0xD8D3C7,s:[0.10,0.08,0.10]},arandela:{cor:0xF7E3A1,s:[0.16,0.12,0.16]},
 luminaria:{cor:0xFFF1BF,s:[0.30,0.04,0.30],dy:-0.095,disco:true},quadro:{cor:0x8A9099,s:[0.28,0.42,0.28]},medicao:{cor:0x5F6670,s:[0.30,0.50,0.30]},
 entrada:{cor:0x3A3F46,s:[0.30,0.60,0.30]},cx:{cor:0x9AA0A6,s:[0.12,0.12,0.12]},forca:{cor:0xE08A1E,s:[0.12,0.12,0.12]}};
const NOME_ELE={tomada_baixa:"Tomada baixa",tomada_media:"Tomada média",tomada_alta:"Tomada alta / ponto 2,20 m",interruptor:"Interruptor",sensor:"Sensor de presença",
 arandela:"Arandela",luminaria:"Luminária de teto",quadro:"Quadro de distribuição",medicao:"Caixa de medição",entrada:"Entrada de serviço",cx:"Caixa de passagem",forca:"Ponto de força"};
const tipoPecaG=c=>{const d=((D.hid&&D.hid.cod[String(c).padStart(2,"0")])||"").toUpperCase();
 if(c>=70||d.startsWith("REGISTRO")||d.startsWith("HIDR"))return "reg";if(d.includes("BUCHA DE LAT"))return "pto";if(d.startsWith("BUCHA")||d.startsWith("LUVA"))return "luva";return "no"};
const COR_PECA={0:0xD9D6CC,1:0xB4AE9E,2:0x8E7CC3,3:0xE08A1E,4:0xF2B24C,5:0x262626,6:0x8F8A80};
const COR_PECA_VED={0:0xB9CFE4,1:0x8EAFCF,3:0xE08A1E,4:0xF2B24C,5:0x262626,6:0x8F8A80};
const NOME_PECA=[["inteiro 14×19×39",0xD9D6CC],["meio 14×19×19",0xB4AE9E],["amarração 34/54",0x8E7CC3],["canaleta J (cinta fachada)",0xE08A1E],
 ["canaleta U (cinta, verga, contraverga)",0xF2B24C],["corte/compensador",0x262626],["enchimento de argamassa (< 5 cm)",0x8F8A80],["vedação 9 cm",0xB9CFE4],["graute vertical",0x1F4E8C]];
const nf=(n,d=2)=>n==null?"—":Number(n).toLocaleString("pt-BR",{minimumFractionDigits:d,maximumFractionDigits:d});
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

// ---------- cena
const canvas=document.getElementById("c");
const renderer=new THREE.WebGLRenderer({canvas,antialias:true});
renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));
renderer.localClippingEnabled=true;
const scene=new THREE.Scene();
const corFundo=()=>getComputedStyle(document.documentElement).getPropertyValue("--stage").trim()||"#EEEDEA";
scene.background=new THREE.Color(corFundo());
const camera=new THREE.PerspectiveCamera(45,1,0.1,800);
const controls=new OrbitControls(camera,canvas);controls.enableDamping=true;controls.dampingFactor=0.1;controls.screenSpacePanning=true;
scene.add(new THREE.HemisphereLight(0xffffff,0x8a8a80,1.1));
const sol=new THREE.DirectionalLight(0xffffff,1.1);sol.position.set(30,60,20);scene.add(sol);
const plano=new THREE.Plane(new THREE.Vector3(0,-1,0),1e6);
const planoV=new THREE.Plane(new THREE.Vector3(-1,0,0),1e6);

function caixa(pos,cor,cx,cy,cz,ax,az,L,H,T,idx,lista){
 // caixa orientada: centro (cx,cy,cz), eixo horizontal (ax,az), comprimento L, altura H, espessura T
 const nx=-az,nz=ax,hl=L/2,hh=H/2,ht=T/2;
 const P=(u,v,w)=>[cx+ax*u*hl+nx*w*ht,cy+v*hh,cz+az*u*hl+nz*w*ht];
 const f=[[[1,-1,-1],[1,1,-1],[1,1,1],[1,-1,1]],[[-1,-1,1],[-1,1,1],[-1,1,-1],[-1,-1,-1]],[[-1,1,-1],[-1,1,1],[1,1,1],[1,1,-1]],
  [[-1,-1,1],[-1,-1,-1],[1,-1,-1],[1,-1,1]],[[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]],[[1,-1,-1],[-1,-1,-1],[-1,1,-1],[1,1,-1]]];
 for(const q of f){const p=q.map(x=>P(...x));for(const k of [0,1,2,0,2,3]){pos.push(...p[k]);cor.push(...lista);idx.push(0)}}
}
function pedacos(L,H,vaos){
 // decompõe a elevação (L × H) menos os vãos em retângulos [u0,u1,z0,z1]
 const cortes=[0,L];vaos.forEach(v=>{cortes.push(Math.max(0,Math.min(L,v[1])),Math.max(0,Math.min(L,v[1]+v[2])))});
 const us=[...new Set(cortes.map(x=>+x.toFixed(3)))].sort((a,b)=>a-b),out=[];
 for(let i=0;i<us.length-1;i++){const a=us[i],b=us[i+1];if(b-a<0.005)continue;
  const tampa=vaos.filter(v=>v[1]<=a+0.003&&v[1]+v[2]>=b-0.003).map(v=>[Math.max(0,v[3]),Math.min(H,v[4])]).sort((x,y)=>x[0]-y[0]);
  let z=0;for(const [z0,z1] of tampa){if(z0>z+0.005)out.push([a,b,z,z0]);z=Math.max(z,z1)}if(H>z+0.005)out.push([a,b,z,H])}
 // junta faixas vizinhas com a mesma altura
 const j=[];for(const r of out){const p=j.find(s=>Math.abs(s[1]-r[0])<0.004&&Math.abs(s[2]-r[2])<0.004&&Math.abs(s[3]-r[3])<0.004);if(p)p[1]=r[1];else j.push(r.slice())}
 return j;
}
const andares=[],pick=[];
D.andares.forEach((A,ia)=>{
 const g=new THREE.Group();g.userData={A,ia};scene.add(g);
 const mats=[];const mat=o=>{const m=new THREE.MeshLambertMaterial(Object.assign({side:THREE.DoubleSide,clippingPlanes:[plano,planoV]},o));m.userData.op=o.opacity??1;mats.push(m);return m};
 // laje (sob o piso)
 A.laje.forEach(L=>{const s=new THREE.Shape(L.ext.map(p=>new THREE.Vector2(p[0],-p[1])));
  L.furos.forEach(h=>s.holes.push(new THREE.Path(h.map(p=>new THREE.Vector2(p[0],-p[1])))));
  const geo=new THREE.ExtrudeGeometry(s,{depth:0.15,bevelEnabled:false});geo.rotateX(-Math.PI/2);
  const me=new THREE.Mesh(geo,mat({color:0xBDB9AF}));me.position.y=-0.15;me.userData.laje=true;g.add(me)});
 // ambientes
 const ambs=[];A.ambientes.forEach((a,k)=>{const s=new THREE.Shape(a.poly.map(p=>new THREE.Vector2(p[0],-p[1])));
  a.furos.forEach(h=>s.holes.push(new THREE.Path(h.map(p=>new THREE.Vector2(p[0],-p[1])))));
  const geo=new THREE.ShapeGeometry(s);geo.rotateX(-Math.PI/2);
  const me=new THREE.Mesh(geo,mat({color:COR_AMB[a.tipo]||0xdddddd,polygonOffset:true,polygonOffsetFactor:-1}));me.position.y=0.006;
  me.userData={tipo:"amb",a,A};g.add(me);ambs.push(me);pick.push(me)});
 // paredes: uma malha por (tipo, fachada), com mapa triângulo → parede
 const grupos={};
 A.paredes.forEach((p,ip)=>{const k=p.tipo+"|"+(p.fachada?"ext":"int");(grupos[k]=grupos[k]||[]).push(ip)});
 const paredes=[];
 Object.entries(grupos).forEach(([k,lista])=>{
  const pos=[],cor=[],idx=[],tri=[];const [tipo]=k.split("|");const c=new THREE.Color(COR_PAREDE[tipo]||0x999999);const rgb=[c.r,c.g,c.b];
  const faixas={};
  lista.forEach(ip=>{const p=A.paredes[ip];const dx=p.b[0]-p.a[0],dz=p.b[1]-p.a[1],L=Math.hypot(dx,dz)||1e-6,ax=dx/L,az=dz/L;
   const ini=pos.length/3;
   pedacos(L,p.h||A.pd,p.vaos).forEach(([u0,u1,z0,z1])=>{const um=(u0+u1)/2;
    caixa(pos,cor,p.a[0]+ax*um,(z0+z1)/2,p.a[1]+az*um,ax,az,u1-u0,z1-z0,Math.max(p.t,0.05),idx,rgb)});
   const n=(pos.length/3-ini)/3;for(let t=0;t<n;t++)tri.push(ip);faixas[ip]=[ini,pos.length/3-ini]});
  const geo=new THREE.BufferGeometry();geo.setAttribute("position",new THREE.Float32BufferAttribute(pos,3));
  geo.setAttribute("color",new THREE.Float32BufferAttribute(cor,3));geo.computeVertexNormals();
  const me=new THREE.Mesh(geo,mat({vertexColors:true}));me.userData={tipo:"par",tipoParede:tipo,fachada:k.endsWith("ext"),tri,faixas,A,base:rgb};
  g.add(me);paredes.push(me);pick.push(me)});
 // paginação: blocos instanciados (uma malha por tipo de parede × fachada × bloco/canaleta)
 const pecas=[],grauteM=[];
 if(A.pag){
  const caixaU=new THREE.BoxGeometry(1,1,1),lista={};
  A.pag.linhas.forEach((L,il)=>L.f.forEach((fi,k)=>fi.forEach(([u,w,c])=>{if(c>=8)return;
   const key=L.tipo+"|"+(L.fachada?"ext":"int")+"|"+(c===3||c===4?"can":"blo");(lista[key]=lista[key]||[]).push([il,k,u,w,c])})));
  const q=new THREE.Quaternion(),Y=new THREE.Vector3(0,1,0),M=new THREE.Matrix4(),pos=new THREE.Vector3(),esc_=new THREE.Vector3(),col=new THREE.Color();
  Object.entries(lista).forEach(([key,arr])=>{
   const [tipo,fach,cat]=key.split("|");const me=new THREE.InstancedMesh(caixaU,mat({}),arr.length);
   const linha=new Int32Array(arr.length),base=new Float32Array(arr.length*3);
   arr.forEach(([il,k,u,w,c],i)=>{const L=A.pag.linhas[il],dx=L.b[0]-L.a[0],dz=L.b[1]-L.a[1],LL=Math.hypot(dx,dz)||1e-6,ax=dx/LL,az=dz/LL;
    const um=(u+w/2)/100;pos.set(L.a[0]+ax*um,k*0.2+0.105,L.a[1]+az*um);q.setFromAxisAngle(Y,Math.atan2(-az,ax));
    esc_.set(Math.max(w/100-0.01,0.01),0.19,tipo==="vedação"?0.09:0.14);M.compose(pos,q,esc_);me.setMatrixAt(i,M);
    col.setHex((tipo==="vedação"?COR_PECA_VED:COR_PECA)[c]??0xcccccc);me.setColorAt(i,col);base.set([col.r,col.g,col.b],i*3);linha[i]=il});
   me.instanceMatrix.needsUpdate=true;me.instanceColor.needsUpdate=true;me.computeBoundingSphere();
   me.userData={tipo:"pec",tipoParede:tipo,fachada:fach==="ext",cat,linha,base,A};me.visible=false;g.add(me);pecas.push(me);pick.push(me)});
  // pontos de graute vertical
  const cil=new THREE.CylinderGeometry(0.045,0.045,1,10),gm=new THREE.InstancedMesh(cil,mat({color:0x1F4E8C}),A.pag.graute.length);
  A.pag.graute.forEach(([x,z],i)=>{M.compose(new THREE.Vector3(x,A.pd/2,z),new THREE.Quaternion(),new THREE.Vector3(1,A.pd+0.02,1));gm.setMatrixAt(i,M)});
  gm.instanceMatrix.needsUpdate=true;gm.computeBoundingSphere();gm.visible=false;g.add(gm);grauteM.push(gm);
 }
 // esquadrias: vidro, caixilho, porta de madeira, portão/elevador, gradil da varanda
 const esq=[];
 {const caixaE=new THREE.BoxGeometry(1,1,1),it={vidro:[],caixilho:[],madeira:[],metal:[],gradil:[]};
  A.paredes.forEach(p=>{if(!p.vaos.length)return;const dx=p.b[0]-p.a[0],dz=p.b[1]-p.a[1],LL=Math.hypot(dx,dz)||1e-6,ax=dx/LL,az=dz/LL,ang=Math.atan2(-az,ax);
   const put=(k,u,y,w,h,t)=>it[k].push([p.a[0]+ax*u,y,p.a[1]+az*u,ang,w,h,t]);
   p.vaos.forEach(([tipo,u0,w,b0,b1,kind])=>{const uc=u0+w/2,h=b1-b0,yc=(b0+b1)/2;
    if(kind==="janela"||kind==="vidro"){put("vidro",uc,yc,w-0.06,h-0.06,0.02);
     put("caixilho",uc,b1-0.025,w,0.05,0.07);put("caixilho",uc,b0+0.025,w,0.05,0.07);put("caixilho",u0+0.025,yc,0.05,h,0.07);put("caixilho",u0+w-0.025,yc,0.05,h,0.07);
     if(w>=1.0)put("caixilho",uc,yc,0.04,h,0.06)}
    else if(kind==="madeira"){put("madeira",uc,h/2,w-0.08,h-0.03,0.035);put("caixilho",u0+0.02,h/2,0.04,h,Math.min(p.t,0.15));put("caixilho",u0+w-0.02,h/2,0.04,h,Math.min(p.t,0.15));put("caixilho",uc,h-0.02,w,0.04,Math.min(p.t,0.15))}
    else if(kind==="portao"||kind==="elevador"){put("metal",uc,h/2,w-0.04,h-0.02,0.05)}
    else if(kind==="gradil"){const yt=1.10;put("gradil",uc,yt,w,0.05,0.05);put("gradil",uc,b0+0.04,w,0.04,0.04);
     const n=Math.max(2,Math.round(w/0.11));for(let i=1;i<n;i++)put("gradil",u0+i*w/n,(b0+yt)/2,0.02,yt-b0,0.02)}})});
  const COR_ESQ={vidro:[0x9CC8E8,0.35],caixilho:[0x8A8F96,1],madeira:[0xA9784A,1],metal:[0x7D8288,1],gradil:[0x3B3D40,1]};
  const M=new THREE.Matrix4(),q=new THREE.Quaternion(),Y=new THREE.Vector3(0,1,0);
  Object.entries(it).forEach(([k,arr])=>{if(!arr.length)return;const [cor,op]=COR_ESQ[k];
   const me=new THREE.InstancedMesh(caixaE,mat({color:cor,transparent:op<1,opacity:op,depthWrite:op>=1}),arr.length);
   arr.forEach(([x,y,z,a,w,h,t],i)=>{q.setFromAxisAngle(Y,a);M.compose(new THREE.Vector3(x,y,z),q,new THREE.Vector3(Math.max(w,0.01),Math.max(h,0.01),t));me.setMatrixAt(i,M)});
   me.instanceMatrix.needsUpdate=true;me.computeBoundingSphere();me.userData={esq:true};g.add(me);esq.push(me)});
 }
 // escada: cada piso é um bloco (espelho + 12 cm de laje por baixo), patamar com 12 cm; corrimão a 0,88 m e guarda-corpo a 1,10 m
 const escM=[];
 if(A.escada){const E=A.escada,h=E.h,esp=0.12,mE=mat({color:0xC9C4B8});mE.userData.base=0xC9C4B8;
  const bloco=(poly,z0,z1)=>{const s=new THREE.Shape(poly.map(p=>new THREE.Vector2(p[0],-p[1])));
   const geo=new THREE.ExtrudeGeometry(s,{depth:Math.max(z1-z0,0.01),bevelEnabled:false});geo.rotateX(-Math.PI/2);
   const me=new THREE.Mesh(geo,mE);me.position.y=z0;me.userData={tipo:"esc",E,A,mat:mE};g.add(me);escM.push(me);pick.push(me)};
  E.degraus.forEach(([k,poly])=>bloco(poly,Math.max(0,(k-1)*h-esp),k*h));
  E.patamares.forEach(([k,poly])=>bloco(poly,k*h-esp,k*h));
  const pecas_=[];const add=(a,b)=>pecas_.push([a,b]);
  E.corrimaos.forEach(c=>{const za=c.z0*h,zb=c.z1*h,P=(t,y)=>[c.a[0]+(c.b[0]-c.a[0])*t,za+(zb-za)*t+y,c.a[1]+(c.b[1]-c.a[1])*t];
   add(P(0,0.88),P(1,0.88));
   if(c.dentro){add(P(0,1.10),P(1,1.10));const L=Math.hypot(c.b[0]-c.a[0],c.b[1]-c.a[1]),n=Math.max(2,Math.round(L/0.28));
    for(let i=0;i<=n;i++){const t=(i+0.5)/(n+1),q=P(t,0);add([q[0],q[1]-0.02,q[2]],[q[0],q[1]+1.10,q[2]])}}});
  const im=new THREE.InstancedMesh(new THREE.BoxGeometry(1,1,1),mat({color:0x3B3D40}),pecas_.length),M=new THREE.Matrix4(),X=new THREE.Vector3(1,0,0);
  pecas_.forEach(([a,b],i)=>{const va=new THREE.Vector3(...a),vb=new THREE.Vector3(...b),d=vb.clone().sub(va),L=d.length();
   M.compose(va.clone().add(vb).multiplyScalar(0.5),new THREE.Quaternion().setFromUnitVectors(X,d.normalize()),new THREE.Vector3(L,0.035,0.035));im.setMatrixAt(i,M)});
  im.instanceMatrix.needsUpdate=true;im.computeBoundingSphere();g.add(im);escM.push(im);
 }
 // água fria: tubos (cilindros por DN) e conexões/registros
 const hidM=[];
 if(A.hid){const cil=new THREE.CylinderGeometry(1,1,1,12),M=new THREE.Matrix4(),Yv=new THREE.Vector3(0,1,0),porDN={};
  A.hid.t.forEach(r=>{const k=(r[8]||0)+"|"+r[6];(porDN[k]=porDN[k]||[]).push(r)});
  Object.entries(porDN).forEach(([key,arr])=>{const [sy,dn]=key.split("|").map(Number);
   const rr=sy?raioES(dn):raioDN(dn),me=new THREE.InstancedMesh(cil,mat({color:sy?(COR_ES[dn]||0x6B4226):(COR_DN[dn]||0x2E86C1)}),arr.length),ids=new Int32Array(arr.length);
   arr.forEach((r,i)=>{const a=new THREE.Vector3(r[0],r[1],r[2]),b=new THREE.Vector3(r[3],r[4],r[5]),d=b.clone().sub(a),L=Math.max(d.length(),0.004);
    M.compose(a.clone().add(b).multiplyScalar(0.5),new THREE.Quaternion().setFromUnitVectors(Yv,d.normalize()),new THREE.Vector3(rr,L,rr));me.setMatrixAt(i,M);ids[i]=r[7]});
   me.instanceMatrix.needsUpdate=true;me.computeBoundingSphere();me.userData={tipo:"hid",ids,A,raio:rr,sys:sy};me.visible=false;g.add(me);hidM.push(me);pick.push(me)});
  const sph=new THREE.SphereGeometry(1,14,10);
  // água fria: peça pelo tipo (descrição da tabela do projetista)
  const tipoPeca=c=>{const d=(D.hid.cod[String(c).padStart(2,"0")]||"").toUpperCase();
   if(c>=70||d.startsWith("REGISTRO")||d.startsWith("HIDR"))return "reg";if(d.includes("BUCHA DE LAT"))return "pto";
   if(d.startsWith("BUCHA")||d.startsWith("LUVA"))return "luva";return "no"};
  const EST={no:[COR_CON,0.026],luva:[0x7A4A2E,0.020],pto:[0xC9A227,0.024],reg:[0xC5CBD2,0.032]};
  const grupoP={};A.hid.c.forEach(c=>{const t=tipoPeca(c[3]);(grupoP[t]=grupoP[t]||[]).push(c)});
  Object.entries(grupoP).forEach(([t,arr])=>{const [cor,r]=EST[t];const me=new THREE.InstancedMesh(sph,mat({color:cor}),arr.length);
   arr.forEach((c,i)=>{M.compose(new THREE.Vector3(c[0],c[1],c[2]),new THREE.Quaternion(),new THREE.Vector3(r,r,r));me.setMatrixAt(i,M)});
   me.instanceMatrix.needsUpdate=true;me.computeBoundingSphere();me.userData={tipo:"con",arr,A,raio:r,sys:0};me.visible=false;g.add(me);hidM.push(me);pick.push(me);
   if(t==="reg"){const vol=new THREE.InstancedMesh(new THREE.CylinderGeometry(1,1,1,16),mat({color:COR_REG}),arr.length);
    arr.forEach((c,i)=>{M.compose(new THREE.Vector3(c[0],c[1]+0.034,c[2]),new THREE.Quaternion(),new THREE.Vector3(0.028,0.012,0.028));vol.setMatrixAt(i,M)});
    vol.instanceMatrix.needsUpdate=true;vol.computeBoundingSphere();vol.userData={sys:0};vol.visible=false;g.add(vol);hidM.push(vol)}});
  // esgoto: conexões (junções/joelhos) e caixas sifonadas/ralos no piso
  const pE=A.hid.p||[];const nos=pE.filter(q=>q[3]===0),cxs=pE.filter(q=>q[3]===1),cxr=pE.filter(q=>q[3]===2);
  if(nos.length){const me=new THREE.InstancedMesh(sph,mat({color:0xCFCAC1}),nos.length);
   nos.forEach((q,i)=>{const r=Math.max((OD_ES[q[5]]||0.05)*0.75,0.03);M.compose(new THREE.Vector3(q[0],q[1],q[2]),new THREE.Quaternion(),new THREE.Vector3(r,r,r));me.setMatrixAt(i,M)});
   me.instanceMatrix.needsUpdate=true;me.computeBoundingSphere();me.userData={sys:1};me.visible=false;g.add(me);hidM.push(me)}
  if(cxs.length){const cx=new THREE.InstancedMesh(new THREE.BoxGeometry(1,1,1),mat({color:0xF2F0EB}),cxs.length),gr=new THREE.InstancedMesh(new THREE.BoxGeometry(1,1,1),mat({color:0x9A9A9A}),cxs.length);
   cxs.forEach((q,i)=>{const L=Math.max(q[4],0.1);M.compose(new THREE.Vector3(q[0],q[1]-0.09,q[2]),new THREE.Quaternion(),new THREE.Vector3(L*1.4,0.18,L*1.4));cx.setMatrixAt(i,M);
    M.compose(new THREE.Vector3(q[0],q[1]+0.004,q[2]),new THREE.Quaternion(),new THREE.Vector3(L,0.006,L));gr.setMatrixAt(i,M)});
   [cx,gr].forEach(m=>{m.instanceMatrix.needsUpdate=true;m.computeBoundingSphere();m.userData={sys:1};m.visible=false;g.add(m);hidM.push(m)})}
  // caixa sifonada redonda (150 mm): corpo cilíndrico e grelha redonda
  if(cxr.length){const cil=new THREE.CylinderGeometry(0.5,0.5,1,24),cx=new THREE.InstancedMesh(cil,mat({color:0xF2F0EB}),cxr.length),gr=new THREE.InstancedMesh(cil,mat({color:0x9A9A9A}),cxr.length);
   cxr.forEach((q,i)=>{const L=Math.max(q[4],0.13);M.compose(new THREE.Vector3(q[0],q[1]-0.1,q[2]),new THREE.Quaternion(),new THREE.Vector3(L*1.15,0.2,L*1.15));cx.setMatrixAt(i,M);
    M.compose(new THREE.Vector3(q[0],q[1]+0.004,q[2]),new THREE.Quaternion(),new THREE.Vector3(L*0.95,0.006,L*0.95));gr.setMatrixAt(i,M)});
   [cx,gr].forEach(m=>{m.instanceMatrix.needsUpdate=true;m.computeBoundingSphere();m.userData={sys:1};m.visible=false;g.add(m);hidM.push(m)})}
 }
 // elétrica: eletrodutos (cilindros por bitola: leve amarelo, pesado laranja) e pontos (caixas, luminárias, quadros)
 const eleM=[];
 if(A.ele){const cil=new THREE.CylinderGeometry(1,1,1,8),M=new THREE.Matrix4(),Yv=new THREE.Vector3(0,1,0),porD={};
  A.ele.t.forEach(r=>{(porD[r[6]]=porD[r[6]]||[]).push(r)});
  Object.entries(porD).forEach(([d,arr])=>{d=+d;const rr=raioEle(d),me=new THREE.InstancedMesh(cil,mat({color:d>=2&&d<=4||d>=6?COR_ELE_P:COR_ELE}),arr.length),ids=new Int32Array(arr.length);
   arr.forEach((r,i)=>{const a=new THREE.Vector3(r[0],r[1],r[2]),b=new THREE.Vector3(r[3],r[4],r[5]),dv=b.clone().sub(a),L=Math.max(dv.length(),0.004);
    M.compose(a.clone().add(b).multiplyScalar(0.5),new THREE.Quaternion().setFromUnitVectors(Yv,dv.normalize()),new THREE.Vector3(rr,L,rr));me.setMatrixAt(i,M);ids[i]=r[7]});
   me.instanceMatrix.needsUpdate=true;me.computeBoundingSphere();me.userData={tipo:"ele",ids,A,raio:rr,sys:"eletroduto"};me.visible=false;g.add(me);eleM.push(me);pick.push(me)});
  const grupoE={};A.ele.p.forEach(p=>{(grupoE[p[3]]=grupoE[p[3]]||[]).push(p)});
  Object.entries(grupoE).forEach(([k,arr])=>{const f=FORMA_ELE[D.ele.tipos[k]]||FORMA_ELE.tomada_baixa;
   const me=new THREE.InstancedMesh(f.disco?DISCO:CUBO,mat({color:f.cor}),arr.length);
   arr.forEach((p,i)=>{M.compose(new THREE.Vector3(p[0],p[1]+(f.dy||0),p[2]),new THREE.Quaternion(),new THREE.Vector3(...f.s));me.setMatrixAt(i,M)});
   me.instanceMatrix.needsUpdate=true;me.computeBoundingSphere();me.userData={tipo:"elep",arr,A,sys:"pontos"};me.visible=false;g.add(me);eleM.push(me);pick.push(me)});
 }
 // cobertura: telhados (fibrocimento i=10%), calhas, laje e reservatórios da caixa d'água
 if(A.cob){
  const listras=()=>{const cv=document.createElement("canvas");cv.width=64;cv.height=8;const c=cv.getContext("2d");c.fillStyle="#D3D0C8";c.fillRect(0,0,64,8);
   c.fillStyle="#A9A69E";for(let i=0;i<64;i+=8)c.fillRect(i,0,3,8);const t=new THREE.CanvasTexture(cv);t.wrapS=t.wrapT=THREE.RepeatWrapping;return t};
  A.cob.telhados.forEach(T=>{const [x0,z0]=T.p0,[x1,z1]=T.p1,baixoZ0=T.calha==="y0",y0=baixoZ0?T.zb:T.za,y1=baixoZ0?T.za:T.zb;
   const geo=new THREE.BufferGeometry();
   geo.setAttribute("position",new THREE.Float32BufferAttribute([x0,y0,z0,x1,y0,z0,x1,y1,z1,x0,y0,z0,x1,y1,z1,x0,y1,z1],3));
   geo.setAttribute("uv",new THREE.Float32BufferAttribute([0,0,1,0,1,1,0,0,1,1,0,1],2));geo.computeVertexNormals();
   const tx=listras();tx.repeat.set(Math.abs(x1-x0)/0.18,1);
   const me=new THREE.Mesh(geo,mat(T.cx?{map:tx,transparent:true,opacity:0.45,depthWrite:false}:{map:tx}));me.userData.cob=true;me.userData.cobv=true;g.add(me);
   if(!T.cx){const zc=baixoZ0?z0:z1,cal=new THREE.Mesh(new THREE.BoxGeometry(Math.abs(x1-x0),0.12,0.25),mat({color:0x9AA0A6}));cal.position.set((x0+x1)/2,T.zb-0.05,zc);cal.userData.cobv=true;g.add(cal)}});
  if(A.cob.laje_res){const [p0,p1]=A.cob.laje_res;const lr=new THREE.Mesh(new THREE.BoxGeometry(Math.abs(p1[0]-p0[0]),0.15,Math.abs(p1[1]-p0[1])),mat({color:0xBDB9AF}));
   lr.position.set((p0[0]+p1[0])/2,A.cob.z_laje_res-0.075,(p0[1]+p1[1])/2);lr.userData.cobv=true;g.add(lr)}
  A.cob.reservatorios.forEach(([x,z,r])=>{const corp=new THREE.Mesh(new THREE.CylinderGeometry(r*0.94,r,A.cob.h_res,32),mat({color:0x2F6DB5}));
   corp.position.set(x,A.cob.z_laje_res+A.cob.h_res/2,z);corp.userData.cobv=true;g.add(corp);
   const tampa=new THREE.Mesh(new THREE.SphereGeometry(r*0.94,28,8,0,Math.PI*2,0,Math.PI/2),mat({color:0x2F6DB5}));tampa.scale.y=0.22;tampa.position.set(x,A.cob.z_laje_res+A.cob.h_res,z);tampa.userData.cobv=true;g.add(tampa)});
 }
 andares.push({g,A,mats,ambs,paredes,pecas,grauteM,esq,escM,hidM,eleM,rotulos:null});
});

