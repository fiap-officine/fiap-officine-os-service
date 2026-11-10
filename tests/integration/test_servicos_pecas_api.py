class TestServicosAPI:
    def test_criar_servico(self, client, auth_headers, servico_data):
        response = client.post(
            "/api/v1/servicos/", json=servico_data, headers=auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["nome"] == "Troca de Óleo"
        assert float(data["preco"]) == 150.00

    def test_listar_servicos(self, client, auth_headers, servico_data):
        client.post("/api/v1/servicos/", json=servico_data, headers=auth_headers)
        response = client.get("/api/v1/servicos/", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_buscar_servico(self, client, auth_headers, servico_data):
        create_resp = client.post(
            "/api/v1/servicos/", json=servico_data, headers=auth_headers
        )
        servico_id = create_resp.json()["id"]
        response = client.get(f"/api/v1/servicos/{servico_id}", headers=auth_headers)
        assert response.status_code == 200

    def test_atualizar_servico(self, client, auth_headers, servico_data):
        create_resp = client.post(
            "/api/v1/servicos/", json=servico_data, headers=auth_headers
        )
        servico_id = create_resp.json()["id"]
        response = client.put(
            f"/api/v1/servicos/{servico_id}",
            json={"preco": 200.00},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert float(response.json()["preco"]) == 200.00

    def test_desativar_servico(self, client, auth_headers, servico_data):
        create_resp = client.post(
            "/api/v1/servicos/", json=servico_data, headers=auth_headers
        )
        servico_id = create_resp.json()["id"]
        response = client.patch(
            f"/api/v1/servicos/{servico_id}/desativar",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["ativo"] is False

    def test_ativar_servico(self, client, auth_headers, servico_data):
        create_resp = client.post(
            "/api/v1/servicos/", json=servico_data, headers=auth_headers
        )
        servico_id = create_resp.json()["id"]
        client.patch(f"/api/v1/servicos/{servico_id}/desativar", headers=auth_headers)
        response = client.patch(
            f"/api/v1/servicos/{servico_id}/ativar", headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["ativo"] is True


class TestPecasAPI:
    def test_criar_peca(self, client, auth_headers, peca_data):
        response = client.post("/api/v1/pecas/", json=peca_data, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["nome"] == "Filtro de Óleo"
        assert "quantidade_estoque" not in data  # estoque no Execution Service

    def test_listar_pecas(self, client, auth_headers, peca_data):
        client.post("/api/v1/pecas/", json=peca_data, headers=auth_headers)
        response = client.get("/api/v1/pecas/", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_atualizar_preco(self, client, auth_headers, peca_data):
        create_resp = client.post(
            "/api/v1/pecas/", json=peca_data, headers=auth_headers
        )
        peca_id = create_resp.json()["id"]
        response = client.put(
            f"/api/v1/pecas/{peca_id}",
            json={"preco": 40.0},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert float(response.json()["preco"]) == 40.0

    def test_desativar_peca(self, client, auth_headers, peca_data):
        create_resp = client.post(
            "/api/v1/pecas/", json=peca_data, headers=auth_headers
        )
        peca_id = create_resp.json()["id"]
        response = client.patch(
            f"/api/v1/pecas/{peca_id}/desativar", headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["ativo"] is False

    def test_ativar_peca(self, client, auth_headers, peca_data):
        create_resp = client.post(
            "/api/v1/pecas/", json=peca_data, headers=auth_headers
        )
        peca_id = create_resp.json()["id"]
        client.patch(f"/api/v1/pecas/{peca_id}/desativar", headers=auth_headers)
        response = client.patch(f"/api/v1/pecas/{peca_id}/ativar", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["ativo"] is True

    def test_buscar_peca_inexistente(self, client, auth_headers):
        response = client.get("/api/v1/pecas/9999", headers=auth_headers)
        assert response.status_code == 404

    def test_atualizar_peca_inexistente(self, client, auth_headers):
        response = client.put(
            "/api/v1/pecas/9999", json={"preco": 100.0}, headers=auth_headers
        )
        assert response.status_code == 404

    def test_desativar_peca_inexistente(self, client, auth_headers):
        response = client.patch("/api/v1/pecas/9999/desativar", headers=auth_headers)
        assert response.status_code == 404

    def test_ativar_peca_inexistente(self, client, auth_headers):
        response = client.patch("/api/v1/pecas/9999/ativar", headers=auth_headers)
        assert response.status_code == 404

    def test_listar_pecas_com_inativos(self, client, auth_headers, peca_data):
        create_resp = client.post(
            "/api/v1/pecas/", json=peca_data, headers=auth_headers
        )
        peca_id = create_resp.json()["id"]
        client.patch(f"/api/v1/pecas/{peca_id}/desativar", headers=auth_headers)
        response = client.get(
            "/api/v1/pecas/?apenas_ativos=false", headers=auth_headers
        )
        assert response.status_code == 200
        ids = [p["id"] for p in response.json()]
        assert peca_id in ids

    def test_endpoint_de_estoque_removido(self, client, auth_headers, peca_data):
        """Entrada de estoque agora é PUT /api/v1/estoque/{peca_id} no Execution."""
        peca_id = client.post(
            "/api/v1/pecas/", json=peca_data, headers=auth_headers
        ).json()["id"]
        response = client.patch(
            f"/api/v1/pecas/{peca_id}/quantidade",
            json={"quantidade_entrada": 10},
            headers=auth_headers,
        )
        assert response.status_code in (404, 405)


class TestServicosAPIEdgeCases:
    def test_buscar_servico_inexistente(self, client, auth_headers):
        response = client.get("/api/v1/servicos/9999", headers=auth_headers)
        assert response.status_code == 404

    def test_atualizar_servico_inexistente(self, client, auth_headers):
        response = client.put(
            "/api/v1/servicos/9999", json={"preco": 200.0}, headers=auth_headers
        )
        assert response.status_code == 404

    def test_desativar_servico_inexistente(self, client, auth_headers):
        response = client.patch("/api/v1/servicos/9999/desativar", headers=auth_headers)
        assert response.status_code == 404

    def test_ativar_servico_inexistente(self, client, auth_headers):
        response = client.patch("/api/v1/servicos/9999/ativar", headers=auth_headers)
        assert response.status_code == 404

    def test_listar_servicos_com_inativos(self, client, auth_headers, servico_data):
        create_resp = client.post(
            "/api/v1/servicos/", json=servico_data, headers=auth_headers
        )
        servico_id = create_resp.json()["id"]
        client.patch(f"/api/v1/servicos/{servico_id}/desativar", headers=auth_headers)
        response = client.get(
            "/api/v1/servicos/?apenas_ativos=false", headers=auth_headers
        )
        assert response.status_code == 200
        ids = [s["id"] for s in response.json()]
        assert servico_id in ids
