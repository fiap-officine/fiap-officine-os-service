"""Orquestrador da Saga da Ordem de Serviço.

Fluxo (PLANO §4):
    T1 criar OS -> T2 GerarOrcamento -> T3 aprovação -> T4 pagamento
    -> T5 ReservarEEnfileirar -> T6 diagnóstico/reparo/finalização (pivô)

Compensações (ordem inversa): LiberarReserva -> EstornarPagamento
-> CancelarOrcamento -> cancelar OS. São executadas **uma por vez**, cada uma
aguardando a confirmação do participante antes de enviar a próxima.

O orquestrador não faz commit: quem chama (consumer ou endpoint) é dono da
transação. Assim, mudança de status da OS, estado da saga e mensagens do
outbox são gravados atomicamente.
"""

import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.domain.entities.ordem_servico import OrdemServico, OrdemServicoHistorico
from app.domain.entities.saga import SagaInstance, SagaLog
from app.domain.enums import (
    PROGRESSO_EXECUCAO,
    SAGA_FORWARD_WAITING,
    SAGA_TERMINAL,
    TRANSICOES_VALIDAS,
    SagaState,
    StatusOrdemServico,
)
from app.messaging import outbox
from app.messaging.envelope import Envelope, new_envelope
from app.messaging.tracing import record_event
from app.saga import messages as m

logger = logging.getLogger(__name__)

S = StatusOrdemServico
St = SagaState


class SagaError(Exception):
    """Erro de regra de negócio da saga (mapeado para 4xx na API)."""

    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.status_code = status_code


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class SagaOrchestrator:
    def __init__(
        self,
        db: Session,
        settings: Settings | None = None,
        clock: Callable[[], datetime] = _utcnow,
    ):
        self.db = db
        self.settings = settings or get_settings()
        self.clock = clock
        self._handlers: dict[tuple[SagaState, str], Callable] = {
            (St.BUDGET_PENDING, m.ORCAMENTO_GERADO): self._on_budget_created,
            (St.BUDGET_PENDING, m.ORCAMENTO_FALHOU): self._on_budget_failed,
            (St.APPROVAL_PENDING, m.ORCAMENTO_APROVADO): self._on_budget_approved,
            (St.APPROVAL_PENDING, m.ORCAMENTO_RECUSADO): self._on_budget_refused,
            (St.PAYMENT_PENDING, m.PAGAMENTO_SOLICITADO): self._on_payment_requested,
            (St.PAYMENT_PENDING, m.PAGAMENTO_CONFIRMADO): self._on_payment_confirmed,
            (St.PAYMENT_PENDING, m.PAGAMENTO_RECUSADO): self._on_payment_refused,
            (St.SCHEDULING, m.EXECUCAO_AGENDADA): self._on_scheduled,
            (St.SCHEDULING, m.RESERVA_FALHOU): self._on_reservation_failed,
            (St.IN_EXECUTION, m.DIAGNOSTICO_INICIADO): self._on_progress,
            (St.IN_EXECUTION, m.REPARO_INICIADO): self._on_progress,
            (St.IN_EXECUTION, m.EXECUCAO_FINALIZADA): self._on_finished,
            (St.COMPENSATING, m.RESERVA_LIBERADA): self._on_compensation_done,
            (St.COMPENSATING, m.PAGAMENTO_ESTORNADO): self._on_compensation_done,
            (St.COMPENSATING, m.ORCAMENTO_CANCELADO): self._on_compensation_done,
            # Respostas tardias que exigem compensação adicional
            (St.COMPENSATING, m.PAGAMENTO_CONFIRMADO): self._on_late_payment,
            (St.CANCELLED, m.PAGAMENTO_CONFIRMADO): self._on_late_payment,
            (St.COMPENSATING, m.EXECUCAO_AGENDADA): self._on_late_reservation,
            (St.CANCELLED, m.EXECUCAO_AGENDADA): self._on_late_reservation,
        }

    # ══════════════════════════════════════════
    # API pública
    # ══════════════════════════════════════════
    def start(self, ordem: OrdemServico) -> SagaInstance:
        """T1 -> T2: cria a saga e envia GerarOrcamento (mesma transação da OS)."""
        saga = SagaInstance(
            id=str(uuid.uuid4()),
            os_id=ordem.id,
            state=St.STARTED.value,
            pending_compensations=[],
            compensation_attempts=0,
            payment_confirmed=False,
            reserved=False,
        )
        self.db.add(saga)
        self.db.flush()
        self._log(saga, "T1", "forward", None, None, "OS criada")

        payload = {
            "cliente": {
                "id": ordem.cliente.id,
                "nome": ordem.cliente.nome,
                "email": ordem.cliente.email,
            },
            "veiculo": {"id": ordem.veiculo.id, "placa": ordem.veiculo.placa},
            "itens": [
                {
                    "tipo": "servico",
                    "ref_id": item.servico_id,
                    "descricao": item.servico.nome if item.servico else None,
                    "quantidade": item.quantidade,
                    "valor_unitario": str(item.valor_unitario),
                }
                for item in ordem.itens_servico
            ]
            + [
                {
                    "tipo": "peca",
                    "ref_id": item.peca_id,
                    "descricao": item.peca.nome if item.peca else None,
                    "quantidade": item.quantidade,
                    "valor_unitario": str(item.valor_unitario),
                }
                for item in ordem.itens_peca
            ],
        }
        self._transition(
            saga, St.BUDGET_PENDING, self.settings.SAGA_BUDGET_TIMEOUT_SECONDS
        )
        self._set_os_status(
            ordem, S.AGUARDANDO_ORCAMENTO, "Orçamento solicitado ao Billing"
        )
        self._send(saga, m.BILLING_COMMANDS, m.GERAR_ORCAMENTO, payload, "T2")
        return saga

    def handle(self, envelope: Envelope) -> None:
        """Processa uma resposta/evento vindo de um participante."""
        saga = self._load_saga(envelope)
        if saga is None:
            logger.warning(
                "Saga não encontrada para mensagem %s (saga_id=%s, os_id=%s)",
                envelope.type,
                envelope.saga_id,
                envelope.os_id,
            )
            return
        ordem = saga.ordem_servico
        handler = self._handlers.get((SagaState(saga.state), envelope.type))
        if handler is None:
            self._log(
                saga,
                saga.state,
                "ignored",
                envelope.type,
                envelope.message_id,
                f"Mensagem inesperada no estado {saga.state}",
            )
            logger.info("Mensagem %s ignorada no estado %s", envelope.type, saga.state)
            return
        self._log(saga, saga.state, "reply", envelope.type, envelope.message_id, None)
        handler(saga, ordem, envelope)

    def cancel(self, ordem: OrdemServico, reason: str) -> SagaInstance | None:
        """Cancelamento solicitado pelo cliente/operador."""
        saga = ordem.saga
        if saga is None:
            # OS legada (anterior à Fase 4): cancela localmente se permitido.
            if S.CANCELADA not in TRANSICOES_VALIDAS.get(ordem.status, []):
                raise SagaError(
                    f"OS em '{ordem.status.value}' não pode ser cancelada", 400
                )
            self._set_os_status(ordem, S.CANCELADA, reason)
            return None

        saga = self._lock(saga.id)
        state = SagaState(saga.state)
        if state in SAGA_TERMINAL or state == St.COMPENSATING:
            raise SagaError(f"Saga já está em {state.value}")
        if state == St.IN_EXECUTION and ordem.status not in (
            S.AGUARDANDO_EXECUCAO,
            S.EM_DIAGNOSTICO,
        ):
            raise SagaError(
                "Reparo já iniciado (pivô da saga): não há compensação possível. "
                "Use recuperação para frente."
            )
        self._begin_compensation(
            saga,
            ordem,
            reason,
            include_reservation=saga.reserved or state == St.SCHEDULING,
        )
        return saga

    def sweep_timeouts(self) -> int:
        """Dispara compensação para sagas com prazo vencido. Retorna quantas tratou."""
        now = self.clock()
        ids = list(
            self.db.scalars(
                select(SagaInstance.id).where(
                    SagaInstance.deadline_at.is_not(None),
                    SagaInstance.deadline_at <= now,
                    SagaInstance.state.not_in([s.value for s in SAGA_TERMINAL]),
                )
            ).all()
        )
        handled = 0
        for saga_id in ids:
            saga = self._lock(saga_id)
            deadline = _as_aware(saga.deadline_at)
            if deadline is None or deadline > now:
                continue
            state = SagaState(saga.state)
            ordem = saga.ordem_servico
            if state in SAGA_FORWARD_WAITING:
                self._log(saga, state.value, "timeout", None, None, "Prazo expirado")
                self._begin_compensation(
                    saga,
                    ordem,
                    f"Timeout aguardando {state.value}",
                    include_reservation=state == St.SCHEDULING,
                )
            elif state == St.COMPENSATING:
                self._retry_compensation(saga, ordem)
            self.db.commit()
            handled += 1
        return handled

    # ══════════════════════════════════════════
    # Handlers do caminho feliz
    # ══════════════════════════════════════════
    def _on_budget_created(self, saga, ordem, env: Envelope) -> None:
        saga.orcamento_id = env.payload.get("orcamento_id")
        self._transition(
            saga, St.APPROVAL_PENDING, self.settings.SAGA_APPROVAL_TIMEOUT_SECONDS
        )
        self._set_os_status(
            ordem,
            S.AGUARDANDO_APROVACAO,
            f"Orçamento #{saga.orcamento_id} gerado: R$ {env.payload.get('valor_total')}",
        )

    def _on_budget_approved(self, saga, ordem, env: Envelope) -> None:
        self._transition(
            saga, St.PAYMENT_PENDING, self.settings.SAGA_PAYMENT_TIMEOUT_SECONDS
        )
        self._set_os_status(
            ordem, S.AGUARDANDO_PAGAMENTO, "Orçamento aprovado pelo cliente"
        )
        self._send(
            saga,
            m.BILLING_COMMANDS,
            m.SOLICITAR_PAGAMENTO,
            {
                "orcamento_id": saga.orcamento_id,
                "valor": str(ordem.valor_total),
                "descricao": f"Oficina - OS #{ordem.id}",
            },
            "T4",
        )

    def _on_payment_requested(self, saga, ordem, env: Envelope) -> None:
        saga.pagamento_id = env.payload.get("pagamento_id")
        saga.checkout_url = env.payload.get("checkout_url")

    def _on_payment_confirmed(self, saga, ordem, env: Envelope) -> None:
        saga.payment_confirmed = True
        saga.pagamento_id = env.payload.get("pagamento_id") or saga.pagamento_id
        self._transition(
            saga, St.SCHEDULING, self.settings.SAGA_SCHEDULING_TIMEOUT_SECONDS
        )
        self._set_os_status(
            ordem,
            S.AGUARDANDO_EXECUCAO,
            f"Pagamento confirmado (MP {env.payload.get('mp_payment_id')})",
        )
        self._send(
            saga,
            m.EXECUTION_COMMANDS,
            m.RESERVAR_E_ENFILEIRAR,
            {
                "pecas": [
                    {"peca_id": i.peca_id, "quantidade": i.quantidade}
                    for i in ordem.itens_peca
                ],
                "servicos": [
                    {
                        "servico_id": i.servico_id,
                        "quantidade": i.quantidade,
                        "tempo_estimado_minutos": (
                            i.servico.tempo_estimado_minutos if i.servico else None
                        ),
                    }
                    for i in ordem.itens_servico
                ],
                "prioridade": "normal",
            },
            "T5",
        )

    def _on_scheduled(self, saga, ordem, env: Envelope) -> None:
        saga.reserved = True
        self._transition(saga, St.IN_EXECUTION, None)
        self._add_history(
            ordem,
            ordem.status.value,
            ordem.status.value,
            f"Peças reservadas; posição na fila: {env.payload.get('posicao_fila')}",
        )

    def _on_progress(self, saga, ordem, env: Envelope) -> None:
        target = {
            m.DIAGNOSTICO_INICIADO: S.EM_DIAGNOSTICO,
            m.REPARO_INICIADO: S.EM_EXECUCAO,
        }[env.type]
        self._advance(ordem, target, env.payload.get("observacao"))

    def _on_finished(self, saga, ordem, env: Envelope) -> None:
        self._advance(ordem, S.FINALIZADA, env.payload.get("observacao"))
        ordem.data_finalizacao = self.clock()
        self._transition(saga, St.COMPLETED, None)

    # ══════════════════════════════════════════
    # Falhas e compensação
    # ══════════════════════════════════════════
    def _on_budget_failed(self, saga, ordem, env: Envelope) -> None:
        self._begin_compensation(
            saga,
            ordem,
            f"Falha ao gerar orçamento: {env.payload.get('motivo')}",
            cancel_budget=False,
        )

    def _on_budget_refused(self, saga, ordem, env: Envelope) -> None:
        motivo = env.payload.get("motivo") or "sem motivo informado"
        self._begin_compensation(saga, ordem, f"Orçamento recusado: {motivo}")

    def _on_payment_refused(self, saga, ordem, env: Envelope) -> None:
        self._begin_compensation(
            saga, ordem, f"Pagamento recusado: {env.payload.get('status_detail')}"
        )

    def _on_reservation_failed(self, saga, ordem, env: Envelope) -> None:
        faltantes = env.payload.get("faltantes") or []
        detalhe = ", ".join(
            f"peça {f.get('peca_id')} (disp. {f.get('disponivel')}, nec. {f.get('necessario')})"
            for f in faltantes
        )
        self._begin_compensation(
            saga,
            ordem,
            f"Estoque insuficiente: {detalhe}"[:500],
            include_reservation=False,
        )

    def _begin_compensation(
        self,
        saga: SagaInstance,
        ordem: OrdemServico,
        reason: str,
        include_reservation: bool = False,
        cancel_budget: bool | None = None,
    ) -> None:
        state = SagaState(saga.state)
        if cancel_budget is None:
            # Em timeout de BUDGET_PENDING o Billing pode ter criado o orçamento
            # e a resposta se perdido: CancelarOrcamento é idempotente.
            cancel_budget = saga.orcamento_id is not None or state == St.BUDGET_PENDING
        pending: list[str] = []
        if saga.reserved or include_reservation:
            pending.append(m.LIBERAR_RESERVA)
        if saga.payment_confirmed:
            pending.append(m.ESTORNAR_PAGAMENTO)
        if cancel_budget:
            pending.append(m.CANCELAR_ORCAMENTO)

        saga.failure_reason = reason[:500]
        saga.pending_compensations = pending
        saga.compensation_attempts = 0
        self._transition(saga, St.COMPENSATING, None)
        self._set_os_status(ordem, S.EM_COMPENSACAO, reason[:500])
        record_event(
            "SagaCompensationEvent",
            {
                "saga_id": saga.id,
                "os_id": ordem.id,
                "from_state": state.value,
                "reason": reason[:255],
                "compensations": ",".join(pending),
            },
        )
        logger.warning("Iniciando compensação: %s", reason)
        self._send_next_compensation(saga, ordem)

    def _send_next_compensation(self, saga: SagaInstance, ordem: OrdemServico) -> None:
        if not saga.pending_compensations:
            self._finish_cancellation(saga, ordem)
            return
        command = saga.pending_compensations[0]
        queue, _ = m.COMPENSATIONS[command]
        self._send(
            saga,
            queue,
            command,
            self._compensation_payload(saga, command),
            "C",
            direction="compensation",
        )
        saga.deadline_at = self.clock() + timedelta(
            seconds=self.settings.SAGA_COMPENSATION_TIMEOUT_SECONDS
        )

    def _compensation_payload(self, saga: SagaInstance, command: str) -> dict:
        if command == m.LIBERAR_RESERVA:
            return {"motivo": saga.failure_reason}
        if command == m.ESTORNAR_PAGAMENTO:
            return {
                "orcamento_id": saga.orcamento_id,
                "pagamento_id": saga.pagamento_id,
                "motivo": saga.failure_reason,
            }
        return {"orcamento_id": saga.orcamento_id, "motivo": saga.failure_reason}

    def _on_compensation_done(self, saga, ordem, env: Envelope) -> None:
        command = m.COMPENSATION_BY_REPLY[env.type]
        pending = list(saga.pending_compensations)
        if command not in pending:
            return  # confirmação duplicada/atrasada
        was_current = pending[0] == command
        pending.remove(command)
        saga.pending_compensations = pending
        if was_current:
            saga.compensation_attempts = 0
            self._send_next_compensation(saga, ordem)

    def _retry_compensation(self, saga: SagaInstance, ordem: OrdemServico) -> None:
        saga.compensation_attempts += 1
        if saga.compensation_attempts >= self.settings.SAGA_COMPENSATION_MAX_ATTEMPTS:
            self._transition(saga, St.FAILED, None)
            self._log(
                saga,
                St.FAILED.value,
                "compensation",
                saga.pending_compensations[0] if saga.pending_compensations else None,
                None,
                "Compensação esgotou as tentativas: intervenção manual necessária",
            )
            record_event(
                "SagaFailedEvent",
                {
                    "saga_id": saga.id,
                    "os_id": ordem.id,
                    "pending": ",".join(saga.pending_compensations),
                },
            )
            logger.error("Saga FAILED: compensação esgotou as tentativas")
            return
        self._send_next_compensation(saga, ordem)

    def _finish_cancellation(self, saga: SagaInstance, ordem: OrdemServico) -> None:
        self._set_os_status(ordem, S.CANCELADA, "Compensações concluídas")
        self._transition(saga, St.CANCELLED, None)

    def _on_late_payment(self, saga, ordem, env: Envelope) -> None:
        """Pagamento confirmado depois que a saga já estava compensando."""
        saga.payment_confirmed = True
        saga.pagamento_id = env.payload.get("pagamento_id") or saga.pagamento_id
        if SagaState(saga.state) == St.COMPENSATING:
            pending = list(saga.pending_compensations)
            if m.ESTORNAR_PAGAMENTO not in pending:
                # Entra logo após a compensação em andamento.
                pending.insert(1 if pending else 0, m.ESTORNAR_PAGAMENTO)
                saga.pending_compensations = pending
                if len(pending) == 1:
                    self._send_next_compensation(saga, ordem)
        else:
            self._send(
                saga,
                m.BILLING_COMMANDS,
                m.ESTORNAR_PAGAMENTO,
                self._compensation_payload(saga, m.ESTORNAR_PAGAMENTO),
                "C",
                direction="compensation",
            )

    def _on_late_reservation(self, saga, ordem, env: Envelope) -> None:
        """Reserva efetivada depois que a saga já estava compensando."""
        saga.reserved = True
        if SagaState(saga.state) == St.COMPENSATING:
            pending = list(saga.pending_compensations)
            if m.LIBERAR_RESERVA not in pending:
                pending.insert(1 if pending else 0, m.LIBERAR_RESERVA)
                saga.pending_compensations = pending
                if len(pending) == 1:
                    self._send_next_compensation(saga, ordem)
        else:
            self._send(
                saga,
                m.EXECUTION_COMMANDS,
                m.LIBERAR_RESERVA,
                self._compensation_payload(saga, m.LIBERAR_RESERVA),
                "C",
                direction="compensation",
            )

    # ══════════════════════════════════════════
    # Utilitários
    # ══════════════════════════════════════════
    def _load_saga(self, envelope: Envelope) -> SagaInstance | None:
        saga_id = envelope.saga_id
        if saga_id is None and envelope.os_id is not None:
            saga_id = self.db.scalar(
                select(SagaInstance.id).where(SagaInstance.os_id == envelope.os_id)
            )
        if saga_id is None:
            return None
        return self._lock(saga_id, missing_ok=True)

    def _lock(self, saga_id: str, missing_ok: bool = False) -> SagaInstance | None:
        saga = self.db.scalar(
            select(SagaInstance)
            .where(SagaInstance.id == saga_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if saga is None and not missing_ok:
            raise SagaError("Saga não encontrada", 404)
        return saga

    def _transition(
        self, saga: SagaInstance, new_state: SagaState, timeout_seconds: int | None
    ) -> None:
        now = self.clock()
        previous = saga.state
        entered = _as_aware(saga.state_changed_at) or now
        saga.state = new_state.value
        saga.state_changed_at = now
        saga.deadline_at = (
            now + timedelta(seconds=timeout_seconds) if timeout_seconds else None
        )
        record_event(
            "SagaStepEvent",
            {
                "saga_id": saga.id,
                "os_id": saga.os_id,
                "step": new_state.value,
                "previous_step": previous,
                "duration_ms": int((now - entered).total_seconds() * 1000),
            },
        )

    def _send(
        self,
        saga: SagaInstance,
        queue: str,
        message_type: str,
        payload: dict,
        step: str,
        direction: str = "forward",
    ) -> Envelope:
        envelope = new_envelope(
            message_type,
            "command",
            payload,
            source=self.settings.SERVICE_NAME,
            saga_id=saga.id,
            os_id=saga.os_id,
            correlation_id=saga.correlation_id,
        )
        outbox.enqueue(self.db, queue, envelope)
        self._log(saga, step, direction, message_type, envelope.message_id, None)
        return envelope

    def _log(
        self,
        saga: SagaInstance,
        step: str,
        direction: str,
        message_type: str | None,
        message_id: str | None,
        detail: str | None,
    ) -> None:
        self.db.add(
            SagaLog(
                saga_id=saga.id,
                step=str(step),
                direction=direction,
                message_type=message_type,
                message_id=message_id,
                detail=detail[:1000] if detail else None,
            )
        )

    def _set_os_status(
        self, ordem: OrdemServico, novo: StatusOrdemServico, observacao: str | None
    ) -> None:
        atual = ordem.status
        if atual == novo:
            return
        if novo not in TRANSICOES_VALIDAS.get(atual, []):
            raise SagaError(
                f"Transição de '{atual.value}' para '{novo.value}' não é permitida", 409
            )
        ordem.status = novo
        self._add_history(ordem, atual.value, novo.value, observacao)

    def _advance(
        self, ordem: OrdemServico, target: StatusOrdemServico, observacao: str | None
    ) -> None:
        """Avança pelos estados de progresso (tolera eventos fora de ordem)."""
        if ordem.status not in PROGRESSO_EXECUCAO:
            logger.warning("Evento de progresso ignorado: OS em %s", ordem.status.value)
            return
        current_idx = PROGRESSO_EXECUCAO.index(ordem.status)
        target_idx = PROGRESSO_EXECUCAO.index(target)
        for status in PROGRESSO_EXECUCAO[current_idx + 1 : target_idx + 1]:
            self._set_os_status(ordem, status, observacao)

    def _add_history(
        self,
        ordem: OrdemServico,
        anterior: str | None,
        novo: str,
        observacao: str | None,
    ) -> None:
        historico = OrdemServicoHistorico(
            status_anterior=anterior,
            status_novo=novo,
            observacao=observacao[:500] if observacao else None,
        )
        ordem.historico.append(historico)
