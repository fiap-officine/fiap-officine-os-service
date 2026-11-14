"""Endpoint interno usado pela Lambda (em vez de acessar o banco do OS Service)."""

TOKEN = {"x-internal-token": "token-interno-teste"}


def test_status_cliente_requer_token(client):
    assert client.get("/internal/clientes/status/52998224725").status_code == 401
    resp = client.get(
        "/internal/clientes/status/52998224725", headers={"x-internal-token": "errado"}
    )
    assert resp.status_code == 401


def test_status_cliente_ativo_inativo_e_inexistente(client, auth_headers, cliente_data):
    cliente = client.post(
        "/api/v1/clientes/", json=cliente_data, headers=auth_headers
    ).json()

    resp = client.get("/internal/clientes/status/529.982.247-25", headers=TOKEN)
    assert resp.status_code == 200
    assert resp.json()["ativo"] is True
    assert resp.json()["id"] == cliente["id"]

    client.delete(f"/api/v1/clientes/{cliente['id']}/desativar", headers=auth_headers)
    resp = client.get("/internal/clientes/status/52998224725", headers=TOKEN)
    assert resp.json()["ativo"] is False
    assert resp.json()["status_descricao"] == "Inativo"

    assert (
        client.get("/internal/clientes/status/11144477735", headers=TOKEN).status_code
        == 404
    )
    assert client.get("/internal/clientes/status/123", headers=TOKEN).status_code == 400
