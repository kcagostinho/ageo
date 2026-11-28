# Leitor de projetos — Fase 1 (medição)

Lê pranchas em **PDF exportado do CAD** (vetorial, com camadas), mede os ambientes e conta as esquadrias.
Plano completo em [`../docs/plano-leitor-de-projetos.md`](../docs/plano-leitor-de-projetos.md).

```bash
pip install -r requirements.txt
python medir.py caminho/projeto.pdf --obra "Nome da obra" --saida obras/<obra>/saida
# com o projeto de água fria (isométricos de prumada + plantas):
python medir.py caminho/projeto.pdf --obra "Nome da obra" --saida obras/<obra>/saida --agua-fria caminho/agua_fria.pdf --esgoto caminho/sanitario.pdf --eletrica caminho/eletrico.pdf
```

Saídas em `--saida`:

| Arquivo | Conteúdo |
|---|---|
| `medicao.xlsx` | **Orçamento da alvenaria e dos revestimentos (B4, SINAPI)**, preços e custo por pavimento; insumos (B3); paginação; paredes; resumo por pavimento; **água fria** (tubos por DN × tabela do projetista, por coluna e andar, trecho a trecho com a parede onde passa, e como foi lido); **elétrica** (pontos e peças × lista de materiais por folha, pontos, eletrodutos, quadros de carga × planta, orçamento SINAPI); **quantitativos por ambiente** (piso, teto, rodapé, parede bruta/líquida) e resumo por tipo de ambiente; ambientes (rótulo × medida); esquadrias; premissas (pé-direito editável); calibração |
| `conferencia.html` | Prancha com cada ambiente desenhado e colorido pelo status, para conferência visual |
| `paredes.html` | Modelo de paredes: cada parede com eixo e espessura, colorida por tipo (estrutural, vedação…). Clique para reclassificar e baixe os ajustes |
| `paginacao.html` | Paginação estimada: elevação de cada parede bloco a bloco, famílias 29 e 39, com comparação de peças e cortes |
| `obra.html` | **Página da obra** (abre no computador e no celular; three.js embutido). Menu lateral no computador e abas embaixo no celular: **Visão geral** (custo medido, R$/m², CUB, situação de cada disciplina e pontos para os projetistas), **Modelo 3D**, **Plantas** (as páginas 2D abaixo, em abas), **Quantitativos** (modelo × tabela do projetista), **Orçamento** por etapa (parte cinza, instalações hidráulicas, incêndio, elétrica; até o item SINAPI), **Conferência**, **Documentos** e **Guia visual**. No 3D: pavimentos em coluna, disciplinas com olho (arquitetura, parte cinza, hidráulica, elétrica), colorir por material, uso dos ambientes, blocos (paginação) ou custo, nomes dos ambientes com liga/desliga, cortes e ficha do elemento selecionado |
| `obra.json` | Tudo acima com os polígonos, para as próximas fases (lacunas, EAP) |

## Como mede

1. **Ingestão** (`leitor/ingestao.py`): traços por camada do CAD (`A-WALL`, `A-DOOR`, `A-GLAZ`…) e textos com coordenadas.
2. **Vistas** (`vistas.py`): separa as plantas de cada prancha e lê título e escala nominal.
3. **Escala** (`escala.py`): compara o valor de cada cota com o comprimento desenhado. A escala nominal não é usada para medir (no projeto-piloto o PDF estava 1,6% menor que 1:50).
   - **Escala única e pavimentos repetidos** (`repeticao.py`):
     - todas as vistas usam a mesma escala: a mediana ponderada das calibrações. As cotas são arredondadas ao centímetro e, vista a vista, variam até 0,02%.
     - Uma vista cujas linhas de parede coincidem com as de outra (≥ 98% a menos de 0,15 pt) é lida numa cópia da folha posicionada sobre ela. Cada ponto com par na referência (mesma camada) recebe a coordenada exata da referência.
     - Andares iguais dão as mesmas áreas, paredes e paginação. O que muda de verdade (ex.: a escada do último andar) é lido do próprio andar.
     - Os dados de um andar repetido ficam no sistema de coordenadas da referência; `desloc` na vista diz onde ele está na folha.
4. **Ambientes** (`ambientes.py`): espaço livre entre paredes e esquadrias. Vãos de porta e janela fechados no alinhamento das faces da parede (pares de "tampas" de parede com porta, batente, vidro ou soleira entre elas). Folha de porta fechada como linha de apoio (`portas.py`). Faixas finas descartadas (miolo de parede, frestas). Linhas de piso só separam cômodos quando necessário.
5. **Conferência**: cada polígono é comparado com a área escrita no rótulo do arquiteto (ok ≤ 2%, conferir ≤ 10%, divergente > 10%).
6. **Esquadrias** (`esquadrias.py`): etiquetas `L x H` e peitoril.
7. **Vãos**: cada porta/janela vira um vão ligado aos ambientes vizinhos — por pontas de parede, por vidro (janela alta acima do plano de corte, porta de correr) ou por folha de porta. Altura e peitoril vêm da etiqueta mais próxima de mesma largura.
8. **Pé-direito** (`pe_direito.py`): lido da corrente de cotas verticais dos cortes (subsolo → térreo → tipos).
9. **Quantitativos** (`quantitativos.py`): contorno de cada ambiente classificado em parede, vão ou aberto (guarda-corpo, lado aberto).
   - Piso = área. Teto = área coberta.
   - Rodapé = contorno com parede − portas.
   - Parede bruta = contorno com parede × pé-direito. Parede líquida = bruta − vãos.
   - Na planilha, pé-direito, rodapé e paredes são fórmulas: mudar o pé-direito na aba Premissas recalcula tudo.
10. **Paredes** (`paredes.py`): a região que não é espaço livre é rasterizada.
    - Em cada coluna e linha da imagem, um trecho de 7 a 45 cm é a espessura de uma parede, e o meio do trecho é o eixo.
    - Os eixos são unidos, prolongados até os encontros (L, T, X) e recebem os vãos.
    - Os lados de cada parede saem dos polígonos dos ambientes.
    - Unidades (apartamentos) = ambientes ligados por porta sem passar pelo núcleo.
    - Classificação inicial: fachada, divisa entre unidades e núcleo = estrutural; interna da unidade = vedação; pavimentos sem unidades = a definir; muros e pilares à parte.
    - Ajustes manuais em `obras/<obra>/ajustes_paredes.json`.
11. **Paginação** (`paginacao.py`): fiada a fiada, por linha de parede (paredes colineares unidas).
    - Cantos em L alternados; T com bloco especial; família 39 com bloco 34 no canto.
    - Cruzamento em X: a estrutural passa sobre a vedação; paredes de mesmo tipo alternam por fiada.
    - Junta a prumo = desencontro menor que 5 cm com a fiada de baixo. Se as arrumações simples não evitam, uma busca exaustiva escolhe a sequência de peças.
    - Corte mínimo de 5 cm. Sobra menor entre peças fixas vira enchimento de argamassa.
    - Vergas e contravergas em canaleta; cinta de respaldo (J na fachada).
    - Meio bloco junto a vãos nas fiadas pares; sobras fora do módulo contadas como corte.
    - Gera a comparação das famílias 29 e 39 e o ajuste que cada parede precisaria para fechar no módulo.
12. **Insumos** (`insumos.py`), com a família escolhida (`--familia 39`, padrão):
    - blocos e canaletas da paginação;
    - argamassa pela geometria das juntas;
    - graute e aço de cintas, vergas, contravergas e pontos verticais (encontros, pontas e laterais de vão);
    - telas nos encontros vedação × estrutural e encunhamento;
    - fundo preparador + gesso por dentro, cerâmica das áreas molhadas e pintura projetada na fachada, varandas e platibanda.
13. **Cobertura e muros inclinados** (`cobertura.py`): parapeito, platibanda, águas do telhado (hachura `A-ROOF-PATT`), calhas e reservatórios da planta de cobertura; muros inclinados por pares de linhas paralelas de `A-WALL`.
14. **Orçamento — B4** (`orcamento.py`, `sinapi.py`, `cub.py`, `saida_orcamento.py`):
    - baixa o SINAPI do mês na Caixa (só SP fica em `obras/_sinapi/`) e o CUB do SindusCon-SP;
    - material contado na paginação × insumo SINAPI; mão de obra da alvenaria tirada da composição SINAPI; graute, armação e revestimentos por composição completa;
    - abas Orçamento, Preços (desoneração, BDI, fbk por pavimento, cotações) e Custo por pavimento, todas com fórmulas;
    - rateio do custo por parede, ambiente e cobertura para o 3D (a soma confere com o total);
    - opções: `--sinapi AAAA-MM`, `--desonerado`, `--sem-preco`; premissas da obra na chave `orcamento` do `premissas.json`.
15. **Escadas** (`escada.py`): a numeração dos degraus dentro do ambiente "Escada…" dá os lances (números seguidos e alinhados), a profundidade do piso e o sentido de subida; o último número de um lance seguido de outro vira patamar; o maior número é a chegada no andar de cima. A largura vem das paredes (ou da metade da distância entre lances). O 3D desenha degraus, patamar, corrimão e guarda-corpo com o espelho = desnível dos cortes ÷ nº de espelhos.
16. **Conferência automática** (`conferencia.py`, aba "Conferência" e terminal), a cada leitura:
    - área medida × rótulo;
    - cada etiqueta de esquadria com um vão, por pavimento (a porta do elevador, sem etiqueta, é contada à parte);
    - um vão de varanda por ambiente de varanda;
    - nenhum vão fora de parede;
    - pavimentos repetidos idênticos à referência;
    - escala única;
    - geometria: ambientes sobrepostos, parede sobre ambiente, parede sem comprimento, vão fora da parede;
    - paginação refeita bloco a bloco em planta, fiada a fiada: peças sobrepostas (na parede e entre paredes), lacunas, cortes < 5 cm, juntas a prumo.
17. **Alterações de projeto** (`alteracoes.py`, arquivo `obras/<obra>/alteracoes.json`): decisões do cliente aplicadas sobre a leitura do PDF, a cada leitura.
    - Hoje: `remover_paredes`, por regra (ambientes dos dois lados, com porta, comprimento máximo) ou por `ids`.
    - Sai a parede com os vãos e as etiquetas dela; a faixa de piso vai metade para cada ambiente e a divisa vira contorno aberto.
    - As paredes vizinhas têm o encontro recalculado; a área esperada passa a ser o rótulo + o acréscimo.
    - Tudo fica registrado em `alteracoes` no `obra.json` e numa linha da aba Conferência.
18. **Água fria** (`hidraulica.py`, `saida_hidraulica.py`, opção `--agua-fria`). O PDF hidráulico não tem camadas: tudo é traço de 0,15 pt e os tubos são polígonos pretos. A leitura é pela imagem.
    - **Tubos**: render em cinza → abertura morfológica (some texto, cota e linha fina) → esqueleto → trechos retos. Cada rótulo "DNxx mm / L,LLm" vai para o tubo pela linha de chamada, ou pelo mais perto sem aceitar um tubo bem maior que o rótulo. Cada código de conexão (círculo) vai para a ponta de tubo mais perto.
    - **Isométrico de prumada** (um por coluna: banheiro, cozinha, varanda): é uma elevação oblíqua em escala.
      - As cotas de altura ("0,20", "1,40"…) dão a escala e o piso de cada andar. O tique de baixo é o piso, conferido com os níveis da arquitetura.
      - O eixo horizontal sai com outra escala (0,95 a 1,07): é calibrado pelo tubo da planta.
      - Rótulo repetido no mesmo tubo (a coluna entre andares aparece nos dois andares) conta uma vez.
      - Tubo desenhado sem rótulo num andar recebe o DN e o comprimento do mesmo tubo em outro andar (marcado "inferido").
    - **Plantas**: registradas sobre as paredes do modelo por votação das linhas (escala e deslocamento).
      - O balão "AF-xx" com a chamada até a marca preta dá o ponto da coluna. A mediana entre os andares é a prumada.
      - O tubo da planta dá a direção do ramal em cada andar.
    - **Auditoria**: cada trecho é localizado na parede (estrutural ou vedação) e no ambiente. Conta como conflito:
      - tubo horizontal embutido em parede estrutural;
      - tubo vertical em ponto de graute;
      - tubo na altura de verga ou contraverga.
    - **Barrilete, térreo, subsolo e colunas do prédio**:
      - horizontais pela planta (posição exata; altura por premissa);
      - verticais pela vista que mais os mostra;
      - colunas que atravessam o prédio uma vez;
      - o rótulo repetido em pedaços alinhados do mesmo tubo conta uma vez.
    - **Preço** (`orcamento_hid.py`, aba "Instalações (B4)"): composição SINAPI por DN e tipo de trecho (prumada, ramal de distribuição, ramal/sub-ramal) e por código de conexão/registro. Peça sem composição tem o preço derivado da mais parecida, trocando o insumo.
    - Resultado e pontos para o projetista em `../docs/plano-hidrossanitario.md`.
19. **Esgoto sanitário** (`esgoto.py`, opção `--esgoto`). Os isométricos são perspectivas (ramais em duas direções), então são lidos só pelos rótulos.
    - **Quantitativo:** pelos isométricos, cada tubo uma vez.
      - A parte de baixo de cada isométrico de apartamento (tubo de queda até o coletor) vai para o grupo dos coletores.
      - Nos coletores, a planta do térreo/subsolo vale para o que ela rotula.
    - **3D:**
      - ramais pela planta de cada andar, com o DN pela espessura do traço (desenhado com o diâmetro real);
      - tubos de queda e ventilações pelos balões TQ-xx/V-xx;
      - coletores pela planta.
    - **Auditoria:** coluna dentro de parede onde não cabe; tubo de queda no ambiente, que pede shaft.
    - **Preço** (`orcamento_hid.calcular_esgoto`): SINAPI por DN e trecho (ramal de descarga, tubo de queda/ventilação, subcoletor), conexões pela descrição da tabela do projetista, caixas e ralos pela quantidade da tabela.
    - A aba "Instalações (B4)" soma água fria e esgoto.
20. **Costura do 3D das instalações** (`rede3d.py`, só visual).
    - Junta as pontas próximas e liga cada ponta solta ao tubo mais perto do mesmo sistema, com percurso ortogonal.
    - Ficam de fora os pontos de consumo, as subidas aos aparelhos e o topo das ventilações.
    - As ligações não entram no quantitativo nem no preço.
21. **Auditoria das instalações** (verificações na aba "Conferência"):
    - **Água fria:** ramais iguais andar a andar; pontos de consumo (09/10) iguais em todos os andares; diâmetro das colunas no balão da planta igual ao do isométrico.
    - **Esgoto:**
      - livro-razão dos rótulos (cada rótulo é um tubo ou a repetição de um tubo já contado);
      - caixas sifonadas e ralos da planta contra a tabela;
      - diâmetros dos tubos de queda no balão contra o isométrico;
      - declividades contra a NBR 8160.
    - **Peça desenhada em todos os andares e rotulada só em alguns:** conta com o rótulo do andar vizinho, marcada como "inferido". Na água fria, o mesmo vale para o ponto de consumo sem etiqueta.
    - **A tabela da prancha** é a moldura desenhada, não o texto mais uma margem. A margem engolia códigos de conexão encostados nela.
22. **Página da obra** (`saida_3d.py` + `leitor/web/`): `obra.html` junta o que antes estava em páginas soltas.
    - **Arquivos:**
      - `web/obra.html`: casca, estilos e interface;
      - `web/cena3d.js`: montagem da cena;
      - `web/ui3d.js`: ficha, legenda, resumo e seleção;
      - `web/telas.js`: telas de dados.
      - `saida_3d.painel()` monta os dados das telas, e `gerar()` junta tudo num arquivo só.
    - **Marca AGEO:**
      - azul #1C48A4 (Shark Blue) para navegação e ações;
      - laranja #EB6D4E (Lava Orange), pouco: item ativo, pendências e o elemento selecionado no 3D;
      - logos em `web/ageo-logo-*.png`.
    - **Disciplinas na cor do material que vai para a obra:**
      - bloco de concreto: estrutural mais escuro, vedação mais clara;
      - concreto armado;
      - PVC soldável marrom na água fria e PVC branco no esgoto;
      - eletroduto corrugado amarelo (leve) e laranja (pesado) na elétrica;
      - tubo vermelho de incêndio, para a próxima disciplina.
    - **Celular primeiro:**
      - 3D em tela cheia;
      - pavimentos numa coluna à direita;
      - folha "Camadas" com disciplinas, colorir por, vista, nomes, cortes e legenda;
      - ficha do elemento num cartão que abre por baixo;
      - tabelas viram lista.
    - **Nomes dos ambientes:** desligados por padrão. Quando ligados, só aparecem os que cabem sem sobrepor.
23. **Instalações elétricas** (`eletrica.py`, `orcamento_ele.py`, `saida_eletrica.py`, opção `--eletrica`). Detalhes, resultados e pontos para o projetista em `../docs/plano-eletrica.md`.
    - **Plantas:** o PDF não tem camadas; a leitura separa pela espessura do traço (0,84 eletroduto, 0,57 símbolos, 0,15 arquitetura).
      - Pontos pela forma do símbolo (caixinha + haste + triângulo, círculo, meia-lua, placa) e pelos textos (circuito, potência, comando, rótulo).
      - Eletrodutos cheios ligados ponta a ponta às caixas; alimentadores pontilhados lidos na ordem em que o PDF desenha os pontinhos, o que atravessa os cruzamentos sem trocar de linha.
      - Bitola pelo rótulo ø, casado um a um com os eletrodutos (o rótulo fica a 8,3 pt, pendurado embaixo do traço).
      - Registro sobre a arquitetura pelas paredes; planta com as prumadas fora do prumo é corrigida pelas próprias prumadas (subsolo: 3,08 m).
    - **Prédio:** prumadas pelas caixas de passagem de mesmo nome; caminho de cada alimentador QM → caixa → QD; quadro de cada ponto pela rede (atravessando as prumadas para as áreas comuns).
    - **Tabelas:** lista de materiais de cada folha e quadros de carga (circuitos, potências, seções, disjuntores).
    - **3D:** eletroduto cheio na laje, pontilhado no piso, descida na parede até a altura de cada ponto (legenda), prumada de caixa a caixa. Nada fica solto (verificado na conferência).
    - **Conferência:** pontos × lista item a item por folha, pontos × quadro de cargas circuito a circuito, comandos, alimentadores, apartamentos iguais, bitolas, eletroduto × lista (medido como o projetista), 3D sem peça solta.
    - **Preço:** quantidades da lista do projetista; o modelo reparte eletroduto entre laje e parede e caixas/tomadas por altura. Abas "Elétrica", "Elétrica - pontos", "Elétrica - eletrodutos", "Elétrica - quadros" e "Elétrica (orçamento)".

## Limitações conhecidas

- Depende de PDF vetorial com camadas no padrão do CAD (nomes AIA: `A-WALL`, `A-DOOR`…). PDF escaneado não funciona.
- Só mede ambientes que têm rótulo de área. A cobertura entra só no 3D (sem quantitativo na planilha). Terreno (planta de locação) e fachadas ficam para depois.
- Paredes ortogonais no modelo de alvenaria. Em muro inclinado, porta ou portão entra quando há uma etiqueta L × H da mesma largura da lacuna entre dois trechos do muro.

Os arquivos das obras (`obras/`) ficam fora do git.

O three.js vem embutido (`leitor/vendor/three-0.160.0-orbit.min.js`, licença MIT em `THREE-LICENSE.txt`). Ele foi gerado com esbuild a partir de `three@0.160.0` e `OrbitControls` (formato IIFE, expõe `THREE` e `OrbitControls`).
