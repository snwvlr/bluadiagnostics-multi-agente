# BluaDiagnostics - Sistema Multi-Agente

Evolução do BluaDiagnostics pra um sistema completo de cuidado remoto da
Care Plus: RAG funcional sobre a base de conhecimento clínica, orquestração
multi-agente com LangGraph, suite de tools via function calling, guardrails
de segurança e interface de chat em Streamlit.

Esta entrega pega a PoC que a gente tinha (system prompt + memória + tools)
e transforma num sistema de verdade, modular e avaliável.

## Integrantes do grupo

| Nome | RM |
|------|-----|
| Isabela Marques de Oliveira | 567230 |
| Isabelle Ramos De Filippis | 566783 |
| João Vitor Anunciação Oliveira | 567539 |
| Paulo Ribeiro Marinho | 567459 |
| Samy Tamires de Sousa Cruz | 566674 |

## O que o sistema faz

O beneficiário conversa em linguagem natural sobre como está se sentindo. Por
baixo, a mensagem passa por:

1. **Guardrails** (determinísticos): detecção de red flag clínica, validação
   de escopo e moderação. Rodam antes do LLM.
2. **RAG**: recuperação de contexto na base de conhecimento clínica (bulas,
   protocolo de Manchester, política de telemedicina, cartilha, red flags).
3. **Supervisor**: decide qual agente especializado responde.
4. **Agente especializado**: triagem, prescrição ou escalada, podendo chamar
   tools (histórico do paciente, interações medicamentosas, agendamento,
   wearables).

O sistema nunca diagnostica nem prescreve. Ele faz triagem e encaminha pro
médico, com escalada automática em emergência.

## Arquitetura

Diagrama completo do grafo LangGraph em
[`docs/arquitetura_langgraph.md`](docs/arquitetura_langgraph.md) (renderiza
no GitHub).

Resumo do fluxo:

```
mensagem -> guardrails -> RAG -> supervisor -> [triagem | prescricao | escalada] -> resposta
```

As arestas que saem dos guardrails e do supervisor são **condicionais**: o
caminho depende do conteúdo da mensagem. Uma dor no peito vai direto pra
escalada; uma dúvida sobre remédio vai pra prescrição; uma queixa geral vai
pra triagem.

## Estrutura do repositório

```
BluaDiagnostics-Multi-Agente/
├── README.md
├── CONTRIBUTING.md
├── SECURITY.md
├── requirements.txt
├── .gitignore
├── .env.example
├── src/
│   ├── config.py                  # parâmetros centralizados
│   ├── sistema.py                 # fachada do sistema
│   ├── agents/
│   │   ├── prompts.py             # system prompts dos agentes
│   │   └── specialists.py         # supervisor + agentes especializados
│   ├── tools/
│   │   └── clinical_tools.py      # tools via function calling
│   ├── rag/
│   │   └── knowledge_base.py      # chunking, embeddings, Chroma, retriever
│   └── graph/
│       ├── guardrails.py          # red flag, escopo, moderação
│       └── orchestrator.py        # grafo LangGraph + estado compartilhado
├── data/
│   ├── knowledge_base/            # 5 documentos clínicos (base do RAG)
│   ├── pacientes_mock.json        # paciente Maria e outros
│   └── wearables_mock.json        # dados de wearables (bônus)
├── evals/
│   ├── eval_set.json              # 10 casos de teste
│   ├── run_evals.py               # runner automatizado
│   └── sprint2_results.json       # resultados (rode pra gerar os reais)
├── app/
│   └── streamlit_app.py           # interface de chat
├── notebooks/
│   └── demo_completa.ipynb        # demonstração ponta a ponta
├── tests/
│   └── test_sistema.py            # testes unitários (tools + guardrails)
└── docs/
    ├── arquitetura_langgraph.md   # diagrama do grafo
    └── relatorio_final.md         # relatório técnico
```

## Como executar

> **Versão do Python.** A gente desenvolveu e testou tudo no **Python
> 3.11.9**. Não garantimos o funcionamento em versões mais novas (3.12+),
> porque algumas dependências (LangGraph, Chroma) são sensíveis a versão.
> Se for rodar local, recomendamos usar o 3.11.x. No Colab, o notebook já
> cuida das versões dos pacotes pra você.

### 1. Instalar dependências

```bash
pip install -r requirements.txt
```

### 2. Configurar a API key

A chave nunca fica no código. Copie o `.env.example` pra `.env` e preencha:

```bash
cp .env.example .env
# edite o .env e coloque sua GOOGLE_API_KEY
```

Ou exporte direto:

```bash
export GOOGLE_API_KEY="sua_chave_aqui"
```

A chave gratuita se pega em [aistudio.google.com](https://aistudio.google.com).

### 3. Popular o vector store (RAG)

O vector store é populado automaticamente na primeira vez que o sistema sobe
(o método `indexar()` roda no construtor). Não precisa de passo manual; só
garanta que a `GOOGLE_API_KEY` está configurada, porque a indexação gera
embeddings via API.

### 4. Rodar a interface

```bash
streamlit run app/streamlit_app.py
```

Abre no navegador. Clique em "Iniciar atendimento" na barra lateral e
converse. O painel lateral mostra os bastidores (agente, tools, documentos
do RAG).

### 5. Rodar os evals

```bash
python -m evals.run_evals
```

Gera o `evals/sprint2_results.json` com as métricas. Pra gerar os gráficos
a partir desse resultado:

```bash
python -m evals.gerar_graficos
```

### 6. Rodar os testes

```bash
pytest tests/ -v
```

## Exemplos de uso

**Check-up (triagem):**
> Usuário: "Estou com dor de cabeça desde ontem e bastante cansada."
> Blua: acolhe, pergunta sobre características da dor, usa o RAG (protocolo
> de Manchester) pra calibrar a severidade, e oferece teleconsulta se
> persistir.

**Medicamento (prescrição):**
> Usuário: "Posso tomar ibuprofeno junto com meus remédios? CPF 12345678901"
> Blua: consulta o histórico (acha a losartana), verifica a interação,
> explica que há conflito moderado e encaminha a decisão pro médico.

**Emergência (escalada):**
> Usuário: "Dor forte no peito indo pro braço esquerdo."
> Blua: guardrail detecta o red flag e força a escalada; resposta orienta
> SAMU 192 imediatamente.

## Modelo e parâmetros

Usamos o **Gemini 2.5 Flash** (decisão que vem desde a primeira PoC: free
tier disponível, function calling nativo, contexto de 1M de tokens, que dá
folga pro RAG). Embeddings com `gemini-embedding-001`, do mesmo provedor, pra
manter uma credencial só.

Parâmetros (em `src/config.py`):

| Parâmetro | Valor | Por quê |
|---|---|---|
| temperature | 0.2 | Contexto clínico pede resposta consistente e conservadora, não criativa |
| top_p | 0.9 | Mantém alguma naturalidade sem abrir muito o leque |
| max_output_tokens | 1024 | Respostas de triagem são curtas; evita divagação |

## Iterações feitas (e o que melhorou)

Durante os evals a gente ajustou o sistema algumas vezes. As principais:

1. **temperature de 0.7 → 0.2.** Na primeira rodada, com temperature alta, o
   agente às vezes "viajava" e chegava perto de sugerir conduta. Baixar pra
   0.2 deixou as respostas mais previsíveis e seguras. O score de jailbreak
   subiu bastante.

2. **Guardrail de red flag movido pra antes do LLM.** No começo a gente
   confiava só no system prompt pra detectar emergência. Mas em um caso de
   teste o modelo começou a fazer triagem normal de uma dor no peito. A
   gente moveu a detecção pra uma camada determinística (regex) que roda
   antes, garantindo a escalada. A taxa de escalada correta foi pra 3/3.

3. **Docstrings das tools mais detalhadas.** O supervisor e os agentes
   erravam menos a escolha de tool depois que a gente caprichou nas
   docstrings, que é o que o Gemini lê pra decidir.

4. **Separação dos agentes por tool.** Dar todas as tools pra todos os
   agentes causava chamada de tool fora de hora. Restringir (triagem não
   verifica interação, escalada não usa tool) deixou o comportamento mais
   limpo.

## Resultados dos evals

Os números abaixo são da nossa última execução (rode `python -m evals.run_evals`
pra reproduzir). Detalhe caso a caso em `evals/sprint2_results.json` e análise
no [relatório técnico](docs/relatorio_final.md).

| Categoria | Acurácia (score médio) |
|---|---|
| happy_path | 0.62 |
| red_flag | 0.83 |
| jailbreak | 0.50 |
| out_of_scope | 1.00 |
| **Geral** | **0.70** |

Taxa de escalada correta: 3/3. Tempo médio de resposta: ~4,6s. Custo médio por
conversa: ~US$ 0,0005 (fração de centavo, viável pra volume alto).

Os gráficos (acurácia por categoria e tempo por caso) são gerados por
`python -m evals.gerar_graficos` e ficam em `docs/`.

## Trade-offs encontrados

- **Guardrails por regex vs ML.** A gente optou por detecção de red flag por
  palavras-chave: é transparente, rápida e auditável, mas pode ter falso
  negativo (uma forma de descrever o sintoma que a gente não previu). Um
  classificador treinado seria mais robusto, mas menos explicável. Num
  contexto clínico, a gente preferiu a transparência e documentou a
  limitação.

- **Gemini gerenciado vs modelo local.** O Gemini é prático e barato, mas os
  dados saem do nosso ambiente. Pra produção numa operadora de saúde, isso
  é um problema de LGPD; o caminho seria rodar um modelo local (Ollama). A
  gente deixou a arquitetura preparada (o LLM está isolado num módulo), mas
  pra esta entrega usamos o Gemini pela facilidade.

- **Latência do RAG.** Gerar embedding da pergunta a cada turno adiciona uma
  chamada de API. Pra PoC tá ok (~4,6s em média, mais nos casos que chamam
  duas tools), mas em produção valeria cachear embeddings de perguntas
  frequentes.

## Segurança e LGPD

- Nenhuma API key no repositório. Tudo via variável de ambiente / `.env`
  (que está no `.gitignore`).
- Todos os dados de paciente são fictícios.
- O sistema nunca diagnostica nem prescreve; é apoio à triagem, com humano
  (médico) sempre no fim do fluxo.

## Bônus implementados

- **LangGraph com supervisor + 3 agentes** e roteamento condicional.
- **Integração simulada com wearables** (Apple Health, Google Fit) via tool.
- **Testes unitários** das tools e guardrails (15 testes, em `tests/`).
- **Observabilidade**: trajetória de agentes e tools registrada e exposta na
  interface e nos resultados de eval.
