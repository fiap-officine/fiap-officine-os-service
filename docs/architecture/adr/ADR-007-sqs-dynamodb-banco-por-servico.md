# ADR-007 — SQS como broker, DynamoDB no Execution e banco por serviço

- **Status:** Aceito
- **Data:** 2026-11
- **Decisores:** Grupo 123
- **Relacionado a:** [ADR-005](ADR-005-banco-gerenciado.md), [ADR-006](ADR-006-microsservicos-saga-orquestrada.md)

## Contexto

O cluster de homologação é um único nó K3s t3.micro (1 GiB de RAM). A Fase 4
exige mensageria, ao menos um banco SQL e um NoSQL, e que nenhum serviço acesse
o banco de outro.

## Decisão

- **Amazon SQS** (standard, long polling, DLQ com `maxReceiveCount = 5`) como
  broker. LocalStack no desenvolvimento e `moto` nos testes.
- **PostgreSQL (RDS)** para OS e Billing — transações ACID para OS, saga,
  outbox e pagamentos. Uma instância Free Tier, com **bancos lógicos e usuários
  distintos** (`os_db`, `billing_db`), `CONNECT` revogado de `PUBLIC`.
- **DynamoDB** para o Execution: reserva de estoque atômica e idempotente com
  `TransactWriteItems` condicional; outbox como item na mesma transação.
- Consumer, outbox relay e varredores rodam **no mesmo processo da API**
  (`RUN_WORKERS=true`): um pod por serviço, sem Redis.
- Pods acessam SQS/DynamoDB pelo **instance profile do nó** (IMDSv2 hop limit 2);
  cada serviço anexa a sua política IAM. No EKS, trocar por IRSA.

## Consequências

- (+) Nada de broker/banco ocupando RAM do nó; serviços gerenciados.
- (+) Custo zero/irrisório no Free Tier (SQS 1M req/mês, DynamoDB on-demand).
- (−) SQS standard não garante ordem: o orquestrador tolera eventos fora de
  ordem e duplicados.
- (−) Instância RDS compartilhada (isolamento lógico, não físico). Uma segunda
  instância elimina o trade-off se houver orçamento.
- (−) No K3s, todos os pods compartilham a role do nó (privilégio mínimo por
  serviço só com IRSA no EKS).

## Alternativas consideradas

- **RabbitMQ no cluster**: UI de filas útil na demo, mas ~150–250 MiB de RAM no
  nó e operação manual.
- **Kafka**: superdimensionado para o volume e caro de operar.
- **MongoDB (Atlas M0 ou pod)**: sem transação condicional tão simples para a
  reserva e mais um fornecedor/credencial.
