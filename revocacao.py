"""Etapa 7d — revocação do dicionário (pedido da revisão): quantas menções a IA ficam de fora por não nomeá-la?

Uso:
    python revocacao.py amostra   PASTA_DADOS SAIDA.xlsx
    python revocacao.py estimar   PASTA_DADOS PLANILHA.xlsx
    python revocacao.py variantes PASTA_DADOS SAIDA.csv
    python revocacao.py paginas   PASTA_DADOS SAIDA.xlsx
    python revocacao.py paginas_estimar PLANILHA.xlsx

Duas perguntas diferentes (separadas na segunda rodada da revisão):
  * menções implícitas (amostra/estimar): IA descrita sem ser nomeada, na camada de vizinhos. O artigo exclui
    essas menções por definição; a medida diz quanto discurso de IA não nomeada fica fora.
  * revocação da IA nomeada (variantes/paginas): menções que nomeiam a IA mas escapam ao dicionário por grafia,
    termo ausente ou defeito do PDF. "variantes" busca no texto integral grafias alternativas em páginas sem
    nenhuma menção detectada; "paginas" sorteia páginas sem nenhum termo das camadas de IA para leitura humana.

amostra  sorteia trechos da camada "vizinhos" (automação, algoritmos, analytics, digitalização...) que não
         contêm nenhum termo de IA, em dois estratos: termos técnicos (algoritmo, analytics, big data, ciência
         de dados, robô, RPA, automação, transformação digital) e termos de eficiência (produtividade,
         eficiência operacional, digitalização). Chatbot, assistente virtual e modelo preditivo ficam de fora:
         já foram decididos (não contam como IA sem nomeá-la). O autor lê cada trecho e marca se ele descreve
         IA sem nomeá-la (sim / nao / duvida).
estimar  lê a planilha preenchida e estima, por estrato, quantos trechos da camada vizinhos descrevem IA
         sem nomeá-la (proporção × total do estrato), e a revocação = trechos com IA nomeada / (nomeada +
         estimada sem nome).
"""
import csv
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font
from openpyxl.worksheet.datavalidation import DataValidation

SEMENTE = 20261107
POR_ESTRATO = 60
ANOS = ["2023", "2024", "2025", "2026"]
FORA = re.compile(r"chatbot|assistentes? virtua|modelos? preditiv", re.I)
TECNICOS = re.compile(r"algoritm|analytics|big data|ci[êe]ncia de dados|rob[ôo]|\brpa\b|automa[çc]|automatiza|transforma[çc][ãa]o digital", re.I)
RE_IA = re.compile(r"intelig[êe]ncia\s+artificial|artificial\s+intelligence|\bIA\b|\bAI\b|machine\s+learning|aprendizado\s+de\s+m|"
                   r"aprendizagem\s+de\s+m|deep\s+learning|redes?\s+neura|vis[ãa]o\s+computacional|linguagem\s+natural|generativ|chatgpt|\bllm", re.I)


VARIANTES = {
    "I.A. / A.I. com pontos": r"\bI\.\s?A\.|\bA\.\s?I\.(?!\s?[A-Z]\.)",
    "inteligência artificial hifenizada ou colada": r"intel[ií]?-\s+g[êe]ncia|intelig[êe]n-\s+cia\s+arti|arti-\s+ficial|intelig[êe]nciaartificial|intelig[êe]ncia-artificial|artificialintelligence",
    "machine learning / deep learning com hífen ou colado": r"machine-learning|machinelearning|deep-learning|deeplearning",
    "GPT e modelos": r"\bGPT\b|\bGPT-?\d|\bClaude\b|\bLlama\b|\bMistral\b|\bGemini\b",
    "computação cognitiva": r"computa[çc][ãa]o\s+cognitiva|sistemas?\s+cognitivos?",
    "aprendizagem automática / automático": r"aprendizagem\s+autom[áa]tica|aprendizado\s+autom[áa]tico",
    "redes neuronais / neural": r"redes?\s+neuronais|\bneural\b",
    "IA minúscula ou com apóstrofo": r"\bIAs\b|\bIA's\b|\bia\s+generativa",
}


def cmd_variantes(pasta, saida):
    """Grafias e termos alternativos em páginas onde o dicionário não detectou nenhuma menção de IA."""
    import json
    from detectar_mencoes import CAMADAS, LIGADURAS
    rx = {k: re.compile(v) for k, v in VARIANTES.items()}
    ia = CAMADAS["ia"] + CAMADAS["ia_gen"]
    linhas, por_tipo = [], defaultdict(set)
    for a in ANOS:
        with open(Path(pasta) / f"secoes_{a}.jsonl", encoding="utf-8") as f:
            for l in f:
                p = json.loads(l)
                t = p["texto"].replace("\x00", "").translate(LIGADURAS)
                if any(r.search(t) for r in ia):
                    continue
                for k, r in rx.items():
                    for m in r.finditer(t):
                        ctx = t[max(0, m.start() - 160): m.end() + 160].replace("\n", " ")
                        linhas.append({"ano": a, "cd_cvm": p["cd_cvm"], "empresa": p["empresa"], "secao": p["secao"],
                                       "pagina": p["pagina"], "tipo": k, "termo": m.group(0), "contexto": ctx})
                        por_tipo[k].add((a, p["cd_cvm"]))
    with open(saida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ano", "cd_cvm", "empresa", "secao", "pagina", "tipo", "termo", "contexto"])
        w.writeheader()
        w.writerows(linhas)
    for k in VARIANTES:
        print(f"{k:55} ocorrências {sum(l['tipo'] == k for l in linhas):5}  companhias-ano {len(por_tipo[k])}")


SECOES_LEITURA = ("1.", "2.10", "4.")
POR_ANO_PAGINAS = 30


def cmd_paginas(pasta, saida):
    """Sorteia páginas das seções 1, 2.10 e 4 sem nenhum termo das camadas de IA (nem variante) para leitura."""
    import json
    from detectar_mencoes import CAMADAS, LIGADURAS
    ia = CAMADAS["ia"] + CAMADAS["ia_gen"] + [re.compile(v) for v in VARIANTES.values()]
    rng = random.Random(SEMENTE + 1)
    escolhidas = []
    for a in ANOS:
        cand = []
        with open(Path(pasta) / f"secoes_{a}.jsonl", encoding="utf-8") as f:
            for l in f:
                p = json.loads(l)
                if not p["secao"].startswith(SECOES_LEITURA):
                    continue
                t = p["texto"].replace("\x00", "").translate(LIGADURAS)
                if len(t.split()) < 150 or any(r.search(t) for r in ia):
                    continue
                cand.append({"ano": a, "cd_cvm": p["cd_cvm"], "empresa": p["empresa"], "secao": p["secao"],
                             "pagina": p["pagina"], "texto": t})
        escolhidas += rng.sample(cand, POR_ANO_PAGINAS)
    rng.shuffle(escolhidas)
    wb = Workbook()
    ws = wb.active
    ws.title = "instrucoes"
    for l in ["Revocação da IA nomeada — leitura do autor", "",
              f"{len(escolhidas)} páginas sorteadas das seções 1 (atividades), 2.10 (planos) e 4 (riscos), {POR_ANO_PAGINAS} por ano,",
              "em que o dicionário NÃO encontrou nenhum termo de IA. Pergunta: a página nomeia a inteligência artificial de algum",
              "jeito que o dicionário não pegou (sigla diferente, termo em inglês, nome de produto de IA, palavra quebrada)?",
              "Leitura rápida: procure por tecnologia, algoritmo, dados, automação, assistente, modelo. Marque nomeia_ia = sim/nao.",
              "Se sim, copie o trecho em 'trecho'. IA descrita sem ser nomeada NÃO conta aqui (vai na outra planilha)."]:
        ws.append([l])
    ws.column_dimensions["A"].width = 120
    ws2 = wb.create_sheet("paginas")
    ws2.append(["n", "ano", "cd_cvm", "empresa", "secao", "pagina", "texto", "nomeia_ia", "trecho"])
    for i, r in enumerate(escolhidas, 1):
        ws2.append([i, r["ano"], r["cd_cvm"], r["empresa"], r["secao"], r["pagina"], r["texto"][:32000], "", ""])
    dv = DataValidation(type="list", formula1='"sim,nao"', allow_blank=True)
    ws2.add_data_validation(dv)
    dv.add(f"H2:H{len(escolhidas) + 1}")
    for col, w in zip("ABCDEFGHI", (5, 6, 8, 24, 7, 6, 110, 11, 40)):
        ws2.column_dimensions[col].width = w
    for row in ws2.iter_rows(min_row=2, min_col=7, max_col=7):
        row[0].alignment = Alignment(wrap_text=True, vertical="top")
    ws2.freeze_panes = "H2"
    wb.save(saida)
    print(f"{len(escolhidas)} páginas -> {saida}")


def cmd_paginas_estimar(planilha):
    linhas = list(load_workbook(planilha, read_only=True)["paginas"].iter_rows(values_only=True))
    cab = linhas[0]
    resp = [dict(zip(cab, l)) for l in linhas[1:] if l[0]]
    sim = sum(str(r["nomeia_ia"]).strip().lower() == "sim" for r in resp)
    n = len(resp)
    # limite superior de 95% (Clopper-Pearson unilateral; com 0 achados, regra de três)
    sup = 1 - 0.05 ** (1 / n) if sim == 0 else None
    print(f"{n} páginas lidas, {sim} com IA nomeada não detectada" + (f"; limite superior de 95%: {100 * sup:.1f}% das páginas" if sup else ""))


def populacao(pasta):
    estratos, vistos = defaultdict(list), set()
    for a in ANOS:
        for r in csv.DictReader(open(Path(pasta) / f"mencoes_{a}.csv", encoding="utf-8")):
            if r["camada"] != "vizinhos" or FORA.search(r["termo"]) or RE_IA.search(r["trecho"]):
                continue
            chave = (r["cd_cvm"], a, r["trecho"])
            if chave in vistos or r["secao"].startswith(("7.", "8.", "13.")):
                continue
            vistos.add(chave)
            estratos["tecnicos" if TECNICOS.search(r["termo"]) else "eficiencia"].append({**r, "ano": a})
    return estratos


def cmd_amostra(pasta, saida):
    estratos = populacao(pasta)
    rng = random.Random(SEMENTE)
    amostra = []
    for e in ("tecnicos", "eficiencia"):
        for r in rng.sample(estratos[e], POR_ESTRATO):
            amostra.append({**r, "estrato": e})
    rng.shuffle(amostra)
    wb = Workbook()
    ws = wb.active
    ws.title = "instrucoes"
    for l in ["Revocação do dicionário — leitura do autor", "",
              "Cada linha é um trecho de FRE com um termo de eficiência ou tecnologia (em 'termo') e SEM nenhum termo de IA.",
              "Pergunta: o trecho descreve inteligência artificial sem usar o nome (ex.: sistema que aprende com dados, "
              "reconhecimento de imagem, previsão automática por modelo estatístico treinado)?",
              "Marque ia_sem_nome = sim, nao ou duvida. Automação comum, RPA por regras, digitalização e 'produtividade' "
              "em geral são 'nao'. Em dúvida, escreva uma linha em comentario.",
              "Chatbot, assistente virtual e modelo preditivo sem nomear IA já foram decididos e não aparecem aqui.",
              f"Total: {len(amostra)} trechos ({POR_ESTRATO} de termos técnicos e {POR_ESTRATO} de termos de eficiência)."]:
        ws.append([l])
    ws.column_dimensions["A"].width = 120
    ws2 = wb.create_sheet("trechos")
    cab = ["n", "ano", "cd_cvm", "empresa", "secao", "estrato", "termo", "trecho", "ia_sem_nome", "comentario"]
    ws2.append(cab)
    for i, r in enumerate(amostra, 1):
        ws2.append([i, r["ano"], r["cd_cvm"], r["empresa"], r["secao"], r["estrato"], r["termo"], r["trecho"], "", ""])
    dv = DataValidation(type="list", formula1='"sim,nao,duvida"', allow_blank=True)
    ws2.add_data_validation(dv)
    dv.add(f"I2:I{len(amostra) + 1}")
    for col, w in zip("ABCDEFGHIJ", (5, 6, 8, 24, 7, 10, 18, 90, 12, 30)):
        ws2.column_dimensions[col].width = w
    for row in ws2.iter_rows(min_row=2, min_col=8, max_col=8):
        row[0].alignment = Alignment(wrap_text=True, vertical="top")
    for c in ws2[1]:
        c.font = Font(bold=True)
    ws2.freeze_panes = "I2"
    wb.save(saida)
    print(f"{len(amostra)} trechos -> {saida}; população: " + ", ".join(f"{e} {len(v)}" for e, v in estratos.items()))


def cmd_estimar(pasta, planilha):
    estratos = populacao(pasta)
    linhas = list(load_workbook(planilha, read_only=True)["trechos"].iter_rows(values_only=True))
    cab = linhas[0]
    resp = [dict(zip(cab, l)) for l in linhas[1:] if l[0]]
    faltam = [r["n"] for r in resp if str(r["ia_sem_nome"] or "").strip().lower() not in ("sim", "nao", "duvida")]
    if faltam:
        print(f"{len(faltam)} trechos sem resposta")
        return
    nomeada = sum(1 for t in csv.DictReader(open(Path(pasta) / "anotacao" / "populacao_v1.csv", encoding="utf-8-sig")))
    total_sem_nome = teto = 0
    for e in ("tecnicos", "eficiencia"):
        rs = [r for r in resp if r["estrato"] == e]
        p = sum(str(r["ia_sem_nome"]).lower() == "sim" for r in rs) / len(rs)
        d = sum(str(r["ia_sem_nome"]).lower() == "duvida" for r in rs) / len(rs)
        est = p * len(estratos[e])
        total_sem_nome += est
        teto += (p + d) * len(estratos[e])
        print(f"{e}: {len(rs)} lidos, sim {100 * p:.1f}% (dúvida {100 * d:.1f}%), população {len(estratos[e])}, "
              f"estimativa {est:.0f} trechos (com as dúvidas: {(p + d) * len(estratos[e]):.0f})")
    # menções implícitas: IA descrita sem ser nomeada, excluída do estudo por definição (não é revocação do dicionário)
    print(f"menções implícitas estimadas: {total_sem_nome:.0f} trechos ({100 * total_sem_nome / nomeada:.1f}% dos {nomeada} "
          f"trechos com IA nomeada); contando as dúvidas como IA, {teto:.0f} ({100 * teto / nomeada:.1f}%)")


if __name__ == "__main__":
    {"amostra": cmd_amostra, "estimar": cmd_estimar, "variantes": cmd_variantes, "paginas": cmd_paginas,
     "paginas_estimar": cmd_paginas_estimar}[sys.argv[1]](*sys.argv[2:])
