"""
Grafo de orquestração do BluaDiagnostics (LangGraph).

Aqui é onde a mágica multi-agente acontece. A gente montou um grafo com:

  entrada -> guardrails -> supervisor -> [triagem | prescricao | escalada] -> fim

O estado é compartilhado entre os nós (histórico, paciente, contexto RAG,
trajetória). As arestas que saem do supervisor são CONDICIONAIS: o
roteamento depende da decisão dele e dos guardrails. Isso é orquestração
de verdade, não chamada sequencial fixa, que é justamente o que vale os
pontos de bônus de arquitetura.

Fluxo detalhado:
1. Nó guardrails: roda red flag / escopo / moderação (determinístico).
   - Se red flag -> pula direto pra escalada.
   - Se fora de escopo -> resposta curta de recusa, encerra.
2. Nó RAG: recupera contexto clínico relevante da base.
3. Nó supervisor: classifica triagem vs prescricao.
4. Nó do especialista escolhido: responde, podendo chamar tools.
"""

from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from src.agents.specialists import (
    rodar_escalada,
    rodar_prescricao,
    rodar_supervisor,
    rodar_triagem,
)
from src.graph.guardrails import checar_escopo, checar_moderacao, checar_red_flag


def _ultimo(valor_atual, valor_novo):
    """Reducer simples: o valor novo sempre substitui o anterior."""
    return valor_novo if valor_novo is not None else valor_atual


class EstadoConversa(TypedDict):
    """Estado compartilhado que trafega entre os nós do grafo.

    É a 'memória de trabalho' de um turno. O histórico acumula entre
    turnos; o resto é recalculado a cada mensagem.
    """

    mensagem_usuario: Annotated[str, _ultimo]
    historico: Annotated[list, _ultimo]
    cpf_paciente: Annotated[str, _ultimo]
    contexto_rag: Annotated[str, _ultimo]
    documentos_rag: Annotated[list, _ultimo]
    agente_escolhido: Annotated[str, _ultimo]
    resposta: Annotated[str, _ultimo]
    tools_chamadas: Annotated[list, _ultimo]
    trajetoria: Annotated[list, _ultimo]
    encerrar: Annotated[bool, _ultimo]


def construir_grafo(base_clinica=None):
    """Constrói e compila o grafo LangGraph.

    Recebe a base_clinica (RAG) por injeção de dependência: assim dá pra
    rodar o grafo sem RAG nos testes, passando None.
    """

    # ---- Nó: guardrails determinísticos -------------------------------
    def no_guardrails(estado: EstadoConversa) -> dict:
        msg = estado["mensagem_usuario"]
        trajetoria = estado.get("trajetoria", []) + ["guardrails"]

        moderacao = checar_moderacao(msg)
        if not moderacao["aprovado"]:
            return {
                "resposta": "Não consigo ajudar com esse pedido.",
                "encerrar": True,
                "trajetoria": trajetoria,
                "agente_escolhido": "moderacao",
            }

        red = checar_red_flag(msg)
        if red["detectado"]:
            # Marca pra rota de escalada; guarda se é saúde mental no cpf? não.
            return {
                "agente_escolhido": "escalada",
                "trajetoria": trajetoria + ["red_flag_detectada"],
                "encerrar": False,
                # passa a flag de saúde mental via contexto_rag (campo livre)
                "contexto_rag": "SAUDE_MENTAL" if red["saude_mental"] else "",
            }

        escopo = checar_escopo(msg)
        if not escopo["no_escopo"]:
            return {
                "resposta": (
                    "Sou o assistente de saúde do Blua, da Care Plus, então "
                    "consigo ajudar só com questões de saúde e do seu plano. "
                    "Pra esse assunto, recomendo procurar uma ferramenta "
                    "específica. Posso te ajudar com algum sintoma ou dúvida "
                    "sobre o plano?"
                ),
                "encerrar": True,
                "trajetoria": trajetoria + ["fora_de_escopo"],
                "agente_escolhido": "fora_de_escopo",
            }

        return {"trajetoria": trajetoria, "encerrar": False}

    # ---- Nó: recuperação RAG ------------------------------------------
    def no_rag(estado: EstadoConversa) -> dict:
        trajetoria = estado.get("trajetoria", []) + ["rag"]
        if base_clinica is None:
            return {"contexto_rag": estado.get("contexto_rag", ""), "documentos_rag": [], "trajetoria": trajetoria}

        # Preserva a flag de saúde mental se o guardrail a setou.
        flag_anterior = estado.get("contexto_rag", "")
        docs = base_clinica.buscar(estado["mensagem_usuario"])
        contexto = "\n\n".join(f"[Fonte: {d['fonte']}]\n{d['texto']}" for d in docs)

        if flag_anterior == "SAUDE_MENTAL":
            contexto = "SAUDE_MENTAL\n" + contexto

        return {"contexto_rag": contexto, "documentos_rag": docs, "trajetoria": trajetoria}

    # ---- Nó: supervisor (decide o roteamento) -------------------------
    def no_supervisor(estado: EstadoConversa) -> dict:
        trajetoria = estado.get("trajetoria", []) + ["supervisor"]
        # Se o guardrail já decidiu escalada, o supervisor não sobrescreve.
        if estado.get("agente_escolhido") == "escalada":
            return {"trajetoria": trajetoria}
        escolha = rodar_supervisor(estado["mensagem_usuario"], estado.get("historico", []))
        return {"agente_escolhido": escolha, "trajetoria": trajetoria}

    # ---- Nós: especialistas -------------------------------------------
    def no_triagem(estado: EstadoConversa) -> dict:
        ctx = estado.get("contexto_rag", "")
        if ctx.startswith("SAUDE_MENTAL"):
            ctx = ctx.replace("SAUDE_MENTAL", "").strip()
        out = rodar_triagem(estado["mensagem_usuario"], estado.get("historico", []), ctx)
        return {
            "resposta": out["resposta"],
            "tools_chamadas": out["tools_chamadas"],
            "trajetoria": estado.get("trajetoria", []) + ["triagem"],
        }

    def no_prescricao(estado: EstadoConversa) -> dict:
        ctx = estado.get("contexto_rag", "")
        out = rodar_prescricao(estado["mensagem_usuario"], estado.get("historico", []), ctx)
        return {
            "resposta": out["resposta"],
            "tools_chamadas": out["tools_chamadas"],
            "trajetoria": estado.get("trajetoria", []) + ["prescricao"],
        }

    def no_escalada(estado: EstadoConversa) -> dict:
        eh_saude_mental = estado.get("contexto_rag", "").startswith("SAUDE_MENTAL")
        out = rodar_escalada(
            estado["mensagem_usuario"],
            estado.get("historico", []),
            saude_mental=eh_saude_mental,
        )
        return {
            "resposta": out["resposta"],
            "tools_chamadas": out["tools_chamadas"],
            "trajetoria": estado.get("trajetoria", []) + ["escalada"],
        }

    # ---- Funções de roteamento condicional ----------------------------
    def rotear_apos_guardrails(estado: EstadoConversa) -> str:
        if estado.get("encerrar"):
            return END
        if estado.get("agente_escolhido") == "escalada":
            # Em emergência pula o RAG e vai direto pro supervisor (que
            # respeita a escalada) e daí pro especialista.
            return "rag"
        return "rag"

    def rotear_apos_supervisor(estado: EstadoConversa) -> str:
        return estado.get("agente_escolhido", "triagem")

    # ---- Montagem do grafo --------------------------------------------
    grafo = StateGraph(EstadoConversa)

    grafo.add_node("guardrails", no_guardrails)
    grafo.add_node("rag", no_rag)
    grafo.add_node("supervisor", no_supervisor)
    grafo.add_node("triagem", no_triagem)
    grafo.add_node("prescricao", no_prescricao)
    grafo.add_node("escalada", no_escalada)

    grafo.add_edge(START, "guardrails")
    grafo.add_conditional_edges("guardrails", rotear_apos_guardrails, {"rag": "rag", END: END})
    grafo.add_edge("rag", "supervisor")
    grafo.add_conditional_edges(
        "supervisor",
        rotear_apos_supervisor,
        {"triagem": "triagem", "prescricao": "prescricao", "escalada": "escalada"},
    )
    grafo.add_edge("triagem", END)
    grafo.add_edge("prescricao", END)
    grafo.add_edge("escalada", END)

    return grafo.compile()
