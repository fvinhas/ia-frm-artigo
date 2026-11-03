"""Etapa 2 — extrai o texto de cada Formulário de Referência por seção.

Aceita dois formatos na mesma pasta:
  * .zip baixado da CVM (formato principal): contém o formulário em XML, com
    cada seção narrativa como um PDF embutido em base64. A seção é identificada
    pela tag do XML (ver secoes_fre.py), não pelo nome do arquivo.
  * .pdf do formulário completo (ex.: baixado no site de RI da empresa): a
    seção é identificada pelo rodapé de cada página ("4.1 ... / PÁGINA: n de m").

Uso:
    python extrair_secoes.py PASTA SAIDA.jsonl

Saída: um JSON por linha com
    arquivo, cd_cvm, empresa, cnpj, ano, versao, secao, titulo_secao, pagina, texto
(para os ZIPs, "pagina" é a página dentro do PDF da seção)
"""
import base64
import html
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import pymupdf  # pip install pymupdf

from secoes_fre import OUTRAS_POR_CAPITULO, TAG_SECAO

# ---------------------------------------------------------------- ZIP / XML ---

# alguns formulários (ex.: Rede Energia 2025 v10) não trazem <NomeArquivoPdf>
RE_BLOCO = re.compile(
    r"<(\w+)>\s*(?:<NomeArquivoPdf>(.*?)</NomeArquivoPdf>\s*)?"
    r"<ImagemObjetoArquivoPdf>(.*?)</ImagemObjetoArquivoPdf>",
    re.S,
)


def campo(xml, tag):
    m = re.search(rf"<{tag}>(.*?)</{tag}>", xml, re.S)
    return html.unescape(m.group(1).strip()) if m else None


def ler_xml_do_zip(caminho):
    with zipfile.ZipFile(caminho) as z:
        nomes = [n for n in z.namelist() if n.lower().endswith(".xml") and "FRE" in n.upper()]
        if not nomes:
            nomes = [n for n in z.namelist() if n.lower().endswith(".xml")
                     and "cadastral" not in n.lower()]
        bruto = z.read(max(nomes, key=lambda n: z.getinfo(n).file_size))
    # o XML se declara utf-8, mas o texto livre costuma vir em windows-1252
    try:
        return bruto.decode("utf-8")
    except UnicodeDecodeError:
        return bruto.decode("cp1252", errors="replace")


def texto_pdf(dados):
    with pymupdf.open(stream=dados, filetype="pdf") as doc:
        return [p.get_text() for p in doc]


RE_ANEXO = re.compile(
    r"<NumeroQuadroRelacionado>(\d+)</NumeroQuadroRelacionado>.*?"
    r"<NumeroGrupoRelacionado>(\d+)</NumeroGrupoRelacionado>.*?"
    r"<ImagemObjetoArquivoPdf>(.*?)</ImagemObjetoArquivoPdf>",
    re.S,
)


def extrair_zip_antigo(caminho, z, fre):
    """Formato antigo do Empresas.NET (até 2022, e alguns envios de 2023 em diante).

    O ZIP traz um .fre (outro ZIP) com AnexoDocumento.xml; cada seção é identificada
    por grupo e quadro numéricos, na numeração antiga do FRE (22 seções). Sem um mapa
    entre as duas numerações, a seção fica como "antigo:G<grupo>.Q<quadro>".
    """
    cad = z.read("FormularioReferencia.xml").decode("cp1252", errors="replace")
    data_ref = campo(cad, "DataReferenciaDocumento") or ""
    meta = {
        "arquivo": Path(caminho).name,
        "cd_cvm": (campo(cad, "CodigoCvm") or "").replace("-", "").zfill(6),
        "empresa": campo(cad, "NomeRazaoSocialCompanhiaAberta"),
        "cnpj": re.sub(r"\D", "", campo(cad, "NumeroCnpjCompanhiaAberta") or ""),
        "ano": data_ref[:4] or None,
        "versao": None,
    }
    with zipfile.ZipFile(io.BytesIO(z.read(fre))) as interno:
        anexos = interno.read("AnexoDocumento.xml").decode("utf-8", errors="replace")
    for quadro, grupo, b64 in RE_ANEXO.findall(anexos):
        secao = f"antigo:G{grupo}.Q{quadro}"
        try:
            paginas = texto_pdf(base64.b64decode(b64))
        except Exception as e:
            print(f"[aviso] {meta['arquivo']} seção {secao}: PDF ilegível ({e})", file=sys.stderr)
            continue
        for i, t in enumerate(paginas, 1):
            yield {**meta, "secao": secao, "titulo_secao": "", "pagina": i,
                   "texto": " ".join(l.strip() for l in t.split("\n") if l.strip())}


def extrair_zip(caminho):
    with zipfile.ZipFile(caminho) as z:
        fre = [n for n in z.namelist() if n.lower().endswith(".fre")]
        if fre:
            yield from extrair_zip_antigo(caminho, z, fre[0])
            return
    xml = ler_xml_do_zip(caminho)
    data_ref = campo(xml, "DataReferencia") or ""
    meta = {
        "arquivo": Path(caminho).name,
        "cd_cvm": campo(xml, "CodigoCvm"),
        "empresa": campo(xml, "RazaoSocialEmpresa"),
        "cnpj": campo(xml, "CnpjEmpresa"),
        "ano": data_ref[-4:] or None,
        "versao": campo(xml, "VersaoDocumento"),
    }
    capitulo = "1"
    for tag, _nome, b64 in RE_BLOCO.findall(xml):
        if tag in TAG_SECAO:
            secao, titulo = TAG_SECAO[tag]
        elif tag == "OutrasInfRelev":
            secao = OUTRAS_POR_CAPITULO.get(capitulo, f"{capitulo}.?")
            titulo = "Outras informações relevantes"
        else:
            secao, titulo = "?", tag  # tag nova: registrar e revisar o mapa
        capitulo = secao.split(".")[0]
        if not b64.strip():
            continue
        try:
            paginas = texto_pdf(base64.b64decode(b64))
        except Exception as e:
            print(f"[aviso] {meta['arquivo']} seção {secao}: PDF ilegível ({e})", file=sys.stderr)
            continue
        for i, t in enumerate(paginas, 1):
            yield {**meta, "secao": secao, "titulo_secao": titulo, "pagina": i,
                   "texto": " ".join(l.strip() for l in t.split("\n") if l.strip())}


# ------------------------------------------------------------ PDF completo ---

RE_PAGINA = re.compile(r"^P[ÁA]GINA:\s*\d+\s+de\s+\d+\s*$")
RE_SECAO = re.compile(r"^\s*(\d{1,2}\.\d{1,2})(?:\s*/\s*\d{1,2}\.\d{1,2})?\s+(.+?)\s*$")
RE_CAB = re.compile(r"Formul[áa]rio de Refer[êe]ncia\s*-\s*(\d{4})\s*-\s*(.+?)\s*(?:Vers[ãa]o\s*:\s*(\d+))?\s*$")


def extrair_pdf(caminho):
    doc = pymupdf.open(caminho)
    meta = {"arquivo": Path(caminho).name, "cd_cvm": None, "empresa": None,
            "cnpj": None, "ano": None, "versao": None}
    paginas = []
    for i, page in enumerate(doc):
        linhas = page.get_text().split("\n")
        secao = titulo = None
        for j in range(len(linhas) - 1, -1, -1):
            if RE_PAGINA.match(linhas[j].strip()):
                for k in range(j - 1, max(j - 4, -1), -1):
                    m = RE_SECAO.match(linhas[k])
                    if m:
                        secao, titulo = m.group(1), m.group(2)
                        break
                break
        m = RE_CAB.search(" ".join(l.strip() for l in linhas[-4:]))
        if m and not meta["empresa"]:
            meta["ano"], meta["empresa"], meta["versao"] = m.group(1), m.group(2).strip(), m.group(3)
        if secao is None:
            continue  # capa, índice ou página sem rodapé padrão
        corpo = [l.strip() for l in linhas if l.strip()
                 and not RE_PAGINA.match(l.strip())
                 and not l.strip().startswith(("Formulário de Referência -", "Versão :"))]
        if corpo and corpo[-1].startswith(secao) and RE_SECAO.match(corpo[-1]):
            corpo = corpo[:-1]
        paginas.append({**meta, "secao": secao, "titulo_secao": titulo,
                        "pagina": i + 1, "texto": " ".join(corpo)})
    for p in paginas:
        for k in ("empresa", "ano", "versao"):
            p[k] = p[k] or meta[k]
    return paginas


# ------------------------------------------------------------------- main ---

def main(pasta, saida):
    arquivos = sorted(p for p in Path(pasta).iterdir() if p.suffix.lower() in (".zip", ".pdf"))
    n_doc = n_pag = 0
    with open(saida, "w", encoding="utf-8") as f:
        for arq in arquivos:
            try:
                linhas = extrair_zip(arq) if arq.suffix.lower() == ".zip" else extrair_pdf(arq)
                k = 0
                for p in linhas:
                    f.write(json.dumps(p, ensure_ascii=False) + "\n")
                    k += 1
                n_pag += k
                n_doc += 1 if k else 0
                if not k:
                    print(f"[aviso] {arq.name}: nenhuma seção extraída", file=sys.stderr)
            except Exception as e:
                print(f"[erro] {arq.name}: {e}", file=sys.stderr)
    print(f"{n_doc}/{len(arquivos)} formulários, {n_pag} páginas -> {saida}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
