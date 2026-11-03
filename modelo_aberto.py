"""Comparação com modelos abertos (Ollama), sem trocar o classificador do estudo.

Uso:
    python modelo_aberto.py classificar MODELO PASTA_ANOTACAO {cega,dupla} SAIDA_DIR
    python modelo_aberto.py comparar    PASTA_ANOTACAO SAIDA_DIR [SAIDA_DIR ...]

classificar  manda ao modelo, via API local do Ollama (http://localhost:11434), o mesmo prompt
             do classificador v3 (prompts/classificador_v3.md), um trecho por chamada, com
             temperatura 0, semente fixa, raciocínio desligado e saída restrita pelo esquema JSON
             dos códigos do guia. Modelo do artigo: gemma4:12b-it-q4_K_M (GGUF, o mesmo arquivo em
             qualquer sistema). Variantes que o Ollama roda pelo motor MLX (ex.: gemma4:12b no Mac)
             recusam a saída estruturada; nelas, cada resposta é validada contra os códigos, a
             inválida é pedida de novo uma vez e, quando o modelo para antes da chave final do JSON,
             ela é acrescentada. Se continuar inválida, o trecho fica sem rótulo ("INVALIDO"), o que
             conta como discordância. Tudo isso fica contado em meta_AMOSTRA.json.
             Amostras: "cega" = os trechos do padrão-ouro anotados às cegas pelo autor (desenvolvimento,
             usados para escolher o modelo); "dupla" = a anotação dupla às cegas (teste).
             Grava em SAIDA_DIR: entrada_AMOSTRA.jsonl, saida_AMOSTRA.jsonl e meta_AMOSTRA.json
             (modelo, digest, versão do Ollama, opções, tempo por trecho). Retomável.
comparar     mede cada SAIDA_DIR (e o v3, como referência) contra os rótulos humanos, com as mesmas
             funções da Tabela 2 (dupla_v2.comparar_par): cegos do padrão-ouro; anotador 1, anotador 2
             e consenso da anotação dupla. Grava SAIDA_DIR/../comparacao_modelos_abertos.csv.

Lê de PASTA_ANOTACAO: populacao_v1.csv, ouro_v1.csv, classificacoes_llm_v3.csv e, em dupla_v2/,
anotacoes_v2.csv e consenso_v2.csv.
"""
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from dupla_v2 import comparar_par

OLLAMA = "http://localhost:11434"
PROMPT = Path(__file__).parent / "prompts" / "classificador_v3.md"
OPCOES = {"temperature": 0, "seed": 42, "num_ctx": 8192}
CAMPOS = ("id_trecho", "empresa", "secao", "titulo_secao", "termos", "trecho")
UM_TRECHO = ("\n\n## Nesta execução\n\nVocê recebe um único trecho por mensagem, como objeto JSON. Responda com um "
             "único objeto JSON no formato acima, sem texto antes ou depois.")
CODIGOS = {"funcao": {"RISCO", "USO", "PROD", "NEGOCIO", "GENERICA", "GOV"}, "evidencia": {"SEM", "CASO", "METRICA"},
           "tom": {"POS", "NEU", "NEG"}, "tempo": {"REALIZADO", "EM_CURSO", "PLANEJADO", "NA"}}
GOVERNANCA = {"politica", "comite_ou_responsavel", "supervisao_humana", "protecao_dados", "nenhuma"}
CORRIGIR = ("A resposta não está no formato pedido. Responda de novo, só com um objeto JSON com os campos e os "
            "códigos exatos do guia.")
ESQUEMA = {
    "type": "object",
    "properties": {
        "id_trecho": {"type": "string"},
        "falso_positivo": {"type": "boolean"},
        **{d: {"type": ["string", "null"], "enum": sorted(c) + [None]} for d, c in CODIGOS.items()},
        "governanca": {"type": ["array", "null"], "items": {"type": "string", "enum": sorted(GOVERNANCA)}},
        "duvida": {"type": "boolean"},
        "justificativa": {"type": "string"},
    },
    "required": ["id_trecho", "falso_positivo", "funcao", "evidencia", "governanca", "tom", "tempo", "duvida",
                 "justificativa"],
}


def extrair(texto):
    """Objeto JSON da resposta e se foi preciso fechar a chave final (o qwen3.5 às vezes para antes dela)."""
    ini = texto.find("{")
    if ini < 0:
        return None, False
    for sufixo, reparo in (("", False), ("}", True)):
        corpo = texto[ini:].rstrip().removesuffix("```").rstrip() + sufixo
        try:
            return json.JSONDecoder().raw_decode(corpo)[0], reparo
        except ValueError:
            continue
    return None, False


def validar(texto):
    """Devolve (objeto, reparado) se os códigos forem válidos; senão, (None, False)."""
    r, reparo = extrair(texto)
    if not isinstance(r, dict):
        return None, False
    return (r, reparo) if codigos_validos(r) else (None, False)


def codigos_validos(r):
    if not isinstance(r.get("falso_positivo"), bool):
        return False
    if r["falso_positivo"]:
        return True
    gov = r.get("governanca") or ["nenhuma"]
    gov = [gov] if isinstance(gov, str) else gov
    if not all(r.get(d) in cods for d, cods in CODIGOS.items()) or not set(gov) <= GOVERNANCA:
        return False
    r["governanca"] = gov
    return True


def api(caminho, corpo=None):
    req = urllib.request.Request(OLLAMA + caminho, data=json.dumps(corpo).encode() if corpo is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)


def ids_amostra(pasta, amostra):
    pop = {t["id_trecho"] for t in csv.DictReader(open(pasta / "populacao_v1.csv", encoding="utf-8-sig"))}
    if amostra == "cega":
        ouro = csv.DictReader(open(pasta / "ouro_v1.csv", encoding="utf-8-sig"))
        return [r["id_trecho"] for r in ouro if r["origem"] == "cega" and r["id_trecho"] in pop]
    dupla = csv.DictReader(open(pasta / "dupla_v2" / "anotacoes_v2.csv", encoding="utf-8"))
    return [r["id_trecho"] for r in dupla if r["id_trecho"] in pop]


def cmd_classificar(modelo, pasta, amostra, saida):
    pasta, saida = Path(pasta), Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    ids = ids_amostra(pasta, amostra)
    pop = {t["id_trecho"]: t for t in csv.DictReader(open(pasta / "populacao_v1.csv", encoding="utf-8-sig"))}
    entrada = [{c: pop[i][c] for c in CAMPOS} for i in ids]
    with open(saida / f"entrada_{amostra}.jsonl", "w", encoding="utf-8") as f:
        for e in entrada:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    arq = saida / f"saida_{amostra}.jsonl"
    feitos = {json.loads(l)["id_trecho"] for l in open(arq, encoding="utf-8")} if arq.exists() else set()
    sistema = PROMPT.read_text(encoding="utf-8") + UM_TRECHO
    info = next(m for m in api("/api/tags")["models"] if m["name"] == modelo)
    segundos, repetidas, invalidas, reparadas = [], 0, 0, 0
    estruturada = True
    with open(arq, "a", encoding="utf-8") as f:
        for k, e in enumerate(entrada, 1):
            if e["id_trecho"] in feitos:
                continue
            t0 = time.time()
            msgs = [{"role": "system", "content": sistema}, {"role": "user", "content": json.dumps(e, ensure_ascii=False)}]
            for tentativa in range(2):
                corpo = {"model": modelo, "stream": False, "think": False, "options": OPCOES, "keep_alive": "30m",
                         "messages": msgs}
                try:
                    r = api("/api/chat", {**corpo, "format": ESQUEMA} if estruturada else corpo)
                except urllib.error.HTTPError as erro:
                    if erro.code != 501 or not estruturada:  # 501: "structured output is unavailable" (motor MLX)
                        raise
                    estruturada = False
                    r = api("/api/chat", corpo)
                resposta, reparo = validar(r["message"]["content"])
                if resposta is not None:
                    reparadas += reparo
                    break
                repetidas += tentativa == 0
                msgs += [r["message"], {"role": "user", "content": CORRIGIR}]
            if resposta is None:
                invalidas += 1
                resposta = {"falso_positivo": False, "funcao": "INVALIDO", "evidencia": "INVALIDO", "governanca": ["INVALIDO"],
                            "tom": "INVALIDO", "tempo": "INVALIDO", "bruto": r["message"]["content"][:500]}
            resposta["id_trecho"] = e["id_trecho"]  # o id vem da entrada, não do modelo
            f.write(json.dumps(resposta, ensure_ascii=False) + "\n")
            f.flush()
            segundos.append(time.time() - t0)
            print(f"{k}/{len(entrada)} {e['id_trecho']} {resposta.get('funcao')} {segundos[-1]:.1f}s", flush=True)

    meta = {"modelo": modelo, "digest": info["digest"], "tamanho_bytes": info["size"],
            "detalhes": info.get("details"), "ollama": api("/api/version")["version"], "opcoes": OPCOES,
            "think": False, "saida_estruturada": estruturada, "prompt": PROMPT.name, "amostra": amostra,
            "trechos": len(entrada),
            "segundos_por_trecho_nesta_execucao": round(sum(segundos) / len(segundos), 1) if segundos else None,
            "respostas_pedidas_de_novo": repetidas, "respostas_invalidas": invalidas,
            "respostas_com_chave_final_acrescentada": reparadas,
            "data": time.strftime("%Y-%m-%d")}
    json.dump(meta, open(saida / f"meta_{amostra}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def ler_saida(arq):
    """Saída JSONL do modelo no formato dos rótulos humanos (falso_positivo sim/nao; governança em texto)."""
    out = {}
    for l in open(arq, encoding="utf-8"):
        r = json.loads(l)
        r["falso_positivo"] = "sim" if r["falso_positivo"] else "nao"
        r["governanca"] = ";".join(r["governanca"] or [])
        out[r["id_trecho"]] = {k: ("" if v is None else v) for k, v in r.items()}
    return out


def cmd_comparar(pasta, *saidas):
    pasta = Path(pasta)
    ouro = {r["id_trecho"]: r for r in csv.DictReader(open(pasta / "ouro_v1.csv", encoding="utf-8-sig"))}
    dupla = list(csv.DictReader(open(pasta / "dupla_v2" / "anotacoes_v2.csv", encoding="utf-8")))
    a1 = {r["id_trecho"]: {k[3:]: v for k, v in r.items() if k.startswith("a1_")} for r in dupla}
    a2 = {r["id_trecho"]: {k[3:]: v for k, v in r.items() if k.startswith("a2_")} for r in dupla}
    cons = {r["id_trecho"]: r for r in csv.DictReader(open(pasta / "dupla_v2" / "consenso_v2.csv", encoding="utf-8"))}
    v3 = {r["id_trecho"]: r for r in csv.DictReader(open(pasta / "classificacoes_llm_v3.csv", encoding="utf-8"))}

    modelos = [("claude-opus-5-5 (v3)", v3)]
    for s in saidas:
        s = Path(s)
        for amostra in ("cega", "dupla"):
            if (s / f"saida_{amostra}.jsonl").exists():
                meta = json.load(open(s / f"meta_{amostra}.json", encoding="utf-8"))
                modelos.append((f"{meta['modelo']} [{amostra}]", ler_saida(s / f"saida_{amostra}.jsonl")))

    linhas = []
    for nome, m in modelos:
        for amostra, refs in (("cega", (("autor_cego", ouro),)),
                              ("dupla", (("anotador1", a1), ("anotador2", a2), ("consenso", cons)))):
            ids = [i for i in ids_amostra(pasta, amostra) if i in m]
            if not ids or (f"[{'dupla' if amostra == 'cega' else 'cega'}]" in nome):
                continue
            for ref_nome, ref in refs:
                for l in comparar_par(ref, m, ids):
                    linhas.append({"modelo": nome.split(" [")[0], "amostra": amostra, "referencia": ref_nome, **l})
    destino = Path(saidas[0]).parent / "comparacao_modelos_abertos.csv"
    with open(destino, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    for l in linhas:
        if l["dimensao"] in ("funcao", "evidencia", "tom", "tempo", "governanca_declarada", "falso_positivo"):
            print(f"{l['modelo']:24} {l['amostra']:5} {l['referencia']:10} {l['dimensao']:20} n={l['n']:3} "
                  f"acordo {l['acordo_pct']:5} α {l['alfa']}")


if __name__ == "__main__":
    {"classificar": cmd_classificar, "comparar": cmd_comparar}[sys.argv[1]](*sys.argv[2:])
