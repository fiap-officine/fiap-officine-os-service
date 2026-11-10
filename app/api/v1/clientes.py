from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_cliente, get_current_user
from app.domain.entities.cliente import Cliente
from app.infrastructure.database import get_db
from app.schemas.cliente import ClienteCreate, ClienteResponse, ClienteUpdate
from app.services import cliente_service

router = APIRouter(prefix="/clientes", tags=["Clientes"])


@router.post(
    "/",
    response_model=ClienteResponse,
    status_code=201,
    dependencies=[Depends(get_current_user)],
)
def criar_cliente(dados: ClienteCreate, db: Session = Depends(get_db)):
    """Cria um novo cliente."""
    return cliente_service.criar_cliente(db, dados)


@router.get(
    "/", response_model=list[ClienteResponse], dependencies=[Depends(get_current_user)]
)
def listar_clientes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Lista todos os clientes com paginação."""
    return cliente_service.listar_clientes(db, skip=skip, limit=limit)


@router.get("/me", response_model=ClienteResponse)
def perfil_cliente(current_cliente: Cliente = Depends(get_current_cliente)):
    """Retorna o perfil do cliente autenticado via token JWT (CPF)."""
    return current_cliente


@router.get(
    "/{cliente_id}",
    response_model=ClienteResponse,
    dependencies=[Depends(get_current_user)],
)
def buscar_cliente(cliente_id: int, db: Session = Depends(get_db)):
    """Busca um cliente pelo ID."""
    return cliente_service.buscar_cliente(db, cliente_id)


@router.get(
    "/cpf-cnpj/{cpf_cnpj}",
    response_model=ClienteResponse,
    dependencies=[Depends(get_current_user)],
)
def buscar_por_cpf_cnpj(cpf_cnpj: str, db: Session = Depends(get_db)):
    """Busca um cliente pelo CPF ou CNPJ."""
    return cliente_service.buscar_cliente_por_cpf_cnpj(db, cpf_cnpj)


@router.put(
    "/{cliente_id}",
    response_model=ClienteResponse,
    dependencies=[Depends(get_current_user)],
)
def atualizar_cliente(
    cliente_id: int, dados: ClienteUpdate, db: Session = Depends(get_db)
):
    """Atualiza dados de um cliente."""
    return cliente_service.atualizar_cliente(db, cliente_id, dados)


@router.delete(
    "/{cliente_id}/desativar", status_code=204, dependencies=[Depends(get_current_user)]
)
def desativar_cliente(cliente_id: int, db: Session = Depends(get_db)):
    """Desativa um cliente."""
    cliente_service.desativar_cliente(db, cliente_id)


@router.put(
    "/{cliente_id}/ativar",
    response_model=ClienteResponse,
    dependencies=[Depends(get_current_user)],
)
def ativar_cliente(cliente_id: int, db: Session = Depends(get_db)):
    """Ativa um cliente."""
    return cliente_service.ativar_cliente(db, cliente_id)
