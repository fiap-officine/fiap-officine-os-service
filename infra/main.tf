# ──────────────────────────────────────────────
# Infra própria do OS Service
#   - Fila os-saga-replies (+ DLQ) que o orquestrador consome
#   - Política IAM: consumir a própria fila e publicar comandos nas filas
#     billing-commands / execution-commands (criadas pelos repos de cada serviço)
# O banco lógico os_db é criado pelo Job k8s/jobs/db-bootstrap.yaml dentro do
# cluster (o RDS compartilhado não é acessível publicamente).
# ──────────────────────────────────────────────
terraform {
  required_version = ">= 1.9.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Backend remoto (descomente; a key é passada no init por ambiente):
  #   terraform init -backend-config="key=os-service/homolog/terraform.tfstate"
  # backend "s3" {
  #   bucket  = "fiap-officine-terraform-state"
  #   region  = "sa-east-1"
  #   encrypt = true
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      Service     = "os-service"
      ManagedBy   = "terraform"
      Repository  = "fiap-officine-os-service"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  prefix     = "${var.project}-${var.environment}"
  queue_arn  = "arn:aws:sqs:${var.aws_region}:${data.aws_caller_identity.current.account_id}"
  publish_to = [for q in ["billing-commands", "execution-commands"] : "${local.queue_arn}:${local.prefix}-${q}"]
}

# ── Fila de respostas da saga (+ DLQ) ───────────
resource "aws_sqs_queue" "replies_dlq" {
  name                      = "${local.prefix}-os-saga-replies-dlq"
  message_retention_seconds = 1209600 # 14 dias
}

resource "aws_sqs_queue" "replies" {
  name                       = "${local.prefix}-os-saga-replies"
  visibility_timeout_seconds = 30
  receive_wait_time_seconds  = 20 # long polling: menos requisições (Free Tier)
  message_retention_seconds  = 345600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.replies_dlq.arn
    maxReceiveCount     = var.max_receive_count
  })
}

resource "aws_sqs_queue_redrive_allow_policy" "replies_dlq" {
  queue_url = aws_sqs_queue.replies_dlq.id
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.replies.arn]
  })
}

# ── IAM ─────────────────────────────────────────
data "aws_iam_policy_document" "os_service" {
  statement {
    sid = "ConsumeOwnQueue"
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:ChangeMessageVisibility",
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl",
    ]
    resources = [aws_sqs_queue.replies.arn]
  }

  statement {
    sid       = "PublishSagaCommands"
    actions   = ["sqs:SendMessage", "sqs:GetQueueUrl"]
    resources = local.publish_to
  }
}

resource "aws_iam_policy" "os_service" {
  name        = "${local.prefix}-os-service"
  description = "OS Service: consome os-saga-replies e publica comandos da saga"
  policy      = data.aws_iam_policy_document.os_service.json
}

# K3s: os pods usam o instance profile do nó. (No EKS, trocar por IRSA.)
resource "aws_iam_role_policy_attachment" "node" {
  count      = var.node_role_name == "" ? 0 : 1
  role       = var.node_role_name
  policy_arn = aws_iam_policy.os_service.arn
}
