# Manual de engenharia (AGENTS.md)

Manual de engenharia deste repositório, **agnóstico de agente**: vale para qualquer IA que abrir esta pasta
(Claude Code, Codex, Grok…). Os arquivos de entrada de cada CLI (`CLAUDE.md` e afins) são ponteiros finos;
conhecimento durável se escreve **aqui** ou em `docs/`.

Responder e comentar em **português-BR**. Identificadores e comentários do código em português, de propósito: a
demo é de uma loja brasileira. Em inglês: o **README**, `docs/DECISIONS.md`, `docs/DASHBOARD-SETUP.md` e os READMEs
de pacote; as notas de projeto em `docs/` ficam em português.

## O que é

Demo pública de **busca agêntica para varejo de moda e calçados em português**, construída sobre a
**Algolia**, portfólio do Luis em busca e agentes para varejo. A demo precisa provar três coisas a quem a abrir:

1. **Domínio do produto Algolia:** busca em pt-BR bem configurada, InstantSearch, Agent Studio.
2. **Integração:** um conector **VTEX → Algolia** (a VTEX domina o e-commerce grande no Brasil e não tem
   conector oficial da Algolia).
3. **Visão de operador:** um **MCP de "copiloto do merchandiser"** que transforma dados de busca em decisão
   de compra e de estoque (o Luis operou varejo por mais de uma década e construiu um sistema de reposição
   por SKU/cor/tamanho em 2020).

- **Público:** nada de dado de cliente, dado de negócio nem credencial no repositório.

## Ao começar uma sessão

- [`README.md`](./README.md) e [`docs/DECISIONS.md`](./docs/DECISIONS.md): o que a demo é, as decisões, os caminhos
  descartados e as limitações conhecidas.
- [`docs/LICOES.md`](./docs/LICOES.md): o que três servidores MCP em produção ensinaram.
- [`docs/fontes/algolia.md`](./docs/fontes/algolia.md): fatos verificados da Algolia (plano Free, MCP,
  Agent Studio, português). **Ler antes de assumir que uma feature existe no plano Free.**
- [`docs/CONTRATO-INDICE.md`](./docs/CONTRATO-INDICE.md) e [`docs/fontes/vtex.md`](./docs/fontes/vtex.md): formato
  do record e fatos verificados da VTEX (Legacy Search API, produto × SKU).

## Estrutura

| Pasta | O que vai ali |
| --- | --- |
| `catalog/` | Script que transforma o dataset de moda da Algolia em catálogo pt-BR (tradução, R$, tamanhos BR) no formato VTEX produto → SKU, e o **mock** da API de catálogo da VTEX |
| `ingest/` | Conector VTEX → Algolia (Python, client `algoliasearch`) e a configuração do índice |
| `web/` | Loja em Next.js + `react-instantsearch` (+ widget `Chat` do Agent Studio) |
| `agent/` | Instruções e configuração do agente do Agent Studio (versionadas; o dashboard é cópia) |
| `copiloto/` | MCP do merchandiser (Python, SDK `mcp` 2.x, Streamable HTTP). Público no Fly.io (`Dockerfile` e `fly.toml` na raiz), sem login e só leitura em `/mcp`; em `/loja/mcp`, só a tool de aviso de estoque do assistente. Não se chama `mcp/` porque a pasta sombrearia o pacote `mcp` do SDK |
| `sintetico/` | Tráfego sintético e declarado para o analytics (cenário à mão, `analyticsTags: sintetico`, chave própria que impõe a tag); agendado em `.github/workflows/`, desligado até a variável `TRAFEGO_SINTETICO=ligado` |
| `evals/` | Golden set de consultas em português (expectativas semânticas, não circulares) e relatórios por data |
| `docs/` | Plano, handover, lições, fontes |
| `data/` | Dataset bruto e intermediários. **Gitignored.** |

## Stack

- **Python ≥ 3.12 com `uv`** para catálogo, conector e MCP; `pytest`, `ruff`.
- **Next.js + `react-instantsearch` + `algoliasearch` (liteClient)** para a loja. Widgets oficiais e o tema
  `satellite` por baixo; por cima, visual de loja profissional (decidido com o Luis em 08/10/2026: a loja tem de
  parecer uma loja de verdade). CSS num arquivo só, com
  tokens em `:root` e classes `ais-*` conferidas no pacote instalado; sem biblioteca de UI; CSS próprio e
  explicável. Busca só no navegador (ver `docs/DECISIONS.md`).
- **Algolia plano Free** (limites em `docs/fontes/algolia.md`). Deploy do front na Vercel.

## Comandos

```bash
uv run pytest && uv run ruff check .          # suíte Python (catalog, ingest, evals, copiloto)
uv run python -m catalog.build                # origens fixadas → data/vtex/ e data/vtex/en/ (mock da VTEX)
uv run python -m ingest.indexar               # ensaio; --aplicar escreve na Algolia (só o que mudou)
uv run python -m ingest.indexar --idioma en   # loja /en: produtos_en (mesmo objectID do pt)
uv run python -m evals.rodar                  # golden set pt: 1 multi-query = 34 buscas da cota
uv run python -m evals.rodar --idioma en      # golden set en: 14 buscas
uv run python -m sintetico.rodar              # ensaio do tráfego sintético; --aplicar gasta 11 buscas da cota
uv run python -m copiloto                     # MCP do merchandiser em stdio (--http PORTA para HTTP)
fly deploy --remote-only --ha=false           # copiloto público no Fly (app copiloto-loja-demo; só leitura)
npm --prefix web run dev                      # loja local (build/lint: run build, run lint)
```

## Regras

- **Português da Algolia:** usar `pt`, **não** `pt-br`, em `queryLanguages`, `indexLanguages`,
  `ignorePlurals` e `removeStopWords` (o `pt-br` não trata plurais; ver fontes).
- **Um índice por idioma** (`produtos_ptbr`, `produtos_en`), com o mesmo `objectID`; o que muda no idioma fica
  em `ingest/config/<idioma>/`. Textos da loja e props de widget por idioma em `web/lib/idioma.tsx`.
- **Free: 3 Rules por índice** (não 10, apesar do pricing). Palavra que só atrapalha ("tamanho", "size") vai em
  `optionalWords`, não em Rule.
- **Chaves** (criar chave exige admin: sempre no dashboard, pelo Luis; nunca imprimir valores):
  - **Write key:** ingestão e copiloto local (`.env`); a admin key não é usada pelo projeto.
  - **Search key restrita do site** (`NEXT_PUBLIC_ALGOLIA_SEARCH_KEY`): só `search`, índices, referer, rate limit
    por IP (dividido por 3); a Search key padrão tem `browse` e nunca vai para o front.
  - **Chave do chat** (`NEXT_PUBLIC_ALGOLIA_CHAT_KEY`): `search`, índices, `maxHitsPerQuery`, validade, **sem
    referer e sem limite por IP** (com eles o agente responde 401); o gasto com LLM fica no rate limit e nos
    approved domains do agente e no teto da chave do provedor.
  - **Chave do copiloto público** (`ALGOLIA_COPILOTO_KEY`, segredo no Fly): só `analytics` e `browse`; o modo
    público recusa subir com a Write key.
  - **Chave dos avisos** (`ALGOLIA_AVISOS_KEY`, segredo no Fly): só `addObject` em `produtos_ptbr_avisos`; grava
    o "avise-me quando chegar" do assistente (`/loja/mcp`), sem contato do cliente.
  - **Chave do sintético** (`ALGOLIA_SINTETICO_KEY`, secret do GitHub): só `search`, `analyticsTags=sintetico`
    imposto.
- **O índice tem de ser reconstruível a partir do repo** (catálogo, settings, sinônimos, Rules): o Free pode
  apagar dados de app inativo.
- **Dados honestos:** catálogo é público/sintético e o README diz a origem. Eventos de Insights gerados para a
  demo são **declarados como sintéticos**. Nunca publicar catálogo real de marca.
- **O assistente não inventa estoque nem preço.** Guardrail explícito nas instruções e nos evals.
- **Escrita via MCP só com confirmação** (mostrar o que vai mudar, esperar o sim, gravar com
  `confirmado=true`, logar). Leitura é o padrão.
- **Estilo dos textos públicos (README, descrições):** sem travessão nem `|` como separador.
- **React InstantSearch: tudo o que vai para widget é estável** (constante de módulo: `transformItems`,
  `translations`, `items`, `attributes`) e `useInstantSearch` só em componentes pequenos. O `useConnector`
  compara props com `dequal` e função por referência: prop recriada a cada render vira widget novo e entra em
  loop de re-render (em 08/10/2026 prendeu ~115% de CPU com a página parada, sem aparecer na rede).
- **Cota de 10K buscas/mês:** evals, testes manuais e o agente gastam busca; prefira browse, Analytics API e
  respostas guardadas (`evals.rodar --de-arquivo`).
- Commits pequenos, por pathspec explícito, prefixo conventional + descrição em pt-BR.

## Estado e histórico

Criado em 07/10/2026 (estrutura base, docs, contexto). Em 07–08/10/2026:
catálogo, conector, índice, loja publicada na Vercel, golden set e copiloto local. Em 08–09/10/2026: loja em
inglês (`/en`, índice `produtos_en`), assistente do Agent Studio na loja e copiloto público no Fly.io. Em 12/10/2026:
tráfego sintético declarado, sugestão de reposição e "avise-me quando chegar". Decisões e limitações em
[`docs/DECISIONS.md`](./docs/DECISIONS.md).
