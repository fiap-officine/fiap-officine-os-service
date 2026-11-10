from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.domain.entities.veiculo import Veiculo
from app.repositories.cliente_repository import ClienteRepository
from app.repositories.veiculo_repository import VeiculoRepository
from app.schemas.veiculo import VeiculoCreate, VeiculoUpdate


def criar_veiculo(db: Session, dados: VeiculoCreate) -> Veiculo:

    cliente_repo = ClienteRepository(db)
    if not cliente_repo.get_by_id(dados.cliente_id):
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    repo = VeiculoRepository(db)
    if repo.get_by_placa(dados.placa):
        raise HTTPException(status_code=400, detail="Placa já cadastrada")

    veiculo = Veiculo(
        cliente_id=dados.cliente_id,
        placa=dados.placa,
        marca=dados.marca,
        modelo=dados.modelo,
        ano=dados.ano,
        ativo=dados.ativo,
        cor=dados.cor,
        observacoes=dados.observacoes,
    )
    return repo.create(veiculo)


def listar_veiculos(db: Session, skip: int = 0, limit: int = 100) -> list[Veiculo]:
    repo = VeiculoRepository(db)
    return repo.get_all(skip=skip, limit=limit)


def buscar_veiculo(db: Session, veiculo_id: int) -> Veiculo:
    repo = VeiculoRepository(db)
    veiculo = repo.get_by_id(veiculo_id)
    if not veiculo:
        raise HTTPException(status_code=404, detail="Veículo não encontrado")
    return veiculo


def buscar_veiculos_por_cliente(db: Session, cliente_id: int) -> list[Veiculo]:
    repo = VeiculoRepository(db)
    return repo.get_by_cliente(cliente_id)


def atualizar_veiculo(db: Session, veiculo_id: int, dados: VeiculoUpdate) -> Veiculo:
    repo = VeiculoRepository(db)
    veiculo = repo.get_by_id(veiculo_id)
    if not veiculo:
        raise HTTPException(status_code=404, detail="Veículo não encontrado")

    update_data = dados.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(veiculo, field, value)

    return repo.update(veiculo)


def deletar_veiculo(db: Session, veiculo_id: int) -> None:
    repo = VeiculoRepository(db)
    veiculo = repo.get_by_id(veiculo_id)
    if not veiculo:
        raise HTTPException(status_code=404, detail="Veículo não encontrado")
    repo.delete(veiculo)
