from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Banco relacional (os_db) ─────────────────
    DB_USER: str = "dbadmin"
    DB_PASSWORD: str = "password"
    DB_HOST: str = "localhost"
    DB_PORT: str = "5432"
    DB_NAME: str = "os_db"

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # ── Autenticação ─────────────────────────────
    JWT_SECRET_KEY: str = "default-secret-key-change-in-production-12345"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    BCRYPT_ROUNDS: int = 12
    AUTH_LAMBDA_URL: str | None = None
    # Token usado por chamadas service-to-service (ex.: Lambda -> /internal/*)
    INTERNAL_API_TOKEN: str = "change-me-internal"

    # ── Aplicação ────────────────────────────────
    APP_ENV: str = "development"
    APP_DEBUG: bool = False
    SERVICE_NAME: str = "os-service"

    # ── Mensageria (Amazon SQS) ──────────────────
    AWS_REGION: str = "us-east-2"
    # Preenchido apenas em ambiente local (LocalStack): http://localhost:4566
    AWS_ENDPOINT_URL: str | None = None
    SQS_QUEUE_PREFIX: str = "fiap-officine"
    SQS_BILLING_COMMANDS: str = "billing-commands"
    SQS_EXECUTION_COMMANDS: str = "execution-commands"
    SQS_OS_REPLIES: str = "os-saga-replies"
    SQS_WAIT_TIME_SECONDS: int = 20
    SQS_MAX_MESSAGES: int = 10

    # Executa consumer + outbox relay + varredor de timeouts dentro do processo
    # da API (lifespan). Evita um pod extra no nó K3s t3.micro (ver PLANO §9.3).
    RUN_WORKERS: bool = False
    OUTBOX_RELAY_INTERVAL_SECONDS: float = 1.0
    SAGA_SWEEP_INTERVAL_SECONDS: float = 15.0

    # ── Timeouts da saga (segundos) ──────────────
    SAGA_BUDGET_TIMEOUT_SECONDS: int = 300
    SAGA_APPROVAL_TIMEOUT_SECONDS: int = 172800  # 48h
    SAGA_PAYMENT_TIMEOUT_SECONDS: int = 1800  # 30 min (2 min na demo)
    SAGA_SCHEDULING_TIMEOUT_SECONDS: int = 300
    SAGA_COMPENSATION_TIMEOUT_SECONDS: int = 120
    SAGA_COMPENSATION_MAX_ATTEMPTS: int = 5

    # ── Observabilidade & New Relic ──────────────
    NEW_RELIC_LICENSE_KEY: str | None = None
    NEW_RELIC_APP_NAME: str = "officine-os-service"
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": ".env", "extra": "ignore"}

    def queue_name(self, logical_name: str) -> str:
        """Nome físico da fila: <prefixo>-<nome lógico>."""
        if not self.SQS_QUEUE_PREFIX:
            return logical_name
        return f"{self.SQS_QUEUE_PREFIX}-{logical_name}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
