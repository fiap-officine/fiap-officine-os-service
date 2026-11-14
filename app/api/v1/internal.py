"""Endpoints service-to-service (não expostos no API Gateway).

A Lambda de autenticação por CPF consulta o status do cliente aqui, em vez de
ler a tabela `clientes` diretamente — nenhum serviço acessa o banco de outro.
"""

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.validators import formatar_cpf_cnpj, validar_cpf_cnpj
from app.infrastructure.database import get_db
from app.repositories.cliente_repository import ClienteRepository
from app.schemas.cliente import ClienteStatusResponse

router = APIRouter(prefix="/internal", tags=["Interno (service-to-service)"])


def verificar_token_interno(
    x_internal_token: str | None = Header(default=None, alias="x-internal-token"),
) -> None:
    esperado = get_settings().INTERNAL_API_TOKEN
    if not x_internal_token or not hmac.compare_digest(x_internal_token, esperado):
        raise HTTPException(status_code=401, detail="Token interno inválido")


@router.get(
    "/clientes/status/{cpf}",
    response_model=ClienteStatusResponse,
    dependencies=[Depends(verificar_token_interno)],
)
def status_cliente(cpf: str, db: Session = Depends(get_db)):
    """Existência e status do cliente pelo CPF/CNPJ (usado pela Lambda)."""
    documento = formatar_cpf_cnpj(cpf)
    if not validar_cpf_cnpj(documento):
        raise HTTPException(status_code=400, detail="CPF ou CNPJ inválido")
    cliente = ClienteRepository(db).get_by_cpf_cnpj(documento)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return ClienteStatusResponse(
        id=cliente.id,
        nome=cliente.nome,
        cpf_cnpj=cliente.cpf_cnpj,
        ativo=cliente.ativo,
        status_descricao="Ativo" if cliente.ativo else "Inativo",
    )
