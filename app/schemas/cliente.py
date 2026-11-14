import re
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.domain.validators import formatar_cpf_cnpj, validar_cpf_cnpj


class ClienteBase(BaseModel):
    nome: str
    cpf_cnpj: str
    email: str | None = None
    telefone: str | None = None
    endereco: str | None = None

    @field_validator("cpf_cnpj")
    @classmethod
    def cpf_cnpj_valido(cls, v: str) -> str:
        documento = formatar_cpf_cnpj(v)
        if not validar_cpf_cnpj(documento):
            raise ValueError("CPF ou CNPJ inválido")
        return documento

    @field_validator("nome")
    @classmethod
    def nome_nao_vazio(cls, v: str) -> str:
        if len(v.strip()) < 2:
            raise ValueError("Nome deve ter no mínimo 2 caracteres")
        return v.strip()

    @field_validator("email")
    @classmethod
    def email_valido(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Formato de e-mail inválido")
        return v.strip().lower()

    @field_validator("telefone")
    @classmethod
    def telefone_valido(cls, v: str | None) -> str | None:
        if v is None:
            return v
        apenas_digitos = re.sub(r"\D", "", v)
        if len(apenas_digitos) < 8:
            raise ValueError("Telefone deve ter no mínimo 8 dígitos")
        return apenas_digitos


class ClienteCreate(ClienteBase):
    pass


class ClienteUpdate(BaseModel):
    nome: str | None = None
    email: str | None = None
    telefone: str | None = None
    endereco: str | None = None

    @field_validator("nome")
    @classmethod
    def nome_nao_vazio(cls, v: str | None) -> str | None:
        if v is not None and len(v.strip()) < 2:
            raise ValueError("Nome deve ter no mínimo 2 caracteres")
        return v.strip() if v else v


class ClienteResponse(ClienteBase):
    id: int
    ativo: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ClienteLoginRequest(BaseModel):
    cpf: str

    @field_validator("cpf")
    @classmethod
    def cpf_valido(cls, v: str) -> str:
        documento = formatar_cpf_cnpj(v)
        from app.domain.validators import validar_cpf

        if not validar_cpf(documento):
            raise ValueError("CPF inválido")
        return documento


class ClienteStatusResponse(BaseModel):
    id: int
    nome: str
    cpf_cnpj: str
    ativo: bool
    status_descricao: str

    model_config = {"from_attributes": True}
