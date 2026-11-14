# Architecture Decision Records (ADRs)

ADRs registram **decisões arquiteturais permanentes** — escolhas estruturais que
moldam o sistema e cujo custo de reversão é alto. Cada ADR segue o formato:
Contexto, Decisão, Consequências e Alternativas consideradas.

> Diferença para RFCs: a **RFC** propõe e discute uma decisão técnica (ex.: qual
> nuvem, qual banco); o **ADR** consolida a decisão arquitetural e suas
> implicações estruturais (ex.: padrão de comunicação, uso de HPA). RFCs desta
> pasta vizinha alimentam os ADRs correspondentes.

| ADR | Título | Status |
|---|---|---|
| [ADR-001](ADR-001-padrao-comunicacao.md) | Padrão de comunicação entre componentes | Aceito |
| [ADR-002](ADR-002-hpa-escalabilidade.md) | Uso de HPA para escalabilidade horizontal | Aceito |
| [ADR-003](ADR-003-api-gateway-auth-serverless.md) | API Gateway como entrada única e autenticação serverless | Aceito |
| [ADR-004](ADR-004-repositorios-cicd.md) | Segregação em quatro repositórios com CI/CD independente | Aceito |
| [ADR-005](ADR-005-banco-gerenciado.md) | Banco de dados gerenciado desacoplado do cluster | Aceito |
| [ADR-006](ADR-006-microsservicos-saga-orquestrada.md) | Microsserviços com Saga orquestrada (Fase 4) | Aceito |
| [ADR-007](ADR-007-sqs-dynamodb-banco-por-servico.md) | SQS como broker, DynamoDB no Execution e banco por serviço (Fase 4) | Aceito |

## Convenção de status

`Proposto` → `Aceito` → (`Substituído por ADR-XXX` | `Descontinuado`)
