from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.infrastructure.database import get_db
from app.schemas.peca import PecaCreate, PecaResponse, PecaUpdate
from app.services import peca_service

router = APIRouter(prefix="/pecas", tags=["Peças e Insumos"])


@router.post(
    "/",
    response_model=PecaResponse,
    status_code=201,
    dependencies=[Depends(get_current_user)],
)
def criar_peca(dados: PecaCreate, db: Session = Depends(get_db)):
    """Cadastra uma peça no catálogo (o saldo de estoque fica no Execution Service)."""
    return peca_service.criar_peca(db, dados)


@router.get(
    "/", response_model=list[PecaResponse], dependencies=[Depends(get_current_user)]
)
def listar_pecas(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    apenas_ativos: bool = Query(True),
    db: Session = Depends(get_db),
):
    """Lista peças e insumos com opção de filtrar apenas ativos."""
    return peca_service.listar_pecas(
        db, skip=skip, limit=limit, apenas_ativos=apenas_ativos
    )


@router.get(
    "/{peca_id}", response_model=PecaResponse, dependencies=[Depends(get_current_user)]
)
def buscar_peca(peca_id: int, db: Session = Depends(get_db)):
    """Busca uma peça pelo ID."""
    return peca_service.buscar_peca(db, peca_id)


@router.put(
    "/{peca_id}", response_model=PecaResponse, dependencies=[Depends(get_current_user)]
)
def atualizar_peca(peca_id: int, dados: PecaUpdate, db: Session = Depends(get_db)):
    """Atualiza dados de uma peça ou insumo."""
    return peca_service.atualizar_peca(db, peca_id, dados)


@router.patch(
    "/{peca_id}/desativar",
    response_model=PecaResponse,
    dependencies=[Depends(get_current_user)],
)
def desativar_peca(peca_id: int, db: Session = Depends(get_db)):
    """Desativa uma peça ou insumo."""
    return peca_service.desativar_peca(db, peca_id)


@router.patch(
    "/{peca_id}/ativar",
    response_model=PecaResponse,
    dependencies=[Depends(get_current_user)],
)
def ativar_peca(peca_id: int, db: Session = Depends(get_db)):
    """Ativa uma peça ou insumo."""
    return peca_service.ativar_peca(db, peca_id)
