"""
Pipeline de RAG do BluaDiagnostics.

Faz o caminho completo: lê os documentos da base de conhecimento, quebra
em chunks, gera embeddings com a API do Gemini, guarda num vector store
Chroma (local, sem servidor) e expõe um retriever.

A gente escolheu Chroma porque roda local e persiste em disco, sem
precisar subir servidor nenhum, o que facilita demais rodar no Colab e
no Streamlit. Embeddings do Gemini porque já usamos a mesma API do LLM,
então é uma credencial só.
"""

import google.generativeai as genai

from src.config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DIR_KB,
    DIR_VECTORSTORE,
    MODELO_EMBEDDING,
    NOME_COLECAO,
    TOP_K_RETRIEVER,
)


def _quebrar_em_chunks(texto: str, fonte: str) -> list[dict]:
    """Quebra um texto em pedaços com sobreposição.

    A sobreposição evita que uma informação importante seja cortada bem na
    fronteira entre dois chunks. Cada chunk carrega o nome do arquivo de
    origem nos metadados, pra gente conseguir mostrar a fonte depois.
    """
    chunks = []
    inicio = 0
    while inicio < len(texto):
        fim = inicio + CHUNK_SIZE
        trecho = texto[inicio:fim].strip()
        if trecho:
            chunks.append({"texto": trecho, "fonte": fonte})
        inicio += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def carregar_documentos() -> list[dict]:
    """Lê todos os .md da base de conhecimento e quebra em chunks."""
    todos = []
    for arquivo in sorted(DIR_KB.glob("*.md")):
        conteudo = arquivo.read_text(encoding="utf-8")
        todos.extend(_quebrar_em_chunks(conteudo, arquivo.name))
    return todos


def _gerar_embedding(texto: str, tipo_tarefa: str) -> list[float]:
    """Gera o vetor de embedding de um texto via API do Gemini."""
    resp = genai.embed_content(
        model=MODELO_EMBEDDING,
        content=texto,
        task_type=tipo_tarefa,
    )
    return resp["embedding"]


class BaseClinica:
    """Vector store da base de conhecimento clínica.

    Encapsula o Chroma. Tem um método pra indexar (rodar uma vez) e um pra
    buscar (usado a cada turno da conversa que precisa de contexto).
    """

    def __init__(self):
        # Import local pra quem não usa RAG não precisar do chromadb instalado.
        import chromadb
        from chromadb.config import Settings

        # Desliga a telemetria do Chroma. Ela não afeta o funcionamento, mas
        # fica tentando enviar estatística de uso e enche o terminal de
        # "Failed to send telemetry event". Aqui a gente silencia isso.
        self._cliente = chromadb.PersistentClient(
            path=str(DIR_VECTORSTORE),
            settings=Settings(anonymized_telemetry=False),
        )
        self._colecao = self._cliente.get_or_create_collection(
            name=NOME_COLECAO,
            metadata={"hnsw:space": "cosine"},
        )

    def indexar(self, forcar: bool = False) -> int:
        """Indexa a base de conhecimento no vector store.

        Se já houver documentos indexados e `forcar` for False, não refaz
        (a indexação custa chamadas de embedding). Retorna quantos chunks
        ficaram indexados.
        """
        if self._colecao.count() > 0 and not forcar:
            return self._colecao.count()

        if forcar and self._colecao.count() > 0:
            # Recria a coleção zerada.
            self._cliente.delete_collection(NOME_COLECAO)
            self._colecao = self._cliente.get_or_create_collection(
                name=NOME_COLECAO, metadata={"hnsw:space": "cosine"}
            )

        chunks = carregar_documentos()
        for i, chunk in enumerate(chunks):
            vetor = _gerar_embedding(chunk["texto"], "retrieval_document")
            self._colecao.add(
                ids=[f"chunk_{i}"],
                embeddings=[vetor],
                documents=[chunk["texto"]],
                metadatas=[{"fonte": chunk["fonte"]}],
            )
        return len(chunks)

    def buscar(self, pergunta: str, top_k: int = TOP_K_RETRIEVER) -> list[dict]:
        """Busca os chunks mais relevantes pra uma pergunta.

        Retorna uma lista de dicts com o texto e a fonte, do mais relevante
        pro menos. É isso que injetamos no contexto do agente.
        """
        if self._colecao.count() == 0:
            return []

        vetor_pergunta = _gerar_embedding(pergunta, "retrieval_query")
        resultado = self._colecao.query(
            query_embeddings=[vetor_pergunta],
            n_results=min(top_k, self._colecao.count()),
        )

        docs = resultado.get("documents", [[]])[0]
        metas = resultado.get("metadatas", [[]])[0]
        return [
            {"texto": doc, "fonte": meta.get("fonte", "desconhecida")}
            for doc, meta in zip(docs, metas)
        ]
