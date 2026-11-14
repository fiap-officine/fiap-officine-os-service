"""Testes de integração da API de Ordens de Serviço (fluxo orquestrado pela saga)."""

from tests.helpers import (
    comandos_enviados,
    criar_os,
    levar_ate_execucao,
    responder,
    saga_de,
    setup_dados,
)


class TestCriarOrdemServico:
    def test_criar_os_inicia_saga_e_envia_gerar_orcamento(
        self, client, auth_headers, db_session
    ):
        ids = setup_dados(client, auth_headers)
        data = criar_os(client, auth_headers, ids)

        assert data["status"] == "aguardando_orcamento"
        assert float(data["valor_total"]) == 221.00
        assert len(data["itens_servico"]) == 1
        assert len(data["itens_peca"]) == 1
        assert [h["status_novo"] for h in data["historico"]] == [
            "recebida",
            "aguardando_orcamento",
        ]
        saga = saga_de(db_session, data["id"])
        assert saga.state == "BUDGET_PENDING"
        assert saga.deadline_at is not None
        assert comandos_enviados(db_session, data["id"]) == ["GerarOrcamento"]

    def test_payload_gerar_orcamento_congela_precos(
        self, client, auth_headers, db_session
    ):
        from tests.helpers import ultimo_comando

        ids = setup_dados(client, auth_headers)
        data = criar_os(client, auth_headers, ids)
        envelope = ultimo_comando(db_session, data["id"]).envelope
        assert envelope["kind"] == "command"
        assert envelope["source"] == "os-service"
        assert envelope["saga_id"] == saga_de(db_session, data["id"]).id
        itens = envelope["payload"]["itens"]
        assert {i["tipo"] for i in itens} == {"servico", "peca"}
        peca = next(i for i in itens if i["tipo"] == "peca")
        assert peca["quantidade"] == 2
        assert peca["valor_unitario"] == "35.50"
        assert envelope["payload"]["cliente"]["email"] == "os@test.com"

    def test_criar_os_sem_itens_retorna_400(self, client, auth_headers):
        cliente_id, veiculo_id, _, _ = setup_dados(client, auth_headers)
        response = client.post(
            "/api/v1/ordens-servico/",
            json={
                "cliente_id": cliente_id,
                "veiculo_id": veiculo_id,
                "itens_servico": [],
            },
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_criar_os_quantidade_invalida(self, client, auth_headers):
        cliente_id, veiculo_id, servico_id, _ = setup_dados(client, auth_headers)
        response = client.post(
            "/api/v1/ordens-servico/",
            json={
                "cliente_id": cliente_id,
                "veiculo_id": veiculo_id,
                "itens_servico": [{"servico_id": servico_id, "quantidade": 0}],
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_criar_os_veiculo_outro_cliente(self, client, auth_headers):
        _, veiculo_id, servico_id, _ = setup_dados(client, auth_headers)
        outro = client.post(
            "/api/v1/clientes/",
            json={"nome": "Outro", "cpf_cnpj": "11222333000181"},
            headers=auth_headers,
        ).json()["id"]
        response = client.post(
            "/api/v1/ordens-servico/",
            json={
                "cliente_id": outro,
                "veiculo_id": veiculo_id,
                "itens_servico": [{"servico_id": servico_id}],
            },
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_criar_os_cliente_inexistente(self, client, auth_headers):
        response = client.post(
            "/api/v1/ordens-servico/",
            json={
                "cliente_id": 999,
                "veiculo_id": 1,
                "itens_servico": [{"servico_id": 1}],
            },
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_criar_os_cliente_inativo(self, client, auth_headers):
        cliente_id, veiculo_id, servico_id, _ = setup_dados(client, auth_headers)
        client.delete(f"/api/v1/clientes/{cliente_id}/desativar", headers=auth_headers)
        response = client.post(
            "/api/v1/ordens-servico/",
            json={
                "cliente_id": cliente_id,
                "veiculo_id": veiculo_id,
                "itens_servico": [{"servico_id": servico_id}],
            },
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_criar_os_veiculo_inexistente(self, client, auth_headers):
        cliente_id, _, servico_id, _ = setup_dados(client, auth_headers)
        response = client.post(
            "/api/v1/ordens-servico/",
            json={
                "cliente_id": cliente_id,
                "veiculo_id": 999,
                "itens_servico": [{"servico_id": servico_id}],
            },
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_criar_os_servico_inexistente(self, client, auth_headers):
        cliente_id, veiculo_id, _, _ = setup_dados(client, auth_headers)
        response = client.post(
            "/api/v1/ordens-servico/",
            json={
                "cliente_id": cliente_id,
                "veiculo_id": veiculo_id,
                "itens_servico": [{"servico_id": 999}],
            },
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_criar_os_servico_inativo(self, client, auth_headers):
        cliente_id, veiculo_id, servico_id, _ = setup_dados(client, auth_headers)
        client.patch(f"/api/v1/servicos/{servico_id}/desativar", headers=auth_headers)
        response = client.post(
            "/api/v1/ordens-servico/",
            json={
                "cliente_id": cliente_id,
                "veiculo_id": veiculo_id,
                "itens_servico": [{"servico_id": servico_id}],
            },
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_criar_os_peca_inexistente(self, client, auth_headers):
        cliente_id, veiculo_id, _, _ = setup_dados(client, auth_headers)
        response = client.post(
            "/api/v1/ordens-servico/",
            json={
                "cliente_id": cliente_id,
                "veiculo_id": veiculo_id,
                "itens_peca": [{"peca_id": 999}],
            },
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_criar_os_peca_inativa(self, client, auth_headers):
        cliente_id, veiculo_id, _, peca_id = setup_dados(client, auth_headers)
        client.patch(f"/api/v1/pecas/{peca_id}/desativar", headers=auth_headers)
        response = client.post(
            "/api/v1/ordens-servico/",
            json={
                "cliente_id": cliente_id,
                "veiculo_id": veiculo_id,
                "itens_peca": [{"peca_id": peca_id}],
            },
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_criar_os_sem_autenticacao(self, client):
        response = client.post("/api/v1/ordens-servico/", json={})
        assert response.status_code == 401


class TestConsultasOrdemServico:
    def test_listar_e_buscar(self, client, auth_headers):
        ids = setup_dados(client, auth_headers)
        os_id = criar_os(client, auth_headers, ids)["id"]

        lista = client.get("/api/v1/ordens-servico/", headers=auth_headers)
        assert lista.status_code == 200
        assert [o["id"] for o in lista.json()] == [os_id]

        detalhe = client.get(f"/api/v1/ordens-servico/{os_id}", headers=auth_headers)
        assert detalhe.status_code == 200
        assert detalhe.json()["id"] == os_id

    def test_buscar_os_inexistente(self, client, auth_headers):
        response = client.get("/api/v1/ordens-servico/999", headers=auth_headers)
        assert response.status_code == 404

    def test_listar_por_status_e_ordenado(self, client, auth_headers):
        ids = setup_dados(client, auth_headers)
        criar_os(client, auth_headers, ids)
        resp = client.get(
            "/api/v1/ordens-servico/?status=aguardando_orcamento&order_by_status=true",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        vazio = client.get(
            "/api/v1/ordens-servico/?status=em_execucao", headers=auth_headers
        )
        assert vazio.json() == []

    def test_buscar_ordens_por_cliente(self, client, auth_headers):
        ids = setup_dados(client, auth_headers)
        criar_os(client, auth_headers, ids)
        resp = client.get(
            f"/api/v1/ordens-servico/cliente/{ids[0]}", headers=auth_headers
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_acompanhar_pelo_cpf(self, client, auth_headers):
        ids = setup_dados(client, auth_headers)
        os_id = criar_os(client, auth_headers, ids)["id"]
        ok = client.get(
            f"/api/v1/ordens-servico/acompanhar/{os_id}?cpf_cnpj=52998224725"
        )
        assert ok.status_code == 200
        errado = client.get(
            f"/api/v1/ordens-servico/acompanhar/{os_id}?cpf_cnpj=00000000000"
        )
        assert errado.status_code == 403
        sem_auth = client.get(f"/api/v1/ordens-servico/acompanhar/{os_id}")
        assert sem_auth.status_code == 401

    def test_consultar_saga(self, client, auth_headers, db_session):
        ids = setup_dados(client, auth_headers)
        os_id = criar_os(client, auth_headers, ids)["id"]
        responder(db_session, os_id, "OrcamentoGerado", {"orcamento_id": 7})

        resp = client.get(f"/api/v1/ordens-servico/{os_id}/saga", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "APPROVAL_PENDING"
        assert data["orcamento_id"] == 7
        tipos = [s["message_type"] for s in data["steps"] if s["message_type"]]
        assert tipos == ["GerarOrcamento", "OrcamentoGerado"]

    def test_consultar_saga_os_inexistente(self, client, auth_headers):
        resp = client.get("/api/v1/ordens-servico/999/saga", headers=auth_headers)
        assert resp.status_code == 404


class TestCancelamentoEEntrega:
    def test_cancelar_antes_do_orcamento_cancela_orcamento(
        self, client, auth_headers, db_session
    ):
        ids = setup_dados(client, auth_headers)
        os_id = criar_os(client, auth_headers, ids)["id"]

        resp = client.post(
            f"/api/v1/ordens-servico/{os_id}/cancelar",
            json={"motivo": "Cliente desistiu"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "em_compensacao"
        assert comandos_enviados(db_session, os_id)[-1] == "CancelarOrcamento"

        responder(db_session, os_id, "OrcamentoCancelado", {"orcamento_id": None})
        detalhe = client.get(f"/api/v1/ordens-servico/{os_id}", headers=auth_headers)
        assert detalhe.json()["status"] == "cancelada"
        assert saga_de(db_session, os_id).state == "CANCELLED"

    def test_cancelar_aguardando_execucao_compensa_tudo_em_ordem(
        self, client, auth_headers, db_session
    ):
        ids = setup_dados(client, auth_headers)
        os_id = criar_os(client, auth_headers, ids)["id"]
        levar_ate_execucao(db_session, os_id)

        resp = client.post(
            f"/api/v1/ordens-servico/{os_id}/cancelar", headers=auth_headers
        )
        assert resp.status_code == 200
        assert saga_de(db_session, os_id).pending_compensations == [
            "LiberarReserva",
            "EstornarPagamento",
            "CancelarOrcamento",
        ]
        responder(db_session, os_id, "ReservaLiberada")
        assert comandos_enviados(db_session, os_id)[-1] == "EstornarPagamento"
        responder(db_session, os_id, "PagamentoEstornado", {"pagamento_id": 20})
        assert comandos_enviados(db_session, os_id)[-1] == "CancelarOrcamento"
        responder(db_session, os_id, "OrcamentoCancelado", {"orcamento_id": 10})
        assert saga_de(db_session, os_id).state == "CANCELLED"

    def test_cancelar_apos_inicio_do_reparo_e_bloqueado(
        self, client, auth_headers, db_session
    ):
        ids = setup_dados(client, auth_headers)
        os_id = criar_os(client, auth_headers, ids)["id"]
        levar_ate_execucao(db_session, os_id)
        responder(db_session, os_id, "ReparoIniciado")

        resp = client.post(
            f"/api/v1/ordens-servico/{os_id}/cancelar", headers=auth_headers
        )
        assert resp.status_code == 409
        assert "pivô" in resp.json()["detail"]

    def test_cancelar_duas_vezes(self, client, auth_headers):
        ids = setup_dados(client, auth_headers)
        os_id = criar_os(client, auth_headers, ids)["id"]
        client.post(f"/api/v1/ordens-servico/{os_id}/cancelar", headers=auth_headers)
        resp = client.post(
            f"/api/v1/ordens-servico/{os_id}/cancelar", headers=auth_headers
        )
        assert resp.status_code == 409

    def test_cliente_nao_cancela_os_de_outro(self, client, auth_headers):
        from app.services.auth_service import create_access_token

        ids = setup_dados(client, auth_headers)
        os_id = criar_os(client, auth_headers, ids)["id"]
        client.post(
            "/api/v1/clientes/",
            json={"nome": "Outro", "cpf_cnpj": "111.444.777-35"},
            headers=auth_headers,
        )
        token = create_access_token({"sub": "11144477735", "role": "cliente"})
        resp = client.post(
            f"/api/v1/ordens-servico/{os_id}/cancelar",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_cliente_cancela_a_propria_os(self, client, auth_headers):
        from app.services.auth_service import create_access_token

        ids = setup_dados(client, auth_headers)
        os_id = criar_os(client, auth_headers, ids)["id"]
        token = create_access_token({"sub": "52998224725", "role": "cliente"})
        resp = client.post(
            f"/api/v1/ordens-servico/{os_id}/cancelar",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_entregar_somente_apos_finalizada(self, client, auth_headers, db_session):
        ids = setup_dados(client, auth_headers)
        os_id = criar_os(client, auth_headers, ids)["id"]

        cedo = client.post(
            f"/api/v1/ordens-servico/{os_id}/entregar", headers=auth_headers
        )
        assert cedo.status_code == 400

        levar_ate_execucao(db_session, os_id)
        responder(db_session, os_id, "ExecucaoFinalizada", {"observacao": "ok"})
        resp = client.post(
            f"/api/v1/ordens-servico/{os_id}/entregar",
            json={"observacao": "Retirado pelo cliente"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "entregue"
        assert data["data_entrega"] is not None

    def test_tempo_medio_apos_finalizacao(self, client, auth_headers, db_session):
        vazio = client.get("/api/v1/ordens-servico/tempo-medio", headers=auth_headers)
        assert vazio.json()["total_ordens_finalizadas"] == 0

        ids = setup_dados(client, auth_headers)
        os_id = criar_os(client, auth_headers, ids)["id"]
        levar_ate_execucao(db_session, os_id)
        responder(db_session, os_id, "ExecucaoFinalizada")
        resp = client.get("/api/v1/ordens-servico/tempo-medio", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total_ordens_finalizadas"] == 1

    def test_cliente_com_os_em_andamento_nao_pode_ser_desativado(
        self, client, auth_headers
    ):
        ids = setup_dados(client, auth_headers)
        criar_os(client, auth_headers, ids)
        resp = client.delete(
            f"/api/v1/clientes/{ids[0]}/desativar", headers=auth_headers
        )
        assert resp.status_code == 400
