output "replies_queue_url" {
  description = "URL da fila os-saga-replies"
  value       = aws_sqs_queue.replies.url
}

output "replies_queue_arn" {
  value = aws_sqs_queue.replies.arn
}

output "replies_dlq_arn" {
  description = "DLQ monitorada pelo alerta do New Relic (mensagens > 0)"
  value       = aws_sqs_queue.replies_dlq.arn
}

output "iam_policy_arn" {
  value = aws_iam_policy.os_service.arn
}
