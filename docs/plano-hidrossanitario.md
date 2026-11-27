# Plano — Água fria e esgoto no modelo (Reserva Paulicéia)

> **Objetivo:** levar os projetos de água fria (pranchas 16 a 23) e esgoto (24 a 30) para o mesmo modelo do arquitetônico. Servem para três coisas:
> - imagens de marketing no 3D;
> - quantitativo trecho a trecho, conferido com as tabelas do projetista;
> - preço SINAPI.
>
> Inclui também uma auditoria de interferências com a alvenaria.

## 1. O que os PDFs têm (reconhecimento, 27/11/2026)

| | Água fria (8 pranchas) | Esgoto (7 pranchas) |
|---|---|---|
| Plantas | subsolo, térreo; 1º ao 5º e cobertura (1:50) | idem |
| Isométricos | 1 por prumada: tipos A, B, C, D × Banheiro, Cozinha/Á.S., V.Gourmet; barrilete (2 vistas); subsolo/térreo | idem, com níveis dos pavimentos (térreo 0,10; 1º 3,05 … cobertura 16,80) |
| Rótulos | cada trecho: "DN25 mm / 0,67m"; cada conexão: código da tabela num círculo; alturas cotadas | idem |
| Colunas | AF-01 a AF-13, AL (alimentação), EXTRAV. (extravasor), com diâmetro por andar | tubos de queda, ventilação, caixas |
| Tabelas do projetista | conexões (17 itens), registros e válvulas (8), tubos por DN | conexões (22), caixas e ralos, caixas de gordura/inspeção, tubos por DN |

**Diferenças em relação ao arquitetônico:**
- Não há camadas do CAD (só "Impressão"). Os tubos são polígonos pretos preenchidos e as paredes, traço fino.
- A leitura usa espessura e preenchimento, não a camada.
- Os mesmos tubos aparecem em mais de uma vista (planta, isométrico, barrilete em 2 vistas). Por isso o quantitativo não pode somar rótulos: precisa reconstruir a rede, cada tubo uma vez.

## 2. Método

1. **Rede por isométrico.**
   - Centro dos tubos (formas grossas), nós (conexões) e trechos.
   - Cada trecho casado com o rótulo "DN / comprimento" e cada nó com o código da conexão.
   - Os três eixos do isométrico saem das direções dos próprios trechos. O comprimento verdadeiro vem do rótulo, e a escala de cada eixo é conferida.
2. **Posição no prédio.**
   - A planta de cada pavimento é registrada sobre o modelo arquitetônico pelas paredes (mesma base de desenho).
   - A coluna (ponto do balão "AF-xx") dá o x, y.
   - Os níveis dos pavimentos (cortes e isométricos de esgoto) dão o z.
3. **3D.**
   - Tubos como cilindros por diâmetro; conexões, registros e peças.
   - Filtro "Água fria" / "Esgoto" e clique com DN, comprimento, trecho e código.
4. **Quantitativo.**
   - Tubos por DN, conexões e registros por código, por pavimento e prumada.
   - Conferido trecho a trecho com os rótulos e no total com as tabelas do projetista.
5. **Auditoria.**
   - Rótulo × geometria em cada trecho.
   - Total × tabela do projetista.
   - A mesma coluna na mesma posição em todos os andares.
   - Pontos de consumo dentro do ambiente certo.
   - Tubo dentro de parede ou shaft; tubo horizontal embutido em parede estrutural (proibido na alvenaria estrutural sem previsão no projeto).
   - Cruzamento com vergas, cintas e pontos de graute.
6. **Preço.** Composições SINAPI de tubos, conexões e registros por DN numa aba "Instalações (B4)", com rateio no 3D.

## 3. Etapas

| Etapa | Entrega | Situação |
|---|---|---|
| H1a | Rede de água fria das prumadas dos apartamentos (isométricos) | **Feito** |
| H1b | Água fria no 3D (modo "Instalações") | **Feito** (prumadas, barrilete, térreo, subsolo e colunas do prédio) |
| H1c | Auditoria de interferências + preço SINAPI | **Feito**: 0 conflitos; R$ 27.555,36 (SINAPI 10/2026, custo direto; após a auditoria da seção 9) |
| H1d | Barrilete, alimentação (AL), extravasor, térreo e subsolo | **Feito** no quantitativo. Posição no 3D: horizontais pela planta (altura por premissa); 43 m de verticais do barrilete/térreo só no quantitativo |
| H2 | Esgoto: quantitativo, 3D, auditoria e preço | **Feito** (seção 6) |

## 4. Como ficou a leitura (H1a/H1b, 27/11/2026)

- **12 isométricos de prumada** (pranchas 20 e 21), um por coluna:

  | Tipo (unidade) | Banheiro | Cozinha/Á.S. | V. Gourmet |
  |---|---|---|---|
  | A (Unidade 3) | AF-01 | AF-03 | AF-02 |
  | B (Unidade 4) | AF-04 | AF-06 | AF-05 |
  | C (Unidade 1) | AF-07 | AF-09 (desce ao térreo) | AF-08 |
  | D (Unidade 2) | AF-10 | AF-12 | AF-11 |

- **O isométrico está em escala na vertical.**
  - As cotas de altura dos pontos (0,20; 0,60; 1,40…) dão a escala de cada vista: 125,8 a 137,4 pt/m, com variação abaixo de 0,1% dentro da vista.
  - O tique de baixo de cada cota é o piso. Os 5 pisos de cada vista caem nos níveis da arquitetura (1º = 2,95 m, depois +2,75) com desvio máximo de 2,6 mm.
- **O eixo horizontal não está exatamente em escala.**
  - Varia de 0,95 a 1,07 conforme a vista (projeção oblíqua). É calibrado pelo tubo desenhado na planta.
  - Nos banheiros, essa calibração bate com a feita pelos rótulos (diferença máxima de 0,8%).
  - Resultado: o ramal do banheiro tem 1,72 m nos 4 tipos, e o da cozinha 2,37 a 2,42 m.
- **Plantas** (pranchas 16 e 17): registradas sobre as paredes da arquitetura.
  - Escala de 0,9998 a 1,0004, com erro médio de 3 a 9 mm.
  - As 15 colunas (AF-01 a AF-13, AL e extravasor) ficam no prumo nos 5 andares, com até 15 mm de diferença entre balões.
- **Rótulos.**
  - 627 rótulos DN/comprimento, todos ligados a um tubo.
  - 51 são repetidos: o trecho da coluna entre dois andares é rotulado em cada andar e conta uma vez.
  - Nas cozinhas o projeto deixa alguns tubos curtos sem rótulo em alguns andares (0,54 m no 1º do Tipo A; 0,18 m em andares do B). Eles entram com o DN e o comprimento do mesmo tubo nos outros andares, marcados como "inferido".
  - Depois disso, as cozinhas A, B e D diferem em 6 cm no total.
- **Auditoria contra a alvenaria (1º ao 5º).**
  - Os 504 trechos (173 horizontais e 331 verticais) passam em paredes de **vedação**: banheiro/quarto 1 e cozinha/varanda gourmet.
  - Nenhum tubo horizontal está em parede estrutural, nenhum vertical cai em ponto de graute e nenhum cruza verga ou contraverga.
  - O projeto hidráulico está compatível com a alvenaria estrutural.

### Quantitativo do prédio × tabela do projetista

| Tubo PVC soldável | Prumadas dos aptos | Barrilete (cobertura) | Térreo e subsolo | Colunas do prédio | **Modelo** | **Tabela** | Diferença |
|---|---|---|---|---|---|---|---|
| DN20 | 100,96 | — | 8,06 | — | **109,02** | 113,52 | −4,50 |
| DN25 | 205,83 | 21,83 | 15,56 | 14,57 (AF-13) | **257,79** | 257,25 | +0,54 |
| DN32 | 24,04 | 50,94 | 24,72 | 43,45 (AL 22,58 + extravasor 20,87) | **143,15** | 145,66 | −2,51 |
| DN40 | — | 5,45 | — | — | **5,45** | 5,45 | 0 |
| DN50 | — | 23,90 | — | — | **23,90** | 23,23 | +0,67 |
| **Total** | 330,83 | 102,12 | 48,34 | 58,02 | **539,31** | 545,11 | **−1,1%** |

**Regra "cada tubo uma vez", usada no barrilete, térreo e subsolo:**
- Horizontais: pela planta. O rótulo repetido no mesmo tubo conta uma vez, inclusive quando o tubo aparece quebrado em pedaços alinhados.
- Verticais: pela vista (planta ou isométrico) que mais os mostra.
- Horizontais que só o isométrico rotula: entram no que passa do que a planta já tem.
- Colunas que atravessam o prédio: uma vez.

**Antes de chegar nessa regra:**
- Somar todas as vistas dava 626,7 m, porque cada tubo vertical longo aparecia em 3 ou 4 vistas e pedaços do mesmo tubo levavam o mesmo rótulo.
- O DN40 do barrilete (4,13 + 1,32 = 5,45 m) confirma a regra: fecha exato com a tabela.

**Conexões e registros:**
- 15 dos 25 códigos batem exatamente com a tabela, entre eles:
  - registros de chuveiro e de gaveta;
  - registros de esfera de 25 e 50 mm;
  - tês de 40 e 50 mm;
  - buchas de 32×25, 40×32 e 50×40.
- Os outros diferem de 1 a 6 peças (joelho 32 mm: −6; tê 32 mm: −3). São conexões das verticais do barrilete e do salão que só aparecem nos isométricos.

### Preço (SINAPI 10/2026 SP, sem desoneração, custo direto)

| Grupo | Custo |
|---|---|
| Tubos (por DN e tipo de trecho: prumada, ramal de distribuição, ramal/sub-ramal) | R$ 10.497,36 |
| Conexões | R$ 9.906,13 |
| Registros e hidrômetro | R$ 7.151,87 |
| **Total** | **R$ 27.555,36** |

**Premissas do preço:**
- **Tipo de trecho.** O SINAPI tem composição por tipo de trecho, porque a produtividade muda: o DN25 custa R$ 6,80/m na prumada e R$ 30,74/m no sub-ramal. No modelo:
  - coluna vertical = prumada;
  - barrilete, alimentação, térreo e subsolo = ramal de distribuição;
  - dentro do apartamento = ramal/sub-ramal.
- **Registros:**
  - gaveta cromado: latão com canopla cromada, porque não há de PVC no SINAPI;
  - chuveiro PVC: registro de pressão PVC soldável.
- **Joelho 20 × 1/2" com bucha de latão** (código 09, 140 peças): não tem composição no SINAPI. O preço é derivado da composição do 25 × 1/2" (90373), trocando o insumo 20147 pelo 3515.
- **Hidrômetro DN 1"**: em geral é fornecido pela concessionária. Conferir.

## 5. Pontos para o projetista hidráulico

1. **Rótulos ausentes nas cozinhas.** Alguns tubos curtos estão desenhados mas sem rótulo em alguns andares (0,06 a 0,54 m). Completar os rótulos nos isométricos das cozinhas.
2. **Rótulo repetido.** O trecho da coluna entre andares aparece rotulado duas vezes. Não é erro de quantidade se a tabela contar o tubo uma vez, mas confunde quem soma pelo desenho.
3. **Tabela "Tubos Rígidos".** O modelo fecha em −1,1% (539,31 × 545,11 m), e o DN40 bate exato.
   - DN20 (−4,5 m) e DN32 (−2,5 m): provavelmente verticais do salão de festas e do barrilete que não têm rótulo em nenhuma vista.
   - Pedir ao projetista o relatório por trecho, se houver.
4. **Bucha de redução "250x40 mm"** (código 04) na tabela de conexões: provável erro de digitação (50x40 mm).
5. **Rótulos repetidos também nas plantas.**
   - No barrilete, o "DN25 5,09m" aparece 11 vezes, para 4 tubos.
   - O "DN40 4,13m" aparece 3 vezes, para 1 tubo.
   - A alimentação e o extravasor aparecem rotulados em várias plantas e vistas.
6. **Ponto de consumo sem etiqueta.**
   - No Tipo B, banheiro do 4º andar, o vaso não tem o código 09. A peça e o tubo estão desenhados, e os outros 4 andares têm a etiqueta.
   - O modelo conta essa peça. A tabela de conexões bate com a contagem das etiquetas, então provavelmente também está com uma peça a menos.


## 6. Esgoto sanitário (H2, 27/11/2026)

**O PDF (pranchas 24 a 30):**
- plantas do subsolo, do térreo e do 1º ao 5º;
- 12 isométricos de prumada e 2 de coletores (térreo e subsolo);
- o 3D do prédio.

Os isométricos são perspectivas de verdade: os ramais correm em duas direções sob o piso, e a horizontal não está em escala. Por isso:

### Como foi lido

- **Quantitativo** (`esgoto.py`): pelos rótulos "DNxx mm / L,LLm" dos isométricos, cada tubo uma vez. O rótulo repetido no mesmo tubo, ou em pedaços alinhados do mesmo tubo, conta uma vez (163 rótulos repetidos).
- **Parte de baixo de cada isométrico de apartamento.** O tubo de queda até o coletor e os coletores são os mesmos das vistas "Coletores" e das plantas do térreo/subsolo. Um trecho entra no grupo dos coletores, uma vez, quando:
  - está abaixo do último tubo que se repete andar a andar; ou
  - é próprio de um tipo (não aparece no mesmo cômodo dos outros tipos) e a planta ou a vista de coletores também o mostra.
- **Coletores.** A planta do térreo/subsolo rotula cada coletor uma vez e vale para o que rotula. Os isométricos só acrescentam o DN/comprimento que a planta não tem.
- **Conexões.** Pelos isométricos dos apartamentos, que já desenham o trecho até os coletores. As vistas de coletores repetem as mesmas peças; somá-las dobrava as curvas.
- **3D:**
  - os ramais vêm da planta de cada andar, que desenha o tubo com o diâmetro real (o DN sai da espessura do traço: 40 ≈ 2,2 pt, 50 ≈ 3,0, 75 ≈ 4,4, 100 ≈ 6,0);
  - tubos de queda (TQ-01 a TQ-16) e ventilações (V-xx) pelos balões;
  - coletores pela planta;
  - altura por premissa: ramal 25 cm sob a laje e coletor sob a laje do térreo.

### Resultado × tabela do projetista

| Tubo PVC esgoto série normal | Apartamentos | Coletores | **Modelo** | **Tabela** | Diferença |
|---|---|---|---|---|---|
| DN40 | 118,40 | 1,65 | **120,05** | 125,47 | −5,42 |
| DN50 | 252,42 | 24,19 | **276,61** | 280,12 | −3,51 |
| DN75 | 126,21 | 49,20 | **175,41** | 176,20 | −0,79 |
| DN100 | 73,88 | 79,72 | **153,60** | 155,45 | −1,85 |
| DN150 | — | 11,32 | **11,32** | 11,32 | 0 |
| **Total** | 570,91 | 166,08 | **736,99** | 748,56 | **−1,5%** |

Valores após a auditoria (seção 9). Antes dela o modelo dava 751,83 m (+0,4%), mas com dois erros que se compensavam em parte: +10,64 m de DN75 e +7,62 m de DN100 contados duas vezes.

- **Conexões:** 10 dos 22 códigos batem exatamente com a tabela, e os outros diferem de 1 a 4 peças. No total, 1.028 conexões contra 1.057.
- **Banheiros:** 50,00 m nos 4 tipos.
- **Varandas gourmet:** iguais nos 4 tipos (32,44 m).
- **Cozinhas:** 57 a 64 m. A do tipo C atende também o térreo.

### Auditoria

- **Prumo:** os 16 tubos de queda e as 12 ventilações ficam no prumo nos 5 andares. A exceção é um balão no 1º andar de TQ-03, TQ-06 e TQ-07, que aponta para outro ponto; nesses casos vale a mediana dos andares.
- **Nenhuma coluna dentro de parede onde não cabe.**
- **Tubos de queda DN75/100 junto à parede:** os 12 ficam no ambiente (banheiro, cozinha e varanda), a 4–9 cm da face da parede. **Prever shaft ou enchimento.** É um item de orçamento a definir (fechamento em drywall ou alvenaria).
- **TQ DN50 das cozinhas** (TQ-03, 07, 11 e 15): ficam dentro de paredes de vedação de 15 cm, o que é compatível.

### Preço (SINAPI 10/2026, sem desoneração, custo direto)

| Grupo | Custo |
|---|---|
| Tubos (ramal de descarga/esgoto, tubo de queda/ventilação, subcoletor) | R$ 22.108,24 |
| Conexões | R$ 26.467,29 |
| Caixas e ralos (quantidade da tabela do projetista) | R$ 11.517,94 |
| **Total esgoto** | **R$ 60.093,47** |
| **Água fria + esgoto** | **R$ 87.648,83** |

**Premissas do preço:**
- **Adaptador de saída de vaso** (código 01): sem composição no SINAPI; usado o preço do joelho 90° DN100 do ramal.
- **Junção 100×50 e tê 75×50:** sem composição no SINAPI; usada a peça igual de bitola maior (100×100 e 75×75), a favor da segurança.
- **Caixas sifonadas, de gordura e de inspeção, prolongamentos e ralos:** quantidade da tabela do projetista. As caixas sifonadas e os ralos das plantas batem exatamente com a tabela (seção 9).
- **Caixa de inspeção e prolongamentos:** só material.
- **Prolongador DN300:** sem preço SINAPI.

### Pontos para o projetista (esgoto)

1. **Rótulos faltando em alguns andares:** 11 peças curtas (0,12 a 0,23 m) estão desenhadas em todos os andares, mas rotuladas só em alguns (cozinhas A a D e banheiro D). O modelo conta essas peças; completar os rótulos no desenho.
2. **Shaft dos tubos de queda:** os TQ DN75/100 ficam no ambiente, junto à parede. Indicar o fechamento (shaft/enchimento) no arquitetônico.
3. **Rótulos repetidos e coletores desenhados em várias vistas:** como na água fria, somar o desenho dá mais que a tabela.
4. **Declividade dos ramais abaixo da NBR 8160.**
   - A norma recomenda no mínimo 2% para DN até 75 e 1% a partir do DN100 (item 4.2.3.2).
   - Nos isométricos, 116 dos 216 rótulos "i=" com DN identificado ficam abaixo disso:

     | DN | Declividade | Rótulos |
     |---|---|---|
     | DN40 | 1,2% | 17 |
     | DN40 | 1,5% | 37 |
     | DN50 | 1,4% | 2 |
     | DN50 | 1,5% | 31 |
     | DN75 | 1,1% | 1 |
     | DN75 | 1,5% | 28 |

   - O DN100 está todo em 1,1% ou mais.
   - Confirmar com o projetista. Se for preciso subir a declividade, muda a altura dos ramais sob a laje e pode mudar o forro.


## 7. Detalhe das peças no 3D (27/11/2026)

**Água fria:**
- O tubo passa contínuo pelo corpo do registro, da luva e do tê. No desenho o traço é interrompido pela peça (até ~22 cm). Antes ficava um vão no 3D.
- Cada peça aparece pelo tipo da tabela do projetista:

  | Peça | No 3D |
  |---|---|
  | Joelho e tê | nó escuro |
  | Bucha e luva | nó menor |
  | Ponto de consumo (joelho com bucha de latão) | latão |
  | Registro e hidrômetro | corpo cromado com volante vermelho |

- Os tês que ligam o ramal à coluna (até 20 cm do eixo) contam como peça da prumada no preço.

**Esgoto:**
- Os ramais da planta são emendados através das conexões (até 30 cm).
- Onde dois ramais se encontram, entra uma junção ou um joelho.
- **Ponta livre do ramal:** vira subida até o aparelho, por premissa:
  - DN100: até o piso (vaso);
  - DN40/50: até 0,50 m (lavatório, pia, tanque).
- **Ponta junto do tubo de queda ou da ventilação:** vira ligação horizontal até a coluna, com a junção.
- **Caixas sifonadas e ralos:** pelos símbolos da planta, com a subida do ramal até a caixa. Por andar: 8 quadradas (caixa sifonada 100 e ralo, nos banheiros) e 8 redondas (caixa sifonada 150, cozinha e área de serviço), desenhadas como dois meios-círculos. Mais 2 quadradas no térreo.


## 8. Costura do 3D e caminho para um BIM exato (27/11/2026)

O 3D é reconstruído dos desenhos 2D, então sobravam pontas de tubo soltas:
- a altura do barrilete, do térreo e dos coletores é premissa;
- parte dos verticais só existe no isométrico, sem posição;
- os ramais da planta do esgoto são interrompidos pelas conexões.

A etapa `rede3d.costurar` (só visual) faz o seguinte:
1. Junta as pontas a até 5 cm.
2. Liga cada ponta solta ao tubo mais perto do mesmo sistema, com percurso ortogonal (até 60 cm na horizontal).
3. Não mexe nos pontos de consumo, nas subidas aos aparelhos nem no topo das ventilações.

| | Pontas soltas antes | Depois |
|---|---|---|
| Água fria | 238 | 5 |
| Esgoto (fora as subidas aos aparelhos) | ~90 | 9 |

As ligações aparecem como "Ligação do 3D" no clique e não entram no quantitativo nem no preço.

**Para um 3D exato (BIM de verdade):**
- Pedir ao projetista hidráulico o arquivo **IFC** do modelo (ou o arquivo nativo). As pranchas têm cara de software BIM de instalações, com tabelas de materiais geradas e vista "3D - Prédio".
- No IFC, cada tubo e conexão vem com posição 3D, diâmetro e ligação real.
- O leitor passaria a importar o IFC (biblioteca `ifcopenshell`) e manteria a conferência com as pranchas.


## 9. Auditoria da água fria e do esgoto (27/11/2026)

Antes de passar ao projeto de incêndio, as duas frentes foram auditadas por um caminho independente do leitor. O auditor relê o PDF e o `obra.json` e confere com outras regras:
- rótulos: livro-razão;
- repetição andar a andar;
- pontos de consumo;
- diâmetros: balão × isométrico;
- caixas × tabela;
- declividades;
- aritmética do preço.

O que deu erro de leitura foi corrigido no leitor. O que é do desenho virou ponto para o projetista. As verificações ficaram permanentes na aba "Conferência": são 67, com 66 ok e 1 "conferir" (declividade, que é ponto de projeto).

### Erros de leitura encontrados e corrigidos

| # | Frente | Erro | Efeito | Correção |
|---|---|---|---|---|
| 1 | Água fria | A área reservada para a tabela de materiais era o texto mais uma margem de 70 pt, e engolia o código "09" do lavatório e o "05" do Tipo A no 1º andar, encostados na tabela. | −1 ponto de consumo, −1 joelho | A tabela agora é a moldura desenhada (traços que encostam no texto). |
| 2 | Água fria | No Tipo B, banheiro do 4º, o vaso não tem a etiqueta 09 no desenho. | −1 ponto de consumo | Andar com menos pontos que os outros, ponto no mesmo lugar nos outros andares e tubo chegando lá: conta como "inferido". |
| 3 | Esgoto | O segundo rótulo do tubo de queda entre o 4º e o 3º andar caiu num tracinho de conexão, e contou como outro tubo. | +2,54 m de DN100 em cada banheiro A, B e C (+7,62 m) | Rótulo num tracinho bem mais curto que ele, encostado no tubo já rotulado igual, é repetição. |
| 4 | Esgoto | O último trecho do tubo de queda do banheiro C tinha o rótulo 2 pt acima do corte entre "apartamento" e "coletores". Com isso, o trecho igual do D era descontado como se fosse o mesmo tubo. | trecho do C no lugar errado; o do D sumia | O corte usa o meio do tubo, não a posição do rótulo. |
| 5 | Esgoto | As descidas DN75 de 5,24 m e 5,40 m atravessam o térreo e o subsolo e são rotuladas nas duas plantas. Eram somadas. | +10,64 m de DN75 | Vertical mais longo que um pé-direito (> 3,1 m) conta pela planta que mais o mostra. |
| 6 | Esgoto | 11 peças curtas desenhadas em todos os andares e rotuladas só em alguns. | −2,0 m (DN40/50) | Mesmo traço, transladado do passo entre andares e sem rótulo: conta com o rótulo do andar vizinho ("inferido"). Conferido no PDF, andar a andar. |
| 7 | Esgoto (3D) | As caixas sifonadas redondas (150 mm) são desenhadas como dois meios-círculos e não eram lidas. | 3D com 8 caixas por andar em vez de 16 | Leitura dos meios-círculos. Agora: 42 quadradas e 40 redondas, igual à tabela. |

**Efeito no total:**
- **Água fria:** 539,31 m (sem mudança). Conexões e registros: 724 contra 736 da tabela. **R$ 27.555,36** (+R$ 46,68).
- **Esgoto:** 736,99 m contra 748,56 m da tabela (−1,5%). Antes eram 751,83 m (+0,4%), com +18 m de dupla contagem compensados em parte pelas peças sem rótulo. Agora todos os DN ficam um pouco abaixo da tabela, como na água fria. **R$ 60.093,47** (−R$ 534,77).
- **Instalações:** **R$ 87.648,83**.

### O que foi conferido e fechou

**Água fria:**
- **Rótulos:** 587 nas pranchas dos apartamentos = 514 trechos + 51 repetidos + 22 do topo (barrilete). Mais 3 tubos sem rótulo, inferidos. Nenhum rótulo sem comprimento.
- **Ramais (fora da coluna):** iguais no 2º, 3º e 4º andar nos 12 isométricos.
- **A coluna muda de andar para andar** (redução de diâmetro, bucha), e isso é do projeto.
- **Pontos de consumo:** 140, ou 7 por apartamento × 20 (banheiro 3, cozinha/área de serviço 3, varanda 1).
- **Alturas dos pontos** coerentes com as cotas, nos 4 tipos:
  - vaso: 0,20 m;
  - lavatório: 0,60 m;
  - chuveiro: 2,06 m;
  - cozinha: 0,9 a 1,0 m.
- **Diâmetro das colunas:** o balão de cada andar na planta é igual ao trecho da coluna no isométrico, nas 13 colunas e 5 andares.
- **Preço:** quantidade × preço = custo nas 41 linhas. Metros orçados = metros do modelo (539,31). Peças orçadas = peças do modelo (724).

**Esgoto:**
- **Rótulos:** 771 = 606 tubos + 165 repetidos, em 14 isométricos. Mais 11 peças inferidas.
- **Banheiros:** 50,00 m nos 4 tipos (antes A, B e C davam 52,54 m, e o D 50,00 m).
- **Varandas gourmet:** 32,44 m nos 4 tipos.
- **Cozinhas:** B 58,36 m e D 57,84 m.
  - A tem 60,00 m, porque o projeto desvia o TQ-02 sob a laje do 1º andar (DN75 0,86 + 0,82 m).
  - C tem 64,95 m, porque atende também o térreo.
- **Diâmetros dos tubos de queda e ventilações:** o balão da planta é igual ao isométrico nas 12 vistas:
  - banheiro: TQ DN100 e V DN50;
  - cozinha e varanda: TQ DN75/50 e V DN50.
- **Caixas sifonadas e ralos:** contados nas plantas e iguais à tabela.
  - Quadradas (caixa sifonada 100 e ralo): 8 por andar + 2 no térreo = 42, igual a 22 + 20 da tabela.
  - Redondas (caixa sifonada 150): 8 por andar = 40, igual à tabela.
- **Preço:** quantidade × preço = custo nas 41 linhas e soma dos grupos = total. Metros orçados = metros do modelo (736,99). Conexões orçadas = conexões do modelo (1.028).
  - As caixas são orçadas pela tabela: 176 de 184 peças. O prolongador DN300 (8) não tem preço no SINAPI.

### O que continua diferente da tabela (e por quê)

- **Água fria, conexões (−12 no total).** As diferenças estão no barrilete e no térreo/subsolo:
  - joelho 32 mm: −6;
  - tê 32 mm: −3;
  - bucha 25×20: −2.

  Ali a planta e o isométrico etiquetam cada um só parte das peças. Tomar o maior dos dois por código fecha o joelho e o tê de 32, mas passa do número em outros 4 códigos (joelho 25 mm, tê de redução 32×25, registro de esfera 32 e joelho com bucha 25×½"). Por isso a regra não foi adotada.
- **Esgoto, tubos (−1,5%) e conexões (1.028 × 1.057).** O que falta são, provavelmente, peças curtas sem rótulo em nenhum andar, que a inferência não alcança porque ela exige o rótulo em pelo menos 2 andares.
- **Preço pela tabela.** Se a preferência for orçar pelo maior entre o modelo e a tabela do projetista (por código e DN), a diferença é pequena. Estimativa com os preços unitários do orçamento:

  | Frente | Tubos | Conexões | Total | Sobre o custo da frente |
  |---|---|---|---|---|
  | Água fria | R$ 80 a 160 | R$ 310 | R$ 390 a 470 | ~1,5% |
  | Esgoto | R$ 320 a 440 | R$ 760 | R$ 1.080 a 1.200 | ~2% |
