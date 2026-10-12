import copy
import json
from pathlib import Path

import pytest

from catalog.traducao import Memoria
from catalog.vtex import Catalogo
from ingest.fonte_vtex import POR_PAGINA, FonteArquivo, LimiteDaApi, todos_os_produtos
from ingest.indexar import IDIOMAS, LIMITE_RECORD, configuracao, montar_registros, tamanho
from ingest.registro import nota_bayesiana, registros

AMOSTRA = json.loads(
    (
        Path(__file__).resolve().parents[2] / "catalog" / "tests" / "fixtures" / "amostra_origem.json"
    ).read_text(encoding="utf-8")
)


def _gravar_mock(pasta: Path, idioma: str) -> Path:
    """Catálogo VTEX gerado da amostra, gravado como o build grava."""
    catalogo = Catalogo(list(AMOSTRA.values()), Memoria.carregar(), idioma=idioma)
    (pasta / "produtos.json").write_text(
        json.dumps(catalogo.produtos(), ensure_ascii=False), encoding="utf-8"
    )
    (pasta / "avaliacoes.json").write_text(json.dumps(catalogo.avaliacoes()), encoding="utf-8")
    return pasta


@pytest.fixture(scope="module")
def mock(tmp_path_factory) -> Path:
    return _gravar_mock(tmp_path_factory.mktemp("vtex"), "pt")


@pytest.fixture(scope="module")
def mock_en(tmp_path_factory) -> Path:
    return _gravar_mock(tmp_path_factory.mktemp("vtex_en"), "en")


@pytest.fixture(scope="module")
def records(mock) -> dict[str, dict]:
    return {r["produto_id"]: r for r in montar_registros(FonteArquivo(mock))}


def _por_origem(records, mock, caso):
    produtos = json.loads((mock / "produtos.json").read_text(encoding="utf-8"))
    pid = next(p["productId"] for p in produtos if p["productReferenceCode"] == AMOSTRA[caso]["objectID"])
    return records[pid]


# paginação da Legacy Search API


def test_paginacao_respeita_limites_da_api(mock):
    fonte = FonteArquivo(mock)
    with pytest.raises(ValueError):
        fonte.pagina(0, POR_PAGINA)
    with pytest.raises(LimiteDaApi):
        fonte.pagina(2550, 2599)
    ids = [p["productId"] for p in todos_os_produtos(fonte)]
    assert len(ids) == len(AMOSTRA) == len(set(ids))
    assert ids == sorted(ids, key=int, reverse=True)


# record


def test_um_record_por_produto_quando_a_loja_tem_produto_por_cor(records):
    assert len(records) == len(AMOSTRA)


def test_record_abaixo_do_limite_do_free(records):
    assert max(tamanho(r) for r in records.values()) < LIMITE_RECORD


def test_tamanhos_disponiveis_e_subconjunto_da_grade(records):
    for r in records.values():
        assert set(r["tamanhos_disponiveis"]) <= set(r["grade"])
        assert r["em_estoque"] == bool(r["tamanhos_disponiveis"])


def test_categoria_hierarquica(records, mock):
    r = _por_origem(records, mock, "tenis_eu_masc")
    assert r["categorias"] == {
        "lvl0": "Masculino",
        "lvl1": "Masculino > Calçados",
        "lvl2": "Masculino > Calçados > Tênis",
    }
    assert r["categoria"] == "Tênis"
    assert r["genero"] == "Masculino"


def test_preco_efetivo_unico_com_promocao(records, mock):
    r = _por_origem(records, mock, "acessorio_promo")
    assert r["em_promocao"] and r["preco"] < r["preco_de"]
    assert r["desconto_pct"] == 10
    sem = _por_origem(records, mock, "tenis_eu_masc")
    assert not sem["em_promocao"] and sem["preco"] == sem["preco_de"]


def test_loja_canonica_gera_um_record_por_cor(mock):
    """Produto com SKUs cor × tamanho (modelo canônico da VTEX) vira um record por cor."""
    produtos = json.loads((mock / "produtos.json").read_text(encoding="utf-8"))
    base = next(p for p in produtos if len(p["items"]) > 1)
    canonico = copy.deepcopy(base)
    outra_cor = copy.deepcopy(base["items"])
    for item in outra_cor:
        item["itemId"] += "9"
        item["Cor"] = ["vermelho"]
    canonico["items"] += outra_cor
    saida = registros(canonico, None, 3.0)
    assert [r["cor"] for r in saida] == [base["items"][0]["Cor"][0], "vermelho"]
    assert len({r["objectID"] for r in saida}) == 2
    assert all(r["produto_id"] == base["productId"] for r in saida)


def test_nota_bayesiana_puxa_poucas_avaliacoes_para_a_media():
    assert nota_bayesiana(5, 1, 3.0) < nota_bayesiana(5, 100, 3.0)
    assert nota_bayesiana(0, 0, 3.0) == 3.0


# configuração do índice


def test_idioma_pt_e_nao_pt_br():
    primario, _ = configuracao("produtos_ptbr")
    for chave in ["queryLanguages", "indexLanguages", "ignorePlurals", "removeStopWords"]:
        assert primario[chave] == ["pt"]


def test_atributos_configurados_existem_no_record(records):
    primario, _ = configuracao("produtos_ptbr")
    r = next(iter(records.values()))

    def existe(caminho: str) -> bool:
        valor = r
        for parte in caminho.split("."):
            if parte not in valor:
                return False
            valor = valor[parte]
        return True

    def nome(attr: str) -> str:
        return attr.split("(")[-1].rstrip(")")

    attrs = [*primario["searchableAttributes"], *primario["attributesForFaceting"]]
    attrs += [nome(c).split(",")[0] for c in primario["customRanking"]]
    for attr in attrs:
        assert existe(nome(attr)), attr


def test_replicas_de_ordenacao_por_preco():
    primario, por_replica = configuracao("produtos_ptbr")
    assert primario["replicas"] == ["produtos_ptbr_preco_asc", "produtos_ptbr_preco_desc"]
    assert por_replica["produtos_ptbr_preco_asc"]["ranking"][0] == "asc(preco)"
    assert por_replica["produtos_ptbr_preco_desc"]["ranking"][0] == "desc(preco)"
    assert "replicas" not in por_replica["produtos_ptbr_preco_asc"]


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_limites_do_free_em_regras_e_sinonimos(idioma):
    pasta = IDIOMAS[idioma].config
    regras = json.loads((pasta / "regras.json").read_text(encoding="utf-8"))
    sinonimos = json.loads((pasta / "sinonimos.json").read_text(encoding="utf-8"))
    assert len(regras) <= 3  # a API recusa a 4ª Rule no Free (08/10/2026), apesar das 10 do pricing
    assert len(sinonimos) <= 1000
    assert len({s["objectID"] for s in sinonimos}) == len(sinonimos)
    assert len({r["objectID"] for r in regras}) == len(regras)


# loja em inglês


def test_en_tem_o_mesmo_objectid_do_pt(mock, mock_en):
    """A cor entra no objectID e vem traduzida; o objectID do en vem do pt pelos SKUs."""
    ids_pt = {s["id"]: r["objectID"] for r in montar_registros(FonteArquivo(mock)) for s in r["skus"]}
    pt = {r["produto_id"]: r for r in montar_registros(FonteArquivo(mock))}
    en = {r["produto_id"]: r for r in montar_registros(FonteArquivo(mock_en), ids_pt)}
    assert pt.keys() == en.keys()
    for pid, r in en.items():
        assert r["objectID"] == pt[pid]["objectID"]
        assert r["preco"] == pt[pid]["preco"]
        assert r["tamanhos_disponiveis"] == pt[pid]["tamanhos_disponiveis"]
    sem_ids = {r["objectID"] for r in montar_registros(FonteArquivo(mock_en))}
    assert sem_ids != {r["objectID"] for r in pt.values()}, "sem o mapa, a cor em inglês mudaria o objectID"


def test_en_sku_sem_par_no_idioma_padrao_falha(mock_en):
    with pytest.raises(ValueError, match="não casam"):
        montar_registros(FonteArquivo(mock_en), {})


def test_settings_do_en_em_ingles():
    primario, por_replica = configuracao("produtos_en", "en")
    for chave in ["queryLanguages", "indexLanguages", "ignorePlurals", "removeStopWords"]:
        assert primario[chave] == ["en"]
    assert primario["replicas"] == ["produtos_en_preco_asc", "produtos_en_preco_desc"]
    assert por_replica["produtos_en_preco_asc"]["queryLanguages"] == ["en"]
    assert primario["optionalWords"] == ["size"]
    assert primario["searchableAttributes"] == configuracao("produtos_ptbr")[0]["searchableAttributes"]


def test_contem_ignora_campos_a_mais_da_api():
    from ingest.indexar import contem, mesmos_objetos

    assert contem({"a": 1, "padrao": True, "b": {"c": [1, 2], "d": 0}}, {"a": 1, "b": {"c": [1, 2]}})
    assert not contem({"a": 1}, {"a": 2})
    assert not contem({"c": [1, 2, 3]}, {"c": [1, 2]})
    atuais = [{"objectID": "x", "type": "synonym", "synonyms": ["a", "b"], "_highlightResult": {}}]
    assert mesmos_objetos(atuais, [{"objectID": "x", "type": "synonym", "synonyms": ["a", "b"]}])
    assert not mesmos_objetos(atuais, [{"objectID": "y", "type": "synonym", "synonyms": ["a", "b"]}])
