"""Etapa 9 — banco de exemplos qualitativos para o artigo da H2D.

Uso:
    python exemplos_h2d.py OURO.csv SAIDA.xlsx

Candidatos vêm do padrão-ouro (códigos confirmados pelo autor, na anotação cega ou na verificação),
sem falsos positivos nem trechos marcados com dúvida, com 200 a 900 caracteres. Por grupo, até
POR_GRUPO trechos, alternando anos e macrossetores, uma vez só por companhia no grupo e no máximo
MAX_EMPRESA vezes no banco inteiro. Grupos: as seis funções e, para a discussão da evidência,
produtividade com métrica e produtividade sem evidência.

O autor escolhe na coluna "usar" os 2–3 por grupo que entram no texto.
"""
import csv
import random
import sys
from collections import defaultdict

SEMENTE = 20261030
POR_GRUPO = 10
MAX_EMPRESA = 3
GRUPOS = [
    ("Risco", lambda t: t["funcao"] == "RISCO"),
    ("Uso", lambda t: t["funcao"] == "USO"),
    ("Produtividade", lambda t: t["funcao"] == "PROD"),
    ("Negócio", lambda t: t["funcao"] == "NEGOCIO"),
    ("Genérica", lambda t: t["funcao"] == "GENERICA"),
    ("Governança", lambda t: t["funcao"] == "GOV"),
    ("Produtividade com métrica", lambda t: t["funcao"] == "PROD" and t["evidencia"] == "METRICA"),
    ("Produtividade sem evidência", lambda t: t["funcao"] == "PROD" and t["evidencia"] == "SEM"),
]
COLUNAS = ["grupo", "usar", "observacao", "ano", "empresa", "macrossetor", "secao", "titulo_secao",
           "funcao", "evidencia", "tom", "tempo", "governanca", "origem", "id_trecho", "trecho"]


def escolher(cands, rng, usos):
    por_ano = defaultdict(list)
    for t in cands:
        por_ano[t["ano"]].append(t)
    for lista in por_ano.values():
        rng.shuffle(lista)
        # alterna macrossetores dentro do ano: 1º de cada setor, depois o 2º de cada, ...
        vistos, ordem = defaultdict(int), {}
        for t in lista:
            ordem[t["id_trecho"]] = vistos[t["macrossetor"]]
            vistos[t["macrossetor"]] += 1
        lista.sort(key=lambda t: ordem[t["id_trecho"]])
    escolhidos, empresas = [], set()
    while len(escolhidos) < POR_GRUPO and any(por_ano.values()):
        for a in sorted(por_ano):
            while por_ano[a]:
                t = por_ano[a].pop(0)
                if t["cd_cvm"] in empresas or usos[t["cd_cvm"]] >= MAX_EMPRESA:
                    continue
                escolhidos.append(t)
                empresas.add(t["cd_cvm"])
                usos[t["cd_cvm"]] += 1
                break
            if len(escolhidos) == POR_GRUPO:
                break
    return sorted(escolhidos, key=lambda t: t["ano"])


def main(ouro_csv, saida):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font
    from openpyxl.worksheet.datavalidation import DataValidation

    rng = random.Random(SEMENTE)
    ouro = [t for t in csv.DictReader(open(ouro_csv, encoding="utf-8-sig"))
            if t["falso_positivo"] != "sim" and t["duvida"] != "sim" and 200 <= len(t["trecho"]) <= 900]
    usos = defaultdict(int)
    linhas = []
    for nome, filtro in GRUPOS:
        for t in escolher([t for t in ouro if filtro(t)], rng, usos):
            linhas.append({**t, "grupo": nome, "usar": "", "observacao": ""})

    wb = Workbook()
    ws = wb.active
    ws.title = "exemplos"
    ws.append(COLUNAS)
    for c in ws[1]:
        c.font = Font(bold=True)
    for l in linhas:
        ws.append([l.get(c, "") for c in COLUNAS])
    larguras = {"grupo": 16, "usar": 7, "observacao": 24, "ano": 6, "empresa": 24, "macrossetor": 16,
                "secao": 7, "titulo_secao": 20, "id_trecho": 18, "trecho": 90}
    for i, col in enumerate(COLUNAS, 1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = larguras.get(col, 11)
    dv = DataValidation(type="list", formula1='"sim,nao"', allow_blank=True)
    dv.add(f"B2:B{len(linhas) + 1}")
    ws.add_data_validation(dv)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "D2"
    ws.auto_filter.ref = ws.dimensions
    nota = wb.create_sheet("leia")
    for texto in (
        "Banco de exemplos para a leitura próxima no artigo da H2D (exemplos_h2d.py, semente 20261030).",
        "Fonte: padrão-ouro (códigos confirmados pelo autor), sem falsos positivos nem dúvidas, 200–900 caracteres.",
        "Marque 'usar = sim' nos 2–3 trechos por grupo que entram no texto; use 'observacao' para o porquê.",
        "Os FRE são documentos públicos; citar com empresa, ano e seção (ex.: Empresa, FRE 2026, seção 4.1).",
        "Antes de escolher, retire qualquer trecho da instituição onde o autor trabalha (restrição do projeto).",
    ):
        nota.append([texto])
    nota.column_dimensions["A"].width = 120
    wb.save(saida)
    por_grupo = defaultdict(int)
    for l in linhas:
        por_grupo[l["grupo"]] += 1
    print(f"{len(linhas)} candidatos -> {saida}", dict(por_grupo))


if __name__ == "__main__":
    main(*sys.argv[1:3])
