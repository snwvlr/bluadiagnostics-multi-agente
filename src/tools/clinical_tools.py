"""
Tools do BluaDiagnostics (function calling).

São as funções que os agentes podem chamar pra interagir com os sistemas
simulados da Care Plus. Na PoC os retornos são mockados, mas o contrato
(assinatura, tipos, docstring) é o mesmo que a gente usaria em produção,
onde cada função viraria uma chamada HTTP autenticada.

A gente escreveu docstrings detalhadas de propósito: é a partir delas que
o Gemini decide quando e como chamar cada tool.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

from src.config import DIR_DADOS

# Carrega os mocks uma vez só, quando o módulo é importado.
with open(DIR_DADOS / "pacientes_mock.json", encoding="utf-8") as f:
    _PACIENTES = json.load(f)["pacientes"]

with open(DIR_DADOS / "wearables_mock.json", encoding="utf-8") as f:
    _WEARABLES = json.load(f)["snapshots"]


def consultar_historico_paciente(cpf: str) -> dict:
    """Consulta o histórico clínico do beneficiário no sistema da Care Plus.

    Use sempre que precisar de idade, alergias, medicamentos em uso ou
    comorbidades pra personalizar a orientação. Nunca invente esses
    dados, chame esta tool.

    Args:
        cpf: CPF do beneficiário, só dígitos, 11 caracteres.

    Returns:
        Dados do paciente, ou um aviso de não encontrado.
    """
    paciente = _PACIENTES.get(cpf)
    if not paciente:
        return {
            "encontrado": False,
            "mensagem": "Não localizei esse CPF na base. Confere se está correto.",
        }
    return {"encontrado": True, **paciente}


def verificar_interacoes_medicamentosas(medicamentos: list[str]) -> dict:
    """Verifica se há interação relevante entre uma lista de medicamentos.

    Use quando o paciente relatar que vai tomar um remédio novo junto com
    os que já usa. Esta tool só verifica, não recomenda medicamento.

    Args:
        medicamentos: Nomes em letra minúscula, sem dose. Mínimo 2 itens.
            Ex.: ['losartana', 'ibuprofeno'].

    Returns:
        Interações encontradas, severidade geral e recomendação.
    """
    nomes = [m.lower().strip() for m in medicamentos]

    # Regra simulada conhecida: AINE reduz efeito de anti-hipertensivo.
    if "losartana" in nomes and "ibuprofeno" in nomes:
        return {
            "interacoes_encontradas": [
                {
                    "medicamento_a": "losartana",
                    "medicamento_b": "ibuprofeno",
                    "severidade": "moderada",
                    "descricao": (
                        "AINEs podem reduzir o efeito anti-hipertensivo da "
                        "losartana e aumentar risco renal."
                    ),
                }
            ],
            "severidade_geral": "moderada",
            "recomendacao": (
                "Recomenda-se avaliação médica antes da associação. O médico "
                "pode considerar uma alternativa analgésica."
            ),
        }

    return {
        "interacoes_encontradas": [],
        "severidade_geral": "nenhuma",
        "recomendacao": "Não há interações relevantes no banco simulado. Confirme sempre com profissional.",
    }


def agendar_teleconsulta(cpf: str, especialidade: str, urgencia: str, motivo: str) -> dict:
    """Agenda uma teleconsulta com a especialidade adequada.

    Use quando a triagem indicar necessidade de avaliação profissional ou
    quando o usuário pedir. NÃO use em casos de red flag, nesses casos a
    orientação é SAMU 192 direto.

    Args:
        cpf: CPF do beneficiário.
        especialidade: clinico_geral, pediatria, ginecologia, cardiologia,
            dermatologia, psiquiatria, endocrinologia ou ortopedia.
        urgencia: 'rotina' (7 dias), 'breve' (48h) ou 'mesmo_dia'.
        motivo: Resumo curto do motivo, pro médico se preparar.

    Returns:
        Dados do agendamento confirmado.
    """
    horarios = {"rotina": 72, "breve": 24, "mesmo_dia": 2}
    horas = horarios.get(urgencia, 72)
    quando = datetime.now() + timedelta(hours=horas)

    return {
        "protocolo": f"BLUA-{datetime.now().strftime('%Y%m%d')}-{abs(hash(cpf)) % 100000:05d}",
        "data_horario": quando.strftime("%Y-%m-%dT%H:%M:00"),
        "especialidade": especialidade,
        "profissional": "Dra. Helena Costa (CRM-SP 123456)",
        "link_consulta": "https://blua.careplus.com.br/sala/demo",
        "status": "confirmado",
    }


def obter_sinais_vitais_wearable(cpf: str, fonte: str) -> dict:
    """Recupera os sinais vitais mais recentes do wearable do beneficiário.

    Use quando o caso se beneficiar de dados objetivos (cansaço,
    palpitação, falta de ar leve). Dados complementares à triagem, nunca
    substituem avaliação médica.

    Args:
        cpf: CPF do beneficiário.
        fonte: 'apple_health' ou 'google_fit'.

    Returns:
        Sinais vitais (FC, SpO2, sono, passos, HRV) ou aviso de ausência.
    """
    do_paciente = _WEARABLES.get(cpf, {})
    snapshot = do_paciente.get(fonte)
    if not snapshot:
        return {"disponivel": False, "mensagem": f"Sem wearable '{fonte}' vinculado a este beneficiário."}
    return {"disponivel": True, **snapshot}


# Mapa nome -> função, usado pelo executor de tools no grafo.
TOOLS_DISPONIVEIS = {
    "consultar_historico_paciente": consultar_historico_paciente,
    "verificar_interacoes_medicamentosas": verificar_interacoes_medicamentosas,
    "agendar_teleconsulta": agendar_teleconsulta,
    "obter_sinais_vitais_wearable": obter_sinais_vitais_wearable,
}
