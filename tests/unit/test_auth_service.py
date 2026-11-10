from app.services.auth_service import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_e_verify(self):
        senha = "minha_senha_123"
        hashed = hash_password(senha)
        assert hashed != senha
        assert verify_password(senha, hashed) is True

    def test_senha_incorreta(self):
        hashed = hash_password("senha_correta")
        assert verify_password("senha_errada", hashed) is False


class TestJWTTokens:
    def test_criar_e_decodificar_token(self):
        token = create_access_token(data={"sub": "admin_test"})
        assert token is not None
        token_data = decode_access_token(token)
        assert token_data.username == "admin_test"

    def test_token_invalido(self):
        import pytest
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token("token_invalido")
        assert exc_info.value.status_code == 401
