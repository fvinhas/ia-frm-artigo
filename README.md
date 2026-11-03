# IA nos Formulários de Referência das companhias abertas brasileiras (2023–2026)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23919753.svg)](https://doi.org/10.5281/zenodo.23919753)

Código, prompts e dados derivados do estudo sobre como as companhias abertas brasileiras falam de
inteligência artificial (IA) nos Formulários de Referência (FRE) entregues à CVM.

Autor: Felipe Domingues Vieira Vinhas ([ORCID 0009-0007-0461-7023](https://orcid.org/0009-0007-0461-7023)).
Artigo submetido à *H2D – Revista de Humanidades Digitais*: "Entre o uso e o risco: as narrativas sobre
inteligência artificial nos Formulários de Referência das companhias abertas brasileiras (2023–2026)".
O material suplementar S2 citado no artigo está em [`SUPLEMENTAR.md`](SUPLEMENTAR.md).

*English summary.* Code, prompts and derived data for a study of how Brazilian listed companies
write about artificial intelligence in the Reference Forms (Formulário de Referência) they file with
the Brazilian Securities and Exchange Commission (CVM), 2023–2026. The pipeline downloads the forms, extracts the
text by section, detects AI mentions with a layered dictionary and classifies each passage with a
large language model validated against a human gold standard. Everything runs on public documents;
there are no human participants.

## O que tem aqui

| Pasta ou arquivo | Conteúdo |
| --- | --- |
| `*.py` | O pipeline, do download às figuras (etapas abaixo) |
| `prompts/` | Prompts do classificador: `classificador_v1.md`, `v2` (descartado) e `v3` (final) |
| `dados_publicos/corpus/` | Resumo por companhia-ano (`resumo_AAAA.csv`: universo de formulários e menções), 2023–2026 |
| `dados_publicos/anotacao/` | População de trechos, amostra, padrão-ouro, lotes que o classificador leu e o que respondeu |
| `dados_publicos/resultados/` | Validação, tabelas da população classificada e índices por companhia-ano |
| `dados_publicos/h2d/` | Figuras do artigo (PNG e SVG) e os dados de cada figura (`dados_figuras.xlsx`) |
| `SUPLEMENTAR.md` | Material suplementar S2: revocação, desenho do padrão-ouro, adjudicação, deriva, correção e modelo aberto |
| `modelo_aberto.py`, `dados_publicos/anotacao/llm_aberto/` | Comparação com um modelo aberto (Gemma 4 via Ollama), reaplicável num computador pessoal |

Não estão aqui, por tamanho, os ZIPs baixados da CVM (~25 GB) nem o texto extraído
(`secoes_AAAA.jsonl`, ~1,2 GB). O pipeline refaz os dois a partir dos dados abertos da CVM.

## Números principais

| | 2023 | 2024 | 2025 | 2026 |
| --- | --- | --- | --- | --- |
| Formulários (última versão por companhia) | 717 | 721 | 700 | 655 |
| Trechos válidos com IA | 410 | 547 | 832 | 1.576 |
| Companhias que citam IA | 18,0% | 21,5% | 27,1% | 36,3% |
| Companhias que tratam a IA como risco | 1,8% | 5,4% | 10,0% | 18,9% |

Índice de 2026 congelado em 25/10/2026. Dicionário revisto em 30/10/2026: "chatbot", "assistente virtual"
e "modelo preditivo" sem nomear IA passaram a termos vizinhos (decisão tomada a partir da anotação dupla).

Alguns números do artigo não saem dos arquivos de `dados_publicos/`, porque dependem dos dados brutos da CVM
(ZIPs, texto extraído `secoes_AAAA.jsonl` e menções `mencoes_AAAA.csv`, que não são publicados). Para refazê-los,
rode o pipeline com os dados da CVM:

| Número no artigo | Origem |
| --- | --- |
| Páginas de texto por ano e total de 544.887 (Tabela 1); cerca de 200 mil páginas das seções 1, 2.10 e 4 sem termo; ligaduras em cerca de mil páginas por ano | `secoes_AAAA.jsonl` (etapa 3) |
| 233 trechos (6,4%) retirados pela revisão do dicionário | diferença entre a população gerada com o `dicionario.py` atual e a gerada com "chatbot", "assistente virtual" e "modelo preditivo" de volta à camada `IA` (etapa 4); o efeito nas proporções por companhia está em `resultados/complementares/sensibilidade_dicionario.csv` |
| Queda da sigla "AI" de 746 para 38 em 2025; 15 ocorrências de "IA" lidas | detecção com e sem as listas `EXCLUSOES` e `SECOES_SEM_SIGLA_AI` (etapa 4) |
| 1.152 documentos da primeira versão; datas medianas de entrega | `baixar_fre.py --primeira` e índices `fre_cia_aberta_AAAA.csv` da CVM; o resumo por ano está em `resultados/complementares/versoes_fre.csv` |
| 41 registros cancelados entre as 59 companhias que saem de 2025 para 2026 | cadastro da CVM (`cad_cia_aberta.csv`, situação e data de cancelamento) cruzado com `corpus/resumo_2025.csv` e `resumo_2026.csv` |
| Três companhias nos trechos de revocação; limite superior de cerca de 1.150 menções implícitas | `revocacao.py` sobre o texto integral |

## Instalação

Testado com Python 3.9.6; o `requirements.txt` fixa as versões exatas usadas no estudo:

```
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Etapas

Os comandos supõem os dados em `dados/`.

1. **Índice anual.** Baixe `fre_cia_aberta_AAAA.zip` em
   <https://dados.cvm.gov.br/dataset/cia_aberta-doc-fre>, descompacte em `dados/fre_AAAA/` e baixe o
   cadastro (`cad_cia_aberta.csv`) em <https://dados.cvm.gov.br/dataset/cia_aberta-cad>.
2. **Download** da versão mais recente de cada companhia. Retomável; o gargalo é o servidor da CVM
   (~8 documentos por minuto com 4 conexões). Se aparecerem falhas, rode de novo.
   `python baixar_fre.py dados/fre_2025/fre_cia_aberta_2025.csv dados/zips_2025`
3. **Extração por seção.** Cada seção narrativa vem como PDF dentro do XML do formulário; a tag
   identifica a seção (`secoes_fre.py`). Também lê o formato antigo do Empresas.NET.
   `python extrair_secoes.py dados/zips_2025 dados/secoes_2025.jsonl`
4. **Detecção de menções** em três camadas (`ia`, `ia_gen`, `vizinhos`), com as regras de exclusão
   das siglas em `dicionario.py`. Unidade: o trecho (a frase com o termo, mais uma antes e uma depois).
   `python detectar_mencoes.py dados/secoes_2025.jsonl dados/mencoes_2025.csv dados/resumo_2025.csv`
5. **Amostra para o padrão-ouro** (estratificada, semente fixa).
   `python amostrar_anotacao.py dados dados/cad_cia_aberta.csv dados/anotacao 2023 2024 2025 2026`
6. **Validação e classificação** (`verificacao.py`, subcomandos `cega`, `lotes`, `juntar`,
   `planilha`, `comparar`, `ouro`, `populacao`). Ver "Classificador" abaixo.
7. **Análise** (e correção pelo padrão-ouro: `python correcao_ouro.py dados/anotacao/populacao_v1.csv dados/anotacao/classificacoes_llm_v3.csv dados/anotacao/ouro_v1.csv dados/anotacao/correcao_v3.csv 2000 dados/anotacao/dupla_v2`). `python analise_v3.py dados/anotacao/populacao_v1.csv dados/anotacao/classificacoes_llm_v3.csv dados/anotacao/ouro_v1.csv dados/anotacao dados`
8. **Figuras, tabelas e exemplos.** `python figuras_tabelas_h2d.py dados dados/h2d` e
   `python exemplos_h2d.py dados/anotacao/ouro_v1.csv dados/h2d/exemplos_h2d.xlsx`
9. **Esta publicação.** `python exportar_publico.py dados dados_publicos`

## Classificador e validação

Cada trecho é classificado em cinco dimensões: função (produtividade, uso, negócio, risco,
governança, genérica), evidência, governança declarada, tom e tempo. O guia de anotação v1 está nos
prompts. No artigo, a função genérica (código `GENERICA`) passou a se chamar **contextual**, para não
confundi-la com o adjetivo "genérico" aplicado aos riscos pouco específicos; os códigos nos dados não mudaram.

- **Padrão-ouro:** 808 trechos estratificados por ano e grupo de seção, com estrato próprio de IA
  generativa. O autor anotou 100 trechos às cegas, sem ver a saída do modelo, e verificou os outros
  708 dimensão por dimensão. A concordância nos 100 cegos é a medida de acurácia; a diferença em
  relação aos verificados mede o efeito de ancoragem.
- **Anotação dupla às cegas (v2):** 200 trechos novos, fora do padrão-ouro, estratificados pela classe
  prevista, codificados de forma independente pelo autor e por um segundo anotador não identificado pelo nome (economista independente, com experiência em auditoria)
  (`anotacao_v2.py`), sem ver o modelo; divergências adjudicadas pelo autor, também sem ver o modelo
  (`dupla_v2.py comparar` e `consenso`). Na população atual (183 trechos), α entre os anotadores:
  função 0,708, evidência 0,780, tom 0,691, tempo 0,682, governança 0,862, falso positivo 0,957.
  Modelo × consenso: 0,894, 0,819, 0,891, 0,872, 0,882 e 0,957. Tipo de risco principal (100 trechos):
  α 0,908 entre os anotadores; 0,921 e 0,961 do modelo com cada um. Códigos em
  `dados_publicos/anotacao/dupla_v2/`.
- **Modelo:** Claude Opus 5.5 (`claude-opus-5-5`), rodado por subagentes do Claude Code em outubro de
  2026, sem API. Cada subagente leu só o prompt e o seu lote de 50 trechos (`dados_publicos/anotacao/llm_vN/entrada_XX.jsonl`)
  e escreveu `saida_XX.jsonl`. Sem API não há controle de temperatura; por isso os lotes e as saídas
  estão publicados inteiros. O v2 piorou a concordância nos cegos e foi descartado; o v3 (v1 mais
  duas regras de falso positivo) classificou o corpus.
- **Resultado (v3, cegos do padrão-ouro, 97 na população atual):** α de Krippendorff de 0,860 (função),
  0,817 (evidência), 0,838 (tom), 0,824 (tempo) e 0,814 (governança). Detalhes em `dados_publicos/resultados/validacao_v3.csv`.
- **Correção pelo padrão-ouro:** `correcao_ouro.py` corrige as proporções da população com o
  estimador de diferença ponderado pela amostra-ouro (Egami et al., 2023), com intervalos de 95% por
  bootstrap, em três versões (ouro inteiro, só os cegos e o consenso da anotação dupla somado ao ouro). Resultado em
  `dados_publicos/resultados/correcao_v3.csv`.
- **Robustez:** `robustez.py` reclassifica 200 trechos com um prompt que não vê a seção nem a companhia
  (`prompts/classificador_v3_semsecao.md`; lotes e saídas em `dados_publicos/anotacao/llm_semsecao/`) e
  mede a repetição de trechos entre companhias (semelhança de Jaccard em sequências de cinco palavras).
  Resultados em `dados_publicos/resultados/robustez_semsecao.csv` e `repeticao_v3.csv`.
- **Análises complementares de robustez (30/10/2026):**
  - `robustez.py repeticao_base`: linha de base da repetição (janelas da seção 4 sobre outros riscos
    recorrentes, centradas em câmbio, juros, clima, segurança cibernética etc.), limiares 0,3/0,5/0,7 e
    persistência ano a ano → `resultados/repeticao_base_v3.csv`. A repetição exclui também pares do mesmo
    grupo econômico, pelos controladores majoritários declarados no FRE (`robustez.grupos`).
  - `robustez.py rodada2_lotes|rodada2_comparar`: segunda execução independente do classificador em 300
    trechos (`anotacao/llm_v3_rodada2/`) → `resultados/rodada2_v3.csv`.
  - `complementares.py`: dicionário atual × anterior, função com peso igual por companhia, denominadores da
    governança, verbos modais e anos explícitos contados no texto, versões do FRE → `resultados/complementares/`.
  - `correcao_ouro.py`: proporções truncadas em [0, 100] e bootstrap da anotação dupla no ano;
    `resultados/tabela_S1_correcao.csv` é a Tabela S1 citada no artigo.
  - `revocacao.py`: revocação da IA nomeada (`variantes`: grafias e termos alternativos no texto integral →
    `resultados/revocacao_variantes_resumo.csv`; `paginas`: 120 páginas sem nenhum termo para leitura humana) e
    menções implícitas (`amostra`: 120 trechos da camada de vizinhos).
  - `robustez.py grupos`: mapa companhia → grupo econômico (cadeia de controle majoritário declarada no FRE) e
    contagem de grupos distintos → `resultados/complementares/mapa_grupos.csv` e `contagem_grupos.csv`.
  - `sensibilidade_versao.py` (com `baixar_fre.py --primeira`): refaz 2023 e 2026 com a primeira versão de cada
    formulário; os 116 trechos novos foram classificados com o v3 (`anotacao/llm_v3_primeira/`) →
    `resultados/complementares/sensibilidade_versao.csv`.

## Reaplicar com um modelo aberto

O classificador do estudo é proprietário. Para reaplicar o procedimento sem ele, use o modelo aberto avaliado no
artigo (seção 4.5; detalhes em `SUPLEMENTAR.md`, S2.6), em qualquer sistema com [Ollama](https://ollama.com) e cerca
de 10 GB livres de memória:

```
ollama pull gemma4:12b-it-q4_K_M
python modelo_aberto.py classificar gemma4:12b-it-q4_K_M dados_publicos/anotacao dupla saida/gemma
python modelo_aberto.py comparar dados_publicos/anotacao saida/gemma
```

Use a tag completa `gemma4:12b-it-q4_K_M` (GGUF): é o mesmo arquivo em qualquer sistema e aceita saída estruturada. No
Mac, a tag curta `gemma4:12b` baixa outra quantização, com resultados diferentes. Na amostra de teste, o Gemma 4
concordou na função com cada anotador no nível dos anotadores entre si (α 0,70 e 0,72 contra 0,71), mas abaixo do
Claude contra o consenso (0,69 contra 0,89).

## Dados de administradores

Os trechos das seções 7 (assembleia e administração), 8 (remuneração) e 13 (declarações) podem citar
administradores pelo nome. Nos arquivos publicados, o texto desses trechos (51 na população e 5 entre os
que só existem na primeira versão do formulário, em `anotacao/llm_v3_primeira/`) e as justificativas e
comentários sobre eles aparecem como "[omitido…]"; os códigos ficam. O texto está no FRE original,
no site da CVM.

## Licenças

- Código: MIT (`LICENSE`).
- Dados em `dados_publicos/`: derivados dos dados abertos da CVM, publicados sob a Open Database
  License (ODbL 1.0); seguem a mesma licença (`dados_publicos/LICENCA.md`).

## Como citar

Vinhas, F. D. V. (2026). *IA nos Formulários de Referência das companhias abertas brasileiras
(2023–2026): código, prompts e dados* (Versão 1.1.0) [Software]. Zenodo. https://doi.org/10.5281/zenodo.23919753

Esse DOI geral aponta sempre para a versão mais recente. Cada release é arquivada no Zenodo com um DOI próprio;
para citar uma versão específica, use o DOI dela (lista abaixo). O artigo submetido à H2D cita a versão 1.1.0:
https://doi.org/10.5281/zenodo.23925565. Ver também `CITATION.cff`.

## Versões

| Versão | DOI | O que mudou |
| --- | --- | --- |
| 1.1.0 | [10.5281/zenodo.23925565](https://doi.org/10.5281/zenodo.23925565) | Comparação com modelo aberto (`modelo_aberto.py`, Gemma 4 via Ollama; S2.6); figuras 2 e 3 com a função "contextual" (código `GENERICA`), "<1" para valores que arredondam a zero e bordas uniformes; material suplementar S2 (`SUPLEMENTAR.md`); versões exatas no `requirements.txt`; metadados do Zenodo e do `CITATION.cff` em português e inglês. Nenhum resultado da versão 1.0.0 mudou. |
| 1.0.0 | [10.5281/zenodo.23919754](https://doi.org/10.5281/zenodo.23919754) | Primeira versão pública. |
