from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.infrastructure.database import Base

if TYPE_CHECKING:
    from .cliente import Cliente
    from .ordem_servico import OrdemServico


class Veiculo(Base):
    __tablename__ = "veiculos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cliente_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clientes.id"), nullable=False, index=True
    )
    placa: Mapped[str] = mapped_column(
        String(7), unique=True, nullable=False, index=True
    )
    marca: Mapped[str] = mapped_column(String(100), nullable=False)
    modelo: Mapped[str] = mapped_column(String(100), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cor: Mapped[str] = mapped_column(String(50), nullable=True)
    # Declarado uma única vez (antes havia duas declarações conflitantes).
    ano: Mapped[int | None] = mapped_column(Integer, nullable=True)
    observacoes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    cliente: Mapped["Cliente"] = relationship("Cliente", back_populates="veiculos")
    ordens_servico: Mapped[list["OrdemServico"]] = relationship(
        "OrdemServico", back_populates="veiculo", lazy="selectin"
    )
