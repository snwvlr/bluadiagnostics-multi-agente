"""
Interface Streamlit do BluaDiagnostics.

Roda com:  streamlit run app/streamlit_app.py

Mostra o chat e, num painel lateral, a "caixa preta" do sistema: qual
agente respondeu, quais tools rodaram e quais documentos o RAG trouxe.
A gente fez questão de deixar isso visível porque é exatamente o que o
vídeo de demonstração precisa mostrar (RAG retornando documento, tools
sendo chamadas, escalada acontecendo).
"""

import os
import sys

# Deixa o Python achar o pacote src/ quando roda via streamlit.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from src.sistema import BluaDiagnostics

st.set_page_config(page_title="BluaDiagnostics", page_icon="🩺", layout="wide")

st.title("🩺 BluaDiagnostics")
st.caption("Check-up digital da Care Plus - assistente de triagem (não substitui médico)")

# Sidebar: configura o paciente e mostra a observabilidade.
with st.sidebar:
    st.header("Sessão")
    cpf = st.text_input("CPF do beneficiário", value="12345678901")
    if st.button("Iniciar / reiniciar atendimento"):
        with st.spinner("Preparando o sistema e indexando a base de conhecimento..."):
            st.session_state.sistema = BluaDiagnostics(cpf=cpf)
            st.session_state.mensagens = []
        st.success("Pronto! Pode mandar sua mensagem.")

    st.divider()
    st.subheader("Bastidores do último turno")
    st.caption("O que o sistema fez por dentro na sua última mensagem.")
    placeholder_obs = st.empty()


# Inicializa estado.
if "mensagens" not in st.session_state:
    st.session_state.mensagens = []
if "sistema" not in st.session_state:
    st.info("Clique em **Iniciar / reiniciar atendimento** na barra lateral pra começar.")


# Renderiza o histórico.
for msg in st.session_state.mensagens:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# Caixa de entrada.
if prompt := st.chat_input("Como você está se sentindo?"):
    if "sistema" not in st.session_state:
        st.warning("Inicie o atendimento na barra lateral primeiro.")
    else:
        st.session_state.mensagens.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Pensando..."):
                resultado = st.session_state.sistema.conversar(prompt)
            st.markdown(resultado["resposta"])

        st.session_state.mensagens.append({"role": "assistant", "content": resultado["resposta"]})

        # Atualiza o painel de observabilidade.
        with placeholder_obs.container():
            st.markdown(f"**Agente acionado:** `{resultado['agente'] or 'n/d'}`")
            st.markdown(f"**Trajetória no grafo:** {' → '.join(resultado['trajetoria'])}")

            if resultado["tools_chamadas"]:
                st.markdown("**Tools chamadas:**")
                for t in resultado["tools_chamadas"]:
                    st.markdown(f"- `{t}`")
            else:
                st.markdown("**Tools chamadas:** nenhuma")

            if resultado["documentos_rag"]:
                st.markdown("**Documentos recuperados (RAG):**")
                for d in resultado["documentos_rag"]:
                    with st.expander(f"📄 {d['fonte']}"):
                        st.write(d["texto"])
            else:
                st.markdown("**Documentos recuperados (RAG):** nenhum")
