import json
from decimal import Decimal
from pathlib import Path

import pytest

from catalog.glossario import cor_en
from catalog.grade import conversor, ordem
from catalog.precos import para_reais, preco_de_venda
from catalog.traducao import Memoria
from catalog.vtex import Catalogo, quantidade_sintetica, slug, texto_en

AMOSTRA = json.loads((Path(__file__).parent / "fixtures" / "amostra_origem.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def produtos() -> dict[str, dict]:
    catalogo = Catalogo(list(AMOSTRA.values()), Memoria.carregar())
    return {p["productReferenceCode"]: p for p in catalogo.produtos()}


def _produto(produtos, caso):
    return produtos[AMOSTRA[caso]["objectID"]]


def _grade(produto):
    return [i["Tamanho"][0] for i in produto["items"]]


# preço


def test_preco_de_vitrine_termina_em_90():
    assert para_reais(100, Decimal("5.5867")) == Decimal("558.90")
    assert para_reais(Decimal("22.5"), Decimal("5.5867")) == Decimal("125.90")


def test_preco_com_desconto_recalculado_em_reais():
    assert preco_de_venda(Decimal("572.90"), 10) == Decimal("515.90")
    assert preco_de_venda(Decimal("572.90"), 0) == Decimal("572.90")


def test_cambio_zero_falha():
    with pytest.raises(ValueError):
        para_reais(10, Decimal("0"))


# grade


def test_calcado_eu_feminino_junta_meio_numero_e_corta_faixa():
    f = conversor(["34", "34.5", "38", "38.5", "46"], "Women > Shoes > Sneakers", "feminino")
    assert f("34") == "33"
    assert f("38") == f("38.5") == "37"
    assert f("46") is None


def test_calcado_eu_masculino():
    f = conversor(["34", "42", "46"], "Men > Shoes > Sneakers", "masculino")
    assert f("34") is None
    assert f("42") == "40"
    assert f("46") == "44"


def test_calcado_us_pela_tabela_nike_brasil():
    grade = ["5", "5.5", "9", "13"]
    assert conversor(grade, "Men > Shoes > Sneakers", "masculino")("9") == "40"
    assert conversor(grade, "Women > Shoes > Pumps", "feminino")("9") == "39"
    assert conversor(grade, "Women > Shoes > Pumps", "feminino")("5.5") is None


def test_letras_e_italiana():
    f = conversor(
        ["XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL"], "Women > Clothing > T-shirts", "feminino"
    )
    assert [f(t) for t in ["XXS", "XS", "M", "XXL", "XXXL"]] == [None, "PP", "M", "XGG", None]
    g = conversor([str(n) for n in range(8)], "Men > Clothing > Jackets", "masculino")
    assert [g("0"), g("5"), g("6")] == ["PP", "XGG", None]


def test_ordem_da_grade_br():
    assert sorted(["G", "PP", "M"], key=ordem) == ["PP", "M", "G"]
    assert sorted(["40", "U", "36"], key=ordem) == ["36", "40", "U"]


@pytest.mark.parametrize("caso", AMOSTRA)
def test_toda_grade_da_amostra_converte(caso, produtos):
    assert _grade(_produto(produtos, caso)), caso


def test_one_size_repetido_vira_um_sku_unico(produtos):
    assert _grade(_produto(produtos, "one_size_repetido")) == ["U"]


def test_grade_br_esperada(produtos):
    assert _grade(_produto(produtos, "tenis_eu_masc")) == [str(n) for n in range(37, 45)]
    assert _grade(_produto(produtos, "roupa_letras")) == ["PP", "P", "M", "G", "GG", "XGG"]
    assert _grade(_produto(produtos, "roupa_num_fem"))[0] == "36"
    assert _grade(_produto(produtos, "jeans"))[0] == "36"
    assert _grade(_produto(produtos, "camisa_colarinho"))[0] == "37"
    assert _grade(_produto(produtos, "cinto"))[0] == "70"


# formato VTEX


def test_produto_no_formato_da_legacy_search_api(produtos):
    p = _produto(produtos, "tenis_eu_masc")
    for campo in ["productId", "productName", "brand", "linkText", "productReference", "categories", "items"]:
        assert campo in p
    assert p["categories"] == ["/Masculino/Calçados/Tênis/", "/Masculino/Calçados/", "/Masculino/"]
    assert p["productReference"] == AMOSTRA["tenis_eu_masc"]["parentID"]
    item = p["items"][0]
    assert item["variations"] == ["Cor", "Tamanho"]
    oferta = item["sellers"][0]["commertialOffer"]
    assert set(oferta) >= {"Price", "ListPrice", "AvailableQuantity", "IsAvailable"}


def test_nome_traduzido_termina_com_a_cor_do_record(produtos):
    p = _produto(produtos, "tenis_eu_masc")
    assert p["productName"] == "Tênis “101H” Springa multicolorido"
    assert p["items"][0]["Cor"] == ["multicolorido"]


def test_sem_cor_nao_acrescenta_nada(produtos):
    p = _produto(produtos, "sem_cor")
    assert not p["productName"].endswith(" ")
    assert p["items"][0]["Cor"] == [""]


def test_estoque_segue_o_booleano_da_origem(produtos):
    origem = AMOSTRA["tenis_eu_masc"]
    tem_estoque_na_origem = any(v["in_stock"] for v in origem["variants"])
    disponiveis = [
        i
        for i in _produto(produtos, "tenis_eu_masc")["items"]
        if i["sellers"][0]["commertialOffer"]["IsAvailable"]
    ]
    assert bool(disponiveis) == tem_estoque_na_origem
    assert quantidade_sintetica("X", False) == 0
    assert 1 <= quantidade_sintetica("X", True) <= 12


def test_promocao_preco_menor_que_preco_de(produtos):
    promo = [p for p in produtos.values() if AMOSTRA_POR_ID[p["productReferenceCode"]]["price"]["on_sales"]]
    assert promo, "a amostra precisa de um produto em promoção"
    for p in promo:
        oferta = p["items"][0]["sellers"][0]["commertialOffer"]
        assert oferta["Price"] < oferta["ListPrice"]


def test_slug_sem_acento():
    assert slug("Tênis “101H” Springa multicolorido") == "tenis-101h-springa-multicolorido"


AMOSTRA_POR_ID = {r["objectID"]: r for r in AMOSTRA.values()}


def test_foto_vem_do_mapa_por_sku_e_falta_vira_lista_vazia():
    r = AMOSTRA["tenis_eu_masc"]
    url = "https://exemplo/foto.jpg"
    com = Catalogo([r], Memoria.carregar(), {r["objectID"]: [url]}).produtos()[0]
    sem = Catalogo([r], Memoria.carregar()).produtos()[0]
    assert [i["imageUrl"] for i in com["items"][0]["images"]] == [url]
    assert sem["items"][0]["images"] == []


# loja em inglês (/en)


@pytest.fixture(scope="module")
def produtos_en() -> dict[str, dict]:
    catalogo = Catalogo(list(AMOSTRA.values()), Memoria.carregar(), idioma="en")
    return {p["productReferenceCode"]: p for p in catalogo.produtos()}


def test_en_mesma_estrutura_do_pt(produtos, produtos_en):
    """Só o texto muda: IDs, preço, grade e estoque são os mesmos nas duas línguas."""
    assert produtos.keys() == produtos_en.keys()
    for codigo, pt in produtos.items():
        en = produtos_en[codigo]
        assert en["productId"] == pt["productId"]
        assert [i["itemId"] for i in en["items"]] == [i["itemId"] for i in pt["items"]]
        assert [i["Tamanho"] for i in en["items"]] == [i["Tamanho"] for i in pt["items"]]
        for i_en, i_pt in zip(en["items"], pt["items"], strict=True):
            assert i_en["sellers"][0]["commertialOffer"] == i_pt["sellers"][0]["commertialOffer"]


def test_en_nome_troca_a_cor_da_origem_pela_corrigida(produtos_en):
    p = _produto(produtos_en, "tenis_eu_masc")
    assert p["productName"] == "Sneakers “101H” Springa multicolor"
    assert p["items"][0]["Cor"] == ["multicolor"]
    assert p["categories"][0] == "/Men/Shoes/Sneakers/"
    assert p["Gênero"] == ["Men"]


def test_en_corrige_alemao_grafia_e_aspas():
    assert texto_en("7 for all mankind – hosen “The skinny“") == "7 for all mankind – pants “The skinny”"
    assert texto_en("Guess – handtaschen „Greyson“") == "Guess – handbag “Greyson”"
    assert texto_en("Chinese writings und structural details") == "Chinese writings and structural details"
    assert cor_en("black/white") == "black and white"
    assert cor_en("whiet") == "white"


def test_idioma_desconhecido_falha_listando_os_validos():
    with pytest.raises(ValueError, match="pt, en"):
        Catalogo([], Memoria.carregar(), idioma="es")
