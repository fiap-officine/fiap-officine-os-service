import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.health import router as health_router
from app.api.v1.internal import router as internal_router
from app.api.v1.router import router
from app.config import get_settings
from app.core.logging import setup_json_logging
from app.core.middleware import ObservabilityMiddleware

settings = get_settings()

# ── Logs estruturados em JSON ───────────────────
setup_json_logging(
    service_name=settings.NEW_RELIC_APP_NAME,
    environment=settings.APP_ENV,
    log_level=settings.LOG_LEVEL,
)
logger = logging.getLogger("app.main")

# ── APM New Relic ───────────────────────────────
if settings.NEW_RELIC_LICENSE_KEY or os.getenv("NEW_RELIC_LICENSE_KEY"):
    try:
        import newrelic.agent

        os.environ.setdefault("NEW_RELIC_APP_NAME", settings.NEW_RELIC_APP_NAME)
        os.environ.setdefault("NEW_RELIC_DISTRIBUTED_TRACING_ENABLED", "true")
        os.environ.setdefault("NEW_RELIC_LOG_LEVEL", "info")
        newrelic.agent.initialize()
        logger.info("Agente APM New Relic inicializado com sucesso.")
    except Exception as exc:  # pragma: no cover
        logger.warning(f"Não foi possível inicializar o New Relic: {exc}")


@asynccontextmanager
async def lifespan(_: FastAPI):
    workers = None
    if settings.RUN_WORKERS:
        from app.workers import BackgroundWorkers

        workers = BackgroundWorkers(settings)
        workers.start()
        logger.info("Workers da saga iniciados no processo da API")
    yield
    if workers is not None:
        workers.stop()


app = FastAPI(
    title="Oficina Mecânica - OS Service",
    description=(
        "Microsserviço de Ordens de Serviço (clientes, veículos, catálogo, OS) e "
        "**orquestrador da Saga** da OS: orçamento (Billing) -> aprovação -> "
        "pagamento (Mercado Pago) -> reserva/execução (Execution), com "
        "compensações. Tech Challenge FIAP SOAT - Fase 4."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(ObservabilityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.APP_ENV == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(internal_router)
app.include_router(router)


@app.get("/", tags=["Health"])
def root_check():
    """Verifica se o serviço está no ar."""
    return {"status": "ok", "service": settings.SERVICE_NAME, "version": "2.0.0"}
