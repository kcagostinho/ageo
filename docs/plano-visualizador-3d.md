# Plano — Visualizador 3D do projeto (three.js)

> **Objetivo:** juntar tudo o que o leitor já produz (ambientes, paredes, vãos, paginação, quantitativos e insumos) num modelo 3D navegável do Reserva Paulicéia. Deve permitir:
> - escolher o andar;
> - clicar em ambientes e paredes para ver os números;
> - ver paredes internas e externas;
> - ver a alvenaria **bloco a bloco**.

Status em 27/11/2026: **3D-1 a 3D-4 feitas.**
- 3D-4: modo "Custo (B4)".
  - Mapa de calor por parede (R$), por m² de parede ou por andar.
  - O clique numa parede ou num ambiente mostra o custo e os itens que o compõem.
  - O resumo traz o custo por grupo e por andar e a comparação com o CUB.
  - A soma dos elementos no 3D é igual ao total da aba Orçamento (B4).
- 3D-2: modo "Paginação (blocos)" com cerca de 30 mil peças instanciadas (1º ao 5º, família 39).
- Destaque de cintas, vergas e contravergas; 74 pontos de graute por pavimento.
- Clique numa parede mostra a contagem por peça e a elevação 2D.
- 3D-3: o prédio completo.
  - Esquadrias por tipo: vidro, caixilho, porta de madeira, portão e elevador, e gradil das varandas (corrimão a 1,10 m).
  - Lajes de cada pavimento.
  - Andar "Cobertura" lido da planta de cobertura (`leitor/leitor/cobertura.py`):
    - parapeito de 1,20 m e platibanda da caixa d'água de 4,00 m;
    - 3 águas de fibrocimento com i = 10% descendo para as calhas, 191 m²;
    - 4 reservatórios de 5.000 L, contados pelo texto da planta e localizados pelos círculos tracejados.
  - Muros: os inclinados agora entram. Os do térreo têm 2,20 m; os do subsolo ficam "a definir".
  - Corte vertical (transversal ou longitudinal) com controle de posição, somado ao corte horizontal.
- Gerador: `leitor/leitor/saida_3d.py`; saída `modelo3d.html`, arquivo único de ~1,5 MB que funciona sem internet.
- three.js 0.160 com OrbitControls, num pacote embutido em `leitor/leitor/vendor` (licença MIT).
- Decisões aplicadas: arquivo HTML; térreo e subsolo incluídos; muros escondidos por padrão.
- Premissas a confirmar:
  - altura dos muros (2,20 m) e dos reservatórios (1,60 m);
  - telhado da caixa d'água simplificado (uma água);
  - "Exportar imagem" ficou para depois.

---

## 1. Viabilidade (medida nos dados atuais)

| Ponto | Resultado |
|---|---|
| Alinhar os andares (cada planta está num lugar diferente da prancha) | Deslocando cada planta para o centro do elevador coincidir, a escada cai no mesmo lugar em todos os andares com erro ≤ 1 mm. Sem rotação: todas as plantas têm a mesma orientação. |
| Altura de cada andar | Pé-direito e lajes já lidos dos cortes: subsolo 2,60, térreo 2,80, tipos 2,60, laje 0,15 m (piso a piso 2,75 m nos tipos). As cotas de nível das plantas (3,04 / 5,79 / 8,54 / 11,29 / 14,04) servem de conferência. |
| Volume da paginação em 3D | ≈ 6.460 peças por pavimento-tipo, ≈ 32 mil na obra. Com *InstancedMesh* (uma malha por tipo de bloco), é leve até no celular. |
| Dados disponíveis | Polígonos dos ambientes; eixo, espessura, tipo, lados e vãos de cada parede; peças da paginação (posição na parede, comprimento, fiada, tipo); quantitativos e insumos. Falta só estender a paginação detalhada a todos os andares (hoje só o 1º guarda as peças). |

---

## 2. O que o usuário vê

**Barra de controle**
- **Andar:** Subsolo · Térreo · 1º … 5º · Todos. O andar escolhido fica sólido e os outros ficam "fantasma" (10%) ou ocultos.
- **Modo:**
  - *Ambientes*: pisos coloridos por tipo (seco, molhado, varanda, circulação, garagem, técnico);
  - *Paredes*: volumes coloridos por tipo (estrutural, vedação, a definir, concreto, muro), com vãos recortados;
  - *Paginação*: blocos 3D (inteiro, meio, 34, 54, canaleta J/U, corte, bloco de 9 cm).
- **Filtros:** estruturais · vedação · só externas (fachada) · só internas · só cintas, vergas e contravergas · pontos de graute vertical · esquadrias.
- **Vista:** isométrica · planta (de cima) · as 4 fachadas. Controle "explodir andares" (afasta os pavimentos) e plano de corte horizontal (para ver dentro).

**Clique (painel de informações)**
- **Ambiente:** nome, unidade, área do rótulo × medida, perímetro, piso, teto, rodapé, parede líquida, portas e janelas, e acabamentos previstos (gesso, cerâmica, pintura).
- **Parede:** ID, tipo e motivo, comprimento, espessura, encontros (L/T/X), o que há de cada lado, vãos e **blocos dessa parede por tipo**, com botão "ver elevação" (a elevação 2D que já existe).
- **Bloco:** tipo, dimensão, fiada e parede.

**Resumo do andar:** quantitativos e insumos daquele pavimento. "Todos" mostra o resumo da obra.

**Celular:** girar e zoom por toque; o painel vira uma gaveta que sobe de baixo.

---

## 3. Como construir

**Fluxo de dados** (tudo gerado pelo leitor, como as outras páginas):

```
obra.json ──► saida_3d.py ──► modelo3d.html (arquivo único: three.js + dados embutidos)
   │            ├─ registro dos andares (deslocamento pelo núcleo)
   │            ├─ níveis z (cortes)
   │            ├─ pt → metros; eixo y do PDF → eixo z da cena
   │            └─ peças da paginação de todos os andares (formato compacto)
```

**Componentes da cena (three.js)**

| Elemento | Técnica |
|---|---|
| Piso dos ambientes | `ShapeGeometry` do polígono (com furos), no nível do andar; clicável (raycaster) |
| Laje | Contorno do andar (ambientes + paredes) extrudado 15 cm |
| Parede sólida | Elevação da parede (comprimento × pé-direito) menos os retângulos dos vãos, decomposta em retângulos → caixas com a espessura. Não precisa de operação booleana. |
| Blocos (paginação) | `InstancedMesh` por tipo de peça, com junta de 1 cm entre blocos. Cortes com escala variável. |
| Esquadrias | Painéis simples nos vãos: vidro (janela), madeira (porta), gradil (varanda) |
| Pontos de graute | Cilindros finos verticais nos encontros e laterais de vão |
| Térreo/subsolo | Paredes "a definir" (laranja), pilares 20×40 (concreto), garagem; muros opcionais |
| Desempenho | Geometria estática unida por andar; sombras desligadas; resolução limitada a 2× |

**Bibliotecas:**
- three.js com versão fixa (ex.: 0.160), mais OrbitControls e BufferGeometryUtils.
- Os arquivos ficam embutidos no HTML para funcionar sem internet, ao custo de cerca de 1 MB a mais.
- Tamanho total esperado: 2 a 3 MB.

---

## 4. Etapas

| Etapa | Entrega | Pronto quando |
|---|---|---|
| **3D-1 · Volumes** | Andares empilhados e alinhados; seleção de andar; pisos clicáveis com os dados; paredes sólidas por tipo com vãos; filtros interna/externa; vistas prontas | Andares alinhados (≤ 1 cm); clique mostra os mesmos números da planilha; gira liso no celular |
| **3D-2 · Paginação** | Blocos 3D por tipo; destaque de cintas, vergas e contravergas; pontos de graute; clique na parede abre a elevação e a contagem | Total de peças no 3D = aba Paginação; a elevação 2D bate com a vista 3D |
| **3D-3 · Completar o prédio** ✅ | Esquadrias; lajes; cobertura (telhado, platibanda, caixa d'água a partir da planta de cobertura e dos cortes); terreno e muros; corte vertical; exportar imagem | Silhueta confere com as fachadas e os cortes |
| **3D-4 · Custo** ✅ | Clique mostra o custo do elemento; mapa de calor de custo por parede/andar | Soma no 3D = total do orçamento |

*Opcional:* exportar IFC para abrir em visualizadores BIM.

---

## 5. Decisões

1. **Formato de entrega:**
   - (a) arquivo HTML único, como as outras páginas, que funciona sem internet;
   - (b) página privada no claude.ai, que pode ser compartilhada com o arquiteto ou o engenheiro por link.
2. **Térreo, subsolo e muros na primeira etapa:**
   - Recomendado: térreo e subsolo entram, com a transição em destaque.
   - Muros ficam escondidos por padrão: os trechos inclinados ainda saem picados.
3. **Detalhe do bloco:**
   - Recomendado: caixa com junta, que é leve.
   - Alternativa: perfil real (furos, canaleta em U), mais pesado no celular.
4. **Cobertura e caixa d'água:** na primeira etapa ou na 3D-3?

## 6. Limitações conhecidas

- Não há projeto estrutural. Lajes e transição são representadas de forma simples; pilares só onde aparecem na planta.
- A paginação é estimativa (premissas da B2/B3) e o 3D mostra exatamente essa estimativa.
- Paredes inclinadas (muros) ainda não são lidas como peças contínuas.
