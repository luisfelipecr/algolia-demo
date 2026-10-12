import json
from collections import Counter

import pytest

from sintetico import rodar


@pytest.fixture
def cenario():
    return rodar.carregar_cenario()


def test_cenario_valido_e_toda_busca_declarada(cenario):
    lote = rodar.montar_lote(cenario, 50, "teste")
    assert len(lote) == 50
    for item in lote:
        r = item["request"]
        assert r["analyticsTags"] == ["sintetico"]
        assert r["userToken"].startswith("sintetico-")
        assert r["clickAnalytics"] is True
        assert r["indexName"] in ("produtos_ptbr", "produtos_en")


def test_lote_deterministico_pela_semente(cenario):
    assert rodar.montar_lote(cenario, 11, "2026-10-09T13") == rodar.montar_lote(cenario, 11, "2026-10-09T13")
    assert rodar.montar_lote(cenario, 11, "2026-10-09T13") != rodar.montar_lote(cenario, 11, "2026-10-09T19")


def test_tamanho_vira_filtro_ou_texto_na_lingua_da_loja(cenario):
    lote = [i for s in range(40) for i in rodar.montar_lote(cenario, 50, f"s{s}") if i["tamanho"]]
    filtros = [i for i in lote if i["request"].get("facetFilters")]
    textos = [i for i in lote if not i["request"].get("facetFilters")]
    assert filtros and textos
    for i in filtros:
        assert i["request"]["facetFilters"] == [f"tamanhos_disponiveis:{i['tamanho']}"]
    for i in textos:
        sufixo = f" size {i['tamanho']}" if i["loja"] == "en" else f" {i['tamanho']}"
        assert i["request"]["query"].endswith(sufixo)


def test_pesos_das_lojas_respeitados(cenario):
    lojas = Counter(i["loja"] for s in range(20) for i in rodar.montar_lote(cenario, 50, f"p{s}"))
    assert 0.65 < lojas["pt"] / 1000 < 0.85


def test_limite_de_buscas(cenario):
    with pytest.raises(ValueError):
        rodar.montar_lote(cenario, 0, "x")
    with pytest.raises(ValueError):
        rodar.montar_lote(cenario, rodar.BUSCAS_MAX + 1, "x")


def test_cenario_com_pesos_errados(tmp_path, cenario):
    cenario["lojas"]["pt"]["peso"] = 0.9
    arquivo = tmp_path / "c.json"
    arquivo.write_text(json.dumps(cenario), encoding="utf-8")
    with pytest.raises(ValueError, match="somam"):
        rodar.carregar_cenario(arquivo)


def test_conferir_chave():
    assert (
        rodar.conferir_chave({"acl": ["search"], "queryParameters": "analyticsTags=sintetico"}, "sintetico")
        == []
    )
    codificada = "analyticsTags=%5B%22sintetico%22%5D&hitsPerPage=24"
    assert rodar.conferir_chave({"acl": ["search"], "queryParameters": codificada}, "sintetico") == []
    parecida = rodar.conferir_chave(
        {"acl": ["search"], "queryParameters": "analyticsTags=nao-sintetico"}, "sintetico"
    )
    assert len(parecida) == 1
    sem_tag = rodar.conferir_chave({"acl": ["search"], "queryParameters": ""}, "sintetico")
    assert len(sem_tag) == 1 and "analyticsTags" in sem_tag[0]
    demais = rodar.conferir_chave(
        {"acl": ["search", "browse", "addObject"], "queryParameters": "analyticsTags=sintetico"}, "sintetico"
    )
    assert len(demais) == 1 and "addObject" in demais[0] and "browse" in demais[0]


class _Resposta:
    def __init__(self, dados):
        self.raw_data = json.dumps(dados)


class _Busca:
    def __init__(self):
        self.pedidos = []

    def search_with_http_info(self, corpo):
        self.pedidos.append(corpo)
        resultados = []
        for i, r in enumerate(corpo["requests"]):
            vazio = i % 3 == 0
            hits = [] if vazio else [{"objectID": f"{i}-{p}"} for p in range(5)]
            resultados.append(
                {
                    "index": r["indexName"],
                    "hits": hits,
                    "nbHits": len(hits),
                    "queryID": f"q{i}",
                    "page": 0,
                    "hitsPerPage": 24,
                }
            )
        return _Resposta({"results": resultados})


class _Insights:
    def __init__(self):
        self.eventos = []

    def push_events_with_http_info(self, corpo):
        self.eventos.extend(corpo["events"])


def test_enviar_uma_multi_query_e_cliques_validos(cenario):
    busca, insights = _Busca(), _Insights()
    lote = rodar.montar_lote(cenario, 30, "envio")
    resumo = rodar.enviar(lote, cenario, "envio", clientes=(busca, insights))
    assert len(busca.pedidos) == 1 and len(busca.pedidos[0]["requests"]) == 30
    assert resumo["buscas"] == 30 and resumo["sem_resultado"] == 10
    assert resumo["cliques"] == len(insights.eventos) > 0
    for e in insights.eventos:
        indice = int(e["queryID"][1:])
        assert indice % 3 != 0  # só clica em busca com resultado
        assert e["eventName"] == "Produto clicado (sintetico)"
        assert e["userToken"].startswith("sintetico-")
        assert 1 <= e["positions"][0] <= 5
        assert e["objectIDs"] == [f"{indice}-{e['positions'][0] - 1}"]


def test_ensaio_nao_envia(capsys):
    assert rodar.main(["--buscas", "5", "--semente", "x"], clientes=(None, None)) == 0
    saida = capsys.readouterr().out
    assert "nada foi enviado" in saida and saida.count("sintetico-") == 5


def test_chave_dedicada_recusa_write_key(monkeypatch):
    monkeypatch.setattr("ingest.indexar.carregar_env", lambda: None)
    monkeypatch.setenv("ALGOLIA_APP_ID", "APP")
    monkeypatch.setenv("ALGOLIA_WRITE_API_KEY", "mesma")
    monkeypatch.setenv("ALGOLIA_SINTETICO_KEY", "mesma")
    with pytest.raises(SystemExit, match="Write key"):
        rodar._chave_dedicada()
    monkeypatch.delenv("ALGOLIA_SINTETICO_KEY")
    with pytest.raises(SystemExit, match="faltam"):
        rodar._chave_dedicada()


def test_nome_do_evento_aceito_pela_insights_api():
    # a API recusa eventName fora de ASCII visível ou com mais de 64 caracteres (visto em 12/10/2026)
    nome = rodar.NOME_DO_CLIQUE
    assert 1 <= len(nome) <= 64 and all(32 <= ord(c) < 127 for c in nome)
