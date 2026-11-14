# ──────────────────────────────────────────────
# Observabilidade como código (New Relic)
#   - Dashboard "fiap-officine — Saga de OS" (saga + saúde dos 3 serviços)
#   - Política de alertas com condições NRQL
#
# Uso (uma vez, a partir da máquina de quem tem a User API key):
#   terraform init
#   terraform apply -var="account_id=<id da conta>" -var="api_key=<NRAK-...>"
# Opcional: -var="alert_email=grupo@exemplo.com" para receber os alertas.
# ──────────────────────────────────────────────
terraform {
  required_version = ">= 1.9.0"

  required_providers {
    newrelic = {
      source  = "newrelic/newrelic"
      version = "~> 3.50"
    }
  }
}

provider "newrelic" {
  account_id = var.account_id
  api_key    = var.api_key
  region     = var.region
}

locals {
  # appName de cada serviço (NEW_RELIC_APP_NAME nos ConfigMaps)
  apps          = ["officine-os-service", "officine-billing-service", "officine-execution-service"]
  apps_nrql     = join(", ", [for a in local.apps : "'${a}'"])
  apps_filter   = "appName IN (${local.apps_nrql})"
  saga_terminal = "('COMPLETED', 'CANCELLED', 'FAILED')"
}
