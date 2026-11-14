# ADR-002 — Uso de HPA para escalabilidade horizontal

- **Status:** Aceito
- **Data:** 2025-07
- **Decisores:** Grupo 123
- **Relacionado a:** [ADR-005](ADR-005-banco-gerenciado.md), [RFC-004](../rfc/RFC-004-observabilidade.md)

## Contexto

Com a expansão para múltiplas unidades, a carga sobre a API é variável: picos em
horário comercial, vales à noite. Manter um número fixo de réplicas ou
significa desperdício de recurso (superprovisionamento) ou risco de degradação
sob pico (subprovisionamento). A fase exige um cluster Kubernetes (K3s em EC2) **com
escalabilidade**.

## Decisão

Usar o **Horizontal Pod Autoscaler (HPA)** do Kubernetes para a API,
escalonando o número de réplicas com base em **utilização de CPU e memória**. O
manifesto vive em `k8s/api-hpa.yaml`.

Parâmetros de referência:
- `minReplicas: 2` (garante disponibilidade mesmo em carga baixa e permite
  rolling update sem downtime).
- `maxReplicas: 10` (teto para conter custo).
- Alvo de **70% de CPU** e **75% de memória**.

O **worker** de notificações também é escalável horizontalmente (múltiplos
consumidores da fila), mas com política própria por profundidade de fila,
independente do HPA da API.

## Consequências

**Positivas**
- Ajuste automático à demanda, atendendo disponibilidade e custo.
- `minReplicas ≥ 2` remove ponto único de falha na API.
- Integra-se ao objetivo de observabilidade: as mesmas métricas de CPU/memória
  monitoradas no New Relic alimentam a decisão de escala.

**Negativas / trade-offs**
- Exige `resources.requests`/`limits` bem calibrados em cada container — sem
  eles o HPA não funciona corretamente.
- Escala reativa: há um atraso entre o pico e a subida de réplicas. Mitigável
  com `behavior` de scale-up mais agressivo se necessário.
- O banco precisa suportar o aumento de conexões concorrentes das novas réplicas
  (ver ADR-005 — pool de conexões e limites do RDS).

## Alternativas consideradas

- **Escala vertical (aumentar recursos do pod):** limitada pelo tamanho do nó e
  não elimina ponto único de falha.
- **Réplicas fixas:** simples, porém ineficiente e arriscado sob picos.
- **KEDA (escala por eventos):** interessante para o worker (escala por
  profundidade de fila); registrado como evolução, mantendo HPA para a API.
