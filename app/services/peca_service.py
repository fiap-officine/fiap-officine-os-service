from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.domain.entities.peca import Peca
from app.repositories.peca_repository import PecaRepository
from app.schemas.peca import PecaCreate, PecaUpdate


def criar_peca(db: Session, dados: PecaCreate) -> Peca:
    peca = Peca(
        codigo=dados.codigo,
        nome=dados.nome,
        descricao=dados.descricao,
        unidade_medida=dados.unidade_medida,
        preco=dados.preco,
        ativo=True,
    )
    return PecaRepository(db).create(peca)


def listar_pecas(
    db: Session, skip: int = 0, limit: int = 100, apenas_ativos: bool = True
) -> list[Peca]:
    repo = PecaRepository(db)
    if apenas_ativos:
        return repo.get_ativos(skip=skip, limit=limit)
    return repo.get_all(skip=skip, limit=limit)


def buscar_peca(db: Session, peca_id: int) -> Peca:
    peca = PecaRepository(db).get_by_id(peca_id)
    if not peca:
        raise HTTPException(status_code=404, detail="Peça não encontrada")
    return peca


def atualizar_peca(db: Session, peca_id: int, dados: PecaUpdate) -> Peca:
    peca = buscar_peca(db, peca_id)
    for field, value in dados.model_dump(exclude_unset=True).items():
        setattr(peca, field, value)
    return PecaRepository(db).update(peca)


def desativar_peca(db: Session, peca_id: int) -> Peca:
    peca = buscar_peca(db, peca_id)
    peca.ativo = False
    return PecaRepository(db).update(peca)


def ativar_peca(db: Session, peca_id: int) -> Peca:
    peca = buscar_peca(db, peca_id)
    peca.ativo = True
    return PecaRepository(db).update(peca)
