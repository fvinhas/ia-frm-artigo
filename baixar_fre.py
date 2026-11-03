"""Etapa 1 — baixa em lote os Formulários de Referência (PDF) da CVM.

Lê o índice fre_cia_aberta_AAAA.csv (de dados.cvm.gov.br), fica com a versão
mais recente de cada companhia e baixa o documento pelo LINK_DOC.

O link devolve um ZIP com o formulário em XML (cada seção narrativa é um PDF
embutido). Em teste de 27/10/2026, cada documento levou 20 a 50 segundos;
700 companhias levam ~6 horas. Rode primeiro o piloto (--limite 3).

O gargalo é o servidor da CVM (~0,4 MB/s por conexão), não a rede local;
--paralelo baixa vários documentos ao mesmo tempo (padrão 4; não exagere).

Uso:
    python baixar_fre.py fre_cia_aberta_2025.csv pdfs_2025 --limite 3
    python baixar_fre.py fre_cia_aberta_2025.csv pdfs_2025          # todas
    python baixar_fre.py fre_cia_aberta_2023.csv zips_2023_primeira --primeira   # primeiras versões

O script pode ser interrompido e retomado: arquivos já baixados são pulados.
Gera pdfs_2025/_log.csv com o resultado de cada download.
"""
import argparse
import csv
import io
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests  # pip install requests

CABECALHOS = {"User-Agent": "Mozilla/5.0 (pesquisa academica; FRE dados abertos)"}


def versoes_mais_recentes(indice, primeira=False):
    """A versão mais recente de cada companhia; com primeira=True, a primeira versão (análise de
    sensibilidade pedida na revisão), e só das companhias que reapresentaram o formulário (para as
    demais, a primeira é a mais recente e já está baixada)."""
    por_cnpj = {}
    with open(indice, encoding="latin1", newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            por_cnpj.setdefault(row["CNPJ_CIA"], []).append(row)
    escolhidas = []
    for rows in por_cnpj.values():
        rows.sort(key=lambda r: int(r["VERSAO"] or 0))
        if primeira:
            if len(rows) > 1:
                escolhidas.append(rows[0])
        else:
            escolhidas.append(rows[-1])
    return sorted(escolhidas, key=lambda r: r["CD_CVM"])


def gravar(destino, conteudo):
    # grava com nome temporário e renomeia: uma interrupção não deixa arquivo pela metade
    tmp = destino.with_name(destino.name + ".part")
    tmp.write_bytes(conteudo)
    tmp.replace(destino)


def salvar(conteudo, destino_base):
    """A CVM devolve um ZIP com o formulário em XML (seções em PDF embutido).

    Guarda o ZIP como veio; extrair_secoes.py lê esse formato.
    """
    if conteudo[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
            xmls = [n for n in z.namelist() if n.lower().endswith(".xml")]
        gravar(destino_base.with_suffix(".zip"), conteudo)
        return f"zip ok ({len(xmls)} xml)"
    if conteudo[:4] == b"%PDF":
        gravar(destino_base.with_suffix(".pdf"), conteudo)
        return "pdf"
    gravar(destino_base.with_suffix(".bin"), conteudo)
    return f"formato desconhecido ({conteudo[:8]!r})"


def baixar(r, base, a):
    url = r["LINK_DOC"].replace("http://", "https://")
    t0 = time.time()
    resultado = "falhou"
    for tent in range(1, a.tentativas + 1):
        try:
            resp = requests.get(url, headers=CABECALHOS, timeout=a.timeout)
            resp.raise_for_status()
            resultado = salvar(resp.content, base)
            break
        except Exception as e:
            resultado = f"erro na tentativa {tent}: {e.__class__.__name__}"
            time.sleep(10 * tent)
    time.sleep(a.pausa)
    return resultado, round(time.time() - t0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("indice")
    ap.add_argument("pasta")
    ap.add_argument("--limite", type=int, default=0, help="baixa só as N primeiras (piloto)")
    ap.add_argument("--timeout", type=int, default=600, help="segundos por documento")
    ap.add_argument("--tentativas", type=int, default=3)
    ap.add_argument("--pausa", type=float, default=3.0, help="segundos entre downloads")
    ap.add_argument("--paralelo", type=int, default=4, help="downloads simultâneos")
    ap.add_argument("--primeira", action="store_true", help="primeira versão das companhias que reapresentaram")
    a = ap.parse_args()

    pasta = Path(a.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    linhas = versoes_mais_recentes(a.indice, a.primeira)
    if a.limite:
        linhas = linhas[: a.limite]
    log_path = pasta / "_log.csv"
    novo = not log_path.exists()
    pendentes = []
    for r in linhas:
        base = pasta / f"{r['CD_CVM']}_{r['DT_REFER'][:4]}_v{r['VERSAO']}"
        if not (base.with_suffix(".zip").exists() or base.with_suffix(".pdf").exists()):
            pendentes.append((r, base))
    print(f"{len(linhas) - len(pendentes)} já baixados, {len(pendentes)} pendentes", flush=True)
    trava = threading.Lock()
    feitos = [0]
    with open(log_path, "a", newline="", encoding="utf-8") as log:
        w = csv.writer(log)
        if novo:
            w.writerow(["cd_cvm", "cnpj", "empresa", "versao", "id_doc", "resultado", "segundos"])

        def tarefa(item):
            r, base = item
            resultado, seg = baixar(r, base, a)
            with trava:
                w.writerow([r["CD_CVM"], r["CNPJ_CIA"], r["DENOM_CIA"], r["VERSAO"], r["ID_DOC"], resultado, seg])
                log.flush()
                feitos[0] += 1
                print(f"[{feitos[0]}/{len(pendentes)}] {r['DENOM_CIA'][:40]:40} {resultado} ({seg}s)", flush=True)

        with ThreadPoolExecutor(max_workers=a.paralelo) as ex:
            list(ex.map(tarefa, pendentes))


if __name__ == "__main__":
    main()
