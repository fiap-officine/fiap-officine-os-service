import enum


class StatusOrdemServico(str, enum.Enum):
    RECEBIDA = "recebida"
    AGUARDANDO_ORCAMENTO = "aguardando_orcamento"
    AGUARDANDO_APROVACAO = "aguardando_aprovacao"
    AGUARDANDO_PAGAMENTO = "aguardando_pagamento"
    AGUARDANDO_EXECUCAO = "aguardando_execucao"
    EM_DIAGNOSTICO = "em_diagnostico"
    EM_EXECUCAO = "em_execucao"
    FINALIZADA = "finalizada"
    ENTREGUE = "entregue"
    EM_COMPENSACAO = "em_compensacao"
    CANCELADA = "cancelada"


S = StatusOrdemServico

# A partir de EM_EXECUCAO (pivô da saga) não há mais compensação: só recuperação
# para frente. Antes dele, qualquer estado pode entrar em compensação.
TRANSICOES_VALIDAS: dict[StatusOrdemServico, list[StatusOrdemServico]] = {
    S.RECEBIDA: [S.AGUARDANDO_ORCAMENTO, S.EM_COMPENSACAO, S.CANCELADA],
    S.AGUARDANDO_ORCAMENTO: [S.AGUARDANDO_APROVACAO, S.EM_COMPENSACAO],
    S.AGUARDANDO_APROVACAO: [S.AGUARDANDO_PAGAMENTO, S.EM_COMPENSACAO],
    S.AGUARDANDO_PAGAMENTO: [S.AGUARDANDO_EXECUCAO, S.EM_COMPENSACAO],
    S.AGUARDANDO_EXECUCAO: [S.EM_DIAGNOSTICO, S.EM_COMPENSACAO],
    S.EM_DIAGNOSTICO: [S.EM_EXECUCAO, S.EM_COMPENSACAO],
    S.EM_EXECUCAO: [S.FINALIZADA],
    S.FINALIZADA: [S.ENTREGUE],
    S.ENTREGUE: [],
    S.EM_COMPENSACAO: [S.CANCELADA],
    S.CANCELADA: [],
}

# Ordem dos estados de progresso informados pelo Execution Service.
# Usada para avançar com tolerância a eventos fora de ordem (SQS standard).
PROGRESSO_EXECUCAO: list[StatusOrdemServico] = [
    S.AGUARDANDO_EXECUCAO,
    S.EM_DIAGNOSTICO,
    S.EM_EXECUCAO,
    S.FINALIZADA,
]

STATUS_FINAIS = {S.FINALIZADA, S.ENTREGUE, S.CANCELADA}
STATUS_EM_ANDAMENTO = [s for s in StatusOrdemServico if s not in STATUS_FINAIS]


class SagaState(str, enum.Enum):
    STARTED = "STARTED"
    BUDGET_PENDING = "BUDGET_PENDING"
    APPROVAL_PENDING = "APPROVAL_PENDING"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    SCHEDULING = "SCHEDULING"
    IN_EXECUTION = "IN_EXECUTION"
    COMPLETED = "COMPLETED"
    COMPENSATING = "COMPENSATING"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


SAGA_FORWARD_WAITING = {
    SagaState.BUDGET_PENDING,
    SagaState.APPROVAL_PENDING,
    SagaState.PAYMENT_PENDING,
    SagaState.SCHEDULING,
}
SAGA_TERMINAL = {SagaState.COMPLETED, SagaState.CANCELLED, SagaState.FAILED}
