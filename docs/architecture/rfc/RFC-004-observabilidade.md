# RFC-004 — Estratégia de observabilidade

- **Status:** Aceita
- **Data:** 2025-07
- **Autores:** Grupo 123
- **Relacionado a:** [ADR-001](../adr/ADR-001-padrao-comunicacao.md), [ADR-002](../adr/ADR-002-hpa-escalabilidade.md)

## 1. Resumo

Propõe-se adotar o **New Relic** como plataforma de observabilidade, cobrindo
logs estruturados, métricas, APM (traces distribuídos) e alertas, com dashboards
de negócio e de infraestrutura construídos em **NRQL**.

## 2. Motivação

A fase exige visibilidade total: monitorar latência das APIs, consumo de
recursos do Kubernetes, healthchecks/uptime, alertas de falha no processamento
de OS e logs estruturados com correlação entre requisições — além de dashboards
de negócio.

## 3. Proposta

### 3.1 Coleta

- **New Relic Python Agent (APM)** instrumentando a aplicação FastAPI —
  transações, traces distribuídos e custom events, com propagação de contexto do
  API Gateway ao worker.
- **New Relic Infrastructure Agent** como `DaemonSet` (`newrelic-infrastructure`)
  no cluster — coleta métricas de CPU/memória por pod e por nó
  (`K8sContainerSample` / `K8sNodeSample`), reinícios de pod, etc.
- **New Relic Synthetics** para monitor de uptime externo, checando `/health`
  em intervalo curto.
- **Métricas do API Gateway** (latência de borda, 4xx/5xx) integradas à conta.

### 3.2 Logs estruturados (JSON)

- Um `ObservabilityMiddleware` na aplicação injeta **correlation ID** e mede
  latência por requisição; um `JSONLogFormatter` emite todo log em **JSON**.
- Campos mínimos: `timestamp`, `level`, `service`, `trace_id`, `correlation_id`,
  `path`, `status_code`, `latency_ms`.
- **Correlação:** o `correlation_id` acompanha a requisição pela API e pelo
  evento publicado na fila, permitindo rastrear uma OS de ponta a ponta
  (API -> Redis -> worker).
- Os logs vão para `stdout` e são encaminhados ao **New Relic Log Management**,
  já correlacionados com as transações do APM.
- **Dados sensíveis:** CPF e credenciais nunca em claro — mascarados no logger.

### 3.3 Monitores e alertas

| Sinal | Condição de alerta |
|---|---|
| Latência da API | p95 acima do limite por X min |
| Erros | taxa de 5xx acima do limite |
| Recursos K8s | CPU/memória saturando (correlaciona com HPA) |
| Healthcheck/uptime | `/health` falhando (Synthetics) |
| **Falha no processamento de OS** | erro/consumo travado no worker da fila |

### 3.4 Dashboards (NRQL)

- **Negócio:** volume diário de OS; tempo médio de execução por status
  (Diagnóstico, Execução, Finalização); erros/falhas nas integrações.
- **Infra:** latência (p50/p95/p99) e throughput por rota; CPU/memória por pod;
  réplicas ativas (HPA); saúde do banco e da fila.

### 3.5 Healthchecks

- Endpoint `/health` (e `/api/v1/health`) expõe estado da API, do PostgreSQL e
  do Redis; usado por readiness/liveness probes no Kubernetes e pelo monitor de
  uptime do New Relic. Rotas de saúde e documentação (`/docs`, `/openapi.json`,
  `/redoc`) ficam abertas (`authorization_type = NONE`) no API Gateway.

## 4. Alternativas consideradas

- **Datadog:** equivalente e também aceito pelo enunciado; foi a primeira opção
  avaliada. **New Relic foi escolhido** pela cobertura do free tier atender a
  homologação, pela experiência com NRQL e pela integração nativa do agente
  Kubernetes. A decisão é reversível — logs em JSON + OpenTelemetry mantêm a
  portabilidade da instrumentação.
- **Stack self-hosted (Prometheus + Grafana + Loki):** poderoso, mas adiciona
  carga operacional significativa frente a uma solução gerenciada.

## 5. Riscos e mitigação

- **Custo por volume de logs/traces:** mitigado com amostragem de traces, níveis
  de log por ambiente e uso do free tier em homologação.
- **Vazamento de dado sensível em log:** mitigado por mascaramento no logger e
  revisão dos campos emitidos.

## 6. Decisão

**New Relic aprovado**, com logs JSON correlacionados, APM/traces distribuídos,
monitores de latência/erro/recurso/uptime/falha de OS e dashboards NRQL de
negócio e infraestrutura.
