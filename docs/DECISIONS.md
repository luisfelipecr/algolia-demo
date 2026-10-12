# Decisions, discarded paths and known limitations

The main design decisions behind the demo, what was tried and dropped, and what is still missing. Detailed notes
in Portuguese: [`CONTRATO-INDICE.md`](./CONTRATO-INDICE.md) (index contract), [`fontes/algolia.md`](./fontes/algolia.md)
(verified Algolia facts, including where the product behaved differently from the docs),
[`fontes/vtex.md`](./fontes/vtex.md) (VTEX APIs) and [`LICOES.md`](./LICOES.md) (lessons from MCP servers in
production).

## Search and data model

- **One record per style and color.** Photos are per color and the color plus size filter stays exact inside the
  record. One record per SKU would give 7,635 records with visual duplicates; one per style would lose the photo
  and the exact color filter. Sizes are nested SKUs with a stock flag.
- **`pt`, not `pt-br`,** in `queryLanguages`, `indexLanguages`, `ignorePlurals` and `removeStopWords`: Algolia
  handles plurals for `pt` and not for `pt-br`.
- **Gender agreement as synonyms** ("vermelho" and "vermelha", "preto" and "preta"), which plurals do not cover.
- **Sizes in stock are searchable** and words such as "tamanho" and "size" are optional, so "tênis 39" returns
  only sneakers with size 39 in stock. Before, the size was only a facet and the query returned nothing.
- **One index per language,** sharing record IDs, so the language switch keeps the shopper on the same product.
  Prices stay in reais and sizes stay Brazilian in both: it is the same store.
- **Settings, synonyms and rules live as code** and the connector applies only what changed: on the Free plan,
  every settings update on an index with replicas took from minutes to 27 minutes to publish.
- **Search runs in the browser only,** with a key restricted by index, referer and rate per IP. Server rendering
  with that key failed (the referer restriction rejects server requests).

## Shopping assistant (Agent Studio)

- **Claude Sonnet 5, one agent for both languages,** 15 steps per answer. With the same instructions, a smaller
  model invented a sale, answered an English question in Portuguese and showed more than three products.
- **Its own search key:** search only, the store indices, a hit cap, and no referer or IP limit. With those two
  restrictions the agent gets a 401, because it searches from Algolia's servers. LLM cost is capped by the agent
  rate limits, approved domains and a spending cap on the provider key.
- **No prompt suggestions while typing:** they would call the LLM on every search. The chat opens with three fixed
  questions per language instead.
- **"Let me know when it is back"** goes through a second MCP endpoint (`/loja/mcp`) that only exposes that tool,
  so the shopping assistant never sees the merchandiser tools. It records a restocking signal, keeps no contact
  details, and writes only after the shopper says yes.

## Merchandiser copilot (MCP)

- **Public, read only, no login,** on Fly.io with its own key (analytics and browse only; the public mode refuses
  to start with a write key). Claude and ChatGPT both accept a connector without authentication; ChatGPT does not
  accept a fixed key. Synonym writes exist only in the local mode, behind a confirmation code tied to the exact
  draft shown.
- **Every answer states its period, freshness and source,** because the Free plan keeps seven days of analytics.
  A value that does not exist (category, size, store) fails with the list of valid values instead of returning
  zero.
- **Diagnoses come from the data, not from the model.** Tested in four rounds on Claude and ChatGPT, every wrong
  conclusion traced back to a tool that said too little:
  - "no results with a filter" read as a broken filter, when it was a size out of stock: the tool now says which
    filter emptied the search and checks it against the catalog;
  - a search that failed before a configuration fix still counted as a problem: the tool now checks whether the
    same search finds products today;
  - stockout by size mixed footwear and clothing (size 39 exists in both): stock now comes per department;
  - a finding based only on synthetic traffic looked real: every line now says how many of its searches are
    synthetic.
- **Restocking suggestion without quantities.** Lost sales first (searches that hit a stockout and shopper
  requests), then demand. Quantities come from sales, which the demo does not have, so the tool lists what to
  restock and says so.

## Data honesty

- **The catalog is public sample data,** translated with a versioned translation memory; sources pinned by commit
  and checksum. Stock quantities are synthetic.
- **Synthetic traffic is declared.** A scheduled job sends searches and clicks written by hand from the catalog,
  four times a day. The key it uses forces the analytics tag `sintetico`, the user tokens are `sintetico-NN`, and
  the copilot reports the synthetic share of every period and every line.
- **Internal product page queries stay out of analytics** (`analytics: false`), so they are not counted as
  shopper searches.

## Discarded paths

- A higher rule count: the pricing page says 10 rules per index on the Free plan, the API refuses the fourth.
- A rule that turns a size into a facet filter: it applies the filter but keeps the word in the query.
- The chat widget's `id` prop to keep one conversation per language: persistence keys on the agent ID; the store
  marks the language in the session instead.
- Inline widget props with `useInstantSearch` on a whole page: a re-render loop that held about 115% CPU with the
  page idle and no network traffic. Everything passed to a widget is now a module constant.
- A typo threshold of 0.75 in the no-result diagnosis: it matched "sapatenis" to "sapatos", which is a different
  product. The threshold is 0.80.
- Product photos from the original dataset: all of them return 404. The catalog uses the same SKUs' photos from the
  commercetools Sunrise sample data.

## Known limitations

- **No sales data,** so no quantities, conversion rates or revenue. Ratings stand in for popularity.
- **The VTEX connector reads a mock** of the Legacy Search API; a client for a live store would plug in behind the
  same interface. That API also stops at 2,500 products, so a large catalog needs the SKU by SKU load VTEX
  recommends for external integrations.
- **Seven days of analytics** on the Free plan, with a delay of one to four hours.
- **The copilot's first call after the machine resumes** can take several seconds while it reloads the catalog.
- **Not built yet:** autocomplete with Query Suggestions, visually similar products, OAuth for the copilot.
- **Public keys can be used by others:** the chat key has no IP limit (the agent needs that), and the copilot has
  no login. Both are read only on a sample store; on the Free plan, an exhausted quota blocks the app instead of
  billing it.
- **Photos are hotlinked** from the commercetools sample data bucket and may disappear; the store falls back to a
  color swatch.
