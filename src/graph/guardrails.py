"""
Guardrails técnicos do BluaDiagnostics.

São verificações determinísticas (sem depender do LLM) que rodam ANTES
de o sistema decidir a conduta. A ideia é ter uma camada de segurança
que não depende só do modelo "se comportar bem".

Três guardrails:
1. Red flag: detecta sinais de emergência e força escalada.
2. Escopo: rejeita perguntas fora do domínio Care Plus/saúde.
3. Moderação: detecta conteúdo claramente impróprio.

A detecção é por palavras-chave. Não é perfeita (um classificador de ML
seria mais robusto), mas é transparente, rápida e auditável, o que num
contexto clínico vale muito. A gente documenta essa limitação no
relatório técnico.
"""

import re
import unicodedata


def _normalizar(texto: str) -> str:
    """Tira acento e baixa pra minúscula, pra casar palavra independente de acento."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return sem_acento.lower()


# Frases/padrões que indicam emergência clínica. Mantemos como frases
# (não só palavras soltas) pra reduzir falso positivo.
PADROES_RED_FLAG = [
    r"dor.{0,15}peito",
    r"dor.{0,15}torac",
    r"aperto.{0,15}peito",
    r"falta de ar",
    r"nao consigo respirar",
    r"dificuldade.{0,15}respirar",
    r"perda.{0,15}forca",
    r"sem forca.{0,15}(braco|perna|lado)",
    r"fala enrolada",
    r"boca torta",
    r"desmai",
    r"convuls",
    r"sangramento.{0,15}(intenso|abundante|nao para)",
    r"pior dor de cabeca da vida",
    r"me machucar",
    r"tirar a (minha )?propria vida",
    r"acabar com tudo",
    r"nao quero mais viver",
    r"me matar",
]

# Termos de saúde mental que pedem encaminhamento ao CVV em vez de triagem comum.
PADROES_SAUDE_MENTAL = [
    r"me machucar",
    r"tirar a (minha )?propria vida",
    r"acabar com tudo",
    r"nao quero mais viver",
    r"me matar",
    r"suicid",
]

# Palavras que indicam que a pergunta provavelmente está no escopo (saúde/plano).
TERMOS_NO_ESCOPO = [
    "dor", "febre", "sintoma", "remedio", "medicamento", "consulta",
    "teleconsulta", "medico", "saude", "plano", "blua", "care plus",
    "exame", "agendar", "tosse", "garganta", "cabeca", "peito", "pressao",
    "diabetes", "alergia", "vacina", "receita", "cansaco", "tontura",
    "enjoo", "nausea", "vomito", "diarreia", "coriza", "espirro",
    "wearable", "batimento", "sono", "frequencia cardiaca",
]

# Tópicos claramente fora do escopo.
PADROES_FORA_ESCOPO = [
    r"redacao", r"vestibular", r"investiment", r"a\u00e7\u00f5es da bolsa",
    r"bitcoin", r"cripto", r"receita de (bolo|comida|mousse)",
    r"codigo (python|java|javascript)", r"piada", r"futebol",
    r"capital d[eo]", r"traduz", r"poema", r"musica",
]


def checar_red_flag(texto: str) -> dict:
    """Verifica se o texto contém sinais de emergência clínica.

    Returns:
        dict com 'detectado' (bool), 'saude_mental' (bool) e 'termo' (o
        padrão que casou, pra log/auditoria).
    """
    t = _normalizar(texto)

    for padrao in PADROES_SAUDE_MENTAL:
        if re.search(padrao, t):
            return {"detectado": True, "saude_mental": True, "termo": padrao}

    for padrao in PADROES_RED_FLAG:
        if re.search(padrao, t):
            return {"detectado": True, "saude_mental": False, "termo": padrao}

    return {"detectado": False, "saude_mental": False, "termo": None}


def checar_escopo(texto: str) -> dict:
    """Verifica se a pergunta está dentro do domínio Care Plus/saúde.

    Estratégia: se bate um padrão claramente fora de escopo E não tem
    nenhum termo de saúde, consideramos fora. A gente é conservador pra
    não rejeitar pergunta clínica legítima por engano.

    Returns:
        dict com 'no_escopo' (bool) e 'motivo'.
    """
    t = _normalizar(texto)

    tem_termo_saude = any(termo in t for termo in TERMOS_NO_ESCOPO)
    bate_fora = any(re.search(p, t) for p in PADROES_FORA_ESCOPO)

    if bate_fora and not tem_termo_saude:
        return {"no_escopo": False, "motivo": "Assunto fora do domínio de saúde/Care Plus."}

    return {"no_escopo": True, "motivo": None}


def checar_moderacao(texto: str) -> dict:
    """Moderação básica de conteúdo claramente abusivo.

    Bem simples de propósito: a moderação pesada fica a cargo do próprio
    Gemini (que já tem filtros de segurança). Aqui é só uma rede extra.

    Returns:
        dict com 'aprovado' (bool).
    """
    t = _normalizar(texto)
    termos_bloqueados = ["bomba caseira", "como fabricar arma"]
    for termo in termos_bloqueados:
        if termo in t:
            return {"aprovado": False, "motivo": "Conteúdo bloqueado pela moderação."}
    return {"aprovado": True, "motivo": None}
