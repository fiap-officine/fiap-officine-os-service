import pytest
from fastapi import HTTPException

from app.api.deps import get_current_cliente
from app.domain.entities.cliente import Cliente
from app.repositories.cliente_repository import ClienteRepository
from app.schemas.cliente import ClienteLoginRequest
from app.services.auth_service import (
    autenticar_cliente_por_cpf,
    decode_access_token,
)
from app.services.cliente_service import consultar_existencia_e_status_cliente


class TestAuthClienteUnit:
    def test_schema_cliente_login_cpf_valido(self):
        req = ClienteLoginRequest(cpf="529.982.247-25")
        assert req.cpf == "52998224725"

    def test_schema_cliente_login_cpf_invalido(self):
        with pytest.raises(ValueError, match="CPF inválido"):
            ClienteLoginRequest(cpf="111.111.111-11")

    def test_consultar_existencia_e_status_cpf_invalido(self, db_session):
        with pytest.raises(HTTPException) as exc:
            consultar_existencia_e_status_cliente(db_session, "1234")
        assert exc.value.status_code == 400
        assert "inválido" in exc.value.detail.lower()

    def test_consultar_existencia_e_status_cliente_inexistente(self, db_session):
        with pytest.raises(HTTPException) as exc:
            consultar_existencia_e_status_cliente(db_session, "52998224725")
        assert exc.value.status_code == 404
        assert "não encontrado" in exc.value.detail.lower()

    def test_consultar_existencia_e_status_cliente_inativo(self, db_session):
        repo = ClienteRepository(db_session)
        cliente = Cliente(
            nome="Cliente Inativo",
            cpf_cnpj="52998224725",
            email="inativo@teste.com",
            ativo=False,
        )
        repo.create(cliente)

        with pytest.raises(HTTPException) as exc:
            consultar_existencia_e_status_cliente(db_session, "52998224725")
        assert exc.value.status_code == 400
        assert "inativo" in exc.value.detail.lower()

    def test_consultar_existencia_e_status_cliente_ativo(self, db_session):
        repo = ClienteRepository(db_session)
        cliente = Cliente(
            nome="Cliente Ativo",
            cpf_cnpj="52998224725",
            email="ativo@teste.com",
            ativo=True,
        )
        repo.create(cliente)

        res = consultar_existencia_e_status_cliente(db_session, "52998224725")
        assert res.id == cliente.id
        assert res.ativo is True

    def test_autenticar_cliente_por_cpf_sucesso(self, db_session):
        repo = ClienteRepository(db_session)
        cliente = Cliente(
            nome="Maria Souza",
            cpf_cnpj="52998224725",
            email="maria@teste.com",
            ativo=True,
        )
        repo.create(cliente)

        token = autenticar_cliente_por_cpf(db_session, "529.982.247-25")
        assert token.access_token is not None
        assert token.token_type == "bearer"

        token_data = decode_access_token(token.access_token)
        assert token_data.cpf == "52998224725"
        assert token_data.role == "cliente"
        assert token_data.cliente_id == cliente.id

    def test_get_current_cliente_dependency(self, db_session):
        repo = ClienteRepository(db_session)
        cliente = Cliente(
            nome="Carlos Pereira",
            cpf_cnpj="52998224725",
            email="carlos@teste.com",
            ativo=True,
        )
        repo.create(cliente)

        token = autenticar_cliente_por_cpf(db_session, "52998224725")
        user = get_current_cliente(token=token.access_token, db=db_session)
        assert user.id == cliente.id

    def test_get_current_cliente_desativado(self, db_session):
        repo = ClienteRepository(db_session)
        cliente = Cliente(
            nome="Carlos Pereira",
            cpf_cnpj="52998224725",
            email="carlos@teste.com",
            ativo=True,
        )
        repo.create(cliente)

        token = autenticar_cliente_por_cpf(db_session, "52998224725")
        cliente.ativo = False
        repo.update(cliente)

        with pytest.raises(HTTPException) as exc:
            get_current_cliente(token=token.access_token, db=db_session)
        assert exc.value.status_code == 401
        assert "inativo" in exc.value.detail.lower()

    def test_autenticar_cliente_via_lambda_sucesso(self, db_session, monkeypatch):
        import urllib.request
        from unittest.mock import MagicMock

        from app.config import get_settings

        settings = get_settings()
        monkeypatch.setattr(
            settings, "AUTH_LAMBDA_URL", "https://api.gateway/auth/login"
        )

        mock_resp = MagicMock()
        mock_resp.read.return_value = (
            b'{"access_token": "token-da-lambda-xyz", "token_type": "bearer"}'
        )
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None

        monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout: mock_resp)

        token = autenticar_cliente_por_cpf(db_session, "529.982.247-25")
        assert token.access_token == "token-da-lambda-xyz"
        assert token.token_type == "bearer"

    def test_autenticar_cliente_via_lambda_erro_http(self, db_session, monkeypatch):
        import io
        import urllib.request
        from urllib.error import HTTPError

        from app.config import get_settings

        settings = get_settings()
        monkeypatch.setattr(
            settings, "AUTH_LAMBDA_URL", "https://api.gateway/auth/login"
        )

        err_fp = io.BytesIO(b'{"detail": "Cliente inativo no sistema"}')
        http_err = HTTPError("url", 400, "Bad Request", {}, err_fp)

        def mock_urlopen(req, timeout):
            raise http_err

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        with pytest.raises(HTTPException) as exc:
            autenticar_cliente_por_cpf(db_session, "529.982.247-25")
        assert exc.value.status_code == 400
        assert "inativo" in exc.value.detail.lower()
