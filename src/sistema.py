"""
BluaDiagnostics, sistema completo.

Esta classe é a fachada do sistema: junta o grafo LangGraph, o RAG e a
memória de conversa num objeto só, fácil de usar tanto no Streamlit
quanto nos evals e no notebook.

Uso típico:
    sistema = BluaDiagnostics(cpf="12345678901")
    resultado = sistema.conversar("Estou com dor de cabeça")
    print(resultado["resposta"])
"""

import google.generativeai as genai

from src.config import get_api_key
from src.graph.orchestrator import construir_grafo
from src.rag.knowledge_base import BaseClinica


class BluaDiagnostics:
    """Fachada do sistema multi-agente."""

    def __init__(self, cpf: str = "12345678901", usar_rag: bool = True, indexar: bool = True):
        # Configura a API uma vez.
        genai.configure(api_key=get_api_key())

        self.cpf = cpf
        self.historico: list[dict] = []

        if usar_rag:
            self.base = BaseClinica()
            if indexar:
                self.base.indexar()
        else:
            self.base = None

        self.grafo = construir_grafo(base_clinica=self.base)

    def conversar(self, mensagem_usuario: str) -> dict:
        """Processa uma mensagem do usuário e devolve a resposta + metadados.

        Os metadados (agente acionado, tools chamadas, documentos do RAG,
        trajetória) são o que a gente usa nos evals e na observabilidade.
        """
        estado_inicial = {
            "mensagem_usuario": mensagem_usuario,
            "historico": list(self.historico),
            "cpf_paciente": self.cpf,
            "contexto_rag": "",
            "documentos_rag": [],
            "agente_escolhido": "",
            "resposta": "",
            "tools_chamadas": [],
            "trajetoria": [],
            "encerrar": False,
        }

        final = self.grafo.invoke(estado_inicial)

        # Atualiza a memória da conversa.
        self.historico.append({"role": "user", "content": mensagem_usuario})
        self.historico.append({"role": "assistant", "content": final["resposta"]})

        return {
            "resposta": final["resposta"],
            "agente": final.get("agente_escolhido", ""),
            "trajetoria": final.get("trajetoria", []),
            "tools_chamadas": final.get("tools_chamadas", []),
            "documentos_rag": final.get("documentos_rag", []),
        }

    def resetar(self):
        """Limpa a memória da conversa (começa um atendimento novo)."""
        self.historico = []
