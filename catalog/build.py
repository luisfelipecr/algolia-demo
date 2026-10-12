"""Gera o catálogo VTEX em pt-BR (e a versão em inglês da loja /en) a partir do dataset fixado.

    uv run python -m catalog.build            # grava em data/vtex/ (pt) e data/vtex/en/
    uv run python -m catalog.build --pendentes # lista textos de origem sem tradução e sai

Saídas (gitignored, reconstruíveis): `produtos.json` (Legacy Search API), `avaliacoes.json` (Reviews and
Ratings) e `categorias.json` (árvore de categorias).
"""

import argparse
import json
import sys
from pathlib import Path

from catalog import fonte
from catalog.traducao import Memoria
from catalog.vtex import IDIOMAS, Catalogo

SAIDA = fonte.RAIZ / "data" / "vtex"


def _gravar(caminho: Path, dados) -> None:
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--pendentes", action="store_true", help="lista textos sem tradução e sai")
    parser.add_argument("--saida", type=Path, default=SAIDA)
    args = parser.parse_args(argv)

    origem = fonte.carregar()
    memoria = Memoria.carregar()
    pendentes = memoria.pendentes({r["name"] for r in origem} | {r["description"] for r in origem})
    if args.pendentes or pendentes:
        for texto in pendentes:
            print(texto)
        print(f"{len(pendentes)} texto(s) sem tradução", file=sys.stderr)
        return 1 if pendentes else 0

    imagens = fonte.imagens_por_sku()
    for idioma in IDIOMAS:
        catalogo = Catalogo(origem, memoria, imagens, idioma)
        produtos = catalogo.produtos()
        pasta = args.saida if idioma == "pt" else args.saida / idioma
        pasta.mkdir(parents=True, exist_ok=True)
        _gravar(pasta / "produtos.json", produtos)
        _gravar(pasta / "avaliacoes.json", catalogo.avaliacoes())
        _gravar(pasta / "categorias.json", catalogo.arvore_categorias())

        skus = sum(len(p["items"]) for p in produtos)
        com_estoque = sum(
            1 for p in produtos for i in p["items"] if i["sellers"][0]["commertialOffer"]["IsAvailable"]
        )
        sem_foto = sum(1 for p in produtos if not p["items"][0]["images"])
        print(
            f"[{idioma}] {len(produtos)} produtos ({sem_foto} sem foto), "
            f"{skus} SKUs ({com_estoque} com estoque)"
        )
        print(f"[{idioma}] gravado em {pasta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
