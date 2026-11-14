from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities.peca import Peca
from app.repositories.base import BaseRepository


class PecaRepository(BaseRepository[Peca]):
    def __init__(self, db: Session):
        super().__init__(Peca, db)

    def get_ativos(self, skip: int = 0, limit: int = 100) -> list[Peca]:
        stmt = select(Peca).where(Peca.ativo.is_(True)).offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())
