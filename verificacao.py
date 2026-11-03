"""Etapa 7 — desenho híbrido de validação: 100 trechos cegos + verificação dos demais.

    python verificacao.py cega AMOSTRA.csv SAIDA_DIR
    python verificacao.py lotes AMOSTRA.csv LOTES_DIR [TAMANHO]
    python verificacao.py populacao PASTA_DADOS cad_cia_aberta.csv POPULACAO.csv 2023 2024 2025 2026
    python verificacao.py juntar LOTES_DIR SAIDA.csv
    python verificacao.py planilha AMOSTRA.csv CLASSIFICACOES.csv CEGA_IDS.csv SAIDA.xlsx
    python verificacao.py comparar CEGA.xlsx CLASSIFICACOES.csv SAIDA_DIR
    python verificacao.py revisar_v2 OURO.csv CLASSIFICACOES_V2.csv SAIDA_DIR
    python verificacao.py ouro AMOSTRA.csv CEGA.xlsx VERIFICACAO.xlsx CLASSIFICACOES.csv SAIDA_DIR [ADJUDICACOES.csv]

Sorteia os 100 trechos que o autor anota sem ver o modelo: os 50 da calibração mais
50 do ouro (equilibrados por ano). Grava SAIDA_DIR/cega_v1_ids.csv e
SAIDA_DIR/anotacao_cega_v1.xlsx (abas instrucoes, cega, codigos).
Os outros trechos da amostra vão para a planilha de verificação, que traz a
proposta do modelo e só é aberta depois que a anotação cega estiver pronta.
"""
import csv
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

from amostrar_anotacao import CODIGOS, GOVERNANCA

SEMENTE = 20261029
EXTRA_OURO = 50

DEFINICOES = [
    ("falso_positivo", "sim", "O termo não se refere a inteligência artificial (ex.: sigla de outra coisa). Marque e pule as demais colunas."),
    ("funcao", "PROD", "Promessa ou expectativa de ganho de produtividade, eficiência, redução de custo ou tempo atribuída à IA."),
    ("funcao", "USO", "Uso concreto já implantado, sem afirmar ganho (ferramenta, área e finalidade nomeadas)."),
    ("funcao", "NEGOCIO", "IA como produto, serviço ou fonte de receita para clientes."),
    ("funcao", "RISCO", "IA como fonte de risco ou ameaça (concorrência, regulação, falhas, viés, segurança, privacidade)."),
    ("funcao", "GOV", "Regras, estruturas ou responsabilidades sobre o uso de IA são o assunto principal."),
    ("funcao", "GENERICA", "Menção vaga, aspiracional ou de contexto, sem as funções acima."),
    ("evidencia", "METRICA", "Número, percentual, valor monetário ou prazo ligado à IA."),
    ("evidencia", "CASO", "Aplicação específica (área, processo ou sistema identificável), sem número."),
    ("evidencia", "SEM", "Nem métrica nem caso."),
    ("governanca", "", GOVERNANCA + " — marque todas as que aparecem, separadas por ponto e vírgula."),
    ("tom", "POS / NEU / NEG", "Oportunidade ou vantagem / descritivo / ameaça, limitação ou custo."),
    ("tempo", "REALIZADO", "Já implantado ou concluído."),
    ("tempo", "EM_CURSO", "Em implantação, piloto ou teste."),
    ("tempo", "PLANEJADO", "Intenção, plano ou expectativa futura."),
    ("tempo", "NA", "Sem referência temporal (típico de RISCO e GENERICA)."),
]
DESEMPATE = [
    "PROD prevalece sobre USO quando o trecho afirma ganho, mesmo que descreva o uso.",
    "RISCO prevalece na seção 4.1 ou 4.2 quando a IA é ameaça, mesmo que cite governança como mitigação.",
    "GOV só quando a regra ou estrutura é o assunto principal; \"uso responsável\" de passagem é GENERICA.",
]
INSTRUCOES = [
    "Anotação cega — 100 trechos (guia de anotação v1)",
    "",
    "1. Leia a aba \"codigos\" (definições e regras de desempate). O guia completo está em https://claude.ai/artifact/5GhmmyURj7TFZw3K2aDbn1, aba \"Guia de anotação v1\".",
    "2. Na aba \"cega\", leia cada trecho. O termo de IA encontrado está em negrito. Use só o trecho, a seção e o nome da empresa; não consulte o formulário nem fontes externas.",
    "3. Primeiro decida se é falso positivo. Se for, marque falso_positivo = sim e passe ao próximo.",
    "4. Se não for, marque falso_positivo = nao e preencha funcao, evidencia, governanca, tom e tempo (listas suspensas; governança é texto, ver aba codigos).",
    "5. Em dúvida entre dois códigos, aplique o desempate, escolha um, marque duvida = sim e escreva uma linha em justificativa.",
    "6. Não procure a classificação do modelo antes de terminar os 100: ela fica guardada à parte e só será comparada depois.",
    "7. Pode parar e retomar quando quiser; salve o arquivo com o mesmo nome. Tempo estimado: cerca de 2 horas.",
    "8. Ao terminar, avise o autor: a planilha de verificação dos demais trechos é liberada em seguida.",
]


def selecionar(amostra):
    rng = random.Random(SEMENTE)
    cal = [t for t in amostra if t["rodada"] == "calibracao"]
    por_ano = defaultdict(list)
    for t in amostra:
        if t["rodada"] == "ouro":
            por_ano[t["ano"]].append(t)
    anos = sorted(por_ano)
    extra = []
    for i, a in enumerate(anos):
        n = EXTRA_OURO // len(anos) + (1 if i < EXTRA_OURO % len(anos) else 0)
        extra += rng.sample(sorted(por_ano[a], key=lambda t: t["id_trecho"]), n)
    cega = cal + extra
    rng.shuffle(cega)
    return cega


def texto_destacado(trecho, termos):
    """Rich text com os termos de IA em negrito (o Excel mostra como no documento)."""
    from openpyxl.cell.rich_text import CellRichText, TextBlock
    from openpyxl.cell.text import InlineFont

    padrao = "|".join(re.escape(t) for t in sorted({t.strip() for t in termos.split(";") if t.strip()},
                                                    key=len, reverse=True))
    if not padrao:
        return trecho
    partes, ini = CellRichText(), 0
    for m in re.finditer(rf"(?<!\w)(?:{padrao})(?!\w)", trecho):
        if m.start() > ini:
            partes.append(trecho[ini:m.start()])
        partes.append(TextBlock(InlineFont(b=True), m.group(0)))
        ini = m.end()
    if ini < len(trecho):
        partes.append(trecho[ini:])
    return partes if len(partes) > 1 else trecho


def planilha_cega(caminho, cega):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    ws = wb.active
    ws.title = "instrucoes"
    for linha in INSTRUCOES:
        ws.append([linha])
    ws["A1"].font = Font(bold=True, size=13)
    ws.column_dimensions["A"].width = 140

    ws = wb.create_sheet("cega")
    visiveis = ["n", "id_trecho", "empresa", "secao", "titulo_secao", "trecho"]
    anotacao = ["falso_positivo", "funcao", "evidencia", "governanca", "tom", "tempo", "duvida", "justificativa"]
    cab = visiveis + anotacao
    ws.append(cab)
    for c in ws[1]:
        c.font = Font(bold=True)
    for i, t in enumerate(cega, 1):
        ws.append([i, t["id_trecho"], t["empresa"], t["secao"], t["titulo_secao"], ""] + [""] * len(anotacao))
        ws.cell(i + 1, visiveis.index("trecho") + 1).value = texto_destacado(t["trecho"], t["termos"])
    larguras = {"n": 5, "id_trecho": 17, "empresa": 22, "secao": 7, "titulo_secao": 20, "trecho": 85,
                "governanca": 24, "justificativa": 36}
    fim = len(cega) + 1
    for i, col in enumerate(cab, 1):
        letra = ws.cell(1, i).column_letter
        ws.column_dimensions[letra].width = larguras.get(col, 13)
        if col in CODIGOS:
            dv = DataValidation(type="list", formula1='"' + ",".join(CODIGOS[col]) + '"', allow_blank=True)
            dv.add(f"{letra}2:{letra}{fim}")
            ws.add_data_validation(dv)
        if col == "governanca":
            dv = DataValidation(allow_blank=True, showInputMessage=True,
                                promptTitle="Governança (marcar todas)", prompt=GOVERNANCA)
            dv.add(f"{letra}2:{letra}{fim}")
            ws.add_data_validation(dv)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "G2"

    ws = wb.create_sheet("codigos")
    ws.append(["dimensão", "código", "definição"])
    for c in ws[1]:
        c.font = Font(bold=True)
    for d in DEFINICOES:
        ws.append(list(d))
    ws.append([])
    ws.append(["desempate", "", ""])
    ws.cell(ws.max_row, 1).font = Font(bold=True)
    for i, r in enumerate(DESEMPATE, 1):
        ws.append(["", str(i), r])
    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 110
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    wb.save(caminho)


def cmd_cega(amostra_csv, saida):
    amostra = list(csv.DictReader(open(amostra_csv, encoding="utf-8-sig")))
    cega = selecionar(amostra)
    saida = Path(saida)
    with open(saida / "cega_v1_ids.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["n", "id_trecho", "rodada", "ano"])
        for i, t in enumerate(cega, 1):
            w.writerow([i, t["id_trecho"], t["rodada"], t["ano"]])
    planilha_cega(saida / "anotacao_cega_v1.xlsx", cega)
    print(f"{len(cega)} trechos cegos -> {saida / 'anotacao_cega_v1.xlsx'}")


def cmd_populacao(pasta, cadastro, saida, *anos):
    """Todos os trechos únicos com menção a IA (mesma unidade e mesmos ids da amostra)."""
    from amostrar_anotacao import carregar_populacao
    from setores import carregar_cadastro

    pop = sorted(carregar_populacao(pasta, anos, carregar_cadastro(cadastro)), key=lambda t: t["id_trecho"])
    campos = ["id_trecho", "ano", "cd_cvm", "empresa", "macrossetor", "secao", "titulo_secao",
              "grupo_secao", "ia_gen", "termos", "trecho"]
    with open(saida, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        for t in pop:
            w.writerow({**t, "termos": "; ".join(dict.fromkeys(t["termos"]))})
    print(f"{len(pop)} trechos -> {saida}")


def cmd_lotes(amostra_csv, pasta, tamanho="50"):
    """Divide a amostra em lotes de entrada para o classificador (agentes isolados).

    A ordem é embaralhada com semente fixa, para cada lote misturar anos e seções, e os
    lotes não dizem quais trechos são da anotação cega.
    """
    amostra = list(csv.DictReader(open(amostra_csv, encoding="utf-8-sig")))
    random.Random(SEMENTE).shuffle(amostra)
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    n = int(tamanho)
    campos = ["id_trecho", "empresa", "secao", "titulo_secao", "termos", "trecho"]
    for k in range(0, len(amostra), n):
        with open(pasta / f"entrada_{k // n + 1:02d}.jsonl", "w", encoding="utf-8") as f:
            for t in amostra[k:k + n]:
                f.write(json.dumps({c: t[c] for c in campos}, ensure_ascii=False) + "\n")
    print(f"{len(amostra)} trechos em {-(-len(amostra) // n)} lotes -> {pasta}")


VALIDOS = {
    "funcao": set(CODIGOS["funcao"]), "evidencia": set(CODIGOS["evidencia"]),
    "tom": set(CODIGOS["tom"]), "tempo": set(CODIGOS["tempo"]),
}
GOV_VALIDOS = {"politica", "comite_ou_responsavel", "supervisao_humana", "protecao_dados", "nenhuma"}


def problemas(r):
    if r.get("falso_positivo"):
        return []
    erros = [f"{k}={r.get(k)!r}" for k, v in VALIDOS.items() if r.get(k) not in v]
    gov = r.get("governanca") or []
    if not gov or set(gov) - GOV_VALIDOS or ("nenhuma" in gov and len(gov) > 1):
        erros.append(f"governanca={gov!r}")
    return erros


def cmd_juntar(pasta, saida):
    """Junta saida_XX.jsonl, confere ids contra entrada_XX.jsonl e os códigos válidos."""
    pasta = Path(pasta)
    linhas, faltando, invalidos = [], [], []
    # um trecho que um agente pulou pode ter sido refeito num lote extra: vale a saída de qualquer lote
    saidas = {}
    for arq in sorted(pasta.glob("saida_*.jsonl")):
        for l in open(arq, encoding="utf-8"):
            l = l.strip()
            if l.startswith("{"):
                r = json.loads(l)
                saidas.setdefault(r.get("id_trecho"), (arq.name, r))
    vistos = set()
    for entrada in sorted(pasta.glob("entrada_*.jsonl")):
        ids = [json.loads(l)["id_trecho"] for l in open(entrada, encoding="utf-8") if l.strip()]
        for i in ids:
            if i in vistos:
                continue
            vistos.add(i)
            if i not in saidas:
                faltando.append((entrada.name, i))
                continue
            nome, r = saidas[i]
            arq = Path(nome)
            erros = problemas(r)
            if erros:
                invalidos.append((arq.name, i, erros))
            r["lote"] = arq.name
            r["governanca"] = "; ".join(r.get("governanca") or [])
            linhas.append(r)
    campos = ["id_trecho", "lote", "falso_positivo", "funcao", "evidencia", "governanca", "tom",
              "tempo", "duvida", "justificativa"]
    with open(saida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)
    print(f"{len(linhas)} classificações -> {saida}; faltando {len(faltando)}; inválidas {len(invalidos)}")
    for x in (faltando + invalidos)[:20]:
        print("  ", x)


INSTRUCOES_VERIFICACAO = [
    "Verificação das classificações do modelo (prompt classificador_v1, guia de anotação v1)",
    "",
    "1. Na aba \"verificar\", leia o trecho (termo de IA em negrito) e a proposta do modelo nas colunas cinza, com a justificativa.",
    "2. Se concorda com tudo, marque revisado = sim e siga.",
    "3. Se discorda de alguma dimensão, escreva o código certo só na coluna amarela daquela dimensão (corr_...) e marque revisado = sim. Colunas amarelas vazias = concordo.",
    "4. Se o trecho não é sobre IA, marque corr_falso_positivo = sim. Se o modelo marcou falso positivo e você discorda, marque corr_falso_positivo = nao e preencha as demais correções.",
    "5. Use comentario para dúvidas ou observações. Os códigos e as regras de desempate estão na aba \"codigos\".",
    "6. Use só o trecho, a seção e o nome da empresa. Pode parar e retomar; salve com o mesmo nome. Tempo estimado: ~30 segundos por trecho.",
]


def cmd_planilha(amostra_csv, classificacoes_csv, cega_ids_csv, saida):
    """Planilha de verificação: só os trechos fora da anotação cega."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    cega = {r["id_trecho"] for r in csv.DictReader(open(cega_ids_csv, encoding="utf-8"))}
    modelo = {r["id_trecho"]: r for r in csv.DictReader(open(classificacoes_csv, encoding="utf-8"))}
    trechos = [t for t in csv.DictReader(open(amostra_csv, encoding="utf-8-sig"))
               if t["id_trecho"] not in cega and t["id_trecho"] in modelo]
    random.Random(SEMENTE).shuffle(trechos)

    wb = Workbook()
    ws = wb.active
    ws.title = "instrucoes"
    for linha in INSTRUCOES_VERIFICACAO:
        ws.append([linha])
    ws["A1"].font = Font(bold=True, size=13)
    ws.column_dimensions["A"].width = 140

    ws = wb.create_sheet("verificar")
    texto = ["n", "id_trecho", "empresa", "secao", "titulo_secao", "trecho"]
    prop = ["m_falso_positivo", "m_funcao", "m_evidencia", "m_governanca", "m_tom", "m_tempo",
            "m_duvida", "m_justificativa"]
    corr = ["revisado", "corr_falso_positivo", "corr_funcao", "corr_evidencia", "corr_governanca",
            "corr_tom", "corr_tempo", "comentario"]
    cab = texto + prop + corr
    ws.append(cab)
    for c in ws[1]:
        c.font = Font(bold=True)
    sim_nao = lambda v: "sim" if str(v).lower() == "true" else "nao"
    for i, t in enumerate(trechos, 1):
        m = modelo[t["id_trecho"]]
        fp = sim_nao(m["falso_positivo"])
        ws.append([i, t["id_trecho"], t["empresa"], t["secao"], t["titulo_secao"], ""]
                  + [fp] + ([""] * 5 if fp == "sim" else
                            [m["funcao"], m["evidencia"], m["governanca"], m["tom"], m["tempo"]])
                  + [sim_nao(m["duvida"]), m["justificativa"]] + [""] * len(corr))
        ws.cell(i + 1, texto.index("trecho") + 1).value = texto_destacado(t["trecho"], t["termos"])
    cinza, amarelo = PatternFill("solid", fgColor="EDEDED"), PatternFill("solid", fgColor="FFF4C2")
    larguras = {"n": 5, "id_trecho": 16, "empresa": 20, "secao": 7, "titulo_secao": 18, "trecho": 80,
                "m_governanca": 20, "m_justificativa": 40, "corr_governanca": 20, "comentario": 30}
    listas = {"revisado": ["sim"], "corr_falso_positivo": ["sim", "nao"],
              "corr_funcao": CODIGOS["funcao"], "corr_evidencia": CODIGOS["evidencia"],
              "corr_tom": CODIGOS["tom"], "corr_tempo": CODIGOS["tempo"]}
    fim = len(trechos) + 1
    for i, col in enumerate(cab, 1):
        letra = ws.cell(1, i).column_letter
        ws.column_dimensions[letra].width = larguras.get(col, 12)
        if col in listas:
            dv = DataValidation(type="list", formula1='"' + ",".join(listas[col]) + '"', allow_blank=True)
            dv.add(f"{letra}2:{letra}{fim}")
            ws.add_data_validation(dv)
        if col == "corr_governanca":
            dv = DataValidation(allow_blank=True, showInputMessage=True,
                                promptTitle="Governança (marcar todas)", prompt=GOVERNANCA)
            dv.add(f"{letra}2:{letra}{fim}")
            ws.add_data_validation(dv)
    for row in ws.iter_rows(min_row=1):
        for c in row:
            col = cab[c.column - 1]
            if c.row > 1:
                c.alignment = Alignment(wrap_text=True, vertical="top")
            if col in prop:
                c.fill = cinza
            elif col in corr[1:]:
                c.fill = amarelo
    ws.freeze_panes = "G2"

    ws = wb.create_sheet("codigos")
    ws.append(["dimensão", "código", "definição"])
    for c in ws[1]:
        c.font = Font(bold=True)
    for d in DEFINICOES:
        ws.append(list(d))
    ws.append([])
    ws.append(["desempate", "", ""])
    for i, r in enumerate(DESEMPATE, 1):
        ws.append(["", str(i), r])
    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 110
    wb.save(saida)
    print(f"{len(trechos)} trechos para verificação -> {saida}")


def alfa_nominal(pares):
    """Alfa de Krippendorff, dados nominais, dois codificadores sem valores faltantes."""
    from collections import Counter
    n = Counter()
    for a, b in pares:
        n[a] += 1
        n[b] += 1
    total = sum(n.values())
    if total < 2:
        return None
    observada = sum(a != b for a, b in pares) * 2 / total
    esperada = (total * total - sum(v * v for v in n.values())) / (total * (total - 1))
    return round(1 - observada / esperada, 3) if esperada else None


def f1_por_classe(pares, classes):
    linhas = []
    for c in classes:
        vp = sum(h == c and m == c for h, m in pares)
        fp = sum(h != c and m == c for h, m in pares)
        fn = sum(h == c and m != c for h, m in pares)
        p = vp / (vp + fp) if vp + fp else 0
        r = vp / (vp + fn) if vp + fn else 0
        linhas.append({"classe": c, "humano": vp + fn, "modelo": vp + fp,
                       "precisao": round(p, 2), "revocacao": round(r, 2),
                       "f1": round(2 * p * r / (p + r), 2) if p + r else 0.0})
    return linhas


def cmd_comparar(cega_xlsx, classificacoes_csv, saida):
    """Compara a anotação cega do autor com o modelo: acordo, alfa, F1 e divergências."""
    from collections import Counter
    from openpyxl import load_workbook

    ws = load_workbook(cega_xlsx, read_only=True)["cega"]
    linhas = list(ws.iter_rows(values_only=True))
    cab = linhas[0]
    humano = {r[cab.index("id_trecho")]: dict(zip(cab, r)) for r in linhas[1:] if r[cab.index("id_trecho")]}
    modelo = {r["id_trecho"]: r for r in csv.DictReader(open(classificacoes_csv, encoding="utf-8"))}
    norm = lambda v: str(v or "").strip()
    sim = lambda v: norm(v).lower() in ("sim", "true")
    gov = lambda v: frozenset(g.strip().lower() for g in re.split(r"[;,]", norm(v)) if g.strip()) or frozenset({"nenhuma"})

    ids = [i for i in humano if i in modelo]
    resumo, divergencias = [], []
    pares_fp = [(sim(humano[i]["falso_positivo"]), sim(modelo[i]["falso_positivo"])) for i in ids]
    resumo.append({"dimensao": "falso_positivo", "n": len(ids),
                   "acordo_pct": round(100 * sum(a == b for a, b in pares_fp) / len(ids), 1),
                   "alfa": alfa_nominal(pares_fp)})
    validos = [i for i in ids if not sim(humano[i]["falso_positivo"]) and not sim(modelo[i]["falso_positivo"])]
    pares = {}
    for dim in ("funcao", "evidencia", "tom", "tempo"):
        pares[dim] = [(norm(humano[i][dim]).upper(), norm(modelo[i][dim]).upper()) for i in validos]
        resumo.append({"dimensao": dim, "n": len(validos),
                       "acordo_pct": round(100 * sum(a == b for a, b in pares[dim]) / len(validos), 1),
                       "alfa": alfa_nominal(pares[dim])})
    pares_gov = [(gov(humano[i]["governanca"]), gov(modelo[i]["governanca"])) for i in validos]
    resumo.append({"dimensao": "governanca (conjunto igual)", "n": len(validos),
                   "acordo_pct": round(100 * sum(a == b for a, b in pares_gov) / len(validos), 1),
                   "alfa": alfa_nominal([("nenhuma" in a, "nenhuma" in b) for a, b in pares_gov])})
    for i in ids:
        h, m = humano[i], modelo[i]
        difs = []
        if sim(h["falso_positivo"]) != sim(m["falso_positivo"]):
            difs.append("falso_positivo")
        elif i in validos:
            difs += [d for d in ("funcao", "evidencia", "tom", "tempo") if norm(h[d]).upper() != norm(m[d]).upper()]
            if gov(h["governanca"]) != gov(m["governanca"]):
                difs.append("governanca")
        if difs:
            divergencias.append({
                "n": h["n"], "id_trecho": i, "empresa": h["empresa"], "secao": h["secao"],
                "dimensoes": "; ".join(difs),
                **{f"h_{d}": norm(h[d]) for d in ("falso_positivo", "funcao", "evidencia", "governanca", "tom", "tempo")},
                **{f"m_{d}": norm(m[d]) for d in ("falso_positivo", "funcao", "evidencia", "governanca", "tom", "tempo")},
                "h_justificativa": norm(h["justificativa"]), "m_justificativa": m["justificativa"],
                "m_duvida": m["duvida"],
            })
    saida = Path(saida)
    with open(saida / "comparacao_cega_v1.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(resumo[0]))
        w.writeheader()
        w.writerows(resumo)
    with open(saida / "comparacao_cega_v1_funcao_f1.csv", "w", newline="", encoding="utf-8") as f:
        dados = f1_por_classe(pares["funcao"], CODIGOS["funcao"])
        w = csv.DictWriter(f, fieldnames=list(dados[0]))
        w.writeheader()
        w.writerows(dados)
    if divergencias:
        with open(saida / "divergencias_cega_v1.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(divergencias[0]))
            w.writeheader()
            w.writerows(divergencias)
    for r in resumo:
        print(r)
    print("\nfuncao (humano x modelo):", Counter(pares["funcao"]).most_common())
    for r in f1_por_classe(pares["funcao"], CODIGOS["funcao"]):
        print(r)
    print(f"\n{len(divergencias)} trechos com alguma divergência -> {saida / 'divergencias_cega_v1.csv'}")


def cmd_ouro(amostra_csv, cega_xlsx, verificacao_xlsx, classificacoes_csv, saida, adjudicacoes_csv=None):
    """Padrão-ouro v1: 100 cegos (código do autor) + 708 verificados (modelo + correções do autor).

    ADJUDICACOES.csv (id_trecho, campo, valor, motivo, data) registra decisões do autor tomadas
    depois da anotação (ex.: comentários "possível falso positivo"); a origem passa a "adjudicado".

    Grava ouro_v1.csv (com a origem de cada código) e efeito_verificacao_v1.csv, que compara
    a taxa de concordância autor x modelo na cega e na verificação.
    """
    from openpyxl import load_workbook

    def ler(caminho, aba):
        linhas = list(load_workbook(caminho, read_only=True)[aba].iter_rows(values_only=True))
        return {r[linhas[0].index("id_trecho")]: dict(zip(linhas[0], r)) for r in linhas[1:]
                if r[linhas[0].index("id_trecho")]}

    norm = lambda v: str(v if v is not None else "").strip()
    sim = lambda v: norm(v).lower() in ("sim", "true")
    dims = ("funcao", "evidencia", "governanca", "tom", "tempo")
    amostra = {t["id_trecho"]: t for t in csv.DictReader(open(amostra_csv, encoding="utf-8-sig"))}
    modelo = {r["id_trecho"]: r for r in csv.DictReader(open(classificacoes_csv, encoding="utf-8"))}
    cega, verif = ler(cega_xlsx, "cega"), ler(verificacao_xlsx, "verificar")

    ouro, avisos = [], []
    mudou = {d: 0 for d in ("falso_positivo",) + dims}
    for i, t in amostra.items():
        m = modelo[i]
        linha = {k: t[k] for k in ("id_trecho", "rodada", "ano", "cd_cvm", "empresa", "macrossetor", "secao",
                                   "titulo_secao", "grupo_secao", "estrato", "peso", "ia_gen", "termos", "trecho")}
        if i in cega:
            h = cega[i]
            linha.update(origem="cega", falso_positivo="sim" if sim(h["falso_positivo"]) else "nao",
                         **{d: norm(h[d]) for d in dims}, duvida=norm(h["duvida"]),
                         comentario=norm(h["justificativa"]))
        else:
            v = verif[i]
            fp = sim(m["falso_positivo"])
            if norm(v["corr_falso_positivo"]):
                fp = sim(v["corr_falso_positivo"])
                mudou["falso_positivo"] += 1
            codigos = {}
            for d in dims:
                c = norm(v[f"corr_{d}"])
                if c:
                    mudou[d] += 1
                codigos[d] = c or ("" if sim(m["falso_positivo"]) else norm(m[d]))
            if not fp and any(not codigos[d] for d in dims):
                avisos.append(f"{i}: não é falso positivo mas falta código em "
                              + ", ".join(d for d in dims if not codigos[d]))
            if fp:
                codigos = {d: "" for d in dims}
            linha.update(origem="verificado" if any(norm(v[f"corr_{d}"]) for d in ("falso_positivo",) + dims)
                         else "verificado_sem_correcao",
                         falso_positivo="sim" if fp else "nao", **codigos,
                         duvida="sim" if sim(m["duvida"]) else "nao", comentario=norm(v["comentario"]))
        ouro.append(linha)

    if adjudicacoes_csv:
        por_id = {t["id_trecho"]: t for t in ouro}
        for a in csv.DictReader(open(adjudicacoes_csv, encoding="utf-8")):
            t = por_id[a["id_trecho"]]
            t[a["campo"]] = a["valor"]
            if a["campo"] == "falso_positivo" and a["valor"] == "sim":
                t.update({d: "" for d in dims})
            t["origem"] = "adjudicado"
            t["comentario"] = (t["comentario"] + " | adjudicado: " + a["motivo"]).strip(" |")

    saida = Path(saida)
    with open(saida / "ouro_v1.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(ouro[0]))
        w.writeheader()
        w.writerows(ouro)

    # concordância autor x modelo: cega (sem ver o modelo) x verificação (vendo o modelo)
    efeito = []
    n_ver = len(verif)
    validos_cega = [i for i in cega if not sim(cega[i]["falso_positivo"]) and not sim(modelo[i]["falso_positivo"])]
    for d in ("falso_positivo",) + dims:
        if d == "falso_positivo":
            ac = sum(sim(cega[i][d]) == sim(modelo[i][d]) for i in cega) / len(cega)
        elif d == "governanca":
            g = lambda x: frozenset(s.strip().lower() for s in re.split(r"[;,]", norm(x)) if s.strip()) or frozenset({"nenhuma"})
            ac = sum(g(cega[i][d]) == g(modelo[i][d]) for i in validos_cega) / len(validos_cega)
        else:
            ac = sum(norm(cega[i][d]).upper() == norm(modelo[i][d]).upper() for i in validos_cega) / len(validos_cega)
        efeito.append({"dimensao": d, "acordo_cega_pct": round(100 * ac, 1),
                       "mantido_verificacao_pct": round(100 * (1 - mudou[d] / n_ver), 1),
                       "correcoes_verificacao": mudou[d]})
    with open(saida / "efeito_verificacao_v1.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(efeito[0]))
        w.writeheader()
        w.writerows(efeito)
    for e in efeito:
        print(e)
    print(f"{len(ouro)} trechos no padrão-ouro -> {saida / 'ouro_v1.csv'}")
    for a in avisos:
        print("[aviso]", a)


REGRAS_V2 = {
    "falso_positivo": "regras 1-2 (nome de empresa com IA; formação de administrador)",
    ("funcao", "GENERICA"): "regras 3-4 (equipe, treinamento, cargo, lista; IA de investida/parceira)",
    ("funcao", "PROD", "USO"): "regra 5 (\"eficiente\" sozinho não é PROD)",
    ("evidencia", "METRICA"): "regras 6-7 (número que não mede a IA; prazo)",
    ("tom",): "regra 8 (descrição técnica = NEU)",
    ("tempo", "NA"): "regra 9 (menção vaga = NA)",
}


def regra_v2(dim, ouro, v2):
    if dim == "falso_positivo":
        return REGRAS_V2["falso_positivo"]
    for chave, texto in REGRAS_V2.items():
        if isinstance(chave, tuple) and chave[0] == dim and (len(chave) == 1 or set(chave[1:]) & {ouro, v2}):
            if chave[1:] == ("PROD", "USO") and {ouro, v2} != {"PROD", "USO"}:
                continue
            return texto
    return ""


def cmd_revisar_v2(ouro_csv, classificacoes_csv, saida):
    """Compara o v2 com o padrão-ouro v1 e gera a planilha de revisão das divergências."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    norm = lambda v: str(v if v is not None else "").strip()
    sim = lambda v: norm(v).lower() in ("sim", "true")
    gov = lambda v: "; ".join(sorted({g.strip().lower() for g in re.split(r"[;,]", norm(v)) if g.strip()} or {"nenhuma"}))
    ouro = list(csv.DictReader(open(ouro_csv, encoding="utf-8-sig")))
    v2 = {r["id_trecho"]: r for r in csv.DictReader(open(classificacoes_csv, encoding="utf-8"))}
    dims = ("funcao", "evidencia", "governanca", "tom", "tempo")

    divergencias, metricas = [], []
    for amostra, filtro in (("todos", None), ("cegos", "cega")):
        linhas = [t for t in ouro if filtro is None or t["origem"] == filtro]
        pares_fp = [(sim(t["falso_positivo"]), sim(v2[t["id_trecho"]]["falso_positivo"])) for t in linhas]
        metricas.append({"amostra": amostra, "dimensao": "falso_positivo", "n": len(linhas),
                         "acordo_pct": round(100 * sum(a == b for a, b in pares_fp) / len(linhas), 1),
                         "alfa": alfa_nominal(pares_fp)})
        validos = [t for t in linhas if not sim(t["falso_positivo"]) and not sim(v2[t["id_trecho"]]["falso_positivo"])]
        for d in dims:
            f = gov if d == "governanca" else (lambda v: norm(v).upper())
            pares = [(f(t[d]), f(v2[t["id_trecho"]][d])) for t in validos]
            metricas.append({"amostra": amostra, "dimensao": d, "n": len(validos),
                             "acordo_pct": round(100 * sum(a == b for a, b in pares) / len(validos), 1),
                             "alfa": alfa_nominal(pares)})

    for t in ouro:
        m = v2[t["id_trecho"]]
        if sim(t["falso_positivo"]) != sim(m["falso_positivo"]):
            difs = [("falso_positivo", t["falso_positivo"], "sim" if sim(m["falso_positivo"]) else "nao")]
        elif sim(t["falso_positivo"]):
            difs = []
        else:
            difs = []
            for d in dims:
                a, b = (gov(t[d]), gov(m[d])) if d == "governanca" else (norm(t[d]).upper(), norm(m[d]).upper())
                if a != b:
                    difs.append((d, a, b))
        for d, a, b in difs:
            divergencias.append({"id_trecho": t["id_trecho"], "origem_ouro": t["origem"], "empresa": t["empresa"],
                                 "secao": t["secao"], "trecho": t["trecho"], "termos": t["termos"],
                                 "dimensao": d, "ouro_v1": a, "modelo_v2": b, "regra_v2": regra_v2(d, a, b),
                                 "justificativa_v2": m["justificativa"]})
    divergencias.sort(key=lambda x: (x["regra_v2"] == "", x["dimensao"], x["id_trecho"]))

    saida = Path(saida)
    with open(saida / "comparacao_v2_ouro_v1.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(metricas[0]))
        w.writeheader()
        w.writerows(metricas)

    wb = Workbook()
    ws = wb.active
    ws.title = "instrucoes"
    for linha in [
        "Revisão das divergências entre o padrão-ouro v1 e o classificador v2",
        "",
        "Cada linha é uma dimensão de um trecho em que o padrão-ouro (sua anotação ou verificação, sob o guia v1) e o modelo v2 discordam.",
        "As primeiras linhas tocam as regras novas do guia v2 (coluna regra_v2): ali o padrão-ouro pode estar desatualizado.",
        "Na coluna decisao escolha: ouro (manter o código do padrão-ouro), v2 (aceitar o código do modelo) ou outro (escreva o código em codigo_outro).",
        "Use comentario para observações. Salve com o mesmo nome e avise o autor.",
    ]:
        ws.append([linha])
    ws["A1"].font = Font(bold=True, size=13)
    ws.column_dimensions["A"].width = 140

    ws = wb.create_sheet("divergencias")
    cab = ["n", "id_trecho", "empresa", "secao", "trecho", "dimensao", "ouro_v1", "modelo_v2", "regra_v2",
           "justificativa_v2", "decisao", "codigo_outro", "comentario"]
    ws.append(cab)
    for c in ws[1]:
        c.font = Font(bold=True)
    for i, d in enumerate(divergencias, 1):
        ws.append([i] + [d[c] for c in cab[1:4]] + [""] + [d[c] for c in cab[5:10]] + ["", "", ""])
        ws.cell(i + 1, 5).value = texto_destacado(d["trecho"], d["termos"])
    larguras = {"n": 5, "id_trecho": 16, "empresa": 18, "secao": 7, "trecho": 75, "dimensao": 12,
                "ouro_v1": 12, "modelo_v2": 12, "regra_v2": 26, "justificativa_v2": 40, "decisao": 10,
                "codigo_outro": 14, "comentario": 28}
    fim = len(divergencias) + 1
    amarelo = PatternFill("solid", fgColor="FFF4C2")
    for i, col in enumerate(cab, 1):
        letra = ws.cell(1, i).column_letter
        ws.column_dimensions[letra].width = larguras.get(col, 12)
    dv = DataValidation(type="list", formula1='"ouro,v2,outro"', allow_blank=True)
    dv.add(f"K2:K{fim}")
    ws.add_data_validation(dv)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
            if cab[c.column - 1] in ("decisao", "codigo_outro", "comentario"):
                c.fill = amarelo
    ws.freeze_panes = "F2"
    wb.save(saida / "revisao_v2.xlsx")

    for m in metricas:
        print(m)
    from collections import Counter
    print(f"\n{len(divergencias)} divergências ({len({d['id_trecho'] for d in divergencias})} trechos); "
          f"ligadas às regras novas: {sum(1 for d in divergencias if d['regra_v2'])}")
    print(Counter((d["dimensao"], d["ouro_v1"], d["modelo_v2"]) for d in divergencias).most_common(15))
    print(f"-> {saida / 'revisao_v2.xlsx'}")


if __name__ == "__main__":
    {"populacao": cmd_populacao, "revisar_v2": cmd_revisar_v2, "ouro": cmd_ouro, "cega": cmd_cega, "lotes": cmd_lotes, "juntar": cmd_juntar, "planilha": cmd_planilha,
     "comparar": cmd_comparar}[sys.argv[1]](*sys.argv[2:])
