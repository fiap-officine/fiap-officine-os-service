import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.entities.messaging import OutboxMessage
from app.infrastructure.database import get_db
from app.messaging.sqs import get_bus
from app.saga.messages import OS_REPLIES

router = APIRouter(prefix="", tags=["Health & Observabilidade"])
settings = get_settings()

START_TIME = time.time()


@router.get("/health", summary="Healthcheck detalhado do serviço e dependências")
@router.get("/api/v1/health", summary="Healthcheck detalhado (prefixado)")
def get_health(response: Response, db: Session = Depends(get_db)):
    """
    Verifica a saúde do OS Service:
    - Banco de dados `os_db` (SELECT 1) — obrigatório (503 se falhar)
    - Fila SQS `os-saga-replies` — degradação parcial (não derruba o pod)
    - Tamanho do outbox pendente (mensagens ainda não publicadas)
    """
    services_status: dict = {}
    is_healthy = True

    try:
        db.execute(text("SELECT 1"))
        services_status["database"] = {"status": "up", "type": "PostgreSQL"}
    except Exception as exc:
        is_healthy = False
        services_status["database"] = {"status": "down", "error": str(exc)}

    try:
        get_bus().ping(OS_REPLIES)
        services_status["messaging"] = {"status": "up", "type": "SQS"}
    except Exception as exc:
        services_status["messaging"] = {"status": "down", "error": str(exc)[:200]}

    if is_healthy:
        try:
            pendentes = db.scalar(
                select(func.count())
                .select_from(OutboxMessage)
                .where(OutboxMessage.status == "pending")
            )
            services_status["outbox"] = {"pending": pendentes or 0}
        except Exception:  # pragma: no cover
            pass

    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "service": settings.SERVICE_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": round(time.time() - START_TIME, 2),
        "environment": settings.APP_ENV,
        "services": services_status,
        "version": "2.0.0",
    }
