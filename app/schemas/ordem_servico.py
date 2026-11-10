from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.domain.enums import StatusOrdemServico


class ItemServicoCreate(BaseModel):
    servico_id: int
    quantidade: int = Field(1, ge=1)


class ItemServicoResponse(BaseModel):
    id: int
    servico_id: int
    quantidade: int
    valor_unitario: Decimal
    valor_total: Decimal

    model_config = {"from_attributes": True}


class ItemPecaCreate(BaseModel):
    peca_id: int
    quantidade: int = Field(1, ge=1)


class ItemPecaResponse(BaseModel):
    id: int
    peca_id: int
    quantidade: int
    valor_unitario: Decimal
    valor_total: Decimal

    model_config = {"from_attributes": True}


class HistoricoResponse(BaseModel):
    id: int
    status_anterior: str | None
    status_novo: str
    observacao: str | None
    data_alteracao: datetime

    model_config = {"from_attributes": True}


class OrdemServicoCreate(BaseModel):
    cliente_id: int
    veiculo_id: int
    observacoes: str | None = None
    itens_servico: list[ItemServicoCreate] | None = None
    itens_peca: list[ItemPecaCreate] | None = None


class OrdemServicoUpdate(BaseModel):
    observacoes: str | None = None


class CancelarOrdemRequest(BaseModel):
    motivo: str | None = None


class SagaStepResponse(BaseModel):
    id: int
    step: str
    direction: str
    message_type: str | None
    message_id: str | None
    detail: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SagaResponse(BaseModel):
    id: str
    os_id: int
    state: str
    deadline_at: datetime | None
    orcamento_id: int | None
    pagamento_id: int | None
    checkout_url: str | None
    payment_confirmed: bool
    reserved: bool
    pending_compensations: list[str]
    compensation_attempts: int
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime
    steps: list[SagaStepResponse]

    model_config = {"from_attributes": True}


class OrdemServicoResponse(BaseModel):
    id: int
    cliente_id: int
    veiculo_id: int
    status: StatusOrdemServico
    observacoes: str | None
    valor_total: Decimal
    created_at: datetime
    updated_at: datetime
    data_finalizacao: datetime | None
    data_entrega: datetime | None
    itens_servico: list[ItemServicoResponse]
    itens_peca: list[ItemPecaResponse]
    historico: list[HistoricoResponse]

    model_config = {"from_attributes": True}


class OrdemServicoResumo(BaseModel):
    id: int
    cliente_id: int
    veiculo_id: int
    status: StatusOrdemServico
    valor_total: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


class TempoMedioResponse(BaseModel):
    tempo_medio_minutos: float
    total_ordens_finalizadas: int
