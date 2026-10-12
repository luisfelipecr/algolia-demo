"""Transforma o dataset de origem no catálogo de uma loja VTEX fictícia, em pt-BR (e em inglês, para /en).

Formato de saída: o produto da Legacy Search API da VTEX (`GET /api/catalog_system/pub/products/search`), com
`items[]` (SKUs) e `sellers[].commertialOffer` (preço e estoque), conforme a spec oficial em
github.com/vtex/openapi-schemas (`VTEX - Search API.json`). É a base do mock que o conector VTEX → Algolia lê.

Modelagem: cada record da origem (uma referência numa cor) vira um Product, e cada tamanho da grade BR vira um
SKU com as especificações Cor e Tamanho. É o padrão "um produto por cor", que a própria VTEX descreve como
legado (o canônico é um produto com SKUs cor × tamanho); o conector agrupa os SKUs pela especificação Cor,
então funciona nos dois casos.

Fotos: as do dataset da Algolia saíram do ar; cada produto usa a foto do mesmo SKU nos dados de exemplo
"Sunrise" da commercetools (ver `fonte.py`). Produto sem foto conhecida sai com `images` vazio.

O que é sintético e declarado no README: quantidades em estoque (derivadas do booleano `in_stock` da origem),
IDs numéricos da VTEX, URLs da loja e o vendedor.

Idioma: `idioma="en"` gera o mesmo catálogo (mesmos IDs, preços, SKUs e estoque) com o texto original em
inglês corrigido pelo glossário; só os valores mudam;
os nomes das especificações (Cor, Tamanho...) são os da loja.
"""

import hashlib
import re
import unicodedata
from decimal import Decimal

from catalog.glossario import (
    CORES,
    GENEROS,
    GENEROS_EN,
    PALAVRAS_EN,
    categoria_en,
    categoria_pt,
    cor_en,
    grupo_cor_en,
    grupo_cor_pt,
)
from catalog.grade import conversor, ordem
from catalog.precos import para_reais, preco_de_venda
from catalog.traducao import Memoria

LOJA = "https://loja-demo.example"
VENDEDOR = {"sellerId": "1", "sellerName": "Loja Demo", "sellerDefault": True}
PRIMEIRO_PRODUTO = 1001
SEM_MARCA = "Sem marca"
SEM_MARCA_EN = "No brand"
IDIOMAS = ("pt", "en")
_PALAVRAS = re.compile(r"\b(" + "|".join(PALAVRAS_EN) + r")\b", re.IGNORECASE)
# “101H“, ”Selma” e „Baker“ na origem: abre com qualquer aspa curva ou baixa, fecha com qualquer curva
_ASPAS = re.compile(r"[“”„]([^“”„]*)[“”]")


def slug(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")


def quantidade_sintetica(sku_origem: str, em_estoque: bool) -> int:
    """Estoque determinístico de 1 a 12 para o que a origem marca como em estoque; 0 para o resto."""
    if not em_estoque:
        return 0
    return 1 + int(hashlib.sha256(sku_origem.encode()).hexdigest(), 16) % 12


def _brl(valor: Decimal) -> float:
    return float(valor)


def _corrigir(m: re.Match) -> str:
    certa = PALAVRAS_EN[m.group(1).lower()]
    return certa.capitalize() if m.group(1)[0].isupper() else certa


def texto_en(texto: str) -> str:
    """Texto de origem limpo para a loja em inglês: sem sobra de alemão nem erro de grafia, aspas certas."""
    texto = _PALAVRAS.sub(_corrigir, texto)
    return _ASPAS.sub(r"“\1”", texto)


def _cor_no_fim(nome: str) -> bool:
    ultima = nome.rsplit(" ", 1)[-1].lower()
    return any(ultima in re.split(r"[-/ ]", c) for c in CORES if c)


class Catalogo:
    """IDs determinísticos (a origem está fixada num commit) para produtos, categorias e marcas."""

    def __init__(
        self,
        origem: list[dict],
        memoria: Memoria,
        imagens: dict[str, list[str]] | None = None,
        idioma: str = "pt",
    ):
        if idioma not in IDIOMAS:
            raise ValueError(f"idioma {idioma!r} desconhecido; válidos: {', '.join(IDIOMAS)}")
        self.idioma = idioma
        self.origem = sorted(origem, key=lambda r: r["objectID"])
        self.memoria = memoria
        # SKU → fotos (Sunrise da commercetools); as URLs de `image_urls` da origem estão fora do ar
        self.imagens = imagens or {}
        caminhos = set()
        for r in self.origem:
            partes = _caminho(r).split(" > ")
            caminhos.update(" > ".join(partes[: i + 1]) for i in range(len(partes)))
        self.categoria_id = {c: i + 1 for i, c in enumerate(sorted(caminhos))}
        marcas = sorted({r["brand"] or SEM_MARCA for r in self.origem})
        self.marca_id = {m: 2000001 + i for i, m in enumerate(marcas)}

    # textos por idioma; a estrutura (IDs, preço, grade, estoque) não depende deles

    def _categoria(self, caminho: str) -> str:
        return categoria_en(caminho) if self.idioma == "en" else categoria_pt(caminho)

    def _cor(self, r: dict) -> str:
        original = r["color"]["original_name"]
        return cor_en(original) if self.idioma == "en" else CORES[original]

    def _nome(self, r: dict, cor: str) -> str:
        if self.idioma == "en":
            # o nome em inglês da origem quase sempre já termina com a cor: a da origem vira a corrigida
            # ("multi" → "multicolor"); outra palavra de cor fica ("pink" para a cor "rose"); sem cor,
            # acrescenta
            nome = texto_en(r["name"])
            original = r["color"]["original_name"]
            if original and nome.lower().endswith(" " + original.lower()):
                nome = nome[: -len(original)].rstrip()
            elif _cor_no_fim(nome):
                return nome
            return f"{nome} {cor}" if cor else nome
        nome_base = self.memoria.traduzir(r["name"])
        return f"{nome_base} {cor}" if cor else nome_base

    def _descricao(self, r: dict) -> str:
        traduzida = self.memoria.traduzir(r["description"])
        # a tradução vazia marca texto de origem que não é descrição ("<p>Test</p>"), nas duas línguas
        if self.idioma == "en":
            return texto_en(r["description"]) if traduzida else ""
        return traduzida

    def _genero(self, r: dict) -> str:
        return (GENEROS_EN if self.idioma == "en" else GENEROS)[r["gender"]].capitalize()

    def _grupo_cor(self, r: dict) -> tuple[str, str]:
        filtro = r["color"]["filter_group"]
        return grupo_cor_en(filtro) if self.idioma == "en" else grupo_cor_pt(filtro)

    def _marca(self, r: dict) -> str:
        return r["brand"] or (SEM_MARCA_EN if self.idioma == "en" else SEM_MARCA)

    def produtos(self) -> list[dict]:
        return [self.produto(r, PRIMEIRO_PRODUTO + i) for i, r in enumerate(self.origem)]

    def avaliacoes(self) -> dict[str, dict]:
        """No formato do app Reviews and Ratings da VTEX (`average`, `totalCount`), fora do catálogo."""
        return {
            str(PRIMEIRO_PRODUTO + i): {
                "average": r["reviews"]["rating"],
                "totalCount": r["reviews"]["count"],
            }
            for i, r in enumerate(self.origem)
        }

    def arvore_categorias(self) -> list[dict]:
        """No formato de `GET /api/catalog_system/pub/category/tree/{nível}`."""

        def filhos(pai: str | None) -> list[dict]:
            nivel = 0 if pai is None else pai.count(" > ") + 1
            return [
                {
                    "id": cid,
                    "name": self._categoria(c).split(" > ")[-1],
                    "hasChildren": any(o.startswith(c + " > ") for o in self.categoria_id),
                    "url": f"{LOJA}/{'/'.join(slug(p) for p in self._categoria(c).split(' > '))}",
                    "children": filhos(c),
                }
                for c, cid in self.categoria_id.items()
                if c.count(" > ") == nivel and (pai is None or c.startswith(pai + " > "))
            ]

        return filhos(None)

    def produto(self, r: dict, product_id: int) -> dict:
        cor = self._cor(r)
        nome = self._nome(r, cor)
        genero = GENEROS[r["gender"]]  # a conversão de grade usa o gênero em pt
        grupo_cor, swatch = self._grupo_cor(r)
        marca = self._marca(r)
        caminho = _caminho(r)
        ancestrais = _ancestrais(caminho)
        link_text = f"{slug(nome)}-{product_id}"

        preco_de = para_reais(r["price"]["value"])
        desconto = -r["price"]["discount_level"] if r["price"]["on_sales"] else 0
        preco = preco_de_venda(preco_de, desconto)

        converter = conversor(r["available_sizes"], caminho, genero)
        por_tamanho: dict[str, list[dict]] = {}
        for v in r["variants"]:
            tamanho = converter(v["abbreviated_size"])
            if tamanho is not None:
                por_tamanho.setdefault(tamanho, []).append(v)

        imagens = [
            {
                "imageId": f"{product_id}{i}",
                "imageLabel": "",
                "imageTag": "",
                "imageUrl": url,
                "imageText": nome,
            }
            for i, url in enumerate(self.imagens.get(r["objectID"], []))
        ]
        itens = []
        for j, tamanho in enumerate(sorted(por_tamanho, key=ordem)):
            originais = por_tamanho[tamanho]
            em_estoque = [v for v in originais if v["in_stock"]]
            ref = (em_estoque or originais)[0]["sku"]
            qtd = quantidade_sintetica(ref, bool(em_estoque))
            item_id = f"{product_id}{j:02d}"
            itens.append(
                {
                    "itemId": item_id,
                    "name": tamanho,
                    "nameComplete": f"{nome} {tamanho}",
                    "complementName": "",
                    "ean": "",
                    "referenceId": [{"Key": "RefId", "Value": ref}],
                    "measurementUnit": "un",
                    "unitMultiplier": 1.0,
                    "isKit": False,
                    "images": imagens,
                    "Cor": [cor],
                    "Tamanho": [tamanho],
                    "variations": ["Cor", "Tamanho"],
                    "sellers": [
                        {
                            **VENDEDOR,
                            "addToCartLink": f"{LOJA}/checkout/cart/add?sku={item_id}&qty=1&seller=1",
                            "commertialOffer": {
                                "Price": _brl(preco),
                                "ListPrice": _brl(preco_de),
                                "PriceWithoutDiscount": _brl(preco_de),
                                "AvailableQuantity": qtd,
                                "IsAvailable": qtd > 0,
                            },
                        }
                    ],
                }
            )

        return {
            "productId": str(product_id),
            "productName": nome,
            "brand": marca,
            "brandId": self.marca_id[r["brand"] or SEM_MARCA],
            "linkText": link_text,
            "productReference": r["parentID"],
            "productReferenceCode": r["objectID"],
            "categoryId": str(self.categoria_id[caminho]),
            "productTitle": nome,
            "metaTagDescription": "",
            "releaseDate": None,
            "categories": ["/" + "/".join(self._categoria(c).split(" > ")) + "/" for c in ancestrais],
            "categoriesIds": [
                "/" + "/".join(str(self.categoria_id[a]) for a in reversed(_ancestrais(c))) + "/"
                for c in ancestrais
            ],
            "link": f"{LOJA}/{link_text}/p",
            "description": self._descricao(r),
            "Gênero": [self._genero(r)],
            "Grupo de cor": [grupo_cor],
            "Amostra de cor": [swatch],
            "allSpecifications": ["Gênero", "Grupo de cor", "Amostra de cor"],
            "allSpecificationsGroups": ["Especificações"],
            "items": itens,
        }


def _caminho(r: dict) -> str:
    hc = r["hierarchical_categories"]
    return hc.get("lvl2") or hc["lvl1"]


def _ancestrais(caminho: str) -> list[str]:
    partes = caminho.split(" > ")
    return [" > ".join(partes[: i + 1]) for i in range(len(partes))][::-1]
