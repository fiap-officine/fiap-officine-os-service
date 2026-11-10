"""Funções auxiliares compartilhadas pelos testes do OS Service."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities.messaging import OutboxMessage
from app.domain.entities.saga import SagaInstance
from app.messaging.consumer import handle_message
from app.messaging.envelope import new_envelope
from app.workers import saga_reply_handler


def setup_dados(client, auth_headers, cpf="529.982.247-25", placa="ABC1234"):
    """Cria cliente, veículo, serviço e peça. Retorna os IDs."""
    cliente_id = client.post(
        "/api/v1/clientes/",
        json={"nome": "Cliente OS", "cpf_cnpj": cpf, "email": "os@test.com"},
        headers=auth_headers,
    ).json()["id"]
    veiculo_id = client.post(
        "/api/v1/veiculos/",
        json={
            "cliente_id": cliente_id,
            "placa": placa,
            "marca": "Fiat",
            "modelo": "Uno",
            "ano": 2020,
        },
        headers=auth_headers,
    ).json()["id"]
    servico_id = client.post(
        "/api/v1/servicos/",
        json={"nome": "Troca de Óleo", "preco": 150.00, "tempo_estimado_minutos": 30},
        headers=auth_headers,
    ).json()["id"]
    peca_id = client.post(
        "/api/v1/pecas/",
        json={"nome": "Filtro de Óleo", "preco": 35.50},
        headers=auth_headers,
    ).json()["id"]
    return cliente_id, veiculo_id, servico_id, peca_id


def criar_os(client, auth_headers, ids, qtd_servico=1, qtd_peca=2):
    cliente_id, veiculo_id, servico_id, peca_id = ids
    payload = {"cliente_id": cliente_id, "veiculo_id": veiculo_id}
    if qtd_servico:
        payload["itens_servico"] = [
            {"servico_id": servico_id, "quantidade": qtd_servico}
        ]
    if qtd_peca:
        payload["itens_peca"] = [{"peca_id": peca_id, "quantidade": qtd_peca}]
    response = client.post(
        "/api/v1/ordens-servico/", json=payload, headers=auth_headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def saga_de(db: Session, os_id: int) -> SagaInstance:
    db.expire_all()
    return db.scalar(select(SagaInstance).where(SagaInstance.os_id == os_id))


def responder(
    db: Session,
    os_id: int,
    message_type: str,
    payload: dict | None = None,
    source: str = "fake-participant",
):
    """Simula a chegada de uma resposta de participante na fila os-saga-replies."""
    saga = saga_de(db, os_id)
    envelope = new_envelope(
        message_type,
        "reply",
        payload or {},
        source=source,
        saga_id=saga.id if saga else None,
        os_id=os_id,
    )
    resultado = handle_message(db, envelope.model_dump_json(), saga_reply_handler)
    db.expire_all()
    return resultado, envelope


def comandos_enviados(db: Session, os_id: int) -> list[str]:
    db.expire_all()
    rows = db.scalars(select(OutboxMessage).order_by(OutboxMessage.id)).all()
    return [r.message_type for r in rows if r.envelope.get("os_id") == os_id]


def ultimo_comando(db: Session, os_id: int) -> OutboxMessage:
    db.expire_all()
    rows = db.scalars(select(OutboxMessage).order_by(OutboxMessage.id)).all()
    return [r for r in rows if r.envelope.get("os_id") == os_id][-1]


def levar_ate_execucao(db: Session, os_id: int) -> None:
    """Percorre o caminho feliz até a OS estar agendada para execução."""
    responder(
        db, os_id, "OrcamentoGerado", {"orcamento_id": 10, "valor_total": "221.00"}
    )
    responder(db, os_id, "OrcamentoAprovado", {"orcamento_id": 10})
    responder(
        db,
        os_id,
        "PagamentoSolicitado",
        {"pagamento_id": 20, "checkout_url": "https://mp/checkout/20"},
    )
    responder(
        db,
        os_id,
        "PagamentoConfirmado",
        {"pagamento_id": 20, "mp_payment_id": "999", "valor": "221.00"},
    )
    responder(db, os_id, "ExecucaoAgendada", {"posicao_fila": 1})
