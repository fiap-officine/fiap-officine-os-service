"""Outbox, consumer idempotente, SQS e workers."""

import json
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.domain.entities.messaging import OutboxMessage, ProcessedMessage
from app.messaging import tracing
from app.messaging.consumer import handle_message, poll_once
from app.messaging.envelope import new_envelope
from app.messaging.outbox import enqueue, relay_pending
from app.messaging.sqs import SqsBus, get_bus, set_bus
from app.saga import messages as m
from app.workers import (
    BackgroundWorkers,
    run_consumer_once,
    run_outbox_relay_once,
    run_sweeper_once,
)
from tests.conftest import drain_queue


def _env(tipo="X", **kw):
    return new_envelope(tipo, "command", {"a": 1}, source="teste", **kw)


class TestOutbox:
    def test_relay_publica_e_marca_enviado(self, db_session, sqs_bus):
        enqueue(db_session, m.BILLING_COMMANDS, _env(saga_id="s1", os_id=1))
        db_session.commit()
        assert relay_pending(db_session, sqs_bus) == 1
        msg = db_session.scalar(select(OutboxMessage))
        assert msg.status == "sent" and msg.sent_at is not None
        recebidas = drain_queue(sqs_bus, m.BILLING_COMMANDS)
        assert len(recebidas) == 1
        corpo = json.loads(recebidas[0]["Body"])
        assert corpo["saga_id"] == "s1"
        assert recebidas[0]["MessageAttributes"]["type"]["StringValue"] == "X"
        # Nada pendente na segunda volta
        assert relay_pending(db_session, sqs_bus) == 0

    def test_falha_no_publish_mantem_pendente(self, db_session):
        enqueue(db_session, m.BILLING_COMMANDS, _env())
        db_session.commit()
        bus = MagicMock()
        bus.send.side_effect = RuntimeError("SQS fora")
        assert relay_pending(db_session, bus) == 0
        msg = db_session.scalar(select(OutboxMessage))
        assert msg.status == "pending"
        assert msg.attempts == 1
        assert "SQS fora" in msg.last_error

    def test_enqueue_injeta_headers_de_trace(self, db_session):
        with patch(
            "app.messaging.outbox.inject_trace_headers",
            return_value={"traceparent": "00-x"},
        ):
            msg = enqueue(db_session, m.BILLING_COMMANDS, _env())
        assert msg.envelope["trace"] == {"traceparent": "00-x"}


class TestConsumer:
    def test_mensagem_invalida(self, db_session):
        assert handle_message(db_session, "nao-e-json", lambda db, e: None) == "invalid"
        assert (
            handle_message(db_session, json.dumps({"x": 1}), lambda db, e: None)
            == "invalid"
        )

    def test_processa_uma_vez(self, db_session):
        chamadas = []
        corpo = _env().model_dump_json()
        assert (
            handle_message(db_session, corpo, lambda db, e: chamadas.append(e))
            == "processed"
        )
        assert (
            handle_message(db_session, corpo, lambda db, e: chamadas.append(e))
            == "duplicate"
        )
        assert len(chamadas) == 1
        assert db_session.scalar(select(ProcessedMessage)).message_type == "X"

    def test_erro_no_handler_faz_rollback_e_propaga(self, db_session):
        corpo = _env().model_dump_json()

        def explode(db, env):
            raise ValueError("boom")

        with pytest.raises(ValueError):
            handle_message(db_session, corpo, explode)
        assert db_session.scalar(select(ProcessedMessage)) is None

    def test_corrida_detectada_pela_pk(self, db_session):
        """Outro consumidor commitou o mesmo message_id entre a checagem e o
        commit: a violação de PK vira 'duplicate'."""
        from sqlalchemy.exc import IntegrityError

        def violacao(db, e):
            raise IntegrityError("INSERT", {}, Exception("unique"))

        corpo = _env().model_dump_json()
        with patch(
            "app.messaging.consumer.already_processed", side_effect=[False, True]
        ):
            assert handle_message(db_session, corpo, violacao) == "duplicate"
        with patch(
            "app.messaging.consumer.already_processed", side_effect=[False, False]
        ):
            with pytest.raises(IntegrityError):
                handle_message(db_session, corpo, violacao)

    def test_poll_once_apaga_sucesso_e_mantem_falha(self, sqs_bus, session_factory):
        sqs_bus.send(m.OS_REPLIES, _env("Ok").model_dump_json(), {})
        sqs_bus.send(m.OS_REPLIES, _env("Falha").model_dump_json(), {})

        def handler(db, env):
            if env.type == "Falha":
                raise RuntimeError("erro")

        with patch("app.messaging.consumer.record_event") as rec:
            assert (
                poll_once(
                    sqs_bus, m.OS_REPLIES, session_factory, handler, wait_seconds=0
                )
                == 1
            )
        rec.assert_called_once()


class TestSqsBus:
    def test_cache_de_url_e_ping(self, sqs_bus):
        url = sqs_bus.queue_url(m.OS_REPLIES)
        assert url.endswith("fiap-officine-os-saga-replies")
        assert sqs_bus.queue_url(m.OS_REPLIES) is url
        assert sqs_bus.ping(m.OS_REPLIES) is True

    def test_get_bus_singleton(self):
        set_bus(None)
        bus = get_bus()
        assert isinstance(bus, SqsBus) and get_bus() is bus
        set_bus(None)

    def test_nome_sem_prefixo(self):
        from app.config import Settings

        assert Settings(SQS_QUEUE_PREFIX="").queue_name("fila") == "fila"


class TestWorkers:
    def test_run_once_helpers(self, db_session, session_factory, sqs_bus):
        enqueue(db_session, m.BILLING_COMMANDS, _env())
        db_session.commit()
        assert run_outbox_relay_once(session_factory, sqs_bus) == 1
        assert run_consumer_once(session_factory, sqs_bus, wait_seconds=0) == 0
        assert run_sweeper_once(session_factory) == 0

    def test_background_workers_start_stop(self):
        workers = BackgroundWorkers()
        chamadas = []
        with (
            patch(
                "app.workers.run_consumer_once", side_effect=lambda: chamadas.append(1)
            ),
            patch("app.workers.run_outbox_relay_once", side_effect=RuntimeError("x")),
            patch("app.workers.run_sweeper_once", return_value=0),
        ):
            workers.start()
            assert len(workers._threads) == 3
            workers.stop(timeout=5)
        assert workers._threads == []
        assert chamadas


class TestTracing:
    def test_funcoes_com_agente_fake(self):
        agente = MagicMock()
        agente.insert_distributed_trace_headers.side_effect = lambda headers: (
            headers.append(("traceparent", "00-abc"))
        )
        agente.application.return_value = MagicMock(enabled=False)
        with patch("app.messaging.tracing._agent", return_value=agente):
            assert tracing.inject_trace_headers() == {"traceparent": "00-abc"}
            tracing.accept_trace_headers({"traceparent": "00-abc"})
            agente.accept_distributed_trace_headers.assert_called_once()
            tracing.record_event("E", {"a": 1})
            agente.record_custom_event.assert_called_once_with("E", {"a": 1})
            tracing.add_attributes({"saga_id": "s", "nada": None})
            agente.add_custom_attribute.assert_called_once_with("saga_id", "s")
            with tracing.background_transaction("x"):
                pass

    def test_funcoes_sem_agente(self):
        with patch("app.messaging.tracing._agent", return_value=None):
            assert tracing.inject_trace_headers() == {}
            tracing.accept_trace_headers({"a": "b"})
            tracing.record_event("E", {})
            tracing.add_attributes({"a": 1})
            with tracing.background_transaction("x"):
                pass
