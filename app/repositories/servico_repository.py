from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities.servico import Servico
from app.repositories.base import BaseRepository


class ServicoRepository(BaseRepository[Servico]):
    def __init__(self, db: Session):
        super().__init__(Servico, db)

    def get_ativos(self, skip: int = 0, limit: int = 100) -> list[Servico]:
        stmt = select(Servico).where(Servico.ativo.is_(True)).offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())
