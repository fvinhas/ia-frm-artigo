"""Etapa 6 — amostra estratificada de trechos para a anotação-ouro (guia v1).

Uso:
    python amostrar_anotacao.py PASTA_DADOS cad_cia_aberta.csv SAIDA_DIR 2023 2024 2025 2026

População: menções das camadas "ia" e "ia_gen" (sem os vizinhos). A unidade é o trecho
(frase ± 1); várias menções no mesmo trecho da mesma empresa-ano viram um trecho só.

Desenho:
  * mesmo número de trechos por ano (POR_ANO), para comparar anos com a mesma precisão;
  * dentro do ano, um estrato para os trechos com IA generativa (qualquer seção) e os
    demais estratificados por grupo de seção, com alocação proporcional à raiz do
    tamanho do estrato e mínimo de MINIMO (ou o estrato inteiro, se menor), para que
    seções raras (resultados, controles) e a IA generativa tenham trechos suficientes;
  * dentro do estrato, sorteio que alterna os macrossetores; no ano inteiro, no máximo
    POR_EMPRESA trechos por empresa; textos idênticos (ex.: controladora e controlada) entram uma vez só;
  * peso amostral = trechos no estrato / trechos sorteados no estrato, para reponderar
    as proporções estimadas;
  * os primeiros CALIBRACAO trechos (espalhados por ano e grupo) formam a rodada de
    calibração; depois do consenso eles também entram no padrão-ouro.

Saídas em SAIDA_DIR:
  amostra_v1.csv           trechos sorteados com estrato, peso e colunas de anotação vazias
  populacao_estratos.csv   tamanho de cada estrato e quantos foram sorteados
  anotacao_v1_A.xlsx / _B.xlsx   planilhas para os dois anotadores (abas calibracao e ouro)
"""
import csv
import hashlib
import html
import math
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

from setores import carregar_cadastro

SEMENTE = 20261028
POR_ANO = 212          # 4 anos x 212 = 848 (~800 ouro + 50 calibração)
MINIMO = 15
POR_EMPRESA = 4
CALIBRACAO = 50

COLUNAS_ANOTACAO = ["falso_positivo", "funcao", "evidencia", "governanca", "tom", "tempo",
                    "duvida", "justificativa"]
CODIGOS = {
    "falso_positivo": ["sim", "nao"],
    "funcao": ["PROD", "USO", "NEGOCIO", "RISCO", "GOV", "GENERICA"],
    "evidencia": ["METRICA", "CASO", "SEM"],
    "tom": ["POS", "NEU", "NEG"],
    "tempo": ["REALIZADO", "EM_CURSO", "PLANEJADO", "NA"],
    "duvida": ["sim", "nao"],
}
GOVERNANCA = "politica; comite_ou_responsavel; supervisao_humana; protecao_dados; nenhuma"


RE_CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")  # o Excel não aceita


def grupo_secao(secao):
    if secao.startswith("antigo:"):
        return "formato antigo"
    if secao in ("4.1", "4.2", "4.3"):
        return "4 riscos"
    if secao == "2.10":
        return "2.10 planos de negócios"
    if secao.startswith(("2.", "3.")):
        return "2-3 resultados e projeções"
    if secao.startswith("1."):
        return "1 atividades"
    if secao.startswith("5."):
        return "5 controles e integridade"
    return "6-13 administração, RH e outros"


def normalizar(texto):
    return re.sub(r"\W+", " ", texto).strip().lower()


def carregar_populacao(pasta, anos, setores):
    trechos = {}
    for a in anos:
        for m in csv.DictReader(open(Path(pasta) / f"mencoes_{a}.csv", encoding="utf-8")):
            if m["camada"] == "vizinhos":
                continue
            chave = (a, m["cd_cvm"], normalizar(m["trecho"]))
            t = trechos.get(chave)
            if t is None:
                cd = m["cd_cvm"].lstrip("0")
                t = trechos[chave] = {
                    "id_trecho": f"{a}-{m['cd_cvm']}-{hashlib.sha1(chave[2].encode()).hexdigest()[:6]}",
                    "ano": a, "cd_cvm": m["cd_cvm"], "empresa": html.unescape(m["empresa"]),
                    "macrossetor": setores.get(cd, ("", "Não classificado"))[1],
                    "secao": m["secao"], "titulo_secao": m["titulo_secao"],
                    "grupo_secao": grupo_secao(m["secao"]),
                    "termos": [], "ia_gen": False, "trecho": RE_CONTROLE.sub(" ", html.unescape(m["trecho"])), "norm": chave[2],
                }
            t["termos"].append(m["termo"])
            t["ia_gen"] |= m["camada"] == "ia_gen"
    return list(trechos.values())


def alocar(tamanhos, total):
    """Raiz do tamanho, com mínimo; nunca mais que o estrato inteiro."""
    aloc = {k: min(n, MINIMO) for k, n in tamanhos.items()}
    while sum(aloc.values()) < total:
        abertos = {k: math.sqrt(n) for k, n in tamanhos.items() if aloc[k] < n}
        if not abertos:
            break
        resto = total - sum(aloc.values())
        soma = sum(abertos.values())
        mudou = False
        for k, w in abertos.items():
            extra = min(tamanhos[k] - aloc[k], max(1, round(resto * w / soma)))
            extra = min(extra, total - sum(aloc.values()))
            if extra > 0:
                aloc[k] += extra
                mudou = True
        if not mudou:
            break
    return aloc


def sortear(trechos, n, rng, textos_usados, por_empresa):
    por_setor = defaultdict(list)
    for t in trechos:
        por_setor[t["macrossetor"]].append(t)
    for lista in por_setor.values():
        rng.shuffle(lista)
    ordem = list(por_setor)
    rng.shuffle(ordem)
    escolhidos = []
    while len(escolhidos) < n and any(por_setor.values()):
        for s in ordem:
            while por_setor[s]:
                t = por_setor[s].pop()
                if t["norm"] in textos_usados or por_empresa[(t["ano"], t["cd_cvm"])] >= POR_EMPRESA:
                    continue
                escolhidos.append(t)
                textos_usados.add(t["norm"])
                por_empresa[(t["ano"], t["cd_cvm"])] += 1
                break
            if len(escolhidos) == n:
                break
    return escolhidos


def gravar_xlsx(caminho, calibracao, ouro):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font
    from openpyxl.worksheet.datavalidation import DataValidation

    visiveis = ["id_trecho", "empresa", "secao", "titulo_secao", "termos", "trecho"]
    larguras = {"id_trecho": 18, "empresa": 24, "secao": 7, "titulo_secao": 22, "termos": 16,
                "trecho": 90, "justificativa": 40, "governanca": 26}
    wb = Workbook()
    wb.remove(wb.active)
    for nome, linhas in (("calibracao", calibracao), ("ouro", ouro)):
        ws = wb.create_sheet(nome)
        cab = visiveis + COLUNAS_ANOTACAO
        ws.append(cab)
        for c in ws[1]:
            c.font = Font(bold=True)
        for t in linhas:
            ws.append([t[c] if c in t else "" for c in visiveis] + [""] * len(COLUNAS_ANOTACAO))
        n = len(linhas) + 1
        for i, col in enumerate(cab, 1):
            letra = ws.cell(1, i).column_letter
            ws.column_dimensions[letra].width = larguras.get(col, 14)
            if col in CODIGOS:
                dv = DataValidation(type="list", formula1='"' + ",".join(CODIGOS[col]) + '"',
                                    allow_blank=True)
                dv.add(f"{letra}2:{letra}{n}")
                ws.add_data_validation(dv)
            if col == "governanca":
                dv = DataValidation(allow_blank=True, showInputMessage=True,
                                    promptTitle="Governança (marcar todas)", prompt=GOVERNANCA)
                dv.add(f"{letra}2:{letra}{n}")
                ws.add_data_validation(dv)
        for row in ws.iter_rows(min_row=2):
            for c in row:
                c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.freeze_panes = "B2"
    ws = wb.create_sheet("codigos")
    ws.append(["dimensão", "códigos"])
    for k, v in CODIGOS.items():
        ws.append([k, ", ".join(v)])
    ws.append(["governanca", GOVERNANCA + " (separar por ponto e vírgula)"])
    ws.append([])
    ws.append(["Guia de anotação v1: https://claude.ai/artifact/5GhmmyURj7TFZw3K2aDbn1"])
    wb.save(caminho)


def main(pasta, cadastro, saida, *anos):
    rng = random.Random(SEMENTE)
    setores = carregar_cadastro(cadastro)
    pop = carregar_populacao(pasta, anos, setores)
    estratos = defaultdict(list)
    for t in sorted(pop, key=lambda t: t["id_trecho"]):
        grupo = "IA generativa" if t["ia_gen"] else t["grupo_secao"]
        estratos[(t["ano"], grupo)].append(t)

    amostra, linhas_estrato, textos_usados = [], [], set()
    por_empresa = defaultdict(int)
    for a in anos:
        tamanhos = {g: len(v) for (ano, g), v in estratos.items() if ano == a}
        for g, n in sorted(alocar(tamanhos, POR_ANO).items()):
            sorteados = sortear(estratos[(a, g)], n, rng, textos_usados, por_empresa)
            peso = round(tamanhos[g] / len(sorteados), 4) if sorteados else 0
            for t in sorteados:
                t["estrato"], t["peso"] = f"{a} | {g}", peso
            amostra += sorteados
            linhas_estrato.append({"ano": a, "grupo_secao": g, "trechos_populacao": tamanhos[g],
                                   "sorteados": len(sorteados), "peso": peso})

    # calibração: alterna estratos para cobrir anos e grupos
    rng.shuffle(amostra)
    por_estrato = defaultdict(list)
    for t in amostra:
        por_estrato[t["estrato"]].append(t)
    calibracao = []
    while len(calibracao) < CALIBRACAO:
        for e in sorted(por_estrato):
            if por_estrato[e] and len(calibracao) < CALIBRACAO:
                calibracao.append(por_estrato[e].pop())
    ids_cal = {t["id_trecho"] for t in calibracao}
    ouro = [t for t in amostra if t["id_trecho"] not in ids_cal]
    for t in amostra:
        t["rodada"] = "calibracao" if t["id_trecho"] in ids_cal else "ouro"
        t["termos"] = "; ".join(dict.fromkeys(t["termos"]))

    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    campos = ["id_trecho", "rodada", "ano", "cd_cvm", "empresa", "macrossetor", "secao",
              "titulo_secao", "grupo_secao", "estrato", "peso", "ia_gen", "termos", "trecho"]
    with open(saida / "amostra_v1.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos + COLUNAS_ANOTACAO, extrasaction="ignore")
        w.writeheader()
        for t in calibracao + ouro:
            w.writerow(t)
    with open(saida / "populacao_estratos.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas_estrato[0]))
        w.writeheader()
        w.writerows(linhas_estrato)
    for anotador in ("A", "B"):
        gravar_xlsx(saida / f"anotacao_v1_{anotador}.xlsx", calibracao, ouro)
    print(f"população: {len(pop)} trechos; amostra: {len(amostra)} "
          f"({len(calibracao)} calibração + {len(ouro)} ouro) -> {saida}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], *sys.argv[4:])
