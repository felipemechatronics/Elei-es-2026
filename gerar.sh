#!/usr/bin/env bash
# Regera dados, gráficos e relatórios de todos os cargos a partir dos arquivos em dados_tse/.
set -euo pipefail
cd "$(dirname "$0")"
python scripts/gerar_dados.py dados_tse/Urnas_Presidente.xlsx --cargo Presidente
python scripts/gerar_dados.py dados_tse/votacao_secao_2026_RN.csv --cargo Governador --anulados 50,29
python scripts/gerar_relatorio.py
python scripts/gerar_deputados.py dados_tse/votacao_secao_2026_RN.csv
python scripts/gerar_lula.py dados_tse/Urnas_Presidente.xlsx dados_tse/votacao_secao_2026_RN.csv
