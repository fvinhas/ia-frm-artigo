"""Etapa 8d — análises complementares de robustez (30/10/2026).

Uso:
    python complementares.py PASTA_DADOS PASTA_ANTES SAIDA_DIR

PASTA_DADOS  a pasta dados/ (populacao_v1.csv e classificacoes_llm_v3.csv em anotacao/, índices fre_AAAA/)
PASTA_ANTES  saídas guardadas antes da revisão do dicionário (dados/antes_chatbot/)

Grava em SAIDA_DIR:
  sensibilidade_dicionario.csv  % das companhias (que citam IA, risco, uso) com o dicionário atual e o anterior
  funcao_por_companhia.csv      distribuição da função com peso igual por companhia (cada companhia soma 1)
  governanca_denominadores.csv  governança declarada sobre todas as companhias, sobre as que citam IA e sobre
                                as que tratam a IA como risco
  marcadores_textuais.csv       % dos trechos com verbo modal ("pode", "poderá"...) e com ano explícito
                                (20xx), por função e ano: indicadores contados direto no texto, independentes
                                das regras do guia sobre tom e tempo
  versoes_fre.csv               versão usada (a mais recente) × primeira versão: % reapresentados e data
"""
import csv
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ANOS = ["2023", "2024", "2025", "2026"]
FUNCOES = ("RISCO", "USO", "PROD", "NEGOCIO", "GENERICA", "GOV")
RE_MODAL = re.compile(r"\b(pode|podem|poder[áã]o?|poderia[m]?|possa[m]?|eventua(?:l|is|lmente))\b", re.I)
RE_ANO = re.compile(r"\b20[0-3]\d\b")
fp = lambda v: str(v).strip().lower() in ("sim", "true")
gov = lambda v: v.strip() != "" and "nenhuma" not in v.lower()


def gravar(caminho, linhas):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    print("->", caminho)


def main(pasta, antes, saida):
    pasta, antes, saida = Path(pasta), Path(antes), Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    an = pasta / "anotacao"
    modelo = {r["id_trecho"]: r for r in csv.DictReader(open(an / "classificacoes_llm_v3.csv", encoding="utf-8"))}
    ok = [dict(t, **modelo[t["id_trecho"]]) for t in csv.DictReader(open(an / "populacao_v1.csv", encoding="utf-8-sig"))
          if not fp(modelo[t["id_trecho"]]["falso_positivo"])]
    entregaram = {a: sum(1 for _ in csv.DictReader(open(pasta / f"resumo_{a}.csv", encoding="utf-8"))) for a in ANOS}

    # 1. dicionário atual × anterior (unidade companhia)
    atual = {(r["universo"], r["ano"]): r for r in csv.DictReader(open(an / "pop_v3_ano_empresas.csv", encoding="utf-8"))}
    ant = {(r["universo"], r["ano"]): r for r in csv.DictReader(open(antes / "pop_v3_ano_empresas.csv", encoding="utf-8"))}
    gravar(saida / "sensibilidade_dicionario.csv",
           [{"ano": a, **{f"{k}_{v}": d[("todas", a)][c] for v, d in (("atual", atual), ("anterior", ant))
                         for k, c in (("citam_ia_pct", "citam_ia_pct"), ("risco_pct", "RISCO_pct_fre"), ("uso_pct", "USO_pct_fre"))}}
            for a in ANOS])

    # 2. função com peso igual por companhia
    linhas = []
    for a in ANOS:
        por_cia = defaultdict(list)
        for t in ok:
            if t["ano"] == a:
                por_cia[t["cd_cvm"]].append(t["funcao"])
        acc = Counter()
        for fs in por_cia.values():
            for f in fs:
                acc[f] += 1 / len(fs)
        linhas.append({"ano": a, "companhias": len(por_cia), **{f: round(100 * acc[f] / len(por_cia), 1) for f in FUNCOES}})
    gravar(saida / "funcao_por_companhia.csv", linhas)

    # 3. governança: denominadores
    linhas = []
    for a in ANOS:
        cias = defaultdict(list)
        for t in ok:
            if t["ano"] == a:
                cias[t["cd_cvm"]].append(t)
        g = {c for c, ts in cias.items() if any(gov(t["governanca"]) for t in ts)}
        r = {c for c, ts in cias.items() if any(t["funcao"] == "RISCO" for t in ts)}
        linhas.append({"ano": a, "entregaram": entregaram[a], "citam_ia": len(cias), "com_governanca": len(g),
                       "gov_pct_entregaram": round(100 * len(g) / entregaram[a], 1),
                       "gov_pct_citam_ia": round(100 * len(g) / len(cias), 1),
                       "tratam_risco": len(r), "risco_e_governanca": len(r & g),
                       "gov_pct_tratam_risco": round(100 * len(r & g) / len(r), 1) if r else ""})
    gravar(saida / "governanca_denominadores.csv", linhas)

    # 4. marcadores contados no texto
    linhas = []
    for a in ANOS + ["todos"]:
        for f in FUNCOES + ("TODAS",):
            ts = [t for t in ok if (a == "todos" or t["ano"] == a) and (f == "TODAS" or t["funcao"] == f)]
            if ts:
                linhas.append({"ano": a, "funcao": f, "trechos": len(ts),
                               "modal_pct": round(100 * sum(bool(RE_MODAL.search(t["trecho"])) for t in ts) / len(ts), 1),
                               "ano_explicito_pct": round(100 * sum(bool(RE_ANO.search(t["trecho"])) for t in ts) / len(ts), 1)})
    gravar(saida / "marcadores_textuais.csv", linhas)

    # 5. versões do FRE: a usada (mais recente) × a primeira
    linhas = []
    for a in ANOS:
        por_cnpj = defaultdict(list)
        with open(pasta / f"fre_{a}" / f"fre_cia_aberta_{a}.csv", encoding="latin1") as f:
            for r in csv.DictReader(f, delimiter=";"):
                por_cnpj[r["CNPJ_CIA"]].append(r)
        reap, dias, depois = 0, [], 0
        for rs in por_cnpj.values():
            rs.sort(key=lambda r: int(r["VERSAO"] or 0))
            prim, ult = rs[0], rs[-1]
            if len(rs) > 1:
                reap += 1
                d = (date.fromisoformat(ult["DT_RECEB"]) - date.fromisoformat(prim["DT_RECEB"])).days
                dias.append(d)
                if d > 90:
                    depois += 1
        dias.sort()
        linhas.append({"ano": a, "companhias": len(por_cnpj), "com_reapresentacao": reap,
                       "reapresentacao_pct": round(100 * reap / len(por_cnpj), 1),
                       "mediana_dias_primeira_ultima": dias[len(dias) // 2] if dias else 0,
                       "ultima_mais_de_90_dias_depois": depois})
    gravar(saida / "versoes_fre.csv", linhas)


if __name__ == "__main__":
    main(*sys.argv[1:4])
