class TestRotasProtegidasCpfIntegration:
    def _criar_cliente(
        self, client, auth_headers, cpf="529.982.247-25", nome="Cliente Teste"
    ):
        resp = client.post(
            "/api/v1/clientes/",
            json={
                "nome": nome,
                "cpf_cnpj": cpf,
                "email": f"{nome.replace(' ', '').lower()}@test.com",
                "telefone": "11999999999",
                "endereco": "Rua Teste, 100",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        return resp.json()

    def test_login_cliente_cpf_invalido(self, client):
        resp = client.post("/api/v1/auth/cliente", json={"cpf": "123"})
        assert resp.status_code == 422

    def test_login_cliente_nao_encontrado(self, client):
        resp = client.post("/api/v1/auth/cliente", json={"cpf": "52998224725"})
        assert resp.status_code == 404

    def test_login_cliente_inativo(self, client, auth_headers):
        cliente = self._criar_cliente(client, auth_headers)
        desat_resp = client.delete(
            f"/api/v1/clientes/{cliente['id']}/desativar", headers=auth_headers
        )
        assert desat_resp.status_code == 204

        resp = client.post("/api/v1/auth/cliente", json={"cpf": cliente["cpf_cnpj"]})
        assert resp.status_code == 400
        assert "inativo" in resp.json()["detail"].lower()

    def test_login_cliente_sucesso(self, client, auth_headers):
        cliente = self._criar_cliente(client, auth_headers)
        resp = client.post("/api/v1/auth/cliente", json={"cpf": cliente["cpf_cnpj"]})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_consultar_status_cliente_endpoint(self, client, auth_headers):
        cliente = self._criar_cliente(client, auth_headers)
        resp = client.get(f"/api/v1/auth/cliente/status/{cliente['cpf_cnpj']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == cliente["id"]
        assert data["ativo"] is True
        assert data["status_descricao"] == "Ativo"

    def test_consultar_status_cliente_inexistente(self, client):
        resp = client.get("/api/v1/auth/cliente/status/52998224725")
        assert resp.status_code == 404

    def test_rotas_me_cliente(self, client, auth_headers):
        cliente = self._criar_cliente(client, auth_headers)
        login_resp = client.post(
            "/api/v1/auth/cliente", json={"cpf": cliente["cpf_cnpj"]}
        )
        token = login_resp.json()["access_token"]
        headers_cliente = {"Authorization": f"Bearer {token}"}

        # /auth/cliente/me sem token deve retornar 401
        assert client.get("/api/v1/auth/cliente/me").status_code == 401
        # /auth/cliente/me com token válido
        resp_auth_me = client.get("/api/v1/auth/cliente/me", headers=headers_cliente)
        assert resp_auth_me.status_code == 200
        assert resp_auth_me.json()["id"] == cliente["id"]
        assert resp_auth_me.json()["ativo"] is True

        # /clientes/me sem token deve retornar 401
        assert client.get("/api/v1/clientes/me").status_code == 401
        # /clientes/me com token válido
        resp_cli_me = client.get("/api/v1/clientes/me", headers=headers_cliente)
        assert resp_cli_me.status_code == 200
        assert resp_cli_me.json()["id"] == cliente["id"]

    def test_acompanhar_os_cliente_autenticado_vs_outro_cliente(
        self, client, auth_headers
    ):
        # Cliente 1
        cli1 = self._criar_cliente(
            client, auth_headers, cpf="529.982.247-25", nome="Cliente Um"
        )
        tok1 = client.post(
            "/api/v1/auth/cliente", json={"cpf": cli1["cpf_cnpj"]}
        ).json()["access_token"]
        h1 = {"Authorization": f"Bearer {tok1}"}

        # Cliente 2
        cli2 = self._criar_cliente(
            client, auth_headers, cpf="111.444.777-35", nome="Cliente Dois"
        )
        tok2 = client.post(
            "/api/v1/auth/cliente", json={"cpf": cli2["cpf_cnpj"]}
        ).json()["access_token"]
        h2 = {"Authorization": f"Bearer {tok2}"}

        # Cria veículo e OS para cliente 1
        veic = client.post(
            "/api/v1/veiculos/",
            json={
                "placa": "ABC1234",
                "marca": "Fiat",
                "modelo": "Uno",
                "ano": 2020,
                "cliente_id": cli1["id"],
            },
            headers=auth_headers,
        ).json()
        serv = client.post(
            "/api/v1/servicos/",
            json={"nome": "Revisao", "preco": 100.0, "tempo_estimado_minutos": 60},
            headers=auth_headers,
        ).json()
        os_resp = client.post(
            "/api/v1/ordens-servico/",
            json={
                "cliente_id": cli1["id"],
                "veiculo_id": veic["id"],
                "itens_servico": [{"servico_id": serv["id"], "quantidade": 1}],
            },
            headers=auth_headers,
        ).json()
        os_id = os_resp["id"]

        # Rota /acompanhar-cliente/{os_id}
        # Sem token -> 401
        assert (
            client.get(f"/api/v1/ordens-servico/acompanhar-cliente/{os_id}").status_code
            == 401
        )
        # Com token do cliente 1 (titular) -> 200
        resp_dono = client.get(
            f"/api/v1/ordens-servico/acompanhar-cliente/{os_id}", headers=h1
        )
        assert resp_dono.status_code == 200
        assert resp_dono.json()["id"] == os_id
        # Com token do cliente 2 (outro cliente) -> 403
        resp_outro = client.get(
            f"/api/v1/ordens-servico/acompanhar-cliente/{os_id}", headers=h2
        )
        assert resp_outro.status_code == 403

        # Rota /minhas-ordens (protegida com get_current_cliente)
        # Sem token -> 401
        assert client.get("/api/v1/ordens-servico/minhas-ordens").status_code == 401
        # Cliente 1 deve ver 1 OS
        resp_minhas1 = client.get("/api/v1/ordens-servico/minhas-ordens", headers=h1)
        assert resp_minhas1.status_code == 200
        assert len(resp_minhas1.json()) == 1
        # Cliente 2 deve ver 0 OS
        resp_minhas2 = client.get("/api/v1/ordens-servico/minhas-ordens", headers=h2)
        assert resp_minhas2.status_code == 200
        assert len(resp_minhas2.json()) == 0

        # Rota /meus-veiculos (protegida com get_current_cliente)
        # Sem token -> 401
        assert client.get("/api/v1/veiculos/meus-veiculos").status_code == 401
        resp_veic1 = client.get("/api/v1/veiculos/meus-veiculos", headers=h1)
        assert resp_veic1.status_code == 200
        assert len(resp_veic1.json()) == 1
        resp_veic2 = client.get("/api/v1/veiculos/meus-veiculos", headers=h2)
        assert resp_veic2.status_code == 200
        assert len(resp_veic2.json()) == 0

        # Rota /acompanhar/{os_id}
        # Com token do titular -> 200
        resp_acomp_tok = client.get(
            f"/api/v1/ordens-servico/acompanhar/{os_id}", headers=h1
        )
        assert resp_acomp_tok.status_code == 200
        # Com token de outro cliente -> 403
        resp_acomp_outro = client.get(
            f"/api/v1/ordens-servico/acompanhar/{os_id}", headers=h2
        )
        assert resp_acomp_outro.status_code == 403
        # Sem token e sem query param -> 401
        assert (
            client.get(f"/api/v1/ordens-servico/acompanhar/{os_id}").status_code == 401
        )
        # Com query param do titular (compatibilidade retroativa) -> 200
        assert (
            client.get(
                f"/api/v1/ordens-servico/acompanhar/{os_id}?cpf_cnpj=52998224725"
            ).status_code
            == 200
        )
