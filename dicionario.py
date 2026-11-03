"""Dicionário de termos para detectar menções a IA nos Formulários de Referência.

Três camadas:
  - "ia":        menções explícitas a inteligência artificial e técnicas associadas
  - "ia_gen":    subconjunto de IA generativa / modelos de linguagem
  - "vizinhos":  termos de eficiência tecnológica que NÃO nomeiam IA
                 (para medir a "fala de eficiência" separada da "fala de IA")

Cada entrada é uma expressão regular, aplicada sem diferenciar maiúsculas,
exceto as marcadas com (?-i), que exigem a grafia exata (siglas).
"""

IA = [
    r"intelig[êe]ncia\s+artificial",
    r"artificial\s+intelligence",
    r"(?-i:\bIA\b)",            # sigla em maiúsculas; filtrar falsos positivos na revisão
    r"(?-i:\bAI\b)",
    r"aprendizado\s+de\s+m[áa]quina",
    r"aprendizagem\s+de\s+m[áa]quina",
    r"machine\s+learning",
    r"deep\s+learning",
    r"aprendizado\s+profundo",
    r"redes?\s+neura(?:l|is)",
    r"vis[ãa]o\s+computacional",
    r"processamento\s+de\s+linguagem\s+natural",
    r"(?-i:\bPLN\b)",
    r"(?-i:\bNLP\b)",
    r"agentes?\s+de\s+IA",
    r"agentes?\s+inteligentes?",
]

IA_GEN = [
    r"IA\s+generativa",
    r"intelig[êe]ncia\s+artificial\s+generativa",
    r"generative\s+AI",
    r"\bGenAI\b",
    r"modelos?\s+de\s+linguagem",
    r"large\s+language\s+models?",
    r"(?-i:\bLLMs?\b)",
    r"ChatGPT",
    r"\bCopilot\b",
    r"Google\s+Gemini",       # "Gemini" sozinho é nome de empresa (Gemini Energy, Gemini Even)
    r"\bOpenAI\b",
]

VIZINHOS = [
    r"automa[çc][ãa]o",
    r"automatiza[çc][ãa]o",
    r"\bRPA\b",
    r"rob[ôo]s?\b",
    r"analytics",
    r"ci[êe]ncia\s+de\s+dados",
    r"\bbig\s+data\b",
    r"algoritmos?",
    r"transforma[çc][ãa]o\s+digital",
    r"digitaliza[çc][ãa]o",
    r"produtividade",
    r"efici[êe]ncia\s+operacional",
    # sem nomear IA, chatbot, assistente virtual e modelo preditivo não são IA: os dois anotadores da
    # anotação dupla v2 os marcaram como falso positivo; decidido pelo autor em 30/10/2026
    r"modelos?\s+preditivos?",
    r"chatbots?",
    r"assistentes?\s+virtua(?:l|is)",
]

# Contextos em que a sigla não é inteligência artificial (revisão de 2025).
# Cada regex cobre a sigla e o contexto; se cobrir a ocorrência, ela é descartada.
# Aplicadas com diferenciação de maiúsculas, exceto onde marcado com (?i:).
EXCLUSOES = [
    # sigla seguida de número: Auto de Infração, Agravo de Instrumento, Inquérito
    # Administrativo ("multa AI 32/2017", "AI-408/2020", "IA nº 19957.011171/2024-79")
    r"\b(?:AI|IA)\s*(?:n[º°o]?\.?\s*|[º°]\s*)?[-–]?\s*\d",
    # artigo/preposição masculina: "do AI", "nos autos do AI", "instaurou o IA".
    # A inteligência artificial é feminina ("a IA", "da IA")
    r"(?i:\b(?:o|do|no|ao|pelo|pelos|dos|nos|os|um|multa)\s+)(?:AI|IA)\b",
    # sigla definida logo depois do nome por extenso: "Auto de Infração (AI)",
    # "agravo de instrumento - AI", "Auditoria Interna (AI)"
    r"(?i:(?:infra[çc][ãa]o|instrumento|auditoria\s+interna|avalia[çc][ãa]o\s+interna)\s*[(\-–]?\s*)AI\b",
    # letras de coluna de planilha colada no PDF
    r"\bAH\s+AI\s+AJ\b",
    # outras siglas vistas em 2023: "Instituto Alpargatas (IA)", "Influenza Aviária, IA",
    # "Ativos Imobilizados (AI)", "IA – Índice Ambiental", "indicador IA",
    # "Investment Fund IA LP", "AG/REsp e AI/RE"
    r"(?i:(?:instituto\s+\w+|influenza\s+avi[áa]ria|ativos\s+imobilizados)\s*[(,–-]?\s*[\"“”]?)(?:IA|AI)\b",
    r"\bIA\s*[–-]\s*(?i:[íi]ndice)",
    r"(?i:indicador\s+)IA\b",
    r"\bFund\s+IA\b",
    r"\bAI/RE\b",
    # 'Auto de Infração ("AI") 0008/2022'; "AI e AE + ICC" (Avaliação Interna/Externa);
    # "GRC&AI" / "GRC & AI" (Governança, Riscos, Conformidade e Auditoria Interna)
    r'\bAI["”)]+\s*\d',
    r"\bAI\s+e\s+AE\b",
    r"\bGRC\s*&\s*AI\b",
    # palavra quebrada pela extração do PDF: "COMPROMISSÁR IA"
    r"(?i:compromiss[áa]r)\s+IA\b",
    # nome de empresa do grupo Iguá ("Fluxx.IA Medição Inteligente"); decidido pelo autor em 28/10/2026
    r"(?i:fluxx)\.IA\b",
]

# A sigla "AI" não é contada nas seções de processos e contingências (4.4 a 4.7):
# lá ela é quase sempre Auto de Infração ou Agravo de Instrumento.
SECOES_SEM_SIGLA_AI = {"4.4", "4.5", "4.6", "4.7"}

# Seções do FRE (Resolução CVM 80/22, versão vigente desde 2023) de interesse
# para o artigo. O número é o prefixo da seção no formulário.
SECOES_INTERESSE = {
    "1.1": "Histórico do emissor",
    "1.2": "Principais atividades",
    "1.9": "Informações ASG",
    "1.14": "Alterações significativas na condução dos negócios",
    "1.16": "Outras informações relevantes (atividades)",
    "2.1": "Condições financeiras e patrimoniais",
    "2.2": "Resultados operacional e financeiro",
    "2.10": "Planos de negócios",
    "2.11": "Outros fatores que influenciaram o desempenho",
    "4.1": "Fatores de risco",
    "4.2": "Cinco principais fatores de risco",
    "5.1": "Gerenciamento de riscos",
    "5.2": "Controles internos",
    "10.1": "Recursos humanos",
}
