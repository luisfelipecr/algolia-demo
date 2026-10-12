"""Roda o golden set de busca contra a Algolia e grava o relatório em `evals/resultados/AAAA-MM-DD.md` (UTC).

    uv run python -m evals.rodar                         # uma chamada multi-query (1 busca por consulta)
    uv run python -m evals.rodar --bruto resposta.json   # idem, guardando a resposta crua para reavaliar
    uv run python -m evals.rodar --de-arquivo resposta.json  # reavalia uma resposta guardada, sem rede
    uv run python -m evals.rodar --idioma en             # loja /en (consultas_en.json, relatório -en.md)

Só leitura e só busca: usa ALGOLIA_APP_ID e ALGOLIA_SEARCH_API_KEY do `.env` (nunca a Write key) e faz **uma**
chamada `search` com todas as consultas. O plano Free tem 10K buscas por mês e cada consulta do multi-query
conta como uma busca. As consultas vão com `analytics: false` para não poluir o analytics que o MCP vai ler.
Sai com código 1 se alguma consulta falhar.
"""

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from evals.avaliador import avaliar_consulta

PASTA = Path(__file__).resolve().parent
RAIZ = PASTA.parent
CONSULTAS = PASTA / "consultas.json"
RESULTADOS = PASTA / "resultados"
CATALOGO = RAIZ / "data" / "algolia" / "registros.json"
# por idioma: consultas, catálogo local (gravado pelo ensaio do conector) e sufixo do relatório
IDIOMAS = {
    "pt": (CONSULTAS, CATALOGO, ""),
    "en": (PASTA / "consultas_en.json", RAIZ / "data" / "algolia" / "registros_en.json", "-en"),
}


def carregar_golden(caminho: Path = CONSULTAS) -> dict:
    golden = json.loads(caminho.read_text(encoding="utf-8"))
    ids = [c["id"] for c in golden["consultas"]]
    if len(ids) != len(set(ids)):
        raise ValueError("id de consulta repetido no golden set")
    return golden


def carregar_catalogo(caminho: Path = CATALOGO) -> list[dict]:
    if not caminho.exists():
        raise SystemExit(
            f"catálogo local ausente ({caminho}); "
            "gere com `uv run python -m ingest.indexar` (ensaio, sem escrita)"
        )
    return json.loads(caminho.read_text(encoding="utf-8"))


def montar_requests(golden: dict) -> list[dict]:
    """Uma request por consulta, na ordem do golden set (a resposta do multi-query vem na mesma ordem)."""
    requests = []
    for caso in golden["consultas"]:
        requests.append(
            {
                **golden.get("parametros_comuns", {}),
                **caso.get("parametros", {}),
                "indexName": caso.get("indice", golden["indice_padrao"]),
                "query": caso["consulta"],
            }
        )
    return requests


def buscar(requests: list[dict], client=None) -> list[dict]:
    """Uma única chamada `search` (multi-query). Devolve os resultados crus, na ordem das requests."""
    if client is None:
        from algoliasearch.search.client import SearchClientSync

        from ingest.indexar import carregar_env

        carregar_env()
        faltando = [v for v in ("ALGOLIA_APP_ID", "ALGOLIA_SEARCH_API_KEY") if not os.environ.get(v)]
        if faltando:
            raise SystemExit(f"faltam no .env: {', '.join(faltando)}")
        client = SearchClientSync(os.environ["ALGOLIA_APP_ID"], os.environ["ALGOLIA_SEARCH_API_KEY"])
    resposta = client.search_with_http_info({"requests": requests, "strategy": "none"})
    resultados = json.loads(resposta.raw_data)["results"]
    if len(resultados) != len(requests):
        raise RuntimeError(f"a Algolia devolveu {len(resultados)} resultados para {len(requests)} consultas")
    return resultados


def avaliar(golden: dict, resultados: list[dict], catalogo: list[dict]) -> list[dict]:
    saida = []
    for caso, resultado in zip(golden["consultas"], resultados, strict=True):
        indice = caso.get("indice", golden["indice_padrao"])
        if resultado.get("index") not in (None, indice):
            raise RuntimeError(f"resposta fora de ordem na consulta {caso['id']}")
        avaliacao = avaliar_consulta(caso, resultado, catalogo)
        avaliacao.update(
            consulta=caso["consulta"],
            indice=indice,
            grupo=caso.get("grupo", ""),
            nota=caso.get("nota", ""),
            achado=caso.get("achado"),
            limitacao=caso.get("limitacao_conhecida"),
        )
        saida.append(avaliacao)
    return saida


def _celula(texto: str) -> str:
    return texto.replace("|", "\\|").replace("\n", " ")


def relatorio(
    avaliacoes: list[dict],
    quando: datetime,
    buscas: int,
    origem: str,
    consultas: str = "evals/consultas.json",
    catalogo: str = "data/algolia/registros.json",
) -> str:
    passaram = sum(a["passou"] for a in avaliacoes)
    linhas = [
        f"# Golden set de busca, {quando:%Y-%m-%d} (UTC)",
        "",
        f"- Executado em {quando:%Y-%m-%d %H:%M} UTC; origem da resposta: {origem}.",
        f"- **{passaram} de {len(avaliacoes)} consultas passaram.**",
        f"- Buscas gastas da cota nesta execução: {buscas} (uma chamada multi-query, `analytics: false`).",
        "- Expectativas: propriedades semânticas do hit ou contagens do catálogo local "
        f"(`{catalogo}`); nada vem do ranking do índice. "
        f"Definições em `{consultas}`.",
        "",
        "| # | id | consulta | índice | nbHits | resultado |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for i, a in enumerate(avaliacoes, 1):
        status = "passou" if a["passou"] else "**FALHOU**"
        if a["limitacao"]:
            status = "limitação documentada (resultado esperado)" if a["passou"] else status
        consulta = f"`{a['consulta']}`" if a["consulta"] else "(vazia)"
        linhas.append(f"| {i} | {a['id']} | {_celula(consulta)} | {a['indice']} | {a['nbHits']} | {status} |")

    falhas = [a for a in avaliacoes if not a["passou"]]
    linhas += ["", "## Falhas", ""]
    if not falhas:
        linhas.append("Nenhuma.")
    for a in falhas:
        linhas += [f"### {a['id']} (`{a['consulta']}`)", "", f"- Por que importa: {a['nota']}"]
        for d in a["detalhes"]:
            if not d["passou"]:
                linhas.append(f"- Falhou `{d['tipo']}`: {d['explicacao']}")
        if a["achado"]:
            linhas.append(f"- **Diagnóstico:** {a['achado']}")
        else:
            linhas.append(
                "- **Diagnóstico:** ainda não registrado (campo `achado` em `evals/consultas.json`)."
            )
        linhas.append("")

    revisar = [a for a in avaliacoes if a["passou"] and a["achado"]]
    if revisar:
        linhas += ["## Achados registrados que já passam (o campo `achado` guarda a história)", ""]
        linhas += [f"- {a['id']}: {a['achado']}" for a in revisar]
        linhas.append("")

    limitacoes = [a for a in avaliacoes if a["limitacao"]]
    if limitacoes:
        linhas += ["## Limitações conhecidas (documentadas, não são regressão)", ""]
        linhas += [f"- {a['id']}: {a['limitacao']}" for a in limitacoes]
        linhas.append("")

    linhas += ["## Detalhe de todas as expectativas", ""]
    for a in avaliacoes:
        linhas.append(f"- **{a['id']}** ({a['grupo']})")
        for d in a["detalhes"]:
            marca = "ok" if d["passou"] else "FALHOU"
            linhas.append(f"  - {marca} `{d['tipo']}`: {d['explicacao']}")
    return "\n".join(linhas) + "\n"


def main(argv: list[str] | None = None, client=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--de-arquivo", type=Path, help="reavalia uma resposta guardada com --bruto (sem rede)"
    )
    parser.add_argument("--bruto", type=Path, help="guarda a resposta crua da Algolia neste arquivo")
    parser.add_argument("--idioma", choices=list(IDIOMAS), default="pt", help="golden set (padrão: pt)")
    parser.add_argument("--consultas", type=Path, help="padrão: o do idioma")
    parser.add_argument("--catalogo", type=Path, help="padrão: o do idioma")
    parser.add_argument("--saida", type=Path, default=RESULTADOS, help="pasta do relatório")
    args = parser.parse_args(argv)
    consultas, catalogo_padrao, sufixo = IDIOMAS[args.idioma]
    args.consultas = args.consultas or consultas
    args.catalogo = args.catalogo or catalogo_padrao

    golden = carregar_golden(args.consultas)
    catalogo = carregar_catalogo(args.catalogo)
    requests = montar_requests(golden)

    if args.de_arquivo:
        resultados = json.loads(args.de_arquivo.read_text(encoding="utf-8"))["results"]
        buscas, origem = 0, f"arquivo `{args.de_arquivo.name}` (reavaliação, sem rede)"
    else:
        resultados = buscar(requests, client)
        buscas, origem = len(requests), "Algolia (Search key)"
        if args.bruto:
            args.bruto.write_text(json.dumps({"results": resultados}, ensure_ascii=False), encoding="utf-8")

    avaliacoes = avaliar(golden, resultados, catalogo)
    quando = datetime.now(UTC)
    args.saida.mkdir(parents=True, exist_ok=True)
    destino = args.saida / f"{quando:%Y-%m-%d}{sufixo}.md"
    nomes = [
        str(p.resolve().relative_to(RAIZ)) if p.resolve().is_relative_to(RAIZ) else p.name
        for p in (args.consultas, args.catalogo)
    ]
    destino.write_text(relatorio(avaliacoes, quando, buscas, origem, *nomes), encoding="utf-8")

    passaram = sum(a["passou"] for a in avaliacoes)
    print(
        f"{passaram} de {len(avaliacoes)} consultas passaram; {buscas} buscas gastas; relatório em {destino}"
    )
    for a in avaliacoes:
        if not a["passou"]:
            print(f"  FALHOU {a['id']}")
    return 0 if passaram == len(avaliacoes) else 1


if __name__ == "__main__":
    sys.exit(main())
