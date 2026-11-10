from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator


class PecaBase(BaseModel):
    """Catálogo de peças (nome/preço). Saldo e reserva de estoque pertencem ao
    Execution Service (`/api/v1/estoque`)."""

    codigo: str | None = None
    nome: str
    descricao: str | None = None
    unidade_medida: str | None = None
    preco: Decimal

    @field_validator("preco")
    @classmethod
    def preco_positivo(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Preço deve ser positivo")
        return v


class PecaCreate(PecaBase):
    pass


class PecaUpdate(BaseModel):
    codigo: str | None = None
    nome: str | None = None
    descricao: str | None = None
    unidade_medida: str | None = None
    preco: Decimal | None = None
    ativo: bool | None = None

    @field_validator("preco")
    @classmethod
    def preco_positivo(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v <= 0:
            raise ValueError("Preço deve ser positivo")
        return v


class PecaResponse(PecaBase):
    id: int
    ativo: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
