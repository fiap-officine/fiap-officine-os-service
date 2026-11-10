from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.infrastructure.database import get_db
from app.schemas.servico import ServicoCreate, ServicoResponse, ServicoUpdate
from app.services import servico_service

router = APIRouter(prefix="/servicos", tags=["Serviços"])


@router.post(
    "/",
    response_model=ServicoResponse,
    status_code=201,
    dependencies=[Depends(get_current_user)],
)
def criar_servico(dados: ServicoCreate, db: Session = Depends(get_db)):
    """Cadastra um novo serviço."""
    return servico_service.criar_servico(db, dados)


@router.get(
    "/", response_model=list[ServicoResponse], dependencies=[Depends(get_current_user)]
)
def listar_servicos(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    apenas_ativos: bool = Query(True),
    db: Session = Depends(get_db),
):
    """Lista serviços com opção de filtrar apenas ativos."""
    return servico_service.listar_servicos(
        db, skip=skip, limit=limit, apenas_ativos=apenas_ativos
    )


@router.get(
    "/{servico_id}",
    response_model=ServicoResponse,
    dependencies=[Depends(get_current_user)],
)
def buscar_servico(servico_id: int, db: Session = Depends(get_db)):
    """Busca um serviço pelo ID."""
    return servico_service.buscar_servico(db, servico_id)


@router.put(
    "/{servico_id}",
    response_model=ServicoResponse,
    dependencies=[Depends(get_current_user)],
)
def atualizar_servico(
    servico_id: int, dados: ServicoUpdate, db: Session = Depends(get_db)
):
    """Atualiza dados de um serviço."""
    return servico_service.atualizar_servico(db, servico_id, dados)


@router.patch(
    "/{servico_id}/desativar",
    response_model=ServicoResponse,
    dependencies=[Depends(get_current_user)],
)
def desativar_servico(servico_id: int, db: Session = Depends(get_db)):
    """Remove um serviço."""
    return servico_service.desativar_servico(db, servico_id)


@router.patch(
    "/{servico_id}/ativar",
    response_model=ServicoResponse,
    dependencies=[Depends(get_current_user)],
)
def ativar_servico(servico_id: int, db: Session = Depends(get_db)):
    """Ativa um serviço."""
    return servico_service.ativar_servico(db, servico_id)
