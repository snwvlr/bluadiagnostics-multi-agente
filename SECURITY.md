# Política de Segurança

O BluaDiagnostics lida com um contexto sensível (saúde), então a gente
levou a segurança a sério mesmo sendo um projeto acadêmico. Aqui está o
que a gente fez e como reportar um problema.

## Como reportar uma vulnerabilidade

Se você achar uma falha de segurança, por favor não abre uma issue
pública. Manda uma mensagem direto pra alguém do grupo descrevendo o
problema. A gente avalia e corrige o quanto antes.

## Cuidados que a gente tomou

### Chaves e segredos
- Nenhuma API key fica no código ou no histórico do Git. A chave vem
  sempre de variável de ambiente ou do arquivo `.env`.
- O `.env` está no `.gitignore`, então nunca é enviado pro repositório.
- Tem um `.env.example` só de modelo, sem chave de verdade.

### Dados de paciente
- Todos os dados de paciente no projeto são fictícios (a Maria e o
  Carlos foram inventados pra demonstração).
- Em um cenário real, dados de saúde são protegidos pela LGPD. Por isso,
  no roadmap do relatório técnico a gente aponta que a versão de produção
  deveria rodar o modelo localmente (pra os dados não saírem da infra da
  operadora) e pseudonimizar qualquer dado antes de mandar pra fora.

### Limites do sistema (segurança clínica)
O sistema foi desenhado pra nunca passar do papel dele:
- Nunca dá diagnóstico definitivo nem receita medicamento.
- Tem guardrails que detectam emergências e mandam pro SAMU 192
  automaticamente, antes mesmo de o modelo responder.
- Recusa pedidos fora do escopo de saúde.
- Resiste a tentativas de "jailbreak" (quando alguém tenta fazer ele
  ignorar as regras).

Esses limites são testados na suite de evals (categorias `red_flag` e
`jailbreak`).

## O que NÃO usar em produção sem revisão

Esse é um projeto acadêmico. Antes de qualquer uso real, seria preciso:
- Validação clínica formal com profissionais de saúde.
- Auditoria de segurança e de conformidade com a LGPD.
- Substituir as ferramentas simuladas por integrações reais com
  autenticação adequada.

## Versões

Esse projeto é uma entrega acadêmica e não tem versões com suporte
contínuo. As dependências estão travadas no `requirements.txt`.
