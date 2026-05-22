#!/bin/bash
cd "$(dirname "$0")"

# Força o Git a adicionar os arquivos ignorando a interpretação de caminhos do shell
git add --all :/

# Cria o commit com a data atual
git commit -m "Auto-sync: $(date '+%Y-%m-%d %H:%M:%S')"

# Envia para o GitHub
git push origin main
