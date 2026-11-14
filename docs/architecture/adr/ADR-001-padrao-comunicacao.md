# ADR-001 — Padrão de comunicação entre componentes

- **Status:** Aceito
- **Data:** 2025-07
- **Decisores:** Grupo 123
- **Relacionado a:** [ADR-003](ADR-003-api-gateway-auth-serverless.md), [RFC-004](../rfc/RFC-004-observabilidade.md)

## Contexto

O sistema tem dois tipos de interação com naturezas distintas:

1. **Requisições de negócio** (criar OS, consultar cliente, alterar status) —
   exigem resposta imediata e síncrona ao chamador.
2. **Efeitos colaterais** (notificar cliente sobre criação/alteração de OS) —
   não precisam bloquear a resposta e podem falhar/reprocessar sem impactar a
   operação principal.

Tratar os dois casos com o mesmo mecanismo síncrono acoplaria a latência da API
à disponibilidade do canal de notificação, prejudicando o objetivo de alta
disponibilidade da fase.

## Decisão

Adotar um **padrão híbrido**:

- **REST/HTTP síncrono** para toda a comunicação externa (cliente ↔ API Gateway
  ↔ aplicação). Contrato descrito em OpenAPI (`docs/openapi.json`), verbos e
  códigos HTTP semânticos.
- **Mensageria assíncrona via fila (Redis)** para notificações. A API publica um
  evento ao criar/alterar uma OS; um **worker** desacoplado consome a fila e
  executa a notificação.

A autenticação por CPF é síncrona, mas isolada em função serverless (ver
ADR-003).

## Consequências

**Positivas**
- Latência da API independente do canal de notificação.
- Worker pode ser escalado e reiniciado sem afetar a API.
- Picos de notificação são absorvidos pela fila (buffer natural).

**Negativas / trade-offs**
- Entrega assíncrona é *eventual*: a notificação não é instantânea.
- Introduz um componente de infraestrutura a operar (Redis) e a
  necessidade de tratar reprocessamento e mensagens mortas.
- Exige correlação de logs (correlation-id) para rastrear uma operação que
  atravessa API e worker — endereçado na RFC-004.

## Alternativas consideradas

- **Tudo síncrono (chamada direta de notificação na request):** rejeitado por
  acoplar disponibilidade e latência.
- **Broker mais robusto (SQS/RabbitMQ/Kafka):** adequado para escala maior, mas
  o Redis já está no stack e atende ao volume atual; a migração é possível sem
  mudar o padrão (apenas o transporte). Registrado como evolução futura.
