import pytest
from pydantic import ValidationError

from app.schemas.cliente import ClienteCreate, ClienteUpdate
from app.schemas.peca import PecaCreate, PecaUpdate
from app.schemas.servico import ServicoCreate
from app.schemas.usuario import UsuarioCreate
from app.schemas.veiculo import VeiculoCreate


class TestClienteSchema:
    def test_cliente_create_valido(self):
        cliente = ClienteCreate(
            nome="João da Silva",
            cpf_cnpj="529.982.247-25",
            email="joao@email.com",
        )
        assert cliente.cpf_cnpj == "52998224725"

    def test_cliente_cpf_invalido(self):
        with pytest.raises(ValidationError) as exc_info:
            ClienteCreate(nome="João", cpf_cnpj="123.456.789-00")
        assert "CPF ou CNPJ inválido" in str(exc_info.value)

    def test_cliente_nome_curto(self):
        with pytest.raises(ValidationError) as exc_info:
            ClienteCreate(nome="J", cpf_cnpj="52998224725")
        assert "mínimo 2 caracteres" in str(exc_info.value)

    def test_cliente_update_parcial(self):
        update = ClienteUpdate(nome="Novo Nome")
        assert update.nome == "Novo Nome"
        assert update.email is None


class TestVeiculoSchema:
    def test_veiculo_placa_valida(self):
        v = VeiculoCreate(
            cliente_id=1, placa="ABC-1234", marca="Fiat", modelo="Uno", ano=2020
        )
        assert v.placa == "ABC1234"

    def test_veiculo_placa_mercosul(self):
        v = VeiculoCreate(
            cliente_id=1, placa="ABC1D23", marca="VW", modelo="Gol", ano=2022
        )
        assert v.placa == "ABC1D23"

    def test_veiculo_placa_invalida(self):
        with pytest.raises(ValidationError):
            VeiculoCreate(
                cliente_id=1, placa="INVALID", marca="Fiat", modelo="Uno", ano=2020
            )

    def test_veiculo_ano_invalido(self):
        with pytest.raises(ValidationError):
            VeiculoCreate(
                cliente_id=1, placa="ABC1234", marca="Fiat", modelo="Uno", ano=1800
            )


class TestServicoSchema:
    def test_servico_valido(self):
        s = ServicoCreate(nome="Troca de Óleo", preco=150.00, tempo_estimado_minutos=30)
        assert s.preco == 150.00

    def test_servico_preco_negativo(self):
        with pytest.raises(ValidationError):
            ServicoCreate(nome="Test", preco=-10, tempo_estimado_minutos=30)

    def test_servico_tempo_negativo(self):
        with pytest.raises(ValidationError):
            ServicoCreate(nome="Test", preco=100, tempo_estimado_minutos=-5)


class TestPecaSchema:
    def test_peca_valida(self):
        p = PecaCreate(nome="Filtro", preco=35.50)
        assert p.nome == "Filtro"

    def test_peca_preco_negativo(self):
        with pytest.raises(ValidationError):
            PecaCreate(nome="Filtro", preco=-1)


class TestUsuarioSchema:
    def test_usuario_valido(self):
        u = UsuarioCreate(
            username="admin",
            email="admin@test.com",
            nome_completo="Admin",
            password="senha12345",
        )
        assert u.username == "admin"

    def test_usuario_senha_curta(self):
        with pytest.raises(ValidationError):
            UsuarioCreate(
                username="admin",
                email="admin@test.com",
                nome_completo="Admin",
                password="123",
            )

    def test_usuario_username_curto(self):
        with pytest.raises(ValidationError):
            UsuarioCreate(
                username="ab",
                email="a@b.com",
                nome_completo="Admin",
                password="senha12345",
            )


class TestPecaSchemaCompleto:
    def test_peca_com_todos_campos(self):
        from decimal import Decimal

        p = PecaCreate(
            codigo="FLT-001",
            nome="Filtro de Óleo",
            descricao="Filtro de óleo sintético",
            unidade_medida="unidade",
            preco=Decimal("35.50"),
        )
        assert p.codigo == "FLT-001"
        assert p.unidade_medida == "unidade"

    def test_peca_preco_zero_invalido(self):
        with pytest.raises(ValidationError):
            PecaCreate(nome="X", preco=0)

    def test_peca_update_preco_invalido(self):
        from decimal import Decimal

        with pytest.raises(ValidationError):
            PecaUpdate(preco=Decimal("-5.00"))

    def test_peca_update_parcial(self):
        dump = PecaUpdate(nome="Novo").model_dump(exclude_unset=True)
        assert dump == {"nome": "Novo"}


class TestClienteSchemaComValidacoes:
    def test_email_invalido(self):
        with pytest.raises(ValidationError):
            ClienteCreate(nome="João", cpf_cnpj="52998224725", email="nao-é-email")

    def test_email_sem_dominio(self):
        with pytest.raises(ValidationError):
            ClienteCreate(nome="João", cpf_cnpj="52998224725", email="joao@")

    def test_telefone_muito_curto(self):
        with pytest.raises(ValidationError):
            ClienteCreate(nome="João", cpf_cnpj="52998224725", telefone="123")

    def test_telefone_normalizado(self):
        c = ClienteCreate(
            nome="João", cpf_cnpj="52998224725", telefone="(11) 98765-4321"
        )
        assert c.telefone == "11987654321"

    def test_email_normalizado_lower(self):
        c = ClienteCreate(nome="João", cpf_cnpj="52998224725", email="JOAO@EMAIL.COM")
        assert c.email == "joao@email.com"

    def test_cliente_update_telefone_none(self):
        u = ClienteUpdate(telefone=None)
        assert u.telefone is None
