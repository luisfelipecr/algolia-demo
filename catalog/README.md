# Catalog

Builds the demo store catalog in Brazilian Portuguese, in the shape of a VTEX catalog, from Algolia's public
fashion dataset. The output is what the VTEX connector reads (through a mock of the VTEX API) and indexes into
Algolia.

```bash
uv run python -m catalog.build
uv run pytest
```

The build downloads the source dataset if needed and writes `data/vtex/` and `data/vtex/en/` (gitignored, rebuilt
on every run).

## Source

[`algolia/datasets`](https://github.com/algolia/datasets/tree/master/ecommerce-federated), folder
`ecommerce-federated`, pinned at commit `32bfb56` with a sha256 check: 1,787 fashion products in English, prices in
EUR. The dataset has no license file; its README invites people to use the data to build something with
Algolia, which is what this demo does. No real store or brand catalog is used.

Product photos: the image URLs in the Algolia dataset no longer resolve (every one returned 404 on 2026-10-08).
The dataset's SKUs come from the commercetools
[Sunrise sample data](https://github.com/commercetools/commercetools-sunrise-data) (Apache-2.0), whose photos are
still published, so each product uses the photo of the same SKU from Sunrise's `data/products.csv` (pinned at
commit `9074de2` with a sha256 check). All 1,787 photo URLs answered 200 and the product names match. Photos are
hotlinked, not copied into this repository.

## What the build does

- **Translation.** Product names and descriptions come from a versioned translation memory,
  `catalog/traducoes/pt-BR.json` (English text, Portuguese text, keyed by a hash of the English). It was written
  once with an LLM, checked automatically (brand and model names kept, no English leftovers) and reviewed by
  sampling. The build fails if any source text has no translation. Colors, categories and gender use a fixed
  glossary in `catalog/glossario.py`, so the same term is used in names, facets and categories.
- **Prices.** EUR to BRL at a fixed rate: 5.5867, the Banco Central do Brasil PTAX selling rate of 2026-10-07.
  Prices are rounded to the usual Brazilian shop format ending in ,90. Discounted prices keep the source discount
  (10%).
- **Sizes.** The source applies a full template size range of each sizing system to every product, so the
  conversion to Brazilian sizes is a documented convention of this demo, not a manufacturer table. Footwear EU
  sizes become BR minus 1 (women) or minus 2 (men), half sizes merge into the size below, and the range is cut to
  33 to 40 (women) and 37 to 44 (men). US footwear follows the Nike Brasil size chart. Letter sizes map to PP, P,
  M, G, GG and XGG. Details and sources are in `catalog/grade.py`.
- **VTEX shape.** Each source record (one style in one color) becomes a VTEX product, and each Brazilian size
  becomes a SKU with the `Cor` and `Tamanho` specifications. The product follows the Legacy Search API
  (`/api/catalog_system/pub/products/search`), with prices and stock in `sellers[].commertialOffer`. VTEX's
  canonical model is one product with color and size SKUs; one product per color is an older pattern that many
  stores still have. The connector groups SKUs by color, so it handles both.

## English version

The store also has an English version at `/en`. The build writes it to `data/vtex/en/` with the same products,
SKUs, prices and stock, and the original English text of the source instead of the translation. The source text
has some leftover German words (hosen, handtaschen, und), misspelled colors (whiet, oliv) and mismatched quotes,
so a short fixed list in `catalog/glossario.py` corrects them. Specification names (`Cor`, `Tamanho`) stay the
same in both languages; only their values change. Prices stay in BRL and sizes stay Brazilian, because it is the
same Brazilian store.

## What is synthetic

- Stock quantities. The source only says whether each size is in stock; the build turns that into a
  deterministic quantity from 1 to 12.
- VTEX ids, store URLs and the seller.
- Ratings are the source review data, exposed in the shape of the VTEX Reviews and Ratings app.

## Known source quirks, kept as they are

- Some product names do not match their category (flip flops under loafers, lace-up shoes under sneakers).
- The same style in the same color sometimes appears more than once with a different print or price.
- Only accessories are on sale in the source.
- Product photos are hotlinked from the commercetools sample data bucket and may disappear; the store falls back
  to a color swatch with a category icon.
