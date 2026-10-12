"""App ASGI do copiloto em Streamable HTTP (o deploy público no Fly).

Sem estado e com resposta JSON única (sem SSE). Por fora do app do SDK, um envoltório com o que servidores
MCP em produção ensinaram (docs/LICOES.md):
- `GET /mcp` responde 405: em modo sem estado o SDK abria um fluxo SSE que nunca fechava;
- `subscriptions/listen` responde "método não existe" na hora: o SDK segurava a chamada por ~240 s;
- corpo acima de 1 MB volta 413 sem chegar ao SDK;
- uma linha de log por chamada (método JSON-RPC, tool, status, tempo).
E, por ser público e sem login: limite de requisições por IP e uma página `/` para quem abrir no navegador.

Dois servidores MCP no mesmo app: o do merchandiser em `/mcp` (só leitura no modo público) e o do assistente
da loja em `/loja/mcp` (só o aviso de "quando chegar", que o Agent Studio chama).
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict, deque
from contextlib import AsyncExitStack

from mcp.server.transport_security import TransportSecuritySettings

from copiloto import ferramentas  # noqa: F401  (registra as tools)
from copiloto.base import PUBLICO, servidor, servidor_loja

log = logging.getLogger("copiloto.http")

SEM_SUPORTE = {"subscriptions/listen"}
MAX_CORPO = 1_000_000
LIMITE_POR_MINUTO = 60  # por IP; um cliente MCP faz poucas chamadas por pergunta
# /loja/mcp grava avisos a partir de um endereço público: limite menor por IP
LIMITES_POR_ROTA = {"/loja/mcp": 10}
PAGINA = (
    "Copiloto do merchandiser da Loja Demo: servidor MCP (Streamable HTTP) em /mcp"
    + (", só leitura.\n" if PUBLICO else ".\n")
    + "Adicione esta URL + /mcp como conector no Claude ou no ChatGPT.\n"
    "Código e documentação: github.com/luisfelipecr/algolia-demo\n"
)


async def _responder(send, status: int, corpo: bytes, tipo: bytes = b"text/plain; charset=utf-8", extra=()):
    await send(
        {"type": "http.response.start", "status": status, "headers": [(b"content-type", tipo), *extra]}
    )
    await send({"type": "http.response.body", "body": corpo})


def _ip(scope) -> str:
    cabecalhos = dict(scope.get("headers") or [])
    # o proxy do Fly põe o IP do cliente em Fly-Client-IP (X-Forwarded-For o cliente pode forjar)
    ip = cabecalhos.get(b"fly-client-ip")
    return ip.decode() if ip else (scope.get("client") or ("?",))[0]


async def _ciclo_de_vida(apps, receive, send):
    """Lifespan ASGI de vários apps: cada servidor MCP precisa do seu gerenciador de sessões rodando."""
    async with AsyncExitStack() as pilha:
        for a in apps:
            contexto = getattr(getattr(a, "router", None), "lifespan_context", None)
            if contexto is not None:
                await pilha.enter_async_context(contexto(a))
        await receive()  # lifespan.startup
        await send({"type": "lifespan.startup.complete"})
        await receive()  # lifespan.shutdown
    await send({"type": "lifespan.shutdown.complete"})


def proteger(rotas, limite_por_minuto: int = LIMITE_POR_MINUTO):
    """`rotas`: {caminho: app MCP}, ou um app só (servido em /mcp)."""
    if not isinstance(rotas, dict):
        rotas = {"/mcp": rotas}
    acessos: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def limite_da(rota: str) -> int:
        return LIMITES_POR_ROTA.get(rota, limite_por_minuto)

    def acima_do_limite(rota: str, ip: str) -> bool:
        agora = time.monotonic()
        fila = acessos[(rota, ip)]
        while fila and agora - fila[0] > 60:
            fila.popleft()
        if len(fila) >= limite_da(rota):
            return True
        fila.append(agora)
        if len(acessos) > 10_000:  # não deixa a memória crescer: esquece quem não chama há mais de 1 min
            for chave in [k for k, f in acessos.items() if not f or agora - f[-1] > 60]:
                del acessos[chave]
        return False

    async def app(scope, receive, send):
        if scope.get("type") == "lifespan":
            if len(rotas) == 1:
                return await next(iter(rotas.values()))(scope, receive, send)
            return await _ciclo_de_vida(list(rotas.values()), receive, send)
        if scope.get("type") != "http":
            return await next(iter(rotas.values()))(scope, receive, send)
        caminho, metodo = scope.get("path"), scope.get("method")
        if caminho in ("/", "/saude") and metodo in ("GET", "HEAD"):
            return await _responder(send, 200, PAGINA.encode())
        if caminho not in rotas:
            return await _responder(send, 404, b"Nada aqui: o servidor MCP fica em /mcp.")
        mcp_app = rotas[caminho]
        if metodo == "GET":
            return await _responder(
                send,
                405,
                "Este servidor MCP não abre fluxo SSE: use POST.".encode(),
                extra=[(b"allow", b"POST")],
            )
        if metodo == "POST" and acima_do_limite(caminho, _ip(scope)):
            return await _responder(
                send,
                429,
                f"Limite de {limite_da(caminho)} chamadas por minuto por IP: tente em instantes.".encode(),
                extra=[(b"retry-after", b"60")],
            )

        t0, corpo, status = time.monotonic(), bytearray(), {"n": 0}
        mensagens = []
        while True:  # lê o corpo inteiro antes (é pequeno) para decidir e depois repassá-lo ao SDK
            msg = await receive()
            mensagens.append(msg)
            if msg.get("type") != "http.request":
                break
            corpo.extend(msg.get("body", b""))
            if len(corpo) > MAX_CORPO:
                return await _responder(send, 413, b"Pedido grande demais.")
            if not msg.get("more_body"):
                break
        try:
            pedido = json.loads(bytes(corpo))
        except ValueError:
            pedido = None
        if isinstance(pedido, dict) and pedido.get("method") in SEM_SUPORTE:
            erro = {
                "jsonrpc": "2.0",
                "id": pedido.get("id"),
                "error": {"code": -32601, "message": "Method not found"},
            }
            log.info(
                "mcp POST %s status=200 ms=%d (sem suporte)", pedido["method"], (time.monotonic() - t0) * 1000
            )
            return await _responder(send, 200, json.dumps(erro).encode(), b"application/json")

        fila = list(mensagens)

        async def receber():
            return fila.pop(0) if fila else await receive()

        async def enviar(msg):
            if msg.get("type") == "http.response.start":
                status["n"] = msg.get("status", 0)
            await send(msg)

        try:
            await mcp_app(scope, receber, enviar)
        finally:
            if isinstance(pedido, dict):
                nome, tool = pedido.get("method", "resposta"), (pedido.get("params") or {}).get("name") or ""
            else:
                nome, tool = ("lote" if isinstance(pedido, list) else "?"), ""
            log.info(
                "mcp %s %s %s status=%s ms=%d",
                metodo,
                nome,
                tool,
                status["n"],
                (time.monotonic() - t0) * 1000,
            )

    return app


def criar():
    """Apps do SDK sem estado e com resposta JSON. No modo público (atrás do proxy do Fly) a proteção contra
    DNS rebinding do SDK, que só aceita localhost, daria 421: fica desligada; HTTPS e limite por IP cobrem.
    Fora dele, o servidor só escuta a própria máquina e a proteção fica ligada."""

    def montar(srv, caminho):
        if PUBLICO:
            seguranca, host = TransportSecuritySettings(enable_dns_rebinding_protection=False), "0.0.0.0"
        else:
            seguranca, host = None, "127.0.0.1"
        return srv.streamable_http_app(
            streamable_http_path=caminho,
            stateless_http=True,
            json_response=True,
            transport_security=seguranca,
            host=host,
        )

    return proteger({"/mcp": montar(servidor, "/mcp"), "/loja/mcp": montar(servidor_loja, "/loja/mcp")})
