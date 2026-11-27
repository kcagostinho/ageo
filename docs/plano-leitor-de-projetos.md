# Plano — Leitor de Projetos (AGEO)

> **Objetivo:** ler os projetos das nossas obras (PDF/DWG + memoriais), **medir**, **achar lacunas de especificação** e **montar a EAP com quantitativos rastreáveis**. No fim, levar o custo de obra para a viabilidade (simulador AGEO).

Status: rascunho de planejamento · 27/11/2026

---

## 1. O que o anúncio mostra

| Tela | O que aparece | Como provavelmente funciona |
|---|---|---|
| **1. Medir e quantificar** | "Visualizador ao vivo" com camadas *Desenho original / Linhas de apoio / Objetos novos / Rótulos*; lista de passos com área e perímetro de cada ambiente; coordenadas em metros; "Script 9 – montar as pranchas" | O Claude Code roda scripts sobre um **DWG/DXF** (coordenadas em metros indicam o espaço de modelo do CAD). As "linhas de apoio" fecham os vãos de porta para cada ambiente virar um polígono fechado, e o script calcula área e perímetro. Uma página web recebe os eventos e desenha na hora. O log mede **um ambiente por segundo**, então é cálculo geométrico, não o modelo "olhando" a planta. |
| **2. Achar o que falta** | Ferramenta de levantamento em PDF no navegador (Selecionar, Contar, Polilinha, Retângulo, Comentar, ORTO); calibração de escala clicando numa cota ("Clique na outra ponta da cota"); painel "Lacunas" L01–L11 por ambiente, com cores | Extrai o texto do PDF (nome do ambiente, "A: 4,55 m²", "PD: 2,60 m", códigos P03/P05) e lê o memorial. O agente confere cada ambiente contra uma lista do que precisa estar especificado. O que falta vira um pino na planta. |
| **3. Juntar numa EAP** | Conversa no claude.ai gerando um .xlsx com abas EAP / Premissas / Resumo: 16 etapas, 73 subetapas e 232 itens, nas colunas Código, Nível, Tipo, Descrição, Unidade e Fonte | Um prompt com a medição e as especificações; o modelo monta a planilha. |

### O que vale copiar

- **Separar "medir" de "interpretar".** Código calcula, IA lê e decide.
- **Coluna "Fonte" em cada item** (Memorial 01, Estrutural pr. 1, Prática) para rastrear a origem.
- **Lacunas como lista de decisões:** você completa com a sua experiência ou manda para o projetista confirmar.
- **Conferência cruzada:** área medida × área escrita no rótulo do arquiteto.

### O que o anúncio não mostra (pontos de atenção)

- **São três ferramentas diferentes**, não um programa integrado. As telas têm visual diferente e a pasta "aula-analise-pdf" sugere material de curso.
- **A EAP é um esqueleto.** 134 dos 232 itens (58%) estão com especificação pendente, e 57 (25%) têm fonte "Prática", ou seja, vêm de suposição. As colunas que aparecem nem mostram quantidade, apesar da legenda.
- **Nem tudo foi medido na tela 1.** O lavabo (1,73 m²) e a lavanderia (3,81 m²) parecem ter ficado sem contorno. Falta uma checagem do tipo "todo rótulo de ambiente tem polígono".
- **Depende do formato.** Com DWG ou PDF vetorial dá para medir automaticamente; com PDF escaneado o resultado não é confiável.
- **O "ao vivo" é vitrine.** Ajuda a conferir, mas não é o que gera valor. Fica para o fim.
- **EAP não é orçamento.** Não aparece preço (SINAPI ou composições próprias).

---

## 2. Princípios do nosso programa

1. **A IA interpreta, o código mede.** Nenhuma medida sai de "olhar a imagem". Toda área, perímetro e contagem sai da geometria vetorial, calculada por script.
2. **Todo número tem fonte:** prancha + coordenada, memorial + página, ou premissa aprovada por você.
3. **Nada é suposto em silêncio.** O que faltar vira lacuna. "Prática" só entra se você aprovar como premissa.
4. **Conferência visual sempre.** Cada ambiente medido aparece desenhado sobre a planta.
5. **Começar pequeno.** Primeiro o arquitetônico de uma obra-piloto, conferido contra os rótulos e o quadro de áreas. Só depois as outras disciplinas.

---

## 3. Arquitetura

```
 obras/<obra>/entrada/   PDF · DWG · memorial · quadro de esquadrias
          │
  ┌───────▼────────┐  textos com coordenadas, linhas, camadas, blocos
  │ 1. Ingestão    │  (código)
  └───────┬────────┘
  ┌───────▼────────┐  escala, ambientes (polígonos), áreas, perímetros,
  │ 2. Medição     │  esquadrias, conferência com rótulos      (código)
  └───────┬────────┘
          ▼
      obra.json   ◄── fonte única da verdade (tudo com "fonte")
          │
  ┌───────▼────────┐  Claude lê memorial/notas → matriz ambiente × serviço
  │ 3. Especific.  │  + checklist → lacunas L01, L02…   (IA + regras)
  │    e lacunas   │
  └───────┬────────┘
  ┌───────▼────────┐  modelo de EAP AGEO + fórmulas ligadas à medição
  │ 4. EAP         │  (código monta, IA escreve descrições)
  └───────┬────────┘
          ▼
 obras/<obra>/saida/   medicao.xlsx · lacunas.pdf · eap.xlsx · visualizador.html
```

### 3.1 Ingestão

| Entrada | Como ler | Qualidade esperada |
|---|---|---|
| **DWG** | Converter para DXF com o ODA File Converter (gratuito) e ler com `ezdxf`: camadas, polilinhas, hachuras, textos e blocos (portas e janelas costumam ser blocos) | Melhor caso: unidades reais e camadas |
| **PDF vetorial** (exportado do CAD) | `PyMuPDF`: `get_drawings()` para linhas e `get_text("words")` para textos com coordenadas; às vezes preserva camadas | Bom, depois de calibrar a escala |
| **PDF escaneado** | Renderizar e passar por OCR. A medição fica semiautomática (calibrar pela cota e clicar) | Baixa. O programa precisa **avisar** |
| **Memorial / caderno de especificações** | Texto direto (PDF/DOCX) lido pelo Claude, citando a página | Bom |

### 3.2 Medição

- **Escala.** Calibrar automaticamente pelas cotas (casar o texto "6,38" com o segmento da cota) e conferir em várias cotas. Se não der, calibrar à mão com dois cliques numa cota, como no anúncio.
- **Ambientes**, em ordem de preferência:
  1. o arquivo já tem polilinha ou hachura de área: usar direto;
  2. senão, pegar as paredes, fechar os vãos de porta com linhas de apoio e rodar `shapely.polygonize`. O ambiente é a face que contém o texto com o nome dele;
  3. se ainda falhar, o usuário clica dentro do ambiente e confirma o polígono proposto.
- **Conferência.** Área medida × área do rótulo, com tolerância de ±2%. Rótulo sem polígono é erro.
- **Quantitativos derivados por ambiente:**

| Serviço | Regra | Depende de |
|---|---|---|
| Piso, contrapiso, forro, pintura de teto | área | polígono |
| Rodapé | perímetro − larguras das portas | esquadrias |
| Parede (pintura/revestimento) | perímetro × altura − vãos | PD, altura do revestimento, esquadrias |
| Soleiras / peitoris | por esquadria | quadro de esquadrias |
| Impermeabilização | área + subida no perímetro | especificação (premissa) |
| Esquadrias | contagem por tipo (P01, J01…) | blocos/rótulos + quadro |

### 3.3 Especificações e lacunas

- **Checklist por tipo de ambiente** (seca, molhada, externa, garagem…), salvo em `config/checklist_ambientes.yaml`. É a sua experiência transformada em regra. Exemplo para área molhada: piso, rodapé/soleira, revestimento de parede com a altura, teto/forro, impermeabilização, ralo, louças, metais e bancada.
- O Claude preenche a matriz **ambiente × serviço** com o que achar no memorial, no quadro de acabamentos e nas notas das pranchas, **sempre com a página de origem**.
- O que faltar vira **lacuna**. Se o memorial disser uma coisa e a prancha outra, vira **lacuna de conflito**.
- **Severidade:** 🔴 muda o custo ou bloqueia · 🟠 dá para assumir com prática · 🟢 informativa.
- Você decide cada lacuna: **assumir** (vira premissa) ou **perguntar** (vai para o relatório do projetista).

### 3.4 EAP

- Um modelo de EAP da AGEO (`config/eap_modelo.yaml`) com etapas e subetapas padrão: preliminares, fundações, estrutura, alvenaria, cobertura, instalações, impermeabilização, revestimentos, pisos, forros, esquadrias, pintura, louças e metais, complementares e limpeza.
- Um script gera o `eap.xlsx` com as abas **EAP · Medição · Especificações · Lacunas · Premissas · Resumo**.
- **A quantidade é uma fórmula** que aponta para a aba Medição (SOMASES), não um número colado. Se a medição mudar, a EAP atualiza sozinha.
- Colunas extras: **Fonte** e **Status** (ok / premissa / pendente).

### 3.5 Visualizador

- Um HTML estático, sem build, no mesmo estilo do `index.html` do simulador. Mostra a prancha em SVG (gerada pelo PyMuPDF), os polígonos dos ambientes, as linhas de apoio e os pinos das lacunas, em camadas que dá para ligar e desligar.
- Ao clicar num ambiente aparecem área, perímetro, especificações e lacunas.
- O modo "ao vivo" (um servidor local que envia eventos enquanto os scripts rodam) é opcional e fica para a Fase 5.

---

## 4. Modelo de dados (`obra.json`)

```json
{
  "obra": "Nome da obra",
  "documentos": [
    {"id": "ARQ-01", "arquivo": "entrada/arq_planta.pdf", "tipo": "pdf_vetorial",
     "escala": {"metros_por_unidade": 0.02646, "metodo": "cota", "erro_pct": 0.3}}
  ],
  "ambientes": [
    {"id": "AMB-07", "nome": "bwc 02", "doc": "ARQ-01", "tipo": "molhada",
     "poligono": [[0, 0], [1.30, 0], [1.30, 3.50], [0, 3.50]],
     "area_m2": 4.55, "perimetro_m": 9.60, "pe_direito_m": 2.60,
     "area_rotulo_m2": 4.55, "divergencia_pct": 0.0, "status": "conferido"}
  ],
  "esquadrias": [
    {"id": "P03", "tipo": "porta", "largura_m": 0.80, "altura_m": 2.10, "ambientes": ["AMB-07", "AMB-03"]}
  ],
  "especificacoes": [
    {"ambiente": "AMB-07", "servico": "piso", "valor": "porcelanato 60x60 acetinado",
     "fonte": {"doc": "MEM-01", "pagina": 7}, "confianca": "alta"}
  ],
  "lacunas": [
    {"id": "L04", "ambiente": "AMB-07", "servico": "revestimento_parede",
     "pergunta": "Altura do revestimento cerâmico: até o teto ou 1,50 m?",
     "severidade": "alta", "decisao": "perguntar", "resposta": null}
  ],
  "premissas": [
    {"id": "PR-03", "texto": "Rodapé de 7 cm no material do piso nas áreas secas", "aprovada": true}
  ]
}
```

---

## 5. Fases

| Fase | Entrega | Pronto quando |
|---|---|---|
| **0. Gabarito e insumos** | Uma obra-piloto com todos os PDFs (arquitetônico, memorial, quadro de esquadrias). Como não há orçamento manual, a conferência usa os **rótulos de área do arquiteto**, o **quadro de áreas** e 3 a 5 ambientes medidos por você. Checklist de acabamentos e modelo de EAP escritos | Pasta da obra organizada e `config/` preenchido |
| **1. Leitura e medição** | Ingestão do PDF, escala, ambientes, áreas e perímetros, conferência com rótulos e quadro de áreas, visualizador simples, `medicao.xlsx` | Pelo menos 90% dos ambientes detectados sozinhos e 100% dentro de ±2% do rótulo depois das correções; soma das áreas bate com o quadro de áreas |
| **1b. Estimativa CUB** | Área equivalente (NBR 12721) × CUB do padrão da obra + itens que o CUB não cobre | Primeiro custo de obra no simulador e referência para conferir o SINAPI |
| **2. Especificações e lacunas** | Matriz ambiente × serviço com fonte, lista de lacunas com severidade, relatório para o projetista, pinos no visualizador | O agente encontra as lacunas que você já conhece e você concorda com pelo menos 80% das que ele marca |
| **3. EAP vinculada** | `eap.xlsx` com fórmulas ligadas à medição e abas de premissas e lacunas | Os quantitativos principais (piso, parede, forro, esquadrias) batem com a conferência manual dos ambientes-amostra |
| **4. Mais disciplinas** | Esquadrias completas; hidrossanitário e elétrico (contagem de pontos e metragem de tubulação por símbolo e legenda). Estrutural fica **paramétrico** (índices de concreto e aço por m², marcados como premissa) até haver projeto | Contagens conferidas com a legenda de cada prancha |
| **5. Orçamento SINAPI** | Itens da EAP ligados a composições SINAPI-SP (o Claude sugere o código, você aprova) + BDI, dando o custo de obra e a curva mensal levados ao simulador AGEO; modo "ao vivo" opcional | Total SINAPI comparado com a estimativa CUB e diferenças explicadas |

---

## 6. Como o Claude entra

**Agora (Fases 0 a 3): o Claude Code é o motor.** É o mesmo modelo do anúncio ("Script 9").
- Roda no seu computador, dentro da pasta do programa.
- Os scripts Python fazem o trabalho determinístico.
- Skills do Claude Code (`.claude/skills/medir-planta`, `achar-lacunas`, `montar-eap`) descrevem o passo a passo de cada etapa.
- O `CLAUDE.md` fixa as regras da seção 2: nunca medir "no olho", todo número com fonte, faltou vira lacuna.
- Você conversa: "lê a obra X", "mostra as lacunas da cozinha", "assume porcelanato 60x60 nas áreas secas".

**Depois (se quiser rodar sem conversa): a Claude API dentro do pipeline.**
- Python SDK com o modelo `claude-opus-5-5`.
- PDFs enviados como documento com *citations* ligado. Cada especificação volta com a página de onde saiu, o que preenche a coluna Fonte.
- *Structured outputs* (JSON validado por schema) para a matriz de especificações.
- *Batch API* (metade do preço) quando não houver pressa.

---

## 7. Stack e custos

| Função | Ferramenta |
|---|---|
| Ler PDF (vetores, textos, render, SVG) | PyMuPDF |
| Ler DXF | ezdxf |
| Converter DWG em DXF | ODA File Converter (gratuito; Windows, Mac e Linux) |
| Geometria (polígonos, áreas, união) | shapely |
| Planilha com fórmulas | openpyxl |
| OCR (só para PDF escaneado) | Tesseract |
| Visualizador | HTML + SVG estático |
| IA | Claude Code → Claude API |

**Custo de IA (estimativa, a medir na Fase 2).** Uma obra pequena (cerca de 10 pranchas + memorial de 40 páginas) deve dar algo como 100 a 200 mil tokens de entrada por rodada completa. No Opus 5.5 (US$ 4 por milhão de tokens de entrada e US$ 20 por milhão de saída), isso fica na ordem de **US$ 1 a 5 por rodada**. Pelo Claude Code, o uso conta no seu plano.

### Estrutura de pastas sugerida

```
leitor-projetos/                 ← repositório privado separado (recomendado)
  CLAUDE.md                      regras do agente
  .claude/skills/
    medir-planta/SKILL.md
    achar-lacunas/SKILL.md
    montar-eap/SKILL.md
  leitor/                        pacote Python
    ingestao.py                  PDF/DXF → textos, linhas, camadas
    escala.py                    calibração por cotas
    ambientes.py                 polygonize, casamento com rótulos, conferência
    quantitativos.py             piso, rodapé, parede, vãos…
    lacunas.py                   checklist × especificações
    eap.py                       gera xlsx com fórmulas
    viewer/index.html            visualizador
  config/
    checklist_ambientes.yaml
    eap_modelo.yaml
    camadas_por_escritorio.yaml  mapa de camadas de cada arquiteto
  obras/<obra>/
    entrada/                     (fora do git)
    saida/
```

---

## 8. Riscos

| Risco | Mitigação |
|---|---|
| PDF escaneado ou sem vetores | Detectar na ingestão e avisar; medição semimanual com escala calibrada |
| DWG sem padrão de camadas | Mapa de camadas por escritório de arquitetura: pergunta uma vez e salva |
| Vão mal fechado gera ambiente errado | Conferência com o rótulo + visualizador + correção manual do polígono |
| IA inventar especificação | Fonte obrigatória (citação de página). Sem fonte, vira lacuna, não valor |
| "Área de quê?" (útil × construída × equivalente) | Definir por serviço: piso usa face interna; quadro de áreas para incorporação segue a NBR 12721 |
| Confidencialidade dos projetos | Arquivos das obras fora do git e repositório privado; conferir o contrato com os projetistas e a política de dados do plano Claude |
| Escopo crescer demais | Fases com "pronto quando", uma obra-gabarito e nada de tentar virar um software comercial de levantamento |

---

## 9. Decisões

**Tomadas (27/11/2026):**
1. **Formato:** PDF exportado do CAD (vetorial). O caminho principal é o PyMuPDF; DWG fica opcional.
2. **Gabarito:** não há obra orçada à mão. O levantamento é justamente a base do orçamento automatizado. A conferência usa rótulos, quadro de áreas, amostras manuais e o CUB como referência de ordem de grandeza.
3. **Orçamento:** SINAPI (detalhado) + CUB (paramétrico, para conferência e estimativa rápida).
4. **Disciplinas:** todos os projetos disponíveis, exceto o estrutural. Começar pelo **arquitetônico**.

**Ainda em aberto:**
- **Onde roda:** qual o sistema operacional do computador onde ficam os arquivos e onde o Claude Code vai rodar?
- **Repositório:** separado e privado (recomendado) ou dentro deste repositório do simulador?

**Próximo passo:** receber o PDF da planta baixa arquitetônica de um pavimento (com o quadro de áreas, se estiver em outra prancha) e o memorial descritivo, e rodar a Fase 1: extrair textos e linhas, calibrar a escala e desenhar os ambientes para conferência.
