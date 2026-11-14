# language: pt
Funcionalidade: Saga da Ordem de Serviço
  Como oficina
  Quero que a OS passe por orçamento, aprovação, pagamento e execução
  Para que falhas em qualquer etapa sejam compensadas com segurança

  Contexto:
    Dado um cliente ativo com um veículo cadastrado
    E uma peça "Pastilha de freio" com 5 unidades em estoque

  Cenário: Fluxo completo com sucesso
    Quando o cliente abre uma OS com 2 unidades de "Pastilha de freio"
    Então o Billing deve receber o comando "GerarOrcamento"
    E a OS deve ficar "aguardando_aprovacao"
    Quando o cliente aprova o orçamento
    Então o Billing deve receber o comando "SolicitarPagamento"
    E a OS deve ficar "aguardando_pagamento"
    Quando o Mercado Pago confirma o pagamento
    Então o Execution deve receber o comando "ReservarEEnfileirar"
    E a OS deve ficar "aguardando_execucao"
    E o estoque de "Pastilha de freio" deve ser 3
    Quando o mecânico finaliza a execução
    Então a OS deve ficar "finalizada"
    E a saga deve estar "COMPLETED"
    E o histórico da OS deve conter "em_diagnostico" e "em_execucao"

  Cenário: Cliente recusa o orçamento
    Quando o cliente abre uma OS com 1 unidade de "Pastilha de freio"
    E o cliente recusa o orçamento
    Então o Billing deve receber o comando "CancelarOrcamento"
    E a OS deve ficar "cancelada"
    E a saga deve estar "CANCELLED"

  Cenário: Estoque insuficiente após pagamento gera estorno
    Quando o cliente abre uma OS com 10 unidades de "Pastilha de freio"
    E o cliente aprova o orçamento
    E o Mercado Pago confirma o pagamento
    Então o Execution deve responder "ReservaFalhou"
    E o Billing deve receber o comando "EstornarPagamento"
    E o Billing deve receber o comando "CancelarOrcamento"
    E a OS deve ficar "cancelada"
    E a saga deve estar "CANCELLED"
    E o estoque de "Pastilha de freio" deve ser 5

  Cenário: Pagamento não confirmado dentro do prazo
    Quando o cliente abre uma OS com 1 unidade de "Pastilha de freio"
    E o cliente aprova o orçamento
    E o prazo de pagamento expira
    Então o Billing deve receber o comando "CancelarOrcamento"
    E o Billing não deve receber o comando "EstornarPagamento"
    E a OS deve ficar "cancelada"

  Cenário: Cliente cancela com a OS já na fila de execução
    Quando o cliente abre uma OS com 2 unidades de "Pastilha de freio"
    E o cliente aprova o orçamento
    E o Mercado Pago confirma o pagamento
    E o cliente cancela a OS
    Então o Execution deve receber o comando "LiberarReserva"
    E o Billing deve receber o comando "EstornarPagamento"
    E o Billing deve receber o comando "CancelarOrcamento"
    E a OS deve ficar "cancelada"
    E o estoque de "Pastilha de freio" deve ser 5

  Cenário: Mensagem duplicada não é processada duas vezes
    Quando o cliente abre uma OS com 1 unidade de "Pastilha de freio"
    E o Billing entrega a resposta "OrcamentoGerado" duas vezes
    Então a OS deve ficar "aguardando_aprovacao"
    E o histórico da OS deve ter 1 registro "aguardando_aprovacao"
