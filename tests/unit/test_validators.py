from app.domain.validators import (
    formatar_cpf_cnpj,
    formatar_placa,
    validar_cnpj,
    validar_cpf,
    validar_cpf_cnpj,
    validar_placa,
)


class TestValidarCPF:
    def test_cpf_valido(self):
        assert validar_cpf("529.982.247-25") is True
        assert validar_cpf("52998224725") is True

    def test_cpf_invalido(self):
        assert validar_cpf("000.000.000-00") is False
        assert validar_cpf("111.111.111-11") is False
        assert validar_cpf("123.456.789-00") is False
        assert validar_cpf("123") is False
        assert validar_cpf("") is False

    def test_cpf_com_formatacao(self):
        assert validar_cpf("529.982.247-25") is True


class TestValidarCNPJ:
    def test_cnpj_valido(self):
        assert validar_cnpj("11.222.333/0001-81") is True
        assert validar_cnpj("11222333000181") is True

    def test_cnpj_invalido(self):
        assert validar_cnpj("00.000.000/0000-00") is False
        assert validar_cnpj("11.111.111/1111-11") is False
        assert validar_cnpj("123") is False
        assert validar_cnpj("") is False


class TestValidarCPFCNPJ:
    def test_cpf_valido(self):
        assert validar_cpf_cnpj("52998224725") is True

    def test_cnpj_valido(self):
        assert validar_cpf_cnpj("11222333000181") is True

    def test_documento_invalido(self):
        assert validar_cpf_cnpj("123") is False
        assert validar_cpf_cnpj("") is False


class TestValidarPlaca:
    def test_placa_formato_antigo(self):
        assert validar_placa("ABC-1234") is True
        assert validar_placa("ABC1234") is True
        assert validar_placa("abc1234") is True

    def test_placa_formato_mercosul(self):
        assert validar_placa("ABC1D23") is True
        assert validar_placa("abc1d23") is True

    def test_placa_invalida(self):
        assert validar_placa("AB12345") is False
        assert validar_placa("ABCD1234") is False
        assert validar_placa("123ABCD") is False
        assert validar_placa("") is False


class TestFormatar:
    def test_formatar_cpf_cnpj(self):
        assert formatar_cpf_cnpj("529.982.247-25") == "52998224725"
        assert formatar_cpf_cnpj("11.222.333/0001-81") == "11222333000181"

    def test_formatar_placa(self):
        assert formatar_placa("abc-1234") == "ABC1234"
        assert formatar_placa("ABC1D23") == "ABC1D23"
