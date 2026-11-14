from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.domain.enums import StatusOrdemServico
from app.infrastructure.database import Base

if TYPE_CHECKING:
    from .cliente import Cliente
    from .peca import Peca
    from .saga import SagaInstance
    from .servico import Servico
    from .veiculo import Veiculo


class OrdemServico(Base):
    __tablename__ = "ordens_servico"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cliente_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clientes.id"), nullable=False, index=True
    )
    veiculo_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("veiculos.id"), nullable=False, index=True
    )
    status: Mapped[StatusOrdemServico] = mapped_column(
        Enum(
            StatusOrdemServico,
            name="status_ordem_servico",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=StatusOrdemServico.RECEBIDA,
        nullable=False,
        index=True,
    )
    observacoes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    valor_total: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=0, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    data_finalizacao: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    data_entrega: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    cliente: Mapped["Cliente"] = relationship(
        "Cliente", back_populates="ordens_servico"
    )
    veiculo: Mapped["Veiculo"] = relationship(
        "Veiculo", back_populates="ordens_servico"
    )
    itens_servico: Mapped[list["OrdemServicoServico"]] = relationship(
        "OrdemServicoServico",
        back_populates="ordem_servico",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    itens_peca: Mapped[list["OrdemServicoPeca"]] = relationship(
        "OrdemServicoPeca",
        back_populates="ordem_servico",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    historico: Mapped[list["OrdemServicoHistorico"]] = relationship(
        "OrdemServicoHistorico",
        back_populates="ordem_servico",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="OrdemServicoHistorico.id",
    )
    saga: Mapped[Optional["SagaInstance"]] = relationship(
        "SagaInstance", back_populates="ordem_servico", uselist=False
    )


class OrdemServicoServico(Base):
    __tablename__ = "ordens_servico_servicos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ordem_servico_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ordens_servico.id"), nullable=False, index=True
    )
    servico_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("servicos.id"), nullable=False
    )
    quantidade: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    valor_unitario: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    ordem_servico: Mapped["OrdemServico"] = relationship(
        "OrdemServico", back_populates="itens_servico"
    )
    servico: Mapped["Servico"] = relationship("Servico", lazy="selectin")


class OrdemServicoPeca(Base):
    __tablename__ = "ordens_servico_pecas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ordem_servico_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ordens_servico.id"), nullable=False, index=True
    )
    peca_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pecas.id"), nullable=False
    )
    quantidade: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    valor_unitario: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    ordem_servico: Mapped["OrdemServico"] = relationship(
        "OrdemServico", back_populates="itens_peca"
    )
    peca: Mapped["Peca"] = relationship("Peca", lazy="selectin")


class OrdemServicoHistorico(Base):
    __tablename__ = "ordens_servico_historico"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ordem_servico_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ordens_servico.id"), nullable=False, index=True
    )
    status_anterior: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status_novo: Mapped[str] = mapped_column(String(50), nullable=False)
    observacao: Mapped[str | None] = mapped_column(String(500), nullable=True)
    data_alteracao: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    ordem_servico: Mapped["OrdemServico"] = relationship(
        "OrdemServico", back_populates="historico"
    )
