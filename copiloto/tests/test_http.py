import json
import os
import subprocess
import sys
from pathlib import Path

from starlette.testclient import TestClient

from copiloto.http import criar, proteger

RAIZ = Path(__file__).resolve().parents[2]
INICIAR = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "teste", "version": "1"},
    },
}
# fora do modo público o SDK só aceita Host local (proteção contra DNS rebinding)
LOCAL = "http://localhost:8000"
CABECALHOS = {"accept": "application/json, text/event-stream", "content-type": "application/json"}


def test_pagina_inicial_e_get_mcp_sem_sse():
    with TestClient(criar(), base_url=LOCAL) as cliente:
        assert "/mcp" in cliente.get("/").text
        r = cliente.get("/mcp")
        assert r.status_code == 405
        assert r.headers["allow"] == "POST"


def test_initialize_por_post_responde_json():
    with TestClient(criar(), base_url=LOCAL) as cliente:
        r = cliente.post("/mcp", json=INICIAR, headers=CABECALHOS)
        assert r.status_code == 200
        assert r.json()["result"]["serverInfo"]["name"] == "copiloto-merchandiser"


def test_assistente_da_loja_tem_endereco_proprio():
    with TestClient(criar(), base_url=LOCAL) as cliente:
        r = cliente.post("/loja/mcp", json=INICIAR, headers=CABECALHOS)
        assert r.json()["result"]["serverInfo"]["name"] == "assistente-da-loja"
        lista = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        tools = cliente.post("/loja/mcp", json=lista, headers=CABECALHOS).json()["result"]["tools"]
        assert [t["name"] for t in tools] == ["avisar_quando_chegar"]
        assert cliente.post("/outro", json=INICIAR, headers=CABECALHOS).status_code == 404


def test_subscriptions_listen_responde_na_hora():
    with TestClient(criar(), base_url=LOCAL) as cliente:
        r = cliente.post(
            "/mcp", json={"jsonrpc": "2.0", "id": 7, "method": "subscriptions/listen"}, headers=CABECALHOS
        )
        assert r.json()["error"]["code"] == -32601


def test_modo_local_recusa_host_de_fora():
    with TestClient(criar(), base_url="http://exemplo.com") as cliente:
        assert cliente.post("/mcp", json=INICIAR, headers=CABECALHOS).status_code == 421


def test_loja_tem_limite_menor_por_ip():
    async def ok(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    app = proteger({"/mcp": ok, "/loja/mcp": ok})
    with TestClient(app) as cliente:
        h = {"fly-client-ip": "203.0.113.20"}
        codigos = [cliente.post("/loja/mcp", json={}, headers=h).status_code for _ in range(11)]
        assert codigos[-1] == 429 and codigos[:10] == [200] * 10
        assert cliente.post("/mcp", json={}, headers=h).status_code == 200  # cada rota tem a sua conta


def test_limite_por_ip():
    async def ok(scope, receive, send):
        if scope["type"] == "lifespan":  # o TestClient abre e fecha o ciclo de vida do app
            while (await receive())["type"] != "lifespan.shutdown":
                await send({"type": "lifespan.startup.complete"})
            await send({"type": "lifespan.shutdown.complete"})
            return
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    with TestClient(proteger(ok, limite_por_minuto=2)) as cliente:
        h = {"fly-client-ip": "203.0.113.9"}
        assert [cliente.post("/mcp", json={}, headers=h).status_code for _ in range(3)] == [200, 200, 429]
        assert cliente.post("/mcp", json={}, headers={"fly-client-ip": "203.0.113.10"}).status_code == 200


def _modo_publico(codigo: str, **env) -> subprocess.CompletedProcess:
    ambiente = {k: v for k, v in os.environ.items() if not k.startswith("ALGOLIA_")} | {
        "COPILOTO_PUBLICO": "1",
        **env,
    }
    return subprocess.run(
        [sys.executable, "-c", codigo], cwd=RAIZ, env=ambiente, capture_output=True, text=True, timeout=60
    )


def test_modo_publico_nao_registra_a_tool_que_grava_no_indice():
    r = _modo_publico(
        "import json; from copiloto import ferramentas; from copiloto.base import servidor;"
        "print(json.dumps(sorted(t.name for t in servidor._tool_manager.list_tools())))"
    )
    assert r.returncode == 0, r.stderr
    tools = json.loads(r.stdout)
    assert "sinonimo" not in tools
    assert {"buscas_sem_resultado", "demanda_por_tamanho", "reportar_problema"} <= set(tools)


def test_modo_publico_recusa_a_write_key():
    r = _modo_publico(
        "from copiloto.fontes import chave_algolia; chave_algolia()", ALGOLIA_WRITE_API_KEY="nao-usar"
    )
    assert r.returncode != 0
    assert "ALGOLIA_COPILOTO_KEY" in r.stderr
