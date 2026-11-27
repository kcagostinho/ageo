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
| H1a | Rede de água fria dos isométricos + quantitativo | **Feito para as 12 prumadas dos apartamentos** |
| H1b | Água fria no 3D | **Feito para as colunas dos apartamentos** (modo "Instalações") |
| H1c | Auditoria de interferências + preço | Auditoria feita (0 conflitos). Preço SINAPI: próxima etapa |
| H1d | Barrilete, alimentação (AL), extravasor, térreo e subsolo | Próxima etapa: plantas da cobertura/térreo/subsolo e isométricos do barrilete e do salão de festas |
| H2a–c | O mesmo para o esgoto (com caimento, caixas e ralos) | Depois da água fria |

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

### Quantitativo das prumadas dos apartamentos × tabela do projetista

| Tubo PVC soldável | Prumadas dos aptos (modelo) | Tabela do projetista (prédio todo) |
|---|---|---|
| DN20 | 100,96 m | 113,52 m |
| DN25 | 205,83 m | 257,25 m |
| DN32 | 24,04 m | 145,66 m |
| DN40 | — | 5,45 m |
| DN50 | — | 23,23 m |

- A diferença é o que falta ler: barrilete, alimentação (AL, cerca de 20 m em DN32 do hidrômetro aos reservatórios), extravasor, térreo (salão de festas) e subsolo.
- A tabela do projetista não bate com a soma simples dos rótulos de nenhuma vista: o DN25 dos isométricos dos aptos sozinho já passa dela (336,7 m somando os repetidos). Ela será comparada de novo quando a rede estiver completa.
- **Conexões e registros**: os códigos lidos batem com a tabela onde o item é só dos apartamentos:
  - registro de chuveiro 20 mm: 16 = 16;
  - registro de chuveiro 25 mm: 4 = 4;
  - registro de gaveta 25 mm: 45 = 45.

## 5. Pontos para o projetista hidráulico

1. **Rótulos ausentes nas cozinhas.** Alguns tubos curtos estão desenhados mas sem rótulo em alguns andares (0,06 a 0,54 m). Completar os rótulos nos isométricos das cozinhas.
2. **Rótulo repetido.** O trecho da coluna entre andares aparece rotulado duas vezes. Não é erro de quantidade se a tabela contar o tubo uma vez, mas confunde quem soma pelo desenho.
3. **Tabela "Tubos Rígidos".** Confirmar se é da revisão atual: será conferida quando o barrilete e o térreo estiverem no modelo.
4. **Bucha de redução "250x40 mm"** (código 04) na tabela de conexões: provável erro de digitação (50x40 mm).
