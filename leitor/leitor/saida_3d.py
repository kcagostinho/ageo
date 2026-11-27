"""Visualizador 3D (three.js) — etapa 3D-1: andares, ambientes clicáveis, paredes por tipo com vãos.

Gera um HTML único (three.js embutido, sem internet). Coordenadas da cena em metros:
X = direita da planta, Z = para baixo na planta, Y = para cima. Cada andar é alinhado pelo centro do
elevador (o mesmo em todos os pavimentos) e posto na altura lida dos cortes.
"""
from __future__ import annotations

import html
import json
import unicodedata
from pathlib import Path

import shapely
from shapely.geometry import Polygon, LineString

VENDOR = Path(__file__).parent / "vendor" / "three-0.160.0-orbit.min.js"


def _sa(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def _acabamento(nome: str, tipo: str) -> str:
    n = _sa(nome)
    if tipo == "externa":
        return "Pintura projetada direto no bloco (premissa)"
    if tipo in ("garagem", "técnico"):
        return "—"
    if "banheiro" in n or "lavabo" in n:
        return "Cerâmica até o teto (premissa) · teto: fundo preparador + gesso"
    if "cozinha" in n or "a.s." in n or "servico" in n:
        return "Cerâmica até 1,50 m (premissa) + fundo preparador + gesso acima · teto: gesso"
    return "Fundo preparador + gesso (paredes e teto)"


def _r(v, n=3):
    return round(float(v), n)


def montar(dados: dict) -> dict:
    from .quantitativos import classificar
    vistas = [v for v in dados["vistas"] if any(a["vista"] == v["id"] for a in dados["ambientes"])]
    pd = dados["premissas"]["pe_direito_m"]
    laje = 0.15
    # níveis: térreo = 0; subsolo abaixo; tipos acima (pé-direito + laje)
    nomes = [v["titulo"] for v in vistas]
    i_ter = next((i for i, t in enumerate(nomes) if "térreo" in t.lower() or "terreo" in t.lower()), 0)
    z = {}
    acc = 0.0
    for i in range(i_ter, len(vistas)):
        z[nomes[i]] = acc
        acc += pd.get(nomes[i], 2.6) + laje
    acc = 0.0
    for i in range(i_ter - 1, -1, -1):
        acc -= pd.get(nomes[i], 2.6) + laje
        z[nomes[i]] = acc
    qidx = {q["indice_ambiente"]: q for q in dados["quantitativos"]}
    pag39 = dados.get("paginacao", {}).get(dados["premissas"].get("familia", "39"), {}).get("por_pavimento", {})

    andares = []
    for ordem, v in enumerate(vistas):
        m = v["m_por_pt"]
        ambs = [(i, a) for i, a in enumerate(dados["ambientes"]) if a["vista"] == v["id"] and a["poligono"]]
        el = next((a for _, a in ambs if a["nome"] == "Elevador"), None)
        if el is None:
            continue
        c = Polygon(el["poligono"]).centroid
        ox, oy = c.x * m, c.y * m
        conv = lambda p: [_r(p[0] * m - ox), _r(p[1] * m - oy)]

        amb_out, polys_m = [], []
        for i, a in ambs:
            q = qidx.get(i, {})
            tipo = classificar(a["nome"])
            poly = [conv(p) for p in a["poligono"]]
            furos = [[conv(p) for p in h] for h in (a.get("furos") or [])]
            polys_m.append((a["nome"], Polygon(poly, furos).buffer(0)))
            amb_out.append({
                "nome": a["nome"], "unidade": a.get("unidade") or "", "tipo": tipo, "poly": poly, "furos": furos,
                "rot": conv(a["rotulo_xy"]), "area": a["area_m2"], "rotulo": a["area_rotulo_m2"], "dif": a["divergencia_pct"],
                "piso": a["area_piso_m2"], "perim": a["perimetro_m"],
                "teto": q.get("teto_m2"), "rodape": q.get("rodape_m"), "parede": q.get("parede_liquida_m2"),
                "portas": q.get("n_portas"), "janelas": q.get("n_janelas"), "acab": _acabamento(a["nome"], tipo),
                "obs": q.get("observacao") or a.get("observacao") or "",
            })

        par_out, caixas = [], []
        for p in dados["paredes"]:
            if p["vista"] != v["id"]:
                continue
            e = p["eixo"]
            a_, b_ = conv(e[:2]), conv(e[2:])
            vaos = []
            for x in p["vaos"]:
                w = x["largura_m"]
                if x["tipo"] == "porta":
                    base, topo = 0.0, x.get("altura_m") or 2.10
                else:
                    base = x.get("peitoril_m") or 1.0
                    topo = base + (x.get("altura_m") or 1.2)
                vaos.append([x["tipo"], _r(x["inicio_m"]), _r(w), _r(base, 2), _r(topo, 2)])
            par_out.append({"id": p["id"], "tipo": p["tipo"], "fachada": p["fachada"], "a": a_, "b": b_,
                            "t": p["espessura_m"], "comp": p["comprimento_m"], "enc": [p["encontros"]["a"], p["encontros"]["b"]],
                            "la": p["lado_a"], "lb": p["lado_b"], "motivo": p["motivo"], "vaos": vaos})
            if p["tipo"] != "muro":
                caixas.append(LineString([a_, b_]).buffer(p["espessura_m"] / 2, cap_style="square"))

        # laje: contorno do andar (ambientes + paredes), com furo no elevador e na escada
        corpo = shapely.union_all([g for _, g in polys_m if not g.is_empty] + caixas).buffer(0.03, join_style="mitre").buffer(-0.03, join_style="mitre")
        furos_laje = [g for n, g in polys_m if n == "Elevador" or n.lower().startswith("escada")]
        if ordem != i_ter and ordem > 0:
            corpo = corpo.difference(shapely.union_all(furos_laje)) if furos_laje else corpo
        laje_out = []
        for g in getattr(corpo, "geoms", [corpo]):
            if g.geom_type != "Polygon" or g.area < 1:
                continue
            g = g.simplify(0.01)
            laje_out.append({"ext": [[_r(x), _r(y)] for x, y in g.exterior.coords][:-1],
                             "furos": [[[_r(x), _r(y)] for x, y in h.coords][:-1] for h in g.interiors]})

        # resumo do andar
        def soma(tipo, campo):
            return sum(x[campo] for x in par_out if x["tipo"] == tipo)
        pdv = pd.get(v["titulo"], 2.6)
        def liq(tipo):
            return sum(x["comp"] * pdv - sum(w * (t1 - t0) for _, _, w, t0, t1 in x["vaos"]) for x in par_out if x["tipo"] == tipo)
        pg = pag39.get(v["titulo"], {})
        blocos_est = sum(val for k, val in pg.items() if k.startswith(("14×", "canaleta J 14", "meia canaleta J 14", "canaleta U 14", "meia canaleta U 14")))
        blocos_ved = sum(val for k, val in pg.items() if k.startswith(("9×", "canaleta U 9", "meia canaleta U 9")))
        resumo = [
            ["Ambientes", f"{len(amb_out)}"],
            ["Piso (soma dos ambientes)", f"{sum(x['piso'] or 0 for x in amb_out):,.2f} m²"],
            ["Parede estrutural", f"{soma('estrutural', 'comp'):,.1f} m · {liq('estrutural'):,.1f} m² líquidos"],
            ["Parede de vedação", f"{soma('vedação', 'comp'):,.1f} m · {liq('vedação'):,.1f} m² líquidos"],
        ]
        if soma("a definir", "comp"):
            resumo.append(["Parede a definir (sob a transição)", f"{soma('a definir', 'comp'):,.1f} m"])
        n_portas = sum(1 for x in par_out for y in x["vaos"] if y[0] == "porta")
        n_jan = sum(1 for x in par_out for y in x["vaos"] if y[0] == "janela")
        n_var = sum(1 for x in par_out for y in x["vaos"] if y[0] == "varanda")
        resumo.append(["Vãos nas paredes", f"{n_portas} portas · {n_jan} janelas" + (f" · {n_var} varandas" if n_var else "")])
        if blocos_est:
            resumo.append(["Blocos estruturais (fam. 39)", f"{blocos_est:,.0f} peças"])
            resumo.append(["Blocos de vedação (9 cm)", f"{blocos_ved:,.0f} peças"])
        andares.append({"id": v["id"], "nome": v["titulo"], "ordem": ordem, "z": _r(z[v["titulo"]], 2), "pd": pdv,
                        "ambientes": amb_out, "paredes": par_out, "laje": laje_out,
                        "resumo": [[k, val.replace(",", "X").replace(".", ",").replace("X", ".")] for k, val in resumo]})

    obra = []
    ins = dados.get("insumos")
    if ins:
        for g, insumo, un, _, base, _, coef, _, perda, _ in ins["linhas"]:
            if any(k in insumo for k in ("Bloco 14", "Bloco 9", "Argamassa", "Graute", "Aço", "Gesso liso", "Pintura projetada direto")):
                q = base * coef * (1 + perda)
                obra.append([insumo, (f"{q:,.0f}" if un == "un" else f"{q:,.1f}").replace(",", "X").replace(".", ",").replace("X", ".") + f" {un}"])
    return {"obra": dados["obra"], "doc": dados["documento"], "gerado": dados["gerado_em"], "andares": andares, "resumoObra": obra}


def gerar(dados: dict, destino: Path):
    modelo = montar(dados)
    js = VENDOR.read_text(encoding="utf-8").replace("</script", "<\\/script")
    payload = json.dumps(modelo, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    txt = (MODELO.replace("__THREE__", js).replace("__DADOS__", payload)
           .replace("__OBRA__", html.escape(modelo["obra"])))
    destino.write_text(txt, encoding="utf-8")


MODELO = r"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Modelo 3D</title>
<style>
:root{--bg:#F3F2EE;--card:rgba(255,255,255,.94);--bd:rgba(0,0,0,.1);--tx:#1A1A1A;--mut:#5F5E5A;--dim:#888780;--acc:#0F6E56;--chip:#fff}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#17181A;--card:rgba(36,36,34,.94);--bd:rgba(255,255,255,.12);--tx:#F5F5F2;--mut:#B4B2A9;--dim:#888780;--acc:#5DCAA5;--chip:#2C2C2A}}
:root[data-theme=dark]{--bg:#17181A;--card:rgba(36,36,34,.94);--bd:rgba(255,255,255,.12);--tx:#F5F5F2;--mut:#B4B2A9;--dim:#888780;--acc:#5DCAA5;--chip:#2C2C2A}
*{box-sizing:border-box}html,body{margin:0;height:100%;background:var(--bg);color:var(--tx);font:13px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;overflow:hidden}
#c{position:fixed;inset:0}
.top{position:fixed;left:0;right:0;top:0;padding:10px 12px;display:flex;flex-direction:column;gap:6px;pointer-events:none;z-index:2}
.row{display:flex;gap:6px;overflow-x:auto;pointer-events:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch}.row::-webkit-scrollbar{display:none}
.tit{font-weight:600;font-size:14px;pointer-events:auto;text-shadow:0 1px 0 var(--bg)}
.chip{flex:none;border:1px solid var(--bd);background:var(--chip);color:var(--tx);border-radius:999px;padding:5px 11px;font:inherit;cursor:pointer;white-space:nowrap}
.chip[aria-pressed=true]{background:var(--acc);border-color:var(--acc);color:#fff}
.chip.f[aria-pressed=false]{opacity:.55}
.chip i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;vertical-align:0}
.painel{position:fixed;right:12px;top:118px;bottom:12px;width:330px;background:var(--card);border:1px solid var(--bd);border-radius:14px;overflow:auto;z-index:2;backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px)}
.sec{padding:12px 14px;border-bottom:1px solid var(--bd)}.sec:last-child{border-bottom:0}
.sec h3{margin:0 0 6px;font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.4px;font-weight:600}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}td{padding:3px 0;vertical-align:top}td.k{color:var(--mut);padding-right:8px;width:48%}
.big{font-size:15px;font-weight:600;margin-bottom:2px}.mut{color:var(--mut)}
.ctl{display:flex;align-items:center;gap:8px;margin:6px 0}.ctl input[type=range]{flex:1}
.handle{display:none}
@media (max-width:760px){
 .painel{left:0;right:0;top:auto;bottom:0;width:auto;max-height:42vh;border-radius:16px 16px 0 0;transition:max-height .2s}
 .painel.min{max-height:52px;overflow:hidden}
 .handle{display:block;width:100%;border:0;background:none;padding:8px 0 2px;cursor:pointer}.handle span{display:block;margin:0 auto;width:40px;height:5px;border-radius:3px;background:var(--dim)}
}
.tip{position:fixed;pointer-events:none;background:#1A1A1A;color:#fff;font-size:12px;padding:5px 8px;border-radius:6px;display:none;z-index:3}
</style></head><body>
<canvas id="c"></canvas>
<div class="top">
 <div class="tit">__OBRA__ · modelo 3D</div>
 <div class="row" id="andares"></div>
 <div class="row" id="modos"></div>
 <div class="row" id="filtros"></div>
</div>
<div class="painel" id="painel">
 <button class="handle" id="handle" aria-label="Recolher painel"><span></span></button>
 <div class="sec" id="info"><h3>Seleção</h3><div class="mut">Toque ou clique num ambiente ou numa parede.</div></div>
 <div class="sec"><h3>Visualização</h3>
  <div class="ctl"><span>Afastar andares</span><input type="range" id="explode" min="0" max="4" step="0.1" value="0"></div>
  <div class="ctl"><label><input type="checkbox" id="corte"> Cortar a</label><input type="range" id="altcorte" min="0.3" max="2.6" step="0.05" value="1.2" disabled><span id="altv">1,20 m</span></div>
  <div class="row" id="cams" style="flex-wrap:wrap"></div>
 </div>
 <div class="sec" id="resumo"></div>
 <div class="sec" id="legenda"></div>
</div>
<div class="tip" id="tip"></div>
<script>__THREE__</script>
<script>
"use strict";
const D=__DADOS__;
const COR_PAREDE={"estrutural":0xC0392B,"vedação":0x2E86C1,"a definir":0xE8A317,"concreto":0x7B7B7B,"muro":0x9A6B2F};
const COR_AMB={"seca":0xE9E1CF,"molhada":0x9FD3E6,"externa":0xB9E0A5,"circulação":0xD9D2E9,"garagem":0xCFCFCF,"técnico":0x8C8C8C};
const NOME_AMB={"seca":"seco (salas, quartos)","molhada":"molhado","externa":"varanda","circulação":"circulação","garagem":"garagem","técnico":"técnico"};
const SEL=0xFFD400;
const nf=(n,d=2)=>n==null?"—":Number(n).toLocaleString("pt-BR",{minimumFractionDigits:d,maximumFractionDigits:d});
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

// ---------- cena
const canvas=document.getElementById("c");
const renderer=new THREE.WebGLRenderer({canvas,antialias:true});
renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));
renderer.localClippingEnabled=true;
const scene=new THREE.Scene();
const corFundo=()=>getComputedStyle(document.documentElement).getPropertyValue("--bg").trim()||"#F3F2EE";
scene.background=new THREE.Color(corFundo());
const camera=new THREE.PerspectiveCamera(45,1,0.1,800);
const controls=new OrbitControls(camera,canvas);controls.enableDamping=true;controls.dampingFactor=0.1;controls.screenSpacePanning=true;
scene.add(new THREE.HemisphereLight(0xffffff,0x8a8a80,1.1));
const sol=new THREE.DirectionalLight(0xffffff,1.1);sol.position.set(30,60,20);scene.add(sol);
const plano=new THREE.Plane(new THREE.Vector3(0,-1,0),1e6);

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
 const mats=[];const mat=o=>{const m=new THREE.MeshLambertMaterial(Object.assign({side:THREE.DoubleSide,clippingPlanes:[plano]},o));mats.push(m);return m};
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
   pedacos(L,A.pd,p.vaos).forEach(([u0,u1,z0,z1])=>{const um=(u0+u1)/2;
    caixa(pos,cor,p.a[0]+ax*um,(z0+z1)/2,p.a[1]+az*um,ax,az,u1-u0,z1-z0,Math.max(p.t,0.05),idx,rgb)});
   const n=(pos.length/3-ini)/3;for(let t=0;t<n;t++)tri.push(ip);faixas[ip]=[ini,pos.length/3-ini]});
  const geo=new THREE.BufferGeometry();geo.setAttribute("position",new THREE.Float32BufferAttribute(pos,3));
  geo.setAttribute("color",new THREE.Float32BufferAttribute(cor,3));geo.computeVertexNormals();
  const me=new THREE.Mesh(geo,mat({vertexColors:true}));me.userData={tipo:"par",tipoParede:tipo,fachada:k.endsWith("ext"),tri,faixas,A,base:rgb};
  g.add(me);paredes.push(me);pick.push(me)});
 andares.push({g,A,mats,ambs,paredes,rotulos:null});
});

// ---------- estado e interface
const S={andar:-1,modo:"paredes",filt:{"estrutural":true,"vedação":true,"a definir":true,"concreto":true,"muro":false,"ext":true,"int":true,"laje":true},explode:0,corte:false,alt:1.2,sel:null};
const el=id=>document.getElementById(id);
function chips(id,itens,ativo,cb,cls=""){const r=el(id);r.innerHTML="";itens.forEach(([v,t,cor])=>{const b=document.createElement("button");b.className="chip "+cls;
 b.innerHTML=(cor!=null?`<i style="background:#${cor.toString(16).padStart(6,"0")}"></i>`:"")+esc(t);b.setAttribute("aria-pressed",ativo(v));b.onclick=()=>{cb(v);atualizar()};r.appendChild(b)})}
function ui(){
 chips("andares",[[-1,"Todos"],...D.andares.map((A,i)=>[i,A.nome.replace("Pavimento ","").replace("ºPavimento","º pav.")])],v=>v===S.andar,v=>{S.andar=v;S.sel=null;enquadrar(false)});
 chips("modos",[["paredes","Paredes"],["ambientes","Ambientes"]],v=>v===S.modo,v=>S.modo=v);
 chips("filtros",[["estrutural","Estrutural",COR_PAREDE["estrutural"]],["vedação","Vedação",COR_PAREDE["vedação"]],["a definir","A definir",COR_PAREDE["a definir"]],
  ["concreto","Pilares/concreto",COR_PAREDE["concreto"]],["muro","Muros",COR_PAREDE["muro"]],["ext","Externas"],["int","Internas"],["laje","Lajes"]],
  v=>S.filt[v],v=>S.filt[v]=!S.filt[v],"f");
}
function atualizar(){
 ui();
 const ii=S.andar;
 andares.forEach((F,i)=>{const acima=ii>=0&&i>ii,abaixo=ii>=0&&i<ii;
  F.g.visible=!acima;F.g.position.y=F.A.z+i*S.explode;
  F.mats.forEach(m=>{m.transparent=abaixo;m.opacity=abaixo?0.12:1;m.depthWrite=!abaixo});
  F.paredes.forEach(me=>{const u=me.userData;me.visible=S.filt[u.tipoParede]!==false&&S.filt[u.fachada?"ext":"int"];
   me.material.transparent=abaixo||S.modo==="ambientes";me.material.opacity=abaixo?0.12:(S.modo==="ambientes"?0.18:1)});
  F.ambs.forEach(me=>{me.material.color.setHex(S.modo==="ambientes"||me===S.sel?.obj?(me===S.sel?.obj?SEL:COR_AMB[me.userData.a.tipo]):0xE4E1D8)});
  F.g.children.forEach(c=>{if(c.userData.laje)c.visible=S.filt.laje});
 });
 // corte horizontal no andar selecionado (ou no térreo em "Todos")
 const ref=ii>=0?andares[ii]:andares.find(F=>/t[ée]rreo/i.test(F.A.nome))||andares[0];
 plano.constant=S.corte?ref.g.position.y+S.alt:1e6;
 rotulos();resumo();legenda();
}
function rotulos(){
 andares.forEach(F=>{if(F.rotulos){F.g.remove(F.rotulos);F.rotulos=null}});
 if(S.andar<0)return;const F=andares[S.andar];const gr=new THREE.Group();
 F.A.ambientes.forEach(a=>{if(a.tipo==="técnico"&&a.nome!=="Elevador")return;
  const cv=document.createElement("canvas"),ctx=cv.getContext("2d"),t=a.nome,fs=44;ctx.font=`600 ${fs}px -apple-system,Segoe UI,Arial`;
  const w=Math.ceil(ctx.measureText(t).width)+28;cv.width=w;cv.height=fs+24;ctx.font=`600 ${fs}px -apple-system,Segoe UI,Arial`;
  ctx.fillStyle="rgba(255,255,255,.85)";ctx.beginPath();ctx.roundRect?ctx.roundRect(0,0,w,cv.height,14):ctx.rect(0,0,w,cv.height);ctx.fill();
  ctx.fillStyle="#1A1A1A";ctx.textBaseline="middle";ctx.fillText(t,14,cv.height/2+2);
  const sp=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(cv),depthTest:false,transparent:true}));
  const h=0.32;sp.scale.set(h*w/cv.height,h,1);sp.position.set(a.rot[0],F.A.pd*0.55,a.rot[1]);sp.renderOrder=10;gr.add(sp)});
 F.g.add(gr);F.rotulos=gr;
}
function resumo(){
 if(S.andar>=0){const A=D.andares[S.andar];el("resumo").innerHTML=`<h3>${esc(A.nome)} · pé-direito ${nf(A.pd)} m · nível ${nf(A.z)} m</h3><table>`+A.resumo.map(([k,v])=>`<tr><td class="k">${esc(k)}</td><td>${esc(v)}</td></tr>`).join("")+"</table>"}
 else el("resumo").innerHTML=`<h3>Obra · principais insumos (família 39)</h3><table>`+D.resumoObra.map(([k,v])=>`<tr><td class="k">${esc(k)}</td><td>${esc(v)}</td></tr>`).join("")+"</table>";
}
function legenda(){
 const it=S.modo==="ambientes"?Object.entries(COR_AMB).map(([k,c])=>[NOME_AMB[k],c]):Object.entries(COR_PAREDE).map(([k,c])=>[k,c]);
 el("legenda").innerHTML="<h3>Legenda</h3>"+it.map(([t,c])=>`<span style="display:inline-flex;align-items:center;margin:0 10px 4px 0"><i style="display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:5px;background:#${c.toString(16).padStart(6,"0")}"></i>${esc(t)}</span>`).join("")
  +`<div class="mut" style="margin-top:6px">Arraste para girar, pinça/roda para zoom, dois dedos (ou botão direito) para mover.</div>`;
}
// ---------- seleção
function limparSel(){
 if(!S.sel)return;const s=S.sel;
 if(s.tipo==="par"){const u=s.obj.userData,[ini,n]=u.faixas[s.ip],c=s.obj.geometry.attributes.color;for(let k=ini;k<ini+n;k++)c.setXYZ(k,...u.base);c.needsUpdate=true}
 S.sel=null;
}
function selecionar(hit){
 limparSel();
 const o=hit.object,u=o.userData;
 if(u.tipo==="par"){const ip=u.tri[hit.faceIndex];const p=u.A.paredes[ip];const [ini,n]=u.faixas[ip],c=o.geometry.attributes.color,y=new THREE.Color(SEL);
  for(let k=ini;k<ini+n;k++)c.setXYZ(k,y.r,y.g,y.b);c.needsUpdate=true;S.sel={tipo:"par",obj:o,ip};
  const vs=p.vaos.map(v=>`${v[0]} ${nf(v[2])}×${nf(v[4]-v[3])}`+(v[0]!=="porta"?` (peitoril ${nf(v[3])})`:"")).join("; ")||"—";
  el("info").innerHTML=`<h3>Parede · ${esc(u.A.nome)}</h3><div class="big">${esc(p.id)} · ${esc(p.tipo)}</div><div class="mut">${esc(p.motivo)}</div><table>
  <tr><td class="k">Comprimento (eixo)</td><td>${nf(p.comp)} m</td></tr><tr><td class="k">Espessura</td><td>${nf(p.t)} m</td></tr>
  <tr><td class="k">Altura</td><td>${nf(u.A.pd)} m · ${Math.round(u.A.pd/0.2)} fiadas</td></tr>
  <tr><td class="k">Fachada</td><td>${p.fachada?"sim (externa)":"não (interna)"}</td></tr><tr><td class="k">Encontros</td><td>${esc(p.enc.join(" / "))}</td></tr>
  <tr><td class="k">Lado A</td><td>${esc(p.la.join(", "))}</td></tr><tr><td class="k">Lado B</td><td>${esc(p.lb.join(", "))}</td></tr>
  <tr><td class="k">Vãos</td><td>${esc(vs)}</td></tr></table>`;
 }else if(u.tipo==="amb"){const a=u.a;S.sel={tipo:"amb",obj:o};
  el("info").innerHTML=`<h3>Ambiente · ${esc(u.A.nome)}</h3><div class="big">${esc(a.nome)}</div><div class="mut">${esc(a.unidade||NOME_AMB[a.tipo]||"")}</div><table>
  <tr><td class="k">Área medida</td><td>${nf(a.area)} m² (rótulo ${nf(a.rotulo)} m², ${a.dif==null?"—":(a.dif>0?"+":"")+nf(a.dif,1)+"%"})</td></tr>
  ${a.piso&&Math.abs(a.piso-a.area)>0.01?`<tr><td class="k">Piso total</td><td>${nf(a.piso)} m²</td></tr>`:""}
  <tr><td class="k">Perímetro</td><td>${nf(a.perim)} m</td></tr><tr><td class="k">Teto</td><td>${nf(a.teto)} m²</td></tr>
  <tr><td class="k">Rodapé</td><td>${nf(a.rodape)} m</td></tr><tr><td class="k">Parede líquida</td><td>${nf(a.parede)} m²</td></tr>
  <tr><td class="k">Portas / janelas</td><td>${a.portas??"—"} / ${a.janelas??"—"}</td></tr><tr><td class="k">Acabamento</td><td>${esc(a.acab)}</td></tr></table>`
  +(a.obs?`<div class="mut" style="margin-top:6px">${esc(a.obs)}</div>`:"");
 }
 if(window.innerWidth<=760)el("painel").classList.remove("min");
 atualizar();
}
const ray=new THREE.Raycaster(),ptr=new THREE.Vector2();let down=null;
canvas.addEventListener("pointerdown",e=>{down=[e.clientX,e.clientY]});
canvas.addEventListener("pointerup",e=>{if(!down||Math.hypot(e.clientX-down[0],e.clientY-down[1])>6)return;
 const r=canvas.getBoundingClientRect();ptr.set((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1);ray.setFromCamera(ptr,camera);
 const alvo=pick.filter(o=>{let p=o;while(p){if(!p.visible)return false;p=p.parent}const ia=o.parent.userData.ia;
  if(S.andar>=0&&ia!==S.andar)return false;if(o.userData.tipo==="par"&&S.modo==="ambientes")return false;return true});
 const hs=ray.intersectObjects(alvo,false).filter(h=>{if(!S.corte)return true;return h.point.y<=plano.constant+1e-3});
 if(hs.length)selecionar(hs[0]);else{limparSel();el("info").innerHTML='<h3>Seleção</h3><div class="mut">Toque ou clique num ambiente ou numa parede.</div>';atualizar()}});
// ---------- câmera
function caixaVisivel(){const b=new THREE.Box3();andares.forEach((F,i)=>{if(S.andar<0||i===S.andar)b.expandByObject(F.g)});return b}
function enquadrar(anim,vista="iso"){
 // distância para a esfera envolvente caber no menor campo de visão (vale para tela em pé ou deitada)
 const b=caixaVisivel(),c=b.getCenter(new THREE.Vector3()),R=b.getBoundingSphere(new THREE.Sphere()).radius;
 const vf=THREE.MathUtils.degToRad(camera.fov),hf=2*Math.atan(Math.tan(vf/2)*camera.aspect),dist=R/Math.sin(Math.min(vf,hf)/2)*1.02;
 const dir={iso:[0.62,0.55,0.68],planta:[0,1,0.0001],cima:[0,0.22,-1],baixo:[0,0.22,1],esq:[-1,0.22,0],dir:[1,0.22,0]}[vista];
 const v=new THREE.Vector3(...dir).normalize().multiplyScalar(dist);
 camera.position.copy(c).add(v);controls.target.copy(c);camera.near=Math.max(0.05,dist/500);camera.far=dist*10;camera.updateProjectionMatrix();controls.update();
}
el("cams").innerHTML="";[["iso","Isométrica"],["planta","Planta"],["cima","Lado de cima"],["baixo","Lado de baixo"],["esq","Lado esquerdo"],["dir","Lado direito"]].forEach(([v,t])=>{
 const b=document.createElement("button");b.className="chip";b.textContent=t;b.title="Lados como na planta 2D";b.onclick=()=>enquadrar(false,v);el("cams").appendChild(b)});
el("explode").oninput=e=>{S.explode=+e.target.value;atualizar()};
el("corte").onchange=e=>{S.corte=e.target.checked;el("altcorte").disabled=!S.corte;atualizar()};
el("altcorte").oninput=e=>{S.alt=+e.target.value;el("altv").textContent=nf(S.alt)+" m";atualizar()};
el("handle").onclick=()=>el("painel").classList.toggle("min");
function redim(){const w=window.innerWidth,h=window.innerHeight;renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix()}
window.addEventListener("resize",redim);
matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change",()=>{scene.background=new THREE.Color(corFundo())});
if(window.innerWidth<=760)el("painel").classList.add("min");
redim();atualizar();enquadrar(false);
(function loop(){requestAnimationFrame(loop);controls.update();renderer.render(scene,camera)})();
</script></body></html>"""
