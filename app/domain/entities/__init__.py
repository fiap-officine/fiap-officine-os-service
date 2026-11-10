"""Importa todos os modelos para registrar os mapeamentos do SQLAlchemy
(relacionamentos por nome, ex.: OrdemServico.saga -> "SagaInstance")."""

from app.domain.entities.cliente import Cliente  # noqa: F401
from app.domain.entities.messaging import OutboxMessage, ProcessedMessage  # noqa: F401
from app.domain.entities.ordem_servico import (  # noqa: F401
    OrdemServico,
    OrdemServicoHistorico,
    OrdemServicoPeca,
    OrdemServicoServico,
)
from app.domain.entities.peca import Peca  # noqa: F401
from app.domain.entities.saga import SagaInstance, SagaLog  # noqa: F401
from app.domain.entities.servico import Servico  # noqa: F401
from app.domain.entities.usuario import Usuario  # noqa: F401
from app.domain.entities.veiculo import Veiculo  # noqa: F401
