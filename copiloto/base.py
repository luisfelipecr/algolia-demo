"""Base do MCP do merchandiser: servidor, decorador das tools, envelope da resposta, auditoria e escrita.

Padrões de servidores MCP em produção com usuários não técnicos (docs/LICOES.md):
- toda resposta traz `sobre_os_dados` (período efetivo, frescor, retenção, fonte) e, se vier vazia, o aviso de
  que vazio não prova ausência;
- erro de entrada volta como erro da tool com o próximo passo (valor inválido lista os válidos);
- escrita só com `confirmado=true` e com o `codigo` do rascunho mostrado (o código é o hash do que vai ser
  gravado: se o modelo trocar o valor depois de mostrar, o código não bate e nada é gravado);
- cada chamada vira uma linha de auditoria (JSONL), que nunca derruba a resposta.

Modo público (`COPILOTO_PUBLICO=1`, o deploy no Fly): sem login, então só leitura. A tool que grava no índice
(sinônimo) não é registrada e a auditoria vai para o log (stdout) em vez de arquivo: o disco do Fly é efêmero.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import functools
import hashlib
import inspect
import json
import logging
import os
import threading
import time
import unicodedata
from collections import deque
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from copiloto.instrucoes import INSTRUCOES, INSTRUCOES_LOJA

log = logging.getLogger("copiloto")

servidor = MCPServer(name="copiloto-merchandiser", title="Copiloto do merchandiser", instructions=INSTRUCOES)
# o assistente de compras da loja (Agent Studio) vê só as tools dele, em outro endereço (/loja/mcp)
servidor_loja = MCPServer(
    name="assistente-da-loja", title="Tools do assistente da loja", instructions=INSTRUCOES_LOJA
)

PUBLICO = os.environ.get("COPILOTO_PUBLICO") == "1"
TEMPO_TOOL_S = 20
RETENCAO_DIAS = 7  # analytics do plano Free
VAZIO = (
    "Nenhuma linha. Isso NÃO prova que não houve: confira o período (o analytics do plano Free guarda só "
    f"{RETENCAO_DIAS} dias) e os filtros antes de concluir."
)
CONFIRMAR = (
    "nada foi gravado: mostre à pessoa o rascunho abaixo e pergunte se pode aplicar; só depois do sim dela "
    "chame de novo com confirmado=true e o mesmo codigo. Pedido ou queixa não é autorização"
)
# None = auditoria no log (modo público, sem disco permanente)
AUDITORIA: Path | None = (
    Path(os.environ["COPILOTO_AUDITORIA"])
    if os.environ.get("COPILOTO_AUDITORIA")
    else None
    if PUBLICO
    else Path(__file__).resolve().parent.parent / "data" / "copiloto"
)
_ultimas: deque[dict] = deque(maxlen=20)  # para o reportar_problema anexar o contexto
_escritas: dict[str, deque[float]] = {}  # um limite por tool: abuso de uma não trava as outras
_trava_escritas = threading.Lock()


# --------------------------------------------------------------------------- utilidades


def sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)).lower()


def escolher(valor: str, opcoes: list[str] | tuple[str, ...], nome: str) -> str:
    """Valor de lista fechada; inválido levanta erro listando os válidos (nunca vira 0 em silêncio)."""
    v = (valor or "").strip()
    por_chave = {sem_acento(o): o for o in opcoes}
    if sem_acento(v) not in por_chave:
        raise ValueError(f"{nome} '{valor}' não existe. Válidos: {', '.join(opcoes)}")
    return por_chave[sem_acento(v)]


def hoje() -> dt.date:
    return dt.datetime.now(dt.UTC).date()


def _data(texto: str, nome: str) -> dt.date:
    t = (texto or "").strip()
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return dt.datetime.strptime(t, formato).date()
        except ValueError:
            continue
    raise ValueError(f"{nome} '{texto}' inválido: use AAAA-MM-DD ou dd/mm/aaaa")


def periodo(inicio: str = "", fim: str = "") -> tuple[dt.date, dt.date, list[str]]:
    """Período inclusivo em UTC, preso à janela de retenção do analytics. Devolve também os avisos."""
    avisos = []
    fim_d = _data(fim, "fim") if fim else hoje()
    inicio_d = _data(inicio, "inicio") if inicio else fim_d - dt.timedelta(days=RETENCAO_DIAS - 1)
    if inicio_d > fim_d:
        raise ValueError("inicio depois do fim")
    limite = hoje() - dt.timedelta(days=RETENCAO_DIAS - 1)
    if inicio_d < limite:
        avisos.append(
            f"o período pedido começa em {inicio_d:%d/%m/%Y}, mas o analytics do plano Free só guarda "
            f"{RETENCAO_DIAS} dias: usei a partir de {limite:%d/%m/%Y}. Antes disso é 'fora da janela', "
            "não 'não houve'"
        )
        inicio_d = limite
    return inicio_d, fim_d, avisos


def para_json(dados) -> str:
    def arredondar(v):
        if isinstance(v, float):
            return round(v, 4 if abs(v) < 1 else 2)
        if isinstance(v, dict):
            return {k: arredondar(x) for k, x in v.items()}
        if isinstance(v, list):
            return [arredondar(x) for x in v]
        return v

    return json.dumps(arredondar(dados), ensure_ascii=False, default=str)


def codigo_de(objeto) -> str:
    return hashlib.sha256(json.dumps(objeto, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:8]


def exigir_confirmacao(confirmado: bool, codigo: str, rascunho: dict) -> None:
    """Grava só com confirmado=true E o código do rascunho exato que foi mostrado."""
    esperado = codigo_de(rascunho)
    if confirmado is not True or codigo != esperado:
        raise ValueError(f"{CONFIRMAR}. codigo={esperado}\nRascunho: {para_json(rascunho)[:1500]}")


def limitar_escrita(tool: str, maximo: int = 5, minutos: int = 10) -> None:
    agora = time.monotonic()
    with _trava_escritas:
        fila = _escritas.setdefault(tool, deque(maxlen=1000))
        while fila and agora - fila[0] >= minutos * 60:
            fila.popleft()
        if len(fila) >= maximo:
            raise ValueError(f"limite de {maximo} escritas a cada {minutos} min atingido: tente mais tarde")
        fila.append(agora)


def _gravar(arquivo: str, linha: dict) -> None:
    if AUDITORIA is None:
        log.info("auditoria %s %s", arquivo, json.dumps(linha, ensure_ascii=False, default=str))
        return
    try:
        AUDITORIA.mkdir(parents=True, exist_ok=True)
        with (AUDITORIA / arquivo).open("a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False, default=str) + "\n")
    except OSError:
        log.exception("auditoria falhou (a resposta segue)")


def registrar(arquivo: str, **campos) -> None:
    _gravar(arquivo, {"quando": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), **campos})


def ultimas_chamadas(n: int = 3) -> list[dict]:
    return list(_ultimas)[-n:]


# --------------------------------------------------------------------------- decorador


def _executar(fn, kwargs, nome_tool) -> tuple[str, bool]:
    t0 = time.monotonic()
    erro = ""
    try:
        res = fn(**kwargs)
        if not isinstance(res, dict):
            res = {"resultado": res}
        if res.get("total_linhas") == 0:
            res.setdefault("aviso", VAZIO)
    except ValueError as exc:
        res, erro = {"erro": str(exc)}, str(exc)
    except Exception as exc:
        log.exception("tool %s falhou", nome_tool)
        res = {
            "erro": f"falha interna ({type(exc).__name__}); ficou no registro",
            "proximo_passo": "tente de novo; se repetir, use reportar_problema",
        }
        erro = f"{type(exc).__name__}: {exc}"
    texto = para_json(res)
    linha = {
        "tool": nome_tool,
        "argumentos": kwargs,
        "ms": int((time.monotonic() - t0) * 1000),
        "erro": erro[:2000],
        "resumo": texto[:1500],
    }
    _ultimas.append(linha)
    registrar("chamadas.jsonl", **linha)
    return texto, bool(erro)


def ferramenta(
    *,
    titulo: str,
    escrita: bool = False,
    destrutiva: bool = False,
    so_local: bool = False,
    alvo: MCPServer | None = None,
):
    """Registra uma função síncrona como tool: roda numa thread com tempo máximo, embala e audita.

    `so_local`: grava no índice; no modo público (sem login) não é registrada. `alvo`: o servidor (padrão: o
    do merchandiser).
    """

    def decorar(fn):
        parametros = list(inspect.signature(fn).parameters)

        @functools.wraps(fn)
        async def envoltorio(*args, **kwargs):
            kwargs = dict(zip(parametros, args, strict=False)) | kwargs
            try:
                texto, deu_erro = await asyncio.wait_for(
                    asyncio.to_thread(_executar, fn, kwargs, fn.__name__), TEMPO_TOOL_S
                )
            except TimeoutError:
                texto = para_json(
                    {
                        "erro": f"passou de {TEMPO_TOOL_S} s e foi interrompida",
                        "proximo_passo": "tente um período menor; se repetir, use reportar_problema",
                    }
                )
                registrar("chamadas.jsonl", tool=fn.__name__, argumentos=kwargs, erro="tempo esgotado")
                deu_erro = True
            if deu_erro:
                raise ToolError(texto)
            return texto

        fn.mcp = envoltorio  # testes passam pelo envoltório
        if so_local and PUBLICO:
            return fn
        (alvo or servidor).tool(
            name=fn.__name__,
            title=titulo,
            annotations=ToolAnnotations(
                title=titulo, readOnlyHint=not escrita, destructiveHint=destrutiva, openWorldHint=False
            ),
        )(envoltorio)
        return fn

    return decorar
