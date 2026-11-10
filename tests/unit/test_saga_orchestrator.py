"""Testes unitários do orquestrador: cada transição e compensação."""

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.entities.ordem_servico import OrdemServico
from app.domain.enums import StatusOrdemServico
from app.saga import messages as m
from app.saga.orchestrator import SagaError, SagaOrchestrator
from tests.helpers import (
    comandos_enviados,
    criar_os,
    levar_ate_execucao,
    responder,
    saga_de,
    setup_dados,
    ultimo_comando,
)


@pytest.fixture
def os_id(client, auth_headers):
    ids = setup_dados(client, auth_headers)
    return criar_os(client, auth_headers, ids)["id"]


def _status(db, os_id) -> str:
    db.expire_all()
    return db.get(OrdemServico, os_id).status.value


def _sweep(db, delta: timedelta, **settings_overrides) -> int:
    agora = datetime.now(timezone.utc) + delta
    orq = SagaOrchestrator(db, clock=lambda: agora)
    for chave, valor in settings_overrides.items():
        orq.settings = orq.settings.model_copy(update={chave: valor})
    return orq.sweep_timeouts()


class TestCaminhoFeliz:
    def test_transicoes_em_ordem(self, db_session, os_id):
        responder(
            db_session,
            os_id,
            m.ORCAMENTO_GERADO,
            {"orcamento_id": 5, "valor_total": "1"},
        )
        assert saga_de(db_session, os_id).state == "APPROVAL_PENDING"
        assert _status(db_session, os_id) == "aguardando_aprovacao"

        responder(db_session, os_id, m.ORCAMENTO_APROVADO, {"orcamento_id": 5})
        assert saga_de(db_session, os_id).state == "PAYMENT_PENDING"
        cmd = ultimo_comando(db_session, os_id)
        assert cmd.message_type == m.SOLICITAR_PAGAMENTO
        assert cmd.envelope["payload"]["orcamento_id"] == 5
        assert cmd.destination == m.BILLING_COMMANDS

        responder(
            db_session,
            os_id,
            m.PAGAMENTO_SOLICITADO,
            {"pagamento_id": 9, "checkout_url": "https://mp/9"},
        )
        saga = saga_de(db_session, os_id)
        assert saga.pagamento_id == 9 and saga.checkout_url == "https://mp/9"

        responder(db_session, os_id, m.PAGAMENTO_CONFIRMADO, {"pagamento_id": 9})
        assert saga_de(db_session, os_id).state == "SCHEDULING"
        cmd = ultimo_comando(db_session, os_id)
        assert cmd.message_type == m.RESERVAR_E_ENFILEIRAR
        assert cmd.destination == m.EXECUTION_COMMANDS
        assert cmd.envelope["payload"]["pecas"][0]["quantidade"] == 2
        assert cmd.envelope["payload"]["servicos"][0]["tempo_estimado_minutos"] == 30

        responder(db_session, os_id, m.EXECUCAO_AGENDADA, {"posicao_fila": 3})
        saga = saga_de(db_session, os_id)
        assert (
            saga.state == "IN_EXECUTION" and saga.reserved and saga.deadline_at is None
        )

    def test_eventos_fora_de_ordem_avancam_estados_intermediarios(
        self, db_session, os_id
    ):
        levar_ate_execucao(db_session, os_id)
        # ExecucaoFinalizada chega antes de Diagnóstico/Reparo
        responder(db_session, os_id, m.EXECUCAO_FINALIZADA)
        db_session.expire_all()
        ordem = db_session.get(OrdemServico, os_id)
        assert ordem.status == StatusOrdemServico.FINALIZADA
        assert ordem.data_finalizacao is not None
        assert [h.status_novo for h in ordem.historico][-3:] == [
            "em_diagnostico",
            "em_execucao",
            "finalizada",
        ]
        # Evento atrasado não regride o status
        responder(db_session, os_id, m.DIAGNOSTICO_INICIADO)
        assert _status(db_session, os_id) == "finalizada"

    def test_mensagem_inesperada_e_registrada_como_ignorada(self, db_session, os_id):
        responder(db_session, os_id, m.PAGAMENTO_CONFIRMADO, {"pagamento_id": 1})
        saga = saga_de(db_session, os_id)
        assert saga.state == "BUDGET_PENDING"
        assert saga.steps[-1].direction == "ignored"

    def test_saga_inexistente_e_ignorada(self, db_session):
        from app.messaging.consumer import handle_message
        from app.messaging.envelope import new_envelope
        from app.workers import saga_reply_handler

        env = new_envelope(
            m.ORCAMENTO_GERADO, "reply", {}, source="x", saga_id="nao-existe"
        )
        assert (
            handle_message(db_session, env.model_dump_json(), saga_reply_handler)
            == "processed"
        )
        env = new_envelope(m.ORCAMENTO_GERADO, "reply", {}, source="x", os_id=12345)
        assert (
            handle_message(db_session, env.model_dump_json(), saga_reply_handler)
            == "processed"
        )

    def test_resposta_localizada_por_os_id(self, db_session, os_id):
        from app.messaging.consumer import handle_message
        from app.messaging.envelope import new_envelope
        from app.workers import saga_reply_handler

        env = new_envelope(
            m.ORCAMENTO_GERADO, "reply", {"orcamento_id": 1}, source="x", os_id=os_id
        )
        handle_message(db_session, env.model_dump_json(), saga_reply_handler)
        assert saga_de(db_session, os_id).state == "APPROVAL_PENDING"


class TestFalhasECompensacoes:
    def test_orcamento_falhou_cancela_sem_compensacoes_remotas(self, db_session, os_id):
        responder(db_session, os_id, m.ORCAMENTO_FALHOU, {"motivo": "sem itens"})
        saga = saga_de(db_session, os_id)
        assert saga.state == "CANCELLED"
        assert "sem itens" in saga.failure_reason
        assert _status(db_session, os_id) == "cancelada"
        assert comandos_enviados(db_session, os_id) == [m.GERAR_ORCAMENTO]

    def test_pagamento_recusado_cancela_orcamento(self, db_session, os_id):
        responder(db_session, os_id, m.ORCAMENTO_GERADO, {"orcamento_id": 5})
        responder(db_session, os_id, m.ORCAMENTO_APROVADO, {"orcamento_id": 5})
        responder(
            db_session, os_id, m.PAGAMENTO_RECUSADO, {"status_detail": "cc_rejected"}
        )
        saga = saga_de(db_session, os_id)
        assert saga.state == "COMPENSATING"
        assert saga.pending_compensations == [m.CANCELAR_ORCAMENTO]
        assert _status(db_session, os_id) == "em_compensacao"
        responder(db_session, os_id, m.ORCAMENTO_CANCELADO)
        assert saga_de(db_session, os_id).state == "CANCELLED"

    def test_reserva_falhou_estorna_e_cancela(self, db_session, os_id):
        responder(db_session, os_id, m.ORCAMENTO_GERADO, {"orcamento_id": 5})
        responder(db_session, os_id, m.ORCAMENTO_APROVADO, {"orcamento_id": 5})
        responder(db_session, os_id, m.PAGAMENTO_CONFIRMADO, {"pagamento_id": 7})
        responder(
            db_session,
            os_id,
            m.RESERVA_FALHOU,
            {"faltantes": [{"peca_id": 1, "disponivel": 0, "necessario": 2}]},
        )
        saga = saga_de(db_session, os_id)
        assert saga.pending_compensations == [
            m.ESTORNAR_PAGAMENTO,
            m.CANCELAR_ORCAMENTO,
        ]
        assert "Estoque insuficiente" in saga.failure_reason
        cmd = ultimo_comando(db_session, os_id)
        assert cmd.message_type == m.ESTORNAR_PAGAMENTO
        assert cmd.envelope["payload"]["pagamento_id"] == 7

    def test_confirmacao_de_compensacao_duplicada_e_ignorada(self, db_session, os_id):
        levar_ate_execucao(db_session, os_id)
        SagaOrchestrator(db_session).cancel(db_session.get(OrdemServico, os_id), "x")
        db_session.commit()
        responder(db_session, os_id, m.RESERVA_LIBERADA)
        responder(db_session, os_id, m.RESERVA_LIBERADA)  # duplicada (outro message_id)
        assert saga_de(db_session, os_id).pending_compensations == [
            m.ESTORNAR_PAGAMENTO,
            m.CANCELAR_ORCAMENTO,
        ]

    def test_confirmacao_fora_de_ordem_remove_da_lista(self, db_session, os_id):
        levar_ate_execucao(db_session, os_id)
        SagaOrchestrator(db_session).cancel(db_session.get(OrdemServico, os_id), "x")
        db_session.commit()
        responder(db_session, os_id, m.ORCAMENTO_CANCELADO)
        assert saga_de(db_session, os_id).pending_compensations == [
            m.LIBERAR_RESERVA,
            m.ESTORNAR_PAGAMENTO,
        ]

    def test_pagamento_tardio_durante_compensacao_gera_estorno(self, db_session, os_id):
        responder(db_session, os_id, m.ORCAMENTO_GERADO, {"orcamento_id": 5})
        responder(db_session, os_id, m.ORCAMENTO_APROVADO, {"orcamento_id": 5})
        _sweep(db_session, timedelta(hours=2))  # timeout do pagamento
        assert saga_de(db_session, os_id).pending_compensations == [
            m.CANCELAR_ORCAMENTO
        ]
        responder(db_session, os_id, m.PAGAMENTO_CONFIRMADO, {"pagamento_id": 3})
        assert saga_de(db_session, os_id).pending_compensations == [
            m.CANCELAR_ORCAMENTO,
            m.ESTORNAR_PAGAMENTO,
        ]
        responder(db_session, os_id, m.ORCAMENTO_CANCELADO)
        assert ultimo_comando(db_session, os_id).message_type == m.ESTORNAR_PAGAMENTO
        responder(db_session, os_id, m.PAGAMENTO_ESTORNADO)
        assert saga_de(db_session, os_id).state == "CANCELLED"

    def test_pagamento_tardio_apos_cancelamento_estorna(self, db_session, os_id):
        responder(db_session, os_id, m.ORCAMENTO_RECUSADO, {"orcamento_id": 5})
        # recusado no estado errado (BUDGET_PENDING) -> ignorado; cancela via API
        SagaOrchestrator(db_session).cancel(db_session.get(OrdemServico, os_id), "x")
        db_session.commit()
        responder(db_session, os_id, m.ORCAMENTO_CANCELADO)
        assert saga_de(db_session, os_id).state == "CANCELLED"
        responder(db_session, os_id, m.PAGAMENTO_CONFIRMADO, {"pagamento_id": 3})
        assert ultimo_comando(db_session, os_id).message_type == m.ESTORNAR_PAGAMENTO
        assert saga_de(db_session, os_id).state == "CANCELLED"

    def test_reserva_tardia_durante_e_apos_compensacao(self, db_session, os_id):
        responder(db_session, os_id, m.ORCAMENTO_GERADO, {"orcamento_id": 5})
        responder(db_session, os_id, m.ORCAMENTO_APROVADO, {"orcamento_id": 5})
        responder(db_session, os_id, m.PAGAMENTO_CONFIRMADO, {"pagamento_id": 3})
        responder(db_session, os_id, m.RESERVA_FALHOU, {"faltantes": []})
        responder(db_session, os_id, m.EXECUCAO_AGENDADA, {"posicao_fila": 1})
        assert saga_de(db_session, os_id).pending_compensations == [
            m.ESTORNAR_PAGAMENTO,
            m.LIBERAR_RESERVA,
            m.CANCELAR_ORCAMENTO,
        ]
        for resposta in (
            m.PAGAMENTO_ESTORNADO,
            m.RESERVA_LIBERADA,
            m.ORCAMENTO_CANCELADO,
        ):
            responder(db_session, os_id, resposta)
        assert saga_de(db_session, os_id).state == "CANCELLED"
        responder(db_session, os_id, m.EXECUCAO_AGENDADA, {"posicao_fila": 1})
        assert ultimo_comando(db_session, os_id).message_type == m.LIBERAR_RESERVA

    def test_cancelar_os_legada_sem_saga(self, db_session, client, auth_headers):
        ids = setup_dados(client, auth_headers)
        ordem = OrdemServico(
            cliente_id=ids[0],
            veiculo_id=ids[1],
            status=StatusOrdemServico.RECEBIDA,
            valor_total=0,
        )
        db_session.add(ordem)
        db_session.commit()
        assert SagaOrchestrator(db_session).cancel(ordem, "legada") is None
        assert ordem.status == StatusOrdemServico.CANCELADA
        with pytest.raises(SagaError):
            SagaOrchestrator(db_session).cancel(ordem, "de novo")

    def test_transicao_invalida_gera_erro(self, db_session, os_id):
        ordem = db_session.get(OrdemServico, os_id)
        with pytest.raises(SagaError):
            SagaOrchestrator(db_session)._set_os_status(
                ordem, StatusOrdemServico.ENTREGUE, None
            )


class TestTimeouts:
    def test_sem_prazo_vencido_nada_acontece(self, db_session, os_id):
        assert _sweep(db_session, timedelta(seconds=0)) == 0
        assert saga_de(db_session, os_id).state == "BUDGET_PENDING"

    def test_timeout_do_orcamento_cancela_orcamento(self, db_session, os_id):
        assert _sweep(db_session, timedelta(hours=1)) == 1
        saga = saga_de(db_session, os_id)
        assert saga.state == "COMPENSATING"
        assert saga.pending_compensations == [m.CANCELAR_ORCAMENTO]
        assert any(s.direction == "timeout" for s in saga.steps)

    def test_timeout_na_reserva_libera_reserva_por_seguranca(self, db_session, os_id):
        responder(db_session, os_id, m.ORCAMENTO_GERADO, {"orcamento_id": 5})
        responder(db_session, os_id, m.ORCAMENTO_APROVADO, {"orcamento_id": 5})
        responder(db_session, os_id, m.PAGAMENTO_CONFIRMADO, {"pagamento_id": 3})
        _sweep(db_session, timedelta(hours=1))
        assert saga_de(db_session, os_id).pending_compensations == [
            m.LIBERAR_RESERVA,
            m.ESTORNAR_PAGAMENTO,
            m.CANCELAR_ORCAMENTO,
        ]

    def test_compensacao_sem_resposta_e_reenviada_e_depois_falha(
        self, db_session, os_id
    ):
        _sweep(db_session, timedelta(hours=1))  # entra em COMPENSATING
        enviados_antes = comandos_enviados(db_session, os_id).count(
            m.CANCELAR_ORCAMENTO
        )
        _sweep(db_session, timedelta(hours=2), SAGA_COMPENSATION_MAX_ATTEMPTS=3)
        assert (
            comandos_enviados(db_session, os_id).count(m.CANCELAR_ORCAMENTO)
            == enviados_antes + 1
        )
        assert saga_de(db_session, os_id).compensation_attempts == 1
        _sweep(db_session, timedelta(hours=3), SAGA_COMPENSATION_MAX_ATTEMPTS=3)
        _sweep(db_session, timedelta(hours=4), SAGA_COMPENSATION_MAX_ATTEMPTS=3)
        saga = saga_de(db_session, os_id)
        assert saga.state == "FAILED"
        assert _status(db_session, os_id) == "em_compensacao"
        # Saga FAILED não é mais varrida
        assert _sweep(db_session, timedelta(hours=5)) == 0
