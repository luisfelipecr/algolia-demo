"""Sobe o copiloto.

    uv run python -m copiloto                 # stdio (Claude Desktop/Code local), sem autenticação
    uv run python -m copiloto --http 8000     # Streamable HTTP em /mcp, sem estado (para deploy)

Precisa de ALGOLIA_APP_ID e de uma chave no ambiente (o .env da raiz é lido): ALGOLIA_COPILOTO_KEY (só
leitura) ou, no uso local, a ALGOLIA_WRITE_API_KEY. O deploy público (Fly, `COPILOTO_PUBLICO=1`) é sem login
e só leitura: a tool de sinônimo não é registrada e a Write key é recusada. Ver docs/DASHBOARD-SETUP.md.
"""

import argparse
import logging

from copiloto import ferramentas  # noqa: F401  (registra as tools)
from copiloto.base import servidor
from ingest.indexar import carregar_env


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--http", type=int, metavar="PORTA", help="serve Streamable HTTP nessa porta")
    args = parser.parse_args()
    carregar_env()
    if args.http:
        import uvicorn

        from copiloto.fontes import chave_algolia
        from copiloto.http import criar

        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
        chave_algolia()  # falha na subida, não na primeira pergunta, se faltar a chave certa
        from copiloto.base import PUBLICO

        # fora do deploy público (que é só leitura), escuta só a própria máquina: o modo local grava sinônimos
        host = "0.0.0.0" if PUBLICO else "127.0.0.1"  # noqa: S104
        uvicorn.run(criar(), host=host, port=args.http, workers=1, proxy_headers=PUBLICO)
    else:
        servidor.run("stdio")


if __name__ == "__main__":
    main()
