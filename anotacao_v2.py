"""Etapa 7b — anotação dupla às cegas (dois anotadores humanos), pedida para a validação do artigo.

Uso:
    python anotacao_v2.py PASTA_ANOTACAO

Lê de PASTA_ANOTACAO: populacao_v1.csv, classificacoes_llm_v3.csv, amostra_v1.csv, ouro_v1.csv e
llm_risco/consistencia_entrada.jsonl. Grava em PASTA_ANOTACAO/dupla_v2/:

  cega_v2_ids.csv                 os 200 trechos novos, com estrato (classe prevista pelo v3) e peso
  anotacao_v2_anotador1.xlsx      para o autor: instruções, os 200 trechos, tipos de risco, códigos
  anotacao_v2_anotador2.xlsx      para o segundo anotador: o mesmo, mais treino e gabarito do treino

Desenho:
  * trechos novos: nenhum anotador os viu. Ficam fora da amostra do padrão-ouro (808), das seções 7, 8
    e 13 (podem citar administradores) e da rodada de consistência dos tipos de risco;
  * sorteio estratificado pela classe que o v3 previu, com cotas (COTAS) que garantem casos de todas
    as classes, inclusive governança (rara) e falso positivo (nenhum caso na anotação cega anterior).
    O peso (trechos do estrato no universo elegível / sorteados) permite reponderar estimativas;
  * no máximo 2 trechos por companhia, alternando os anos;
  * os dois anotadores recebem os mesmos trechos, na mesma ordem embaralhada, sem a saída do modelo;
  * tipos de risco: os 100 trechos da rodada de consistência (o modelo já os classificou duas vezes);
  * treino (só anotador 2): 15 trechos do padrão-ouro, com o gabarito do autor numa aba separada.
"""
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

from verificacao import DEFINICOES, DESEMPATE, texto_destacado
from amostrar_anotacao import CODIGOS, GOVERNANCA

SEMENTE = 20261104
# na ordem do sorteio: as classes raras primeiro, para não esbarrarem no limite por companhia
COTAS = {"GOV": 17, "FALSO_POSITIVO": 20, "PROD": 32, "NEGOCIO": 30, "GENERICA": 28, "USO": 36, "RISCO": 37}
POR_EMPRESA = 2
TREINO = {"RISCO": 3, "USO": 3, "PROD": 2, "NEGOCIO": 2, "GENERICA": 2, "GOV": 2, "FALSO_POSITIVO": 1}
SECOES_FORA = ("7.", "8.", "13.")
fp = lambda v: str(v).strip().lower() in ("sim", "true")

TIPOS_RISCO = [
    ("REGULACAO", "Leis, regulamentos, decisões de autoridades ou incerteza regulatória sobre IA; custo de conformidade; responsabilização legal pelo uso de IA."),
    ("SEGURANCA", "Ciberataques, fraudes, phishing, malware, deepfakes ou vazamento de dados potencializados por IA."),
    ("CONCORRENCIA", "Perda de competitividade, concorrentes que adotam IA mais rápido, disrupção ou obsolescência do modelo de negócio, não capturar os ganhos esperados com a IA."),
    ("OPERACIONAL", "Falhas, erros, vieses ou imprecisão dos próprios sistemas de IA; dependência de fornecedores ou dados; uso inadequado por empregados; custos de implementação; propriedade intelectual."),
    ("REPUTACAO_ETICA", "Danos à imagem, uso antiético, discriminação, falta de transparência ou desconfiança do público associados à IA."),
    ("TRABALHO", "Efeitos sobre emprego, substituição de pessoas, requalificação, escassez de profissionais de IA."),
    ("GENERICO", "A IA aparece só numa lista de tecnologias ou tendências, sem dizer que dano traz. Use sozinho, só quando nenhum outro tipo se aplica."),
]
REGRAS_FP = [
    "Falso positivo: o termo não se refere a inteligência artificial (sigla de outra coisa, como auto de infração ou inquérito administrativo; texto corrompido).",
    "Também é falso positivo o nome de empresa, produto ou marca que contém \"IA\"/\"AI\" quando a IA não é o assunto do trecho (ex.: uma controlada chamada \"Fluxx.IA\" numa lista de participações).",
    "Também é falso positivo a IA citada só na formação acadêmica ou no currículo de um administrador, sem relação com a companhia.",
    "Programas ou produtos que tratam de IA (ex.: \"AI Academy\", um assistente virtual com IA) NÃO são falso positivo.",
]


def instrucoes(anotador):
    comum = [
        "Use só o trecho, a seção e o nome da empresa. Não consulte o formulário, a internet nem conhecimento sobre a empresa.",
        "Não converse sobre os trechos com o outro anotador até os dois terminarem. A anotação é independente.",
        "Se o trecho for da instituição onde você trabalha, marque conflito = sim e não anote o resto da linha.",
        "Primeiro decida se é falso positivo (regras na aba \"codigos\"). Se for, marque falso_positivo = sim e passe ao próximo.",
        "Se não for, marque falso_positivo = nao e preencha funcao, evidencia, governanca, tom e tempo (listas suspensas; em governança, escreva os códigos separados por ponto e vírgula, ou nenhuma).",
        "Em dúvida entre dois códigos, aplique as regras de desempate, escolha um, marque duvida = sim e escreva uma linha em justificativa.",
        "Aba \"tipos_risco\": para cada trecho de risco, escreva em tipos todos os tipos que o trecho liga à IA (separados por ponto e vírgula) e escolha o principal na lista. Definições na aba \"codigos_risco\".",
        "Pode parar e retomar quando quiser; salve o arquivo com o mesmo nome e devolva-o ao terminar.",
    ]
    if anotador == 1:
        topo = ["Anotação dupla às cegas — anotador 1 (autor)", "",
                "Você e o anotador 2 recebem os mesmos 200 trechos, nenhum deles visto antes por vocês (estão fora do padrão-ouro). O modelo já os classificou, mas a saída fica guardada à parte.",
                "Tempo estimado: cerca de 4 horas para a aba \"trechos\" e 1 hora para a aba \"tipos_risco\".", ""]
    else:
        topo = ["Anotação às cegas — anotador 2", "",
                "Obrigado por ajudar. Esta planilha valida a classificação de trechos de Formulários de Referência (documentos públicos que as companhias abertas entregam à CVM) em que aparece um termo ligado a inteligência artificial (IA). O termo encontrado está em negrito.",
                "O seu nome não aparece no artigo nem no repositório: as anotações são identificadas como \"anotador_2\".",
                "Ordem: (1) leia as abas \"codigos\" e \"codigos_risco\"; (2) faça a aba \"treino\" (15 trechos) e só depois compare com a aba \"gabarito_treino\"; (3) faça a aba \"trechos\" (200) sem voltar ao gabarito; (4) faça a aba \"tipos_risco\" (100).",
                "Tempo estimado: 30 minutos de treino, cerca de 4 horas para os 200 trechos e 1 hora para os tipos de risco.", ""]
    return topo + [f"{i}. {t}" for i, t in enumerate(comum, 1)]


def sortear(pasta):
    rng = random.Random(SEMENTE)
    modelo = {r["id_trecho"]: r for r in csv.DictReader(open(pasta / "classificacoes_llm_v3.csv", encoding="utf-8"))}
    ouro = {r["id_trecho"] for r in csv.DictReader(open(pasta / "amostra_v1.csv", encoding="utf-8-sig"))}
    consistencia = {json.loads(l)["id_trecho"] for l in open(pasta / "llm_risco" / "consistencia_entrada.jsonl", encoding="utf-8")}
    classe = lambda i: "FALSO_POSITIVO" if fp(modelo[i]["falso_positivo"]) else modelo[i]["funcao"]
    elegiveis = [t for t in csv.DictReader(open(pasta / "populacao_v1.csv", encoding="utf-8-sig"))
                 if t["id_trecho"] in modelo and t["id_trecho"] not in ouro | consistencia
                 and not t["secao"].startswith(SECOES_FORA)]
    por_classe = defaultdict(list)
    for t in sorted(elegiveis, key=lambda t: t["id_trecho"]):
        por_classe[classe(t["id_trecho"])].append(t)
    usados, escolhidos = Counter(), []
    for c, cota in COTAS.items():
        por_ano = defaultdict(list)
        for t in por_classe[c]:
            por_ano[t["ano"]].append(t)
        for lista in por_ano.values():
            rng.shuffle(lista)
        n0 = len(escolhidos)
        while len(escolhidos) - n0 < cota and any(por_ano.values()):
            for a in sorted(por_ano):
                while por_ano[a]:
                    t = por_ano[a].pop()
                    if usados[t["cd_cvm"]] < POR_EMPRESA:
                        usados[t["cd_cvm"]] += 1
                        escolhidos.append({**t, "estrato": c, "peso": round(len(por_classe[c]) / cota, 4)})
                        break
                if len(escolhidos) - n0 == cota:
                    break
    rng.shuffle(escolhidos)
    return escolhidos, len(elegiveis), {c: len(v) for c, v in por_classe.items()}


def treino(pasta):
    rng = random.Random(SEMENTE + 1)
    cega = {r["id_trecho"] for r in csv.DictReader(open(pasta / "cega_v1_ids.csv", encoding="utf-8"))}
    ouro = [o for o in csv.DictReader(open(pasta / "ouro_v1.csv", encoding="utf-8-sig"))
            if o["id_trecho"] not in cega and not o["secao"].startswith(SECOES_FORA)]
    itens = []
    for c, n in TREINO.items():
        cands = [o for o in ouro if (fp(o["falso_positivo"]) if c == "FALSO_POSITIVO" else
                                     (not fp(o["falso_positivo"]) and o["funcao"] == c))]
        # prefere trechos sem dúvida e de tamanho médio; se faltarem (governança é rara), aceita os demais
        bons = [o for o in cands if o["duvida"] != "sim" and 150 <= len(o["trecho"]) <= 700]
        base = bons if len(bons) >= n else cands
        itens += rng.sample(sorted(base, key=lambda o: o["id_trecho"]), n)
    rng.shuffle(itens)
    return itens


def definicao(codigo):
    return next((d[2] for d in DEFINICOES if d[1] == codigo), "")


def aba_trechos(wb, nome, trechos, colunas_anotacao, larguras_extra=None):
    from openpyxl.styles import Alignment, Font
    from openpyxl.worksheet.datavalidation import DataValidation
    ws = wb.create_sheet(nome)
    visiveis = ["n", "id_trecho", "empresa", "secao", "titulo_secao", "trecho"]
    cab = visiveis + colunas_anotacao
    ws.append(cab)
    for c in ws[1]:
        c.font = Font(bold=True)
    for i, t in enumerate(trechos, 1):
        ws.append([i, t["id_trecho"], t.get("empresa", ""), t.get("secao", ""), t.get("titulo_secao", ""), ""] + [""] * len(colunas_anotacao))
        ws.cell(i + 1, visiveis.index("trecho") + 1).value = texto_destacado(t["trecho"], t.get("termos", ""))
    larguras = {"n": 5, "id_trecho": 17, "empresa": 22, "secao": 7, "titulo_secao": 20, "trecho": 85,
                "governanca": 24, "justificativa": 36, "tipos": 30, **(larguras_extra or {})}
    listas = {**{k: v for k, v in CODIGOS.items()}, "conflito": ["sim", "nao"],
              "principal": [k for k, _ in TIPOS_RISCO]}
    fim = len(trechos) + 1
    for i, col in enumerate(cab, 1):
        letra = ws.cell(1, i).column_letter
        ws.column_dimensions[letra].width = larguras.get(col, 13)
        if col in listas:
            dv = DataValidation(type="list", formula1='"' + ",".join(listas[col]) + '"', allow_blank=True)
            dv.add(f"{letra}2:{letra}{fim}")
            ws.add_data_validation(dv)
        if col == "governanca":
            dv = DataValidation(allow_blank=True, showInputMessage=True, promptTitle="Governança (marcar todas)", prompt=GOVERNANCA)
            dv.add(f"{letra}2:{letra}{fim}")
            ws.add_data_validation(dv)
        if col == "tipos":
            dv = DataValidation(allow_blank=True, showInputMessage=True, promptTitle="Tipos (marcar todos)",
                                prompt="; ".join(k for k, _ in TIPOS_RISCO))
            dv.add(f"{letra}2:{letra}{fim}")
            ws.add_data_validation(dv)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "G2"
    return ws


def abas_texto(wb, nome, linhas, larguras):
    from openpyxl.styles import Alignment, Font
    ws = wb.create_sheet(nome)
    for linha in linhas:
        ws.append(list(linha) if isinstance(linha, (list, tuple)) else [linha])
    ws["A1"].font = Font(bold=True, size=13)
    for letra, w in larguras.items():
        ws.column_dimensions[letra].width = w
    for row in ws.iter_rows():
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    return ws


def planilha(caminho, anotador, trechos, risco, itens_treino):
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    abas_texto(wb, "instrucoes", instrucoes(anotador), {"A": 140})
    anotacao = ["conflito", "falso_positivo", "funcao", "evidencia", "governanca", "tom", "tempo", "duvida", "justificativa"]
    if anotador == 2:
        aba_trechos(wb, "treino", itens_treino, anotacao)
        gab = [("Gabarito do treino (consulte só depois de anotar a aba treino)", "", "", "", "", "", "", "", ""),
               ("n", "id_trecho", "falso_positivo", "funcao", "evidencia", "governanca", "tom", "tempo", "por quê (definição do código de função)")]
        for i, o in enumerate(itens_treino, 1):
            e_fp = fp(o["falso_positivo"])
            gab.append((i, o["id_trecho"], "sim" if e_fp else "nao", "" if e_fp else o["funcao"],
                        "" if e_fp else o["evidencia"], "" if e_fp else o["governanca"], "" if e_fp else o["tom"],
                        "" if e_fp else o["tempo"],
                        definicao("sim") if e_fp else definicao(o["funcao"]) + (f" Nota do autor: {o['comentario']}" if o.get("comentario") else "")))
        abas_texto(wb, "gabarito_treino", gab, {"A": 5, "B": 18, "C": 12, "D": 12, "E": 12, "F": 20, "G": 8, "H": 12, "I": 80})
    aba_trechos(wb, "trechos", trechos, anotacao)
    aba_trechos(wb, "tipos_risco", risco, ["conflito", "tipos", "principal", "duvida", "justificativa"])
    cod = [("dimensão", "código", "definição")] + [tuple(d) for d in DEFINICOES]
    cod += [("", "", ""), ("desempate", "", "")] + [("", str(i), r) for i, r in enumerate(DESEMPATE, 1)]
    cod += [("", "", ""), ("falso positivo", "", "")] + [("", str(i), r) for i, r in enumerate(REGRAS_FP, 1)]
    abas_texto(wb, "codigos", cod, {"A": 16, "B": 18, "C": 110})
    abas_texto(wb, "codigos_risco", [("Tipos de risco ligados à IA (marcar todos; escolher um principal)", "")] +
               [(k, v) for k, v in TIPOS_RISCO] +
               [("", ""), ("principal", "O tipo que é o assunto central do trecho; em empate, o que aparece primeiro.")],
               {"A": 20, "B": 120})
    wb.save(caminho)


def main(pasta):
    pasta = Path(pasta)
    saida = pasta / "dupla_v2"
    saida.mkdir(exist_ok=True)
    trechos, n_eleg, por_classe = sortear(pasta)
    risco = [json.loads(l) for l in open(pasta / "llm_risco" / "consistencia_entrada.jsonl", encoding="utf-8")]
    pop = {t["id_trecho"]: t for t in csv.DictReader(open(pasta / "populacao_v1.csv", encoding="utf-8-sig"))}
    risco = [{**pop[r["id_trecho"]]} for r in risco]
    random.Random(SEMENTE + 2).shuffle(risco)
    itens_treino = treino(pasta)
    with open(saida / "cega_v2_ids.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["n", "id_trecho", "ano", "cd_cvm", "estrato", "peso"])
        for i, t in enumerate(trechos, 1):
            w.writerow([i, t["id_trecho"], t["ano"], t["cd_cvm"], t["estrato"], t["peso"]])
    with open(saida / "tipos_risco_v2_ids.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["n", "id_trecho"])
        for i, t in enumerate(risco, 1):
            w.writerow([i, t["id_trecho"]])
    planilha(saida / "anotacao_v2_anotador1.xlsx", 1, trechos, risco, itens_treino)
    planilha(saida / "anotacao_v2_anotador2.xlsx", 2, trechos, risco, itens_treino)
    print(f"elegíveis {n_eleg} {por_classe}")
    print(f"trechos: {len(trechos)} {dict(Counter(t['estrato'] for t in trechos))}; anos {dict(Counter(t['ano'] for t in trechos))}")
    print(f"tipos de risco: {len(risco)}; treino: {len(itens_treino)} -> {saida}")


if __name__ == "__main__":
    main(sys.argv[1])
