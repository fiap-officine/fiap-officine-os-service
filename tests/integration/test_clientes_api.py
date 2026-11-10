class TestClientesAPI:
    def test_criar_cliente(self, client, auth_headers, cliente_data):
        response = client.post(
            "/api/v1/clientes/", json=cliente_data, headers=auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["nome"] == "João da Silva"
        assert data["cpf_cnpj"] == "52998224725"

    def test_criar_cliente_sem_auth(self, client, cliente_data):
        response = client.post("/api/v1/clientes/", json=cliente_data)
        assert response.status_code == 401

    def test_criar_cliente_cpf_invalido(self, client, auth_headers):
        response = client.post(
            "/api/v1/clientes/",
            json={"nome": "Teste", "cpf_cnpj": "000.000.000-00"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_criar_cliente_cpf_duplicado(self, client, auth_headers, cliente_data):
        client.post("/api/v1/clientes/", json=cliente_data, headers=auth_headers)
        response = client.post(
            "/api/v1/clientes/", json=cliente_data, headers=auth_headers
        )
        assert response.status_code == 400

    def test_listar_clientes(self, client, auth_headers, cliente_data):
        client.post("/api/v1/clientes/", json=cliente_data, headers=auth_headers)
        response = client.get("/api/v1/clientes/", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_buscar_cliente_por_id(self, client, auth_headers, cliente_data):
        create_resp = client.post(
            "/api/v1/clientes/", json=cliente_data, headers=auth_headers
        )
        cliente_id = create_resp.json()["id"]
        response = client.get(f"/api/v1/clientes/{cliente_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["id"] == cliente_id

    def test_buscar_cliente_inexistente(self, client, auth_headers):
        response = client.get("/api/v1/clientes/9999", headers=auth_headers)
        assert response.status_code == 404

    def test_buscar_por_cpf_cnpj(self, client, auth_headers, cliente_data):
        client.post("/api/v1/clientes/", json=cliente_data, headers=auth_headers)
        response = client.get(
            "/api/v1/clientes/cpf-cnpj/52998224725", headers=auth_headers
        )
        assert response.status_code == 200

    def test_atualizar_cliente(self, client, auth_headers, cliente_data):
        create_resp = client.post(
            "/api/v1/clientes/", json=cliente_data, headers=auth_headers
        )
        cliente_id = create_resp.json()["id"]
        response = client.put(
            f"/api/v1/clientes/{cliente_id}",
            json={"nome": "Nome Atualizado"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["nome"] == "Nome Atualizado"

    def test_desativar_cliente(self, client, auth_headers, cliente_data):
        create_resp = client.post(
            "/api/v1/clientes/", json=cliente_data, headers=auth_headers
        )
        cliente_id = create_resp.json()["id"]
        response = client.delete(
            f"/api/v1/clientes/{cliente_id}/desativar", headers=auth_headers
        )
        assert response.status_code == 204

    def test_ativar_cliente(self, client, auth_headers, cliente_data):
        create_resp = client.post(
            "/api/v1/clientes/", json=cliente_data, headers=auth_headers
        )
        cliente_id = create_resp.json()["id"]
        client.delete(f"/api/v1/clientes/{cliente_id}/desativar", headers=auth_headers)
        response = client.put(
            f"/api/v1/clientes/{cliente_id}/ativar", headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["id"] == cliente_id

    def test_buscar_por_cpf_inexistente(self, client, auth_headers):
        response = client.get(
            "/api/v1/clientes/cpf-cnpj/99999999999", headers=auth_headers
        )
        assert response.status_code == 404

    def test_atualizar_cliente_inexistente(self, client, auth_headers):
        response = client.put(
            "/api/v1/clientes/9999",
            json={"nome": "Ninguém"},
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_desativar_cliente_inexistente(self, client, auth_headers):
        response = client.delete(
            "/api/v1/clientes/9999/desativar", headers=auth_headers
        )
        assert response.status_code == 404

    def test_desativar_cliente_com_os_em_aberto(
        self, client, auth_headers, cliente_data
    ):
        create_resp = client.post(
            "/api/v1/clientes/", json=cliente_data, headers=auth_headers
        )
        cliente_id = create_resp.json()["id"]

        resp = client.post(
            "/api/v1/veiculos/",
            json={
                "cliente_id": cliente_id,
                "placa": "TST9999",
                "marca": "Ford",
                "modelo": "Ka",
                "ano": 2021,
            },
            headers=auth_headers,
        )
        veiculo_id = resp.json()["id"]

        servico_id = client.post(
            "/api/v1/servicos/",
            json={"nome": "Revisão", "preco": 100.0, "tempo_estimado_minutos": 60},
            headers=auth_headers,
        ).json()["id"]
        client.post(
            "/api/v1/ordens-servico/",
            json={
                "cliente_id": cliente_id,
                "veiculo_id": veiculo_id,
                "itens_servico": [{"servico_id": servico_id}],
            },
            headers=auth_headers,
        )

        response = client.delete(
            f"/api/v1/clientes/{cliente_id}/desativar", headers=auth_headers
        )
        assert response.status_code == 400
        assert "ordens de serviço em andamento" in response.json()["detail"]

    def test_cliente_email_invalido(self, client, auth_headers):
        response = client.post(
            "/api/v1/clientes/",
            json={"nome": "João", "cpf_cnpj": "529.982.247-25", "email": "nao-é-email"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_cliente_telefone_curto(self, client, auth_headers):
        response = client.post(
            "/api/v1/clientes/",
            json={"nome": "João", "cpf_cnpj": "529.982.247-25", "telefone": "123"},
            headers=auth_headers,
        )
        assert response.status_code == 422
