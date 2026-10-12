# VTEX: fatos verificados (07/10/2026)

Levantados nas specs OpenAPI oficiais ([vtex/openapi-schemas](https://github.com/vtex/openapi-schemas)) e no
help center da VTEX, para o mock e o conector. **[não confirmado]** marca o que não foi verificado.

## Legacy Search API: `GET /api/catalog_system/pub/products/search`

- A spec chama de "Legacy Search API"; a operação não está marcada como `deprecated`.
- Produto: `productId` (string), `productName`, `brand`, `brandId`, `linkText`, `productReference`,
  `productReferenceCode`, `categoryId`, `productTitle`, `metaTagDescription`, `releaseDate`, `categories`
  (`"/Dep/Cat/"`), `categoriesIds` (`"/1/2/"`), `link`, `description`, `allSpecifications`,
  `allSpecificationsGroups`, `items[]`. Especificação de produto vira chave no topo com lista de valores.
- Item (SKU): `itemId`, `name`, `nameComplete`, `complementName`, `ean`, `referenceId: [{Key: "RefId", Value}]`,
  `measurementUnit`, `unitMultiplier`, `isKit`, `images[]` (`imageId`, `imageLabel`, `imageTag`, `imageUrl`,
  `imageText`), `sellers[]`. Especificação de SKU vira chave no item (`"Cor": [...]`) e `variations` lista os
  nomes; a caixa do nome segue o cadastro da loja (o schema de exemplo da spec usa `COR`/`TAMANHO`).
- `sellers[].commertialOffer` (grafia da VTEX): `Price`, `ListPrice`, `PriceWithoutDiscount`,
  `AvailableQuantity`, `IsAvailable`, entre outros.
- Paginação `_from`/`_to`, **no máximo 50 por resposta** e `_from` ≤ 2.500: catálogo maior que 2.500 produtos não
  sai inteiro por aqui. O mock da demo tem 1.787.

## Outros endpoints

- `GET /api/catalog_system/pvt/products/GetProductAndSkuIds?_from&_to&categoryId`: `{data: {productId: [skuIds]},
  range: {total, from, to}}`, até 250 por página.
- `GET /api/catalog_system/pvt/sku/stockkeepingunitbyid/{skuId}` ("SKU and context"): `SkuSpecifications`/
  `ProductSpecifications` como `{FieldName, FieldValues, ...}`, `AlternateIds{Ean, RefId}`, imagens, categorias.
- `GET /api/catalog/pvt/product/{productId}`: `Id`, `Name`, `RefId`, `LinkId`, `DepartmentId`, `CategoryId`,
  `BrandId`, `Description`, `ReleaseDate`, `IsActive`...
- Preço: `GET /pricing/prices/{itemId}` (`basePrice`, `listPrice`, `costPrice`, `fixedPrices[]`). Estoque:
  `GET /api/logistics/pvt/inventory/skus/{skuId}` (`balance[]` com `totalQuantity`, `reservedQuantity`).
- **Carga completa recomendada pela VTEX para integrações externas:** listar SKUs por canal de venda → "SKU and
  context" → produto → simulação de fulfillment para preço e estoque
  ([guia](https://developers.vtex.com/docs/guides/external-marketplace-integration-product-load)). O conector real
  para loja grande deve seguir esse caminho; a demo usa a Legacy Search API pela simplicidade.
- Intelligent Search API v0: a spec diz que a v1 a substitui.
- Conectores de busca de terceiros (Constructor, Doofinder) usam a Catalog API, mas o endpoint exato
  **[não confirmado]**.

## Modelagem produto × SKU

- O modelo canônico da VTEX é **um produto com SKUs cor × tamanho**
  ([produto × SKU](https://help.vtex.com/docs/tutorials/what-is-the-difference-between-product-and-sku)).
- "Um produto por cor" é descrito pela própria VTEX como **workaround antigo**, hoje substituído por "detaching
  SKUs by specification", útil para lojas de roupa separarem por cor
  ([doc](https://help.vtex.com/en/docs/tutorials/detaching-skus-by-specification)). Quanto ainda é comum
  **[não confirmado]**. A demo usa produto por cor (fiel ao dataset) e o conector agrupa por `Cor`.

## Câmbio usado no catálogo

PTAX do BCB, EUR, fechamento de 07/10/2026: compra 5,5851, **venda 5,5867** (conferido na API
`olinda.bcb.gov.br`). BCE no mesmo dia: 5,5953 BRL/EUR. O euro caiu cerca de 5% entre 02/10 e 05/10/2026.
