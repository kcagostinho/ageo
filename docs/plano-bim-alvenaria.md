# Plano — "BIM de alvenaria" para orçamento (Reserva Paulicéia)

> **Objetivo:** transformar as paredes do projeto num modelo paramétrico (cada parede um objeto, com espessura, altura, encontros e vãos) e, a partir dele, contar **bloco inteiro, meio bloco, blocos de amarração, canaletas U/J e compensadores**, mais argamassa, graute, aço, telas e revestimentos ("massa"). A planilha final deve ter **todos os parâmetros de precificação** editáveis.

Status em 27/11/2026:
- **B1 (modelo de paredes) feita:** `leitor/leitor/paredes.py`, aba Paredes e página `paredes.html`.
- **B2 (paginação) feita:** `leitor/leitor/paginacao.py`, abas Paginação e Paginação por parede, página `paginacao.html`, com comparação das famílias 29 e 39.
- **Família escolhida: 39** (27/11/2026).
- **Amarração revisada (27/11/2026).** A paginação tinha 7.845 juntas a prumo (29%): toda fiada começava no mesmo ponto quando a ponta era T, vão ou bloco especial. Agora cada trecho escolhe a arrumação (inteiro ou meio no início, sobra numa ou noutra ponta, compensador se preciso), o bloco T e as pontas de verga se deslocam até 20 cm, e a conferência dá **0 juntas a prumo** em 25.303 juntas.
- **B3 (insumos) feita:** `leitor/leitor/insumos.py` e aba "Insumos (B3)". Cada linha é base medida × coeficiente × (1 + perda), com coeficiente e perda editáveis.
- **B4 (preço) feita:** `leitor/leitor/orcamento.py`, `sinapi.py`, `cub.py` e as abas "Orçamento (B4)", "Preços (B4)" e "Custo por pavimento (B4)".
  - SINAPI baixado da Caixa (SP, 10/2026, sem desoneração) e CUB do SindusCon-SP (R8-N, 10/2026).
  - Blocos, canaletas, argamassa e tela: quantidade da paginação × insumo SINAPI.
  - Mão de obra da alvenaria: pedreiro + servente da composição SINAPI.
  - Graute, armação, encunhamento e revestimentos: composição SINAPI completa.
- **Revisão da paginação (27/11/2026), conferida bloco a bloco por andar:**
  - cruzamento em X: a estrutural passa direto e a vedação para nas faces; paredes de mesmo tipo alternam por fiada. Antes, os dois blocos ocupavam o mesmo lugar;
  - junta a prumo = desencontro menor que 5 cm (antes 2,5 cm). Quando as arrumações simples não resolvem, uma busca exaustiva escolhe a combinação de peças. Resultado: 0 juntas a prumo;
  - corte mínimo de 5 cm. Sobra menor vira enchimento de argamassa (46 por andar), e ponta de verga ou bloco especial a menos de 5 cm de outra peça encosta nela;
  - pilares do subsolo e do térreo com o tamanho desenhado; antes alguns colapsavam para comprimento zero;
  - trecho de parede sobre a porta de correr alinhado com a parede vizinha.
- Correção junto com a B4: 19 trechos curtos do muro inclinado do térreo entravam como fachada (cerca de 22 m² de pintura). Agora são muro.

### Resultado da B4 (SINAPI 10/2026 SP, sem desoneração, sem BDI)

| Grupo | Custo direto |
|---|---|
| Alvenaria estrutural (blocos, argamassa, mão de obra) | R$ 141.442 |
| Alvenaria de vedação (blocos, argamassa, tela, mão de obra, encunhamento) | R$ 83.833 |
| Graute | R$ 31.256 |
| Armação | R$ 27.893 |
| Revestimento interno (fundo preparador, gesso, chapisco + emboço + cerâmica) | R$ 184.438 |
| Revestimento externo (selador + textura: fachada, varandas, platibanda) | R$ 41.825 |
| **Total** | **R$ 510.686** |

- Por pavimento-tipo: cerca de R$ 98 mil (R$ 440/m²). Térreo: R$ 19,9 mil (só revestimentos). Cobertura: R$ 3,9 mil (platibanda).
- R$ 384/m² sobre 1.329 m² acima do subsolo = 15,6% do custo do prédio pelo CUB R8-N (R$ 2.245,68/m² × 1.458 m²).
- Maiores itens:
  - gesso das paredes: R$ 59 mil;
  - bloco 14×19×39: R$ 53 mil;
  - mão de obra da alvenaria estrutural: R$ 43 mil;
  - mão de obra da vedação: R$ 37 mil.
- Os 4.290 blocos para cortes custam R$ 21,0 mil (4% da B4). Modular portas e janelas reduz esse valor.
- Premissas a confirmar (todas editáveis na aba Preços (B4)):
  - fbk 8/8/6/4,5/4,5 MPa do 1º ao 5º pavimento;
  - fgk 20 MPa;
  - cerâmica 33×45 sobre chapisco + emboço de 10 mm.
- Preços derivados (sem item no SINAPI, a cotar):
  - bloco T 14×19×54 = 54/39 do inteiro;
  - canaleta J = canaleta U;
  - canaleta 9×19×39 = 2 × canaleta 9×19×19.
- A pintura projetada não existe no SINAPI: usei a textura acrílica manual como equivalente.

### Resultado da B3 (obra: 1º ao 5º pavimento; fachada e gesso incluem o térreo)

| Insumo | Quantidade (com perdas) |
|---|---|
| Bloco 14×19×39 / meio / 34 / 54 | 10.810 / 1.119 / 378 / 210 un |
| Canaleta J / U (14 cm) | 1.035 / 1.581 un (+ meias) |
| Blocos para cortes/compensadores | 4.290 un (cai muito com portas/janelas moduladas) |
| Bloco 9×19×39 / meio / canaleta | 9.792 / 1.665 / 315 un |
| Argamassa de assentamento (estrutural + vedação) | 5,96 + 3,95 m³ |
| Graute (cintas, vergas/contravergas, pontos verticais, vedação) | 7,83 + 6,56 + 13,76 + 0,99 m³ |
| Aço (Ø10 cintas, Ø8 vergas, Ø10 verticais, Ø6,3 vedação) | 715 + 384 + 753 + 65 kg |
| Telas vedação × estrutural / encunhamento | 792 un / 450 m |
| Fundo preparador / gesso paredes / gesso tetos | 3.871 / 2.775 / 1.096 m² |
| Cerâmica banheiros (até o teto) / cozinhas (1,50 m) | 370 / 343 m² (premissa) |
| Pintura projetada: fachada / varandas / platibanda | 1.060 / 246 / 176 m² |

### Resultado da B2 (por pavimento-tipo; os 5 são iguais)

| | Família 29 | Família 39 |
|---|---|---|
| Peças estruturais (inteiro + meio + especiais + canaletas) | 4.027 (16,5/m²) | 3.046 (12,5/m²) |
| Linhas estruturais que fecham no módulo | 3 de 14 | 8 de 14 |
| Cortes em trecho corrido / junto a vão | 283 / 499 | 242 / 512 |

A família 39 encaixa melhor nesta arquitetura e usa 24% menos peças. Nas duas famílias, a maior parte dos cortes vem da largura e da posição de portas e janelas fora do módulo: compatibilizar isso com o arquiteto elimina a maioria deles.

---

## 0. Resposta curta

**É possível.** O resultado é um modelo de paredes voltado a orçamento ("BIM de alvenaria"), não o BIM de projeto do Revit:
- Comprimentos, áreas e vãos são **medidos** no desenho, com precisão de ±1%, como na Fase 1.
- A contagem de blocos sai de uma **paginação automática estimada**, fiada a fiada. A margem esperada é de ±3% a 5% até existir a paginação executiva do engenheiro.
- Graute e aço saem de **regras paramétricas** (±20% a 30%) até existir o cálculo estrutural.

O modelo não substitui o projeto de alvenaria estrutural. Serve para orçar antes dele e, depois, para conferi-lo.

---

## 1. O que o desenho já mostra

| # | Achado | Evidência | Impacto no orçamento |
|---|---|---|---|
| 1 | **Parte da torre apoia sobre pilares** (garagem sob a projeção do pavimento-tipo) | 6 retângulos isolados de 20×40 cm no subsolo e 5 no térreo, alinhados com a linha "projeção do pavimento-tipo" | Há **estrutura de transição em concreto armado** (pilares, vigas e laje de transição) sob os tipos. A alvenaria estrutural vale do 1º ao 5º pavimento; subsolo e térreo são, ao menos em parte, concreto. Item grande, a confirmar com o engenheiro. |
| 2 | **A arquitetura parece não estar modulada** para bloco | Cotas internas redondas (2,55 / 2,60 / 3,65 / 3,95 / 0,95 / 2,05) que não fecham, descontando a junta, em módulo de 15 nem de 20 cm | A paginação vai exigir ajuste de medidas, compensadores ou cortes. O modelo vai listar parede a parede onde o módulo não fecha (relatório para o arquiteto). |
| 3 | **Paredes desenhadas com 15 cm** (algumas com 10 cm, provavelmente shafts ou divisórias) | Pontas de parede medidas: 65 de 0,15 m e 34 de 0,10 m no tipo | É preciso definir se 15 cm = bloco 14 + gesso, ou só o bloco. Com reboco externo de 2,5 cm, a parede real fica mais grossa que a desenhada. |
| 4 | **Modulação vertical fecha** | Pé-direito 2,60 = 13 fiadas de 20 cm (bloco 19 + junta 1); térreo 2,80 = 14 fiadas; laje de 15 cm nos cortes | Altura das paredes e número de fiadas saem direto. |
| 5 | **O PDF foi exportado do Revit** | Camadas no padrão de exportação do Revit (A-WALL, A-DOOR-FRAM, A-FLOR-OVHD, Q-SPCQ…) | Vale **pedir ao arquiteto o IFC ou o RVT**: as paredes já vêm como objetos e a etapa B1 fica mais rápida e mais exata. |

---

## 2. O modelo de paredes

Cada parede é um objeto com:

| Atributo | Origem |
|---|---|
| Pavimento, eixo (início/fim), comprimento pelo eixo e por face | Linhas de parede (A-WALL): pares de faces paralelas → eixo |
| Espessura desenhada e espessura real (bloco + revestimentos) | Desenho + premissa |
| Altura e nº de fiadas | Pé-direito dos cortes (2,60 → 13; 2,80 → 14) |
| Tipo: **estrutural / vedação / concreto / arrimo** | Regra inicial + revisão manual (abaixo) |
| Ambiente de cada lado (face A, face B); se é fachada | Polígonos da Fase 1 |
| Encontros nas pontas: **L, T, X ou livre** | Grafo de eixos |
| Vãos: posição, largura, altura, peitoril | Vãos da Fase 1 (portas e janelas) |
| Revestimento de cada face (gesso, reboco, cerâmica, fachada) | Tipo do ambiente + premissas/memorial |

**Classificação estrutural × vedação.** Regra inicial, a partir do que você disse ("vedação nas paredes internas"):
- **Estruturais:** fachada, paredes entre apartamentos e núcleo (escada, elevador, hall).
- **Vedação:** divisórias internas dos apartamentos.

Você revisa clicando nas paredes numa página de conferência. O projeto estrutural, quando existir, manda.

**Conferências do modelo:**
- comprimento × altura das paredes bate com as áreas de face já medidas na Fase 1;
- os 5 pavimentos-tipo dão o mesmo resultado;
- planta com os eixos coloridos por tipo.

---

## 3. Paginação automática (estimativa)

Para cada parede, fiada a fiada:

1. **Trecho corrido** entre encontros e vãos → blocos inteiros + meio bloco. Sobra fora de módulo → compensador ou corte (registrado para o relatório de modulação).
2. **Encontros**: fiadas ímpares e pares alternam a amarração.
   - Canto em L: o bloco de uma parede passa sobre a outra.
   - Encontro em T e em X: bloco especial de amarração da família (ex.: 14×19×34 ou 14×19×54 na família 39; 14×19×44 na família 29) ou meio bloco.
   - Estrutural × vedação: sem amarração por bloco, com tela ou grampo a cada 2 fiadas.
3. **Vãos**:
   - Fiadas cortadas pela porta ou janela.
   - **Verga**: canaleta acima do vão, com transpasse de cada lado (premissa: 30 cm).
   - **Contraverga**: canaleta sob a janela, com o mesmo transpasse.
4. **Respaldo**:
   - Estruturais: última fiada de **canaleta U/J = cinta**.
   - Vedação: última fiada com folga para encunhamento (fixação na laje).
5. **Saídas**: contagem por tipo de bloco, por parede e por pavimento; **elevação de cada parede desenhada bloco a bloco (SVG)**, que é a parte visual do "BIM". Exportação IFC para abrir num visualizador BIM fica como opcional.

---

## 4. Insumos e parâmetros de preço

| Item | Unidade | Como calcula | Parâmetro a definir |
|---|---|---|---|
| Bloco estrutural: inteiro, meio, amarração, canaleta U, canaleta J, compensador | un | Paginação | Material (concreto/cerâmico), família (29/39), **fbk por pavimento** |
| Bloco de vedação: inteiro, meio, canaleta | un | Paginação | Largura (9 / 11,5 / 14), material |
| Argamassa de assentamento | m³ | Volume das juntas (horizontal e vertical) | Junta (1 cm), assentamento só nas faces ou total, traço ou industrializada |
| Graute | m³ | Furos preenchidos: cintas, vergas, contravergas, pontos verticais | fgk; regra dos pontos verticais (cantos, encontros, laterais de vão, espaçamento máximo) |
| Aço | kg | Barras em cintas, vergas e pontos verticais | Bitolas, nº de barras, transpasse (até haver cálculo) |
| Tela ou grampo de amarração | un | Encontros estrutural × vedação, a cada 2 fiadas | Tipo e espaçamento |
| Encunhamento (vedação) | m | Comprimento das paredes de vedação | Material |
| Revestimento interno ("massa") | m², m³ | Área de cada face (Fase 1) × espessura | Gesso direto no bloco (espessura) ou chapisco + reboco |
| Revestimento externo (fachada) | m², m³ | Perímetro externo × altura total (inclui platibanda) − vãos | Chapisco + emboço, espessura |
| Cerâmica de parede (áreas molhadas) | m² | Faces dos ambientes molhados × altura | Até o teto ou até 1,50 m (memorial) |
| Mão de obra | h | Composições SINAPI ou produtividade própria | Referência |
| Perdas | % | Por insumo | Percentuais |
| Transição em concreto (subsolo/térreo) | m³, kg, m² | Projeto estrutural (fora deste modelo) | Paramétrico até haver projeto |

**Preço:** SINAPI-SP (mês de referência, desonerado ou não) para composições e mão de obra; **cotação de bloco** com fornecedores da região, porque o preço varia muito com o fbk. CUB como conferência da ordem de grandeza.

---

## 5. Fases

| Fase | Entrega | Pronto quando |
|---|---|---|
| **B1. Modelo de paredes** | Eixos, espessuras, encontros, vãos e classificação; página para revisar a classificação | Comprimentos × altura batem com as faces da Fase 1; tipos idênticos entre si; classificação revisada por você |
| **B2. Paginação e blocos** | Contagem por tipo de bloco, pavimento e parede; elevações SVG; relatório de paredes fora de módulo | 3 ou 4 paredes típicas conferidas à mão contra a elevação gerada |
| **B3. Demais insumos** | Argamassa, graute, aço, telas, encunhamento, revestimentos, com premissas editáveis na planilha | Cada número rastreável até a parede e a premissa que o gerou |
| **B4. Preço** ✅ | Ligação a SINAPI e cotações; custo da alvenaria e dos revestimentos por pavimento; comparação com CUB | Total por m² na faixa esperada, ou diferença explicada |
| *(opcional)* | Exportação IFC | Abre num visualizador BIM gratuito |

A B1 não depende das decisões abaixo e pode começar já.

---

## 6. Decisões e dados necessários

**Respondido (27/11/2026):**
- **Bloco de concreto.** A família (29 ou 39) ainda não está definida: a B2 vai paginar com as duas e comparar o encaixe na arquitetura (cortes, compensadores, nº de blocos) para ajudar a escolher.
- **Vedação em bloco de 9 cm.** Atenção: a arquitetura desenha as divisórias com 15 cm. Com bloco de 9 cm + gesso, a parede fica com cerca de 10 cm, e os ambientes ganham uns 5 cm a cada divisória. Isso pede compatibilização com o arquiteto.
- **Interno:** fundo preparador + gesso direto no bloco.
- **Fachada:** pintura projetada direto no bloco, sem emboço. O bloco da fachada precisa ter padrão de alvenaria aparente (faces e arestas regulares, junta bem acabada).

**Varanda gourmet (revisado em 27/11/2026):**
- O lado externo da varanda tem 1,50 m de **mureta** (traço fino na planta, abaixo do plano de corte) com gradil e corrimão. Os 0,60 m restantes são parede inteira, atrás do tanque.
- Pela Fachada Frontal (rua Ernesto): mureta até 0,60 m (3 fiadas); abertura de 1,50 m até 2,20 m; verga em 2,20–2,40; respaldo em cima.
- O modelo trata a varanda como vão (mureta + abertura), com cinta no topo da mureta e verga, e desconta a abertura das áreas de parede.
- **A confirmar:** a planta indica "guarda-corpo h=1,30 m", mas na fachada o corrimão aparece a cerca de 1,10 m. A altura da mureta (0,60) e o topo da abertura (2,20) são premissas editáveis.

**Pendente:**

1. **Bloco:** concreto ou cerâmico? Família 29 (módulo 15) ou 39 (módulo 20)? Largura do bloco de vedação?
2. **fbk por pavimento:** do engenheiro. Se ainda não houver, uso premissa por faixa (maior embaixo, menor em cima).
3. **Revestimentos:** interno com gesso direto no bloco (qual espessura?) ou reboco? Espessura do emboço externo?
4. **Áreas molhadas:** cerâmica até o teto ou até 1,50 m?
5. **Transição:** confirmar a estrutura de concreto sob a torre (pilares 20×40 no subsolo e térreo).
6. **Pedir ao arquiteto:** o IFC/RVT e, se já existir, o projeto de modulação ou de alvenaria estrutural.
