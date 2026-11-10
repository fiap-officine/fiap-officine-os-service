from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.domain.entities.ordem_servico import (
    OrdemServico,
    OrdemServicoHistorico,
    OrdemServicoPeca,
    OrdemServicoServico,
)
from app.domain.entities.saga import SagaInstance
from app.domain.enums import TRANSICOES_VALIDAS, StatusOrdemServico
from app.messaging.tracing import record_event
from app.repositories.cliente_repository import ClienteRepository
from app.repositories.ordem_servico_repository import OrdemServicoRepository
from app.repositories.peca_repository import PecaRepository
from app.repositories.servico_repository import ServicoRepository
from app.repositories.veiculo_repository import VeiculoRepository
from app.saga.orchestrator import SagaError, SagaOrchestrator
from app.schemas.ordem_servico import OrdemServicoCreate, TempoMedioResponse


def criar_ordem_servico(db: Session, dados: OrdemServicoCreate) -> OrdemServico:
    """T1 da saga: valida, grava a OS, cria a saga e enfileira GerarOrcamento
    no outbox — tudo em uma única transação."""
    cliente = ClienteRepository(db).get_by_id(dados.cliente_id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    if not cliente.ativo:
        raise HTTPException(
            status_code=400,
            detail="Cliente inativo não pode abrir novas Ordens de Serviço",
        )

    veiculo = VeiculoRepository(db).get_by_id(dados.veiculo_id)
    if not veiculo:
        raise HTTPException(status_code=404, detail="Veículo não encontrado")
    if veiculo.cliente_id != dados.cliente_id:
        raise HTTPException(
            status_code=400, detail="Veículo não pertence ao cliente informado"
        )

    if not dados.itens_servico and not dados.itens_peca:
        raise HTTPException(
            status_code=400,
            detail="A OS precisa de ao menos um serviço ou peça para gerar orçamento",
        )

    servico_repo = ServicoRepository(db)
    itens_servico: list[OrdemServicoServico] = []
    valor_total = Decimal("0.00")
    for item in dados.itens_servico or []:
        servico = servico_repo.get_by_id(item.servico_id)
        if not servico:
            raise HTTPException(
                status_code=404, detail=f"Serviço ID {item.servico_id} não encontrado"
            )
        if not servico.ativo:
            raise HTTPException(
                status_code=400, detail=f"Serviço '{servico.nome}' está inativo"
            )
        valor_item = servico.preco * item.quantidade
        itens_servico.append(
            OrdemServicoServico(
                servico_id=item.servico_id,
                servico=servico,
                quantidade=item.quantidade,
                valor_unitario=servico.preco,
                valor_total=valor_item,
            )
        )
        valor_total += valor_item

    peca_repo = PecaRepository(db)
    itens_peca: list[OrdemServicoPeca] = []
    for item in dados.itens_peca or []:
        peca = peca_repo.get_by_id(item.peca_id)
        if not peca:
            raise HTTPException(
                status_code=404, detail=f"Peça ID {item.peca_id} não encontrada"
            )
        if not peca.ativo:
            raise HTTPException(
                status_code=400, detail=f"Peça '{peca.nome}' está inativa"
            )
        # O preço é "congelado" aqui e segue no comando GerarOrcamento.
        # Saldo de estoque é verificado pelo Execution Service na reserva (T5).
        valor_item = peca.preco * item.quantidade
        itens_peca.append(
            OrdemServicoPeca(
                peca_id=item.peca_id,
                peca=peca,
                quantidade=item.quantidade,
                valor_unitario=peca.preco,
                valor_total=valor_item,
            )
        )
        valor_total += valor_item

    ordem = OrdemServico(
        cliente_id=dados.cliente_id,
        cliente=cliente,
        veiculo_id=dados.veiculo_id,
        veiculo=veiculo,
        status=StatusOrdemServico.RECEBIDA,
        observacoes=dados.observacoes,
        valor_total=valor_total,
        itens_servico=itens_servico,
        itens_peca=itens_peca,
    )
    ordem.historico.append(
        OrdemServicoHistorico(
            status_anterior=None,
            status_novo=StatusOrdemServico.RECEBIDA.value,
            observacao="Ordem de serviço criada",
        )
    )
    db.add(ordem)
    db.flush()

    try:
        SagaOrchestrator(db).start(ordem)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(ordem)

    record_event(
        "OrdemServicoEvent",
        {
            "action": "criada",
            "os_id": ordem.id,
            "cliente_id": dados.cliente_id,
            "status": ordem.status.value,
            "valor_total": float(valor_total),
        },
    )
    return ordem


def listar_ordens_servico(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    status: StatusOrdemServico | None = None,
    order_by_status: bool = False,
    exclude_finalizados: bool = True,
) -> list[OrdemServico]:
    return OrdemServicoRepository(db).get_list(
        status=status,
        order_by_status=order_by_status,
        exclude_finalizados=exclude_finalizados,
        skip=skip,
        limit=limit,
    )


def buscar_ordem_servico(db: Session, os_id: int) -> OrdemServico:
    ordem = OrdemServicoRepository(db).get_by_id(os_id)
    if not ordem:
        raise HTTPException(status_code=404, detail="Ordem de serviço não encontrada")
    return ordem


def buscar_ordens_por_cliente(db: Session, cliente_id: int) -> list[OrdemServico]:
    return OrdemServicoRepository(db).get_by_cliente(cliente_id)


def buscar_saga(db: Session, os_id: int) -> SagaInstance:
    ordem = buscar_ordem_servico(db, os_id)
    if ordem.saga is None:
        raise HTTPException(
            status_code=404, detail="Esta OS não possui saga (criada antes da Fase 4)"
        )
    return ordem.saga


def cancelar_ordem_servico(
    db: Session, os_id: int, motivo: str | None = None
) -> OrdemServico:
    """Dispara a compensação da saga (ou cancela localmente OS legada)."""
    ordem = buscar_ordem_servico(db, os_id)
    try:
        SagaOrchestrator(db).cancel(ordem, motivo or "Cancelada a pedido")
        db.commit()
    except SagaError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    db.refresh(ordem)
    return ordem


def entregar_veiculo(
    db: Session, os_id: int, observacao: str | None = None
) -> OrdemServico:
    """Ação local do OS Service, fora da saga (que termina em `finalizada`)."""
    ordem = buscar_ordem_servico(db, os_id)
    novo = StatusOrdemServico.ENTREGUE
    if novo not in TRANSICOES_VALIDAS.get(ordem.status, []):
        raise HTTPException(
            status_code=400,
            detail=f"Transição de '{ordem.status.value}' para '{novo.value}' não é "
            f"permitida. Transições válidas: "
            f"{[t.value for t in TRANSICOES_VALIDAS.get(ordem.status, [])]}",
        )
    anterior = ordem.status.value
    ordem.status = novo
    ordem.data_entrega = datetime.now(timezone.utc)
    ordem.historico.append(
        OrdemServicoHistorico(
            status_anterior=anterior,
            status_novo=novo.value,
            observacao=observacao or "Veículo entregue ao cliente",
        )
    )
    db.commit()
    db.refresh(ordem)
    record_event(
        "OrdemServicoEvent",
        {"action": "entregue", "os_id": os_id, "status_anterior": anterior},
    )
    return ordem


def obter_tempo_medio(db: Session) -> TempoMedioResponse:
    tempo_medio, total = OrdemServicoRepository(db).get_tempo_medio_execucao()
    return TempoMedioResponse(
        tempo_medio_minutos=round(tempo_medio, 2), total_ordens_finalizadas=total
    )
