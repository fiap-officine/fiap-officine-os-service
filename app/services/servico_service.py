from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.domain.entities.servico import Servico
from app.repositories.servico_repository import ServicoRepository
from app.schemas.servico import ServicoCreate, ServicoUpdate


def criar_servico(db: Session, dados: ServicoCreate) -> Servico:
    repo = ServicoRepository(db)
    servico = Servico(
        nome=dados.nome,
        descricao=dados.descricao,
        preco=dados.preco,
        tempo_estimado_minutos=dados.tempo_estimado_minutos,
        ativo=True,
    )
    return repo.create(servico)


def listar_servicos(
    db: Session, skip: int = 0, limit: int = 100, apenas_ativos: bool = True
) -> list[Servico]:
    repo = ServicoRepository(db)
    if apenas_ativos:
        return repo.get_ativos(skip=skip, limit=limit)
    return repo.get_all(skip=skip, limit=limit)


def buscar_servico(db: Session, servico_id: int) -> Servico:
    repo = ServicoRepository(db)
    servico = repo.get_by_id(servico_id)
    if not servico:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")
    return servico


def atualizar_servico(db: Session, servico_id: int, dados: ServicoUpdate) -> Servico:
    repo = ServicoRepository(db)
    servico = repo.get_by_id(servico_id)
    if not servico:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")

    update_data = dados.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(servico, field, value)

    return repo.update(servico)


def desativar_servico(db: Session, servico_id: int) -> Servico:
    repo = ServicoRepository(db)
    servico = repo.get_by_id(servico_id)
    if not servico:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")
    servico.ativo = False
    return repo.update(servico)


def ativar_servico(db: Session, servico_id: int) -> Servico:
    repo = ServicoRepository(db)
    servico = repo.get_by_id(servico_id)
    if not servico:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")
    servico.ativo = True
    return repo.update(servico)
