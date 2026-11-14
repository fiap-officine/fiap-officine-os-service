# RFC-002 — Escolha do banco de dados gerenciado

- **Status:** Aceita
- **Data:** 2025-07
- **Autores:** Grupo 123
- **Consolida em:** [ADR-005](../adr/ADR-005-banco-gerenciado.md)
- **Relacionado a:** [data-model.md](../data-model.md)

## 1. Resumo

Propõe-se **PostgreSQL 16.9 gerenciado (Amazon RDS)** como banco de dados da
aplicação.

## 2. Motivação

O domínio é fortemente transacional e relacional (clientes, veículos, ordens de
serviço, itens, estoque, histórico). A Fase 3 exige banco **gerenciado** com
consistência e performance. É preciso decidir o *engine* (relacional vs. NoSQL;
qual SGBD) e formalizar a justificativa.

## 3. Proposta

**Engine: PostgreSQL.** Racional:

- **ACID e integridade referencial** — essenciais para estoque, orçamento e
  transições de status.
- **Modelo relacional rico** — consultas de negócio dependem de JOINs e chaves
  estrangeiras (OS por cliente, tempo médio por status, histórico).
- **Tipos adequados** — `NUMERIC` para dinheiro, `ENUM` nativo para status,
  `TIMESTAMPTZ` para datas com fuso.
- **Ecossistema já adotado** — SQLAlchemy 2.0 + Alembic, sem custo de migração
  de tecnologia.

**Modalidade: gerenciada (RDS), Multi-AZ**, com backup automático, TLS e
credenciais em Secrets Manager. Detalhes operacionais na ADR-005.

## 4. Alternativas consideradas

| Opção | Por que não |
|---|---|
| **MySQL gerenciado** | Capaz, mas o projeto já usa recursos PostgreSQL (ENUM nativo, tipos) e o time tem mais domínio |
| **SQL Server** | Custo de licenciamento sem benefício para o caso de uso |
| **NoSQL (DynamoDB/MongoDB)** | Modelo de acesso é relacional; reconstruir integridade/JOINs em NoSQL adicionaria complexidade sem ganho |
| **Aurora PostgreSQL** | Compatível e escalável; mantido como evolução futura por custo/simplicidade nesta fase |

## 5. Riscos e mitigação

- **Conexões sob HPA:** réplicas em escala podem esgotar conexões — mitigado com
  pool na aplicação e, se necessário, RDS Proxy/PgBouncer (ADR-005).
- **Latência cluster↔banco:** mantê-los na mesma região/VPC.

## 6. Decisão

**PostgreSQL 16.9 em Amazon RDS aprovado.** Ajustes de modelo (índices,
consistência de estoque) descritos em [data-model.md](../data-model.md).
