import asyncio
import json

import pytest
from mcp import Client

from copiloto import base, ferramentas
from copiloto.base import servidor, servidor_loja
from copiloto.fontes import definir_fontes

CATALOGO = [
    {
        "objectID": "1-preto",
        "nome": "Tênis “Lakers” Philippe Model preto",
        "marca": "Philippe Model",
        "categoria": "Tênis",
        "categorias": {
            "lvl0": "Feminino",
            "lvl1": "Feminino > Calçados",
            "lvl2": "Feminino > Calçados > Tênis",
        },
        "grade": ["36", "37", "38"],
        "tamanhos_disponiveis": ["36"],
        "em_estoque": True,
    },
    {
        "objectID": "2-azul",
        "nome": "Camiseta Michael Kors azul",
        "marca": "Michael Kors",
        "categoria": "Camisetas",
        "categorias": {
            "lvl0": "Feminino",
            "lvl1": "Feminino > Roupas",
            "lvl2": "Feminino > Roupas > Camisetas",
        },
        "grade": ["P", "M", "G"],
        "tamanhos_disponiveis": [],
        "em_estoque": False,
    },
]


class FontesFalsas:
    """Loja em português (produtos_teste); a FontesFalsasEn é a mesma loja em inglês."""

    indice = "produtos_teste"

    def __init__(self):
        self.sinonimos: dict[str, dict] = {}
        # o que a Analytics API devolve com search=: os filtros que zeraram aquela busca
        self.filtros_por_busca: dict[str, list[dict]] = {
            "tenis": [
                {"attribute": "tamanhos_disponiveis", "operator": ":", "value": "38", "count": 3, "grupo": 0}
            ]
        }
        self.avisos_gravados: list[dict] = []
        self.sem_resultado = [
            {"search": "sapatenis", "count": 3, "withFilterCount": 0},
            {"search": "tenix lakers", "count": 1, "withFilterCount": 0},
            {"search": "tenis", "count": 2, "withFilterCount": 2},
        ]
        # como a API devolve: da mais feita para a menos
        self.mais_feitas = [
            {"search": "", "count": 9, "nbHits": 2},
            {"search": "m", "count": 7, "nbHits": 0},
            {"search": "tenis", "count": 5, "nbHits": 40},
            {"search": "tenis 38", "count": 4, "nbHits": 0},
            {"search": "tênis tamanho 37", "count": 2, "nbHits": 1},
            {"search": "lakers", "count": 2, "nbHits": 1},
        ]

    def buscas_sem_resultado(self, inicio, fim, limite, tag=None):
        if tag:
            return [b for b in self.sem_resultado if b["search"] == "sapatenis"]  # as 3 são sintéticas
        return self.sem_resultado[:limite]

    def buscas_mais_feitas(self, inicio, fim, limite, tag=None):
        if tag:
            return [{"search": "tenis", "count": 2, "nbHits": 40}]
        return self.mais_feitas[:limite]

    def valores_de_filtro(self, atributo, inicio, fim):
        return [{"value": "38", "count": 4}, {"value": "M", "count": 2}]

    def filtros_sem_resultado(self, inicio, fim, busca=None):
        # como a API real: sem `search`, vazio
        return self.filtros_por_busca.get(busca, []) if busca is not None else []

    def analytics_atualizado_em(self):
        return "2026-10-08T15:00:00Z"

    def contagem_de_buscas(self, inicio, fim, tag=None):
        return 4 if tag == "sintetico" else 10

    def catalogo(self):
        return CATALOGO

    def avisos(self):
        return self.avisos_gravados

    def gravar_aviso(self, aviso):
        self.avisos_gravados.append(aviso)

    def sinonimo(self, object_id):
        return self.sinonimos.get(object_id)

    def salvar_sinonimo(self, sinonimo):
        self.sinonimos[sinonimo["objectID"]] = sinonimo

    def remover_sinonimo(self, object_id):
        self.sinonimos.pop(object_id)


class FontesFalsasEn(FontesFalsas):
    indice = "produtos_teste_en"

    def __init__(self):
        super().__init__()
        self.sem_resultado = [{"search": "loafers", "count": 5, "withFilterCount": 0}]
        self.mais_feitas = [{"search": "sneakers size 38", "count": 6, "nbHits": 3}]

    def valores_de_filtro(self, atributo, inicio, fim):
        return [{"value": "38", "count": 1}]

    def filtros_sem_resultado(self, inicio, fim, busca=None):
        return []


@pytest.fixture(autouse=True)
def fontes_falsas(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "AUDITORIA", tmp_path)
    base._escritas.clear()
    falsas = FontesFalsas()
    definir_fontes({"pt": falsas, "en": FontesFalsasEn()})
    yield falsas
    definir_fontes(None)


def chamar(nome, **kw) -> dict:
    texto = asyncio.run(getattr(ferramentas, nome).mcp(**kw))
    return json.loads(texto)


# leitura


def test_todo_resultado_traz_sobre_os_dados_com_retencao():
    r = chamar("buscas_sem_resultado")
    assert "7 dias" in r["sobre_os_dados"]["retencao"]
    assert r["sobre_os_dados"]["periodo"]


def test_sobre_os_dados_declara_o_trafego_sintetico_por_indice():
    sintetico = chamar("termos_em_alta", loja="ambas")["sobre_os_dados"]["trafego_sintetico"]
    assert sintetico["por_indice"] == {
        "produtos_teste": {"buscas": 10, "sinteticas": 4},
        "produtos_teste_en": {"buscas": 10, "sinteticas": 4},
    }
    assert "sintetico" in sintetico["o_que_e"]


def test_sapatenis_nao_vira_sapato():
    r = chamar("buscas_sem_resultado", loja="pt")
    por_busca = {b["busca"]: b for b in r["buscas"]}
    assert por_busca["sapatenis"]["diagnostico"].startswith("sem produto no catálogo")
    assert por_busca["tenix lakers"]["diagnostico"].startswith("provável erro de digitação")
    assert por_busca["tenis"]["diagnostico"].startswith("ruptura: sem o filtro de tamanho 38")


def test_demanda_por_tamanho_cruza_analytics_e_ruptura():
    r = chamar("demanda_por_tamanho", categoria="feminino > calcados", loja="pt")
    assert r["categoria"] == "Feminino > Calçados"
    linha = {t["tamanho"]: t for t in r["tamanhos"]}["38"]
    assert linha == {
        "tamanho": "38",
        "buscas_com_filtro": 4,
        "buscas_que_zeraram": 3,
        "buscas_com_tamanho_no_texto": 4,
        "buscas_no_texto_sem_resultado": 4,
        "exemplos_no_texto": ["tenis 38"],
        "estoque_por_departamento": [
            {
                "departamento": "Feminino > Calçados",
                "produtos_na_grade": 1,
                "com_estoque": 0,
                "ruptura": 1,
                "ruptura_pct": 100.0,
            }
        ],
    }
    assert "M" not in {t["tamanho"] for t in r["tamanhos"] if t["estoque_por_departamento"]}


def test_ruptura_separa_calcado_de_roupa_no_mesmo_tamanho(monkeypatch, fontes_falsas):
    jeans = {
        **CATALOGO[1],
        "objectID": "3-azul",
        "nome": "Calça jeans",
        "categoria": "Jeans",
        "categorias": {"lvl0": "Feminino", "lvl1": "Feminino > Roupas", "lvl2": "Feminino > Roupas > Jeans"},
        "grade": ["36", "38"],
        "tamanhos_disponiveis": ["38"],
    }
    monkeypatch.setattr(fontes_falsas, "catalogo", lambda: [*CATALOGO, jeans])
    r = chamar("demanda_por_tamanho", loja="pt")
    estoque = {
        e["departamento"]: e
        for e in {t["tamanho"]: t for t in r["tamanhos"]}["38"]["estoque_por_departamento"]
    }
    assert estoque["Feminino > Calçados"]["ruptura_pct"] == 100.0
    assert estoque["Feminino > Roupas"]["ruptura_pct"] == 0.0


def test_busca_que_ja_encontra_hoje_nao_vira_recomendacao(fontes_falsas):
    fontes_falsas.sem_resultado = [
        {"search": "tenis 36", "count": 3, "withFilterCount": 0},
        {"search": "camiseta social", "count": 1, "withFilterCount": 0},
    ]
    por = {b["busca"]: b for b in chamar("buscas_sem_resultado", loja="pt")["buscas"]}
    assert por["tenis 36"]["diagnostico"].startswith("já encontra hoje")
    assert por["tenis 36"]["produtos_hoje_no_catalogo"] == 1
    assert por["camiseta social"]["diagnostico"] == (
        "sem produto no catálogo com: social (há produtos com: camiseta)"
    )


def test_tamanho_digitado_conta_com_palavra_de_tamanho_e_letra_sozinha_nao():
    r = chamar("demanda_por_tamanho", loja="pt")
    por = {t["tamanho"]: t for t in r["tamanhos"]}
    assert por["37"]["buscas_com_tamanho_no_texto"] == 2  # "tênis tamanho 37"
    assert por["37"]["buscas_no_texto_sem_resultado"] == 0
    assert por["M"]["buscas_com_tamanho_no_texto"] == 0  # "m" sozinho é ambíguo


def test_ambas_as_lojas_somam_filtro_e_texto():
    r = chamar("demanda_por_tamanho")
    linha = {t["tamanho"]: t for t in r["tamanhos"]}["38"]
    assert linha["buscas_com_filtro"] == 5  # 4 no pt + 1 no en
    assert linha["buscas_com_tamanho_no_texto"] == 10  # "tenis 38" (4) + "sneakers size 38" (6)
    assert linha["exemplos_no_texto"][0] == "sneakers size 38"
    assert r["sobre_os_dados"]["indices"] == ["produtos_teste", "produtos_teste_en"]


def test_tamanho_digitado_nao_vira_produto_faltando(fontes_falsas):
    fontes_falsas.sem_resultado = [
        {"search": "tenis 38", "count": 2, "withFilterCount": 0},
        {"search": "tenis tam", "count": 1, "withFilterCount": 0},
        {"search": "", "count": 1, "withFilterCount": 1},
    ]
    r = chamar("buscas_sem_resultado", loja="pt")
    por = {b["busca"]: b["diagnostico"] for b in r["buscas"]}
    assert por["tenis 38"].startswith("tamanho digitado (38)")
    assert not por["tenis tam"].startswith("sem produto")
    assert por["(sem texto: só filtros)"] == "zerou só com filtro"


def test_buscas_sem_resultado_das_duas_lojas_dizem_a_loja():
    r = chamar("buscas_sem_resultado")
    assert [(b["busca"], b["loja"]) for b in r["buscas"]][:2] == [("loafers", "en"), ("sapatenis", "pt")]


def test_loja_invalida_lista_as_validas():
    with pytest.raises(Exception, match="Válidos: pt, en, ambas"):
        asyncio.run(ferramentas.termos_em_alta.mcp(loja="es"))


def test_sinonimo_vai_para_o_indice_da_loja_e_nao_aceita_ambas():
    r = chamar("sinonimo", acao="criar", termos=["sneaker", "trainer"], loja="en")
    assert r["rascunho"]["indice"] == "produtos_teste_en"
    with pytest.raises(Exception, match="Válidos: pt, en"):
        asyncio.run(ferramentas.sinonimo.mcp(acao="criar", termos=["a", "b"], loja="ambas"))


def test_categoria_invalida_lista_as_validas():
    with pytest.raises(Exception) as erro:
        asyncio.run(ferramentas.demanda_por_tamanho.mcp(categoria="sapatos"))
    assert "Válidos:" in str(erro.value)
    assert "Feminino > Calçados > Tênis" in str(erro.value)


def test_termos_em_alta_sem_busca_vazia_e_com_cobertura():
    r = chamar("termos_em_alta", loja="pt", limite=3)
    assert [t["busca"] for t in r["termos"]] == ["m", "tenis", "tenis 38"]
    assert {t["busca"]: t["cobertura"] for t in r["termos"]} == {
        "m": "sem resultado",
        "tenis": "ok",
        "tenis 38": "sem resultado",
    }


def test_vazio_avisa_que_nao_prova_ausencia(fontes_falsas):
    fontes_falsas.sem_resultado = []
    r = chamar("buscas_sem_resultado", loja="pt")
    assert r["total_linhas"] == 0
    assert "NÃO prova" in r["aviso"]


def test_periodo_fora_da_janela_avisa():
    r = chamar("termos_em_alta", inicio="2020-01-01")
    assert any("fora da janela" in a for a in r["sobre_os_dados"]["avisos"])


# escrita


def test_sinonimo_sem_confirmar_nao_grava(fontes_falsas):
    r = chamar("sinonimo", acao="criar", termos=["sapatênis", "sapato casual"])
    assert r["gravado"] is False
    assert r["codigo"]
    assert fontes_falsas.sinonimos == {}


def test_sinonimo_com_codigo_errado_nao_grava(fontes_falsas):
    with pytest.raises(Exception, match="nada foi gravado"):
        asyncio.run(
            ferramentas.sinonimo.mcp(acao="criar", termos=["a", "b"], confirmado=True, codigo="00000000")
        )
    assert fontes_falsas.sinonimos == {}


def test_sinonimo_grava_com_o_codigo_do_rascunho_e_audita(fontes_falsas, tmp_path):
    rascunho = chamar("sinonimo", acao="criar", termos=["moletom", "hoodie"])
    r = chamar(
        "sinonimo", acao="criar", termos=["moletom", "hoodie"], confirmado=True, codigo=rascunho["codigo"]
    )
    assert r["gravado"] is True
    assert list(fontes_falsas.sinonimos) == ["copiloto-moletom-hoodie"]
    assert r["como_desfazer"]["acao"] == "remover"
    assert (tmp_path / "escritas.jsonl").read_text(encoding="utf-8").count("\n") == 1


def test_codigo_muda_se_o_termo_muda():
    a = chamar("sinonimo", acao="criar", termos=["moletom", "hoodie"])
    b = chamar("sinonimo", acao="criar", termos=["moletom", "hoodies"])
    assert a["codigo"] != b["codigo"]


def test_remover_so_o_que_o_copiloto_criou():
    with pytest.raises(Exception, match="não existe sinônimo"):
        asyncio.run(ferramentas.sinonimo.mcp(acao="remover", termos=["tênis", "sneaker"]))


def test_reportar_problema_pede_confirmacao_e_anexa_contexto(tmp_path):
    chamar("termos_em_alta")
    assert chamar("reportar_problema", o_que_esta_errado="contagem estranha")["gravado"] is False
    assert chamar("reportar_problema", o_que_esta_errado="contagem estranha", confirmado=True)["gravado"]
    linha = json.loads((tmp_path / "reportes.jsonl").read_text(encoding="utf-8"))
    assert linha["ultimas_chamadas"][-1]["tool"] == "reportar_problema"


# protocolo MCP de verdade (cliente e servidor em processo)


def test_protocolo_lista_tools_e_chama():
    async def rodar():
        async with Client(servidor) as cliente:
            tools = {t.name: t for t in (await cliente.list_tools()).tools}
            assert set(tools) == {
                "buscas_sem_resultado",
                "demanda_por_tamanho",
                "termos_em_alta",
                "cobertura_dos_dados",
                "sugestao_de_reposicao",
                "sinonimo",
                "reportar_problema",
            }
            assert "confirmado=true" in tools["sinonimo"].description
            ok = await cliente.call_tool("cobertura_dos_dados", {})
            assert not ok.is_error
            erro = await cliente.call_tool("demanda_por_tamanho", {"categoria": "sapatos"})
            assert erro.is_error
            assert "Válidos:" in erro.content[0].text

    asyncio.run(rodar())


def test_instrucoes_curtas():
    assert len(base.INSTRUCOES) < 2000


def test_contagem_pede_ate_o_dia_seguinte_e_soma_so_o_periodo():
    import datetime as dt

    from copiloto.fontes import FontesAlgolia

    class Analytics:
        def get_searches_count_with_http_info(self, index, start_date, end_date, tags=None):
            self.pedido = (start_date, end_date)
            dias = [{"date": "2026-10-08", "count": 53}, {"date": "2026-10-12", "count": 8}]
            dias.append({"date": "2026-10-13", "count": 99})  # fora do período: não entra

            class R:
                raw_data = json.dumps({"count": 160, "dates": dias})

            return R()

    f = object.__new__(FontesAlgolia)
    f.indice, f._cache, f.analytics = "produtos_teste", {}, Analytics()
    assert f.contagem_de_buscas(dt.date(2026, 10, 6), dt.date(2026, 10, 12)) == 61
    assert f.analytics.pedido == ("2026-10-06", "2026-10-13")


def _filtro(atributo, valor, operador=":"):
    return {"attribute": atributo, "operator": operador, "value": valor, "count": 1, "grupo": 0}


def test_filtro_de_tamanho_que_zera_e_ruptura_nao_filtro_quebrado(fontes_falsas):
    fontes_falsas.sem_resultado = [
        {"search": "tenis", "count": 2, "withFilterCount": 2},
        {"search": "tenis lakers", "count": 1, "withFilterCount": 1},
        {"search": "", "count": 1, "withFilterCount": 1},
    ]
    fontes_falsas.filtros_por_busca = {
        "tenis": [_filtro("tamanhos_disponiveis", "38")],  # o tênis tem 38 na grade, sem estoque
        "tenis lakers": [_filtro("categorias.lvl0", "Masculino")],  # o tênis é feminino
        "": [_filtro("referencia", "LKHD"), _filtro("objectID", "-1-preto")],
    }
    por = {b["busca"]: b for b in chamar("buscas_sem_resultado", loja="pt")["buscas"]}
    assert por["tenis"]["diagnostico"].startswith("ruptura: sem o filtro de tamanho 38 a busca acha ~1")
    assert por["tenis"]["filtros_que_zeraram"] == ["tamanhos_disponiveis:38"]
    assert por["tenis lakers"]["diagnostico"].startswith(
        "zerou com o filtro categorias.lvl0:Masculino: o texto"
    )
    assert por["(sem texto: só filtros)"]["diagnostico"].startswith("consulta interna da página de produto")


def test_filtro_que_hoje_acha_produto_nao_e_problema(fontes_falsas):
    fontes_falsas.sem_resultado = [{"search": "tenis", "count": 1, "withFilterCount": 1}]
    fontes_falsas.filtros_por_busca = {"tenis": [_filtro("tamanhos_disponiveis", "36")]}
    (linha,) = chamar("buscas_sem_resultado", loja="pt")["buscas"]
    assert linha["diagnostico"].startswith(
        "zerou com o filtro tamanhos_disponiveis:36; hoje o mesmo filtro acha ~1"
    )


def test_cada_linha_diz_quantas_ocorrencias_sao_sinteticas():
    zeradas = {b["busca"]: b for b in chamar("buscas_sem_resultado", loja="pt")["buscas"]}
    assert zeradas["sapatenis"]["vezes_sinteticas"] == 3
    assert zeradas["tenix lakers"]["vezes_sinteticas"] == 0
    termos = {b["busca"]: b for b in chamar("termos_em_alta", loja="pt")["termos"]}
    assert termos["tenis"]["vezes"] == 5 and termos["tenis"]["vezes_sinteticas"] == 2


def test_aviso_so_para_tamanho_esgotado_e_so_com_confirmacao(fontes_falsas):
    with pytest.raises(Exception, match="em estoque"):
        asyncio.run(ferramentas.avisar_quando_chegar.mcp(produto="1-preto", tamanho="36"))
    with pytest.raises(Exception, match="Grade: 36, 37, 38"):
        asyncio.run(ferramentas.avisar_quando_chegar.mcp(produto="1-preto", tamanho="44"))
    rascunho = chamar("avisar_quando_chegar", produto="1-preto", tamanho="37")
    assert rascunho["registrado"] is False and fontes_falsas.avisos_gravados == []
    ok = chamar("avisar_quando_chegar", produto="1-preto", tamanho="37", confirmado=True)
    assert ok["registrado"] is True and "não guardamos contato" in ok["mensagem"]
    (gravado,) = fontes_falsas.avisos_gravados
    assert gravado["produto"] == "1-preto" and gravado["tamanho"] == "37" and gravado["loja"] == "pt"
    assert set(gravado) == {"objectID", "produto", "nome", "cor", "categoria", "tamanho", "loja", "quando"}
    assert gravado["objectID"].startswith("1-preto-37-pt-")  # um por produto, tamanho, loja e dia


def test_reposicao_poe_aviso_de_cliente_e_busca_zerada_na_frente(fontes_falsas):
    hoje = base.hoje().isoformat()
    antigo = {"produto": "1-preto", "tamanho": "37", "loja": "pt", "quando": "2020-01-01T00:00:00+00:00"}
    fontes_falsas.avisos_gravados = [
        {"produto": "1-preto", "tamanho": "37", "loja": "pt", "quando": hoje}
    ] * 2
    fontes_falsas.avisos_gravados.append(antigo)  # fora do período: não conta
    r = chamar("sugestao_de_reposicao", categoria="Feminino > Calçados", loja="pt")
    assert r["unidade"] == "pares"
    primeiro, segundo = r["prioridades"]
    assert primeiro["tamanho"] == "38"  # 3 buscas zeraram no filtro + 4 no texto
    assert primeiro["venda_perdida"]["buscas_que_zeraram"] == 7
    assert segundo["tamanho"] == "37" and segundo["venda_perdida"]["avisos_de_cliente"] == 2
    assert segundo["repor"][0]["produto"] == "1-preto" and segundo["repor"][0]["avisos"] == 2
    assert "ponto de partida" in r["premissas"][0]


def test_reposicao_exige_categoria():
    with pytest.raises(Exception, match="informe a categoria"):
        asyncio.run(ferramentas.sugestao_de_reposicao.mcp(categoria=""))


def test_servidor_da_loja_so_tem_o_aviso():
    async def rodar():
        async with Client(servidor_loja) as cliente:
            return {t.name for t in (await cliente.list_tools()).tools}

    assert asyncio.run(rodar()) == {"avisar_quando_chegar"}


def test_reposicao_ordena_referencias_por_avaliacoes(monkeypatch, fontes_falsas):
    outro = {**CATALOGO[0], "objectID": "9-branco", "nome": "Tênis branco", "avaliacoes": 80}
    monkeypatch.setattr(
        fontes_falsas, "catalogo", lambda: [{**CATALOGO[0], "avaliacoes": 5}, outro, CATALOGO[1]]
    )
    linha = {
        x["tamanho"]: x
        for x in chamar("sugestao_de_reposicao", categoria="Feminino > Calçados", loja="pt")["prioridades"]
    }["38"]
    assert [r["produto"] for r in linha["repor"]] == ["9-branco", "1-preto"]


def test_campos_do_catalogo_trazem_avaliacoes():
    from copiloto.fontes import CAMPOS_CATALOGO

    assert "avaliacoes" in CAMPOS_CATALOGO  # sem ele, a ordem por avaliações da reposição vira 0 para todos
