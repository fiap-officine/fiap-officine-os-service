resource "newrelic_alert_policy" "saga" {
  name                = "fiap-officine — Saga de OS"
  incident_preference = "PER_CONDITION_AND_TARGET"
}

# Saga em FAILED: a compensação esgotou as tentativas (intervenção manual)
resource "newrelic_nrql_alert_condition" "saga_failed" {
  policy_id          = newrelic_alert_policy.saga.id
  name               = "Saga falhou (compensação esgotada)"
  description        = "Uma OS ficou com a saga em FAILED. Ver SagaFailedEvent e GET /ordens-servico/{id}/saga."
  type               = "static"
  aggregation_window = 60
  aggregation_method = "event_flow"
  aggregation_delay  = 120

  nrql {
    query = "SELECT count(*) FROM SagaFailedEvent"
  }

  critical {
    operator              = "above"
    threshold             = 0
    threshold_duration    = 60
    threshold_occurrences = "at_least_once"
  }
}

# Mensagens chegando na DLQ (depende da integração AWS → New Relic)
resource "newrelic_nrql_alert_condition" "dlq" {
  policy_id          = newrelic_alert_policy.saga.id
  name               = "Mensagens na DLQ"
  description        = "Alguma fila *-dlq tem mensagens: um consumer falhou 5 vezes seguidas."
  type               = "static"
  aggregation_window = 300
  aggregation_method = "event_timer"
  aggregation_timer  = 300

  nrql {
    query = "SELECT max(aws.sqs.ApproximateNumberOfMessagesVisible) FROM QueueSample WHERE aws.sqs.QueueName LIKE '%-dlq' FACET aws.sqs.QueueName"
  }

  critical {
    operator              = "above"
    threshold             = 0
    threshold_duration    = 300
    threshold_occurrences = "at_least_once"
  }
}

# Erros repetidos no processamento de mensagens (antes de irem para a DLQ)
resource "newrelic_nrql_alert_condition" "message_failures" {
  policy_id          = newrelic_alert_policy.saga.id
  name               = "Falhas no processamento de mensagens"
  type               = "static"
  aggregation_window = 300
  aggregation_method = "event_flow"
  aggregation_delay  = 120

  nrql {
    query = "SELECT count(*) FROM MessageProcessingFailure FACET appName"
  }

  warning {
    operator              = "above"
    threshold             = 5
    threshold_duration    = 300
    threshold_occurrences = "at_least_once"
  }
}

# Latência p95 por serviço
resource "newrelic_nrql_alert_condition" "latency" {
  policy_id          = newrelic_alert_policy.saga.id
  name               = "Latência p95 alta"
  type               = "static"
  aggregation_window = 60
  aggregation_method = "event_flow"
  aggregation_delay  = 120

  nrql {
    query = "SELECT percentile(duration, 95) FROM Transaction WHERE ${local.apps_filter} FACET appName"
  }

  critical {
    operator              = "above"
    threshold             = var.latency_p95_seconds
    threshold_duration    = 300
    threshold_occurrences = "all"
  }
}

# Taxa de erro por serviço
resource "newrelic_nrql_alert_condition" "error_rate" {
  policy_id          = newrelic_alert_policy.saga.id
  name               = "Taxa de erro acima de 5%"
  type               = "static"
  aggregation_window = 60
  aggregation_method = "event_flow"
  aggregation_delay  = 120

  nrql {
    query = "SELECT percentage(count(*), WHERE error IS true) FROM Transaction WHERE ${local.apps_filter} FACET appName"
  }

  critical {
    operator              = "above"
    threshold             = 5
    threshold_duration    = 300
    threshold_occurrences = "all"
  }
}

# Webhook do Mercado Pago com assinatura inválida
resource "newrelic_nrql_alert_condition" "webhook_rejected" {
  policy_id          = newrelic_alert_policy.saga.id
  name               = "Webhook Mercado Pago rejeitado"
  description        = "Notificação com x-signature inválida: segredo errado ou tentativa de fraude."
  type               = "static"
  aggregation_window = 60
  aggregation_method = "event_flow"
  aggregation_delay  = 120

  nrql {
    query = "SELECT count(*) FROM WebhookRejected"
  }

  warning {
    operator              = "above"
    threshold             = 0
    threshold_duration    = 60
    threshold_occurrences = "at_least_once"
  }
}

# ── Notificação por e-mail (opcional) ──
resource "newrelic_notification_destination" "email" {
  count = var.alert_email == "" ? 0 : 1
  name  = "fiap-officine — e-mail do grupo"
  type  = "EMAIL"

  property {
    key   = "email"
    value = var.alert_email
  }
}

resource "newrelic_notification_channel" "email" {
  count          = var.alert_email == "" ? 0 : 1
  name           = "fiap-officine — alertas da saga"
  type           = "EMAIL"
  product        = "IINT"
  destination_id = newrelic_notification_destination.email[0].id

  property {
    key   = "subject"
    value = "[fiap-officine] {{issueTitle}}"
  }
}

resource "newrelic_workflow" "email" {
  count                 = var.alert_email == "" ? 0 : 1
  name                  = "fiap-officine — alertas da saga"
  muting_rules_handling = "NOTIFY_ALL_ISSUES"

  issues_filter {
    name = "Política da saga"
    type = "FILTER"

    predicate {
      attribute = "labels.policyIds"
      operator  = "EXACTLY_MATCHES"
      values    = [newrelic_alert_policy.saga.id]
    }
  }

  destination {
    channel_id = newrelic_notification_channel.email[0].id
  }
}
