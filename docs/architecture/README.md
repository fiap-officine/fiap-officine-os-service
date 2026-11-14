# Documentação de Arquitetura — Oficina Mecânica (Fase 3)

Este diretório reúne a documentação arquitetural da aplicação de gestão de
oficina mecânica, evoluída na Fase 3 para operação em nuvem com autenticação
serverless, banco gerenciado, cluster Kubernetes escalável, observabilidade e
CI/CD segregado por repositório.

> **Nuvem de referência:** AWS. A justificativa formal está na
> [RFC-001](rfc/RFC-001-escolha-nuvem.md). Todo o desenho se traduz de forma
> equivalente para GCP/Azure (API Gateway → Apigee/APIM, Lambda → Cloud
> Functions/Azure Functions, RDS → Cloud SQL/Azure Database, EKS → GKE/AKS).

## Índice

| Documento | Conteúdo |
|---|---|
| [Modelo de Dados](data-model.md) | Justificativa do banco, diagrama ER e relacionamentos |
| [ADRs](adr/README.md) | Decisões arquiteturais permanentes |
| [RFCs](rfc/README.md) | Decisões técnicas em discussão/proposta |

---

## 1. Visão geral

A aplicação é um sistema de gestão de ordens de serviço (OS) para uma rede de
oficinas com múltiplas unidades. O núcleo de negócio (API + worker) roda em
Kubernetes; a autenticação de clientes por CPF é feita de forma **serverless**
(fora do cluster) e todo o tráfego externo entra por um **API Gateway** único.

Componentes principais:

- **API Gateway** — ponto único de entrada, roteamento e proteção das rotas
  sensíveis (ver [ADR-003](adr/ADR-003-api-gateway-auth-serverless.md)).
- **Função Serverless de Autenticação (Lambda)** — valida o CPF, consulta a
  existência/status do cliente no banco e emite um JWT.
- **Aplicação principal (FastAPI)** — regras de negócio de OS, clientes,
  veículos, serviços e peças; roda em Kubernetes com HPA.
- **Worker de notificações** — consome eventos da fila (Redis) e dispara
  notificações de forma assíncrona.
- **Banco de dados gerenciado (RDS PostgreSQL)** — persistência transacional
  (ver [RFC-002](rfc/RFC-002-banco-de-dados.md) e [ADR-005](adr/ADR-005-banco-gerenciado.md)).
- **Observabilidade (New Relic)** — logs estruturados, métricas, APM e alertas
  (ver [RFC-004](rfc/RFC-004-observabilidade.md)).

---

## 2. Diagrama de Componentes (visão de nuvem)

```mermaid
flowchart TB
    subgraph Client["Cliente / Front-end"]
        U["Cliente da oficina<br/>(navegador / app)"]
        ADM["Operador / Admin"]
    end

    subgraph AWS["Nuvem (AWS)"]
        APIGW["API Gateway HTTP v2<br/>(entrada única + Lambda Authorizer JWT)"]

        subgraph Serverless["Camada Serverless"]
            LAMBDA["Lambda: Auth por CPF<br/>valida CPF · consulta cliente · emite JWT"]
        end

        subgraph K8S["Cluster Kubernetes (K3s em EC2)"]
            ING["Ingress Controller"]
            API["Deployment: API FastAPI<br/>+ HPA (CPU/memória)"]
            WORKER["Deployment: Worker<br/>(consumidor de notificações)"]
            NRAGENT["DaemonSet: New Relic Infra Agent"]
        end

        subgraph Data["Dados gerenciados"]
            RDS[("RDS PostgreSQL<br/>Multi-AZ")]
            REDIS[("Redis 7<br/>fila de notificações")]
        end
    end

    subgraph Obs["Observabilidade"]
        NR["New Relic<br/>Logs · Métricas · APM · Alertas · Dashboards NRQL"]
    end

    U -->|"POST /auth (CPF)"| APIGW
    U -->|"Rotas protegidas + JWT"| APIGW
    ADM -->|"Rotas admin + JWT"| APIGW

    APIGW -->|"autenticação"| LAMBDA
    APIGW -->|"tráfego autorizado"| ING
    ING --> API

    LAMBDA -->|"consulta cliente/status"| RDS
    API --> RDS
    API -->|"publica evento"| REDIS
    WORKER -->|"consome evento"| REDIS

    API -.->|"logs JSON + traces + métricas"| NRAGENT
    WORKER -.-> NRAGENT
    LAMBDA -.->|"logs/métricas"| NR
    NRAGENT --> NR
    APIGW -.->|"métricas de latência"| NR
```

---

## 3. Diagrama de Sequência — Autenticação por CPF

Fluxo serverless de autenticação. O cliente informa o CPF; a função valida o
documento, confirma a existência e o status na base e devolve um JWT usado nas
rotas protegidas.

```mermaid
sequenceDiagram
    autonumber
    actor C as Cliente
    participant GW as API Gateway
    participant L as Lambda (Auth CPF)
    participant DB as RDS PostgreSQL

    C->>GW: POST /auth { cpf }
    GW->>L: Invoca função de autenticação
    L->>L: Valida formato e dígitos do CPF
    alt CPF inválido
        L-->>GW: 400 CPF inválido
        GW-->>C: 400 Bad Request
    else CPF válido
        L->>DB: SELECT cliente WHERE cpf_cnpj = :cpf
        alt Cliente não existe ou inativo
            DB-->>L: vazio / ativo = false
            L-->>GW: 401 Cliente não autorizado
            GW-->>C: 401 Unauthorized
        else Cliente existe e ativo
            DB-->>L: dados do cliente (id, nome, ativo)
            L->>L: Gera JWT (sub, exp) assinado
            L-->>GW: 200 { access_token, token_type }
            GW-->>C: 200 { access_token }
        end
    end

    Note over C,GW: Requisições seguintes enviam Authorization: Bearer <JWT>
    C->>GW: GET /api/v1/... + Bearer JWT
    GW->>GW: Authorizer valida assinatura e expiração do JWT
    GW->>C: Encaminha para a aplicação (se válido) ou 401
```

---

## 4. Diagrama de Sequência — Abertura de Ordem de Serviço

Fluxo de negócio de criação de uma OS já autenticado, incluindo cálculo
automático de orçamento e notificação assíncrona via fila.

```mermaid
sequenceDiagram
    autonumber
    actor OP as Operador (autenticado)
    participant GW as API Gateway
    participant API as API FastAPI (K3s)
    participant DB as RDS PostgreSQL
    participant Q as Redis (fila)
    participant W as Worker
    participant NR as New Relic

    OP->>GW: POST /api/v1/ordens-servico + Bearer JWT
    GW->>GW: Authorizer valida JWT
    GW->>API: Encaminha requisição autorizada
    API->>DB: Valida cliente e veículo
    API->>DB: Cria OS (status = recebida)
    API->>DB: Insere itens (serviços/peças) e calcula valor_total
    API->>DB: Registra histórico de status
    API->>Q: Publica evento "OS criada"
    API-->>GW: 201 Created (OS + orçamento)
    GW-->>OP: 201 Created
    Q-->>W: Entrega evento
    W->>W: Processa e envia notificação
    API-.->>NR: Log JSON + trace (correlation-id)
    W-.->>NR: Log JSON do processamento
```

---

## 5. Fluxo de status da OS

Máquina de estados implementada em `app/domain/enums.py` (`TRANSICOES_VALIDAS`).
Transições fora deste grafo são rejeitadas pela camada de serviço.

```mermaid
stateDiagram-v2
    [*] --> recebida
    recebida --> em_diagnostico
    recebida --> cancelada
    em_diagnostico --> aguardando_aprovacao
    em_diagnostico --> cancelada
    aguardando_aprovacao --> em_execucao
    aguardando_aprovacao --> cancelada
    em_execucao --> finalizada
    finalizada --> entregue
    entregue --> [*]
    cancelada --> [*]
```

---

## 6. Rastreabilidade requisito → documento

| Requisito do enunciado (Fase 3) | Onde é atendido |
|---|---|
| API Gateway para roteamento/controle | [ADR-003](adr/ADR-003-api-gateway-auth-serverless.md), §2 |
| Function serverless de autenticação por CPF | [RFC-003](rfc/RFC-003-autenticacao-cpf.md), §3 |
| Banco de dados gerenciado | [RFC-002](rfc/RFC-002-banco-de-dados.md), [ADR-005](adr/ADR-005-banco-gerenciado.md) |
| Cluster Kubernetes escalável (HPA) | [ADR-002](adr/ADR-002-hpa-escalabilidade.md) |
| Terraform / IaC e 4 repositórios | [ADR-004](adr/ADR-004-repositorios-cicd.md) |
| Monitoramento e observabilidade | [RFC-004](rfc/RFC-004-observabilidade.md) |
| Padrão de comunicação | [ADR-001](adr/ADR-001-padrao-comunicacao.md) |
| Diagramas de componentes e sequência | Este documento, §2–§4 |
| Justificativa do banco + modelo ER | [data-model.md](data-model.md) |
