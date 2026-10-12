"""Tráfego sintético e declarado para o analytics da demo: buscas e cliques inventados, nunca de cliente.

    uv run python -m sintetico.rodar                    # ensaio: mostra o lote e o custo, sem rede
    uv run python -m sintetico.rodar --aplicar          # envia: 1 multi-query (N buscas da cota) + cliques
    uv run python -m sintetico.rodar --buscas 20 --semente 2026-10-09T13

Por que existe: o plano Free guarda só 7 dias de analytics, e uma loja de demo quase não tem visita; sem
volume, o copiloto do merchandiser responde "sem dado". O cenário (`cenario.json`) é escrito à mão a partir do
catálogo e diz a intenção de cada consulta (ruptura de grade, demanda sem oferta, candidata a sinônimo).

Como fica declarado:
- toda busca vai com `analyticsTags: ["sintetico"]`, e a chave própria (ALGOLIA_SINTETICO_KEY) tem de impor
  essa tag nos `queryParameters`: o script confere a chave antes de enviar e recusa a Write e a Search padrão;
- `userToken` = `sintetico-NN`; os cliques vão para a Insights API com o nome
  "Produto clicado (sintetico)" (a API só aceita ASCII visível, até 64 caracteres, no eventName);
- o copiloto separa real × sintético pela tag.

Custo: cada consulta do multi-query conta como 1 busca da cota de 10K/mês; Insights não conta. O padrão (11
buscas, 4 vezes ao dia) dá cerca de 1.340 buscas por mês.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import sys
from pathlib import Path
from urllib.parse import parse_qs

PASTA = Path(__file__).resolve().parent
CENARIO = PASTA / "cenario.json"
BUSCAS_PADRAO = 11
BUSCAS_MAX = 50
ACL_PERMITIDA = {"search"}
NOME_DO_CLIQUE = "Produto clicado (sintetico)"  # a Insights API recusa acento no eventName


def carregar_cenario(caminho: Path = CENARIO) -> dict:
    cenario = json.loads(caminho.read_text(encoding="utf-8"))
    soma = sum(loja["peso"] for loja in cenario["lojas"].values())
    if abs(soma - 1) > 1e-9:
        raise ValueError(f"os pesos das lojas somam {soma}, não 1")
    if abs(sum(cenario["modo_do_tamanho"].values()) - 1) > 1e-9:
        raise ValueError("modo_do_tamanho tem de somar 1")
    for nome, loja in cenario["lojas"].items():
        vistas = [c["consulta"] for c in loja["consultas"]]
        if len(vistas) != len(set(vistas)):
            raise ValueError(f"consulta repetida na loja {nome}")
    return cenario


def semente_padrao(agora: dt.datetime | None = None) -> str:
    """Uma semente por hora (UTC): rodar de novo na mesma hora repete o mesmo lote."""
    agora = agora or dt.datetime.now(dt.UTC)
    return f"{agora:%Y-%m-%dT%H}"


def montar_lote(cenario: dict, n: int, semente: str) -> list[dict]:
    """As N buscas do lote, sorteadas pelos pesos do cenário. Cada item: loja, request e intenção."""
    if not 1 <= n <= BUSCAS_MAX:
        raise ValueError(f"buscas por lote: de 1 a {BUSCAS_MAX}")
    sorteio = random.Random(semente)
    nomes = list(cenario["lojas"])
    lote = []
    for _ in range(n):
        nome = sorteio.choices(nomes, weights=[cenario["lojas"][x]["peso"] for x in nomes])[0]
        loja = cenario["lojas"][nome]
        caso = sorteio.choices(loja["consultas"], weights=[c["peso"] for c in loja["consultas"]])[0]
        consulta, filtros, tamanho = caso["consulta"], [], None
        if caso.get("tamanhos"):
            modos = cenario["modo_do_tamanho"]
            modo = sorteio.choices(list(modos), weights=list(modos.values()))[0]
            if modo != "nenhum":
                tamanhos = caso["tamanhos"]
                tamanho = sorteio.choices(list(tamanhos), weights=list(tamanhos.values()))[0]
                if modo == "filtro":
                    filtros = [f"tamanhos_disponiveis:{tamanho}"]
                else:
                    consulta = loja["tamanho_no_texto"].format(consulta=consulta, tamanho=tamanho)
        usuario = f"{cenario['tag']}-{sorteio.randrange(1, cenario['usuarios'] + 1):02d}"
        request = {
            "indexName": loja["indice"],
            "query": consulta,
            "analyticsTags": [cenario["tag"]],
            "clickAnalytics": True,
            "userToken": usuario,
            "hitsPerPage": 24,  # o mesmo da loja
            "attributesToRetrieve": ["objectID"],
            "attributesToHighlight": [],
        }
        if filtros:
            request["facetFilters"] = filtros
        lote.append(
            {"loja": nome, "request": request, "intencao": caso.get("intencao", ""), "tamanho": tamanho}
        )
    return lote


def cliques(lote: list[dict], resultados: list[dict], cenario: dict, semente: str) -> list[dict]:
    """Eventos de clique para parte das buscas com resultado, na posição sorteada com peso 1/posição."""
    sorteio = random.Random(f"{semente}-cliques")
    eventos = []
    for item, resultado in zip(lote, resultados, strict=True):
        hits = resultado.get("hits") or []
        if not hits or not resultado.get("queryID") or sorteio.random() >= cenario["taxa_de_clique"]:
            continue
        posicoes = list(range(1, len(hits) + 1))
        posicao = sorteio.choices(posicoes, weights=[1 / p for p in posicoes])[0]
        eventos.append(
            {
                "eventType": "click",
                "eventName": NOME_DO_CLIQUE,
                "index": item["request"]["indexName"],
                "userToken": item["request"]["userToken"],
                "queryID": resultado["queryID"],
                "objectIDs": [hits[posicao - 1]["objectID"]],
                "positions": [posicao + resultado.get("page", 0) * resultado.get("hitsPerPage", 24)],
            }
        )
    return eventos


def conferir_chave(info: dict, tag: str) -> list[str]:
    """Problemas da chave (vazio = pode usar): só `search` e a tag imposta nos queryParameters."""
    problemas = []
    sobra = set(info.get("acl") or []) - ACL_PERMITIDA
    if sobra:
        problemas.append(f"a chave tem permissões demais ({', '.join(sorted(sobra))}); use uma só com search")
    impostos = parse_qs(info.get("queryParameters") or "")
    tags = set()
    for valor in impostos.get("analyticsTags", []):  # "sintetico", "a,b" ou '["sintetico"]'
        try:
            lista = json.loads(valor)
        except ValueError:
            lista = valor.split(",")
        tags.update(str(x).strip() for x in (lista if isinstance(lista, list) else [lista]))
    if tag not in tags:
        problemas.append(f"a chave não impõe analyticsTags={tag} nos queryParameters")
    return problemas


def _chave_dedicada() -> str:
    from ingest.indexar import carregar_env

    carregar_env()
    chave = os.environ.get("ALGOLIA_SINTETICO_KEY", "")
    if not chave or not os.environ.get("ALGOLIA_APP_ID"):
        raise SystemExit("faltam ALGOLIA_APP_ID e ALGOLIA_SINTETICO_KEY (chave própria, criada no dashboard)")
    outras = {os.environ.get(v) for v in ("ALGOLIA_WRITE_API_KEY", "ALGOLIA_SEARCH_API_KEY")} - {None, ""}
    if chave in outras:
        raise SystemExit("ALGOLIA_SINTETICO_KEY não pode ser a Write key nem a Search key padrão")
    return chave


def enviar(lote: list[dict], cenario: dict, semente: str, clientes=None) -> dict:
    """Confere a chave, faz 1 multi-query e manda os cliques. `clientes` = (busca, insights) nos testes."""
    if clientes is None:
        from algoliasearch.insights.client import InsightsClientSync
        from algoliasearch.search.client import SearchClientSync

        chave = _chave_dedicada()
        app_id = os.environ["ALGOLIA_APP_ID"]
        busca, insights = SearchClientSync(app_id, chave), InsightsClientSync(app_id, chave)
        info = json.loads(busca.get_api_key_with_http_info(chave).raw_data)
        problemas = conferir_chave(info, cenario["tag"])
        if problemas:
            raise SystemExit("chave recusada: " + "; ".join(problemas))
    else:
        busca, insights = clientes
    resposta = busca.search_with_http_info({"requests": [i["request"] for i in lote], "strategy": "none"})
    resultados = json.loads(resposta.raw_data)["results"]
    if len(resultados) != len(lote):
        raise RuntimeError(f"a Algolia devolveu {len(resultados)} resultados para {len(lote)} buscas")
    eventos = cliques(lote, resultados, cenario, semente)
    if eventos:
        insights.push_events_with_http_info({"events": eventos})
    return {
        "buscas": len(lote),
        "sem_resultado": sum(1 for r in resultados if not r.get("nbHits")),
        "cliques": len(eventos),
    }


def main(argv: list[str] | None = None, clientes=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--aplicar", action="store_true", help="envia de verdade (gasta N buscas da cota)")
    parser.add_argument(
        "--buscas", type=int, default=BUSCAS_PADRAO, help=f"buscas no lote (1 a {BUSCAS_MAX})"
    )
    parser.add_argument("--semente", default="", help="padrão: a hora atual em UTC (AAAA-MM-DDTHH)")
    parser.add_argument("--cenario", type=Path, default=CENARIO)
    args = parser.parse_args(argv)

    cenario = carregar_cenario(args.cenario)
    semente = args.semente or semente_padrao()
    lote = montar_lote(cenario, args.buscas, semente)
    for item in lote:
        r = item["request"]
        filtro = f" [{r['facetFilters'][0]}]" if r.get("facetFilters") else ""
        print(f"{item['loja']}  {r['userToken']}  {r['query']}{filtro}  ({item['intencao']})")
    if not args.aplicar:
        print(f"ensaio: {len(lote)} buscas da cota se aplicado (semente {semente}); nada foi enviado")
        return 0
    resumo = enviar(lote, cenario, semente, clientes)
    print(
        f"enviado: {resumo['buscas']} buscas ({resumo['sem_resultado']} sem resultado), "
        f"{resumo['cliques']} cliques; tag {cenario['tag']}, semente {semente}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
