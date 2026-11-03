"""Etapa 8 — validação do classificador v3 e tabelas da população classificada.

Uso:
    python analise_v3.py POPULACAO.csv CLASSIFICACOES_V3.csv OURO.csv SAIDA_DIR [PASTA_DADOS]

Com PASTA_DADOS (onde estão os resumo_AAAA.csv), grava também pop_v3_ano_empresas.csv: por ano,
quantas companhias têm ao menos um trecho de cada função, sobre todas as que entregaram FRE e
sobre as que citam IA (todas e painel balanceado).

Os trechos em formato antigo (só 13, de 5 companhias em 2023, todos no grupo 828 = seção 7
"Atividades do emissor" da numeração antiga) entram no grupo "1 atividades" (MAPA_ANTIGO).

Grava em SAIDA_DIR:
  validacao_v3.csv          concordância v3 x padrão-ouro (todos e só os 100 cegos), α e acordo
  validacao_v3_funcao_f1.csv  F1 por função, nos cegos
  pop_v3_ano.csv            distribuição de função, evidência, tom e tempo por ano (sem falsos positivos)
  pop_v3_ano_secao.csv      função por ano e grupo de seção
  pop_v3_setor.csv          função e evidência por macrossetor (2023 e 2026 e total)
  indices_empresa_ano_v3.csv  índices por empresa-ano (trechos, % PROD, % com evidência, governança)
"""
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from amostrar_anotacao import CODIGOS
from verificacao import alfa_nominal, f1_por_classe

DIMS = ("funcao", "evidencia", "tom", "tempo")
# grupo da numeração antiga -> grupo de seção atual (seção 7 antiga = seção 1 atual, atividades)
MAPA_ANTIGO = {"antigo:G828.": "1 atividades"}
norm = lambda v: str(v if v is not None else "").strip()
sim = lambda v: norm(v).lower() in ("sim", "true")
gov = lambda v: frozenset(g.strip().lower() for g in re.split(r"[;,]", norm(v)) if g.strip()) or frozenset({"nenhuma"})


def pct(c, total):
    return {k: round(100 * v / total, 1) for k, v in c.items()} if total else {}


def gravar(caminho, linhas):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        campos = list(dict.fromkeys(k for l in linhas for k in l))
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)


def validar(ouro, modelo, saida):
    linhas, f1 = [], []
    for amostra, filtro in (("todos", None), ("cegos", "cega")):
        ts = [t for t in ouro if t["id_trecho"] in modelo and (filtro is None or t["origem"] == filtro)]
        pares = [(sim(t["falso_positivo"]), sim(modelo[t["id_trecho"]]["falso_positivo"])) for t in ts]
        linhas.append({"amostra": amostra, "dimensao": "falso_positivo", "n": len(ts),
                       "acordo_pct": round(100 * sum(a == b for a, b in pares) / len(ts), 1),
                       "alfa": alfa_nominal(pares)})
        validos = [t for t in ts if not sim(t["falso_positivo"]) and not sim(modelo[t["id_trecho"]]["falso_positivo"])]
        for d in DIMS + ("governanca",):
            if d == "governanca":
                pares = [(gov(t[d]), gov(modelo[t["id_trecho"]][d])) for t in validos]
            else:
                pares = [(norm(t[d]).upper(), norm(modelo[t["id_trecho"]][d]).upper()) for t in validos]
            linhas.append({"amostra": amostra, "dimensao": d, "n": len(validos),
                           "acordo_pct": round(100 * sum(a == b for a, b in pares) / len(validos), 1),
                           "alfa": alfa_nominal(pares)})
            if d == "funcao" and amostra == "cegos":
                f1 = f1_por_classe(pares, CODIGOS["funcao"])
    gravar(saida / "validacao_v3.csv", linhas)
    gravar(saida / "validacao_v3_funcao_f1.csv", f1)
    return linhas, f1


def por_empresas(ok, pasta_dados, anos, saida):
    entregaram = {a: {r["cd_cvm"].lstrip("0") for r in csv.DictReader(open(Path(pasta_dados) / f"resumo_{a}.csv", encoding="utf-8"))}
                  for a in anos}
    painel = set.intersection(*entregaram.values())
    linhas = []
    for universo in ("todas", "painel"):
        for a in anos:
            base = entregaram[a] if universo == "todas" else painel
            ts = [t for t in ok if t["ano"] == a and t["cd_cvm"].lstrip("0") in base]
            citam = {t["cd_cvm"] for t in ts}
            linha = {"universo": universo, "ano": a, "empresas_fre": len(base), "citam_ia": len(citam),
                     "citam_ia_pct": round(100 * len(citam) / len(base), 1)}
            com = lambda f: {t["cd_cvm"] for t in ts if f(t)}
            grupos = {**{k: com(lambda t, k=k: norm(t["funcao"]).upper() == k) for k in CODIGOS["funcao"]},
                      "PROD_SEM_EVIDENCIA": com(lambda t: norm(t["funcao"]).upper() == "PROD" and norm(t["evidencia"]).upper() == "SEM"),
                      "GOVERNANCA_DECLARADA": com(lambda t: "nenhuma" not in gov(t["governanca"]))}
            for k, cds in grupos.items():
                linha[f"{k}_n"] = len(cds)
                linha[f"{k}_pct_fre"] = round(100 * len(cds) / len(base), 1)
                linha[f"{k}_pct_citam"] = round(100 * len(cds) / len(citam), 1) if citam else 0
            linhas.append(linha)
    gravar(saida / "pop_v3_ano_empresas.csv", linhas)
    return linhas


def main(populacao_csv, classificacoes_csv, ouro_csv, saida, pasta_dados=None):
    saida = Path(saida)
    pop = list(csv.DictReader(open(populacao_csv, encoding="utf-8-sig")))
    for t in pop:
        for prefixo, grupo in MAPA_ANTIGO.items():
            if t["secao"].startswith(prefixo):
                t["grupo_secao"] = grupo
    modelo = {r["id_trecho"]: r for r in csv.DictReader(open(classificacoes_csv, encoding="utf-8"))}
    # o padrão-ouro vale só dentro da população atual (trechos que o dicionário deixou de detectar saem)
    ids_pop = {t["id_trecho"] for t in pop}
    ouro = [o for o in csv.DictReader(open(ouro_csv, encoding="utf-8-sig")) if o["id_trecho"] in ids_pop]
    val, f1 = validar(ouro, modelo, saida)

    trechos = [{**t, **{k: modelo[t["id_trecho"]][k] for k in ("falso_positivo",) + DIMS + ("governanca",)}}
               for t in pop if t["id_trecho"] in modelo]
    falsos = sum(sim(t["falso_positivo"]) for t in trechos)
    ok = [t for t in trechos if not sim(t["falso_positivo"])]
    anos = sorted({t["ano"] for t in ok})

    por_ano = []
    for a in anos + ["total"]:
        ts = [t for t in ok if a == "total" or t["ano"] == a]
        linha = {"ano": a, "trechos": len(ts),
                 "empresas": len({t["cd_cvm"] for t in ts})}
        for d in DIMS:
            for k, v in pct(Counter(norm(t[d]).upper() for t in ts), len(ts)).items():
                linha[f"{d}_{k}"] = v
        prod = [t for t in ts if norm(t["funcao"]).upper() == "PROD"]
        linha["prod_sem_evidencia_pct"] = round(100 * sum(norm(t["evidencia"]).upper() == "SEM" for t in prod) / len(prod), 1) if prod else 0
        linha["prod_com_metrica_pct"] = round(100 * sum(norm(t["evidencia"]).upper() == "METRICA" for t in prod) / len(prod), 1) if prod else 0
        linha["com_governanca_pct"] = round(100 * sum("nenhuma" not in gov(t["governanca"]) for t in ts) / len(ts), 1)
        por_ano.append(linha)
    gravar(saida / "pop_v3_ano.csv", por_ano)

    ano_secao = []
    for a in anos:
        for g in sorted({t["grupo_secao"] for t in ok}):
            ts = [t for t in ok if t["ano"] == a and t["grupo_secao"] == g]
            if ts:
                ano_secao.append({"ano": a, "grupo_secao": g, "trechos": len(ts),
                                  **{f"funcao_{k}": v for k, v in pct(Counter(norm(t["funcao"]).upper() for t in ts), len(ts)).items()}})
    gravar(saida / "pop_v3_ano_secao.csv", ano_secao)

    setor = []
    for m in sorted({t["macrossetor"] for t in ok}):
        for a in (anos[0], anos[-1], "total"):
            ts = [t for t in ok if t["macrossetor"] == m and (a == "total" or t["ano"] == a)]
            if ts:
                setor.append({"macrossetor": m, "ano": a, "trechos": len(ts),
                              **{f"funcao_{k}": v for k, v in pct(Counter(norm(t["funcao"]).upper() for t in ts), len(ts)).items()},
                              "com_evidencia_pct": round(100 * sum(norm(t["evidencia"]).upper() != "SEM" for t in ts) / len(ts), 1)})
    gravar(saida / "pop_v3_setor.csv", setor)

    empresas = defaultdict(list)
    for t in ok:
        empresas[(t["cd_cvm"], t["empresa"], t["macrossetor"], t["ano"])].append(t)
    indices = []
    for (cd, emp, macro, a), ts in sorted(empresas.items()):
        prod = [t for t in ts if norm(t["funcao"]).upper() == "PROD"]
        govs = set().union(*(gov(t["governanca"]) for t in ts)) - {"nenhuma"}
        indices.append({"cd_cvm": cd, "empresa": emp, "macrossetor": macro, "ano": a, "trechos_ia": len(ts),
                        **{f"n_{k}": sum(norm(t["funcao"]).upper() == k for t in ts) for k in CODIGOS["funcao"]},
                        "prod_com_evidencia": sum(norm(t["evidencia"]).upper() != "SEM" for t in prod),
                        "evidencia_produtividade": round(sum(norm(t["evidencia"]).upper() != "SEM" for t in prod) / len(prod), 3) if prod else "",
                        "governanca_elementos": len(govs), "governanca": "; ".join(sorted(govs))})
    gravar(saida / "indices_empresa_ano_v3.csv", indices)

    print("validação (v3 x padrão-ouro):")
    for v in val:
        print("  ", v)
    print("F1 função (cegos):", [(x["classe"], x["f1"]) for x in f1])
    print(f"\npopulação: {len(trechos)} trechos classificados; falsos positivos {falsos} ({round(100 * falsos / len(trechos), 1)}%)")
    for l in por_ano:
        print("  ", l["ano"], l["trechos"], {k: v for k, v in l.items() if k.startswith(("funcao_", "prod_", "com_"))})
    print(f"\n{len(indices)} empresas-ano -> {saida / 'indices_empresa_ano_v3.csv'}")
    if pasta_dados:
        print("\ncompanhias (% das que entregaram FRE):")
        for l in por_empresas(ok, pasta_dados, anos, saida):
            print("  ", l["universo"], l["ano"], l["empresas_fre"], l["citam_ia_pct"],
                  {k[:-8]: v for k, v in l.items() if k.endswith("_pct_fre")})


if __name__ == "__main__":
    main(*sys.argv[1:6])
