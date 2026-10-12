"""Leitura do catálogo de uma loja VTEX pela Legacy Search API (`/api/catalog_system/pub/products/search`).

A paginação segue a da API: `_from`/`_to` inclusivos, no máximo 50 produtos por página e `_from` até 2.500
(acima disso a VTEX não responde; loja maior precisa da carga por SKU, ver docs/fontes/vtex.md). A demo lê o
mock gerado pelo `catalog/` com a mesma interface; um client HTTP para loja real entra no lugar de
`FonteArquivo` sem mudar o resto do conector.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

POR_PAGINA = 50
LIMITE_FROM = 2500
PASTA_MOCK = Path(__file__).resolve().parent.parent / "data" / "vtex"


class LimiteDaApi(RuntimeError):
    """O catálogo passou do teto de paginação da Legacy Search API."""


class FonteVtex(Protocol):
    def pagina(self, de: int, ate: int) -> list[dict]: ...

    def avaliacoes(self) -> dict[str, dict]: ...


class FonteArquivo:
    """Mock: os arquivos de `data/vtex/` servidos com a paginação da API."""

    def __init__(self, pasta: Path = PASTA_MOCK):
        caminho = pasta / "produtos.json"
        if not caminho.exists():
            raise FileNotFoundError(f"{caminho} não existe: rode `uv run python -m catalog.build` antes")
        # a API devolve por productId decrescente
        self._produtos = sorted(
            json.loads(caminho.read_text(encoding="utf-8")), key=lambda p: int(p["productId"]), reverse=True
        )
        self._avaliacoes = json.loads((pasta / "avaliacoes.json").read_text(encoding="utf-8"))

    def pagina(self, de: int, ate: int) -> list[dict]:
        if ate - de + 1 > POR_PAGINA:
            raise ValueError(f"a API devolve no máximo {POR_PAGINA} produtos por página")
        if de > LIMITE_FROM:
            raise LimiteDaApi(f"_from={de} passa do teto de {LIMITE_FROM} da Legacy Search API")
        return self._produtos[de : ate + 1]

    def avaliacoes(self) -> dict[str, dict]:
        return self._avaliacoes


def todos_os_produtos(fonte: FonteVtex) -> Iterator[dict]:
    de = 0
    while True:
        pagina = fonte.pagina(de, de + POR_PAGINA - 1)
        yield from pagina
        if len(pagina) < POR_PAGINA:
            return
        de += POR_PAGINA
