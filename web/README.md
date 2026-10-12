# Storefront

Next.js storefront built with React InstantSearch, in two languages: Brazilian Portuguese at `/` (index
`produtos_ptbr`) and English at `/en` (index `produtos_en`, same record IDs). It has a search box, hierarchical
categories, sizes in stock, color, brand, price range, a sale toggle, sorting by price, pagination, a product page
with other colors of the same style, and the Agent Studio shopping assistant behind the chat button.

```bash
cp .env.example .env.local   # app ID, search key, index names and the assistant's variables
npm ci
npm run dev
npm run lint && npm run typecheck && npm run build
```

Without `NEXT_PUBLIC_ALGOLIA_AGENT_ID` and `NEXT_PUBLIC_ALGOLIA_CHAT_KEY` the chat button is hidden; the rest of the
store works.

Searches run only in the browser. In production the search key is restricted (search ACL only, the store indices,
referer, rate limit per IP); the chat has its own search-only key, because the agent searches from Algolia's
servers. See [`docs/DASHBOARD-SETUP.md`](../docs/DASHBOARD-SETUP.md).

Everything passed to an InstantSearch widget (`transformItems`, `translations`, `items`) is a module constant,
built once per language in `lib/idioma.tsx`: a prop recreated on every render registers as a new widget and starts
a re-render and search loop.
