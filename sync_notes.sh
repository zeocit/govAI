#!/bin/bash
# Entra na pasta do Lab Notebook (garante o caminho correto)
cd "$(dirname "$0")"

# Adiciona todos os arquivos novos ou modificados
git add .

# Cria um commit com a data e hora atual do sistema
git commit -m "Auto-sync: $(date '+%Y-%m-%d %H:%M:%S')"

# Envia para o GitHub na branch main
git push origin main
