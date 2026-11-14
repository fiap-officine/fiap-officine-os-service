# ADR-005 — Banco de dados gerenciado desacoplado do cluster

- **Status:** Aceito
- **Data:** 2025-07
- **Decisores:** Grupo 123
- **Relacionado a:** [RFC-002](../rfc/RFC-002-banco-de-dados.md), [ADR-002](ADR-002-hpa-escalabilidade.md), [ADR-004](ADR-004-repositorios-cicd.md)

## Contexto

Na Fase 2 o PostgreSQL roda como um pod no próprio cluster, com
`PersistentVolumeClaim`. Isso acopla o dado ao ciclo de vida do cluster,
concentra a responsabilidade de backup/HA no time e não atende ao requisito de
**banco de dados gerenciado** da Fase 3. A escolha do *engine* (PostgreSQL) já
está justificada na [RFC-002](../rfc/RFC-002-banco-de-dados.md); este ADR trata
de **onde e como** o banco roda.

## Decisão

Prover o banco como serviço **gerenciado (Amazon RDS PostgreSQL)**, **fora do
cluster**, provisionado por Terraform em um **repositório dedicado**
(`fiap-officine-database`, ver ADR-004).

Características:
- **Multi-AZ** para alta disponibilidade e failover automático.
- Instância em **subnet privada**; acesso restrito ao cluster (K3s) e à Lambda de
  autenticação por security group.
- **TLS obrigatório** e credenciais no **Secrets Manager** (nada em manifesto).
- **Migrations Alembic** aplicadas pelo pipeline do repositório de banco, antes
  do rollout da aplicação.
- **Pool de conexões** dimensionado na aplicação para respeitar o limite de
  conexões da instância, considerando a escala de réplicas do HPA (db.t4g.micro em homologação, db.t4g.small em produção) (ADR-002).

## Consequências

**Positivas**
- Backup automatizado, point-in-time recovery, patching e failover a cargo do
  provedor — atende disponibilidade e reduz carga operacional.
- Dado sobrevive à recriação do cluster; separação clara de responsabilidades
  entre repositórios de infra.
- Escala de leitura futura via read replicas sem mudar a aplicação.

**Negativas / trade-offs**
- Custo maior que um contêiner de banco.
- Latência de rede entre cluster e banco (mitigada mantendo ambos na mesma
  região/VPC).
- Gestão de conexões passa a ser crítica sob HPA — exige pool e, se necessário,
  um pooler (ex.: PgBouncer/RDS Proxy).

## Alternativas consideradas

- **Postgres em contêiner no cluster (Fase 2):** não atende ao requisito de
  banco gerenciado e concentra risco operacional.
- **Banco serverless (Aurora Serverless):** escala fina e ótimo para carga
  intermitente, porém com trade-offs de custo/latência; registrado como evolução
  possível mantendo compatibilidade PostgreSQL.
