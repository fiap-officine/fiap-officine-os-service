from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_actor,
    get_current_cliente,
    get_current_user,
    get_optional_cliente,
)
from app.domain.entities.cliente import Cliente
from app.domain.entities.usuario import Usuario
from app.domain.enums import StatusOrdemServico
from app.infrastructure.database import get_db
from app.schemas.ordem_servico import (
    CancelarOrdemRequest,
    OrdemServicoCreate,
    OrdemServicoResponse,
    OrdemServicoResumo,
    SagaResponse,
    TempoMedioResponse,
)
from app.services import ordem_servico_service

router = APIRouter(prefix="/ordens-servico", tags=["Ordens de Serviço"])


@router.post(
    "/",
    response_model=OrdemServicoResponse,
    status_code=201,
    dependencies=[Depends(get_current_user)],
)
def criar_ordem_servico(dados: OrdemServicoCreate, db: Session = Depends(get_db)):
    """Abre a OS e inicia a saga: o comando `GerarOrcamento` é gravado no outbox
    na mesma transação e publicado para o Billing Service."""
    return ordem_servico_service.criar_ordem_servico(db, dados)


@router.get(
    "/",
    response_model=list[OrdemServicoResumo],
    dependencies=[Depends(get_current_user)],
)
def listar_ordens_servico(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    status: StatusOrdemServico | None = None,
    order_by_status: bool = Query(
        False, description="Ordenar por prioridade de status"
    ),
    exclude_finalizados: bool = Query(
        True, description="Excluir ordens finalizadas/entregues/canceladas"
    ),
    db: Session = Depends(get_db),
):
    """Lista ordens de serviço com filtro opcional por status."""
    return ordem_servico_service.listar_ordens_servico(
        db,
        skip=skip,
        limit=limit,
        status=status,
        order_by_status=order_by_status,
        exclude_finalizados=exclude_finalizados,
    )


@router.get(
    "/tempo-medio",
    response_model=TempoMedioResponse,
    dependencies=[Depends(get_current_user)],
)
def tempo_medio_execucao(db: Session = Depends(get_db)):
    """Retorna o tempo médio de execução dos serviços finalizados."""
    return ordem_servico_service.obter_tempo_medio(db)


@router.get("/minhas-ordens", response_model=list[OrdemServicoResumo])
def listar_minhas_ordens(
    current_cliente: Cliente = Depends(get_current_cliente),
    db: Session = Depends(get_db),
):
    """Lista ordens de serviço do cliente autenticado via token JWT (CPF)."""
    return ordem_servico_service.buscar_ordens_por_cliente(db, current_cliente.id)


@router.get("/acompanhar-cliente/{os_id}", response_model=OrdemServicoResponse)
def acompanhar_os_cliente(
    os_id: int,
    current_cliente: Cliente = Depends(get_current_cliente),
    db: Session = Depends(get_db),
):
    """Permite ao cliente autenticado via CPF acompanhar sua ordem de serviço."""
    ordem = ordem_servico_service.buscar_ordem_servico(db, os_id)
    if ordem.cliente_id != current_cliente.id:
        raise HTTPException(
            status_code=403, detail="Você não tem permissão para acompanhar esta OS"
        )
    return ordem


@router.get("/acompanhar/{os_id}", response_model=OrdemServicoResponse)
def acompanhar_ordem_servico(
    os_id: int,
    cpf_cnpj: str | None = Query(None, description="CPF ou CNPJ do cliente"),
    current_cliente: Cliente | None = Depends(get_optional_cliente),
    db: Session = Depends(get_db),
):
    """Acompanhamento da OS via token JWT (CPF) ou query param."""
    from app.domain.validators import formatar_cpf_cnpj

    ordem = ordem_servico_service.buscar_ordem_servico(db, os_id)
    cliente = ordem.cliente

    if current_cliente:
        if not cliente or cliente.id != current_cliente.id:
            raise HTTPException(
                status_code=403, detail="CPF/CNPJ não corresponde ao cliente desta OS"
            )
        return ordem

    if cpf_cnpj:
        if not cliente or cliente.cpf_cnpj != formatar_cpf_cnpj(cpf_cnpj):
            raise HTTPException(
                status_code=403, detail="CPF/CNPJ não corresponde ao cliente desta OS"
            )
        return ordem

    raise HTTPException(
        status_code=401,
        detail="Autenticação necessária via token Bearer (CPF) ou parâmetro cpf_cnpj",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.get(
    "/cliente/{cliente_id}",
    response_model=list[OrdemServicoResumo],
    dependencies=[Depends(get_current_user)],
)
def buscar_ordens_por_cliente(cliente_id: int, db: Session = Depends(get_db)):
    """Lista ordens de serviço de um cliente específico."""
    return ordem_servico_service.buscar_ordens_por_cliente(db, cliente_id)


@router.get(
    "/{os_id}",
    response_model=OrdemServicoResponse,
    dependencies=[Depends(get_current_user)],
)
def buscar_ordem_servico(os_id: int, db: Session = Depends(get_db)):
    """Busca uma ordem de serviço pelo ID com detalhes completos."""
    return ordem_servico_service.buscar_ordem_servico(db, os_id)


@router.get(
    "/{os_id}/saga",
    response_model=SagaResponse,
    dependencies=[Depends(get_current_user)],
)
def consultar_saga(os_id: int, db: Session = Depends(get_db)):
    """Estado da saga da OS: passo atual, prazo, compensações pendentes e a
    linha do tempo de comandos/respostas."""
    return ordem_servico_service.buscar_saga(db, os_id)


@router.post("/{os_id}/cancelar", response_model=OrdemServicoResponse)
def cancelar_ordem_servico(
    os_id: int,
    dados: CancelarOrdemRequest | None = None,
    actor: tuple[Usuario | None, Cliente | None] = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Cancela a OS disparando as compensações da saga (liberar reserva ->
    estornar pagamento -> cancelar orçamento). Não é permitido após o início do
    reparo (pivô). Cliente só pode cancelar a própria OS."""
    _, cliente = actor
    if cliente is not None:
        ordem = ordem_servico_service.buscar_ordem_servico(db, os_id)
        if ordem.cliente_id != cliente.id:
            raise HTTPException(
                status_code=403, detail="Você não tem permissão para cancelar esta OS"
            )
    motivo = dados.motivo if dados else None
    return ordem_servico_service.cancelar_ordem_servico(db, os_id, motivo)


@router.post(
    "/{os_id}/entregar",
    response_model=OrdemServicoResponse,
    dependencies=[Depends(get_current_user)],
)
def entregar_veiculo(
    os_id: int,
    observacao: str | None = Body(None, embed=True),
    db: Session = Depends(get_db),
):
    """Entrega o veículo ao cliente (ação local, após a saga concluir)."""
    return ordem_servico_service.entregar_veiculo(db, os_id, observacao)
