"""Participantes fake da saga (Billing e Execution) para os testes BDD.

Consomem os comandos reais publicados pelo outbox relay nas filas SQS
(mockadas pelo moto) e respondem na fila `os-saga-replies`, exatamente como
os serviços reais. O orquestrador sob teste é o código de produção.
"""

import itertools
import json
from datetime import datetime, timedelta, timezone

from app.messaging.envelope import Envelope, new_envelope
from app.messaging.sqs import SqsBus
from app.saga import messages as m
from app.saga.orchestrator import SagaOrchestrator
from app.workers import run_consumer_once, run_outbox_relay_once


class _Participant:
    queue: str
    source: str

    def __init__(self, bus: SqsBus):
        self.bus = bus
        self.received: list[Envelope] = []
        self.sent: list[Envelope] = []

    def reply(self, origem: Envelope, message_type: str, payload: dict) -> None:
        envelope = new_envelope(
            message_type,
            "reply",
            payload,
            source=self.source,
            saga_id=origem.saga_id,
            os_id=origem.os_id,
            correlation_id=origem.correlation_id,
        )
        self.publish(envelope)

    def publish(self, envelope: Envelope) -> None:
        self.bus.send(m.OS_REPLIES, envelope.model_dump_json(), {"type": envelope.type})
        self.sent.append(envelope)

    def poll(self) -> int:
        count = 0
        for raw in self.bus.receive(self.queue, wait_seconds=0):
            envelope = Envelope.model_validate(json.loads(raw["Body"]))
            self.received.append(envelope)
            self.handle(envelope)
            self.bus.delete(self.queue, raw["ReceiptHandle"])
            count += 1
        return count

    def handle(self, envelope: Envelope) -> None:  # pragma: no cover - abstrato
        raise NotImplementedError

    def comandos(self) -> list[str]:
        return [e.type for e in self.received]

    def ultimo(self, message_type: str) -> Envelope:
        return [e for e in self.received if e.type == message_type][-1]


class FakeBilling(_Participant):
    queue = m.BILLING_COMMANDS
    source = "fake-billing"

    def __init__(self, bus: SqsBus):
        super().__init__(bus)
        self._ids = itertools.count(1)

    def handle(self, env: Envelope) -> None:
        if env.type == m.GERAR_ORCAMENTO:
            total = sum(
                float(i["valor_unitario"]) * i["quantidade"]
                for i in env.payload["itens"]
            )
            self.reply(
                env,
                m.ORCAMENTO_GERADO,
                {"orcamento_id": next(self._ids), "valor_total": f"{total:.2f}"},
            )
        elif env.type == m.SOLICITAR_PAGAMENTO:
            pagamento_id = next(self._ids)
            self.reply(
                env,
                m.PAGAMENTO_SOLICITADO,
                {
                    "pagamento_id": pagamento_id,
                    "checkout_url": f"https://sandbox.mercadopago/checkout/{pagamento_id}",
                },
            )
        elif env.type == m.ESTORNAR_PAGAMENTO:
            self.reply(
                env,
                m.PAGAMENTO_ESTORNADO,
                {"pagamento_id": env.payload.get("pagamento_id")},
            )
        elif env.type == m.CANCELAR_ORCAMENTO:
            self.reply(
                env,
                m.ORCAMENTO_CANCELADO,
                {"orcamento_id": env.payload.get("orcamento_id")},
            )

    # Ações externas (cliente / Mercado Pago)
    def cliente_aprova(self) -> None:
        origem = self.ultimo(m.GERAR_ORCAMENTO)
        self.reply(origem, m.ORCAMENTO_APROVADO, {"orcamento_id": 1})

    def cliente_recusa(self) -> None:
        origem = self.ultimo(m.GERAR_ORCAMENTO)
        self.reply(origem, m.ORCAMENTO_RECUSADO, {"orcamento_id": 1, "motivo": "caro"})

    def mercado_pago_confirma(self) -> None:
        origem = self.ultimo(m.SOLICITAR_PAGAMENTO)
        self.reply(
            origem,
            m.PAGAMENTO_CONFIRMADO,
            {
                "pagamento_id": 2,
                "mp_payment_id": "123456",
                "valor": origem.payload["valor"],
            },
        )


class FakeExecution(_Participant):
    queue = m.EXECUTION_COMMANDS
    source = "fake-execution"

    def __init__(self, bus: SqsBus):
        super().__init__(bus)
        self.estoque: dict[int, int] = {}
        self.reservas: dict[int, list[dict]] = {}

    def handle(self, env: Envelope) -> None:
        if env.type == m.RESERVAR_E_ENFILEIRAR:
            pecas = env.payload["pecas"]
            faltantes = [
                {
                    "peca_id": p["peca_id"],
                    "disponivel": self.estoque.get(p["peca_id"], 0),
                    "necessario": p["quantidade"],
                }
                for p in pecas
                if self.estoque.get(p["peca_id"], 0) < p["quantidade"]
            ]
            if faltantes:
                self.reply(env, m.RESERVA_FALHOU, {"faltantes": faltantes})
                return
            for p in pecas:
                self.estoque[p["peca_id"]] -= p["quantidade"]
            self.reservas[env.os_id] = pecas
            self.reply(env, m.EXECUCAO_AGENDADA, {"posicao_fila": len(self.reservas)})
        elif env.type == m.LIBERAR_RESERVA:
            for p in self.reservas.pop(env.os_id, []):
                self.estoque[p["peca_id"]] += p["quantidade"]
            self.reply(env, m.RESERVA_LIBERADA, {})

    def mecanico_finaliza(self) -> None:
        origem = self.ultimo(m.RESERVAR_E_ENFILEIRAR)
        self.reply(origem, m.DIAGNOSTICO_INICIADO, {"mecanico": "Zé"})
        self.reply(origem, m.REPARO_INICIADO, {"mecanico": "Zé"})
        self.reply(origem, m.EXECUCAO_FINALIZADA, {"observacao": "Pastilhas trocadas"})


class SagaHarness:
    """Bombeia mensagens entre outbox -> participantes -> orquestrador até
    o sistema ficar ocioso."""

    def __init__(self, bus: SqsBus, session_factory):
        self.bus = bus
        self.session_factory = session_factory
        self.billing = FakeBilling(bus)
        self.execution = FakeExecution(bus)

    def pump(self, max_rounds: int = 50) -> None:
        for _ in range(max_rounds):
            atividade = run_outbox_relay_once(self.session_factory, self.bus)
            atividade += self.billing.poll()
            atividade += self.execution.poll()
            atividade += run_consumer_once(
                self.session_factory, self.bus, wait_seconds=0
            )
            if not atividade:
                return
        raise AssertionError("A saga não estabilizou (possível loop de mensagens)")

    def avancar_relogio(self, delta: timedelta) -> None:
        agora = datetime.now(timezone.utc) + delta
        db = self.session_factory()
        try:
            SagaOrchestrator(db, clock=lambda: agora).sweep_timeouts()
        finally:
            db.close()
        self.pump()
