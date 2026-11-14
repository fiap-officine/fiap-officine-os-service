from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities.cliente import Cliente
from app.domain.entities.ordem_servico import OrdemServico
from app.domain.enums import STATUS_EM_ANDAMENTO
from app.repositories.cliente_repository import ClienteRepository
from app.schemas.cliente import ClienteCreate, ClienteUpdate


def criar_cliente(db: Session, dados: ClienteCreate) -> Cliente:
    repo = ClienteRepository(db)

    if repo.get_by_cpf_cnpj(dados.cpf_cnpj):
        raise HTTPException(status_code=400, detail="CPF/CNPJ já cadastrado")

    cliente = Cliente(
        nome=dados.nome,
        cpf_cnpj=dados.cpf_cnpj,
        email=dados.email,
        telefone=dados.telefone,
        endereco=dados.endereco,
    )
    return repo.create(cliente)


def listar_clientes(db: Session, skip: int = 0, limit: int = 100) -> list[Cliente]:
    repo = ClienteRepository(db)
    return repo.get_all(skip=skip, limit=limit)


def buscar_cliente(db: Session, cliente_id: int) -> Cliente:
    repo = ClienteRepository(db)
    cliente = repo.get_by_id(cliente_id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return cliente


def buscar_cliente_por_cpf_cnpj(db: Session, cpf_cnpj: str) -> Cliente:
    repo = ClienteRepository(db)
    cliente = repo.get_by_cpf_cnpj(cpf_cnpj)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return cliente


def atualizar_cliente(db: Session, cliente_id: int, dados: ClienteUpdate) -> Cliente:
    repo = ClienteRepository(db)
    cliente = repo.get_by_id(cliente_id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    update_data = dados.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(cliente, field, value)

    return repo.update(cliente)


def desativar_cliente(db: Session, cliente_id: int) -> Cliente:
    repo = ClienteRepository(db)
    cliente = repo.get_by_id(cliente_id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    status_abertos = STATUS_EM_ANDAMENTO
    os_aberta = db.scalars(
        select(OrdemServico)
        .where(
            OrdemServico.cliente_id == cliente_id,
            OrdemServico.status.in_(status_abertos),
        )
        .limit(1)
    ).first()
    if os_aberta:
        raise HTTPException(
            status_code=400,
            detail="Cliente possui ordens de serviço em andamento e não pode ser inativado",
        )

    cliente.ativo = False
    return repo.update(cliente)


def ativar_cliente(db: Session, cliente_id: int) -> Cliente:
    repo = ClienteRepository(db)
    cliente = repo.get_by_id(cliente_id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    cliente.ativo = True
    return repo.update(cliente)


def consultar_existencia_e_status_cliente(db: Session, cpf_cnpj: str) -> Cliente:
    """Consulta a existência e o status do cliente na base de dados pelo CPF/CNPJ.

    Valida formato do CPF/CNPJ, verifica se existe e se está ativo.
    """
    from app.domain.validators import formatar_cpf_cnpj, validar_cpf_cnpj

    doc_limpo = formatar_cpf_cnpj(cpf_cnpj)
    if not validar_cpf_cnpj(doc_limpo):
        raise HTTPException(status_code=400, detail="CPF ou CNPJ inválido")

    repo = ClienteRepository(db)
    cliente = repo.get_by_cpf_cnpj(doc_limpo)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    if not cliente.ativo:
        raise HTTPException(
            status_code=400,
            detail="Cliente inativo no sistema",
        )

    return cliente
