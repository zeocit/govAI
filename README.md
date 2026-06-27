# govAI

Mapeamento cientométrico do campo de produção da Governança Digital, com teoria de campos de Bourdieu como moldura analítica. Pós-doutorado de Fernando Leite na FGV EAESP (CEAPG, Área de Tecnologia e Governos), financiado pela FAPESP (processo 2023/13163-7), supervisão da Profa. Maria Alexandra Viegas Cortez da Cunha. Estágio BEPE na Danube University Krems, anfitriã Profa. Gabriela Viale Pereira.

Adapta a metodologia "Cientometria 2.0", desenvolvida para a Ciência Política brasileira, ao campo da Governança Digital.

## Pipeline

A ordem de execução está codificada no nome dos scripts. Esta sequência é referenciada pelo Manual Operacional, pelo Protocolo de Anotação e pelo pré-registro OSF, e é o que permite reproduzir o depósito Zenodo.

```
01a  coleta OpenAlex (periódicos do universo de fontes, 2000-2024)
02   limpeza estrutural
02b  detecção de retrações
02c  deduplicação fuzzy por título
02d  extração da estrutura de autoria (rede de coautoria)
02f  extração de referências citadas (rede de citações)
04a  pré-classificação LLM: cluster disciplinar (mono-rótulo)
04b  pré-classificação LLM: orientação epistemológica (três flags independentes)
04c  amostragem estratificada para o Gold Standard (Label Studio)
05   consolidação das anotações em Gold Standard (concordância entre anotadores)
06a  treino do classificador de cluster (BERTimbau, mono-rótulo)
06b  treino do classificador epistemológico (BERTimbau, multi-rótulo)
07   aplicação dos modelos ao corpus completo
09   exportação consolidada para Zenodo (.R)
```

Etapas posteriores (modelagem de tópicos com BERTopic, redes SBM/ERGM, prestígio por PageRank/eigenvector) entram quando o código correspondente for escrito.

## Camada epistemológica: dois eixos

A classificação epistemológica usa dois eixos ortogonais.

Eixo 1, orientação empírica: `epi_positivista` e `epi_interpretativa` (flags independentes), das quais se deriva `orientacao_proeminente` ∈ {positivista, interpretativa, mixed, nenhuma} por regra determinística (sem prioridade, sem DN-domina).

Eixo 2, registro doutrinário-normativo: `epi_doutrinario_normativa`, flag binária independente, com operacionalização disjuntiva (registro doutrinário OU normativo basta). Subtags diagnósticas `dn:modo`, `dn:norm`, `dn:ambos`.

A derivação determinística vive em `pipeline_v7/utils/derive_orientacao.py` (fonte única). Os limiares de concordância vivem em `pipeline_v7/utils/thresholds.py` (fonte única).

## Estrutura do repositório

```
pipeline_v7/      scripts numerados do pipeline + utils/ (módulos reutilizáveis)
lab-notebook/     caderno de laboratório (Open Science): um .md por achado/decisão
notebooks/        notebooks Colab (piloto, calibração)
pilot/            material do pré-teste
references/       snapshots PDF imutáveis por marco OSF (codebook, protocolos)
data/             esqueleto; conteúdo não versionado (ver .gitignore)
archive/legacy/   versões obsoletas preservadas
```

## Reprodutibilidade e governança

O Manual Operacional, o Codebook, os Guias de Anotação e o Protocolo são mantidos no Google Drive ("1 Metodologia") como superfície de edição. O repositório aponta para o canônico; `references/` guarda apenas snapshots PDF congelados por marco.

O pré-registro OSF (v2.0) e seus adendos são documentos com timestamp e DOI. Documentos registrados não se editam: qualquer mudança de limiar ou de schema entra como adendo nomeado, com assinatura da supervisora.

Cada script grava hash SHA-256 em `snapshot.json` para auditoria. As sementes são fixas (42, 123, 2026).

## Ambiente

Python via uv; R com renv. Pacotes-chave: pyalex, pandas, transformers (BERTimbau), BERTopic, irrCAC (R, IRR canônico), statnet (ergm, network, sna). LLM de pré-classificação via OpenRouter.

Variáveis de ambiente em `.env` (ver `.env.example`). Nunca versionar `.env`.

## Pré-registro, dados e citação

Pré-registro OSF: ver `references/osf/`. DOI a inserir após depósito.
Depósito de dados Zenodo: DOI a inserir após publicação.
Para citar este trabalho, ver `CITATION.cff`.

## Licença

Ver `LICENSE`.
