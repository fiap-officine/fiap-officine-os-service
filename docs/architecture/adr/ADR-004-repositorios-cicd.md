# ADR-004 — Segregação em quatro repositórios com CI/CD independente

- **Status:** Aceito
- **Data:** 2025-07
- **Decisores:** Grupo 123
- **Relacionado a:** [ADR-005](ADR-005-banco-gerenciado.md), [ADR-003](ADR-003-api-gateway-auth-serverless.md)

## Contexto

Na Fase 2 todo o projeto (aplicação, manifestos Kubernetes, Terraform e
workflows) vive em um único repositório. A Fase 3 exige **quatro repositórios
separados**, cada um com CI/CD próprio e deploy automático, além de regras de
proteção de branch. Componentes com ciclos de vida e permissões diferentes não
devem compartilhar o mesmo pipeline e o mesmo blast radius.

## Decisão

Segregar em **quatro repositórios** na organização GitHub **`fiap-officine`**,
cada um com pipeline independente:

| # | Repositório | Conteúdo | Deploy |
|---|---|---|---|
| 1 | `fiap-officine-lambda` | Função serverless de autenticação por CPF | Publicação da Lambda |
| 2 | `fiap-officine-kubernets` | Terraform da infra base AWS (VPC, K3s, API Gateway, security groups) | `terraform apply` |
| 3 | `fiap-officine-database` | Terraform do banco gerenciado (RDS) + scripts SQL/migrations | `terraform apply` |
| 4 | `fiap-officine-api` | Aplicação principal (FastAPI + worker) executando no cluster | Build de imagem + rollout no K3s |

**Ordem de dependência de deploy:** `fiap-officine-kubernets` (VPC/K3s) →
`fiap-officine-database` (RDS nas subnets privadas da VPC) →
(`fiap-officine-lambda` ∥ `fiap-officine-api`).

> A VPC e as subnets privadas são provisionadas pelo repositório
> `fiap-officine-kubernets`; o `fiap-officine-database` consome essas subnets
> para posicionar o RDS de forma isolada, acessível apenas pelos pods da
> aplicação e pela Lambda de autenticação.

**Regras de proteção (todos os repositórios):**
- Branch `main`/`master` protegida, **sem commit direto**.
- Merge **somente via Pull Request** (com review e checks verdes obrigatórios).
- **Deploy automático** nas branches de **homologação** (`develop`) e
  **produção** (`main`).

**Estrutura de pipeline por repositório:**
- *PR:* lint, testes/validação (`terraform validate`, `pytest`, `ruff`),
  `plan` do Terraform quando aplicável.
- *Merge em develop/main:* build, publicação de artefato/imagem e deploy
  automático para o ambiente correspondente.

## Consequências

**Positivas**
- Cada componente evolui, versiona e é auditado isoladamente; permissões e
  secrets são concedidos por menor privilégio.
- Falha ou rollback de um componente não arrasta os demais.
- Pipelines menores e mais rápidos; histórico de mudança mais legível.

**Negativas / trade-offs**
- Mudança que atravessa componentes exige coordenação entre repositórios
  (versionar contratos, respeitar ordem de deploy).
- Mais configuração inicial (4 conjuntos de CI/CD, secrets e proteções).
- Necessidade de documentar claramente as dependências entre repos (feito na
  tabela acima e no README de cada um).

## Alternativas consideradas

- **Mono-repo com múltiplos pipelines (paths filter):** menos atrito de
  coordenação, mas não atende ao requisito explícito de quatro repositórios e
  mantém permissões acopladas.
- **Separar apenas app e infra (2 repos):** insuficiente frente ao enunciado e
  ainda mistura banco com cluster.
