"""Executor do golden set, sem rede: client falso que conta as chamadas."""

import json

import pytest

from evals.avaliador import OPERADORES, avaliar_expectativa
from evals.rodar import CONSULTAS, IDIOMAS, carregar_golden, main, montar_requests

TIPOS = {
    "nb_hits",
    "nb_hits_catalogo",
    "recall_catalogo",
    "todos",
    "algum",
    "nenhum",
    "ordenado",
    "invariante",
}


class RespostaFalsa:
    def __init__(self, raw_data: str):
        self.raw_data = raw_data


class ClientFalso:
    """Só tem `search_with_http_info`: qualquer outra chamada (escrita, browse) quebra o teste."""

    def __init__(self, por_consulta):
        self.por_consulta = por_consulta
        self.chamadas = []

    def search_with_http_info(self, params):
        self.chamadas.append(params)
        results = [
            {"index": r["indexName"], "query": r["query"], **self.por_consulta(r)} for r in params["requests"]
        ]
        return RespostaFalsa(json.dumps({"results": results}))


def _condicoes(cond):
    yield cond
    for chave in ("qualquer", "todas"):
        for c in cond.get(chave, []):
            yield from _condicoes(c)
    if "nao" in cond:
        yield from _condicoes(cond["nao"])


# tamanho esperado de cada golden set: o pt cobre o catálogo; o en, o que muda com o idioma
TAMANHOS = {"pt": (25, 40), "en": (10, 20)}


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_golden_set_bem_formado(idioma):
    golden = carregar_golden(IDIOMAS[idioma][0])
    consultas = golden["consultas"]
    minimo, maximo = TAMANHOS[idioma]
    assert minimo <= len(consultas) <= maximo
    assert len({c["id"] for c in consultas}) == len(consultas)
    for caso in consultas:
        assert caso["nota"], caso["id"]
        assert caso["expectativas"], caso["id"]
        for exp in caso["expectativas"]:
            assert exp["tipo"] in TIPOS, caso["id"]
            for chave in ("condicao", "regra"):
                if chave in exp:
                    for c in _condicoes(exp[chave]):
                        if "op" in c:
                            assert c["op"] in OPERADORES, (caso["id"], c)


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_recall_pede_pagina_cheia(idioma):
    """Recall só é conferível com a página cobrindo nbHits; sem isso a falha diria 'página curta'."""
    golden = carregar_golden(IDIOMAS[idioma][0])
    for caso, request in zip(golden["consultas"], montar_requests(golden), strict=True):
        if any(e["tipo"] == "recall_catalogo" for e in caso["expectativas"]):
            assert request["hitsPerPage"] == 1000, caso["id"]


def test_golden_set_cobre_os_casos_pedidos():
    consultas = {c["consulta"] for c in carregar_golden()["consultas"]}
    for obrigatoria in (
        "tenis",
        "calca",
        "bolsas",
        "camisetas",
        "tenix",
        "jaqeta",
        "sneaker",
        "hoodie",
        "puffer",
        "bolsa vermelha",
        "camiseta preta",
        "tênis feminino",
        "cinto promoção",
        "sapatênis",
        "michael kors",
        "",
    ):
        assert obrigatoria in consultas


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_golden_set_avaliavel_sem_erro(idioma):
    """Toda expectativa roda (sem ValueError) contra uma resposta e um catálogo mínimos."""
    catalogo = [{"objectID": "1", "nome": "Tênis", "categoria": "Tênis", "categorias": {"lvl0": "Feminino"}}]
    for caso in carregar_golden(IDIOMAS[idioma][0])["consultas"]:
        for exp in caso["expectativas"]:
            avaliar_expectativa(exp, {"hits": catalogo, "nbHits": 1}, catalogo)


def test_requests_herdam_parametros_comuns_e_nao_alimentam_analytics():
    golden = carregar_golden()
    requests = montar_requests(golden)
    assert len(requests) == len(golden["consultas"])
    for r in requests:
        assert r["analytics"] is False
        assert r["indexName"].startswith("produtos_ptbr")
        assert r["hitsPerPage"] <= 1000
    por_id = dict(zip((c["id"] for c in golden["consultas"]), requests, strict=True))
    assert por_id["replica-jaqueta-preco-asc"]["indexName"] == "produtos_ptbr_preco_asc"
    assert por_id["tamanho-tenis-38"]["facetFilters"] == ["tamanhos_disponiveis:38"]
    assert por_id["tamanho-tenis-38"]["attributesToRetrieve"]  # herdado


MINI = {
    "indice_padrao": "produtos_ptbr",
    "parametros_comuns": {"hitsPerPage": 20, "analytics": False},
    "consultas": [
        {
            "id": "promo",
            "consulta": "cinto promoção",
            "nota": "Rule de promoção",
            "expectativas": [
                {"tipo": "todos", "condicao": {"campo": "em_promocao", "op": "igual", "valor": True}}
            ],
        },
        {
            "id": "zero",
            "consulta": "sapatênis",
            "nota": "sem resultado",
            "achado": "diagnóstico de teste",
            "expectativas": [{"tipo": "nb_hits", "igual": 0}],
        },
    ],
}


@pytest.fixture
def arquivos(tmp_path):
    golden = tmp_path / "consultas.json"
    golden.write_text(json.dumps(MINI), encoding="utf-8")
    catalogo = tmp_path / "registros.json"
    catalogo.write_text("[]", encoding="utf-8")
    return golden, catalogo, tmp_path / "resultados"


def _args(arquivos, *extra):
    golden, catalogo, saida = arquivos
    return ["--consultas", str(golden), "--catalogo", str(catalogo), "--saida", str(saida), *extra]


def test_uma_unica_chamada_e_sucesso(arquivos):
    client = ClientFalso(
        lambda r: (
            {"hits": [{"objectID": "1", "em_promocao": True}], "nbHits": 1}
            if r["query"] == "cinto promoção"
            else {"hits": [], "nbHits": 0}
        )
    )
    assert main(_args(arquivos), client=client) == 0
    assert len(client.chamadas) == 1
    assert [r["query"] for r in client.chamadas[0]["requests"]] == ["cinto promoção", "sapatênis"]
    relatorio = next(arquivos[2].glob("*.md")).read_text(encoding="utf-8")
    assert "2 de 2 consultas passaram" in relatorio
    assert "Buscas gastas da cota nesta execução: 2" in relatorio
    assert "Achados registrados que já passam" in relatorio  # o achado de "zero" precisa ser revisto


def test_violacao_reprova_e_vai_para_o_relatorio(arquivos):
    """Um hit fora de promoção na busca com Rule TEM de falhar, com o motivo no relatório."""
    client = ClientFalso(
        lambda r: {"hits": [{"objectID": "9", "nome": "Cinto X", "em_promocao": False}], "nbHits": 1}
    )
    assert main(_args(arquivos), client=client) == 1
    relatorio = next(arquivos[2].glob("*.md")).read_text(encoding="utf-8")
    assert "0 de 2 consultas passaram" in relatorio
    assert "**FALHOU**" in relatorio
    assert "9 «Cinto X»" in relatorio
    assert "diagnóstico de teste" in relatorio


def test_reavaliar_de_arquivo_nao_usa_rede(arquivos, tmp_path):
    bruto = tmp_path / "bruto.json"
    client = ClientFalso(lambda r: {"hits": [{"objectID": "1", "em_promocao": True}], "nbHits": 0})
    main(_args(arquivos, "--bruto", str(bruto)), client=client)

    class SemRede:
        def search_with_http_info(self, params):
            raise AssertionError("não deveria buscar")

    assert main(_args(arquivos, "--de-arquivo", str(bruto)), client=SemRede()) == 0
    relatorio = next(arquivos[2].glob("*.md")).read_text(encoding="utf-8")
    assert "Buscas gastas da cota nesta execução: 0" in relatorio


def test_consultas_padrao_existe():
    assert CONSULTAS.exists()
