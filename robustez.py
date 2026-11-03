"""Etapa 8c — testes de robustez pedidos pela revisão do rascunho da H2D.

Uso:
    python robustez.py lotes      POPULACAO.csv CLASSIF_V3.csv PASTA_LOTES
    python robustez.py comparar   POPULACAO.csv CLASSIF_V3.csv PASTA_LOTES SAIDA.csv
    python robustez.py repeticao  POPULACAO.csv CLASSIF_V3.csv SAIDA.csv
    python robustez.py tipos_risco POPULACAO.csv CLASSIF_V3.csv PASTA_RISCO SAIDA.csv
    python robustez.py repeticao_base POPULACAO.csv CLASSIF_V3.csv PASTA_DADOS SAIDA.csv ANO...
    python robustez.py grupos POPULACAO.csv CLASSIF_V3.csv PASTA_DADOS MAPA.csv CONTAGEM.csv
    python robustez.py rodada2_lotes    POPULACAO.csv PASTA_V3 PASTA_RODADA2
    python robustez.py rodada2_comparar CLASSIF_V3.csv PASTA_RODADA2 SAIDA.csv

lotes      sorteia 200 trechos válidos (100 da seção 4, 100 das demais; semente fixa) e grava lotes de 50
           só com id, termos e trecho, para o prompt prompts/classificador_v3_semsecao.md, que não vê a
           seção, o título nem a companhia. Cada lote é classificado por um agente isolado, como no v3,
           e grava saida_XX.jsonl na mesma pasta.
comparar   compara a classificação sem seção com a do v3: distribuição da função e acordo por grupo
           (seção 4 / demais), e α de Krippendorff da função nos 200. Responde se a associação
           seção–função vem do texto ou da informação de seção dada ao modelo.
repeticao  para cada trecho válido, procura um quase-duplicado em outra companhia do mesmo ano:
           semelhança de Jaccard >= LIMIAR entre conjuntos de sequências de cinco palavras. Também
           exclui pares de empresas com o mesmo primeiro nome (indicador grosseiro de mesmo grupo).
           Grava a porcentagem por ano e função.
tipos_risco junta a codificação exploratória dos tipos de risco (prompts/tipos_risco_v1.md; lotes
           entrada_XX/saida_XX em PASTA_RISCO, só trechos com função RISCO) e grava, por ano, a % dos
           trechos de risco que citam cada tipo e a % em que ele é o principal, além da % das
           companhias que entregaram o FRE com ao menos um trecho de cada tipo. Compara a rodada
           principal com a rodada independente de consistencia_entrada/saida (100 trechos).
"""
import csv
import glob
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from verificacao import alfa_nominal

SEMENTE = 20261101
POR_GRUPO = 100
TAMANHO_LOTE = 50
LIMIAR = 0.5
FUNCOES = ("RISCO", "USO", "PROD", "NEGOCIO", "GENERICA", "GOV")
fp = lambda v: str(v).strip().lower() in ("sim", "true")


def validos(populacao_csv, classif_csv):
    modelo = {r["id_trecho"]: r for r in csv.DictReader(open(classif_csv, encoding="utf-8"))}
    return [dict(t, **{k: modelo[t["id_trecho"]][k] for k in ("funcao", "evidencia", "tom", "tempo")})
            for t in csv.DictReader(open(populacao_csv, encoding="utf-8-sig"))
            if t["id_trecho"] in modelo and not fp(modelo[t["id_trecho"]]["falso_positivo"])]


def cmd_lotes(populacao_csv, classif_csv, pasta):
    rng = random.Random(SEMENTE)
    ok = validos(populacao_csv, classif_csv)
    s4 = [t for t in ok if t["secao"].startswith("4.")]
    outras = [t for t in ok if not t["secao"].startswith("4.")]
    amostra = rng.sample(s4, POR_GRUPO) + rng.sample(outras, POR_GRUPO)
    rng.shuffle(amostra)
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    for i in range(0, len(amostra), TAMANHO_LOTE):
        with open(pasta / f"entrada_{i // TAMANHO_LOTE + 1:02d}.jsonl", "w", encoding="utf-8") as f:
            for t in amostra[i:i + TAMANHO_LOTE]:
                f.write(json.dumps({"id_trecho": t["id_trecho"], "termos": t["termos"], "trecho": t["trecho"]},
                                   ensure_ascii=False) + "\n")
    print(f"{len(amostra)} trechos em {-(-len(amostra) // TAMANHO_LOTE)} lotes -> {pasta}")


def cmd_comparar(populacao_csv, classif_csv, pasta, saida):
    v3 = {t["id_trecho"]: t for t in validos(populacao_csv, classif_csv)}
    sem = {}
    for arq in sorted(glob.glob(str(Path(pasta) / "saida_*.jsonl"))):
        for linha in open(arq, encoding="utf-8"):
            if linha.strip():
                r = json.loads(linha)
                sem[r["id_trecho"]] = r
    entrada = [json.loads(l)["id_trecho"] for arq in sorted(glob.glob(str(Path(pasta) / "entrada_*.jsonl")))
               for l in open(arq, encoding="utf-8") if l.strip()]
    # trechos que saíram da população (chatbot, assistente virtual e modelo preditivo sem nomear IA) ficam de fora
    entrada = [i for i in entrada if i in v3]
    faltando = [i for i in entrada if i not in sem]
    rotulo = lambda r: "FALSO_POSITIVO" if fp(r.get("falso_positivo")) else str(r.get("funcao")).upper()
    linhas = []
    for grupo, filtro in (("secao_4", lambda s: s.startswith("4.")), ("demais", lambda s: not s.startswith("4.")),
                          ("todos", lambda s: True)):
        ids = [i for i in entrada if i in sem and filtro(v3[i]["secao"])]
        pares = [(v3[i]["funcao"], rotulo(sem[i])) for i in ids]
        c_v3, c_sem = Counter(a for a, _ in pares), Counter(b for _, b in pares)
        linha = {"grupo": grupo, "n": len(ids),
                 "acordo_funcao_pct": round(100 * sum(a == b for a, b in pares) / len(pares), 1),
                 "alfa_funcao": alfa_nominal(pares)}
        for d in ("tempo", "tom", "evidencia"):
            linha[f"acordo_{d}_pct"] = round(100 * sum(not fp(sem[i].get("falso_positivo")) and
                                                       str(sem[i].get(d)).upper() == v3[i][d].upper() for i in ids) / len(ids), 1)
        for k in FUNCOES + ("FALSO_POSITIVO",):
            linha[f"v3_{k}"], linha[f"semsecao_{k}"] = c_v3.get(k, 0), c_sem.get(k, 0)
        linhas.append(linha)
    gravar(saida, linhas)
    for l in linhas:
        print(l["grupo"], l["n"], "acordo função", l["acordo_funcao_pct"], "α", l["alfa_funcao"],
              "| RISCO v3/sem seção:", l["v3_RISCO"], l["semsecao_RISCO"])
    if faltando:
        print("faltando:", faltando)


RE_GOVERNO = re.compile(r"tesouro|uni[ãa]o federal|governo|minist[ée]rio|estado d[eo]|munic[íi]pio|prefeitura|secretaria", re.I)


def grupos(pasta_dados, ano):
    """cd_cvm -> id do grupo econômico, pelos controladores declarados no próprio FRE (posição acionária).

    Duas companhias ficam no mesmo grupo se compartilham um controlador pessoa jurídica na cadeia majoritária
    (o acionista direto com ao menos 50% das ações ordinárias ou do total, o acionista majoritário dele, e assim
    por diante) ou se uma controla a outra. Entes públicos (Tesouro, estados, municípios) não
    unem grupos: companhias estatais diferentes não são tratadas como o mesmo grupo."""
    pasta = Path(pasta_dados) / f"fre_{ano}"
    cnpj_cd = {}
    with open(pasta / f"fre_cia_aberta_{ano}.csv", encoding="latin1") as f:
        for r in csv.DictReader(f, delimiter=";"):
            cnpj_cd[re.sub(r"\D", "", r["CNPJ_CIA"])] = r["CD_CVM"].zfill(6)
    pai = {}
    def raiz(x):
        while pai.setdefault(x, x) != x:
            pai[x] = pai[pai[x]]
            x = pai[x]
        return x
    def unir(a, b):
        pai[raiz(a)] = raiz(b)
    # cadeia majoritária: controlador direto com >= 50%, depois o controlador majoritário dele, e assim por diante.
    # Linhas indiretas de acionistas minoritários (ex.: donos de um sócio de uma SPE) não entram na cadeia.
    por_cia = defaultdict(list)
    with open(pasta / f"fre_cia_aberta_posicao_acionaria_{ano}.csv", encoding="latin1") as f:
        for r in csv.DictReader(f, delimiter=";"):
            cia = cnpj_cd.get(re.sub(r"\D", "", r["CNPJ_Companhia"]))
            if cia:
                por_cia[cia].append(r)
    for cia, rows in por_cia.items():
        maj = lambda r: max(float(r.get("Percentual_Acao_Ordinaria_Circulacao") or 0),
                            float(r.get("Percentual_Total_Acoes_Circulacao") or 0)) >= 50
        filhos = defaultdict(list)
        for r in rows:
            filhos[r.get("ID_Acionista_Relacionado") or ""].append(r)
        fila = [r for r in filhos[""] if maj(r)]
        vistos = set()
        while fila:
            r = fila.pop()
            if r["ID_Acionista"] in vistos:
                continue
            vistos.add(r["ID_Acionista"])
            doc, nome = re.sub(r"\D", "", r["CPF_CNPJ_Acionista"] or ""), r["Acionista"] or ""
            if r.get("Tipo_Pessoa_Acionista") == "PJ" and doc.strip("0") and not RE_GOVERNO.search(nome):
                unir("cvm:" + cia, "pj:" + doc)
                if doc in cnpj_cd:
                    unir("cvm:" + cia, "cvm:" + cnpj_cd[doc])
            fila += [x for x in filhos[r["ID_Acionista"]] if maj(x)]
    for doc, cd in cnpj_cd.items():
        unir("cvm:" + cd, "pj:" + doc)  # a companhia é também o CNPJ dela (controladora de outra)
    return {cd: raiz("cvm:" + cd) for cd in cnpj_cd.values()}


def shingles(texto):
    w = re.findall(r"\w+", texto.lower())
    return {" ".join(w[i:i + 5]) for i in range(max(1, len(w) - 4))}


def cmd_repeticao(populacao_csv, classif_csv, saida):
    ok = validos(populacao_csv, classif_csv)
    pasta_dados = Path(populacao_csv).parent.parent
    g = {a: grupos(pasta_dados, a) for a in sorted({t["ano"] for t in ok})}
    por_ano = defaultdict(list)
    for t in ok:
        t["_sh"] = shingles(t["trecho"])
        t["_nome"] = t["empresa"].split()[0].lower()
        t["_grupo"] = g[t["ano"]].get(t["cd_cvm"], t["cd_cvm"])
        por_ano[t["ano"]].append(t)
    linhas = []
    for ano, ts in sorted(por_ano.items()):
        repete, repete_outro_grupo, repete_outro_ctrl = set(), set(), set()
        for i, t in enumerate(ts):
            for u in ts[i + 1:]:
                if u["cd_cvm"] == t["cd_cvm"]:
                    continue
                if len(t["_sh"] & u["_sh"]) / len(t["_sh"] | u["_sh"]) >= LIMIAR:
                    repete |= {t["id_trecho"], u["id_trecho"]}
                    if t["_nome"] != u["_nome"]:
                        repete_outro_grupo |= {t["id_trecho"], u["id_trecho"]}
                    if t["_nome"] != u["_nome"] and t["_grupo"] != u["_grupo"]:
                        repete_outro_ctrl |= {t["id_trecho"], u["id_trecho"]}
        for f in FUNCOES:
            grupo = [t for t in ts if t["funcao"] == f]
            if grupo:
                linhas.append({"ano": ano, "funcao": f, "trechos": len(grupo),
                               "quase_duplicado_pct": round(100 * sum(t["id_trecho"] in repete for t in grupo) / len(grupo), 1),
                               "sem_mesmo_primeiro_nome_pct": round(100 * sum(t["id_trecho"] in repete_outro_grupo for t in grupo) / len(grupo), 1),
                               "sem_mesmo_grupo_pct": round(100 * sum(t["id_trecho"] in repete_outro_ctrl for t in grupo) / len(grupo), 1)})
    gravar(saida, linhas)
    for l in linhas:
        if l["funcao"] in ("RISCO", "USO"):
            print(l)


TIPOS = ("REGULACAO", "SEGURANCA", "CONCORRENCIA", "OPERACIONAL", "REPUTACAO_ETICA", "TRABALHO", "GENERICO")


def ler_jsonl(padrao):
    saida = {}
    for arq in sorted(glob.glob(padrao)):
        for linha in open(arq, encoding="utf-8"):
            if linha.strip():
                r = json.loads(linha)
                saida[r["id_trecho"]] = r
    return saida


def cmd_tipos_risco(populacao_csv, classif_csv, pasta, saida):
    risco = {t["id_trecho"]: t for t in validos(populacao_csv, classif_csv) if t["funcao"] == "RISCO"}
    principal = ler_jsonl(str(Path(pasta) / "saida_*.jsonl"))
    faltando = [i for i in risco if i not in principal]
    entregaram = {}
    pasta_dados = Path(populacao_csv).parent.parent
    for a in sorted({t["ano"] for t in risco.values()}):
        entregaram[a] = len(list(csv.DictReader(open(pasta_dados / f"resumo_{a}.csv", encoding="utf-8"))))
    linhas = []
    for a in sorted(entregaram):
        ids = [i for i, t in risco.items() if t["ano"] == a and i in principal]
        for k in TIPOS:
            com = [i for i in ids if k in principal[i]["tipos"]]
            linhas.append({"ano": a, "tipo": k, "trechos_risco": len(ids),
                           "cita_pct": round(100 * len(com) / len(ids), 1),
                           "principal_pct": round(100 * sum(principal[i]["principal"] == k for i in ids) / len(ids), 1),
                           "companhias_pct_fre": round(100 * len({risco[i]["cd_cvm"] for i in com}) / entregaram[a], 1)})
    gravar(saida, linhas)
    rodada2 = ler_jsonl(str(Path(pasta) / "consistencia_saida.jsonl"))
    comuns = [i for i in rodada2 if i in principal]
    pares = [(principal[i]["principal"], rodada2[i]["principal"]) for i in comuns]
    jac = [len(set(principal[i]["tipos"]) & set(rodada2[i]["tipos"])) / len(set(principal[i]["tipos"]) | set(rodada2[i]["tipos"]))
           for i in comuns]
    print(f"{len(principal)} de {len(risco)} trechos de risco codificados; faltando {len(faltando)}")
    print(f"consistência (n={len(comuns)}): principal igual {round(100 * sum(a == b for a, b in pares) / len(pares), 1)}%, "
          f"α {alfa_nominal(pares)}; Jaccard médio dos tipos {round(sum(jac) / len(jac), 2)}")
    for k in TIPOS:
        a_ = sum(k in principal[i]["tipos"] for i in comuns)
        b_ = sum(k in rodada2[i]["tipos"] for i in comuns)
        ambos = sum(k in principal[i]["tipos"] and k in rodada2[i]["tipos"] for i in comuns)
        print(f"  {k:16} rodada1 {a_:3} rodada2 {b_:3} ambas {ambos:3}")
    for l in linhas:
        if l["ano"] in ("2023", "2026"):
            print(l)


SEMENTE_BASE = 20261106
LIMIARES = (0.3, 0.5, 0.7)
RE_IA_SOLTA = re.compile(r"intelig[êe]ncia\s+artificial|artificial\s+intelligence|\bIA\b|\bAI\b|machine\s+learning|"
                         r"aprendizado|aprendizagem|redes?\s+neura|generativ|chatgpt|\bllm", re.I)
RE_FRASE = re.compile(r"(?<=[.!?;])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9•(\-])")
# temas recorrentes de fatores de risco que não são IA: a janela é centrada na frase do tema, como o trecho
# de IA é centrado na frase do termo (janelas sem âncora quase nunca se alinham entre empresas)
RE_ANCORA = re.compile(r"c[âa]mbi|taxas? de juros|infla[çc][ãa]o|cibern[ée]tic|mudan[çc]as? clim[áa]tic|pandemi|"
                       r"covid|lavagem de dinheiro|corrup[çc][ãa]o|LGPD|prote[çc][ãa]o de dados", re.I)


def quase_duplicados(itens, limiar):
    """itens: dicts com _sh, cd_cvm, _nome e _grupo. Devolve (ids com par em outra companhia, ids com par fora do
    mesmo grupo econômico — nem mesmo primeiro nome, nem mesmo controlador)."""
    rep, rep_outro = set(), set()
    for i, t in enumerate(itens):
        for u in itens[i + 1:]:
            if u["cd_cvm"] == t["cd_cvm"] or not t["_sh"] or not u["_sh"]:
                continue
            if len(t["_sh"] & u["_sh"]) / len(t["_sh"] | u["_sh"]) >= limiar:
                rep |= {t["id"], u["id"]}
                if t["_nome"] != u["_nome"] and t.get("_grupo", 1) != u.get("_grupo", 2):
                    rep_outro |= {t["id"], u["id"]}
    return rep, rep_outro


def cmd_repeticao_base(populacao_csv, classif_csv, pasta_dados, saida, *anos, ancorada=True):
    """Linha de base da repetição e sensibilidade ao limiar (pedidos da revisão).

    Para cada ano, compara a repetição entre companhias dos trechos de risco de IA com a de trechos da
    seção 4 que não falam de IA: para cada companhia, sorteia tantas janelas de três frases (a mesma
    unidade do trecho, centradas numa frase sobre um tema de risco recorrente que não é IA: câmbio, juros,
    inflação, ataques cibernéticos, clima, pandemia, corrupção, proteção de dados) quantos trechos de risco
    de IA ela tem, e aplica o mesmo critério. Cinco sorteios;
    limiares 0,3, 0,5 e 0,7. Também mede a persistência: % dos trechos de risco de IA do ano com um
    quase-duplicado (≥ 0,5) entre os trechos da mesma companhia no ano anterior."""
    ok = validos(populacao_csv, classif_csv)
    g = {a: grupos(pasta_dados, a) for a in sorted({t["ano"] for t in ok})}
    risco = defaultdict(list)
    for t in ok:
        if t["funcao"] == "RISCO":
            risco[t["ano"]].append({"id": t["id_trecho"], "cd_cvm": t["cd_cvm"], "_nome": t["empresa"].split()[0].lower(),
                                    "_grupo": g[t["ano"]].get(t["cd_cvm"], t["cd_cvm"]), "_sh": shingles(t["trecho"])})
    linhas = []
    for ano in anos:
        alvo = Counter(t["cd_cvm"] for t in risco[ano])
        janelas = defaultdict(list)
        nomes = {}
        with open(Path(pasta_dados) / f"secoes_{ano}.jsonl", encoding="utf-8") as f:
            for linha in f:
                if '"secao": "4.' not in linha:
                    continue
                p = json.loads(linha)
                if p["cd_cvm"] not in alvo or not p["secao"].startswith("4."):
                    continue
                nomes[p["cd_cvm"]] = p["empresa"].split()[0].lower()
                fs = [x for x in RE_FRASE.split(p["texto"].replace("\x00", "")) if x.strip()]
                for i in range(1, len(fs) - 1):
                    jan = " ".join(fs[i - 1:i + 2])
                    if ancorada and not RE_ANCORA.search(fs[i]):
                        continue
                    if len(jan.split()) >= 30 and not RE_IA_SOLTA.search(jan):
                        janelas[p["cd_cvm"]].append(jan)
        for lim in LIMIARES:
            r, ro = quase_duplicados(risco[ano], lim)
            n = len(risco[ano])
            base, base_o = [], []
            for s in range(5):
                rng = random.Random(SEMENTE_BASE + s)
                pool = []
                for cd, k in alvo.items():
                    for j, jan in enumerate(rng.sample(janelas[cd], min(k, len(janelas[cd])))):
                        pool.append({"id": f"{cd}-{j}", "cd_cvm": cd, "_nome": nomes[cd], "_grupo": g[ano].get(cd, cd),
                                     "_sh": shingles(jan)})
                b, bo = quase_duplicados(pool, lim)
                base.append(100 * len(b) / len(pool))
                base_o.append(100 * len(bo) / len(pool))
            linhas.append({"ano": ano, "limiar": lim, "trechos_risco_ia": n,
                           "risco_ia_pct": round(100 * len(r) / n, 1), "risco_ia_sem_mesmo_grupo_pct": round(100 * len(ro) / n, 1),
                           "base_sem_ia_pct": round(sum(base) / 5, 1), "base_sem_ia_sem_mesmo_grupo_pct": round(sum(base_o) / 5, 1)})
            print(linhas[-1])
        anterior = str(int(ano) - 1)
        if anterior in risco:
            prev = defaultdict(list)
            for t in risco[anterior]:
                prev[t["cd_cvm"]].append(t["_sh"])
            pers = sum(any(len(t["_sh"] & u) / len(t["_sh"] | u) >= 0.5 for u in prev[t["cd_cvm"]]) for t in risco[ano])
            print(ano, "persistência (mesma companhia, ano anterior, ≥ 0,5):", round(100 * pers / len(risco[ano]), 1), "%")
            for l in linhas:
                if l["ano"] == ano:
                    l["persistencia_ano_anterior_pct"] = round(100 * pers / len(risco[ano]), 1)
    gravar(saida, linhas)


def cmd_grupos(populacao_csv, classif_csv, pasta_dados, saida_mapa, saida_contagem):
    """Publica o mapa companhia → grupo econômico (por ano) e conta grupos distintos nos indicadores
    principais (pedido da segunda rodada): cita IA, risco e uso, no total e por macrossetor."""
    from setores import carregar_cadastro
    ok = validos(populacao_csv, classif_csv)
    cad = carregar_cadastro(Path(pasta_dados) / "cad_cia_aberta.csv")
    macro = lambda cd: cad.get(cd.lstrip("0"), ("", "Não classificado"))[1]
    mapa, cont = [], []
    for ano in ("2023", "2024", "2025", "2026"):
        g = grupos(pasta_dados, ano)
        tam = Counter(g.values())
        nomes = {}
        for r in csv.DictReader(open(Path(pasta_dados) / f"resumo_{ano}.csv", encoding="utf-8")):
            nomes[r["cd_cvm"]] = r["empresa"]
        ids = {gid: f"G{ano}-{i:03d}" for i, gid in enumerate(sorted(set(g.values())), 1)}
        for cd, gid in sorted(g.items()):
            mapa.append({"ano": ano, "cd_cvm": cd, "empresa": nomes.get(cd, ""), "grupo": ids[gid], "companhias_no_grupo": tam[gid]})
        ts = [t for t in ok if t["ano"] == ano]
        for rotulo, filtro in (("cita_ia", lambda t: True), ("risco", lambda t: t["funcao"] == "RISCO"), ("uso", lambda t: t["funcao"] == "USO")):
            for setor in ("todos",) + tuple(sorted({macro(cd) for cd in g})):
                cds = {t["cd_cvm"] for t in ts if filtro(t) and (setor == "todos" or macro(t["cd_cvm"]) == setor)}
                if setor != "todos" and not cds:
                    continue
                cont.append({"ano": ano, "indicador": rotulo, "macrossetor": setor, "companhias": len(cds),
                             "grupos": len({g.get(cd, cd) for cd in cds})})
        multi = sum(1 for v in tam.values() if v > 1)
        print(ano, "grupos com mais de uma companhia:", multi, "| maior:", max(tam.values()))
    gravar(saida_mapa, mapa)
    gravar(saida_contagem, cont)
    for l in cont:
        if l["ano"] in ("2023", "2026") and (l["macrossetor"] in ("todos", "Energia e saneamento")):
            print(l)


SEMENTE_RODADA2 = 20261105
N_RODADA2 = 300


def cmd_rodada2_lotes(populacao_csv, pasta_v3, pasta):
    """Sorteia 300 trechos da população atual e regrava, em lotes de 50, as mesmas entradas que o v3 leu.

    Cada lote é classificado de novo por um agente isolado com prompts/classificador_v3.md, sem ver a
    primeira rodada; mede a estabilidade do classificador nas cinco dimensões (pedido da revisão)."""
    ids = sorted(t["id_trecho"] for t in csv.DictReader(open(populacao_csv, encoding="utf-8-sig")))
    amostra = random.Random(SEMENTE_RODADA2).sample(ids, N_RODADA2)
    entradas = {}
    for arq in glob.glob(str(Path(pasta_v3) / "entrada_*.jsonl")):
        for linha in open(arq, encoding="utf-8"):
            if linha.strip():
                r = json.loads(linha)
                entradas[r["id_trecho"]] = r
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    for i in range(0, N_RODADA2, TAMANHO_LOTE):
        with open(pasta / f"entrada_{i // TAMANHO_LOTE + 1:02d}.jsonl", "w", encoding="utf-8") as f:
            for t in amostra[i:i + TAMANHO_LOTE]:
                f.write(json.dumps(entradas[t], ensure_ascii=False) + "\n")
    print(f"{N_RODADA2} trechos em {N_RODADA2 // TAMANHO_LOTE} lotes -> {pasta}")


def cmd_rodada2_comparar(classif_csv, pasta, saida):
    """Compara a segunda rodada com a classificação v3: acordo e α por dimensão."""
    v3 = {r["id_trecho"]: r for r in csv.DictReader(open(classif_csv, encoding="utf-8"))}
    r2 = ler_jsonl(str(Path(pasta) / "saida_*.jsonl"))
    ids = [i for i in ler_jsonl(str(Path(pasta) / "entrada_*.jsonl")) if i in r2]
    rot = lambda r: "FALSO_POSITIVO" if fp(r.get("falso_positivo")) else str(r.get("funcao")).upper()
    gov = lambda v: "nenhuma" not in (v if isinstance(v, str) else ";".join(v or [])).lower()
    linhas = [{"dimensao": "funcao_com_fp", "pares": [(rot(v3[i]), rot(r2[i])) for i in ids]},
              {"dimensao": "falso_positivo", "pares": [(fp(v3[i]["falso_positivo"]), fp(r2[i].get("falso_positivo"))) for i in ids]}]
    validos = [i for i in ids if not fp(v3[i]["falso_positivo"]) and not fp(r2[i].get("falso_positivo"))]
    for d in ("funcao", "evidencia", "tom", "tempo"):
        linhas.append({"dimensao": d, "pares": [(v3[i][d].upper(), str(r2[i].get(d)).upper()) for i in validos]})
    linhas.append({"dimensao": "governanca_declarada", "pares": [(gov(v3[i]["governanca"]), gov(r2[i].get("governanca"))) for i in validos]})
    saida_l = [{"dimensao": l["dimensao"], "n": len(l["pares"]),
                "acordo_pct": round(100 * sum(a == b for a, b in l["pares"]) / len(l["pares"]), 1),
                "alfa": alfa_nominal(l["pares"])} for l in linhas]
    gravar(saida, saida_l)
    for l in saida_l:
        print(l)


def gravar(caminho, linhas):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)


if __name__ == "__main__":
    {"lotes": cmd_lotes, "comparar": cmd_comparar, "repeticao": cmd_repeticao, "tipos_risco": cmd_tipos_risco,
     "repeticao_base": cmd_repeticao_base, "grupos": cmd_grupos, "rodada2_lotes": cmd_rodada2_lotes, "rodada2_comparar": cmd_rodada2_comparar}[sys.argv[1]](*sys.argv[2:])
