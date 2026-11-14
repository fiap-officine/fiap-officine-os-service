from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.domain.entities.ordem_servico import OrdemServico, OrdemServicoHistorico
from app.domain.enums import StatusOrdemServico
from app.repositories.base import BaseRepository


class OrdemServicoRepository(BaseRepository[OrdemServico]):
    def __init__(self, db: Session):
        super().__init__(OrdemServico, db)

    def get_by_cliente(
        self, cliente_id: int, skip: int = 0, limit: int = 100
    ) -> list[OrdemServico]:
        stmt = (
            select(OrdemServico)
            .where(OrdemServico.cliente_id == cliente_id)
            .offset(skip)
            .limit(limit)
            .order_by(OrdemServico.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def get_by_status(
        self, status: StatusOrdemServico, skip: int = 0, limit: int = 100
    ) -> list[OrdemServico]:
        stmt = (
            select(OrdemServico)
            .where(OrdemServico.status == status)
            .offset(skip)
            .limit(limit)
            .order_by(OrdemServico.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def get_list(
        self,
        status: StatusOrdemServico | None = None,
        order_by_status: bool = False,
        exclude_finalizados: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> list[OrdemServico]:
        """Retorna lista de OS com opções de ordenação por prioridade de status
        e exclusão das ordens finalizadas/entregues (lógica, não física).
        """
        stmt = select(OrdemServico)

        if status:
            stmt = stmt.where(OrdemServico.status == status)

        if exclude_finalizados:
            stmt = stmt.where(
                ~OrdemServico.status.in_(
                    [
                        StatusOrdemServico.FINALIZADA,
                        StatusOrdemServico.ENTREGUE,
                        StatusOrdemServico.CANCELADA,
                    ]
                )
            )

        if order_by_status:
            # Prioridade: em execução > diagnóstico > aguardando execução >
            # pagamento > aprovação > orçamento > recebida > outros
            prioridades = [
                StatusOrdemServico.EM_EXECUCAO,
                StatusOrdemServico.EM_DIAGNOSTICO,
                StatusOrdemServico.AGUARDANDO_EXECUCAO,
                StatusOrdemServico.AGUARDANDO_PAGAMENTO,
                StatusOrdemServico.AGUARDANDO_APROVACAO,
                StatusOrdemServico.AGUARDANDO_ORCAMENTO,
                StatusOrdemServico.RECEBIDA,
            ]
            priority_case = case(
                *[
                    (OrdemServico.status == status, idx)
                    for idx, status in enumerate(prioridades, start=1)
                ],
                else_=len(prioridades) + 1,
            )
            stmt = stmt.order_by(priority_case.asc(), OrdemServico.created_at.asc())
        else:
            stmt = stmt.order_by(OrdemServico.created_at.desc())

        stmt = stmt.offset(skip).limit(limit)

        return list(self.db.scalars(stmt).all())

    def get_tempo_medio_execucao(self) -> tuple[float, int]:
        """Retorna o tempo médio de execução (em minutos) e a quantidade de OS finalizadas."""
        stmt = select(OrdemServico).where(
            OrdemServico.status.in_(
                [StatusOrdemServico.FINALIZADA, StatusOrdemServico.ENTREGUE]
            ),
            OrdemServico.data_finalizacao.isnot(None),
        )
        ordens = list(self.db.scalars(stmt).all())

        if not ordens:
            return 0.0, 0

        total_minutos = 0.0
        count = 0
        for os in ordens:
            if os.data_finalizacao and os.created_at:
                delta = os.data_finalizacao - os.created_at
                total_minutos += delta.total_seconds() / 60
                count += 1

        if count == 0:
            return 0.0, 0

        return total_minutos / count, count

    def adicionar_historico(
        self,
        ordem_servico_id: int,
        status_anterior: str | None,
        status_novo: str,
        observacao: str | None = None,
    ) -> OrdemServicoHistorico:
        historico = OrdemServicoHistorico(
            ordem_servico_id=ordem_servico_id,
            status_anterior=status_anterior,
            status_novo=status_novo,
            observacao=observacao,
        )
        self.db.add(historico)
        self.db.commit()
        self.db.refresh(historico)
        return historico
