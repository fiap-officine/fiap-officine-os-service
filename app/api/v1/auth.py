from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_cliente, get_current_user
from app.domain.entities.cliente import Cliente
from app.domain.entities.usuario import Usuario
from app.infrastructure.database import get_db
from app.schemas.cliente import (
    ClienteLoginRequest,
    ClienteResponse,
    ClienteStatusResponse,
)
from app.schemas.token import Token
from app.schemas.usuario import UsuarioCreate, UsuarioResponse
from app.services import auth_service, cliente_service

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post("/register", response_model=UsuarioResponse, status_code=201)
def registrar(dados: UsuarioCreate, db: Session = Depends(get_db)):
    """Registra um novo usuário administrativo."""
    return auth_service.registrar_usuario(db, dados)


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    """Autentica o usuário e retorna um token JWT."""
    return auth_service.autenticar_usuario(db, form_data.username, form_data.password)


@router.get("/me", response_model=UsuarioResponse)
def perfil(current_user: Usuario = Depends(get_current_user)):
    """Retorna informações do usuário autenticado."""
    return current_user


@router.post("/cliente", response_model=Token)
def login_cliente(dados: ClienteLoginRequest, db: Session = Depends(get_db)):
    """Autentica o cliente via CPF, validando existência e status ativo, e retorna um token JWT."""
    return auth_service.autenticar_cliente_por_cpf(db, dados.cpf)


@router.get("/cliente/status/{cpf}", response_model=ClienteStatusResponse)
def consultar_status_cliente(cpf: str, db: Session = Depends(get_db)):
    """Consulta a existência e o status do cliente na base de dados pelo CPF."""
    cliente = cliente_service.consultar_existencia_e_status_cliente(db, cpf)
    return ClienteStatusResponse(
        id=cliente.id,
        nome=cliente.nome,
        cpf_cnpj=cliente.cpf_cnpj,
        ativo=cliente.ativo,
        status_descricao="Ativo" if cliente.ativo else "Inativo",
    )


@router.get("/cliente/me", response_model=ClienteResponse)
def perfil_cliente(current_cliente: Cliente = Depends(get_current_cliente)):
    """Retorna informações do cliente autenticado via token JWT (CPF)."""
    return current_cliente
