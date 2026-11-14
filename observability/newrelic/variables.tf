variable "account_id" {
  description = "ID da conta New Relic"
  type        = number
}

variable "api_key" {
  description = "User API key do New Relic (NRAK-...)"
  type        = string
  sensitive   = true
}

variable "region" {
  description = "Região da conta New Relic (US ou EU)"
  type        = string
  default     = "US"
}

variable "alert_email" {
  description = "E-mail que recebe os alertas (vazio = só registra os incidentes no New Relic)"
  type        = string
  default     = ""
}

variable "latency_p95_seconds" {
  description = "Limite de latência p95 por serviço, em segundos"
  type        = number
  default     = 1
}
