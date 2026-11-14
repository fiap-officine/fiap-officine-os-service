"""Contratos de mensagens da saga da OS (ver docs/contracts/)."""

# Filas (nomes lógicos)
BILLING_COMMANDS = "billing-commands"
EXECUTION_COMMANDS = "execution-commands"
OS_REPLIES = "os-saga-replies"

# ── Comandos: OS -> Billing ──────────────────────
GERAR_ORCAMENTO = "GerarOrcamento"
SOLICITAR_PAGAMENTO = "SolicitarPagamento"
ESTORNAR_PAGAMENTO = "EstornarPagamento"
CANCELAR_ORCAMENTO = "CancelarOrcamento"

# ── Comandos: OS -> Execution ────────────────────
RESERVAR_E_ENFILEIRAR = "ReservarEEnfileirar"
LIBERAR_RESERVA = "LiberarReserva"

# ── Respostas / eventos: Billing -> OS ───────────
ORCAMENTO_GERADO = "OrcamentoGerado"
ORCAMENTO_FALHOU = "OrcamentoFalhou"
ORCAMENTO_APROVADO = "OrcamentoAprovado"
ORCAMENTO_RECUSADO = "OrcamentoRecusado"
ORCAMENTO_CANCELADO = "OrcamentoCancelado"
PAGAMENTO_SOLICITADO = "PagamentoSolicitado"
PAGAMENTO_CONFIRMADO = "PagamentoConfirmado"
PAGAMENTO_RECUSADO = "PagamentoRecusado"
PAGAMENTO_ESTORNADO = "PagamentoEstornado"

# ── Respostas / eventos: Execution -> OS ─────────
EXECUCAO_AGENDADA = "ExecucaoAgendada"
RESERVA_FALHOU = "ReservaFalhou"
RESERVA_LIBERADA = "ReservaLiberada"
DIAGNOSTICO_INICIADO = "DiagnosticoIniciado"
REPARO_INICIADO = "ReparoIniciado"
EXECUCAO_FINALIZADA = "ExecucaoFinalizada"

# Compensação -> (fila de destino, resposta que a confirma)
COMPENSATIONS: dict[str, tuple[str, str]] = {
    LIBERAR_RESERVA: (EXECUTION_COMMANDS, RESERVA_LIBERADA),
    ESTORNAR_PAGAMENTO: (BILLING_COMMANDS, PAGAMENTO_ESTORNADO),
    CANCELAR_ORCAMENTO: (BILLING_COMMANDS, ORCAMENTO_CANCELADO),
}
COMPENSATION_BY_REPLY: dict[str, str] = {
    reply: command for command, (_, reply) in COMPENSATIONS.items()
}
