# Plano — "BIM de alvenaria" para orçamento (Reserva Paulicéia)

> **Objetivo:** transformar as paredes do projeto num modelo paramétrico (cada parede um objeto, com espessura, altura, encontros e vãos) e, a partir dele, contar **bloco inteiro, meio bloco, blocos de amarração, canaletas U/J e compensadores**, mais argamassa, graute, aço, telas e revestimentos ("massa"). A planilha final deve ter **todos os parâmetros de precificação** editáveis.

Status: **B1 (modelo de paredes) feita** em 27/11/2026: `leitor/leitor/paredes.py`, aba Paredes da planilha e página `paredes.html`. Próximo: B2 (paginação).

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
| **B4. Preço** | Ligação a SINAPI e cotações; custo da alvenaria e dos revestimentos por pavimento; comparação com CUB | Total por m² na faixa esperada, ou diferença explicada |
| *(opcional)* | Exportação IFC | Abre num visualizador BIM gratuito |

A B1 não depende das decisões abaixo e pode começar já.

---

## 6. Decisões e dados necessários

**Respondido (27/11/2026):**
- **Bloco de concreto.** A família (29 ou 39) ainda não está definida: a B2 vai paginar com as duas e comparar o encaixe na arquitetura (cortes, compensadores, nº de blocos) para ajudar a escolher.
- **Vedação em bloco de 9 cm.** Atenção: a arquitetura desenha as divisórias com 15 cm. Com bloco de 9 cm + gesso, a parede fica com cerca de 10 cm, e os ambientes ganham uns 5 cm a cada divisória. Isso pede compatibilização com o arquiteto.
- **Interno:** fundo preparador + gesso direto no bloco.
- **Fachada:** pintura projetada direto no bloco, sem emboço. O bloco da fachada precisa ter padrão de alvenaria aparente (faces e arestas regulares, junta bem acabada).

**Pendente:**

1. **Bloco:** concreto ou cerâmico? Família 29 (módulo 15) ou 39 (módulo 20)? Largura do bloco de vedação?
2. **fbk por pavimento:** do engenheiro. Se ainda não houver, uso premissa por faixa (maior embaixo, menor em cima).
3. **Revestimentos:** interno com gesso direto no bloco (qual espessura?) ou reboco? Espessura do emboço externo?
4. **Áreas molhadas:** cerâmica até o teto ou até 1,50 m?
5. **Transição:** confirmar a estrutura de concreto sob a torre (pilares 20×40 no subsolo e térreo).
6. **Pedir ao arquiteto:** o IFC/RVT e, se já existir, o projeto de modulação ou de alvenaria estrutural.
