# Classificador de menções a IA nos Formulários de Referência — prompt v1

Versão: v1 (28/10/2026). Baseado no "Guia de anotação v1". Qualquer mudança neste arquivo gera v2.

## Tarefa

Você recebe trechos de Formulários de Referência (FRE) entregues por companhias abertas
brasileiras à CVM. Cada trecho contém pelo menos um termo que um dicionário associou a
inteligência artificial (IA). O termo encontrado vem no campo `termos`. Classifique cada
trecho em cinco dimensões, seguindo exatamente as definições abaixo.

Use apenas o trecho, o número e o título da seção e o nome da empresa. Não consulte outros
arquivos, a internet nem conhecimento sobre a empresa. Classifique cada trecho de forma
independente.

## Passo 0 — falso positivo

Primeiro, confirme se o termo realmente se refere a IA. Se não se refere (ex.: "IA" ou "AI"
como sigla de outra coisa, nome próprio sem relação com IA, texto corrompido), marque
`"falso_positivo": true` e deixe as outras dimensões como `null`.

Nomes de produtos, programas ou empresas que se apresentam como IA (ex.: "Fluxx.IA",
"AI Academy") referem-se a IA: não são falso positivo.

## Dimensão 1 — funcao (escolher uma)

- `PROD`: promessa ou expectativa de ganho de produtividade, eficiência, redução de custo ou
  tempo atribuída à IA. Indicadores: "permitirá ganhos de eficiência", "reduzir custos
  operacionais", "otimizar processos".
- `USO`: descrição de uso concreto já implantado, sem afirmar ganho. Ferramenta, área e
  finalidade nomeadas: "utilizamos modelos de IA na análise de crédito".
- `NEGOCIO`: IA como produto, serviço ou fonte de receita para clientes; oferta ao mercado,
  nova linha de negócio.
- `RISCO`: IA como fonte de risco ou ameaça: concorrentes, regulação, falhas, viés,
  segurança, privacidade.
- `GOV`: regras, estruturas ou responsabilidades sobre o uso de IA: política, comitê,
  diretoria responsável, diretrizes, supervisão humana.
- `GENERICA`: menção vaga, aspiracional ou de contexto, sem as funções acima: "em um mundo
  marcado pela IA", listas de tendências.

Desempate:
1. PROD prevalece sobre USO quando o trecho afirma ganho, mesmo que descreva o uso.
2. RISCO prevalece quando o trecho está na seção 4.1 ou 4.2 e descreve a IA como ameaça,
   mesmo que cite governança como mitigação.
3. GOV só quando a regra ou estrutura é o assunto principal; uma menção de passagem a "uso
   responsável" é GENERICA.

Se o trecho tiver várias menções com funções diferentes, classifique pela menção que é o
assunto principal do trecho.

## Dimensão 2 — evidencia (para qualquer função)

- `METRICA`: traz número, percentual, valor monetário ou prazo ligado à IA.
- `CASO`: descreve uma aplicação específica (área, processo ou sistema identificável), sem número.
- `SEM`: nem métrica nem caso.

O número precisa estar ligado à IA; números sobre outros assuntos no mesmo trecho não contam.

## Dimensão 3 — governanca (lista; marcar todas que aparecem)

`politica`, `comite_ou_responsavel`, `supervisao_humana`, `protecao_dados`; ou `nenhuma`
(sozinha) se nenhuma aparece. Só conta governança ligada ao uso de IA.

## Dimensão 4 — tom

- `POS`: IA apresentada como oportunidade ou vantagem.
- `NEU`: descritivo, sem valoração.
- `NEG`: IA apresentada como ameaça, limitação ou custo.

## Dimensão 5 — tempo

- `REALIZADO`: já implantado ou concluído.
- `EM_CURSO`: em implantação, piloto ou teste.
- `PLANEJADO`: intenção, plano ou expectativa futura.
- `NA`: sem referência temporal (típico de RISCO e GENERICA).

## Exemplos (criados para o guia; não são citações de formulários)

| Trecho | funcao | evidencia | governanca | tom | tempo |
|---|---|---|---|---|---|
| A adoção de IA na esteira de crédito reduziu em 30% o tempo de análise | PROD | METRICA | nenhuma | POS | REALIZADO |
| Iniciamos piloto de IA generativa no atendimento, sob política aprovada pelo conselho | USO | CASO | politica | NEU | EM_CURSO |
| Concorrentes que adotem IA mais rapidamente podem reduzir nossa participação de mercado | RISCO | SEM | nenhuma | NEG | NA |
| A Companhia criou comitê para avaliar riscos e usos de IA, com supervisão humana obrigatória | GOV | SEM | comite_ou_responsavel; supervisao_humana | NEU | REALIZADO |
| Vivemos uma era de transformação impulsionada pela IA | GENERICA | SEM | nenhuma | POS | NA |

## Formato de saída

Uma linha JSON por trecho (JSONL), na mesma ordem da entrada, sem texto antes ou depois:

```
{"id_trecho": "...", "falso_positivo": false, "funcao": "USO", "evidencia": "CASO", "governanca": ["nenhuma"], "tom": "NEU", "tempo": "REALIZADO", "duvida": false, "justificativa": "..."}
```

- `duvida`: `true` quando hesitou entre dois códigos em alguma dimensão.
- `justificativa`: até 30 palavras, em português, citando entre aspas a parte do trecho que
  sustenta a função (e a dimensão em dúvida, se houver).
- Use exatamente os códigos acima, em maiúsculas onde indicado.
