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
`message_id`, `message_type` e `trace_id`/`span_id` (logs in context).

O agente encaminha os logs ao New Relic com
`application_logging.forwarding.context_data.enabled = true` e uma *record
factory* ([app/core/logging.py](../app/core/logging.py)) copia `saga_id`, `os_id`
e `correlation_id` do contexto para cada registro. No New Relic Logs:

```
context.saga_id:"<uuid da saga>"
```

mostra a saga inteira nos três serviços (o `saga_id` está em
`GET /api/v1/ordens-servico/{id}/saga`).

## 3. Eventos customizados

| Evento | Atributos | Emitido quando |
|---|---|---|
| `SagaStepEvent` | `saga_id, os_id, step, previous_step, duration_ms` | toda transição de estado da saga |
| `SagaCompensationEvent` | `saga_id, os_id, from_state, reason, compensations` | início da compensação |
| `SagaFailedEvent` | `saga_id, os_id, pending` | compensação esgotou as tentativas |
| `OrdemServicoEvent` | `action, os_id, status, valor_total` | OS criada/entregue |
| `OrcamentoEvent` (Billing) | `action, orcamento_id` | orçamento gerado/aprovado/recusado |
| `PagamentoEvent` (Billing) | `action, pagamento_id` | pagamento aprovado/recusado/estornado/estorno automático |
| `WebhookRejected` (Billing) | `reason, data_id` | notificação do Mercado Pago com assinatura inválida |
| `ExecucaoEvent` (Execution) | `action, os_id` | OS agendada, reserva liberada, diagnóstico/reparo/finalização |
| `MessageProcessingFailure` | `queue, error` | erro no consumer (mensagem volta para retry/DLQ) |
| `MessageRejected` | `reason` | mensagem inválida (fora do contrato) |

## 4. Dashboard e alertas como código

[observability/newrelic/](../observability/newrelic/) (Terraform, provider
`newrelic/newrelic`) cria:

- **Dashboard "fiap-officine — Saga de OS"**, com duas páginas:
  - *Saga*: sagas iniciadas/concluídas/canceladas/falhas, estado final, funil,
    tempo médio por passo, transições ao longo do tempo, compensações por
    motivo, últimas compensações e sagas em `FAILED`.
  - *Serviços*: throughput, latência p95 e taxa de erro por serviço, falhas de
    processamento de mensagens, pagamentos, webhooks rejeitados e mensagens
    nas DLQs.
- **Política de alertas "fiap-officine — Saga de OS"**:

| Alerta | Condição (NRQL) | Severidade |
|---|---|---|
| Saga falhou | `count(*) FROM SagaFailedEvent` > 0 | crítico |
| Mensagens na DLQ | `max(aws.sqs.ApproximateNumberOfMessagesVisible)` em `*-dlq` > 0 por 5 min | crítico |
| Falhas no processamento de mensagens | `count(*) FROM MessageProcessingFailure` > 5 em 5 min | aviso |
| Latência p95 alta | `percentile(duration, 95)` por serviço > 1 s por 5 min | crítico |
| Taxa de erro | `percentage(count(*), WHERE error IS true)` por serviço > 5% por 5 min | crítico |
| Webhook Mercado Pago rejeitado | `count(*) FROM WebhookRejected` > 0 | aviso |

Aplicar (uma vez, com uma User API key):

```bash
cd observability/newrelic
terraform init
terraform apply -var="account_id=<id da conta>" -var="api_key=<NRAK-...>"                 -var="alert_email=<e-mail do grupo>"   # opcional
```

Os gráficos e o alerta de DLQ dependem da **integração AWS → New Relic**
(CloudWatch Metric Streams ou polling da integração SQS/DynamoDB), configurada
no painel do New Relic em *Infrastructure → AWS*.
