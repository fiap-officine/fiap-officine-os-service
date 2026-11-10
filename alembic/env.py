from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.config import get_settings
from app.domain.entities.cliente import Cliente  # noqa
from app.domain.entities.messaging import OutboxMessage, ProcessedMessage  # noqa
from app.domain.entities.ordem_servico import (  # noqa
    OrdemServico,
    OrdemServicoHistorico,
    OrdemServicoPeca,
    OrdemServicoServico,
)
from app.domain.entities.peca import Peca  # noqa
from app.domain.entities.saga import SagaInstance, SagaLog  # noqa
from app.domain.entities.servico import Servico  # noqa

# Importar todos os modelos para que o Alembic os detecte
from app.domain.entities.usuario import Usuario  # noqa
from app.domain.entities.veiculo import Veiculo  # noqa
from app.infrastructure.database import Base

config = context.config

# Sobrescrever URL do banco com a variável de ambiente
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
