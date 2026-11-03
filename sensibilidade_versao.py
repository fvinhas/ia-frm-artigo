"""Etapa 8e — sensibilidade à versão do FRE (pedido da segunda rodada da revisão).

A análise usa a versão mais recente de cada formulário, que costuma ser reapresentada meses depois da
primeira entrega (no FRE de 2023, a versão mais recente chegou, na mediana, em maio de 2024). Aqui o corpus
de 2023 e 2026 é refeito com a PRIMEIRA versão de cada companhia, e os indicadores principais são comparados.

Uso:
    python sensibilidade_versao.py montar     PASTA_DADOS ANO...
    python sensibilidade_versao.py lotes      PASTA_DADOS PASTA_LOTES ANO...
    python sensibilidade_versao.py comparar   PASTA_DADOS PASTA_LOTES SAIDA.csv ANO...

montar    junta as seções das primeiras versões (dados/secoes_AAAA_primeira.jsonl, extraídas de
          zips_AAAA_primeira/ pelas companhias que reapresentaram) às seções das companhias com versão única
          (iguais nas duas análises) em dados/primeira/secoes_AAAA.jsonl. Depois rode detectar_mencoes.py
          sobre esse arquivo, gravando em dados/primeira/.
lotes     monta a população de trechos da primeira versão (mesma unidade e mesmos ids da análise principal:
          o id depende do texto) e grava em lotes de 50, com o formato de entrada do v3, só os trechos que
          ainda não têm classificação. Cada lote é classificado por um agente isolado com classificador_v3.md.
comparar  junta as classificações (v3 + lotes novos) e compara, por ano: % das companhias que citam IA, que
          tratam a IA como risco e que relatam uso, e a % dos trechos de risco.
"""
import csv
import glob
import json
import sys
from collections import defaultdict
from pathlib import Path

from amostrar_anotacao import carregar_populacao
from setores import carregar_cadastro

TAMANHO_LOTE = 50
fp = lambda v: str(v).strip().lower() in ("sim", "true")


def reapresentadas(pasta, ano):
    por = defaultdict(set)
    with open(Path(pasta) / f"fre_{ano}" / f"fre_cia_aberta_{ano}.csv", encoding="latin1") as f:
        for r in csv.DictReader(f, delimiter=";"):
            por[r["CD_CVM"].zfill(6)].add(r["VERSAO"])
    return {cd for cd, vs in por.items() if len(vs) > 1}


def cmd_montar(pasta, *anos):
    pasta = Path(pasta)
    (pasta / "primeira").mkdir(exist_ok=True)
    for ano in anos:
        reap = reapresentadas(pasta, ano)
        n_prim = n_unica = 0
        with open(pasta / "primeira" / f"secoes_{ano}.jsonl", "w", encoding="utf-8") as out:
            for linha in open(pasta / f"secoes_{ano}_primeira.jsonl", encoding="utf-8"):
                out.write(linha)
                n_prim += 1
            for linha in open(pasta / f"secoes_{ano}.jsonl", encoding="utf-8"):
                # o código do índice está no nome do arquivo; o do XML às vezes difere (ex.: 027235 × 094757)
                if json.loads(linha)["arquivo"].split("_")[0].zfill(6) not in reap:
                    out.write(linha)
                    n_unica += 1
        print(f"{ano}: {n_prim} páginas de primeiras versões + {n_unica} de companhias com versão única")


def classificacoes(pasta, pasta_lotes):
    modelo = {r["id_trecho"]: r for r in csv.DictReader(open(Path(pasta) / "anotacao" / "classificacoes_llm_v3.csv", encoding="utf-8"))}
    for arq in sorted(glob.glob(str(Path(pasta_lotes) / "saida_*.jsonl"))):
        for linha in open(arq, encoding="utf-8"):
            if linha.strip().startswith("{"):
                r = json.loads(linha)
                modelo.setdefault(r["id_trecho"], r)
    return modelo


def cmd_lotes(pasta, pasta_lotes, *anos):
    pasta = Path(pasta)
    pop = carregar_populacao(pasta / "primeira", anos, carregar_cadastro(pasta / "cad_cia_aberta.csv"))
    modelo = classificacoes(pasta, pasta_lotes)
    novos = [t for t in sorted(pop, key=lambda t: t["id_trecho"]) if t["id_trecho"] not in modelo]
    Path(pasta_lotes).mkdir(parents=True, exist_ok=True)
    for i in range(0, len(novos), TAMANHO_LOTE):
        with open(Path(pasta_lotes) / f"entrada_{i // TAMANHO_LOTE + 1:02d}.jsonl", "w", encoding="utf-8") as f:
            for t in novos[i:i + TAMANHO_LOTE]:
                f.write(json.dumps({"id_trecho": t["id_trecho"], "empresa": t["empresa"], "secao": t["secao"],
                                    "titulo_secao": t["titulo_secao"], "termos": "; ".join(dict.fromkeys(t["termos"])),
                                    "trecho": t["trecho"]}, ensure_ascii=False) + "\n")
    print(f"população da primeira versão: {len(pop)} trechos; já classificados {len(pop) - len(novos)}; "
          f"novos {len(novos)} em {-(-len(novos) // TAMANHO_LOTE)} lotes -> {pasta_lotes}")


def indicadores(pop, modelo, ano, entregaram):
    ts = [t for t in pop if t["ano"] == ano and t["id_trecho"] in modelo and not fp(modelo[t["id_trecho"]]["falso_positivo"])]
    f = lambda t: str(modelo[t["id_trecho"]]["funcao"]).upper()
    cias = lambda filtro: len({t["cd_cvm"] for t in ts if filtro(t)})
    return {"trechos_validos": len(ts),
            "cita_ia_pct": round(100 * cias(lambda t: True) / entregaram, 1),
            "risco_pct_cias": round(100 * cias(lambda t: f(t) == "RISCO") / entregaram, 1),
            "uso_pct_cias": round(100 * cias(lambda t: f(t) == "USO") / entregaram, 1),
            "risco_pct_trechos": round(100 * sum(f(t) == "RISCO" for t in ts) / len(ts), 1),
            "uso_pct_trechos": round(100 * sum(f(t) == "USO" for t in ts) / len(ts), 1),
            "sem_classificacao": sum(1 for t in pop if t["ano"] == ano and t["id_trecho"] not in modelo)}


def cmd_comparar(pasta, pasta_lotes, saida, *anos):
    pasta = Path(pasta)
    cad = carregar_cadastro(pasta / "cad_cia_aberta.csv")
    modelo = classificacoes(pasta, pasta_lotes)
    ultima = list(csv.DictReader(open(pasta / "anotacao" / "populacao_v1.csv", encoding="utf-8-sig")))
    primeira = carregar_populacao(pasta / "primeira", anos, cad)
    linhas = []
    for ano in anos:
        n = sum(1 for _ in csv.DictReader(open(pasta / f"resumo_{ano}.csv", encoding="utf-8")))
        for versao, pop in (("mais_recente", ultima), ("primeira", primeira)):
            linhas.append({"ano": ano, "versao": versao, "companhias_fre": n, **indicadores(pop, modelo, ano, n)})
            print(linhas[-1])
    with open(saida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    # lista dos trechos da população da primeira versão: com classificacoes_llm_v3.csv e as saídas de
    # llm_v3_primeira/, permite refazer a comparação a partir dos dados públicos (pedido da revisão)
    ids = Path(saida).with_name("populacao_primeira_versao_ids.csv")
    with open(ids, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id_trecho", "ano", "cd_cvm", "secao"])
        for t in sorted(primeira, key=lambda t: t["id_trecho"]):
            w.writerow([t["id_trecho"], t["ano"], t["cd_cvm"], t["secao"]])
    print("->", ids)


if __name__ == "__main__":
    {"montar": cmd_montar, "lotes": cmd_lotes, "comparar": cmd_comparar}[sys.argv[1]](*sys.argv[2:])
