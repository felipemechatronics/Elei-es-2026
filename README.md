# Como o RN votou em 2026

Resultados das eleições de 2026 no Rio Grande do Norte por município, bairro e local de votação, a partir dos boletins por seção do TSE.

**Conteúdo atual: Governador, 1º turno (4/10/2026).** O projeto foi feito para qualquer cargo majoritário. Para gerar a versão de Presidente, basta rodar os scripts com o arquivo da eleição federal (veja [Gerar para Presidente](#gerar-para-presidente)).

- **Site interativo** (`docs/`): mapa do estado que desce até os bairros e locais de votação, destaques, gráficos e tabela de todos os municípios. Feito para o GitHub Pages.
- **Relatório** ([`relatorio/RELATORIO.md`](relatorio/RELATORIO.md)): o mesmo conteúdo em texto, tabelas e figuras estáticas, legível direto no GitHub.
- **Dados** (`docs/dados/`): resultados por município, bairro e local de votação em CSV.

![Quem ficou à frente em cada município](relatorio/img/mapa_vencedor.png)

![Bairros das maiores cidades](relatorio/img/bairros_maiores_cidades.png)

## Publicar no GitHub Pages

1. Crie um repositório e envie esta pasta (`git init`, `git add .`, `git commit`, `git push`).
2. No GitHub, abra **Settings → Pages**, escolha **Deploy from a branch**, branch `main` e pasta `/docs`.
3. O site fica em `https://<seu-usuario>.github.io/<nome-do-repositorio>/`.

## Regerar os dados

Requer Python 3.10+.

```bash
pip install -r requirements.txt
# baixe o votacao_secao do TSE e coloque em dados_tse/ (CSV ou ZIP)
./gerar.sh dados_tse/votacao_secao_2026_RN.csv --cargo Governador --anulados 50,29
```

Esse é o comando que gerou a versão atual. Os votos dos candidatos 50 e 29 foram anulados na totalização e contam como nulos; com isso, os totais batem exatamente com o projeto de referência, por município e por local de votação.

## Gerar para Presidente

O arquivo `votacao_secao` da eleição estadual não traz os votos para Presidente: eles ficam no arquivo da eleição geral **federal** do TSE (coluna `DS_CARGO` = "Presidente"). Com ele em `dados_tse/`:

```bash
./gerar.sh dados_tse/<arquivo da eleição federal>.zip --cargo Presidente --turno 1
```

O script filtra o RN sozinho, então serve tanto o arquivo do RN quanto o nacional. Para nomes de urna, crie `config/candidatos_presidente.json` (mesmo formato de `config/candidatos_governador.json`). Para o 2º turno, use `--turno 2`.

`gerar.sh` roda dois scripts:

| Script | O que faz |
|---|---|
| `scripts/gerar_dados.py` | Lê o arquivo do TSE, filtra cargo, UF e turno, soma por local, bairro e município e grava `docs/dados.js`, os CSVs e `relatorio/resumo.json`. |
| `scripts/gerar_relatorio.py` | Gera as figuras em `relatorio/img/` e o `relatorio/RELATORIO.md`. |
| `scripts/extrair_base.py` | (Só uma vez) monta a base geográfica em `base/` a partir do projeto de referência. |

Opções úteis de `gerar_dados.py`:

- `--anulados 50,29`: números de candidatos com registro indeferido ou cassado; os votos deles passam a contar como nulos, como na totalização do TSE. O arquivo por seção não traz essa informação.
- `config/candidatos_<cargo>.json`: nomes de urna e partidos, para corrigir os nomes curtos gerados automaticamente a partir do nome completo. Exemplo: `{"13": {"nome": "Fulano", "partido": "PT"}}`.

Os arquivos brutos do TSE ficam fora do Git (`.gitignore`), porque passam do limite de 100 MB por arquivo do GitHub.

## Estrutura

```
base/        municípios, bairros e locais de votação georreferenciados (não depende do cargo)
config/      ajustes opcionais de nomes e partidos
dados_tse/   arquivos brutos do TSE (não versionados)
docs/        site do GitHub Pages: index.html, dados.js e CSVs
relatorio/   RELATORIO.md, resumo.json e figuras
scripts/     geração dos dados e do relatório
```

## Metodologia

- Percentuais de candidatos são calculados sobre os votos válidos. Comparecimento e abstenção, sobre o eleitorado apto. Brancos e nulos, sobre o comparecimento.
- O voto é atribuído ao local onde o eleitor vota, e não ao endereço onde mora.
- Cada local de votação é posicionado pela coordenada do cadastro do TSE e atribuído ao bairro do IBGE (Censo 2022) que o contém. Locais sem coordenada válida aparecem em posição aproximada e não entram em nenhum bairro. Só há bairros nos municípios que têm bairros delimitados pelo IBGE.
- O partido é inferido pelo número de urna do candidato.

## Fontes e créditos

- Votos por seção e cadastro de locais de votação: [TSE, Portal de Dados Abertos](https://dadosabertos.tse.jus.br/).
- Malhas de municípios e bairros: [IBGE](https://www.ibge.gov.br/geociencias/downloads-geociencias.html).
- Base geográfica (coordenadas dos locais, atribuição de bairros e eleitorado apto) organizada a partir do projeto [Como o RN votou para governador](https://sousapfe.github.io/eleicoesRN/) ([repositório](https://github.com/sousapfe/eleicoesRN)), de Peterson Sousa.
- Gráficos e mapas com [D3](https://d3js.org/) e matplotlib.
