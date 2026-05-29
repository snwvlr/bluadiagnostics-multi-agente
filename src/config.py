"""
Configuração central do BluaDiagnostics.

A gente centralizou tudo aqui pra não ter parâmetro hard-coded espalhado
pelo código (o enunciado penaliza isso). Qualquer ajuste de modelo,
temperatura ou caminho é feito num lugar só.
"""

import os
from pathlib import Path

# Carrega o arquivo .env (se existir) pra dentro das variáveis de ambiente.
# É isso que faz a GOOGLE_API_KEY do .env ficar visível pro os.environ.
# Se o python-dotenv não estiver instalado, segue sem ele (em Colab, por
# exemplo, a chave vem do Secrets e não tem .env).
try:
    from dotenv import load_dotenv

    _RAIZ_PROJETO = Path(__file__).resolve().parent.parent
    load_dotenv(_RAIZ_PROJETO / ".env")
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Caminhos do projeto
# ---------------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parent.parent
DIR_DADOS = RAIZ / "data"
DIR_KB = DIR_DADOS / "knowledge_base"
DIR_VECTORSTORE = DIR_DADOS / "chroma_db"
DIR_EVALS = RAIZ / "evals"

# ---------------------------------------------------------------------------
# Modelo e parâmetros
# ---------------------------------------------------------------------------
# A escolha do Gemini 2.5 Flash vem desde a Sprint 1: free tier disponível,
# function calling nativo e contexto de 1M de tokens (sobra pro RAG).
MODELO_LLM = "gemini-2.5-flash"
MODELO_EMBEDDING = "models/gemini-embedding-001"

# Parâmetros ajustados durante os evals (ver README, seção de iterações).
# temperature baixa porque é contexto clínico: a gente quer respostas
# consistentes e conservadoras, não criativas.
TEMPERATURE = 0.2
TOP_P = 0.9
MAX_OUTPUT_TOKENS = 1024

# ---------------------------------------------------------------------------
# RAG
# ---------------------------------------------------------------------------
CHUNK_SIZE = 600          # caracteres por chunk
CHUNK_OVERLAP = 100       # sobreposição pra não cortar contexto no meio
TOP_K_RETRIEVER = 3       # quantos documentos o retriever traz por consulta
NOME_COLECAO = "base_clinica_careplus"

# ---------------------------------------------------------------------------
# Rate limiting (free tier padrão é 5 RPM; nossa conta tem crédito de teste)
# ---------------------------------------------------------------------------
DELAY_ENTRE_CHAMADAS_SEG = 1  # com crédito (Tier 1) não precisa de muito


def get_api_key() -> str:
    """Busca a API key do Gemini de variável de ambiente.

    Nunca colocamos a chave no código. Em produção/Colab ela vem de
    variável de ambiente ou de secret. Se não achar, levanta erro
    explicando o que fazer.
    """
    chave = os.environ.get("GOOGLE_API_KEY")
    if not chave:
        raise RuntimeError(
            "GOOGLE_API_KEY não encontrada. Defina a variável de ambiente "
            "antes de rodar (export GOOGLE_API_KEY=... ou use um arquivo "
            ".env com python-dotenv)."
        )
    return chave
