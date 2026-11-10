# ADR-006 — Microsserviços com Saga orquestrada

- **Status:** Aceito
- **Data:** 2026-11
- **Decisores:** Grupo 123
- **Substitui parcialmente:** [ADR-001](ADR-001-padrao-comunicacao.md) (fila Redis de notificações), [ADR-004](ADR-004-repositorios-cicd.md) (quatro repositórios)

## Contexto

A Fase 4 exige dividir o monólito em pelo menos três microsserviços, cada um com
repositório, infraestrutura e banco próprios, e coordenar o fluxo da OS
(orçamento → aprovação → pagamento → execução) com **Saga Pattern** e
compensação. O fluxo tem esperas humanas longas (aprovação do cliente,
pagamento no Mercado Pago) e um ponto sem volta (início do reparo).

## Decisão

1. **Três serviços**: `os-service` (OS, clientes, veículos, catálogo e
   orquestrador), `billing-service` (orçamento e Mercado Pago) e
   `execution-service` (estoque, fila e reparo).
2. **Saga orquestrada** no `os-service`, com estado persistido
   (`saga_instances`, `saga_log`) e tabela de transição declarativa
   `(estado, mensagem) → ação`.
3. Comunicação **assíncrona por comandos/respostas** em Amazon SQS (uma fila de
   entrada por serviço + DLQ); REST síncrono só para ações do usuário
   (aprovar orçamento, ações do mecânico) e para a Lambda consultar clientes.
4. **Transactional Outbox** nos produtores e **consumidores idempotentes**
   (`message_id`) em todos os serviços.
5. **Timeouts** por passo (`deadline_at`) e varredor que dispara compensação;
   compensações retentadas até um limite, depois a saga vai para `FAILED`.
6. **Pivô explícito** em `ReparoIniciado`: depois dele não há compensação.

## Consequências

- (+) Ordem de compensação em um único lugar, testável (BDD cobre fluxo feliz,
  recusa, estoque insuficiente com estorno, timeout, cancelamento e duplicatas).
- (+) Estado da saga consultável (`GET /ordens-servico/{id}/saga`) e
  observável (eventos `SagaStepEvent`, `SagaCompensationEvent`).
- (+) Billing e Execution não se conhecem; podem evoluir e escalar sozinhos.
- (−) O orquestrador concentra lógica e conhece os contratos dos participantes
  (mitigado por contratos versionados em `docs/contracts`).
- (−) Consistência eventual: a OS passa por estados intermediários
  (`aguardando_*`, `em_compensacao`).

## Alternativas consideradas

- **Saga coreografada**: menos acoplamento ao orquestrador, mas compensações
  espalhadas por handlers de eventos e difícil responder "em que passo está a
  OS?"; esperas longas exigiriam timers distribuídos.
- **2PC/XA**: inviável entre PostgreSQL, DynamoDB e Mercado Pago.
