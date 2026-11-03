"""Etapa 9 — figuras e tabelas do artigo da H2D (recorte 2023–2026, classificador v3).

Uso:
    python figuras_tabelas_h2d.py PASTA_DADOS SAIDA_DIR

Lê de PASTA_DADOS: resumo_AAAA.csv, secoes_AAAA.jsonl (só conta linhas), cad_cia_aberta.csv e,
em anotacao/, populacao_v1.csv, classificacoes_llm_v3.csv e validacao_v3.csv.

Grava em SAIDA_DIR:
  fig1_citam_ia.png/.svg        % das companhias que citam IA e IA generativa, por ano
  fig2_funcoes_empresas.png/.svg  % das companhias com ao menos um trecho de cada função (pequenos múltiplos)
  fig3_secao_funcao.png/.svg    função dos trechos por grupo de seção (mapa de calor, 2023–2026)
  fig4_setores.png/.svg         % das companhias que citam IA por macrossetor, 2023 e 2026
  dados_figuras.xlsx            os números de cada figura (uma aba por figura)
  tabelas_h2d.docx              tabelas no padrão da revista (legenda acima, só linhas horizontais)

Unidade: trechos únicos (frase ± 1) sem os falsos positivos do v3; "companhia cita IA" = ao menos
um trecho válido. Denominador das % de companhias: as que entregaram FRE no ano.
"""
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from setores import carregar_cadastro

ANOS = ["2023", "2024", "2025", "2026"]
FUNCOES = [("RISCO", "Risco"), ("USO", "Uso"), ("PROD", "Produtividade"), ("NEGOCIO", "Negócio"),
           ("GENERICA", "Contextual"), ("GOV", "Governança")]  # código GENERICA = função "contextual" no artigo
NOME = dict(FUNCOES)
GRUPOS = [("1 atividades", "1 Atividades"), ("2.10 planos de negócios", "2.10 Planos de negócios"),
          ("2-3 resultados e projeções", "2–3 Resultados e projeções"), ("4 riscos", "4 Fatores de risco"),
          ("5 controles e integridade", "5 Controles e integridade"),
          ("6-13 administração, RH e outros", "6–13 Administração, RH e outros")]
MAPA_ANTIGO = {"antigo:G828.": "1 atividades"}  # seção 7 antiga = atividades (ver analise_v3.py)

# paleta de referência (dataviz): azul e laranja para as duas séries; azul sequencial no mapa de calor
AZUL, LARANJA, CINZA, TINTA, TINTA2 = "#2a78d6", "#eb6834", "#c9c8c3", "#0b0b0b", "#52514e"
SEQ = ["#ffffff", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

plt.rcParams.update({
    "font.family": "Arial", "font.size": 9, "axes.edgecolor": CINZA, "axes.labelcolor": TINTA2,
    "xtick.color": TINTA2, "ytick.color": TINTA2, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#e6e5e1", "grid.linewidth": 0.6, "axes.axisbelow": True,
    "svg.fonttype": "none",
})

sim = lambda v: str(v).strip().lower() in ("sim", "true")
br = lambda x, d=1: f"{x:.{d}f}".replace(".", ",")


def carregar(pasta):
    pasta = Path(pasta)
    an = pasta / "anotacao"
    modelo = {r["id_trecho"]: r for r in csv.DictReader(open(an / "classificacoes_llm_v3.csv", encoding="utf-8"))}
    pop = []
    for t in csv.DictReader(open(an / "populacao_v1.csv", encoding="utf-8-sig")):
        t.update({k: modelo[t["id_trecho"]][k] for k in ("falso_positivo", "funcao", "evidencia", "governanca", "tom", "tempo")})
        for prefixo, g in MAPA_ANTIGO.items():
            if t["secao"].startswith(prefixo):
                t["grupo_secao"] = g
        pop.append(t)
    entregaram = {a: {r["cd_cvm"].lstrip("0") for r in csv.DictReader(open(pasta / f"resumo_{a}.csv", encoding="utf-8"))}
                  for a in ANOS}
    paginas = {a: sum(1 for _ in open(pasta / f"secoes_{a}.jsonl", encoding="utf-8")) for a in ANOS}
    setores = carregar_cadastro(pasta / "cad_cia_aberta.csv")
    validacao = list(csv.DictReader(open(an / "validacao_v3.csv", encoding="utf-8")))
    return pop, entregaram, paginas, setores, validacao


def salvar(fig, saida, nome):
    for ext in ("png", "svg"):
        fig.savefig(saida / f"{nome}.{ext}", dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def fig1(ok, entregaram, saida):
    linhas = []
    for a in ANOS:
        ts = [t for t in ok if t["ano"] == a]
        ia = {t["cd_cvm"] for t in ts}
        gen = {t["cd_cvm"] for t in ts if sim(t["ia_gen"])}
        n = len(entregaram[a])
        linhas.append({"ano": a, "companhias_fre": n, "citam_ia": len(ia), "citam_ia_pct": round(100 * len(ia) / n, 1),
                       "citam_ia_gen": len(gen), "citam_ia_gen_pct": round(100 * len(gen) / n, 1)})
    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    x = range(len(ANOS))
    for chave, cor, estilo, rotulo in (("citam_ia_pct", AZUL, "-", "Inteligência artificial (qualquer termo)"),
                                       ("citam_ia_gen_pct", LARANJA, "--", "IA generativa")):
        y = [l[chave] for l in linhas]
        ax.plot(x, y, color=cor, lw=2, ls=estilo, marker="o", ms=5, markeredgecolor="white", markeredgewidth=1)
        ax.annotate(f"{br(y[-1])}%", (x[-1], y[-1]), xytext=(6, 0), textcoords="offset points", va="center", color=TINTA, fontsize=8.5)
        ax.annotate(f"{br(y[0])}%", (x[0], y[0]), xytext=(-6, 0), textcoords="offset points", va="center", ha="right", color=TINTA, fontsize=8.5)
        ax.annotate(rotulo, (0.5, (y[0] + y[1]) / 2), xytext=(0, 12), textcoords="offset points", ha="center", color=TINTA2, fontsize=8.5)
    ax.set_xticks(list(x), ANOS)
    ax.set_xlim(-0.45, 3.45)
    ax.set_ylim(0, 45)
    ax.set_ylabel("% das companhias que entregaram o FRE")
    ax.grid(axis="x", visible=False)
    salvar(fig, saida, "fig1_citam_ia")
    return linhas


def fig2(ok, entregaram, saida):
    linhas = []
    for cod, nome in FUNCOES:
        for a in ANOS:
            n = len({t["cd_cvm"] for t in ok if t["ano"] == a and t["funcao"] == cod})
            linhas.append({"funcao": nome, "ano": a, "companhias": n, "pct": round(100 * n / len(entregaram[a]), 1)})
    fig, eixos = plt.subplots(2, 3, figsize=(6.3, 3.8), sharex=True, sharey=True)
    for ax, (cod, nome) in zip(eixos.flat, FUNCOES):
        y = [l["pct"] for l in linhas if l["funcao"] == nome]
        ax.plot(range(4), y, color=AZUL, lw=2, marker="o", ms=4.5, markeredgecolor="white", markeredgewidth=1)
        ax.set_title(nome, fontsize=9, color=TINTA, loc="left")
        ax.annotate(f"{br(y[0])}", (0, y[0]), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=7.5, color=TINTA2)
        ax.annotate(f"{br(y[-1])}", (3, y[-1]), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=7.5, color=TINTA)
        ax.set_xticks(range(4), ANOS, fontsize=7)
        ax.set_xlim(-0.4, 3.4)
        ax.set_ylim(0, 24)
        ax.grid(axis="x", visible=False)
    fig.supylabel("% das companhias que entregaram o FRE", fontsize=8.5, color=TINTA2)
    fig.tight_layout()
    salvar(fig, saida, "fig2_funcoes_empresas")
    return linhas


def fig3(ok, saida):
    """Dois painéis, 2023 e 2026: a mudança no tempo fica visível (pedido da revisão), com legenda de cor."""
    from matplotlib.colors import BoundaryNorm, ListedColormap
    norm = BoundaryNorm([0, 1, 5, 10, 20, 35, 50, 75, 100.01], len(SEQ))
    cmap = ListedColormap(SEQ)
    linhas = []
    fig, eixos = plt.subplots(1, 2, figsize=(7.4, 3.3), sharey=True)
    for k, (ax, ano) in enumerate(zip(eixos, ("2023", "2026"))):
        matriz, ns = [], []
        for g, rotulo in GRUPOS:
            ts = [t for t in ok if t["grupo_secao"] == g and t["ano"] == ano]
            c = Counter(t["funcao"] for t in ts)
            linha = [100 * c[cod] / len(ts) if ts else float("nan") for cod, _ in FUNCOES]
            matriz.append(linha)
            ns.append(len(ts))
            linhas.append({"ano": ano, "grupo_secao": rotulo, "trechos": len(ts),
                           **{nome: round(v, 1) if ts else "" for (_, nome), v in zip(FUNCOES, linha)}})
        im = ax.imshow(matriz, cmap=cmap, norm=norm, aspect="auto")
        for i, linha in enumerate(matriz):
            for j, v in enumerate(linha):
                if ns[i] and v >= 0.5:
                    ax.text(j, i, br(v, 0), ha="center", va="center", fontsize=7.5, color="white" if v >= 35 else TINTA)
                elif ns[i] and v > 0:  # há trechos, mas arredonda para 0
                    ax.text(j, i, "<1", ha="center", va="center", fontsize=7, color=TINTA)
                elif ns[i]:
                    ax.text(j, i, "0", ha="center", va="center", fontsize=7, color=CINZA)
        ax.set_xticks(range(len(FUNCOES)), ["Risco", "Uso", "Produt.", "Negócio", "Context.", "Govern."], fontsize=7.5, rotation=0)
        ax.set_title(f"{ano}", fontsize=9, color=TINTA, loc="left")
        if k == 0:
            ax.set_yticks(range(len(GRUPOS)), [r for _, r in GRUPOS], fontsize=7.5)
        for i, n in enumerate(ns):
            ax.text(len(FUNCOES) - 0.45, i, f" n={n}", va="center", fontsize=6.5, color=TINTA2)
        ax.tick_params(length=0)
        ax.xaxis.tick_top()
        ax.grid(False)
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.set_xticks([x - 0.5 for x in range(1, len(FUNCOES))], minor=True)
        ax.set_yticks([y - 0.5 for y in range(1, len(GRUPOS))], minor=True)
        ax.grid(which="minor", color="white", linewidth=2)
        ax.tick_params(which="minor", length=0)
        # borda branca também por fora, para as células das pontas terem o mesmo tamanho aparente das internas
        for x in (-0.5, len(FUNCOES) - 0.5):
            ax.axvline(x, color="white", linewidth=2, clip_on=False)
        for y in (-0.5, len(GRUPOS) - 0.5):
            ax.axhline(y, color="white", linewidth=2, clip_on=False)
    cb = fig.colorbar(im, ax=eixos, orientation="horizontal", fraction=0.06, pad=0.06, aspect=40,
                      ticks=[0, 1, 5, 10, 20, 35, 50, 75, 100])
    cb.ax.tick_params(labelsize=7, length=0)
    cb.set_label("% dos trechos do grupo de seção (cada linha soma 100); 0 = nenhum trecho; <1 = menos de 1%",
                 fontsize=7.5, color=TINTA2)
    cb.outline.set_visible(False)
    salvar(fig, saida, "fig3_secao_funcao")
    return linhas


def por_setor(ok, entregaram, setores):
    macro = lambda cd: setores.get(cd.lstrip("0"), ("", "Não classificado"))[1]
    linhas = []
    for a in ANOS:
        cias = defaultdict(set)
        for cd in entregaram[a]:
            cias[macro(cd)].add(cd)
        citam = defaultdict(set)
        for t in ok:
            if t["ano"] == a:
                citam[macro(t["cd_cvm"])].add(t["cd_cvm"].lstrip("0"))
        for m, cds in cias.items():
            linhas.append({"macrossetor": m, "ano": a, "companhias": len(cds), "citam_ia": len(citam[m] & cds),
                           "pct": round(100 * len(citam[m] & cds) / len(cds), 1)})
    return linhas


def fig4(setor, saida):
    d = defaultdict(dict)
    for l in setor:
        d[l["macrossetor"]][l["ano"]] = l
    nomes = sorted((m for m in d if m != "Não classificado"), key=lambda m: d[m]["2026"]["pct"])
    fig, ax = plt.subplots(figsize=(6.0, 4.0))
    for i, m in enumerate(nomes):
        a, b = d[m]["2023"]["pct"], d[m]["2026"]["pct"]
        ax.plot([a, b], [i, i], color=CINZA, lw=2, zorder=1)
        ax.scatter([b], [i], s=40, color=AZUL, edgecolor="white", linewidth=1, zorder=3)
        # 2023 por cima, vazado e maior, para continuar visível quando os dois valores coincidem
        ax.scatter([a], [i], s=60, facecolor="none", edgecolor=AZUL, linewidth=1.4, zorder=4)
        ax.annotate(br(b, 0), (max(a, b), i), xytext=(8, 0), textcoords="offset points", va="center", fontsize=7.5, color=TINTA)
        if abs(a - b) >= 4:
            ax.annotate(br(a, 0), (min(a, b), i), xytext=(-8, 0), textcoords="offset points", va="center", ha="right",
                        fontsize=7, color=TINTA2)
    ax.set_yticks(range(len(nomes)), [f"{m} ({d[m]['2023']['companhias']}/{d[m]['2026']['companhias']})" for m in nomes])
    ax.set_xlim(0, 80)
    ax.set_xlabel("% das companhias que citam IA (entre parênteses: companhias em 2023/2026)")
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    ax.scatter([], [], s=60, facecolor="none", edgecolor=AZUL, linewidth=1.4, label="2023")
    ax.scatter([], [], s=40, color=AZUL, label="2026")
    ax.legend(loc="lower right", frameon=False, fontsize=8)
    salvar(fig, saida, "fig4_setores")


# ---------- tabelas (docx) ----------

def borda(celula, lados):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    tcPr = celula._tc.get_or_add_tcPr()
    bordas = OxmlElement("w:tcBorders")
    for lado in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{lado}")
        if lado in lados:
            el.set(qn("w:val"), "single")
            el.set(qn("w:sz"), "8")
            el.set(qn("w:color"), "000000")
        else:
            el.set(qn("w:val"), "nil")
        bordas.append(el)
    tcPr.append(bordas)


def tabela(doc, numero, titulo, cabecalho, linhas, nota=None):
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt
    p = doc.add_paragraph()
    p.add_run(f"Tabela {numero}").bold = True
    p.add_run(f". {titulo}")
    t = doc.add_table(rows=1 + len(linhas), cols=len(cabecalho))
    for i, linha in enumerate([cabecalho] + linhas):
        for j, v in enumerate(linha):
            c = t.cell(i, j)
            c.text = str(v)
            par = c.paragraphs[0]
            par.alignment = WD_ALIGN_PARAGRAPH.LEFT if j == 0 else WD_ALIGN_PARAGRAPH.RIGHT
            for r in par.runs:
                r.font.size = Pt(9)
                r.bold = i == 0
            lados = (["top", "bottom"] if i == 0 else []) + (["bottom"] if i == len(linhas) else [])
            borda(c, lados)
    if nota:
        n = doc.add_paragraph()
        n.add_run(f"Nota. {nota}").font.size = Pt(8)
    doc.add_paragraph()


def tabelas(ok, todos, entregaram, paginas, validacao, setor, emp, saida):
    from docx import Document
    doc = Document()
    doc.add_paragraph("Tabelas do artigo (H2D). Gerado por figuras_tabelas_h2d.py; os números vêm dos "
                      "arquivos em dados/. Ajustar numeração e notas ao texto final.")
    cias = {a: len({t["cd_cvm"] for t in ok if t["ano"] == a}) for a in ANOS}
    tr = {a: sum(t["ano"] == a for t in todos) for a in ANOS}
    fp = {a: sum(t["ano"] == a and sim(t["falso_positivo"]) for t in todos) for a in ANOS}
    val = {a: tr[a] - fp[a] for a in ANOS}
    fmt = lambda n: f"{n:,}".replace(",", ".")
    tabela(doc, 1, "Corpus e trechos analisados, por ano de referência do FRE",
           ["", *ANOS, "Total"],
           [["Formulários (última versão por companhia)", *[fmt(len(entregaram[a])) for a in ANOS], fmt(sum(len(entregaram[a]) for a in ANOS))],
            ["Páginas de texto extraídas", *[fmt(paginas[a]) for a in ANOS], fmt(sum(paginas.values()))],
            ["Trechos com termo de IA", *[fmt(tr[a]) for a in ANOS], fmt(sum(tr.values()))],
            ["Falsos positivos (classificador)", *[fmt(fp[a]) for a in ANOS], fmt(sum(fp.values()))],
            ["Trechos válidos", *[fmt(val[a]) for a in ANOS], fmt(sum(val.values()))],
            ["Companhias com ao menos um trecho válido", *[fmt(cias[a]) for a in ANOS], ""],
            ["% das companhias", *[br(100 * cias[a] / len(entregaram[a])) for a in ANOS], ""]],
           "Trecho = frase com o termo, mais uma frase antes e uma depois; trechos idênticos na mesma "
           "companhia-ano contam uma vez. Índice de 2026 de 25/10/2026.")

    dims = [("funcao", "Função"), ("evidencia", "Evidência"), ("tom", "Tom"), ("tempo", "Tempo"),
            ("governanca", "Governança"), ("falso_positivo", "Falso positivo")]
    v = {(l["amostra"], l["dimensao"]): l for l in validacao}
    tabela(doc, 2, "Concordância entre o classificador (prompt v3) e o padrão-ouro",
           ["Dimensão", "Cegos: acordo (%)", "Cegos: α", "Todos: acordo (%)", "Todos: α"],
           [[nome, br(float(v[("cegos", d)]["acordo_pct"])), br(float(v[("cegos", d)]["alfa"]), 3) if v[("cegos", d)]["alfa"] else "—",
             br(float(v[("todos", d)]["acordo_pct"])), br(float(v[("todos", d)]["alfa"]), 3)] for d, nome in dims],
           f"Cegos: {v[('cegos', 'funcao')]['n']} trechos anotados pelo autor sem ver a saída do modelo. Todos: padrão-ouro "
           f"completo (cegos + trechos verificados pelo autor; n = {v[('todos', 'funcao')]['n']} sem falsos positivos). "
           "α = alfa de Krippendorff nominal. Nenhum falso positivo entre os cegos, por isso sem α.")

    linhas = []
    for cod, nome in FUNCOES:
        pt = [100 * sum(t["funcao"] == cod for t in ok if t["ano"] == a) / val[a] for a in ANOS]
        pc = [next(l["pct"] for l in emp if l["funcao"] == nome and l["ano"] == a) for a in ANOS]
        linhas.append([nome, *[br(x) for x in pt], *[br(x) for x in pc]])
    tabela(doc, 3, "Função da IA nos trechos e nas companhias, por ano",
           ["Função", *[f"Trechos {a}" for a in ANOS], *[f"Cias. {a}" for a in ANOS]], linhas,
           "Trechos: % dos trechos válidos do ano (somam 100). Companhias: % das companhias que entregaram o FRE "
           "com ao menos um trecho da função (não somam 100).")

    linhas = []
    for d, nome, cods in (("evidencia", "Evidência", [("METRICA", "Métrica"), ("CASO", "Caso"), ("SEM", "Sem evidência")]),
                          ("tom", "Tom", [("POS", "Positivo"), ("NEU", "Neutro"), ("NEG", "Negativo")]),
                          ("tempo", "Tempo", [("REALIZADO", "Realizado"), ("EM_CURSO", "Em curso"),
                                              ("PLANEJADO", "Planejado"), ("NA", "Sem referência")])):
        for cod, rot in cods:
            linhas.append([f"{nome}: {rot}", *[br(100 * sum(t[d] == cod for t in ok if t["ano"] == a) / val[a]) for a in ANOS]])
    tabela(doc, 4, "Evidência, tom e tempo dos trechos, por ano (%)", ["", *ANOS], linhas,
           "% dos trechos válidos do ano; cada dimensão soma 100.")

    d = defaultdict(dict)
    for l in setor:
        d[l["macrossetor"]][l["ano"]] = l
    nomes = sorted((m for m in d if m != "Não classificado"), key=lambda m: -d[m]["2026"]["pct"])
    tabela(doc, 5, "Companhias que citam IA, por macrossetor (%)",
           ["Macrossetor", *ANOS, "n (2026)"],
           [[m, *[br(d[m][a]["pct"]) if a in d[m] else "—" for a in ANOS], d[m]["2026"]["companhias"]] for m in nomes],
           "Macrossetor a partir do setor de atividade do cadastro da CVM. Excluídas as companhias sem setor.")
    doc.save(saida / "tabelas_h2d.docx")


def planilha(abas, saida):
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    for nome, linhas in abas.items():
        ws = wb.create_sheet(nome)
        ws.append(list(linhas[0]))
        for l in linhas:
            ws.append(list(l.values()))
    wb.save(saida / "dados_figuras.xlsx")


def main(pasta, saida):
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    todos, entregaram, paginas, setores, validacao = carregar(pasta)
    ok = [t for t in todos if not sim(t["falso_positivo"])]
    f1 = fig1(ok, entregaram, saida)
    f2 = fig2(ok, entregaram, saida)
    f3 = fig3(ok, saida)
    setor = por_setor(ok, entregaram, setores)
    fig4(setor, saida)
    tabelas(ok, todos, entregaram, paginas, validacao, setor, f2, saida)
    planilha({"fig1": f1, "fig2": f2, "fig3": f3, "fig4_tab5": setor}, saida)
    print(f"{len(ok)} trechos válidos; figuras, tabelas e dados em {saida}")
    for l in f1:
        print("  ", l)


if __name__ == "__main__":
    main(*sys.argv[1:3])
