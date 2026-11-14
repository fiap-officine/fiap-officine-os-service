from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.domain.entities.cliente import Cliente
from app.domain.entities.usuario import Usuario
from app.infrastructure.database import get_db
from app.repositories.cliente_repository import ClienteRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.services.auth_service import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    """Dependency que valida o token JWT e retorna o usuário autenticado."""
    token_data = decode_access_token(token)
    repo = UsuarioRepository(db)
    user = repo.get_by_username(token_data.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Usuário inativo")
    return user


def get_admin_user(current_user: Usuario = Depends(get_current_user)) -> Usuario:
    """Dependency que exige permissão de administrador."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissão de administrador necessária",
        )
    return current_user


def get_current_cliente(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Cliente:
    """Dependency que valida o token JWT do cliente via CPF e retorna o cliente autenticado."""
    token_data = decode_access_token(token)
    cpf = token_data.cpf or (
        token_data.username if token_data.role == "cliente" else None
    )
    if not cpf:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido para autenticação de cliente",
            headers={"WWW-Authenticate": "Bearer"},
        )

    repo = ClienteRepository(db)
    cliente = repo.get_by_cpf_cnpj(cpf)
    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cliente não encontrado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not cliente.ativo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cliente inativo no sistema",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return cliente


def get_current_actor(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> tuple[Usuario | None, Cliente | None]:
    """Valida o token JWT e retorna (Usuario, None) se for admin ou (None, Cliente) se for cliente."""
    token_data = decode_access_token(token)
    if token_data.role == "cliente":
        repo = ClienteRepository(db)
        cliente = repo.get_by_cpf_cnpj(token_data.cpf or token_data.username)
        if not cliente:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Cliente não encontrado",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not cliente.ativo:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Cliente inativo no sistema",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return (None, cliente)
    else:
        repo = UsuarioRepository(db)
        user = repo.get_by_username(token_data.username)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuário não encontrado",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise HTTPException(status_code=400, detail="Usuário inativo")
        return (user, None)


oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/cliente", auto_error=False
)


def get_optional_cliente(
    token: str | None = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db),
) -> Cliente | None:
    """Dependency opcional que retorna o cliente se um token JWT válido de cliente for fornecido."""
    if not token:
        return None
    try:
        token_data = decode_access_token(token)
        cpf = token_data.cpf or (
            token_data.username if token_data.role == "cliente" else None
        )
        if not cpf:
            return None
        repo = ClienteRepository(db)
        cliente = repo.get_by_cpf_cnpj(cpf)
        if cliente and cliente.ativo:
            return cliente
    except HTTPException:
        return None
    return None
