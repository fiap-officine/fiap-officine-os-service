from app.domain.enums import (
    PROGRESSO_EXECUCAO,
    STATUS_EM_ANDAMENTO,
    TRANSICOES_VALIDAS,
    SagaState,
)
from app.domain.enums import StatusOrdemServico as S


class TestStatusOrdemServico:
    def test_valores(self):
        assert S.RECEBIDA.value == "recebida"
        assert S.AGUARDANDO_ORCAMENTO.value == "aguardando_orcamento"
        assert S.AGUARDANDO_PAGAMENTO.value == "aguardando_pagamento"
        assert S.AGUARDANDO_EXECUCAO.value == "aguardando_execucao"
        assert S.EM_COMPENSACAO.value == "em_compensacao"
        assert S.CANCELADA.value == "cancelada"

    def test_caminho_feliz_e_valido(self):
        caminho = [
            S.RECEBIDA,
            S.AGUARDANDO_ORCAMENTO,
            S.AGUARDANDO_APROVACAO,
            S.AGUARDANDO_PAGAMENTO,
            S.AGUARDANDO_EXECUCAO,
            S.EM_DIAGNOSTICO,
            S.EM_EXECUCAO,
            S.FINALIZADA,
            S.ENTREGUE,
        ]
        for atual, proximo in zip(caminho, caminho[1:], strict=False):
            assert proximo in TRANSICOES_VALIDAS[atual], (atual, proximo)

    def test_compensacao_permitida_antes_do_pivo(self):
        for status in (
            S.RECEBIDA,
            S.AGUARDANDO_ORCAMENTO,
            S.AGUARDANDO_APROVACAO,
            S.AGUARDANDO_PAGAMENTO,
            S.AGUARDANDO_EXECUCAO,
            S.EM_DIAGNOSTICO,
        ):
            assert S.EM_COMPENSACAO in TRANSICOES_VALIDAS[status]

    def test_sem_compensacao_apos_pivo(self):
        for status in (S.EM_EXECUCAO, S.FINALIZADA, S.ENTREGUE):
            assert S.EM_COMPENSACAO not in TRANSICOES_VALIDAS[status]

    def test_compensacao_termina_em_cancelada(self):
        assert TRANSICOES_VALIDAS[S.EM_COMPENSACAO] == [S.CANCELADA]

    def test_estados_finais(self):
        assert TRANSICOES_VALIDAS[S.ENTREGUE] == []
        assert TRANSICOES_VALIDAS[S.CANCELADA] == []
        assert S.CANCELADA not in STATUS_EM_ANDAMENTO
        assert S.EM_COMPENSACAO in STATUS_EM_ANDAMENTO

    def test_progresso_execucao_ordenado(self):
        assert PROGRESSO_EXECUCAO[0] == S.AGUARDANDO_EXECUCAO
        assert PROGRESSO_EXECUCAO[-1] == S.FINALIZADA


class TestSagaState:
    def test_estados(self):
        assert SagaState("COMPENSATING") is SagaState.COMPENSATING
        assert len(SagaState) == 10
