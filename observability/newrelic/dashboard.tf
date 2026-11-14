resource "newrelic_one_dashboard" "saga" {
  name        = "fiap-officine — Saga de OS"
  permissions = "public_read_only"

  # ── Página 1: a saga de ponta a ponta ──
  page {
    name = "Saga"

    widget_billboard {
      title  = "Sagas nas últimas 24h"
      row    = 1
      column = 1
      width  = 6
      height = 3
      nrql_query {
        query = <<-NRQL
          SELECT filter(uniqueCount(saga_id), WHERE step = 'BUDGET_PENDING') AS 'Iniciadas',
                 filter(uniqueCount(saga_id), WHERE step = 'COMPLETED') AS 'Concluídas',
                 filter(uniqueCount(saga_id), WHERE step = 'CANCELLED') AS 'Canceladas (compensadas)',
                 filter(uniqueCount(saga_id), WHERE step = 'FAILED') AS 'Falharam'
          FROM SagaStepEvent SINCE 1 day ago
        NRQL
      }
    }

    widget_pie {
      title  = "Estado final das sagas"
      row    = 1
      column = 7
      width  = 6
      height = 3
      nrql_query {
        query = "SELECT uniqueCount(saga_id) FROM SagaStepEvent WHERE step IN ${local.saga_terminal} FACET step SINCE 7 days ago"
      }
    }

    widget_funnel {
      title  = "Funil da saga"
      row    = 4
      column = 1
      width  = 6
      height = 3
      nrql_query {
        query = <<-NRQL
          SELECT funnel(saga_id,
                        WHERE step = 'BUDGET_PENDING' AS 'Orçamento solicitado',
                        WHERE step = 'APPROVAL_PENDING' AS 'Aguardando aprovação',
                        WHERE step = 'PAYMENT_PENDING' AS 'Aprovado',
                        WHERE step = 'IN_EXECUTION' AS 'Pago e na fila',
                        WHERE step = 'COMPLETED' AS 'Concluído')
          FROM SagaStepEvent SINCE 7 days ago
        NRQL
      }
    }

    widget_bar {
      title  = "Tempo médio em cada passo (s)"
      row    = 4
      column = 7
      width  = 6
      height = 3
      nrql_query {
        query = "SELECT average(duration_ms) / 1000 AS 'segundos' FROM SagaStepEvent FACET previous_step SINCE 1 day ago"
      }
    }

    widget_line {
      title  = "Transições da saga por passo"
      row    = 7
      column = 1
      width  = 8
      height = 3
      nrql_query {
        query = "SELECT count(*) FROM SagaStepEvent FACET step TIMESERIES AUTO SINCE 6 hours ago"
      }
    }

    widget_table {
      title  = "Compensações por motivo"
      row    = 7
      column = 9
      width  = 4
      height = 3
      nrql_query {
        query = "SELECT count(*) AS 'compensações' FROM SagaCompensationEvent FACET reason SINCE 7 days ago"
      }
    }

    widget_table {
      title  = "Últimas compensações"
      row    = 10
      column = 1
      width  = 8
      height = 3
      nrql_query {
        query = "SELECT timestamp, os_id, saga_id, from_state, reason, compensations FROM SagaCompensationEvent SINCE 7 days ago LIMIT 20"
      }
    }

    widget_table {
      title  = "Sagas que falharam (intervenção manual)"
      row    = 10
      column = 9
      width  = 4
      height = 3
      nrql_query {
        query = "SELECT timestamp, os_id, saga_id, pending FROM SagaFailedEvent SINCE 7 days ago LIMIT 20"
      }
    }
  }

  # ── Página 2: saúde dos microsserviços ──
  page {
    name = "Serviços"

    widget_line {
      title  = "Throughput por serviço (req/min)"
      row    = 1
      column = 1
      width  = 6
      height = 3
      nrql_query {
        query = "SELECT rate(count(*), 1 minute) FROM Transaction WHERE ${local.apps_filter} FACET appName TIMESERIES AUTO SINCE 3 hours ago"
      }
    }

    widget_line {
      title  = "Latência p95 por serviço (s)"
      row    = 1
      column = 7
      width  = 6
      height = 3
      nrql_query {
        query = "SELECT percentile(duration, 95) FROM Transaction WHERE ${local.apps_filter} FACET appName TIMESERIES AUTO SINCE 3 hours ago"
      }
    }

    widget_line {
      title  = "Taxa de erro por serviço (%)"
      row    = 4
      column = 1
      width  = 6
      height = 3
      nrql_query {
        query = "SELECT percentage(count(*), WHERE error IS true) FROM Transaction WHERE ${local.apps_filter} FACET appName TIMESERIES AUTO SINCE 3 hours ago"
      }
    }

    widget_table {
      title  = "Falhas no processamento de mensagens (SQS)"
      row    = 4
      column = 7
      width  = 6
      height = 3
      nrql_query {
        query = "SELECT count(*) FROM MessageProcessingFailure FACET appName, queue SINCE 1 day ago"
      }
    }

    widget_billboard {
      title  = "Pagamentos (Mercado Pago)"
      row    = 7
      column = 1
      width  = 6
      height = 3
      nrql_query {
        query = "SELECT count(*) FROM PagamentoEvent FACET action SINCE 1 day ago"
      }
    }

    widget_table {
      title  = "Webhooks rejeitados (assinatura inválida)"
      row    = 7
      column = 7
      width  = 6
      height = 3
      nrql_query {
        query = "SELECT timestamp, reason, data_id FROM WebhookRejected SINCE 7 days ago LIMIT 20"
      }
    }

    widget_line {
      title  = "Mensagens nas DLQs (integração AWS → New Relic)"
      row    = 10
      column = 1
      width  = 12
      height = 3
      nrql_query {
        query = "SELECT max(aws.sqs.ApproximateNumberOfMessagesVisible) FROM QueueSample WHERE aws.sqs.QueueName LIKE '%-dlq' FACET aws.sqs.QueueName TIMESERIES AUTO SINCE 1 day ago"
      }
    }
  }
}

output "dashboard_url" {
  description = "Link do dashboard da saga"
  value       = newrelic_one_dashboard.saga.permalink
}
