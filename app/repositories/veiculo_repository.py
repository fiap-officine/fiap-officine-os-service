from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities.veiculo import Veiculo
from app.repositories.base import BaseRepository


class VeiculoRepository(BaseRepository[Veiculo]):
    def __init__(self, db: Session):
        super().__init__(Veiculo, db)

    def get_by_placa(self, placa: str) -> Veiculo | None:
        stmt = select(Veiculo).where(Veiculo.placa == placa)
        return self.db.scalars(stmt).first()

    def get_by_cliente(self, cliente_id: int) -> list[Veiculo]:
        stmt = select(Veiculo).where(Veiculo.cliente_id == cliente_id)
        return list(self.db.scalars(stmt).all())
