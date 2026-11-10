from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator


class ServicoBase(BaseModel):
    nome: str
    descricao: str | None = None
    preco: Decimal
    tempo_estimado_minutos: int

    @field_validator("preco")
    @classmethod
    def preco_positivo(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Preço deve ser positivo")
        return v

    @field_validator("tempo_estimado_minutos")
    @classmethod
    def tempo_positivo(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Tempo estimado deve ser positivo")
        return v


class ServicoCreate(ServicoBase):
    pass


class ServicoUpdate(BaseModel):
    nome: str | None = None
    descricao: str | None = None
    preco: Decimal | None = None
    tempo_estimado_minutos: int | None = None
    ativo: bool | None = None

    @field_validator("preco")
    @classmethod
    def preco_positivo(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v <= 0:
            raise ValueError("Preço deve ser positivo")
        return v


class ServicoResponse(ServicoBase):
    id: int
    ativo: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
