# Dashboard setup

What the code cannot create on its own: API keys (creating a key needs the admin key, which this project never
uses), the Agent Studio agent and the scheduled synthetic traffic. Everything else (indices, settings, synonyms,
rules) is applied from the repository by `uv run python -m ingest.indexar --aplicar`. Menu names may differ
slightly between dashboard versions.

## API keys

Created in Settings, API Keys, All API Keys, New API key. Each key gets only what its component needs.

| Key | Used by | ACL | Indices | Other restrictions |
| --- | --- | --- | --- | --- |
| Write API key (default) | ingestion, local copilot | default | all | never in the browser or on the server of the public copilot |
| Store search key | storefront (`NEXT_PUBLIC_ALGOLIA_SEARCH_KEY`) | `search` | the six product indices | referer "starting with" the store domain, 100 queries per IP per hour, 50 hits per query, no expiry |
| Chat key | storefront chat (`NEXT_PUBLIC_ALGOLIA_CHAT_KEY`) | `search` | `produtos_ptbr*`, `produtos_en*` | hit cap; **no referer and no IP limit**: the agent searches from Algolia's servers and gets a 401 with either |
| Copilot key | public copilot (`ALGOLIA_COPILOTO_KEY`, Fly secret) | `analytics`, `browse` | `produtos_ptbr*`, `produtos_en*` | the public mode refuses to start with a write key |
| Restock requests key | public copilot (`ALGOLIA_AVISOS_KEY`, Fly secret) | `addObject` | `produtos_ptbr_avisos` | the index is created by the first request |
| Synthetic traffic key | GitHub Actions (`ALGOLIA_SINTETICO_KEY`) | `search` | `produtos_ptbr`, `produtos_en` | query parameters `analyticsTags=sintetico`, 30 queries per IP per hour |

Algolia applies the per IP limit on each of the cluster's three servers, so the effective limit is up to three
times the value set.

## Shopping assistant (Agent Studio)

1. **LLM provider:** your own key (Anthropic in this demo), with a spending cap at the provider. The free test model
   only works inside the dashboard.
2. **Agent:** model Claude Sonnet 5; instructions pasted from [`agent/instrucoes.md`](../agent/instrucoes.md) (the
   repository is the source of truth; the dashboard keeps a copy); max steps per completion 15 (lower values cut
   the answer); max tokens 8,000.
3. **Tools:**
   - Algolia Search with `produtos_ptbr` and `produtos_en` (the agent picks the index by the language of the
     question). Check after publishing that the agent has it: an agent without the search tool invents products.
   - MCP server `https://copiloto-loja-demo.fly.dev/loja/mcp`, no authentication, tool `avisar_quando_chegar`,
     approval not required (the agent asks the shopper first and the tool only writes with `confirmado=true`).
4. **Safety controls:** rate limit of 12 requests per minute per IP and 60 per minute in total; approved domains:
   the store domain and `localhost`.
5. **Store variables** (Vercel): `NEXT_PUBLIC_ALGOLIA_AGENT_ID` and `NEXT_PUBLIC_ALGOLIA_CHAT_KEY`.

The published configuration can be checked with `GET https://{APP_ID}.algolia.net/agent-studio/1/agents/{AGENT_ID}`
(write key; the request needs a `User-Agent` header).

## Synthetic traffic (GitHub Actions)

The workflow [`trafego-sintetico.yml`](../.github/workflows/trafego-sintetico.yml) runs four times a day and only
when the repository variable `TRAFEGO_SINTETICO` is `ligado`. Secrets: `ALGOLIA_APP_ID` and
`ALGOLIA_SINTETICO_KEY`. Before sending anything, `sintetico/rodar.py` reads the key's own restrictions from the
API and refuses a key with more than `search` or without the forced analytics tag. To test it once: Actions,
trafego-sintetico, Run workflow (11 searches from the monthly quota). To stop it: delete the variable.

## Merchandiser copilot (Fly.io)

`fly secrets set` for `ALGOLIA_APP_ID`, `ALGOLIA_COPILOTO_KEY` and `ALGOLIA_AVISOS_KEY`, then
`fly deploy --remote-only --ha=false`. The machine suspends when idle and resumes on the next request.
