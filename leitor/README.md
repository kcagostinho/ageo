# Leitor de projetos — Fase 1 (medição)

Lê pranchas em **PDF exportado do CAD** (vetorial, com camadas), mede os ambientes e conta as esquadrias.
Plano completo em [`../docs/plano-leitor-de-projetos.md`](../docs/plano-leitor-de-projetos.md).

```bash
pip install -r requirements.txt
python medir.py caminho/projeto.pdf --obra "Nome da obra" --saida obras/<obra>/saida
```

Saídas em `--saida`:

| Arquivo | Conteúdo |
|---|---|
| `medicao.xlsx` | Resumo por pavimento; **quantitativos por ambiente** (piso, teto, rodapé, parede bruta/líquida) e resumo por tipo de ambiente; ambientes (rótulo × medida); esquadrias; premissas (pé-direito editável); calibração |
| `conferencia.html` | Prancha com cada ambiente desenhado e colorido pelo status, para conferência visual |
| `paredes.html` | Modelo de paredes: cada parede com eixo e espessura, colorida por tipo (estrutural, vedação…). Clique para reclassificar e baixe os ajustes |
| `paginacao.html` | Paginação estimada: elevação de cada parede bloco a bloco, famílias 29 e 39, com comparação de peças e cortes |
| `obra.json` | Tudo acima com os polígonos, para as próximas fases (lacunas, EAP) |

## Como mede

1. **Ingestão** (`leitor/ingestao.py`): traços por camada do CAD (`A-WALL`, `A-DOOR`, `A-GLAZ`…) e textos com coordenadas.
2. **Vistas** (`vistas.py`): separa as plantas de cada prancha e lê título e escala nominal.
3. **Escala** (`escala.py`): compara o valor de cada cota com o comprimento desenhado. A escala nominal não é usada para medir (no projeto-piloto o PDF estava 1,6% menor que 1:50).
4. **Ambientes** (`ambientes.py`): espaço livre entre paredes e esquadrias. Vãos de porta e janela fechados no alinhamento das faces da parede (pares de "tampas" de parede com porta, batente, vidro ou soleira entre elas). Folha de porta fechada como linha de apoio (`portas.py`). Faixas finas descartadas (miolo de parede, frestas). Linhas de piso só separam cômodos quando necessário.
5. **Conferência**: cada polígono é comparado com a área escrita no rótulo do arquiteto (ok ≤ 2%, conferir ≤ 10%, divergente > 10%).
6. **Esquadrias** (`esquadrias.py`): etiquetas `L x H` e peitoril.
7. **Vãos**: cada porta/janela vira um vão ligado aos ambientes vizinhos — por pontas de parede, por vidro (janela alta acima do plano de corte, porta de correr) ou por folha de porta. Altura e peitoril vêm da etiqueta mais próxima de mesma largura.
8. **Pé-direito** (`pe_direito.py`): lido da corrente de cotas verticais dos cortes (subsolo → térreo → tipos).
10. **Paredes** (`paredes.py`): a região que não é espaço livre é rasterizada.
    - Em cada coluna e linha da imagem, um trecho de 7 a 45 cm é a espessura de uma parede, e o meio do trecho é o eixo.
    - Os eixos são unidos, prolongados até os encontros (L, T, X) e recebem os vãos.
    - Os lados de cada parede saem dos polígonos dos ambientes.
    - Unidades (apartamentos) = ambientes ligados por porta sem passar pelo núcleo.
    - Classificação inicial: fachada, divisa entre unidades e núcleo = estrutural; interna da unidade = vedação; pavimentos sem unidades = a definir; muros e pilares à parte.
    - Ajustes manuais em `obras/<obra>/ajustes_paredes.json`.
11. **Paginação** (`paginacao.py`): fiada a fiada, por linha de parede (paredes colineares unidas).
    - Cantos em L alternados; T com bloco especial; família 39 com bloco 34 no canto.
    - Vergas e contravergas em canaleta; cinta de respaldo (J na fachada).
    - Meio bloco junto a vãos nas fiadas pares; sobras fora do módulo contadas como corte.
    - Gera a comparação das famílias 29 e 39 e o ajuste que cada parede precisaria para fechar no módulo.
9. **Quantitativos** (`quantitativos.py`): contorno de cada ambiente classificado em parede, vão ou aberto (guarda-corpo, lado aberto).
   - Piso = área. Teto = área coberta.
   - Rodapé = contorno com parede − portas.
   - Parede bruta = contorno com parede × pé-direito. Parede líquida = bruta − vãos.
   - Na planilha, pé-direito, rodapé e paredes são fórmulas: mudar o pé-direito na aba Premissas recalcula tudo.

## Limitações conhecidas

- Depende de PDF vetorial com camadas no padrão do CAD (nomes AIA: `A-WALL`, `A-DOOR`…). PDF escaneado não funciona.
- Só mede ambientes que têm rótulo de área. Áreas de terreno (planta de locação), cobertura, fachadas e cortes ficam para depois.
- Paredes ortogonais. Vãos em paredes inclinadas não são fechados automaticamente.

Os arquivos das obras (`obras/`) ficam fora do git.
