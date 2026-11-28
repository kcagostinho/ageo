# Instalações elétricas no modelo (Reserva Paulicéia)

> **Objetivo:** levar o projeto elétrico (pranchas 08 a 15) para o mesmo modelo do arquitetônico, como foi feito com a água fria e o esgoto:
> - 3D com tudo ligado (eletroduto → descida → caixa; prumadas de caixa a caixa; nada solto);
> - quantitativo conferido com a lista de materiais e com os quadros de carga do projetista;
> - preço SINAPI.

Atualizado em 28/11/2026.

## 1. O que o PDF tem

| Folha | Conteúdo |
|---|---|
| 1 a 5 | Planta do 5º, 4º, 3º, 2º e 1º pavimentos; quadros de carga e de demanda dos 4 QDs do andar; lista de materiais; legenda |
| 6 | Térreo: caixas de medição QM1–QM22, entrada de serviço AL1, alimentadores, QD21 (salão) e QD22 (área comum); lista de materiais; legenda |
| 7 | Subsolo (garagem): iluminação, tomadas, portão; lista de materiais |
| 8 | Quadros de carga do QD21, QD22, QM1–QM22 e AL1; quadros de demanda; diagrama unifilar |

**Como o desenho é feito:**
- Não há camadas e tudo é preto. A leitura separa pela espessura do traço:
  - 0,84 pt: eletrodutos, setas e bolinhas das prumadas;
  - 0,57 pt: símbolos e tracinhos da fiação;
  - 0,15 pt: arquitetura de fundo.
- Os alimentadores são pontilhados: cada pontinho é um traço de comprimento zero.

## 2. Método

1. **Pontos** pela forma do símbolo, conferida com a legenda de cada folha:
   - caixinha de 5,8 pt na parede + haste + o que está na ponta da haste:
     - triângulo vazado: tomada universal a 0,30 m;
     - triângulo meio cheio: tomada 10 A a 1,10 m;
     - triângulo cheio: tomada 20 A ou ponto a 2,20 m ("CHG" é o chuveiro);
     - círculo de 13,5 pt: interruptor (hachurado = paralelo; com traço = 2 teclas; dois círculos = 2 simples + 1 paralelo);
     - meia-lua: arandela;
     - círculo grande com "M/1F": tomada 20 A do portão a 0,30 m;
   - círculo de 32 pt: luminária de teto ("ELM" com 5.550 W: ponto de força do elevador a 0,30 m);
   - meia-lua com placa: sensor de presença a 2,20 m;
   - retângulo meio cheio: quadro (QD a 1,50 m); ampulheta: caixa de medição (QM a 1,60 m);
   - quadrado com X: caixa de passagem (CXnn), com bolinha quando é prumada.
2. **Textos de cada ponto:** circuito, potência, letra de comando e rótulo. O casamento é global, pelo mais perto: duas tomadas lado a lado não disputam o mesmo número.
3. **Eletrodutos cheios** ligados ponta a ponta às caixas. A ponta pode chegar na caixinha ou no próprio símbolo.
4. **Alimentadores pontilhados** lidos na ordem em que o PDF desenha os pontinhos.
   - A ordem segue o traçado, então atravessa os cruzamentos do térreo sem trocar de linha.
   - A sequência é partida onde vira de repente, e duas pontas só se emendam se ninguém mais estiver ali e fora de um quadro ou caixa.
5. **Bitola** pelo rótulo ø, casado um a um com os eletrodutos (atribuição ótima).
   - Custo: o rótulo fica a 8,3 pt do seu eletroduto, pendurado embaixo dele e escrito paralelo.
   - Sem rótulo: 3/4" no eletroduto cheio e 1.1/2" no pontilhado.
6. **Registro** de cada planta sobre a arquitetura pelas paredes (escala 0,4999 a 0,5001; resíduo de 1,6 a 5,5 mm).
   - As prumadas têm de ficar uma sobre a outra. No subsolo, a hachura do piso do estacionamento prendeu o registro 3,08 m fora; as 5 prumadas concordaram e corrigiram a posição.
7. **Prédio:**
   - prumadas pelas caixas de passagem de mesmo nome (25 prumadas, desvio máximo de 3 mm entre andares);
   - caminho de cada alimentador: QM → caixa da prumada → QD;
   - quadro de cada ponto pela rede. As áreas comuns atravessam as prumadas até o QD22.
8. **Tabelas:** lista de materiais de cada folha e quadros de carga (circuitos, potências por tipo, seção, disjuntor, fases).
9. **3D:**
   - eletroduto cheio no meio da laje acima (pé-direito + 7,5 cm);
   - pontilhado no piso (−5 cm);
   - descida ou subida na parede até a altura de cada ponto pela legenda;
   - luminária: caixa octogonal na laje e a luminária no forro;
   - prumada vertical de caixa a caixa.
10. **Preço:** quantidades da lista do projetista; o modelo reparte o que o SINAPI separa (seção 6).

## 3. Resultado da leitura

| | 5º | 4º | 3º | 2º | 1º | Térreo | Subsolo |
|---|---|---|---|---|---|---|---|
| Pontos (sem caixas e quadros) | 165 | 164 | 164 | 164 | 164 | 55 | 21 |
| Quadros (QD/QM) | 4 | 4 | 4 | 4 | 4 | 2 + 22 | — |
| Caixas de passagem | 8 | 12 | 16 | 20 | 24 | 25 | 5 |
| Eletrodutos lidos | 173 | 172 | 172 | 172 | 172 | 114 | 22 |
| Pontas soltas | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

- **3D:** 4.206,7 m de eletroduto (1.817 m na laje, 1.723 m de descidas, 426 m no piso, 239 m de prumadas), 5.489 trechos. **Nada solto:** toda ponta encosta em outro eletroduto ou numa caixa, e toda caixa tem eletroduto. A conferência verifica isso a cada leitura.
- **Alimentadores:** os 22 QDs chegam no QM de mesmo número. No térreo, 11 vão em 2" e 11 em 3" (exatamente os 22 rótulos do desenho); dos medidores até a AL1 vão em 1.1/2".

## 4. Conferência (aba "Conferência" e tela de conferência da página)

**Fecham:**
- Pontos e peças × lista de materiais, item a item, em todas as folhas: tomadas por tipo, interruptores por tipo, sensores, luminárias por potência, arandelas, caixas 4×2", 4×4", octogonais, de passagem e quadros. A única diferença é a do térreo (seção 7).
- Pontos por circuito e potência × quadro de cargas: **22 de 22 quadros iguais ponto a ponto**.
- Letras de comando: toda luminária tem interruptor ou sensor com a mesma letra no mesmo quadro.
- Os 20 apartamentos têm os mesmos pontos, circuito a circuito.
- Eletroduto 3/4" × lista nos andares-tipo: −0,3% a 0,0%, medindo como o projetista: comprimento desenhado + descida do forro até o topo da caixa.
- Eletroduto 2" e 3" × lista no prédio: −1,6% e −1,7%, com a caixa de passagem da prumada a 2,00 m (premissa).

**Não fecham (explicado; o orçamento usa a lista):**
- Eletroduto 3/4" no térreo (−12,7%) e no subsolo (−17,3%). Com a mesma medida que fecha nos andares-tipo, a lista tem trechos que a planta não desenha.
- Eletroduto 1" (−8,9%) e 1.1/2" (+21,1%) no prédio. O programa do projetista conta as prumadas e as chegadas aos quadros de outro jeito, que o leitor não conseguiu reproduzir.

## 5. Premissas do modelo

- Arandela a 2,00 m: a legenda não dá a altura.
- Caixa de passagem da prumada a 2,00 m: a legenda não dá. Com essa altura, os eletrodutos de 2" e 3" do térreo fecham com a lista.
- Eletroduto cheio na laje e pontilhado no piso. É a convenção usual; o desenho não diz.
- Alimentador que chega entre duas caixas vizinhas da fileira de prumadas (térreo, QM5 e QM9): vale a numeração. A QMn sobe pela CXn, como em todos os andares.
- Fileira CX24/CX25/CX26 encostada no QD22 (térreo): as setas das prumadas ligam as três caixas ao quadro.

## 6. Preço (SINAPI 10/2026 SP, sem desoneração, custo direto)

**R$ 320.853,60**, aba "Elétrica (orçamento)" e etapa 03 da tela de orçamento:

| Grupo | R$ |
|---|---|
| Cabos | 179.794,54 |
| Eletrodutos | 45.945,13 |
| Tomadas, interruptores e sensores | 30.307,23 |
| Caixas | 26.711,77 |
| Quadros e proteção | 19.040,40 |
| Iluminação | 9.972,72 |
| Entrada de serviço e medição | 8.860,07 |
| Acessórios | 221,74 |

**O que vem do modelo:**
- eletroduto 3/4" e 1": metros da lista repartidos entre laje e parede na proporção medida em cada andar;
- caixa 4×2": baixa, média ou alta pela altura de cada ponto;
- tomada 20 A: alta (ar-condicionado) ou baixa (portões).

**Substituições:**
- **Luminárias:** o projeto pede incandescente, que saiu do mercado brasileiro (Portaria Interministerial 1.007/2010); o SINAPI só tem LED.
- **Eletroduto pesado 1.1/2", 2" e 3":** PEAD corrugado da mesma bitola.
- **Disjuntores:** 13 A pelo preço do 16 A; 63 A e 70 A pela composição de 50 A com o disjuntor de 63 A.
- **DR 80 A:** pelo DR 63 A.
- **DPS 40 kA:** pelo de 20 kA (o de 40 kA está sem preço em SP).
- **Quadro de 12 disjuntores:** composição do de 6 com o quadro trocado.
- **Cabo de 25 mm²:** composição do de 16 mm² com o cabo trocado.
- **Só material** (o SINAPI não tem composição): caixas de medição CPFL, poste, parafuso e acessórios de uso geral.

**Sem preço:**
- caixa tipo T (proteção geral);
- buchas e arruelas de zamak;
- arruela de pressão;
- parafuso autoatarraxante.

## 7. Pontos para o projetista elétrico

1. **Eletroduto do ar-condicionado (circuito 7, cabo de 4 mm²)** sem rótulo ø nos 10 apartamentos de QD par (QD2, QD4 … QD20). Nos de QD ímpar ele é 1". O modelo segue o desenho (3/4"); confirmar a bitola.
2. **Caixas de medição:** a lista do térreo tem 23 individuais (21 bifásicas, 1 monofásica, 1 trifásica), mas a planta tem 22 (QM1–QM22). A trifásica não aparece na planta.
3. **CX25 no subsolo:** está na lista e na planta, mas não recebe eletroduto nem tem a bolinha de prumada.
4. **Térreo:** os alimentadores de QM5 e QM9 terminam entre duas caixas da fileira de prumadas. Pela numeração, entram na CX5 e na CX9.
5. **Lâmpadas incandescentes** especificadas na lista. Trocar por LED equivalente (orçado assim).
6. **Alturas que faltam na legenda:** arandela e caixas de passagem das prumadas.

## 8. Arquivos

- `leitor/leitor/eletrica.py`: leitura (plantas, prédio, tabelas, 3D, conferência).
- `leitor/leitor/orcamento_ele.py`: preço SINAPI.
- `leitor/leitor/saida_eletrica.py`: abas da planilha.
- Página: camada "Elétrica" (eletrodutos; pontos e quadros), ficha do eletroduto e do ponto, resumo por andar.
- Uso: `python medir.py <arquitetônico.pdf> ... --eletrica <eletrico.pdf>`.
