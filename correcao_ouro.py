"""Etapa 8b — corrige as proporções da população classificada pelo LLM usando o padrão-ouro.

Uso:
    python correcao_ouro.py POPULACAO.csv CLASSIFICACOES_V3.csv OURO.csv SAIDA.csv [REPETICOES] [PASTA_DUPLA]

Por que: rótulos de LLM com 85–90% de acerto podem enviesar proporções agregadas, e uma amostra-ouro
sorteada com probabilidades conhecidas corrige esse viés (Egami et al., 2023, "design-based supervised
learning"). Estimador de diferença, ano a ano:

    total_k = soma, na população, do rótulo do modelo para k
            + soma, no ouro, de (rótulo humano − rótulo do modelo) × peso amostral

O peso é o da amostra estratificada (trechos no estrato / sorteados). As proporções são razões de
totais (ex.: risco / trechos válidos; produtividade sem evidência / produtividade). Intervalos de 95%
por bootstrap estratificado do ouro (a população classificada é um censo; a incerteza vem do ouro).

Duas versões:
  ouro   todo o padrão-ouro (cegos + verificados + adjudicados). Os verificados carregam a ancoragem
         do autor no modelo, então a correção tende a ser menor do que deveria.
  cegos  só os 100 trechos anotados às cegas, com peso = peso amostral × (ouro do ano / cegos do
         ano). Sem ancoragem, mas com intervalos bem mais largos.

Terceira versão, se PASTA_DUPLA (dados/anotacao/dupla_v2) for dada:
  dupla  o consenso da anotação dupla às cegas v2 (dois anotadores, sem ver o modelo; adjudicação pelo
         autor). Os 200 trechos foram sorteados fora do ouro, por classe prevista pelo v3; o peso é
         recalculado na população atual (elegíveis do estrato / sorteados que continuam nela). Os trechos
         do ouro entram com o rótulo humano e peso 1 (são conhecidos), o resto da população é corrigido
         pelo consenso. Seções 7, 8 e 13 e os 100 da consistência dos tipos de risco ficam com o modelo.

Os trechos do ouro que o dicionário deixou de detectar (7 "Fluxx.IA"; chatbot, assistente virtual e
modelo preditivo sem nomear IA, desde 30/10/2026) não estão na população e ficam de fora.
"""
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

SEMENTE = 20261031
ANOS = ["2023", "2024", "2025", "2026"]
norm = lambda v: str(v or "").strip().upper()
fp = lambda v: str(v).strip().lower() in ("sim", "true")


def indicadores(r):
    """Rótulos de um trecho -> dicionário de indicadores 0/1 (válido, função, evidência, tom, tempo)."""
    if fp(r["falso_positivo"]):
        return {"valido": 0}
    f, e = norm(r["funcao"]), norm(r["evidencia"])
    d = {"valido": 1, f"funcao_{f}": 1, f"evidencia_{e}": 1, f"tom_{norm(r['tom'])}": 1,
         f"tempo_{norm(r['tempo'])}": 1}
    if f == "PROD":
        d["prod_SEM"] = int(e == "SEM")
    return d


# (nome da medida, numerador, denominador)
MEDIDAS = ([(f"funcao_{k}", f"funcao_{k}", "valido") for k in ("RISCO", "USO", "PROD", "NEGOCIO", "GENERICA", "GOV")]
           + [(f"evidencia_{k}", f"evidencia_{k}", "valido") for k in ("METRICA", "CASO", "SEM")]
           + [(f"tom_{k}", f"tom_{k}", "valido") for k in ("POS", "NEU", "NEG")]
           + [(f"tempo_{k}", f"tempo_{k}", "valido") for k in ("REALIZADO", "EM_CURSO", "PLANEJADO", "NA")]
           + [("prod_sem_evidencia", "prod_SEM", "funcao_PROD"), ("falso_positivo", "fp", "todos")])


def totais(base, ouro):
    """base: totais do modelo na população; ouro: lista de (peso, ind_humano, ind_modelo)."""
    t = defaultdict(float, base)
    for peso, h, m in ouro:
        for k in set(h) | set(m):
            t[k] += peso * (h.get(k, 0) - m.get(k, 0))
        t["fp"] += peso * ((1 - h.get("valido", 0)) - (1 - m.get("valido", 0)))
    return t


def proporcoes(t):
    # o estimador de diferença pode sair de [0, 100] em estratos com poucos casos humanos; trunca (declarado no texto)
    return {nome: min(100.0, max(0.0, 100 * t[num] / t[den])) if t[den] else float("nan") for nome, num, den in MEDIDAS}


def bootstrap(base, por_estrato, rng, repeticoes):
    amostras = []
    for _ in range(repeticoes):
        ouro = [x for linhas in por_estrato.values() for x in rng.choices(linhas, k=len(linhas))]
        amostras.append(proporcoes(totais(base, ouro)))
    ic = {}
    for nome, _, _ in MEDIDAS:
        v = sorted(a[nome] for a in amostras)
        ic[nome] = (v[int(0.025 * len(v))], v[int(0.975 * len(v)) - 1])
    return ic


def amostra_dupla(pasta, pop, modelo, ouro):
    """Consenso v2 com peso recalculado na população atual -> {ano: {estrato: [(peso, h, m)]}}."""
    pasta = Path(pasta)
    an = pasta.parent
    sorteio = list(csv.DictReader(open(pasta / "cega_v2_ids.csv", encoding="utf-8")))
    consenso = {r["id_trecho"]: r for r in csv.DictReader(open(pasta / "consenso_v2.csv", encoding="utf-8"))}
    fora = {r["id_trecho"] for r in csv.DictReader(open(an / "amostra_v1.csv", encoding="utf-8-sig"))}
    fora |= {json.loads(l)["id_trecho"] for l in open(an / "llm_risco" / "consistencia_entrada.jsonl", encoding="utf-8") if l.strip()}
    classe = lambda i: "FALSO_POSITIVO" if fp(modelo[i]["falso_positivo"]) else norm(modelo[i]["funcao"])
    elegiveis = Counter(classe(t["id_trecho"]) for t in pop
                        if t["id_trecho"] not in fora and not t["secao"].startswith(("7.", "8.", "13.")))
    ids = {t["id_trecho"]: t for t in pop}
    ficam = [r for r in sorteio if r["id_trecho"] in ids and r["id_trecho"] in consenso]
    sorteados = Counter(r["estrato"] for r in ficam)
    saida = defaultdict(lambda: defaultdict(list))
    for r in ficam:
        i = r["id_trecho"]
        saida[r["ano"]][r["estrato"]].append((elegiveis[r["estrato"]] / sorteados[r["estrato"]],
                                              indicadores(consenso[i]), indicadores(modelo[i])))
    fixos = defaultdict(list)
    for o in ouro:
        fixos[o["ano"]].append((1.0, indicadores(o), indicadores(modelo[o["id_trecho"]])))
    return saida, fixos, len(ficam)


def main(populacao_csv, classif_csv, ouro_csv, saida, repeticoes=2000, pasta_dupla=None):
    repeticoes = int(repeticoes)
    rng = random.Random(SEMENTE)
    modelo = {r["id_trecho"]: r for r in csv.DictReader(open(classif_csv, encoding="utf-8"))}
    pop = [t for t in csv.DictReader(open(populacao_csv, encoding="utf-8-sig")) if t["id_trecho"] in modelo]
    ids = {t["id_trecho"] for t in pop}
    ouro = [o for o in csv.DictReader(open(ouro_csv, encoding="utf-8-sig")) if o["id_trecho"] in ids]
    if pasta_dupla:
        dupla, fixos, n_dupla = amostra_dupla(pasta_dupla, pop, modelo, ouro)
        print(f"dupla: {n_dupla} trechos do consenso na população atual; {len(ouro)} do ouro com rótulo humano")

    linhas = []
    for a in ANOS:
        base = defaultdict(float)
        for t in pop:
            if t["ano"] == a:
                m = indicadores(modelo[t["id_trecho"]])
                for k, v in m.items():
                    base[k] += v
                base["fp"] += 1 - m["valido"]
                base["todos"] += 1
        ingenuo = proporcoes(base)
        ouro_ano = [o for o in ouro if o["ano"] == a]
        n_cegos = sum(o["origem"] == "cega" for o in ouro_ano)
        versoes = {}
        for versao, filtro, fator in (("ouro", lambda o: True, 1.0),
                                      ("cegos", lambda o: o["origem"] == "cega", len(ouro_ano) / n_cegos)):
            por_estrato = defaultdict(list)
            for o in ouro_ano:
                if filtro(o):
                    # cegos: poucos por estrato, então o bootstrap reamostra no ano inteiro
                    por_estrato[o["estrato"] if versao == "ouro" else a].append(
                        (float(o["peso"]) * fator, indicadores(o), indicadores(modelo[o["id_trecho"]])))
            amostra = [x for v in por_estrato.values() for x in v]
            versoes[versao] = (proporcoes(totais(base, amostra)), bootstrap(base, por_estrato, rng, repeticoes))
        if pasta_dupla:
            # o ouro é somado à base (conhecido, sem reamostrar). O bootstrap reamostra o consenso do ano inteiro:
            # por estrato, estratos sem nenhuma divergência davam intervalos de amplitude zero
            base_d = totais(base, fixos[a])
            por_estrato = {a: [x for v in dupla[a].values() for x in v]}
            amostra = [x for v in por_estrato.values() for x in v]
            versoes["dupla"] = (proporcoes(totais(base_d, amostra)), bootstrap(base_d, por_estrato, rng, repeticoes))
        for nome, _, _ in MEDIDAS:
            linha = {"ano": a, "medida": nome, "modelo_pct": round(ingenuo[nome], 1)}
            for versao, (est, ic) in versoes.items():
                linha[f"{versao}_pct"] = round(est[nome], 1)
                linha[f"{versao}_ic95"] = f"{ic[nome][0]:.1f}–{ic[nome][1]:.1f}"
            linhas.append(linha)

    with open(saida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    principais = ("funcao_RISCO", "funcao_USO", "funcao_PROD", "funcao_NEGOCIO", "funcao_GENERICA", "funcao_GOV",
                  "evidencia_SEM", "tom_NEG", "tempo_NA", "tempo_PLANEJADO", "prod_sem_evidencia", "falso_positivo")
    extra = ("dupla",) if pasta_dupla else ()
    print(f"{'medida':22} {'ano':5} {'modelo':>7}" + "".join(f" {v:>7} {'IC95':>12}" for v in ("ouro", "cegos") + extra))
    for l in linhas:
        if l["medida"] in principais and l["ano"] in ("2023", "2026"):
            print(f"{l['medida']:22} {l['ano']:5} {l['modelo_pct']:7}" +
                  "".join(f" {l[v + '_pct']:7} {l[v + '_ic95']:>12}" for v in ("ouro", "cegos") + extra))


if __name__ == "__main__":
    main(*sys.argv[1:7])
