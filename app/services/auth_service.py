from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.entities.usuario import Usuario
from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.token import Token, TokenData
from app.schemas.usuario import UsuarioCreate

settings = get_settings()
pwd_context = CryptContext(
    schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=settings.BCRYPT_ROUNDS
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    return jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def decode_access_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        sub: str | None = payload.get("sub")
        if sub is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido",
                headers={"WWW-Authenticate": "Bearer"},
            )
        role: str | None = payload.get("role", "admin")
        cliente_id: int | None = payload.get("cliente_id")
        return TokenData(
            username=sub,
            cpf=sub if role == "cliente" else None,
            role=role,
            cliente_id=cliente_id,
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def registrar_usuario(db: Session, dados: UsuarioCreate) -> Usuario:
    repo = UsuarioRepository(db)

    if repo.get_by_username(dados.username):
        raise HTTPException(status_code=400, detail="Username já cadastrado")
    if repo.get_by_email(dados.email):
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    usuario = Usuario(
        username=dados.username,
        email=dados.email,
        nome_completo=dados.nome_completo,
        hashed_password=hash_password(dados.password),
        is_active=True,
        is_admin=True,
    )
    return repo.create(usuario)


def autenticar_usuario(db: Session, username: str, password: str) -> Token:
    repo = UsuarioRepository(db)
    usuario = repo.get_by_username(username)

    if not usuario or not verify_password(password, usuario.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not usuario.is_active:
        raise HTTPException(status_code=400, detail="Usuário inativo")

    access_token = create_access_token(data={"sub": usuario.username, "role": "admin"})
    return Token(access_token=access_token)


def autenticar_cliente_por_cpf(db: Session, cpf: str) -> Token:
    """Autentica cliente via CPF, validando existência e status ativo no banco de dados.

    Se AUTH_LAMBDA_URL estiver configurada, delega a autenticação para a Function Serverless (AWS Lambda).
    Caso contrário, executa a validação e emissão localmente.
    """
    if settings.AUTH_LAMBDA_URL:
        import json
        import urllib.request
        from urllib.error import HTTPError

        from app.domain.validators import formatar_cpf_cnpj

        cpf_limpo = formatar_cpf_cnpj(cpf)
        req_data = json.dumps({"cpf": cpf_limpo}).encode("utf-8")
        req = urllib.request.Request(
            settings.AUTH_LAMBDA_URL,
            data=req_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp_json = json.loads(resp.read().decode("utf-8"))
                if "body" in resp_json and isinstance(resp_json["body"], str):
                    body = json.loads(resp_json["body"])
                else:
                    body = resp_json
                return Token(
                    access_token=body["access_token"],
                    token_type=body.get("token_type", "bearer"),
                )
        except HTTPError as e:
            try:
                err_body = json.loads(e.read().decode("utf-8"))
                detail = err_body.get(
                    "detail", err_body.get("error", "Erro de autenticação na Lambda")
                )
            except Exception:
                detail = "Erro de autenticação na Function Serverless"
            raise HTTPException(status_code=e.code, detail=detail) from e
        except Exception:
            # Fallback para processamento local caso a Lambda não responda
            pass

    from app.services.cliente_service import consultar_existencia_e_status_cliente

    cliente = consultar_existencia_e_status_cliente(db, cpf)

    access_token = create_access_token(
        data={
            "sub": cliente.cpf_cnpj,
            "role": "cliente",
            "cliente_id": cliente.id,
            "nome": cliente.nome,
        }
    )
    return Token(access_token=access_token)
