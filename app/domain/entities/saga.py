from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.infrastructure.database import Base

if TYPE_CHECKING:
    from .ordem_servico import OrdemServico


class SagaInstance(Base):
    """Estado persistido da saga orquestrada de uma Ordem de Serviço."""

    __tablename__ = "saga_instances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    os_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ordens_servico.id"), nullable=False, unique=True
    )
    state: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    state_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    orcamento_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pagamento_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checkout_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    payment_confirmed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    reserved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pending_compensations: Mapped[list] = mapped_column(
        JSON, default=list, nullable=False
    )
    compensation_attempts: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    ordem_servico: Mapped["OrdemServico"] = relationship(
        "OrdemServico", back_populates="saga"
    )
    steps: Mapped[list["SagaLog"]] = relationship(
        "SagaLog",
        back_populates="saga",
        lazy="selectin",
        order_by="SagaLog.id",
        cascade="all, delete-orphan",
    )


class SagaLog(Base):
    """Linha do tempo da saga: comandos enviados, respostas e compensações."""

    __tablename__ = "saga_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    saga_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("saga_instances.id"), nullable=False, index=True
    )
    step: Mapped[str] = mapped_column(String(30), nullable=False)
    # forward | compensation | reply | timeout | ignored
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    message_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    detail: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    saga: Mapped["SagaInstance"] = relationship("SagaInstance", back_populates="steps")
