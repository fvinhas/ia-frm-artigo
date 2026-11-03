# Tipos de risco atribuídos à IA nos Formulários de Referência — prompt v1

Versão: v1 (28/10/2026). Codificação exploratória dos trechos que o classificador v3 marcou com
função RISCO. Qualquer mudança neste arquivo gera v2.

## Tarefa

Você recebe trechos de Formulários de Referência (FRE) de companhias abertas brasileiras em que a
inteligência artificial (IA) aparece como fonte de risco ou ameaça. Para cada trecho, identifique
que tipo de risco o texto liga à IA. Use apenas o texto do trecho; não consulte outros arquivos, a
internet nem conhecimento sobre a empresa. Classifique cada trecho de forma independente.

## Tipos (marcar todos os que o trecho liga à IA)

- `REGULACAO`: leis, regulamentos, decisões de autoridades ou incerteza regulatória sobre IA;
  custo de conformidade; responsabilização legal pelo uso de IA; proteção de dados quando ligada à
  regulação da IA.
- `SEGURANCA`: ciberataques, fraudes, *phishing*, *malware*, *deepfakes* ou vazamento de dados
  potencializados por IA (de terceiros ou da própria companhia).
- `CONCORRENCIA`: perda de competitividade, concorrentes que adotam IA mais rápido, disrupção ou
  obsolescência do modelo de negócio, mudança no comportamento dos clientes causada pela IA, não
  conseguir capturar os ganhos esperados com a IA.
- `OPERACIONAL`: falhas, erros, vieses ou resultados imprecisos dos próprios sistemas de IA;
  dependência de fornecedores ou de dados; uso inadequado por empregados; custos de
  implementação; propriedade intelectual ligada a conteúdo gerado ou usado por IA.
- `REPUTACAO_ETICA`: danos à imagem, uso antiético, discriminação, falta de transparência ou
  desconfiança do público associados à IA.
- `TRABALHO`: efeitos sobre emprego, substituição de pessoas, requalificação, escassez de
  profissionais de IA.
- `GENERICO`: a IA aparece só numa lista de tecnologias ou tendências (\"inovações disruptivas,
  como IA, robótica...\") sem que o trecho diga que tipo de dano ela traz.

Use `GENERICO` sozinho, apenas quando nenhum outro tipo se aplica.

## Tipo principal

Escolha também um `principal`: o tipo que é o assunto central do trecho. Em caso de empate, prefira
o que vem primeiro no trecho.

## Formato de saída

Uma linha JSON por trecho (JSONL), na mesma ordem da entrada, sem texto antes ou depois:

```
{"id_trecho": "...", "tipos": ["SEGURANCA", "REPUTACAO_ETICA"], "principal": "SEGURANCA", "duvida": false, "justificativa": "..."}
```

- `duvida`: `true` quando hesitou entre dois tipos.
- `justificativa`: até 25 palavras, em português, citando entre aspas a parte do trecho que
  sustenta o tipo principal.
- Use exatamente os códigos acima, em maiúsculas.
