#!/usr/bin/env bash
# Regera todos os dados, gráficos e o relatório.
# Uso: ./gerar.sh dados_tse/votacao_secao_2026_BR.zip [--cargo Presidente] [--turno 1]
set -euo pipefail
cd "$(dirname "$0")"
python scripts/gerar_dados.py "$@"
python scripts/gerar_relatorio.py
