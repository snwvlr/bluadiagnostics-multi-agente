"""
Agentes do BluaDiagnostics.

Cada agente é uma função que recebe o estado da conversa e devolve uma
resposta. O supervisor é um classificador leve (decide o roteamento); os
especialistas (triagem, prescrição, escalada) é que conversam de verdade
com o usuário e podem chamar tools.

A gente usa o SDK do Gemini direto pra ter controle fino sobre o function
calling. O LangGraph (em graph/) cuida da orquestração entre esses
agentes.
"""

import google.generativeai as genai

from src.agents.prompts import (
    PROMPT_ESCALADA,
    PROMPT_PRESCRICAO,
    PROMPT_SUPERVISOR,
    PROMPT_TRIAGEM,
    contexto_data_hora,
)
from src.config import MAX_OUTPUT_TOKENS, MODELO_LLM, TEMPERATURE, TOP_P
from src.tools.clinical_tools import (
    agendar_teleconsulta,
    consultar_historico_paciente,
    obter_sinais_vitais_wearable,
    verificar_interacoes_medicamentosas,
)

_GENERATION_CONFIG = {
    "temperature": TEMPERATURE,
    "top_p": TOP_P,
    "max_output_tokens": MAX_OUTPUT_TOKENS,
}

# Quais tools cada agente pode usar. Separar assim deixa cada agente mais
# focado e reduz chamada de tool fora de contexto.
TOOLS_TRIAGEM = [consultar_historico_paciente, obter_sinais_vitais_wearable, agendar_teleconsulta]
TOOLS_PRESCRICAO = [consultar_historico_paciente, verificar_interacoes_medicamentosas, agendar_teleconsulta]


def _montar_historico_para_gemini(historico: list[dict]) -> list[dict]:
    """Converte nosso histórico interno pro formato que o SDK do Gemini espera."""
    convertido = []
    for msg in historico:
        papel = "user" if msg["role"] == "user" else "model"
        convertido.append({"role": papel, "parts": [msg["content"]]})
    return convertido


def _texto_seguro(resp) -> str:
    """Lê o texto de uma resposta do Gemini sem quebrar se ela vier vazia.

    O acessor resp.text levanta erro quando a resposta não tem texto (por
    exemplo, quando o limite de tokens é atingido ou um filtro de segurança
    dispara). Aqui a gente tenta ler de forma defensiva e devolve string
    vazia em vez de explodir, deixando quem chamou decidir o fallback.
    """
    try:
        return resp.text or ""
    except Exception:
        # Tenta garimpar o texto direto das partes do candidato.
        try:
            partes = resp.candidates[0].content.parts
            return "".join(getattr(p, "text", "") for p in partes)
        except Exception:
            return ""


def rodar_supervisor(mensagem_usuario: str, historico: list[dict]) -> str:
    """Classifica pra qual agente a conversa deve ir.

    Retorna uma de: 'triagem', 'prescricao', 'escalada'. Se o modelo
    devolver algo inesperado, a gente cai no default 'triagem' (o caminho
    mais seguro e comum).
    """
    modelo = genai.GenerativeModel(
        model_name=MODELO_LLM,
        system_instruction=PROMPT_SUPERVISOR,
        # O Flash gasta tokens de raciocínio antes de responder, então um
        # limite muito baixo faz a resposta voltar vazia. 200 dá folga de
        # sobra pra ele devolver uma palavra só.
        generation_config={"temperature": 0.0, "max_output_tokens": 200},
    )
    # Damos só os últimos turnos pra decisão ser rápida e barata.
    contexto = _montar_historico_para_gemini(historico[-4:])
    contexto.append({"role": "user", "parts": [mensagem_usuario]})

    resp = modelo.generate_content(contexto)

    # Lê o texto com cuidado: se por qualquer motivo a resposta vier sem
    # texto (limite de token, filtro de segurança), a gente cai no default
    # 'triagem' em vez de quebrar.
    decisao = (_texto_seguro(resp)).strip().lower()

    for valido in ("escalada", "prescricao", "triagem"):
        if valido in decisao:
            return valido
    return "triagem"


def _rodar_agente_conversacional(
    system_prompt: str,
    tools: list,
    mensagem_usuario: str,
    historico: list[dict],
    contexto_rag: str = "",
) -> dict:
    """Roda um agente especialista com tools e (opcionalmente) contexto RAG.

    Retorna a resposta em texto e a lista de tools que foram chamadas
    (pra gente registrar a trajetória nos evals e na observabilidade).
    """
    instrucao = system_prompt + "\n\n" + contexto_data_hora()
    if contexto_rag:
        instrucao += (
            "\n\nCONTEXTO CLÍNICO RECUPERADO DA BASE DE CONHECIMENTO "
            "(use pra embasar sua resposta, cite a orientação quando útil):\n"
            + contexto_rag
        )

    modelo = genai.GenerativeModel(
        model_name=MODELO_LLM,
        system_instruction=instrucao,
        tools=tools,
        generation_config=_GENERATION_CONFIG,
    )

    chat = modelo.start_chat(
        history=_montar_historico_para_gemini(historico),
        enable_automatic_function_calling=True,
    )
    resposta = chat.send_message(mensagem_usuario)

    # Extrai quais tools foram chamadas, varrendo o histórico do chat.
    tools_chamadas = []
    for msg in chat.history:
        for parte in msg.parts:
            fc = getattr(parte, "function_call", None)
            if fc and fc.name:
                tools_chamadas.append(fc.name)

    return {"resposta": _texto_seguro(resposta), "tools_chamadas": tools_chamadas}


def rodar_triagem(mensagem_usuario, historico, contexto_rag=""):
    """Agente de triagem: coleta sintomas e orienta."""
    return _rodar_agente_conversacional(
        PROMPT_TRIAGEM, TOOLS_TRIAGEM, mensagem_usuario, historico, contexto_rag
    )


def rodar_prescricao(mensagem_usuario, historico, contexto_rag=""):
    """Agente de prescrição: verifica medicamentos e encaminha pro médico."""
    return _rodar_agente_conversacional(
        PROMPT_PRESCRICAO, TOOLS_PRESCRICAO, mensagem_usuario, historico, contexto_rag
    )


def rodar_escalada(mensagem_usuario, historico, contexto_rag="", saude_mental=False):
    """Agente de escalada: orienta emergência (SAMU) ou sofrimento mental (CVV).

    Esse agente não usa tools de propósito: em emergência, a prioridade é
    velocidade e clareza, não consulta a sistemas.
    """
    modelo = genai.GenerativeModel(
        model_name=MODELO_LLM,
        system_instruction=PROMPT_ESCALADA + "\n\n" + contexto_data_hora(),
        generation_config={"temperature": 0.1, "max_output_tokens": MAX_OUTPUT_TOKENS},
    )
    dica = (
        "[contexto interno: o guardrail detectou possível sofrimento mental, "
        "priorize acolhimento e CVV 188]"
        if saude_mental
        else "[contexto interno: o guardrail detectou possível emergência clínica, "
        "priorize SAMU 192]"
    )
    chat = modelo.start_chat(history=_montar_historico_para_gemini(historico))
    resposta = chat.send_message(f"{dica}\n\nMensagem do usuário: {mensagem_usuario}")
    return {"resposta": _texto_seguro(resposta), "tools_chamadas": []}
