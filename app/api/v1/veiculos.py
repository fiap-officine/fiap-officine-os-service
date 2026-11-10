from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_cliente, get_current_user
from app.domain.entities.cliente import Cliente
from app.infrastructure.database import get_db
from app.schemas.veiculo import VeiculoCreate, VeiculoResponse, VeiculoUpdate
from app.services import veiculo_service

router = APIRouter(prefix="/veiculos", tags=["Veículos"])


@router.post(
    "/",
    response_model=VeiculoResponse,
    status_code=201,
    dependencies=[Depends(get_current_user)],
)
def criar_veiculo(dados: VeiculoCreate, db: Session = Depends(get_db)):
    """Cadastra um novo veículo vinculado a um cliente."""
    return veiculo_service.criar_veiculo(db, dados)


@router.get(
    "/", response_model=list[VeiculoResponse], dependencies=[Depends(get_current_user)]
)
def listar_veiculos(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Lista todos os veículos com paginação."""
    return veiculo_service.listar_veiculos(db, skip=skip, limit=limit)


@router.get("/meus-veiculos", response_model=list[VeiculoResponse])
def listar_meus_veiculos(
    current_cliente: Cliente = Depends(get_current_cliente),
    db: Session = Depends(get_db),
):
    """Lista todos os veículos do cliente autenticado via CPF."""
    return veiculo_service.buscar_veiculos_por_cliente(db, current_cliente.id)


@router.get(
    "/{veiculo_id}",
    response_model=VeiculoResponse,
    dependencies=[Depends(get_current_user)],
)
def buscar_veiculo(veiculo_id: int, db: Session = Depends(get_db)):
    """Busca um veículo pelo ID."""
    return veiculo_service.buscar_veiculo(db, veiculo_id)


@router.get(
    "/cliente/{cliente_id}",
    response_model=list[VeiculoResponse],
    dependencies=[Depends(get_current_user)],
)
def buscar_veiculos_por_cliente(cliente_id: int, db: Session = Depends(get_db)):
    """Lista veículos de um cliente específico."""
    return veiculo_service.buscar_veiculos_por_cliente(db, cliente_id)


@router.put(
    "/{veiculo_id}",
    response_model=VeiculoResponse,
    dependencies=[Depends(get_current_user)],
)
def atualizar_veiculo(
    veiculo_id: int, dados: VeiculoUpdate, db: Session = Depends(get_db)
):
    """Atualiza dados de um veículo."""
    return veiculo_service.atualizar_veiculo(db, veiculo_id, dados)


@router.delete(
    "/{veiculo_id}", status_code=204, dependencies=[Depends(get_current_user)]
)
def deletar_veiculo(veiculo_id: int, db: Session = Depends(get_db)):
    """Remove um veículo."""
    veiculo_service.deletar_veiculo(db, veiculo_id)
