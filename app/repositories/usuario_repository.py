from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities.usuario import Usuario
from app.repositories.base import BaseRepository


class UsuarioRepository(BaseRepository[Usuario]):
    def __init__(self, db: Session):
        super().__init__(Usuario, db)

    def get_by_username(self, username: str) -> Usuario | None:
        stmt = select(Usuario).where(Usuario.username == username)
        return self.db.scalars(stmt).first()

    def get_by_email(self, email: str) -> Usuario | None:
        stmt = select(Usuario).where(Usuario.email == email)
        return self.db.scalars(stmt).first()
