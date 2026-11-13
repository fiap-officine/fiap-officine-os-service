import contextvars
import json
import logging
from unittest.mock import MagicMock, patch

from app.core.logging import JSONLogFormatter, correlation_id_ctx
from app.infrastructure.database import get_db
from app.main import app


class TestJSONLogFormatter:
    def test_json_log_formatter_outputs_valid_json(self):
        formatter = JSONLogFormatter(service_name="test-service", environment="test")
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Mensagem de teste para New Relic",
            args=(),
            exc_info=None,
        )
        record.os_id = 42

        token = correlation_id_ctx.set("corr-test-12345")
        try:
            formatted = formatter.format(record)
            data = json.loads(formatted)

            assert data["message"] == "Mensagem de teste para New Relic"
            assert data["level"] == "INFO"
            assert data["service"] == "test-service"
            assert data["environment"] == "test"
            assert data["correlation_id"] == "corr-test-12345"
            assert data["os_id"] == 42
            assert "timestamp" in data
        finally:
            correlation_id_ctx.reset(token)


class TestObservabilityMiddleware:
    def test_middleware_injects_correlation_headers(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "X-Correlation-ID" in response.headers
        assert "X-Request-ID" in response.headers
        assert "X-Response-Time-Ms" in response.headers

    def test_middleware_propagates_custom_correlation_id(self, client):
        custom_id = "custom-uuid-abc-123"
        response = client.get("/", headers={"X-Correlation-ID": custom_id})
        assert response.status_code == 200
        assert response.headers["X-Correlation-ID"] == custom_id


class TestHealthEndpoint:
    def test_health_check_operational(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "uptime_seconds" in data
        assert "services" in data
        assert "database" in data["services"]
        assert data["services"]["database"]["status"] == "up"
        assert data["services"]["messaging"]["status"] == "up"
        assert data["services"]["outbox"]["pending"] == 0

    def test_health_messaging_down_nao_derruba(self, client):
        with patch("app.api.v1.health.get_bus") as get_bus:
            get_bus.return_value.ping.side_effect = Exception("SQS indisponível")
            response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["services"]["messaging"]["status"] == "down"

    def test_health_api_prefixed(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_check_database_failure(self, client):

        def failing_db():
            mock_db = MagicMock()
            mock_db.execute.side_effect = Exception("Conexão com PostgreSQL recusada")
            yield mock_db

        app.dependency_overrides[get_db] = failing_db
        try:
            response = client.get("/health")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["services"]["database"]["status"] == "down"
        finally:
            app.dependency_overrides.pop(get_db, None)


class TestContextRecordFactory:
    """saga_id/os_id/correlation_id viram atributos do LogRecord (New Relic context_data)."""

    @staticmethod
    def _novo_record():
        from app.core.logging import _context_record_factory

        return _context_record_factory("t", logging.INFO, "t.py", 1, "msg", (), None)

    def test_copia_o_contexto_para_o_record(self):
        from app.core.logging import correlation_id_ctx, os_id_ctx, saga_id_ctx

        def run():
            saga_id_ctx.set("saga-1")
            os_id_ctx.set(7)
            correlation_id_ctx.set("corr-1")
            return self._novo_record()

        record = contextvars.Context().run(run)
        assert (record.saga_id, record.os_id, record.correlation_id) == (
            "saga-1",
            7,
            "corr-1",
        )

    def test_sem_contexto_nao_cria_atributos(self):
        record = contextvars.Context().run(self._novo_record)
        assert not hasattr(record, "saga_id")
        assert not hasattr(record, "os_id")

    def test_setup_instala_a_factory(self):
        from app.core.logging import _context_record_factory, setup_json_logging

        anterior = logging.getLogRecordFactory()
        try:
            setup_json_logging(service_name="teste", environment="test")
            assert logging.getLogRecordFactory() is _context_record_factory
        finally:
            logging.setLogRecordFactory(anterior)
