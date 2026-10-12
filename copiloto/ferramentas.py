"""Tools do copiloto do merchandiser.

O Productivity MCP oficial da Algolia já lê analytics, settings e sinônimos cru. Estas tools se diferenciam
pela decisão de varejo: demanda perdida por tamanho (analytics x estoque por grade), cobertura do catálogo, e
escrita de sinônimo com confirmação ligada ao rascunho exato.
"""

from __future__ import annotations

import datetime as dt
import difflib
import functools
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from copiloto import base
from copiloto.base import ferramenta, periodo, sem_acento, servidor_loja
from copiloto.fontes import LOJAS, fontes

ORDEM_LETRAS = ["PP", "P", "M", "G", "GG", "XGG"]
COBERTURA_BAIXA = 5
# semelhança mínima para tratar como erro de digitação: "tenix"→"tenis" é 0,80; "sapatenis"→"sapatos" é 0,75 e
# "social"→"special" é 0,77, que são outra coisa (sapatênis não é sapato)
SEMELHANCA_DIGITACAO = 0.8
PREFIXO_COPILOTO = "copiloto-"
# palavras que só anunciam o tamanho (optionalWords dos índices): não são produto faltando
PALAVRAS_DE_TAMANHO = {"tamanho", "tam", "numero", "num", "size"}
# conectivos que não decidem se a busca casa ("jaqueta de couro", "bag with strap")
CONECTIVOS = {"de", "da", "do", "das", "dos", "e", "com", "para", "the", "for", "with", "and", "of"}
# analyticsTags das buscas geradas para a demo (sintetico/cenario.json)
TAG_SINTETICO = "sintetico"


def _ordem_tamanho(t: str) -> tuple[int, float]:
    if t in ORDEM_LETRAS:
        return (0, ORDEM_LETRAS.index(t))
    if t == "U":
        return (2, 0)
    try:
        return (1, float(t))
    except ValueError:
        return (3, 0)


def _lojas(loja: str, ambas: bool = True) -> list[str]:
    """`pt`, `en` ou `ambas` (as duas lojas: a demanda é uma só); inválida volta com as válidas."""
    validas = [*LOJAS, "ambas"] if ambas else list(LOJAS)
    escolhida = base.escolher(loja, validas, "loja")
    return list(LOJAS) if escolhida == "ambas" else [escolhida]


def _sinteticas(lista: list[dict]) -> Counter[str]:
    """Ocorrências sintéticas por busca (a mesma lista da Analytics API, filtrada pela tag)."""
    return Counter({b.get("search", ""): b.get("count", 0) for b in lista})


def _sobre(inicio, fim, lojas, avisos=(), fonte="Algolia Analytics API") -> dict:
    # status e contagens de cada índice em paralelo: são chamadas pequenas e independentes à Analytics API
    pedidos = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        for lj in lojas:
            f = fontes(lj)
            pedidos[f.indice] = (
                executor.submit(f.analytics_atualizado_em),
                executor.submit(f.contagem_de_buscas, inicio, fim),
                executor.submit(f.contagem_de_buscas, inicio, fim, TAG_SINTETICO),
            )
    return {
        "periodo": f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y} (UTC, inclusivo)",
        "analytics_atualizado_em": {i: p[0].result() for i, p in pedidos.items()},
        "retencao": f"{base.RETENCAO_DIAS} dias (plano Free); atraso típico de 1 a 4 h",
        "fonte": fonte,
        "indices": list(pedidos),
        "trafego_sintetico": {
            "por_indice": {
                i: {"buscas": p[1].result(), "sinteticas": p[2].result()} for i, p in pedidos.items()
            },
            "o_que_e": f"buscas e cliques gerados para a demo ter volume (analyticsTags {TAG_SINTETICO}, "
            "cenário em sintetico/cenario.json); o resto é visita real à loja",
        },
        "avisos": list(avisos),
    }


def _categorias(catalogo: list[dict]) -> list[str]:
    caminhos = set()
    for p in catalogo:
        caminhos.update(v for v in (p.get("categorias") or {}).values() if v)
    return sorted(caminhos)


def _filtrar_categoria(catalogo: list[dict], categoria: str) -> tuple[list[dict], str]:
    if not categoria:
        return catalogo, "todas"
    caminho = base.escolher(categoria, _categorias(catalogo), "categoria")
    return [p for p in catalogo if caminho in (p.get("categorias") or {}).values()], caminho


def _vocabulario(catalogo: list[dict]) -> dict[str, int]:
    palavras: Counter[str] = Counter()
    for p in catalogo:
        texto = " ".join([p.get("nome", ""), p.get("marca", ""), p.get("categoria", "")])
        palavras.update(w for w in re.findall(r"[a-z0-9]+", sem_acento(texto)) if len(w) > 2)
    return dict(palavras)


def tamanhos_no_texto(busca: str, validos: set[str]) -> set[str]:
    """Tamanhos da grade digitados na busca ("tênis 39", "sneakers size 38", "camiseta m").

    Estimativa: vale a palavra que é exatamente um tamanho da grade do catálogo. Uma letra sozinha ("m") não
    conta: é ambígua sem o produto ao lado.
    """
    palavras = re.findall(r"[a-z0-9]+", sem_acento(busca))
    achados = set()
    for w in palavras:
        if w.isalpha() and len(palavras) == 1:
            continue
        t = w.upper() if w.isalpha() else w
        if t in validos:
            achados.add(t)
    return achados


def _palavras_do_produto(p: dict) -> set[str]:
    campos = [p.get(k) or "" for k in ("nome", "marca", "categoria", "genero", "cor", "grupo_cor")]
    campos.append((p.get("categorias") or {}).get("lvl1") or "")  # o nível pesquisável no índice
    return set(re.findall(r"[a-z0-9]+", sem_acento(" ".join(campos))))


_AUSENTE = object()  # atributo que o catálogo do copiloto não tem


def _valor_do_filtro(p: dict, atributo: str):
    if atributo.startswith("categorias."):
        return (p.get("categorias") or {}).get(atributo.split(".", 1)[1])
    return p.get(atributo, _AUSENTE)


def _passa(p: dict, f: dict) -> bool | None:
    """O produto passa no filtro do analytics? None = atributo que o catálogo do copiloto não tem."""
    v = _valor_do_filtro(p, f.get("attribute", ""))
    if v is _AUSENTE:
        return None
    alvo, op = str(f.get("value", "")), f.get("operator", ":")
    if op == ":":
        if isinstance(v, list):
            return alvo in v
        return str(v).lower() == alvo.lower()
    try:
        x, y = float(v), float(alvo)
    except (TypeError, ValueError):
        return None
    return {"<": x < y, "<=": x <= y, ">": x > y, ">=": x >= y, "=": x == y, "!=": x != y}.get(op)


def produtos_hoje(busca: str, catalogo: list[dict], grade: set[str], filtros=()) -> int | None:
    """Estimativa de quantos produtos a busca (com os filtros dados) encontraria hoje no catálogo indexado.

    Exige todas as palavras (sem acento, sem conectivo nem palavra de tamanho) no nome, marca, categoria,
    gênero ou cor, e o tamanho digitado em estoque. Não modela plural, erro de digitação nem a descrição,
    então tende a errar para menos (0 para o que a busca acha), não para mais. None = filtro desconhecido.
    """
    palavras = re.findall(r"[a-z0-9]+", sem_acento(busca))
    tamanhos = tamanhos_no_texto(busca, grade)
    exigidas = {
        w
        for w in palavras
        if w not in CONECTIVOS
        and w not in PALAVRAS_DE_TAMANHO
        and (w.upper() if w.isalpha() else w) not in tamanhos
    }
    if not exigidas and not tamanhos and not filtros:
        return 0
    total = 0
    for p in catalogo:
        if not (exigidas <= _palavras_do_produto(p) and tamanhos <= set(p.get("tamanhos_disponiveis") or [])):
            continue
        passa = [_passa(p, f) for f in filtros]
        if None in passa:
            return None
        total += all(passa)
    return total


def _diagnostico_do_filtro(termo: str, filtros: list[dict], catalogo: list[dict], grade: set[str]) -> str:
    """Por que a busca zerou com filtro: ruptura de tamanho, combinação sem produto ou consulta interna."""
    nomes = ", ".join(f"{f['attribute']}{f.get('operator', ':')}{f['value']}" for f in filtros)
    atributos = {f["attribute"] for f in filtros}
    if not termo and atributos & {"objectID", "referencia"}:
        return (
            "consulta interna da página de produto (outras cores da mesma referência), não é busca de cliente"
        )
    pelo_texto = produtos_hoje(termo, catalogo, grade) if termo else len(catalogo)
    com = produtos_hoje(termo, catalogo, grade, filtros)
    tamanhos = [f["value"] for f in filtros if f["attribute"] == "tamanhos_disponiveis"]
    if com is None:
        return f"zerou com o filtro {nomes}"
    if com:
        return (
            f"zerou com o filtro {nomes}; hoje o mesmo filtro acha ~{com} produtos (zerou antes de uma "
            "mudança de estoque ou de configuração): nada a corrigir"
        )
    if tamanhos and pelo_texto:
        sem_o_tamanho = produtos_hoje(
            termo, catalogo, grade, [f for f in filtros if f["attribute"] != "tamanhos_disponiveis"]
        )
        if sem_o_tamanho:
            return (
                f"ruptura: sem o filtro de tamanho {', '.join(tamanhos)} a busca acha ~{sem_o_tamanho} "
                f"produtos, e nenhum tem esse tamanho em estoque (filtro {nomes}); demanda perdida, ver "
                "demanda_por_tamanho"
            )
    return f"zerou com o filtro {nomes}: o texto acha ~{base} produtos, nenhum com esse filtro"


@ferramenta(titulo="Buscas sem resultado")
def buscas_sem_resultado(inicio: str = "", fim: str = "", limite: int = 20, loja: str = "ambas") -> dict:
    """Buscas da loja que voltaram vazias no período, com o diagnóstico de cada uma.

    `inicio`/`fim`: AAAA-MM-DD ou dd/mm/aaaa (vazio = últimos 7 dias, a janela do plano Free; ao responder,
    repita sobre_os_dados.periodo como veio, não "a semana"). `limite`: até
    100. `loja`: pt, en ou ambas (padrão; cada linha diz de qual loja veio). Diagnóstico: "ruptura" (o filtro
    de tamanho zerou porque nenhum produto tem aquele tamanho em estoque: demanda perdida, assunto de
    reposição, não de configuração), "zerou com o filtro X" (`filtros_que_zeraram`: a combinação não tem
    produto, ou já acha hoje), "provável erro de digitação ou variação" (candidata a sinônimo: confira antes
    de propor), "sem produto no catálogo" (demanda sem oferta: assunto de compra), "já encontra hoje" (o
    analytics soma a janela: zerou antes de uma mudança; não proponha mudar o que já funciona) ou "consulta
    interna" (não é busca de cliente: ignore). Filtro que zera não é filtro quebrado. Estimativas pelo
    catálogo. Palavra parecida não é o mesmo produto: sapatênis não é sapato. `vezes_sinteticas`: quantas
    ocorrências são do tráfego sintético da demo; diga quando um achado vier só delas.
    """
    ini, fim_d, avisos = periodo(inicio, fim)
    limite = max(1, min(int(limite), 100))
    lojas = _lojas(loja)
    linhas = []
    zeradas = {lj: fontes(lj).buscas_sem_resultado(ini, fim_d, limite) for lj in lojas}
    sinteticas = {
        lj: _sinteticas(fontes(lj).buscas_sem_resultado(ini, fim_d, 1000, TAG_SINTETICO)) for lj in lojas
    }
    # qual filtro zerou cada busca que teve filtro (uma chamada pequena por busca, em paralelo)
    with ThreadPoolExecutor(max_workers=8) as executor:
        pedidos = {
            (lj, b.get("search", "")): executor.submit(
                fontes(lj).filtros_sem_resultado, ini, fim_d, b.get("search", "")
            )
            for lj in lojas
            for b in zeradas[lj]
            if b.get("withFilterCount")
        }
    filtros_da_busca = {}
    for chave, pedido in pedidos.items():
        valores = pedido.result()
        # o grupo mais frequente (a API ordena por contagem): a combinação de filtros que mais zerou
        filtros_da_busca[chave] = [v for v in valores if v.get("grupo", 0) == 0]
    for lj in lojas:
        catalogo = fontes(lj).catalogo()
        vocab = _vocabulario(catalogo)
        grade = {t for p in catalogo for t in p.get("grade") or []}
        for b in zeradas[lj]:
            termo = b.get("search", "")
            palavras = re.findall(r"[a-z0-9]+", sem_acento(termo))
            tamanhos = tamanhos_no_texto(termo, grade)
            faltando = [
                w
                for w in palavras
                if w not in vocab
                and w not in PALAVRAS_DE_TAMANHO
                and (w.upper() if w.isalpha() else w) not in tamanhos
            ]
            digitacao = {
                w: difflib.get_close_matches(w, vocab, n=2, cutoff=SEMELHANCA_DIGITACAO) for w in faltando
            }
            parecidas = {w: difflib.get_close_matches(w, vocab, n=2, cutoff=0.7) for w in faltando}
            hoje = (produtos_hoje(termo, catalogo, grade) or 0) if termo else 0
            existentes = [w for w in palavras if w in vocab and w not in CONECTIVOS]
            so_com_filtro = b.get("withFilterCount", 0) >= b.get("count", 0) > 0
            filtros = filtros_da_busca.get((lj, termo), [])
            if so_com_filtro and filtros:
                diagnostico = _diagnostico_do_filtro(termo, filtros, catalogo, grade)
            elif not termo:
                diagnostico = "zerou só com filtro"
            elif hoje and so_com_filtro:
                diagnostico = f"zerou só com filtro (sem ele, o texto acha ~{hoje} produtos hoje)"
            elif hoje:
                diagnostico = (
                    f"já encontra hoje (~{hoje} produtos no catálogo): zerou antes de uma mudança de "
                    "configuração ou de estoque; nada a corrigir na busca"
                )
            elif tamanhos and not faltando:
                # o tamanho digitado é pesquisável: a busca só zera se nenhum produto tiver estoque nele
                diagnostico = f"tamanho digitado ({', '.join(sorted(tamanhos))}): ver demanda_por_tamanho"
            elif b.get("withFilterCount") and not faltando:
                diagnostico = "zerou só com filtro"
            elif faltando and all(digitacao.values()):
                diagnostico = "provável erro de digitação ou variação de termo do catálogo"
            elif faltando:
                diagnostico = f"sem produto no catálogo com: {', '.join(faltando)}"
                if existentes:
                    diagnostico += f" (há produtos com: {', '.join(existentes)})"
            else:
                diagnostico = "palavras existem, combinação não (ver termos separados)"
            linhas.append(
                {
                    "busca": termo or "(sem texto: só filtros)",
                    "loja": lj,
                    "vezes": b.get("count", 0),
                    "vezes_com_filtro": b.get("withFilterCount", 0),
                    "vezes_sinteticas": sinteticas[lj][termo],
                    "diagnostico": diagnostico,
                    "produtos_hoje_no_catalogo": hoje,
                    "filtros_que_zeraram": [
                        f"{f['attribute']}{f.get('operator', ':')}{f['value']}"
                        for f in filtros_da_busca.get((lj, termo), [])
                    ],
                    # só referência: parecido na escrita não é o mesmo produto (sapatênis não é sapato)
                    "palavras_parecidas_no_catalogo": {k: v for k, v in parecidas.items() if v},
                }
            )
    linhas = sorted(linhas, key=lambda x: -x["vezes"])[:limite]
    return {
        "buscas": linhas,
        "total_linhas": len(linhas),
        "sobre_os_dados": _sobre(ini, fim_d, lojas, avisos),
    }


def _sinais_de_tamanho(ini, fim_d, lojas, validos):
    """Procura por tamanho no analytics: filtro, filtros que zeraram, digitado no texto e texto que zerou."""
    filtro: Counter[str] = Counter()
    zeradas: Counter[str] = Counter()
    no_texto: Counter[str] = Counter()
    texto_zerado: Counter[str] = Counter()
    exemplos: dict[str, Counter[str]] = {}
    for lj in lojas:
        for v in fontes(lj).valores_de_filtro("tamanhos_disponiveis", ini, fim_d):
            filtro[v["value"]] += v.get("count", 0)
        # sem `search`, a Analytics API devolve vazio nos filtros que zeraram: pergunta busca a busca
        zeradas_lj = fontes(lj).buscas_sem_resultado(ini, fim_d, 1000)
        com_filtro = [b.get("search", "") for b in zeradas_lj if b.get("withFilterCount")]
        f = fontes(lj)
        with ThreadPoolExecutor(max_workers=8) as executor:
            listas = executor.map(functools.partial(f.filtros_sem_resultado, ini, fim_d), com_filtro)
            for v in (v for lista in listas for v in lista):
                if v.get("attribute") == "tamanhos_disponiveis":
                    zeradas[v.get("value")] += v.get("count", 0)
        for b in fontes(lj).buscas_mais_feitas(ini, fim_d, 1000):
            for t in tamanhos_no_texto(b.get("search", ""), validos):
                no_texto[t] += b.get("count", 0)
                texto_zerado[t] += b.get("count", 0) if b.get("nbHits", 1) == 0 else 0
                exemplos.setdefault(t, Counter())[b["search"]] += b.get("count", 0)
    return filtro, zeradas, no_texto, texto_zerado, exemplos


@ferramenta(titulo="Demanda perdida por tamanho")
def demanda_por_tamanho(inicio: str = "", fim: str = "", categoria: str = "", loja: str = "ambas") -> dict:
    """Quanto se buscou por cada tamanho e quanto do catálogo tem esse tamanho em estoque.

    Duas formas de buscar um tamanho, contadas em colunas separadas (quem digita e filtra conta nas duas):
    pelo filtro `tamanhos_disponiveis` (e as buscas que esse filtro zerou) e digitado no texto ("tênis 39",
    "sneakers size 38"), lido das 1.000 buscas mais feitas de cada loja, com exemplos. O estoque vem do
    catálogo indexado, em `estoque_por_departamento` (o 39 é calçado e também jeans): `ruptura` = produtos
    com o tamanho na grade e sem estoque nele, a lista de reposição. Cite a ruptura por departamento, nunca
    somada.
    `categoria`: caminho na língua da loja, ex. "Feminino > Calçados > Tênis" (vazio = todas; inválida volta
    com as válidas; com loja=ambas, o caminho em português). `loja`: pt, en ou ambas (padrão). Não some
    calçado com roupa: a grade é diferente.
    """
    ini, fim_d, avisos = periodo(inicio, fim)
    lojas = _lojas(loja)
    # mesmo catálogo e estoque nas duas lojas: o da primeira escolhida
    catalogo, caminho = _filtrar_categoria(fontes(lojas[0]).catalogo(), categoria)
    validos = {t for p in fontes(lojas[0]).catalogo() for t in p.get("grade") or []}
    filtro, zeradas, no_texto, texto_zerado, exemplos = _sinais_de_tamanho(ini, fim_d, lojas, validos)
    if caminho != "todas":
        avisos.append("o analytics (filtro e texto) é da loja inteira; o estoque é da categoria escolhida")

    # estoque por tamanho e departamento: o 39 é calçado e também jeans, e grades diferentes não se somam
    por_tamanho: dict[str, dict[str, dict]] = {}
    for p in catalogo:
        disponiveis = set(p.get("tamanhos_disponiveis") or [])
        departamento = (
            (p.get("categorias") or {}).get("lvl1") or (p.get("categorias") or {}).get("lvl0") or "?"
        )
        for t in p.get("grade") or []:
            linha = por_tamanho.setdefault(t, {}).setdefault(
                departamento, {"produtos_na_grade": 0, "com_estoque": 0}
            )
            linha["produtos_na_grade"] += 1
            linha["com_estoque"] += t in disponiveis
    for t in set(filtro) | set(zeradas) | set(no_texto):
        por_tamanho.setdefault(t, {})

    linhas = []
    for t in sorted(por_tamanho, key=_ordem_tamanho):
        estoque = []
        for departamento, g in sorted(por_tamanho[t].items(), key=lambda x: -x[1]["produtos_na_grade"]):
            ruptura = g["produtos_na_grade"] - g["com_estoque"]
            estoque.append(
                {
                    "departamento": departamento,
                    **g,
                    "ruptura": ruptura,
                    "ruptura_pct": round(100 * ruptura / g["produtos_na_grade"], 1),
                }
            )
        linhas.append(
            {
                "tamanho": t,
                "buscas_com_filtro": filtro.get(t, 0),
                "buscas_que_zeraram": zeradas.get(t, 0),
                "buscas_com_tamanho_no_texto": no_texto.get(t, 0),
                "buscas_no_texto_sem_resultado": texto_zerado.get(t, 0),
                "exemplos_no_texto": [b for b, _ in exemplos[t].most_common(3)] if t in exemplos else [],
                "estoque_por_departamento": estoque,
            }
        )
    sobre = _sobre(
        ini,
        fim_d,
        lojas,
        avisos,
        fonte="Algolia Analytics API (filtros e buscas) + catálogo indexado (estoque)",
    )
    return {
        "categoria": caminho,
        "como_foi_calculado": "filtro: valores de tamanhos_disponiveis no analytics; texto: tamanho da "
        "grade digitado nas 1.000 buscas mais feitas de cada loja (estimativa: letra sozinha não conta; "
        "buscas fora das 1.000 mais feitas ficam de fora); estoque: grade e tamanhos_disponiveis de cada "
        "produto no índice, por departamento (a busca é da loja inteira: não reparta entre departamentos)",
        "tamanhos": linhas,
        "total_linhas": len(linhas),
        "sobre_os_dados": sobre,
    }


@ferramenta(titulo="Termos em alta e cobertura")
def termos_em_alta(inicio: str = "", fim: str = "", limite: int = 20, loja: str = "ambas") -> dict:
    """Buscas mais feitas no período e quantos produtos cada uma encontra (cobertura do catálogo).

    `cobertura`: "sem resultado" (0), "baixa" (menos de 5 produtos) ou "ok". Termo em alta com cobertura baixa
    é sinal de compra ou de configuração. A busca vazia (navegação sem digitar) fica de fora. `limite`: até
    100. `loja`: pt, en ou ambas (padrão; cada linha diz de qual loja veio). `vezes_sinteticas`: quantas
    ocorrências são do tráfego sintético da demo.
    """
    ini, fim_d, avisos = periodo(inicio, fim)
    limite = max(1, min(int(limite), 100))
    lojas = _lojas(loja)
    linhas = []
    for lj in lojas:
        sinteticas = _sinteticas(fontes(lj).buscas_mais_feitas(ini, fim_d, 1000, TAG_SINTETICO))
        for b in fontes(lj).buscas_mais_feitas(ini, fim_d, limite + 1):
            if not b.get("search"):
                continue
            n = b.get("nbHits", 0)
            cobertura = "sem resultado" if n == 0 else "baixa" if n < COBERTURA_BAIXA else "ok"
            linhas.append(
                {
                    "busca": b["search"],
                    "loja": lj,
                    "vezes": b.get("count", 0),
                    "vezes_sinteticas": sinteticas[b["search"]],
                    "produtos": n,
                    "cobertura": cobertura,
                }
            )
    linhas = sorted(linhas, key=lambda x: -x["vezes"])[:limite]
    return {
        "termos": linhas,
        "total_linhas": len(linhas),
        "sobre_os_dados": _sobre(ini, fim_d, lojas, avisos),
    }


@ferramenta(titulo="Sugestão de reposição")
def sugestao_de_reposicao(
    categoria: str, inicio: str = "", fim: str = "", loja: str = "ambas", referencias_por_tamanho: int = 5
) -> dict:
    """Onde repor primeiro numa categoria: os tamanhos sem estoque que o cliente procurou, e as referências a
    repor em cada um.

    Ordem: primeiro a venda perdida (busca que zerou naquele tamanho e aviso de "quando chegar" de cliente),
    depois a procura (filtro e tamanho digitado). Tamanho sem estoque e sem procura no período fica em
    `sem_procura_no_periodo`, sem prioridade. Referências: primeiro as com aviso de cliente, depois as mais
    avaliadas (proxy de giro: a demo não tem venda). Sem quantidade: ela sai da venda (média x cobertura menos
    o estoque projetado, arredondada em lote), que a demo não tem. É ponto de partida, não decisão: diga as
    premissas. `categoria` (obrigatória): caminho na língua da loja, ex. "Feminino > Calçados > Tênis".
    `loja`: pt, en ou ambas. Calçado em pares, roupa e acessório em peças.
    """
    ini, fim_d, avisos_txt = periodo(inicio, fim)
    lojas = _lojas(loja)
    if not (categoria or "").strip():
        raise ValueError(
            "informe a categoria, ex. 'Feminino > Calçados > Tênis' (a reposição é por categoria)"
        )
    catalogo, caminho = _filtrar_categoria(fontes(lojas[0]).catalogo(), categoria)
    validos = {t for p in fontes(lojas[0]).catalogo() for t in p.get("grade") or []}
    filtro, zeradas, no_texto, texto_zerado, _ = _sinais_de_tamanho(ini, fim_d, lojas, validos)
    ids = {p["objectID"] for p in catalogo}
    avisos = [
        a
        for a in fontes("pt").avisos()
        if a.get("produto") in ids
        and a.get("loja") in lojas
        and f"{ini}" <= a.get("quando", "")[:10] <= f"{fim_d}"
    ]
    avisos_por: Counter[tuple[str, str]] = Counter((a["produto"], a["tamanho"]) for a in avisos)
    avisos_tam: Counter[str] = Counter(a["tamanho"] for a in avisos)
    unidade = "pares" if re.search(r"cal[cç]ados|shoes", caminho, re.I) else "peças"

    linhas, sem_procura = [], []
    for t in sorted({x for p in catalogo for x in p.get("grade") or []}, key=_ordem_tamanho):
        na_grade = [p for p in catalogo if t in (p.get("grade") or [])]
        sem = [p for p in na_grade if t not in (p.get("tamanhos_disponiveis") or [])]
        if not sem:
            continue
        procura = filtro[t] + no_texto[t] + avisos_tam[t]
        ruptura_pct = round(100 * len(sem) / len(na_grade), 1)
        if not procura:
            sem_procura.append({"tamanho": t, "ruptura_pct": ruptura_pct})
            continue
        refs = sorted(
            sem,
            key=lambda p: (-avisos_por[(p["objectID"], t)], -(p.get("avaliacoes") or 0), p.get("nome", "")),
        )
        linhas.append(
            {
                "tamanho": t,
                "venda_perdida": {
                    "buscas_que_zeraram": zeradas[t] + texto_zerado[t],
                    "avisos_de_cliente": avisos_tam[t],
                },
                "procura": procura,
                "produtos_na_grade": len(na_grade),
                "sem_estoque": len(sem),
                "ruptura_pct": ruptura_pct,
                "repor": [
                    {
                        "produto": p["objectID"],
                        "nome": p.get("nome", ""),
                        "cor": p.get("cor", ""),
                        "avisos": avisos_por[(p["objectID"], t)],
                        "avaliacoes": p.get("avaliacoes") or 0,
                        "outros_tamanhos_sem_estoque": [
                            x
                            for x in p.get("grade") or []
                            if x != t and x not in (p.get("tamanhos_disponiveis") or [])
                        ],
                    }
                    for p in refs[: max(1, min(int(referencias_por_tamanho), 20))]
                ],
            }
        )
    linhas.sort(
        key=lambda x: (
            -(x["venda_perdida"]["buscas_que_zeraram"] + x["venda_perdida"]["avisos_de_cliente"]),
            -x["procura"],
            -x["ruptura_pct"],
        )
    )
    avisos_txt.append(
        "a procura por filtro e texto é da loja inteira; o estoque e os avisos são da categoria"
    )
    return {
        "categoria": caminho,
        "unidade": unidade,
        "prioridades": linhas,
        "sem_procura_no_periodo": sem_procura,
        "premissas": [
            "sugestão é ponto de partida, não decisão: confira antes de pedir",
            "sem quantidade: numa loja real, média de venda x cobertura menos o estoque projetado, em lote",
            "avaliações como proxy de giro (a demo não tem venda); estoque por tamanho é sintético",
        ],
        "como_foi_calculado": "venda perdida = buscas que zeraram no tamanho (filtro ou digitado) + avisos "
        "de 'quando chegar' do assistente no período (um por produto, tamanho e dia); procura = filtro + "
        "tamanho digitado + avisos; ruptura = produtos da categoria com o tamanho na grade e sem estoque",
        "total_linhas": len(linhas),
        "sobre_os_dados": _sobre(
            ini,
            fim_d,
            lojas,
            avisos_txt,
            fonte="Algolia Analytics API + catálogo indexado + avisos do assistente",
        ),
    }


@ferramenta(titulo="Cobertura e confiança dos dados")
def cobertura_dos_dados() -> dict:
    """Até quando vai o analytics de cada loja (pt e en), o que o plano Free guarda e o estoque por grade.

    Use antes de concluir qualquer coisa ("não houve" e "fora da janela" são diferentes).
    """
    catalogo = fontes("pt").catalogo()
    com_estoque = sum(1 for p in catalogo if p.get("em_estoque"))
    skus = sum(len(p.get("grade") or []) for p in catalogo)
    skus_com_estoque = sum(len(p.get("tamanhos_disponiveis") or []) for p in catalogo)
    ini, fim_d, avisos = periodo()
    return {
        "catalogo": {
            "produtos": len(catalogo),
            "produtos_com_algum_estoque": com_estoque,
            "skus_por_tamanho": skus,
            "skus_com_estoque": skus_com_estoque,
            "estoque_e_sintetico": True,
            "lojas": "pt e en têm o mesmo catálogo e estoque (mesmos objectIDs); só o texto muda",
        },
        "limites_conhecidos": [
            "analytics do plano Free: 7 dias de retenção, atraso de 1 a 4 h",
            "estoque por tamanho vem do conector VTEX (quantidades sintéticas na demo)",
            "sem eventos de compra reais: taxas de conversão não são confiáveis nesta demo",
        ],
        "sobre_os_dados": _sobre(
            ini, fim_d, list(LOJAS), avisos, fonte="Algolia Analytics API + catálogo indexado"
        ),
    }


def _slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", sem_acento(texto)).strip("-")[:60]


@ferramenta(titulo="Criar ou remover sinônimo", escrita=True, destrutiva=True, so_local=True)
def sinonimo(
    acao: str,
    termos: list[str],
    entrada: str = "",
    loja: str = "pt",
    confirmado: bool = False,
    codigo: str = "",
) -> dict:
    """Cria ou remove um sinônimo de busca no índice. ESCRITA: exige confirmação.

    `acao`: criar ou remover. `loja`: pt ou en (o sinônimo é da língua do índice; padrão pt). `termos`: as
    palavras equivalentes (2 a 10). `entrada`: preencha só para
    sinônimo de mão única (quem busca a entrada vê também os termos; o contrário não vale). Regra: chame
    primeiro sem confirmar; a tool devolve o rascunho, o impacto estimado e um `codigo`. MOSTRE o rascunho à
    pessoa; só depois do sim dela chame de novo com confirmado=true e o mesmo codigo. Pedido ou queixa não é
    autorização. Só remove sinônimos criados por este copiloto (os da configuração ficam no repo).
    """
    acao = base.escolher(acao, ["criar", "remover"], "acao")
    f = fontes(_lojas(loja, ambas=False)[0])
    termos = [t.strip() for t in termos if t and t.strip()]
    if not 2 <= len(termos) <= 10 and not (entrada and 1 <= len(termos) <= 10):
        raise ValueError("informe de 2 a 10 termos (ou 1 a 10 com entrada, para mão única)")
    object_id = PREFIXO_COPILOTO + _slug((entrada + "-" if entrada else "") + "-".join(termos))
    if entrada:
        novo = {"objectID": object_id, "type": "oneWaySynonym", "input": entrada.strip(), "synonyms": termos}
    else:
        novo = {"objectID": object_id, "type": "synonym", "synonyms": termos}

    atual = f.sinonimo(object_id)
    if acao == "remover" and atual is None:
        raise ValueError(f"não existe sinônimo {object_id} criado pelo copiloto")
    catalogo = f.catalogo()
    impacto = {
        t: sum(
            1
            for p in catalogo
            if sem_acento(t) in sem_acento(p.get("nome", "") + " " + p.get("categoria", ""))
        )
        for t in ([entrada] if entrada else []) + termos
    }
    rascunho = {"acao": acao, "indice": f.indice, "sinonimo": novo if acao == "criar" else atual}
    if confirmado:
        base.exigir_confirmacao(confirmado, codigo, rascunho)  # código diferente do rascunho: nada é gravado
    else:
        return {
            "gravado": False,
            "mensagem": base.CONFIRMAR,
            "rascunho": rascunho,
            "ja_existe": atual,
            "produtos_com_cada_termo": impacto,
            "codigo": base.codigo_de(rascunho),
        }

    base.limitar_escrita("sinonimo")
    if acao == "criar":
        f.salvar_sinonimo(novo)
        desfazer = {"acao": "remover", "termos": termos, "entrada": entrada, "loja": loja}
    else:
        f.remover_sinonimo(object_id)
        desfazer = {"acao": "criar", "termos": termos, "entrada": entrada, "loja": loja}
    base.registrar("escritas.jsonl", tool="sinonimo", rascunho=rascunho, codigo=codigo)
    return {
        "gravado": True,
        "sinonimo": rascunho["sinonimo"],
        "como_desfazer": desfazer,
        "observacao": "vale para a busca em alguns segundos. Para manter depois de reconstruir o índice, "
        "copie para ingest/config/sinonimos.json (a configuração do repo é a fonte da verdade)",
    }


@ferramenta(titulo="Reportar problema", escrita=True)
def reportar_problema(
    o_que_esta_errado: str, valor_visto: str = "", valor_esperado: str = "", confirmado: bool = False
) -> dict:
    """Registra que um número ou resposta do copiloto está errado, com as últimas chamadas como contexto.

    Escreva como a pessoa disse, sem completar. MOSTRE o texto e só chame com confirmado=true depois do sim.
    """
    if not (o_que_esta_errado or "").strip():
        raise ValueError("diga o que está errado")
    reporte = {
        "o_que_esta_errado": o_que_esta_errado.strip()[:2000],
        "valor_visto": valor_visto[:500],
        "valor_esperado": valor_esperado[:500],
    }
    if confirmado is not True:
        return {"gravado": False, "mensagem": base.CONFIRMAR, "rascunho": reporte}
    base.limitar_escrita("reportar_problema")
    base.registrar("reportes.jsonl", **reporte, ultimas_chamadas=base.ultimas_chamadas(3))
    return {"gravado": True, "mensagem": "registrado com as 3 últimas chamadas como contexto"}


# --------------------------------------------------------------------------- assistente da loja (/loja/mcp)

MAX_AVISOS = 5000  # a demo é pública: teto de records no índice de avisos


@ferramenta(titulo="Avisar quando chegar", escrita=True, alvo=servidor_loja)
def avisar_quando_chegar(produto: str, tamanho: str, loja: str = "pt", confirmado: bool = False) -> dict:
    """Registra que o cliente quer este produto num tamanho que está sem estoque, para a loja repor.

    `produto`: o objectID do produto mostrado pela busca. `tamanho`: o tamanho pedido. `loja`: pt ou en.
    Use só quando o tamanho pedido estiver esgotado. Chame com confirmado=true apenas depois de o cliente
    dizer que quer o aviso; sem isso, a tool devolve o que seria registrado. A demo não guarda contato: diga
    ao cliente que numa loja real o aviso iria por e-mail.
    """
    lj = _lojas(loja, ambas=False)[0]
    p = next((x for x in fontes(lj).catalogo() if x.get("objectID") == (produto or "").strip()), None)
    if p is None:
        raise ValueError(f"produto '{produto}' não existe: use o objectID de um produto mostrado pela busca")
    t = (tamanho or "").strip().upper()
    if t not in (p.get("grade") or []):
        raise ValueError(
            f"tamanho '{tamanho}' não existe para este produto. Grade: {', '.join(p.get('grade') or [])}"
        )
    if t in (p.get("tamanhos_disponiveis") or []):
        raise ValueError(f"o tamanho {t} está em estoque: não precisa de aviso, ofereça o produto")
    aviso = {
        "produto": p["objectID"],
        "nome": p.get("nome", ""),
        "cor": p.get("cor", ""),
        "categoria": (p.get("categorias") or {}).get("lvl2") or (p.get("categorias") or {}).get("lvl1", ""),
        "tamanho": t,
        "loja": lj,
    }
    if confirmado is not True:
        return {
            "registrado": False,
            "mensagem": "pergunte ao cliente se quer o aviso; só então confirme",
            "aviso": aviso,
        }
    if len(fontes("pt").avisos()) >= MAX_AVISOS:
        raise ValueError("a demo atingiu o limite de avisos registrados; agradeça e siga sem registrar")
    base.limitar_escrita("avisar_quando_chegar", maximo=30, minutos=10)
    agora = dt.datetime.now(dt.UTC)
    # um aviso por produto, tamanho, loja e dia: repetir no mesmo dia regrava o record, não infla a demanda
    fontes("pt").gravar_aviso(
        {
            "objectID": f"{p['objectID']}-{t}-{lj}-{agora:%Y%m%d}",
            **aviso,
            "quando": agora.isoformat(timespec="seconds"),
        }
    )
    base.registrar("avisos.jsonl", **aviso)
    return {
        "registrado": True,
        "aviso": aviso,
        "mensagem": "aviso registrado para a reposição. Esta é uma loja de demonstração: não guardamos "
        "contato, numa loja real o aviso iria por e-mail",
    }
