# Pré-teste Posturas Epistemológicas

Pasta de calibração da camada epistemológica do projeto *Cientometria 2.0 / Campo de Produção da Governança Digital* (FAPESP 2023/13163-7). Contém os documentos e a planilha para a sessão de calibração inter-anotador que precede a anotação completa do Gold Standard.

---

## Arquivos ativos

| Arquivo | Função |
| --- | --- |
| `1_Protocolo_Calibracao_Epi_v2.docx` | Protocolo da calibração: desenho, critério de entrada (α_DN ≥ 0,667), métricas, produtos esperados. Documento de referência do coordenador. |
| `Tutorial_Calibracao_Epi_v2.docx` | Passo a passo para o anotador: como abrir a planilha, o que preencher, como exportar. Distribuir a ann1 e ann2 antes da sessão. |
| `3_Guia_Anotacao_Posturas_v4.docx` | Definições operacionais das três categorias (EE, IC, DN), regra de ouro, heurísticas, exemplos anotados. Instrumento de referência durante a anotação. **Nota:** o critério DN é disjuntivo, registre a faceta em notas (`dn:modo`, `dn:norm` ou `dn:ambos`). |
| `govai_calibracao_colab.ipynb` | Notebook Colab para cálculo do α de Krippendorff por categoria (α_EE, α_IC, α_DN) e distribuição dos rótulos. Rodar depois de exportar as planilhas dos dois anotadores. |
| `anotacao_calibracao.csv` | Planilha de anotação: 25 artigos pré-carregados com `doc_id`, `titulo`, `abstract` e demais metadados. Colunas `epi_positivista`, `epi_interpretativa`, `epi_doutrinario_normativa`, `confianca` e `notas` em branco, para preenchimento pelos anotadores. |

### Sequência de execução

1. Anotador recebe `Tutorial_Calibracao_Epi_v2.docx` + `3_Guia_Anotacao_Posturas_v4.docx` + `anotacao_calibracao.csv`.
2. Cada anotador preenche sua cópia da planilha independentemente e exporta como `calib_ann1.csv` / `calib_ann2.csv`.
3. Coordenador roda `govai_calibracao_colab.ipynb` com os dois CSVs para calcular α por categoria.
4. Aplicar o critério de entrada (§6 do Protocolo): α_DN ≥ 0,667 para prosseguir, caso contrário refinar o Guia e recalibrar.
5. Discussão conjunta das divergências; linha de consenso salva como `calib_gold.csv`.

---

## Arquivos arquivados

Os arquivos abaixo pertencem a uma etapa anterior: o piloto formal de comparação tipológica entre o esquema binário (EE/IC + DN derivado) e o ternário mutuamente exclusivo (EE/IC/DN). Essa decisão foi tomada em bases conceituais antes da anotação, tornando o piloto desnecessário. Estão mantidos como registro histórico; não devem ser usados na calibração atual.

| Arquivo | Por que arquivado |
| --- | --- |
| `1_protocolo_piloto_tipologia.docx` | Protocolo do piloto de decisão tipológica. Substituído pelo `1_Protocolo_Calibracao_Epi_v2.docx`. |
| `2_tutorial_piloto_govai.pdf` | Tutorial do piloto (BERTimbau, silhouette, F1_DN B1 vs. B2). Sem uso na calibração atual. |
| `3_guia_anotacao_posturas_v3.docx` | Guia do piloto com Chave A / Chave B e DN derivado por exclusão. Substituído pelo `3_Guia_Anotacao_Posturas_v4.docx`. Atenção: apesar do nome semelhante, é outro documento com outra estrutura. |
| `govai_pilot_colab.ipynb` | Notebook do piloto (análise de separabilidade por embeddings). Pode ser mantido se houver interesse futuro na análise de validade convergente (silhouette/ARI); caso contrário, descartar. |
| `sample.csv` | Amostra do piloto (199 artigos, duas subamostras: prevalência e reforço DN). Não é a planilha de calibração. |

Sugestão: mover para uma subpasta `arquivo/` para não aparecerem no mesmo nível dos arquivos ativos.

---

## Notas técnicas

- **Escala `confianca`:** 1 (baixa), 2 (razoável), 3 (alta). Não há nível 0. Quando `confianca = 1`, a coluna `notas` é obrigatória.
- **Critério DN disjuntivo:** basta `dn:modo` (argumentação doutrinal/conceitual) ou `dn:norm` (prescrição normativa) para `epi_doutrinario_normativa = 1`. Quando ambos presentes: `dn:ambos`. Registrar em `notas`.
- **Cálculo de α:** pacote `irrCAC` (R), canônico per DA-06 do Codebook. O gate de calibração (0,667) é mais exigente que o gate do Gold Standard (0,55), por ser filtro inicial de desenvolvimento do instrumento.
- **Claude não participa como anotador:** criaria circularidade (coautorou o Codebook); o α mediria consistência humano-LLM, não confiabilidade inter-humana.
- **Sign-off pendente:** o limiar α_DN ≥ 0,667 requer aprovação da Profa. Cunha (Addendum 2 ao pré-registro OSF) antes do início da calibração.
