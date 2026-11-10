"""Fase 4: saga orquestrada, outbox, idempotência; estoque sai do OS Service

- Novos status da OS (aguardando_orcamento, aguardando_pagamento,
  aguardando_execucao, em_compensacao)
- Tabelas saga_instances, saga_log, outbox, processed_messages
- Remove colunas de estoque de `pecas` (agora no Execution Service/DynamoDB)
- Remove ordens_servico.orcamento_aprovado (agora orcamentos.status no Billing)

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-11-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOVOS_STATUS = [
    "aguardando_orcamento",
    "aguardando_pagamento",
    "aguardando_execucao",
    "em_compensacao",
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # ALTER TYPE ... ADD VALUE não pode ser usado na mesma transação em que
        # o valor é criado: roda em autocommit.
        with op.get_context().autocommit_block():
            for status in NOVOS_STATUS:
                op.execute(
                    f"ALTER TYPE status_ordem_servico ADD VALUE IF NOT EXISTS '{status}'"
                )

    op.create_table(
        "saga_instances",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "os_id",
            sa.Integer(),
            sa.ForeignKey("ordens_servico.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "state_changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("orcamento_id", sa.Integer(), nullable=True),
        sa.Column("pagamento_id", sa.Integer(), nullable=True),
        sa.Column("checkout_url", sa.String(1000), nullable=True),
        sa.Column(
            "payment_confirmed", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("reserved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "pending_compensations", sa.JSON(), nullable=False, server_default="[]"
        ),
        sa.Column(
            "compensation_attempts", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("failure_reason", sa.String(500), nullable=True),
        sa.Column("correlation_id", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_saga_instances_state", "saga_instances", ["state"])
    op.create_index("ix_saga_instances_deadline_at", "saga_instances", ["deadline_at"])

    op.create_table(
        "saga_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "saga_id",
            sa.String(36),
            sa.ForeignKey("saga_instances.id"),
            nullable=False,
        ),
        sa.Column("step", sa.String(30), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("message_type", sa.String(60), nullable=True),
        sa.Column("message_id", sa.String(36), nullable=True),
        sa.Column("detail", sa.String(1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_saga_log_saga_id", "saga_log", ["saga_id"])

    op.create_table(
        "outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.String(36), nullable=False, unique=True),
        sa.Column("destination", sa.String(60), nullable=False),
        sa.Column("message_type", sa.String(60), nullable=False),
        sa.Column("envelope", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_outbox_status", "outbox", ["status"])

    op.create_table(
        "processed_messages",
        sa.Column("message_id", sa.String(36), primary_key=True),
        sa.Column("message_type", sa.String(60), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    with op.batch_alter_table("pecas") as batch:
        batch.drop_column("quantidade_estoque")
        batch.drop_column("quantidade_reservada")
        batch.drop_column("estoque_minimo")

    with op.batch_alter_table("ordens_servico") as batch:
        batch.drop_column("orcamento_aprovado")


def downgrade() -> None:
    with op.batch_alter_table("ordens_servico") as batch:
        batch.add_column(
            sa.Column(
                "orcamento_aprovado",
                sa.Boolean(),
                nullable=False,
                server_default="false",
            )
        )
    with op.batch_alter_table("pecas") as batch:
        batch.add_column(
            sa.Column(
                "quantidade_estoque", sa.Integer(), nullable=False, server_default="0"
            )
        )
        batch.add_column(
            sa.Column(
                "quantidade_reservada",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch.add_column(
            sa.Column(
                "estoque_minimo", sa.Integer(), nullable=False, server_default="0"
            )
        )
    op.drop_table("processed_messages")
    op.drop_index("ix_outbox_status", table_name="outbox")
    op.drop_table("outbox")
    op.drop_index("ix_saga_log_saga_id", table_name="saga_log")
    op.drop_table("saga_log")
    op.drop_index("ix_saga_instances_deadline_at", table_name="saga_instances")
    op.drop_index("ix_saga_instances_state", table_name="saga_instances")
    op.drop_table("saga_instances")
    # Valores adicionados a um ENUM do PostgreSQL não podem ser removidos sem
    # recriar o tipo; mantidos no downgrade.
