"""Etapa 10 — monta dados_publicos/, a parte dos dados que vai para o repositório público.

Uso:
    python exportar_publico.py PASTA_DADOS SAIDA_DIR

Não entram (grandes ou refeitos pelo pipeline a partir da CVM): os ZIPs baixados, os índices
anuais, secoes_AAAA.jsonl e mencoes_AAAA.csv. Também não entram as planilhas de trabalho (.xlsx de
anotação, verificação, revisão do v2 e banco de exemplos).

Dados de administradores: o projeto usa dados de administradores só agregados por companhia. Os
trechos das seções 7 (assembleia e administração), 8 (remuneração) e 13 (declarações dos
diretores) podem citar pessoas pelo nome; neles, o texto do trecho e as justificativas e
comentários que o citam são trocados por OMITIDO, em todos os arquivos (inclusive nos lotes que
o classificador leu). Os códigos ficam. O texto original está no FRE da companhia, no site da CVM.
"""
import csv
import json
import shutil
import sys
from pathlib import Path

ANOS = ["2023", "2024", "2025", "2026"]
SECOES_PRIVADAS = ("7.", "8.", "13.")
OMITIDO = "[omitido: seção sobre administradores; ver o FRE original no site da CVM]"
CAMPOS_TEXTO = ("trecho", "justificativa", "comentario", "h_justificativa", "m_justificativa")

ANOTACAO_CSV = ["populacao_v1.csv", "amostra_v1.csv", "populacao_estratos.csv", "cega_v1_ids.csv",
                "ouro_v1.csv", "adjudicacoes_v1.csv", "divergencias_cega_v1.csv",
                "classificacoes_llm_v1.csv", "classificacoes_llm_v2.csv", "classificacoes_llm_v3.csv"]
RESULTADOS_CSV = ["comparacao_cega_v1.csv", "comparacao_cega_v1_funcao_f1.csv", "comparacao_v2_ouro_v1.csv",
                  "efeito_verificacao_v1.csv", "validacao_v3.csv", "validacao_v3_funcao_f1.csv",
                  "pop_v3_ano.csv", "pop_v3_ano_empresas.csv", "pop_v3_ano_secao.csv", "pop_v3_setor.csv",
                  "indices_empresa_ano_v3.csv", "correcao_v3.csv", "robustez_semsecao.csv", "repeticao_v3.csv", "tipos_risco_v1.csv",
                  "repeticao_base_v3.csv", "rodada2_v3.csv", "tabela_S1_correcao.csv"]
REVISAO_CSV = ["sensibilidade_dicionario.csv", "funcao_por_companhia.csv", "governanca_denominadores.csv",
               "marcadores_textuais.csv", "versoes_fre.csv", "mapa_grupos.csv", "contagem_grupos.csv",
               "sensibilidade_versao.csv", "populacao_primeira_versao_ids.csv"]
DUPLA_CSV = ["cega_v2_ids.csv", "tipos_risco_v2_ids.csv", "anotacoes_v2.csv", "consenso_v2.csv", "concordancia_v2.csv",
             "f1_v2.csv", "tipos_risco_v2.csv", "concordancia_consenso_v2.csv", "f1_consenso_v2.csv"]
H2D = ["fig1_citam_ia", "fig2_funcoes_empresas", "fig3_secao_funcao", "fig4_setores"]


def privada(secao):
    return secao.startswith(SECOES_PRIVADAS)


def copiar_csv(origem, destino, ids_privados):
    with open(origem, encoding="utf-8-sig", newline="") as f:
        leitor = csv.DictReader(f)
        campos, linhas = leitor.fieldnames, list(leitor)
    n = 0
    for l in linhas:
        if l.get("id_trecho") in ids_privados:
            for c in CAMPOS_TEXTO:
                if l.get(c):
                    l[c] = OMITIDO
            n += 1
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)
    return n


def copiar_jsonl(origem, destino, ids_privados):
    destino.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(origem, encoding="utf-8") as f, open(destino, "w", encoding="utf-8") as g:
        for linha in f:
            if not linha.strip():
                continue
            r = json.loads(linha)
            if r.get("id_trecho") in ids_privados:
                for c in CAMPOS_TEXTO:
                    if r.get(c):
                        r[c] = OMITIDO
                n += 1
            g.write(json.dumps(r, ensure_ascii=False) + "\n")
    return n


def main(pasta, saida):
    pasta, saida = Path(pasta), Path(saida)
    licenca = (saida / "LICENCA.md").read_text(encoding="utf-8") if (saida / "LICENCA.md").exists() else None
    if saida.exists():
        shutil.rmtree(saida)
    if licenca:
        saida.mkdir(parents=True)
        (saida / "LICENCA.md").write_text(licenca, encoding="utf-8")
    an = pasta / "anotacao"
    ids_privados = {t["id_trecho"] for t in csv.DictReader(open(an / "populacao_v1.csv", encoding="utf-8-sig"))
                    if privada(t["secao"])}
    ids_privados |= {t["id_trecho"] for t in csv.DictReader(open(an / "amostra_v1.csv", encoding="utf-8-sig"))
                     if privada(t["secao"])}
    # trechos que só existem na primeira versão do FRE (sensibilidade_versao.py) ficam fora da população
    ids_privados |= {t["id_trecho"] for t in csv.DictReader(open(an / "complementares" / "populacao_primeira_versao_ids.csv",
                                                                 encoding="utf-8-sig"))
                     if privada(t["secao"])}

    omitidos = 0
    for a in ANOS:
        (saida / "corpus").mkdir(parents=True, exist_ok=True)
        shutil.copy(pasta / f"resumo_{a}.csv", saida / "corpus" / f"resumo_{a}.csv")
    for nome in ANOTACAO_CSV:
        omitidos += copiar_csv(an / nome, saida / "anotacao" / nome, ids_privados)
    for nome in RESULTADOS_CSV:
        omitidos += copiar_csv(an / nome, saida / "resultados" / nome, ids_privados)
    for nome in DUPLA_CSV:
        omitidos += copiar_csv(an / "dupla_v2" / nome, saida / "anotacao" / "dupla_v2" / nome, ids_privados)
    for nome in REVISAO_CSV:
        omitidos += copiar_csv(an / "complementares" / nome, saida / "resultados" / "complementares" / nome, ids_privados)
    copiar_csv(an / "revocacao" / "variantes_resumo_v1.csv", saida / "resultados" / "revocacao_variantes_resumo.csv", ids_privados)
    copiar_csv(an / "revocacao" / "leituras_resumo_v1.csv", saida / "resultados" / "revocacao_leituras_resumo.csv", ids_privados)
    for versao in ("llm_v1", "llm_v2", "llm_v3", "llm_v3_rodada2", "llm_v3_primeira", "llm_semsecao", "llm_risco"):
        for arq in sorted((an / versao).glob("*.jsonl")):
            omitidos += copiar_jsonl(arq, saida / "anotacao" / versao / arq.name, ids_privados)
    (saida / "h2d").mkdir(parents=True, exist_ok=True)
    for nome in H2D:
        for ext in ("png", "svg"):
            shutil.copy(pasta / "h2d" / f"{nome}.{ext}", saida / "h2d")
    shutil.copy(pasta / "h2d" / "dados_figuras.xlsx", saida / "h2d")

    tamanho = sum(p.stat().st_size for p in saida.rglob("*") if p.is_file())
    print(f"{len(ids_privados)} trechos de seções de administradores; {omitidos} linhas com texto omitido; "
          f"{sum(1 for p in saida.rglob('*') if p.is_file())} arquivos, {tamanho / 1e6:.1f} MB -> {saida}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
