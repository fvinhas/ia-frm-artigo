# Material suplementar S2: detalhes da detecção e da validação

Complementa as seções 4.2 e 4.5 do artigo "Entre o uso e o risco: as narrativas sobre inteligência artificial nos
Formulários de Referência das companhias abertas brasileiras (2023–2026)", submetido à *H2D – Revista de Humanidades
Digitais*. A Tabela S1 (correção das proporções) está em `dados_publicos/resultados/tabela_S1_correcao.csv`.

Nos dados, a função que o artigo chama de **contextual** tem o código `GENERICA` (referência vaga, aspiracional ou de
contexto, sem prática da própria companhia). O nome mudou no artigo para não confundir a função com o adjetivo
"genérico", usado para os riscos pouco específicos.

## S2.1 Revocação da IA nomeada e menções implícitas (seção 4.2)

- **Grafias alternativas.** Buscamos no texto integral, nas páginas sem nenhuma menção detectada, grafias e termos
  alternativos ("I.A.", "A.I.", palavras quebradas pela extração, nomes de modelos como GPT ou Claude). Só sete trechos
  nomeavam a IA, de três companhias que já constavam como citando IA no mesmo ano (`revocacao.py variantes` →
  `resultados/revocacao_variantes_resumo.csv`).
- **Páginas sem termo.** Como verificação qualitativa, nenhuma de 120 páginas sorteadas entre as cerca de 200 mil
  páginas das seções 1, 2.10 e 4 sem nenhum termo nomeava a IA (`revocacao.py paginas`).
- **Menções implícitas** (IA descrita sem ser nomeada; fora do estudo por definição). A leitura de 120 trechos da
  terceira camada do dicionário encontrou um que descrevia IA sem nomeá-la e seis em dúvida. A estimativa pontual é de
  cerca de 90 trechos na população (2,7% dos trechos com IA nomeada). Contando as dúvidas, chega a cerca de 770; o
  limite superior de 95% da amostra, a cerca de 1.150, um terço dos trechos nomeados. O discurso de IA não nomeada é
  provavelmente pequeno, mas a estimativa é imprecisa com 120 leituras (`resultados/revocacao_leituras_resumo.csv`).
- **Revisão do dicionário.** A transferência de "chatbot", "assistente virtual" e "modelo preditivo" para a terceira
  camada excluiu 233 trechos (6,4%): 12,8% dos trechos de 2023 e 3,5% dos de 2026
  (`resultados/complementares/sensibilidade_dicionario.csv`).

## S2.2 Desenho do padrão-ouro (seção 4.5)

808 trechos sorteados da população com semente fixa, estratificados por ano e grupo de seção, com um estrato próprio
para a IA generativa. A alocação é proporcional à raiz do tamanho de cada estrato, com pelo menos 15 trechos por
estrato e no máximo quatro trechos por companhia em cada ano. Os pesos amostrais permitem reponderar as estimativas
(`amostrar_anotacao.py`). Após a revisão do dicionário, 751 trechos da amostra permanecem na população.

## S2.3 Critérios da adjudicação na anotação dupla (seção 4.5)

O segundo anotador recebeu uma planilha com as mesmas definições e regras de desempate do guia que orienta o *prompt*,
sem as saídas do modelo, e treinou com 15 casos e gabarito do autor. A adjudicação das divergências coube ao autor,
feita à mão e sem consultar a saída do modelo. Nas 41 divergências de função entre trechos que nenhum dos dois marcou
como falso positivo, o consenso ficou com o rótulo do segundo anotador em 30, com o do autor em 10 e com um terceiro
rótulo em uma (`dados_publicos/anotacao/dupla_v2/`).

O critério foi a aplicação estrita das definições do guia a cada trecho:

- uma aplicação de IA identificada da própria companhia conta como **uso** mesmo sem implantação concluída (exemplo:
  um sistema em desenvolvimento para verificar equipamentos de proteção individual);
- IA integrada a serviços oferecidos aos clientes conta como **negócio**, ainda que o trecho cite ganhos de eficiência
  (exemplo: uma plataforma de automação vendida a clientes);
- benefícios atribuídos à IA no setor ou na tecnologia em geral, sem iniciativa da companhia, contam como menção
  **contextual**, não como produtividade (exemplo: a definição de Indústria 4.0 com seus benefícios);
- **produtividade** fica reservada aos trechos que atribuem à IA um ganho específico da própria companhia (exemplo:
  licenças de assistente de IA associadas à eficiência administrativa).

## S2.4 Deriva do codificador (seção 4.5)

A concordância entre o modelo e o autor é menor na amostra de teste do que nos trechos cegos do desenvolvimento (α de
0,71 contra 0,86 na função). Parte da diferença vem das cotas, que concentram classes difíceis, mas ela persiste com a
ponderação amostral (acordo de 74% contra 89%) e coincide com uma codificação mais ampla de produtividade pelo autor na
amostra de teste (44 trechos, contra 27 do segundo anotador e 29 do modelo). Uma deriva do codificador entre as duas
anotações é a explicação mais plausível. Se for deriva, ela também alcança o padrão-ouro e o consenso, ambos
dependentes do autor; por isso as correções da S2.5 são lidas como análise de sensibilidade, e não como valores
verdadeiros.

Na Tabela 2 do artigo, o acordo na função entre os anotadores e entre o modelo e o autor é idêntico (75,9%; α = 0,708).
É coincidência, verificada nos dados publicados: os trechos de acordo diferem em 12 casos, mas os totais coincidem.

## S2.5 Correção das proporções (seções 4.5 e 5)

Rótulos com acerto de 85% a 90% podem introduzir viés nas proporções agregadas (Egami et al., 2023). Aplicamos às
proporções populacionais um estimador de diferença ponderado pela amostra humana (`correcao_ouro.py`), em três versões:

1. **Referência:** o consenso da anotação dupla acrescido dos rótulos humanos do padrão-ouro.
2. **Padrão-ouro inteiro:** conserva a ancoragem dos casos verificados.
3. **Só os casos cegos** do padrão-ouro.

O estimador soma ao total do modelo, em cada ano, a diferença ponderada entre o rótulo humano e o do modelo na amostra:
T = Σ m + Σ w(h − m). Na anotação dupla, estratificada pela classe prevista e não por ano, o peso é o do estrato,
recalculado na população atual, e a soma se restringe aos trechos de cada ano. As proporções são razões de totais,
truncadas em [0, 100], com intervalos de 95% por *bootstrap* no ano. Quando a amostra humana não tem nenhuma
divergência numa medida e ano, o intervalo tem amplitude zero e subestima a incerteza; a Tabela S1 indica esses casos
e onde o truncamento atuou.

Na versão de referência, os ajustes alteram os níveis em até três pontos, exceto em 2023, sobretudo na ausência de
evidência (27,3% no modelo e 14,7% na correção) e de referência temporal (17,3% e 9,9%), sem modificar as tendências.
Na função, a correção de referência leva o risco de 5,4% para 38,8% e o uso de 40,5% para 15,7% entre 2023 e 2026; com
todo o padrão-ouro, o risco vai de 5,2% para 40,0%, e o uso, de 35,8% para 16,4%.

Sobre o tempo (seção 5.4): a correção baseada apenas nos trechos cegos do autor estimava 40,3% de trechos sem
referência temporal em 2026 (IC95% de 20,6% a 52,0%), contra 52,0% do modelo; a correção de referência, pela anotação
dupla, não confirma essa diferença (50,7%; IC95% de 48,1% a 52,0%, cujo limite superior coincide com o valor do modelo
porque poucos trechos da amostra divergem nessa medida).

## S2.6 Comparação com um modelo aberto (seção 4.5)

O classificador do estudo é um modelo proprietário (Claude Opus 5.5). Para que qualquer leitor possa reaplicar e
auditar o procedimento num computador pessoal, o mesmo *prompt* (`prompts/classificador_v3.md`) foi aplicado a
modelos abertos via [Ollama](https://ollama.com) 0.40.14, um trecho por chamada, com temperatura 0, semente 42,
raciocínio desligado e saída restrita por esquema JSON aos códigos do guia (`modelo_aberto.py`). Máquina: MacBook Air
M5 com 16 GB de memória, cerca de 12 segundos por trecho.

**Escolha do modelo** (amostra de desenvolvimento: os 97 trechos cegos do padrão-ouro, contra o autor). Dois
candidatos que cabem em 16 GB: Gemma 4 12B (α = 0,75 na função) e Qwen 3.5 9B (α = 0,59). Venceu o Gemma 4.

**Modelo do artigo:** `gemma4:12b-it-q4_K_M` (GGUF, quantização Q4_K_M, digest
`6114515d63c17436a7c0417d82820ac65ad643e2806c5a3c89cb62846436ed0b`). É o mesmo arquivo em qualquer sistema e aceita
saída estruturada. Nenhuma resposta inválida.

**Resultado na amostra de teste** (anotação dupla às cegas; α de Krippendorff, as mesmas funções da Tabela 2):

| Dimensão | Humanos entre si | Claude × autor | Claude × anotador 2 | Claude × consenso | Gemma × autor | Gemma × anotador 2 | Gemma × consenso |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Função | 0,708 | 0,708 | 0,901 | 0,894 | 0,702 | 0,720 | 0,686 |
| Evidência | 0,780 | 0,718 | 0,839 | 0,819 | 0,696 | 0,815 | 0,796 |
| Tom | 0,691 | 0,779 | 0,818 | 0,891 | 0,770 | 0,783 | 0,882 |
| Tempo | 0,682 | 0,733 | 0,834 | 0,872 | 0,685 | 0,738 | 0,769 |
| Governança declarada | 0,862 | 0,806 | 0,941 | 0,882 | 0,862 | 1,000 | 0,941 |
| Falso positivo | 0,957 | 0,957 | 1,000 | 0,957 | 0,904 | 0,861 | 0,904 |

Na função, o modelo aberto concorda com cada anotador no nível em que os anotadores concordam entre si, mas fica bem
abaixo do Claude contra o consenso. Ele serve para reaplicar e auditar o procedimento, não para substituir o
classificador. Tabela completa (acordo, α e n por dimensão, amostra e referência):
`dados_publicos/resultados/comparacao_modelos_abertos.csv`.

**A quantização importa.** No Mac, a tag padrão `gemma4:12b` baixa outra variante do mesmo modelo, que o Ollama roda
pelo motor MLX (safetensors) e que não aceita saída estruturada. Com ela, a concordância na função foi de 0,680
(autor), 0,811 (anotador 2) e 0,769 (consenso); em 20 trechos, a função coincidiu com a da variante GGUF em 18. As
saídas dessa variante e as do Qwen 3.5 ficam publicadas como execuções adicionais
(`dados_publicos/anotacao/llm_aberto/`); nelas, a validação dos códigos foi feita depois da resposta, e o Qwen precisou
que a chave final do JSON fosse acrescentada em 74 das 97 respostas (contagens em `meta_*.json`).

**Como reaplicar** (qualquer sistema com Ollama e cerca de 10 GB livres de memória):

```
ollama pull gemma4:12b-it-q4_K_M
python modelo_aberto.py classificar gemma4:12b-it-q4_K_M PASTA_ANOTACAO dupla saida/gemma
python modelo_aberto.py comparar PASTA_ANOTACAO saida/gemma
```

`PASTA_ANOTACAO` precisa de `populacao_v1.csv`, `ouro_v1.csv`, `classificacoes_llm_v3.csv` e `dupla_v2/`, que estão em
`dados_publicos/anotacao/`. Nos trechos das seções de administradores, o texto publicado está omitido; para eles, o
original está no FRE, no site da CVM.
