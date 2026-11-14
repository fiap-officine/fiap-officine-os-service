import os

# ── Ambiente de teste: definido ANTES de importar a aplicação ──
os.environ["NEW_RELIC_LICENSE_KEY"] = ""
os.environ["RUN_WORKERS"] = "false"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-2"
os.environ["AWS_REGION"] = "us-east-2"
os.environ.pop("AWS_ENDPOINT_URL", None)
os.environ["SQS_WAIT_TIME_SECONDS"] = "0"
os.environ["INTERNAL_API_TOKEN"] = "token-interno-teste"
os.environ["BCRYPT_ROUNDS"] = "4"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from moto import mock_aws  # noqa: E402
from sqlalchemy import StaticPool, create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import app.domain.entities  # noqa: E402,F401  (registra todos os modelos)
from app.config import get_settings  # noqa: E402
from app.infrastructure.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.messaging.sqs import SqsBus, set_bus  # noqa: E402
from app.saga import messages as m  # noqa: E402

SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def drain_queue(bus: SqsBus, logical: str) -> list[dict]:
    """Remove (e retorna) todas as mensagens visíveis da fila."""
    drained = []
    while True:
        msgs = bus.receive(logical, wait_seconds=0, max_messages=10)
        if not msgs:
            return drained
        for msg in msgs:
            bus.delete(logical, msg["ReceiptHandle"])
        drained.extend(msgs)


@pytest.fixture(scope="session")
def _aws_session():
    """moto é iniciado uma única vez por sessão (iniciar por teste custa ~2s)."""
    settings = get_settings()
    with mock_aws():
        bus = SqsBus(settings)
        for logical in (m.BILLING_COMMANDS, m.EXECUTION_COMMANDS, m.OS_REPLIES):
            bus.client.create_queue(QueueName=settings.queue_name(logical))
        yield bus


@pytest.fixture(autouse=True)
def sqs_bus(_aws_session):
    """SQS mockado (moto) com as filas da saga, esvaziadas a cada teste."""
    bus = _aws_session
    for logical in (m.BILLING_COMMANDS, m.EXECUTION_COMMANDS, m.OS_REPLIES):
        drain_queue(bus, logical)
    set_bus(bus)
    yield bus
    set_bus(None)


@pytest.fixture(scope="function")
def db_session():
    """Cria tabelas e fornece uma sessão de teste limpa por teste."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def session_factory(db_session):
    """Fábrica de sessões ligada ao mesmo banco em memória (workers/consumer)."""
    return TestingSessionLocal


@pytest.fixture(scope="function")
def client(db_session):
    """TestClient do FastAPI com override do DB."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client):
    """Registra um usuário e retorna headers com token JWT."""
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "admin_test",
            "email": "admin@test.com",
            "nome_completo": "Admin Teste",
            "password": "senha12345",
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "admin_test", "password": "senha12345"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def cliente_data():
    return {
        "nome": "João da Silva",
        "cpf_cnpj": "529.982.247-25",
        "email": "joao@email.com",
        "telefone": "11999999999",
        "endereco": "Rua Teste, 123",
    }


@pytest.fixture
def veiculo_data():
    return {"placa": "ABC1234", "marca": "Fiat", "modelo": "Uno", "ano": 2020}


@pytest.fixture
def servico_data():
    return {
        "nome": "Troca de Óleo",
        "descricao": "Troca completa de óleo do motor",
        "preco": 150.00,
        "tempo_estimado_minutos": 30,
    }


@pytest.fixture
def peca_data():
    return {
        "nome": "Filtro de Óleo",
        "descricao": "Filtro de óleo motor",
        "preco": 35.50,
    }
