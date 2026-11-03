"""Etapa 3 — detecta menções a IA (e termos vizinhos) no texto por seção.

Uso:
    python detectar_mencoes.py SECOES.jsonl MENCOES.csv RESUMO.csv

MENCOES.csv: uma linha por ocorrência, com o trecho (frase da menção mais
uma frase de cada lado) — é a unidade de anotação do guia.
RESUMO.csv: contagens por empresa-ano-camada e total de palavras do formulário,
para calcular intensidade (menções por mil palavras).
"""
import csv
import json
import re
import sys
from collections import Counter, defaultdict

from dicionario import EXCLUSOES, IA, IA_GEN, SECOES_SEM_SIGLA_AI, VIZINHOS


def compilar(lista):
    return [re.compile(p, re.IGNORECASE) for p in lista]


CAMADAS = {"ia_gen": compilar(IA_GEN), "ia": compilar(IA), "vizinhos": compilar(VIZINHOS)}
RE_EXCLUSOES = [re.compile(p) for p in EXCLUSOES]
RE_FRASE = re.compile(r"(?<=[.!?;])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9•(\-])")


def frases(texto):
    return [f for f in RE_FRASE.split(texto) if f.strip()]


def excluida(frase, m):
    """True se a ocorrência cai num contexto de EXCLUSOES (sigla que não é IA)."""
    ini, fim = max(0, m.start() - 40), min(len(frase), m.end() + 20)
    for rx in RE_EXCLUSOES:
        for e in rx.finditer(frase, ini, fim):
            if e.start() <= m.start() and m.end() <= e.end():
                return True
    return False


# ligaduras que alguns PDFs usam no lugar das letras ("arƟﬁcial" = "artificial")
LIGADURAS = str.maketrans({"Ɵ": "ti", "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "ft", "ﬆ": "st"})
RE_LIXO = re.compile(r"[!\"#$%&*+<=>?@\[\\\]^{|}~\t]")


def lixo(frase, m):
    """True se a sigla está no meio de texto corrompido (fonte sem mapa de caracteres no PDF)."""
    return len(RE_LIXO.findall(frase, max(0, m.start() - 30), m.end() + 30)) >= 4


def main(entrada, saida_mencoes, saida_resumo):
    palavras = Counter()
    resumo = defaultdict(Counter)
    vistos = set()
    with open(entrada, encoding="utf-8") as f, open(saida_mencoes, "w", newline="", encoding="utf-8") as out:
        w = csv.writer(out)
        w.writerow(["cd_cvm", "empresa", "ano", "versao", "secao", "titulo_secao", "pagina",
                    "camada", "termo", "trecho"])
        for linha in f:
            p = json.loads(linha)
            p["texto"] = p["texto"].replace("\x00", "").translate(LIGADURAS)  # NUL e ligaduras dos PDFs
            chave = (p["cd_cvm"], p["empresa"], p["ano"])
            palavras[chave] += len(p["texto"].split())
            fs = frases(p["texto"])
            for i, fr in enumerate(fs):
                ocupados = []  # trechos já contados como IA generativa ou IA nesta frase
                for camada, padroes in CAMADAS.items():
                    for rx in padroes:
                        for m in rx.finditer(fr):
                            # IA generativa também conta como IA (abaixo); um termo de IA
                            # contido num termo já contado (ex.: "IA" em "IA generativa")
                            # não é contado de novo
                            if camada in ("ia_gen", "ia"):
                                if excluida(fr, m) or (m.group(0) in ("AI", "IA") and lixo(fr, m)):
                                    continue
                                if m.group(0) == "AI" and p["secao"] in SECOES_SEM_SIGLA_AI:
                                    continue
                                if any(a <= m.start() and m.end() <= b for a, b in ocupados):
                                    continue
                                ocupados.append((m.start(), m.end()))
                            # nos ZIPs da CVM a página recomeça em cada seção
                            id_ = (chave, p["secao"], p["pagina"], i, camada, m.start())
                            if id_ in vistos:
                                continue
                            vistos.add(id_)
                            trecho = " ".join(fs[max(i - 1, 0): i + 2])
                            w.writerow([p["cd_cvm"], p["empresa"], p["ano"], p["versao"], p["secao"],
                                        p["titulo_secao"], p["pagina"], camada,
                                        m.group(0), trecho])
                            resumo[chave][camada] += 1
                            if camada == "ia_gen":
                                resumo[chave]["ia"] += 1
    with open(saida_resumo, "w", newline="", encoding="utf-8") as out:
        w = csv.writer(out)
        w.writerow(["cd_cvm", "empresa", "ano", "palavras", "mencoes_ia", "mencoes_ia_gen",
                    "mencoes_vizinhos", "ia_por_mil_palavras"])
        for chave, n in sorted(palavras.items()):
            c = resumo[chave]
            w.writerow([*chave, n, c["ia"], c["ia_gen"], c["vizinhos"],
                        round(1000 * c["ia"] / n, 3) if n else 0])
    print(f"{len(palavras)} formulários; menções gravadas em {saida_mencoes}; resumo em {saida_resumo}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
