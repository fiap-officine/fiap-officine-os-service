"""Steps BDD da saga da Ordem de Serviço (pytest-bdd, Gherkin em português)."""

from datetime import timedelta

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from app.domain.entities.ordem_servico import OrdemServico
from app.domain.entities.saga import SagaInstance
from app.saga import messages as m
from tests.bdd.fakes import SagaHarness

scenarios("features/saga_ordem_servico.feature")


@pytest.fixture
def harness(sqs_bus, session_factory):
    return SagaHarness(sqs_bus, session_factory)


@pytest.fixture
def ctx():
    return {}


# ── Contexto ─────────────────────────────────────
@given("um cliente ativo com um veículo cadastrado")
def cliente_com_veiculo(client, auth_headers, ctx):
    cliente = client.post(
        "/api/v1/clientes/",
        json={"nome": "Maria BDD", "cpf_cnpj": "52998224725", "email": "maria@bdd.com"},
        headers=auth_headers,
    ).json()
    veiculo = client.post(
        "/api/v1/veiculos/",
        json={
            "cliente_id": cliente["id"],
            "placa": "BDD2026",
            "marca": "VW",
            "modelo": "Gol",
            "ano": 2019,
        },
        headers=auth_headers,
    ).json()
    ctx.update(cliente_id=cliente["id"], veiculo_id=veiculo["id"], pecas={})


@given(parsers.parse('uma peça "{nome}" com {qtd:d} unidades em estoque'))
def peca_em_estoque(client, auth_headers, harness, ctx, nome, qtd):
    peca = client.post(
        "/api/v1/pecas/", json={"nome": nome, "preco": 120.0}, headers=auth_headers
    ).json()
    ctx["pecas"][nome] = peca["id"]
    harness.execution.estoque[peca["id"]] = qtd


# ── Ações ────────────────────────────────────────
@when(parsers.re(r'o cliente abre uma OS com (?P<qtd>\d+) unidades? de "(?P<nome>.+)"'))
def abrir_os(client, auth_headers, harness, ctx, qtd, nome):
    resp = client.post(
        "/api/v1/ordens-servico/",
        json={
            "cliente_id": ctx["cliente_id"],
            "veiculo_id": ctx["veiculo_id"],
            "itens_peca": [{"peca_id": ctx["pecas"][nome], "quantidade": int(qtd)}],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    ctx["os_id"] = resp.json()["id"]
    harness.pump()


@when("o cliente aprova o orçamento")
def cliente_aprova(harness):
    harness.billing.cliente_aprova()
    harness.pump()


@when("o cliente recusa o orçamento")
def cliente_recusa(harness):
    harness.billing.cliente_recusa()
    harness.pump()


@when("o Mercado Pago confirma o pagamento")
def mp_confirma(harness):
    harness.billing.mercado_pago_confirma()
    harness.pump()


@when("o mecânico finaliza a execução")
def mecanico_finaliza(harness):
    harness.execution.mecanico_finaliza()
    harness.pump()


@when("o prazo de pagamento expira")
def prazo_expira(harness):
    harness.avancar_relogio(timedelta(hours=1))


@when("o cliente cancela a OS")
def cliente_cancela(client, auth_headers, harness, ctx):
    resp = client.post(
        f"/api/v1/ordens-servico/{ctx['os_id']}/cancelar",
        json={"motivo": "Desistência"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    harness.pump()


@when(parsers.parse('o Billing entrega a resposta "{tipo}" duas vezes'))
def resposta_duplicada(harness, tipo):
    # O fake já respondeu uma vez durante o pump; reenvia o MESMO envelope.
    original = next(e for e in harness.billing.sent if e.type == tipo)
    harness.billing.publish(original)
    harness.pump()


# ── Verificações ─────────────────────────────────
def _ordem(db_session, ctx) -> OrdemServico:
    db_session.expire_all()
    return db_session.get(OrdemServico, ctx["os_id"])


@then(parsers.parse('o Billing deve receber o comando "{comando}"'))
def billing_recebeu(harness, comando):
    assert comando in harness.billing.comandos(), harness.billing.comandos()


@then(parsers.parse('o Billing não deve receber o comando "{comando}"'))
def billing_nao_recebeu(harness, comando):
    assert comando not in harness.billing.comandos(), harness.billing.comandos()


@then(parsers.parse('o Execution deve receber o comando "{comando}"'))
def execution_recebeu(harness, comando):
    assert comando in harness.execution.comandos(), harness.execution.comandos()


@then(parsers.parse('o Execution deve responder "{resposta}"'))
def execution_respondeu(harness, resposta):
    assert resposta in [e.type for e in harness.execution.sent]


@then(parsers.parse('a OS deve ficar "{status}"'))
def os_no_status(db_session, ctx, status):
    assert _ordem(db_session, ctx).status.value == status


@then(parsers.parse('a saga deve estar "{estado}"'))
def saga_no_estado(db_session, ctx, estado):
    db_session.expire_all()
    saga = db_session.query(SagaInstance).filter_by(os_id=ctx["os_id"]).one()
    assert saga.state == estado


@then(parsers.parse('o estoque de "{nome}" deve ser {qtd:d}'))
def estoque_igual(harness, ctx, nome, qtd):
    assert harness.execution.estoque[ctx["pecas"][nome]] == qtd


@then(parsers.parse('o histórico da OS deve conter "{a}" e "{b}"'))
def historico_contem(db_session, ctx, a, b):
    status = [h.status_novo for h in _ordem(db_session, ctx).historico]
    assert a in status and b in status, status


@then(parsers.parse('o histórico da OS deve ter {n:d} registro "{status}"'))
def historico_conta(db_session, ctx, n, status):
    registros = [
        h for h in _ordem(db_session, ctx).historico if h.status_novo == status
    ]
    assert len(registros) == n


def test_contrato_de_filas():
    """As compensações declaradas apontam para filas e respostas existentes."""
    for comando, (fila, resposta) in m.COMPENSATIONS.items():
        assert fila in (m.BILLING_COMMANDS, m.EXECUTION_COMMANDS)
        assert m.COMPENSATION_BY_REPLY[resposta] == comando
