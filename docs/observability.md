# Observabilidade distribuída (Fase 4)

Reaproveita a stack da Fase 3 (New Relic APM, logs JSON, correlation-id,
DaemonSet de infraestrutura) e acrescenta rastreamento da saga entre os três
microsserviços.

## 1. Distributed tracing atravessando o SQS

- **Publish** ([app/messaging/outbox.py](../app/messaging/outbox.py)): ao gravar no
  outbox, `newrelic.agent.insert_distributed_trace_headers()` preenche o campo
  `trace` do envelope (`newrelic`, `traceparent`, `tracestate`).
- **Consume** ([app/messaging/consumer.py](../app/messaging/consumer.py)): cada
  mensagem é processada dentro de `newrelic.agent.BackgroundTask` e chama
  `accept_distributed_trace_headers(headers, transport_type="Queue")`.
- Resultado: um único trace `OS → Billing → OS → Execution` no Distributed
  Tracing / Service Map. Cada serviço usa `NEW_RELIC_APP_NAME` próprio
  (`officine-os-service`, `officine-billing-service`, `officine-execution-service`).

## 2. Logs estruturados

Todos os logs (JSON, stdout) carregam `correlation_id`, `saga_id`, `os_id`,
`message_id`, `message_type` e `trace_id`/`span_id` (logs in context). Filtro no
New Relic Logs: `saga_id:"<uuid>"` mostra a saga inteira nos três serviços.

## 3. Eventos customizados

| Evento | Atributos | Emitido quando |
|---|---|---|
| `SagaStepEvent` | `saga_id, os_id, step, previous_step, duration_ms` | toda transição de estado da saga |
| `SagaCompensationEvent` | `saga_id, os_id, from_state, reason, compensations` | início da compensação |
| `SagaFailedEvent` | `saga_id, os_id, pending` | compensação esgotou as tentativas |
| `OrdemServicoEvent` | `action, os_id, status, valor_total` | OS criada/entregue |
| `MessageProcessingFailure` | `queue, error` | erro no consumer (mensagem volta para retry/DLQ) |

## 4. Dashboard "Saga de OS" (NRQL)

```sql
-- Sagas por estado final
SELECT count(*) FROM SagaStepEvent WHERE step IN ('COMPLETED','CANCELLED','FAILED') FACET step SINCE 1 day ago

-- Tempo médio em cada passo (segundos)
SELECT average(duration_ms)/1000 AS 'seg' FROM SagaStepEvent FACET previous_step SINCE 1 day ago

-- Compensações por motivo
SELECT count(*) FROM SagaCompensationEvent FACET reason SINCE 7 days ago

-- Funil da saga
SELECT funnel(saga_id, WHERE step='BUDGET_PENDING' AS 'Orçamento', WHERE step='PAYMENT_PENDING' AS 'Aprovado', WHERE step='IN_EXECUTION' AS 'Pago e agendado', WHERE step='COMPLETED' AS 'Concluído') FROM SagaStepEvent SINCE 7 days ago

-- Taxa de erro e p95 por serviço
SELECT percentage(count(*), WHERE error IS true) AS 'erro %', percentile(duration, 95) FROM Transaction WHERE appName LIKE 'officine-%' FACET appName TIMESERIES

-- Mensagens nas DLQs (integração CloudWatch -> New Relic)
SELECT latest(aws.sqs.ApproximateNumberOfMessagesVisible) FROM QueueSample WHERE aws.sqs.QueueName LIKE '%-dlq' FACET aws.sqs.QueueName
```

## 5. Alertas

| Alerta | Condição |
|---|---|
| DLQ com mensagens | `ApproximateNumberOfMessagesVisible > 0` em qualquer `*-dlq` por 5 min |
| Saga falhou | `SELECT count(*) FROM SagaFailedEvent` > 0 |
| Latência | p95 de `Transaction` por `appName` > 1s por 5 min |
| Webhook Mercado Pago | `Transaction` em `/api/v1/pagamentos/webhook` com `httpResponseCode = 401` > 0 |
| Outbox acumulando | `/health` → `services.outbox.pending` > 50 (synthetic monitor) |
