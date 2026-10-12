import json
from pathlib import Path

import pytest

from catalog import fonte
from catalog.glossario import CATEGORIAS, CORES, GRUPOS_COR, categoria_pt, grupo_cor_pt
from catalog.traducao import Memoria, TraducaoFaltando, chave

AMOSTRA = json.loads((Path(__file__).parent / "fixtures" / "amostra_origem.json").read_text(encoding="utf-8"))
ORIGEM_DISPONIVEL = (fonte.PASTA / "products.json").exists()


def test_categoria_traduz_caminho_inteiro():
    assert categoria_pt("Women > Shoes > Sneakers") == "Feminino > Calçados > Tênis"
    assert categoria_pt("Accessories > Women > Clothing") == "Acessórios > Feminino > Vestuário"


def test_grupo_cor_separa_swatch():
    assert grupo_cor_pt("blue;#0075BB") == ("azul", "#0075BB")
    nome, swatch = grupo_cor_pt("multicolor;https://exemplo/color_wheel.svg")
    assert nome == "multicolorido"
    assert swatch.startswith("https://")


def test_glossario_sem_travessao_nem_barra():
    for valor in [*CORES.values(), *GRUPOS_COR.values(), *CATEGORIAS.values()]:
        assert "—" not in valor
        assert "–" not in valor
        assert "|" not in valor


def test_memoria_falha_alto_quando_falta_traducao():
    memoria = Memoria({})
    memoria.adicionar("Bag", "Bolsa")
    assert memoria.traduzir("Bag") == "Bolsa"
    assert memoria.traduzir("") == ""
    with pytest.raises(TraducaoFaltando):
        memoria.traduzir("Wallet")


def test_memoria_salva_ordenada_e_relê(tmp_path):
    memoria = Memoria({})
    memoria.adicionar("Wallet", "Carteira")
    memoria.adicionar("Bag", "Bolsa")
    caminho = tmp_path / "pt-BR.json"
    memoria.salvar(caminho)
    relida = Memoria.carregar(caminho)
    assert [e["en"] for e in relida.entradas.values()] == ["Bag", "Wallet"]
    assert relida.entradas[chave("Bag")]["pt"] == "Bolsa"


@pytest.mark.parametrize("registro", AMOSTRA.values(), ids=AMOSTRA.keys())
def test_amostra_coberta_pelo_glossario(registro):
    assert registro["color"]["original_name"] in CORES
    grupo_cor_pt(registro["color"]["filter_group"])
    hc = registro["hierarchical_categories"]
    categoria_pt(hc.get("lvl2") or hc["lvl1"])


@pytest.mark.skipif(not ORIGEM_DISPONIVEL, reason="dataset de origem não baixado (rode o build uma vez)")
def test_origem_inteira_coberta_pelo_glossario():
    registros = fonte.carregar()
    assert len(registros) == 1787
    for r in registros:
        assert r["color"]["original_name"] in CORES
        grupo_cor_pt(r["color"]["filter_group"])
        hc = r["hierarchical_categories"]
        categoria_pt(hc.get("lvl2") or hc["lvl1"])


def test_memoria_versionada_cobre_a_amostra():
    memoria = Memoria.carregar()
    for r in AMOSTRA.values():
        assert memoria.traduzir(r["name"])
        memoria.traduzir(r["description"])


def test_memoria_versionada_sem_travessao_nem_barra():
    for entrada in Memoria.carregar().entradas.values():
        assert not any(s in entrada["pt"] for s in ("—", "–", "--", "|")), entrada


@pytest.mark.skipif(not ORIGEM_DISPONIVEL, reason="dataset de origem não baixado (rode o build uma vez)")
def test_memoria_versionada_cobre_a_origem_inteira():
    memoria = Memoria.carregar()
    textos = {r["name"] for r in fonte.carregar()} | {r["description"] for r in fonte.carregar()}
    assert memoria.pendentes(textos) == []


@pytest.mark.skipif(
    not (ORIGEM_DISPONIVEL and fonte.IMAGENS.caminho.exists()),
    reason="origens não baixadas (rode o build uma vez)",
)
def test_todo_produto_da_origem_tem_foto_no_sunrise():
    imagens = fonte.imagens_por_sku()
    assert all(imagens.get(r["objectID"]) for r in fonte.carregar())


def test_foto_sempre_na_versao_grande():
    assert fonte._maior("https://x/products/083436_1_medium.jpg") == "https://x/products/083436_1_large.jpg"
    assert fonte._maior("https://x/products/083441_1_large.jpg") == "https://x/products/083441_1_large.jpg"
