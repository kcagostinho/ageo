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
| `medicao.xlsx` | Resumo por pavimento, ambientes (área do rótulo × medida, perímetro, status), esquadrias por tipo e dimensão, calibração da escala |
| `conferencia.html` | Prancha com cada ambiente desenhado e colorido pelo status, para conferência visual |
| `obra.json` | Tudo acima com os polígonos, para as próximas fases (lacunas, EAP) |

## Como mede

1. **Ingestão** (`leitor/ingestao.py`): traços por camada do CAD (`A-WALL`, `A-DOOR`, `A-GLAZ`…) e textos com coordenadas.
2. **Vistas** (`vistas.py`): separa as plantas de cada prancha e lê título e escala nominal.
3. **Escala** (`escala.py`): compara o valor de cada cota com o comprimento desenhado. A escala nominal não é usada para medir (no projeto-piloto o PDF estava 1,6% menor que 1:50).
4. **Ambientes** (`ambientes.py`): espaço livre entre paredes e esquadrias. Vãos de porta e janela fechados no alinhamento das faces da parede (pares de "tampas" de parede com porta, batente, vidro ou soleira entre elas). Folha de porta fechada como linha de apoio (`portas.py`). Faixas finas descartadas (miolo de parede, frestas). Linhas de piso só separam cômodos quando necessário.
5. **Conferência**: cada polígono é comparado com a área escrita no rótulo do arquiteto (ok ≤ 2%, conferir ≤ 10%, divergente > 10%).
6. **Esquadrias** (`esquadrias.py`): etiquetas `L x H` e peitoril.

## Limitações conhecidas

- Depende de PDF vetorial com camadas no padrão do CAD (nomes AIA: `A-WALL`, `A-DOOR`…). PDF escaneado não funciona.
- Só mede ambientes que têm rótulo de área. Áreas de terreno (planta de locação), cobertura, fachadas e cortes ficam para depois.
- Paredes ortogonais. Vãos em paredes inclinadas não são fechados automaticamente.

Os arquivos das obras (`obras/`) ficam fora do git.
