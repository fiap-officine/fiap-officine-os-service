"""Loops de background do OS Service.

1. **Consumer** de `os-saga-replies` -> orquestrador da saga.
2. **Outbox relay** -> publica comandos pendentes no SQS.
3. **Varredor de timeouts** -> dispara compensação de sagas vencidas.

Podem rodar dentro do processo da API (`RUN_WORKERS=true`, via lifespan) ou
como processo separado (`python -m app.worker`).
"""

import logging
import threading
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.infrastructure.database import SessionLocal
from app.messaging.consumer import poll_once
from app.messaging.envelope import Envelope
from app.messaging.outbox import relay_pending
from app.messaging.sqs import SqsBus, get_bus
from app.saga.messages import OS_REPLIES
from app.saga.orchestrator import SagaOrchestrator

logger = logging.getLogger(__name__)


def saga_reply_handler(db: Session, envelope: Envelope) -> None:
    SagaOrchestrator(db).handle(envelope)


def run_outbox_relay_once(
    session_factory: Callable[[], Session] = SessionLocal,
    bus: SqsBus | None = None,
) -> int:
    db = session_factory()
    try:
        return relay_pending(db, bus or get_bus())
    finally:
        db.close()


def run_consumer_once(
    session_factory: Callable[[], Session] = SessionLocal,
    bus: SqsBus | None = None,
    wait_seconds: int | None = None,
) -> int:
    return poll_once(
        bus or get_bus(),
        OS_REPLIES,
        session_factory,
        saga_reply_handler,
        wait_seconds=wait_seconds,
    )


def run_sweeper_once(session_factory: Callable[[], Session] = SessionLocal) -> int:
    db = session_factory()
    try:
        return SagaOrchestrator(db).sweep_timeouts()
    finally:
        db.close()


class BackgroundWorkers:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    def _loop(self, name: str, func: Callable[[], object], interval: float) -> None:
        logger.info("Worker '%s' iniciado", name)
        while not self._stop.is_set():
            try:
                func()
            except Exception as exc:
                logger.error("Erro no worker '%s': %s", name, exc, exc_info=True)
                self._stop.wait(5)
                continue
            if interval:
                self._stop.wait(interval)
        logger.info("Worker '%s' encerrado", name)

    def start(self) -> None:
        loops = [
            ("saga-consumer", run_consumer_once, 0),
            (
                "outbox-relay",
                run_outbox_relay_once,
                self.settings.OUTBOX_RELAY_INTERVAL_SECONDS,
            ),
            (
                "saga-timeout-sweeper",
                run_sweeper_once,
                self.settings.SAGA_SWEEP_INTERVAL_SECONDS,
            ),
        ]
        for name, func, interval in loops:
            thread = threading.Thread(
                target=self._loop, args=(name, func, interval), name=name, daemon=True
            )
            thread.start()
            self._threads.append(thread)

    def stop(self, timeout: float = 25.0) -> None:
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=timeout)
        self._threads.clear()

    def wait(self) -> None:
        self._stop.wait()
