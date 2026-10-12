"""Produto VTEX → records da Algolia, um por produto × cor (contrato em docs/CONTRATO-INDICE.md).

Os SKUs são agrupados pela especificação `Cor`: numa loja com um produto por cor sai um record por produto;
numa loja canônica (SKUs cor × tamanho) sai um record por cor do produto. O tamanho fica aninhado em `skus` e
vira dois facets: `grade` (todos os tamanhos cadastrados) e `tamanhos_disponiveis` (só os com estoque), o par
que mede demanda perdida por tamanho.
"""

import re
import unicodedata

# Média bayesiana da nota: produto com poucas avaliações puxa para a média do catálogo
MINIMO_AVALIACOES = 10


def _slug(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")


def media_do_catalogo(avaliacoes: dict[str, dict]) -> float:
    notas = [a["average"] for a in avaliacoes.values() if a["totalCount"]]
    return sum(notas) / len(notas) if notas else 0.0


def nota_bayesiana(media: float, total: int, media_catalogo: float) -> float:
    m = MINIMO_AVALIACOES
    return round((media * total + media_catalogo * m) / (total + m), 1)


def _especificacao(item: dict, produto: dict, nome: str) -> str:
    """Valor de uma spec no SKU; se a loja cadastrou como spec de produto, cai para o produto."""
    valores = item.get(nome) or produto.get(nome) or [""]
    return valores[0]


def _categorias(produto: dict) -> tuple[dict[str, str], str]:
    mais_profunda = max(produto["categories"], key=lambda c: c.count("/"))
    partes = [p for p in mais_profunda.split("/") if p]
    niveis = {f"lvl{i}": " > ".join(partes[: i + 1]) for i in range(len(partes))}
    return niveis, partes[-1]


def registros(produto: dict, avaliacao: dict | None, media_catalogo: float) -> list[dict]:
    grupos: dict[str, list[dict]] = {}
    for item in produto["items"]:
        grupos.setdefault(_especificacao(item, produto, "Cor"), []).append(item)

    categorias, categoria = _categorias(produto)
    avaliacao = avaliacao or {"average": 0, "totalCount": 0}
    saida = []
    for cor, itens in grupos.items():
        ofertas = [(i, i["sellers"][0]["commertialOffer"]) for i in itens]
        skus = [
            {
                "id": i["itemId"],
                "tamanho": _especificacao(i, produto, "Tamanho"),
                "em_estoque": o["IsAvailable"],
            }
            for i, o in ofertas
        ]
        # preço efetivo único: o menor preço de venda do grupo, com o preço cheio do mesmo SKU
        _, oferta = min(ofertas, key=lambda io: io[1]["Price"])
        preco, preco_de = oferta["Price"], oferta["ListPrice"]
        imagens = itens[0]["images"]
        saida.append(
            {
                "objectID": f"{produto['productId']}-{_slug(cor) or 'sem-cor'}",
                "produto_id": produto["productId"],
                "referencia": produto["productReference"],
                "nome": produto["productName"],
                "marca": produto["brand"],
                "descricao": produto["description"],
                "categoria": categoria,
                "categorias": categorias,
                "genero": _especificacao(itens[0], produto, "Gênero"),
                "cor": cor,
                "grupo_cor": _especificacao(itens[0], produto, "Grupo de cor"),
                "amostra_cor": _especificacao(itens[0], produto, "Amostra de cor"),
                "imagem": imagens[0]["imageUrl"] if imagens else "",
                "url": produto["link"],
                "preco": preco,
                "preco_de": preco_de,
                "em_promocao": preco < preco_de,
                "desconto_pct": round(100 * (1 - preco / preco_de)) if preco < preco_de else 0,
                "grade": [s["tamanho"] for s in skus],
                "tamanhos_disponiveis": [s["tamanho"] for s in skus if s["em_estoque"]],
                "em_estoque": any(s["em_estoque"] for s in skus),
                "skus": skus,
                "nota": avaliacao["average"],
                "avaliacoes": avaliacao["totalCount"],
                "avaliacao_bayes": nota_bayesiana(
                    avaliacao["average"], avaliacao["totalCount"], media_catalogo
                ),
            }
        )
    return saida
