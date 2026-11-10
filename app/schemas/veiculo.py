from datetime import datetime

from pydantic import BaseModel, field_validator

from app.domain.validators import formatar_placa, validar_placa


class VeiculoBase(BaseModel):
    cliente_id: int
    placa: str
    marca: str
    modelo: str
    ano: int
    ativo: bool = True
    cor: str | None = None
    observacoes: str | None = None

    @field_validator("placa")
    @classmethod
    def placa_valida(cls, v: str) -> str:
        if not validar_placa(v):
            raise ValueError("Placa inválida. Use formato ABC1234 ou ABC1D23")
        return formatar_placa(v)

    @field_validator("ano")
    @classmethod
    def ano_valido(cls, v: int) -> int:
        ano_atual = datetime.now().year + 1

        if v < 1900 or v > ano_atual:
            raise ValueError(f"Ano deve estar entre 1900 e {ano_atual}")

        return v


class VeiculoCreate(VeiculoBase):
    pass


class VeiculoUpdate(BaseModel):
    marca: str | None = None
    modelo: str | None = None
    ano: int | None = None

    @field_validator("ano")
    @classmethod
    def ano_valido(cls, v: int | None) -> int | None:
        if v is not None and (v < 1900 or v > 2030):
            raise ValueError("Ano deve estar entre 1900 e 2030")
        return v


class VeiculoResponse(VeiculoBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
