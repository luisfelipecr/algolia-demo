"""Avaliador do golden set: toda expectativa tem de passar quando atendida e FALHAR quando violada."""

import pytest

from evals.avaliador import avaliar_consulta, avaliar_expectativa, condicao_ok, normalizar, valor_campo

TENIS = {
    "qualquer": [
        {"campo": "categoria", "op": "igual", "valor": "Tênis"},
        {"campo": "nome", "op": "contem_palavra", "valor": "tênis"},
    ]
}


def hit(object_id: str, **campos) -> dict:
    base = {
        "objectID": object_id,
        "nome": "Produto",
        "categoria": "Outros",
        "categorias": {"lvl0": "Feminino"},
        "preco": 100.0,
        "preco_de": 100.0,
        "em_promocao": False,
        "em_estoque": True,
        "tamanhos_disponiveis": ["38"],
        "grade": ["37", "38"],
    }
    return {**base, **campos}


def resposta(*hits, nb: int | None = None) -> dict:
    return {"hits": list(hits), "nbHits": len(hits) if nb is None else nb}


def test_normalizar_tira_acento_e_caixa():
    assert normalizar("Tênis Calça ÓCULOS") == "tenis calca oculos"


def test_contem_palavra_nao_casa_substring():
    """'sapatênis' não é 'tênis': a palavra tem de ser inteira (o erro de 11 pontos das lições)."""
    assert condicao_ok(hit("1", nome="Tênis Hogan"), TENIS)
    assert not condicao_ok(hit("2", nome="Sapatênis Hogan"), TENIS)
    assert condicao_ok(hit("3", nome="tenis sem acento"), TENIS)


def test_campo_ausente_nao_satisfaz_condicao():
    assert not condicao_ok({"objectID": "1"}, {"campo": "preco", "op": "menor_igual", "valor": 300})
    assert not condicao_ok({"objectID": "1"}, {"campo": "avaliacao_bayes", "op": "presente"})
    assert condicao_ok(
        {"objectID": "1", "avaliacao_bayes": 4.1}, {"campo": "avaliacao_bayes", "op": "presente"}
    )


def test_campo_aninhado_e_pesquisavel():
    h = hit("1", nome="Bolsa", marca="Guess", categorias={"lvl0": "Feminino", "lvl1": "Feminino > Bolsas"})
    assert valor_campo(h, "categorias.lvl1") == "Feminino > Bolsas"
    assert "Guess" in valor_campo(h, "_pesquisavel")
    assert "Feminino > Bolsas" in valor_campo(h, "_pesquisavel")


def test_operador_desconhecido_explode_em_vez_de_passar():
    with pytest.raises(ValueError):
        condicao_ok(hit("1"), {"campo": "nome", "op": "parecido", "valor": "x"})


@pytest.mark.parametrize(
    ("exp", "nb", "esperado"),
    [
        ({"tipo": "nb_hits", "igual": 0}, 0, True),
        ({"tipo": "nb_hits", "igual": 0}, 3, False),
        ({"tipo": "nb_hits", "min": 5}, 4, False),
        ({"tipo": "nb_hits", "min": 5, "max": 10}, 7, True),
        ({"tipo": "nb_hits", "max": 10}, 11, False),
    ],
)
def test_nb_hits(exp, nb, esperado):
    assert avaliar_expectativa(exp, {"hits": [], "nbHits": nb}, None)[0] is esperado


def test_todos_passa_e_falha_nomeando_quem_violou():
    exp = {"tipo": "todos", "condicao": TENIS}
    assert avaliar_expectativa(exp, resposta(hit("1", nome="Tênis A"), hit("2", categoria="Tênis")), None)[0]
    ok, motivo = avaliar_expectativa(
        exp, resposta(hit("1", nome="Tênis A"), hit("2", nome="Sapatênis B")), None
    )
    assert not ok
    assert "2 «Sapatênis B»" in motivo


def test_todos_respeita_primeiros():
    exp = {"tipo": "todos", "primeiros": 1, "condicao": TENIS}
    assert avaliar_expectativa(exp, resposta(hit("1", nome="Tênis A"), hit("2", nome="Bolsa")), None)[0]


def test_todos_e_algum_falham_sem_hits():
    """Verde vazio não prova nada: zero hits reprova `todos`, salvo permissão explícita."""
    assert not avaliar_expectativa({"tipo": "todos", "condicao": TENIS}, resposta(), None)[0]
    assert not avaliar_expectativa({"tipo": "algum", "condicao": TENIS}, resposta(), None)[0]
    assert avaliar_expectativa(
        {"tipo": "todos", "condicao": TENIS, "permitir_vazio": True}, resposta(), None
    )[0]


def test_algum():
    exp = {
        "tipo": "algum",
        "primeiros": 2,
        "condicao": {"campo": "grupo_cor", "op": "igual", "valor": "vermelho"},
    }
    sim = resposta(hit("1", grupo_cor="preto"), hit("2", grupo_cor="vermelho"))
    nao = resposta(hit("1", grupo_cor="preto"), hit("2", grupo_cor="azul"), hit("3", grupo_cor="vermelho"))
    assert avaliar_expectativa(exp, sim, None)[0]
    assert not avaliar_expectativa(exp, nao, None)[0]


def test_nenhum():
    exp = {"tipo": "nenhum", "condicao": TENIS}
    assert avaliar_expectativa(exp, resposta(), None)[0]
    assert avaliar_expectativa(exp, resposta(hit("1", nome="Sapatênis")), None)[0]
    ok, motivo = avaliar_expectativa(
        exp, resposta(hit("1", nome="Sapato"), hit("2", categoria="Tênis")), None
    )
    assert not ok and "2 «Produto»" in motivo


def test_nenhum_campo_presente_pega_atributo_que_vazou():
    exp = {"tipo": "nenhum", "condicao": {"campo": "avaliacao_bayes", "op": "presente"}}
    assert avaliar_expectativa(exp, resposta(hit("1")), None)[0]
    assert not avaliar_expectativa(exp, resposta(hit("1", avaliacao_bayes=4.2)), None)[0]


CATALOGO = [
    hit("t1", categoria="Tênis"),
    hit("t2", categoria="Tênis"),
    hit("b1", categoria="Bolsas"),
]


def test_recall_catalogo_passa_com_todos_e_falha_listando_os_que_faltam():
    exp = {"tipo": "recall_catalogo", "regra": {"campo": "categoria", "op": "igual", "valor": "Tênis"}}
    assert avaliar_expectativa(exp, resposta(hit("t1"), hit("t2"), hit("b1")), CATALOGO)[0]
    ok, motivo = avaliar_expectativa(exp, resposta(hit("t1"), hit("b1")), CATALOGO)
    assert not ok and "faltam 1 de 2" in motivo and "t2" in motivo


def test_recall_falha_se_a_pagina_nao_cobre_nbhits():
    exp = {"tipo": "recall_catalogo", "regra": {"campo": "categoria", "op": "igual", "valor": "Tênis"}}
    ok, motivo = avaliar_expectativa(exp, resposta(hit("t1"), hit("t2"), nb=50), CATALOGO)
    assert not ok and "hitsPerPage" in motivo


def test_recall_falha_se_nbhits_menor_que_o_catalogo_mesmo_com_pagina_curta():
    exp = {"tipo": "recall_catalogo", "regra": {"campo": "categoria", "op": "igual", "valor": "Tênis"}}
    ok, motivo = avaliar_expectativa(exp, resposta(hit("t1"), nb=1), CATALOGO)
    assert not ok and "faltam pelo menos 1" in motivo


def test_recall_com_regra_vazia_no_catalogo_falha():
    exp = {"tipo": "recall_catalogo", "regra": {"campo": "categoria", "op": "igual", "valor": "Sapatênis"}}
    assert not avaliar_expectativa(exp, resposta(hit("t1")), CATALOGO)[0]


def test_nb_hits_catalogo_igual_e_min():
    regra = {"campo": "categoria", "op": "igual", "valor": "Tênis"}
    igual = {"tipo": "nb_hits_catalogo", "comparacao": "igual", "regra": regra}
    minimo = {"tipo": "nb_hits_catalogo", "comparacao": "min", "regra": regra}
    assert avaliar_expectativa(igual, {"hits": [], "nbHits": 2}, CATALOGO)[0]
    assert not avaliar_expectativa(igual, {"hits": [], "nbHits": 3}, CATALOGO)[0]
    assert avaliar_expectativa(minimo, {"hits": [], "nbHits": 3}, CATALOGO)[0]
    assert not avaliar_expectativa(minimo, {"hits": [], "nbHits": 1}, CATALOGO)[0]
    tudo = {"tipo": "nb_hits_catalogo", "comparacao": "igual", "regra": {"todas": []}}
    assert avaliar_expectativa(tudo, {"hits": [], "nbHits": 3}, CATALOGO)[0]


def test_expectativa_de_catalogo_sem_catalogo_explode():
    with pytest.raises(ValueError):
        avaliar_expectativa({"tipo": "recall_catalogo", "regra": {"todas": []}}, resposta(), None)


@pytest.mark.parametrize(
    ("precos", "sentido", "esperado"),
    [
        ([100, 100, 200], "asc", True),
        ([100, 300, 200], "asc", False),
        ([300, 200, 200], "desc", True),
        ([300, 100, 200], "desc", False),
    ],
)
def test_ordenado(precos, sentido, esperado):
    hits = [hit(str(i), preco=p) for i, p in enumerate(precos)]
    exp = {"tipo": "ordenado", "campo": "preco", "sentido": sentido}
    assert avaliar_expectativa(exp, resposta(*hits), None)[0] is esperado


def test_ordenado_falha_com_um_hit_ou_campo_ausente():
    exp = {"tipo": "ordenado", "campo": "preco", "sentido": "asc"}
    assert not avaliar_expectativa(exp, resposta(hit("1")), None)[0]
    sem_preco = {"objectID": "2", "nome": "x"}
    assert not avaliar_expectativa(exp, resposta(hit("1"), sem_preco), None)[0]


@pytest.mark.parametrize(
    ("nome", "bom", "ruim"),
    [
        ("estoque_coerente", hit("1"), hit("1", tamanhos_disponiveis=[], em_estoque=True)),
        ("promocao_coerente", hit("1", preco=80.0, em_promocao=True), hit("1", preco=80.0)),
        ("tamanhos_na_grade", hit("1"), hit("1", tamanhos_disponiveis=["44"])),
    ],
)
def test_invariantes(nome, bom, ruim):
    exp = {"tipo": "invariante", "nome": nome}
    assert avaliar_expectativa(exp, resposta(bom), None)[0]
    assert not avaliar_expectativa(exp, resposta(bom, ruim), None)[0]


def test_invariante_com_campo_faltando_falha():
    exp = {"tipo": "invariante", "nome": "estoque_coerente"}
    assert not avaliar_expectativa(exp, resposta({"objectID": "1"}), None)[0]


def test_tipo_desconhecido_explode():
    with pytest.raises(ValueError):
        avaliar_expectativa({"tipo": "parecido"}, resposta(), None)


def test_consulta_so_passa_se_todas_as_expectativas_passam():
    caso = {
        "id": "x",
        "expectativas": [
            {"tipo": "nb_hits", "min": 1},
            {"tipo": "todos", "condicao": {"campo": "em_promocao", "op": "igual", "valor": True}},
        ],
    }
    boa = avaliar_consulta(caso, resposta(hit("1", em_promocao=True)), None)
    ruim = avaliar_consulta(caso, resposta(hit("1", em_promocao=True), hit("2")), None)
    assert boa["passou"]
    assert not ruim["passou"]
    assert [d["passou"] for d in ruim["detalhes"]] == [True, False]
