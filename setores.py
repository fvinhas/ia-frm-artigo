"""Agrupa o SETOR_ATIV do cadastro da CVM (cad_cia_aberta.csv) em macrossetores.

O cadastro tem ~35 setores, e as holdings aparecem à parte como
"Emp. Adm. Part. - <setor>". Aqui a holding vai para o setor que ela controla;
só "Emp. Adm. Part. - Sem Setor Principal" fica como holding.

Cadastro: https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv
"""
import csv

MACRO = {
    "Bancos": "Financeiro",
    "Intermediação Financeira": "Financeiro",
    "Seguradoras e Corretoras": "Financeiro",
    "Arrendamento Mercantil": "Financeiro",
    "Crédito Imobiliário": "Financeiro",
    "Bolsas de Valores/Mercadorias e Futuros": "Financeiro",
    "Securitização de Recebíveis": "Securitização",
    "Energia Elétrica": "Energia e saneamento",
    "Saneamento, Serv. Água e Gás": "Energia e saneamento",
    "Serviços Transporte e Logística": "Transporte e logística",
    "Comércio (Atacado e Varejo)": "Comércio",
    "Construção Civil, Mat. Constr. e Decoração": "Construção e imobiliário",
    "Const. Civil, Mat. Const. e Decoração": "Construção e imobiliário",
    "Metalurgia e Siderurgia": "Indústria",
    "Máquinas, Equipamentos, Veículos e Peças": "Indústria",
    "Máqs., Equip., Veíc. e Peças": "Indústria",
    "Têxtil e Vestuário": "Indústria",
    "Petroquímicos e Borracha": "Indústria",
    "Papel e Celulose": "Indústria",
    "Embalagens": "Indústria",
    "Petróleo e Gás": "Petróleo, gás e mineração",
    "Extração Mineral": "Petróleo, gás e mineração",
    "Agricultura (Açúcar, Álcool e Cana)": "Agro e alimentos",
    "Alimentos": "Agro e alimentos",
    "Bebidas e Fumo": "Agro e alimentos",
    "Reflorestamento": "Agro e alimentos",
    "Serviços Médicos": "Saúde",
    "Serviços médicos": "Saúde",
    "Farmacêutico e Higiene": "Saúde",
    "Telecomunicações": "Telecom e TI",
    "Comunicação e Informática": "Telecom e TI",
    "Educação": "Educação, turismo e lazer",
    "Hospedagem e Turismo": "Educação, turismo e lazer",
    "Brinquedos e Lazer": "Educação, turismo e lazer",
    "Sem Setor Principal": "Holding sem setor principal",
}


def macrossetor(setor_ativ):
    s = (setor_ativ or "").replace("Emp. Adm. Part. - ", "").strip()
    return MACRO.get(s, "Não classificado")


def carregar_cadastro(caminho):
    """CD_CVM (sem zeros à esquerda) -> (setor original, macrossetor)."""
    setores = {}
    with open(caminho, encoding="latin1", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            cd = r["CD_CVM"].lstrip("0")
            if r["SETOR_ATIV"] or cd not in setores:
                setores[cd] = (r["SETOR_ATIV"], macrossetor(r["SETOR_ATIV"]))
    return setores
