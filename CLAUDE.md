# CLAUDE.md

Instruções persistentes para sessões de Claude no repositório govAI. Leia antes de editar qualquer coisa.

## Projeto

Mapeamento cientométrico do campo da Governança Digital, teoria de campos de Bourdieu como moldura. Pós-doc de Fernando Leite, FGV EAESP / CEAPG, FAPESP 2023/13163-7. Supervisão: Profa. Maria Alexandra Viegas Cortez da Cunha. BEPE: Profa. Gabriela Viale Pereira (Danube University Krems). Segundo anotador: Vittorio (confirmado).

## Estilo (não negociável)

- Nunca usar travessão (em-dash). Usar vírgula, dois-pontos, parênteses ou ponto e vírgula.
- Documentos em PT-BR formal, limpo, minimalista, sem floreios nem linguagem genérica de IA.
- Não começar respostas com elogio ou concordância ritual. Primeira frase entrega a informação mais útil.
- Papel: par intelectual crítico e sênior. Questionar pressupostos, apontar lacunas, não validar por deferência.
- Nunca fabricar referências, autores, títulos, URLs, citações, estatísticas, nomes de função ou API.

## Documentos Word

- Markdown → pandoc → .docx com `--reference-doc=reference.docx` (Avenir Next como fonte do tema).
- Avenir Next Regular, exceto código/markdown/similares.
- Número de versão apenas no nome do arquivo, nunca no corpo do documento.
- Os docx canônicos (Manual, Codebook, Guias, Protocolo) vivem no Google Drive ("1 Metodologia"), não no repo. `references/` guarda só snapshots PDF congelados por marco OSF.

## Tipologia epistemológica: dois eixos

- Eixo 1 (orientação empírica): `epi_positivista`, `epi_interpretativa` independentes; deriva-se `orientacao_proeminente` ∈ {positivista, interpretativa, mixed, nenhuma} por regra determinística. Sem prioridade, sem DN-domina.
- Eixo 2 (registro doutrinário-normativo): `epi_doutrinario_normativa`, flag binária independente, operacionalização DISJUNTIVA (doutrinário OU normativo). Subtags `dn:modo`/`dn:norm`/`dn:ambos`.
- `mixed` só quando pos=1 E int=1 E DN=0. (0,0,0) → `inconclusiva`.
- Fonte única da derivação: `pipeline_v7/utils/derive_orientacao.py`. Não duplicar a lógica em outro script.

## Limiares de concordância

- Fonte única: `pipeline_v7/utils/thresholds.py`. Não hardcodar alfas em script algum; importar de lá.
- `ALPHA_GATE_CLUSTER=0.67`, `ALPHA_GATE_EPI=0.55`, `ALPHA_CALIB_DN_FLOOR=0.667` (era 0.40), `KAPPA_REF=0.61` (diagnóstico), `POS_WEIGHT_CAP=10.0` (provisório).
- O piso de calibração de DN (0.667) EXCEDE o gate epi (0.55). Inversão deliberada, documentada no Addendum 2. Não "corrigir" silenciosamente.

## Pipeline

Ordem codificada no nome dos scripts: `01a 02 02b 02c 02d 02f 04a 04b 04c 05 06a 06b 07 09`. Esta ordem é referenciada pelo Manual, Protocolo e OSF. Não renomear nem reorganizar em módulos temáticos sem decisão explícita: a sequência numerada é dispositivo de reprodutibilidade.

## Lab Notebook

- Um arquivo .md por achado ou decisão relevante para replicabilidade, em `lab-notebook/`.
- Nome: `YYYY-MM-DD_short-title.md`. Título e conteúdo em inglês.
- Formato: data ISO 8601, título descritivo, contexto, o que foi feito, resultado/observação, próximos passos.
- Gerar entrada sempre que houver decisão metodológica, experimento, resultado, mudança de direção, código modificado ou nova fonte de dados.

## Governança OSF

- Documentos registrados (Pré-registro v2.0, Addendum 1) têm timestamp e DOI. NUNCA editar.
- Qualquer mudança de limiar ou schema entra como adendo nomeado, com assinatura da Profa. Cunha antes do início da anotação.

## Credenciais e push

- Claude NÃO manuseia tokens, chaves de API ou senhas. Não inserir credencial em URL de remote, credential helper ou qualquer campo.
- Push autenticado é feito por Fernando, na máquina dele. Claude gera os arquivos e o bloco de comandos `git`; Fernando executa.
- `.env` nunca é versionado.

## Pendências vivas (atualizar conforme avança)

- Contaminação do cluster Law (~360 artigos, ~99% STEM): remediar depois de fechar os scripts. Não reabrir a hipótese lexical.
- Apêndice metodológico (dois eixos, limiares, regra disjuntiva DN) com base no Lab Notebook.
- Refactor para pacote instalável (`src/govai/` + pyproject.toml) depois da primeira calibração.
