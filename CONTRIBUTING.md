# Como contribuir

Esse guia é pra quem for mexer no BluaDiagnostics depois da gente, seja
um colega de grupo ou alguém que pegou o projeto pra continuar. A ideia é
deixar registrado como a gente organizou as coisas pra manter tudo
coerente.

## Antes de começar

1. Clona o repositório e entra na pasta.
2. Instala as dependências: `pip install -r requirements.txt`
3. Copia o `.env.example` pra `.env` e coloca sua chave do Gemini.
4. Roda os testes pra ver se está tudo certo: `pytest tests/`

## Como o projeto está organizado

A gente separou o código por responsabilidade, pra ficar fácil de achar
as coisas:

- `src/agents/` - os agentes (supervisor, triagem, prescrição, escalada)
  e os prompts de cada um.
- `src/tools/` - as ferramentas que os agentes chamam (histórico,
  interações, agendamento, wearable).
- `src/rag/` - o pipeline de RAG (chunking, embeddings, busca).
- `src/graph/` - o grafo LangGraph e os guardrails de segurança.
- `evals/` - a suite de avaliação automatizada.
- `tests/` - os testes unitários.
- `data/knowledge_base/` - os documentos da base de conhecimento.

## Regras que a gente seguiu

- **Nada de chave no código.** A API key vem sempre do `.env` ou de
  variável de ambiente. O `.env` está no `.gitignore` e nunca deve ser
  commitado.
- **Parâmetros centralizados.** Modelo, temperatura, tamanho de chunk,
  tudo fica em `src/config.py`. Não espalha número mágico pelo código.
- **Comentários em português, simples.** A ideia é qualquer um do grupo
  entender depois.
- **Teste antes de subir.** Se mexer numa tool ou num guardrail, roda o
  `pytest tests/` pra garantir que não quebrou nada.

## Pra adicionar coisas novas

- **Nova tool:** cria a função em `src/tools/clinical_tools.py` com uma
  docstring bem detalhada (é o que o modelo lê pra decidir quando usar),
  e adiciona ela na lista do agente certo em `src/agents/specialists.py`.
- **Novo documento na base:** joga o `.md` em `data/knowledge_base/` e
  roda o sistema uma vez pra reindexar.
- **Nova regra de segurança:** mexe em `src/graph/guardrails.py` e
  adiciona um teste correspondente em `tests/test_sistema.py`.

## Commits

Mensagens curtas e diretas, descrevendo o que mudou. Exemplo:
"Adiciona tool de checagem de sintomas" ou "Corrige roteamento do
supervisor".
