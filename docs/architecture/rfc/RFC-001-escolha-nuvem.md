# RFC-001 — Escolha do provedor de nuvem

- **Status:** Aceita
- **Data:** 2025-07
- **Autores:** Grupo 123
- **Consolida em:** [ADR-003](../adr/ADR-003-api-gateway-auth-serverless.md), [ADR-004](../adr/ADR-004-repositorios-cicd.md), [ADR-005](../adr/ADR-005-banco-gerenciado.md)

## 1. Resumo

Propõe-se adotar a **AWS** como provedor de nuvem para hospedar o cluster
Kubernetes, o API Gateway, a função serverless de autenticação e o banco de
dados gerenciado.

## 2. Motivação

A Fase 3 dá **livre escolha de nuvem**, mas exige um conjunto coeso de serviços:
API Gateway, função serverless, banco gerenciado, cluster Kubernetes escalável e
provisionamento por Terraform. A decisão precisa garantir que todas essas peças
tenham serviço gerenciado maduro, boa integração entre si e com Terraform, e
ferramental de observabilidade.

## 3. Proposta

Mapeamento dos requisitos para serviços AWS:

| Requisito | Serviço AWS |
|---|---|
| API Gateway | **Amazon API Gateway (HTTP API v2)** |
| Função serverless de autenticação | **AWS Lambda** |
| Banco de dados gerenciado | **Amazon RDS (PostgreSQL)** |
| Cluster Kubernetes escalável | **K3s em EC2** (free tier) + HPA |
| Fila de notificações | **Redis 7** (in-cluster) |
| Segredos | **AWS Secrets Manager** |
| IaC | **Terraform** (provider AWS oficial e maduro) |
| Observabilidade | **New Relic** integrado (ver RFC-004) |

## 4. Alternativas consideradas

- **Google Cloud (GKE + Cloud Functions + Apigee + Cloud SQL):** stack
  equivalente e forte em Kubernetes; preterido por familiaridade da equipe e
  amplitude do ecossistema/documentação da AWS.
- **Azure (AKS + Azure Functions + APIM + Azure Database):** igualmente capaz;
  mesma linha de decisão.
- **Multi-cloud:** descartado por complexidade desproporcional ao escopo.

O desenho é **portável**: cada serviço tem equivalente direto nas outras nuvens,
então a decisão não amarra o domínio a AWS além da camada de infraestrutura.

## 5. Riscos e mitigação

- **Vendor lock-in:** mitigado por Terraform (infra reprovisionável) e por manter
  a aplicação em contêineres Kubernetes (portáveis) e PostgreSQL padrão.
- **Custo:** mitigado por HPA (ADR-002), banco corretamente dimensionado e
  serverless por uso na autenticação.

## 6. Decisão

**AWS aprovada** como provedor de referência. Consolidada nos ADRs 003, 004 e
005.
