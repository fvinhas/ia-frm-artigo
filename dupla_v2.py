"""Etapa 7c — resultados da anotação dupla às cegas (anotacao_v2.py).

Uso:
    python dupla_v2.py comparar   PASTA_ANOTACAO
    python dupla_v2.py consenso   PASTA_ANOTACAO

comparar  lê dupla_v2/anotacao_v2_anotador1.xlsx e _anotador2.xlsx, a classificação do v3
          (classificacoes_llm_v3.csv) e os tipos de risco do modelo (llm_risco/saida_*.jsonl e
          consistencia_saida.jsonl). Grava em dupla_v2/:
            concordancia_v2.csv     acordo e α de Krippendorff por dimensão, para os pares
                                    anotador1×anotador2, modelo×anotador1 e modelo×anotador2
            f1_v2.csv               F1 por classe de função (falso positivo como classe)
            tipos_risco_v2.csv      tipo principal (α) e cada tipo como presença/ausência (α)
            anotacoes_v2.csv        os códigos dos dois anotadores, trecho a trecho (sem o texto)
            adjudicacao_v2.xlsx     os trechos em que os dois anotadores divergem, com as duas
                                    respostas lado a lado e colunas para o consenso do autor. A
                                    saída do modelo não aparece, para não puxar o consenso para ela.
consenso  lê a adjudicação preenchida e compara o modelo com o consenso (concordancia_consenso_v2.csv,
          f1_consenso_v2.csv); nos trechos sem divergência, o consenso é a resposta comum.
"""
import csv
import glob
import json
import re
import sys
from collections import Counter
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from verificacao import alfa_nominal, f1_por_classe

DIMS = ("funcao", "evidencia", "tom", "tempo")
CLASSES = ("RISCO", "USO", "PROD", "NEGOCIO", "GENERICA", "GOV", "FALSO_POSITIVO")
TIPOS = ("REGULACAO", "SEGURANCA", "CONCORRENCIA", "OPERACIONAL", "REPUTACAO_ETICA", "TRABALHO", "GENERICO")
LISTAS = {"falso_positivo": "sim,nao", "funcao": "RISCO,USO,PROD,NEGOCIO,GENERICA,GOV",
          "evidencia": "SEM,CASO,METRICA", "tom": "POS,NEU,NEG", "tempo": "REALIZADO,EM_CURSO,PLANEJADO,NA"}
norm = lambda v: str(v if v is not None else "").strip()
sim = lambda v: norm(v).lower() in ("sim", "true")
gov = lambda v: frozenset(g.strip().lower() for g in re.split(r"[;,]", norm(v)) if g.strip()) or frozenset({"nenhuma"})
tipos = lambda v: frozenset(t.strip().upper() for t in re.split(r"[;,]", norm(v)) if t.strip()) if isinstance(v, str) else frozenset(v or ())


def ler_aba(caminho, aba):
    linhas = list(load_workbook(caminho, read_only=True)[aba].iter_rows(values_only=True))
    cab = linhas[0]
    return {r[cab.index("id_trecho")]: dict(zip(cab, r)) for r in linhas[1:] if r[cab.index("id_trecho")]}


def rotulo(r):
    return "FALSO_POSITIVO" if sim(r["falso_positivo"]) else norm(r["funcao"]).upper()


def comparar_par(a, b, ids):
    """Acordo e α entre duas codificações (dicts por id), nos ids dados."""
    linhas = []
    pares = [(sim(a[i]["falso_positivo"]), sim(b[i]["falso_positivo"])) for i in ids]
    linhas.append(("falso_positivo", pares))
    linhas.append(("funcao_com_fp", [(rotulo(a[i]), rotulo(b[i])) for i in ids]))
    validos = [i for i in ids if not sim(a[i]["falso_positivo"]) and not sim(b[i]["falso_positivo"])]
    for d in DIMS:
        linhas.append((d, [(norm(a[i][d]).upper(), norm(b[i][d]).upper()) for i in validos]))
    linhas.append(("governanca_declarada", [("nenhuma" not in gov(a[i]["governanca"]), "nenhuma" not in gov(b[i]["governanca"]))
                                           for i in validos]))
    linhas.append(("governanca_conjunto", [(gov(a[i]["governanca"]), gov(b[i]["governanca"])) for i in validos]))
    return [{"dimensao": d, "n": len(p), "acordo_pct": round(100 * sum(x == y for x, y in p) / len(p), 1),
             "alfa": alfa_nominal(p)} for d, p in linhas]


def na_populacao(pasta):
    """Ids da população atual: trechos que o dicionário deixou de detectar (chatbot, assistente virtual e
    modelo preditivo sem nomear IA, desde 30/10/2026) saem da validação, como saem da análise."""
    return {t["id_trecho"] for t in csv.DictReader(open(pasta / "populacao_v1.csv", encoding="utf-8-sig"))}


def modelo_v3(pasta):
    return {r["id_trecho"]: r for r in csv.DictReader(open(pasta / "classificacoes_llm_v3.csv", encoding="utf-8"))}


def gravar(caminho, linhas):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)


def cmd_comparar(pasta):
    pasta = Path(pasta)
    dupla = pasta / "dupla_v2"
    a1 = ler_aba(dupla / "anotacao_v2_anotador1.xlsx", "trechos")
    a2 = ler_aba(dupla / "anotacao_v2_anotador2.xlsx", "trechos")
    modelo = modelo_v3(pasta)
    pop = na_populacao(pasta)
    ids = [i for i in a1 if i in a2 and i in pop and not sim(a1[i]["conflito"]) and not sim(a2[i]["conflito"])]
    faltando = [i for i in ids if not norm(a1[i]["falso_positivo"]) or not norm(a2[i]["falso_positivo"])]
    print(f"{len(ids)} trechos sem conflito e na população atual; {len(faltando)} sem resposta")

    conc = []
    for nome, x, y in (("anotador1_x_anotador2", a1, a2), ("modelo_x_anotador1", a1, modelo), ("modelo_x_anotador2", a2, modelo)):
        for l in comparar_par(x, y, ids):
            conc.append({"par": nome, **l})
    gravar(dupla / "concordancia_v2.csv", conc)
    for l in conc:
        print(f"{l['par']:22} {l['dimensao']:22} n={l['n']:3} acordo {l['acordo_pct']:5} α {l['alfa']}")

    f1 = []
    for nome, ref, outro in (("anotador2_vs_anotador1", a1, a2), ("modelo_vs_anotador1", a1, modelo), ("modelo_vs_anotador2", a2, modelo)):
        for l in f1_por_classe([(rotulo(ref[i]), rotulo(outro[i])) for i in ids], CLASSES):
            f1.append({"par": nome, **l})
    gravar(dupla / "f1_v2.csv", f1)
    print("F1 função (referência = anotador 1):")
    for nome in ("anotador2_vs_anotador1", "modelo_vs_anotador1", "modelo_vs_anotador2"):
        print(f"  {nome:24}", " · ".join(f"{l['classe']} {l['f1']}" for l in f1 if l["par"] == nome))

    copia = sum(all(norm(a1[i][c]) == norm(a2[i][c]) for c in ("falso_positivo", "funcao", "evidencia", "governanca", "tom", "tempo"))
                for i in ids)
    print(f"linhas idênticas nas seis dimensões: {copia} de {len(ids)}")

    campos = ("falso_positivo", "funcao", "evidencia", "governanca", "tom", "tempo", "duvida")
    gravar(dupla / "anotacoes_v2.csv", [{"id_trecho": i, **{f"a{k}_{c}": norm(a[i][c]) for k, a in ((1, a1), (2, a2)) for c in campos}}
                                        for i in ids])
    tipos_risco(pasta, dupla)
    planilha_adjudicacao(dupla, a1, a2, ids)


def tipos_risco(pasta, dupla):
    r1 = ler_aba(dupla / "anotacao_v2_anotador1.xlsx", "tipos_risco")
    r2 = ler_aba(dupla / "anotacao_v2_anotador2.xlsx", "tipos_risco")
    m1, m2 = {}, {}
    for arq, destino in [(a, m1) for a in sorted(glob.glob(str(pasta / "llm_risco" / "saida_*.jsonl")))] + \
                        [(str(pasta / "llm_risco" / "consistencia_saida.jsonl"), m2)]:
        for linha in open(arq, encoding="utf-8"):
            if linha.strip():
                r = json.loads(linha)
                destino[r["id_trecho"]] = r
    pop = na_populacao(pasta)
    ids = [i for i in r1 if i in r2 and i in m1 and i in pop and not sim(r1[i]["conflito"]) and not sim(r2[i]["conflito"])]
    codif = {"anotador1": r1, "anotador2": r2, "modelo": m1, "modelo_rodada2": m2}
    linhas = []
    for x, y in (("anotador1", "anotador2"), ("modelo", "anotador1"), ("modelo", "anotador2"), ("modelo", "modelo_rodada2")):
        a, b = codif[x], codif[y]
        comuns = [i for i in ids if i in b]
        p = [(norm(a[i]["principal"]).upper(), norm(b[i]["principal"]).upper()) for i in comuns]
        jac = [len(tipos(a[i]["tipos"]) & tipos(b[i]["tipos"])) / len(tipos(a[i]["tipos"]) | tipos(b[i]["tipos"]))
               for i in comuns if tipos(a[i]["tipos"]) | tipos(b[i]["tipos"])]
        linha = {"par": f"{x}_x_{y}", "n": len(comuns),
                 "principal_acordo_pct": round(100 * sum(u == v for u, v in p) / len(p), 1),
                 "principal_alfa": alfa_nominal(p), "jaccard_medio": round(sum(jac) / len(jac), 2)}
        for t in TIPOS:
            linha[f"alfa_{t}"] = alfa_nominal([(t in tipos(a[i]["tipos"]), t in tipos(b[i]["tipos"])) for i in comuns])
        linhas.append(linha)
    gravar(dupla / "tipos_risco_v2.csv", linhas)
    print("Tipos de risco:")
    for l in linhas:
        print(f"  {l['par']:30} n={l['n']} principal {l['principal_acordo_pct']}% α {l['principal_alfa']} "
              f"Jaccard {l['jaccard_medio']} |", " ".join(f"{t[:4]} {l['alfa_' + t]}" for t in TIPOS))


def diverge(x, y):
    if sim(x["falso_positivo"]) != sim(y["falso_positivo"]):
        return ["falso_positivo"]
    if sim(x["falso_positivo"]):
        return []
    d = [c for c in DIMS if norm(x[c]).upper() != norm(y[c]).upper()]
    return d + (["governanca"] if gov(x["governanca"]) != gov(y["governanca"]) else [])


def planilha_adjudicacao(dupla, a1, a2, ids):
    if (dupla / "adjudicacao_v2.xlsx").exists():
        print("adjudicacao_v2.xlsx já existe (preenchida pelo autor); não foi regravada")
        return
    wb = Workbook()
    ws = wb.active
    ws.title = "adjudicacao"
    ws.append(["Adjudicação da anotação dupla v2 — só os trechos em que os dois anotadores divergem. "
               "Para cada linha, preencha as colunas 'consenso_*' (a resposta final). Copie a resposta de um dos "
               "anotadores ou escreva outra. Nas dimensões em que os dois concordam, o consenso já vem preenchido. "
               "A saída do modelo não aparece de propósito."])
    cab = ["n", "id_trecho", "empresa", "secao", "trecho", "divergem_em"]
    campos = ("falso_positivo", "funcao", "evidencia", "governanca", "tom", "tempo")
    for c in campos:
        cab += [f"a1_{c}", f"a2_{c}", f"consenso_{c}"]
    cab += ["a1_justificativa", "a2_justificativa", "comentario"]
    ws.append(cab)
    n = 0
    for i in ids:
        d = diverge(a1[i], a2[i])
        if not d:
            continue
        n += 1
        linha = [n, i, a1[i]["empresa"], a1[i]["secao"], a1[i]["trecho"], ", ".join(d)]
        for c in campos:
            v1, v2 = norm(a1[i][c]), norm(a2[i][c])
            igual = gov(v1) == gov(v2) if c == "governanca" else v1.upper() == v2.upper()
            linha += [v1, v2, v1 if igual and c not in d else ""]
        linha += [norm(a1[i]["justificativa"]), norm(a2[i]["justificativa"]), ""]
        ws.append(linha)
    amarelo = PatternFill("solid", fgColor="FFF2CC")
    for col, c in enumerate(cab, 1):
        ws.cell(2, col).font = Font(bold=True)
        if c.startswith("consenso_"):
            for row in range(3, n + 3):
                ws.cell(row, col).fill = amarelo
            base = c.removeprefix("consenso_") if hasattr(c, "removeprefix") else c[len("consenso_"):]
            if base in LISTAS:
                dv = DataValidation(type="list", formula1=f'"{LISTAS[base]}"', allow_blank=True)
                ws.add_data_validation(dv)
                dv.add(f"{ws.cell(3, col).column_letter}3:{ws.cell(3, col).column_letter}{n + 2}")
    ws.column_dimensions["E"].width = 80
    for row in ws.iter_rows(min_row=3, min_col=5, max_col=5):
        row[0].alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "F3"
    wb.save(dupla / "adjudicacao_v2.xlsx")
    print(f"{n} trechos com divergência -> {dupla / 'adjudicacao_v2.xlsx'}")


def cmd_consenso(pasta):
    pasta = Path(pasta)
    dupla = pasta / "dupla_v2"
    a1 = ler_aba(dupla / "anotacao_v2_anotador1.xlsx", "trechos")
    a2 = ler_aba(dupla / "anotacao_v2_anotador2.xlsx", "trechos")
    linhas = list(load_workbook(dupla / "adjudicacao_v2.xlsx", read_only=True)["adjudicacao"].iter_rows(values_only=True))
    cab = linhas[1]
    adj = {r[cab.index("id_trecho")]: dict(zip(cab, r)) for r in linhas[2:] if r[cab.index("id_trecho")]}
    pop = na_populacao(pasta)
    ids = [i for i in a1 if i in a2 and i in pop and not sim(a1[i]["conflito"]) and not sim(a2[i]["conflito"])]
    consenso, incompletos = {}, []
    for i in ids:
        if i in adj:
            c = {k: adj[i][f"consenso_{k}"] for k in ("falso_positivo", "funcao", "evidencia", "governanca", "tom", "tempo")}
            if not norm(c["falso_positivo"]) or (not sim(c["falso_positivo"]) and not all(norm(c[k]) for k in DIMS)):
                incompletos.append(i)
            consenso[i] = c
        else:
            consenso[i] = a1[i]
    if incompletos:
        print(f"{len(incompletos)} trechos da adjudicação sem consenso preenchido; preencha antes de rodar de novo")
        return
    modelo = modelo_v3(pasta)
    conc = [{"par": "modelo_x_consenso", **l} for l in comparar_par(consenso, modelo, ids)]
    gravar(dupla / "concordancia_consenso_v2.csv", conc)
    f1 = [{"par": "modelo_vs_consenso", **l} for l in f1_por_classe([(rotulo(consenso[i]), rotulo(modelo[i])) for i in ids], CLASSES)]
    gravar(dupla / "f1_consenso_v2.csv", f1)
    with open(dupla / "consenso_v2.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id_trecho", "falso_positivo", "funcao", "evidencia", "governanca", "tom", "tempo", "origem"])
        for i in ids:
            c = consenso[i]
            w.writerow([i] + [norm(c[k]) for k in ("falso_positivo", "funcao", "evidencia", "governanca", "tom", "tempo")]
                       + ["adjudicado" if i in adj else "acordo"])
    for l in conc:
        print(f"{l['dimensao']:22} n={l['n']:3} acordo {l['acordo_pct']:5} α {l['alfa']}")
    print("F1:", " · ".join(f"{l['classe']} {l['f1']}" for l in f1))


if __name__ == "__main__":
    {"comparar": cmd_comparar, "consenso": cmd_consenso}[sys.argv[1]](*sys.argv[2:])
