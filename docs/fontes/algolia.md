# Algolia: fatos verificados (07/10/2026)

Levantamento feito em 07/10/2026 na documentação, pricing, changelog, GitHub e npm oficiais, e revisado no mesmo
dia por uma segunda pesquisa com verificação cruzada (antes de começar a construir). O que não foi confirmado está marcado
**[não confirmado]**. Revalidar antes de depender de um limite.

## Plano Free ([pricing](https://www.algolia.com/pricing), tabela lida célula a célula)

- 10K search requests/mês · 50K records · **10 KB por record** · 5K recommend requests/mês · 5K crawls/mês
- 1 app, 1 GB · **3 Rules por índice na prática** (o pricing diz 10; a API recusou a 4ª em 08/10/2026: "quota of
  rules has been exceeded… Current: 5, allowed: 3") · analytics retido **7 dias** · até 1.000 sinônimos por índice
  ([service limits](https://www.algolia.com/doc/guides/scaling/algolia-service-limits)). Índices: o pricing diz 20,
  a página de service limits diz 10 para o Free; contar com 10.
- **Inclui:** Query Suggestions, A/B Testing, sinônimos manuais, NLP, Recommend API (todos os modelos),
  Events/Insights API, Search/Event Analytics, **Agent Studio**.
- **Não inclui:** AI Synonyms, Dynamic Re-Ranking, Personalization, Virtual Replicas, Query Categorization,
  Visual Editor (Grow Plus) · **NeuralSearch**, Smart Groups, Dynamic Facets (só Elevate).
- **Sem cartão de crédito.** O nome antigo do plano era "Build" (1M records; os termos atuais do Free dão 50K).
- **Regiões no Free:** só US (East, West, Central), UK e EU West. O cluster do Brasil (São Paulo) existe, mas não
  no Free nem no pay-as-you-go; DSN também não. A região não muda por autosserviço (só pelo suporte)
  ([suporte](https://support.algolia.com/hc/en-us/articles/14298498947217)). O cadastro pelo dashboard **não
  pergunta a região**; a CLI aceita `--region` no `auth signup`/`application create`.
- **Cota estourada:** a aplicação Free fica bloqueada até o próximo ciclo, sem cobrança
  ([suporte](https://support.algolia.com/hc/en-us/articles/13646265384977)).
- **Inatividade:** os termos do Free permitem apagar os dados após 30 dias sem uso; o suporte fala em 2 meses.
  Buscas pela aba Index do dashboard não contam na cota e contam como atividade.
- **O que conta como search request:** cada tecla no search-as-you-type, a query vazia do carregamento, cada
  refinamento/página, Query Suggestions e `searchForFacetValues`. Não contam: browse, getSettings, getObjects,
  Analytics API, eventos de Insights e a aba Index do dashboard
  ([suporte](https://support.algolia.com/hc/en-us/articles/17245378392977)). Replicas padrão somam records.
- Logo da Algolia ao lado da busca no Free: exigido por artigos de suporte de 2023 e 2024; os termos atuais só
  falam de atribuição quando a cota estoura **[não confirmado se ainda vale]**. Barato cumprir (`PoweredBy`).
- Grow/Grow Plus: $0 de entrada, pay-as-you-go; plano pago exige meio de pagamento. Trial de 14 dias de "Premium
  Plan": os termos antigos continuam no ar, mas pricing e termos do Free não falam de trial **[não confirmado]**.

## Observado na indexação (08/10/2026)

- **Fila de indexação lenta no Free:** a 1ª carga completa (settings num índice vazio, replicas, sinônimos, Rules,
  1.787 records por `replace_all_objects`) publicou em cerca de 1 minuto. Depois, **todo `set_settings` no índice
  já populado com replicas** ficou `notPublished` de vários minutos a cerca de 27 minutos, mesmo com settings
  idênticas, sem erro nos logs de build e sem incidente no status público. Hipótese **[não confirmada]**: a mudança
  de settings reconstrói primário e replicas no cluster compartilhado. Por isso o indexador compara com o estado
  atual e só aplica o que mudou, e limita a espera.
- **`algoliasearch` Python 4.47:** `list_indices()` quebra na validação (pydantic) quando o app tem replicas
  (faltam `lastBuildTimeS`, `numberOfPendingTasks`, `pendingTask`); `list_indices_with_http_info()` e ler o JSON
  cru resolve.
- Mover o índice temporário sobre um primário com replicas mantém as replicas; o *copy* não leva a setting
  `replicas` ([operation-index](https://www.algolia.com/doc/rest-api/search/operation-index)).

- **Propagação de sinônimo não é instantânea:** depois de a task publicar, a busca simples já via o sinônimo
  novo, mas a mesma busca por multi-query ainda devolveu o resultado antigo por alguns minutos (08/10/2026).
  Causa **[não confirmada]** (consistência entre os 3 servidores ou cache). Eval logo depois de mudar
  configuração pode dar falso vermelho: repetir depois de alguns minutos antes de concluir.
- **`GET /2/searches/count` e o último dia** (12/10/2026): com `startDate` 06/10 e `endDate` 12/10 (hoje), a
  contagem omitiu as buscas do dia 12 (57), e o top searches do mesmo período as incluiu (65); com `endDate` 13/10,
  a lista diária trouxe o dia 12. Causa **[não confirmada]**. O copiloto pede até o dia seguinte e soma os dias do
  período.
- **`GET /2/filters/noResults` precisa de `search`** (12/10/2026): sem o parâmetro, devolveu `values` vazio no
  período; com `search=tenis feminino`, devolveu o filtro que zerou aquela busca (`tamanhos_disponiveis:34`). O
  copiloto pergunta busca a busca (as que têm `withFilterCount`).
- **Analytics API no Free funciona com a Write key** (ACL `analytics`): buscas sem resultado, buscas mais feitas,
  valores de filtro por atributo. Sem dados no período, `get_top_filters_no_results` devolve `{"values": null}`.

## Chaves de API

- O dashboard mostra Application ID, Search API Key e Write API Key; a Admin key fica em All API Keys.
- ACLs conferidas no app da demo com `GET /1/keys/{key}` (07/10/2026): a **Search key padrão** tem `search`,
  `listIndexes`, `settings` e `browse` (com `browse`, quem tiver a chave baixa o índice inteiro) e não pode ser
  editada. A **Write key** tem `search`, `browse`, `seeUnretrievableAttributes`, `listIndexes`, `analytics`,
  `logs`, `addObject`, `deleteObject`, `deleteIndex`, `settings`, `editSettings`: basta para records, settings,
  sinônimos e Rules (`saveSynonyms`/`saveRules` exigem `editSettings` na
  [spec](https://github.com/algolia/api-clients-automation/tree/main/specs/search/paths)). **Criar chave exige
  `admin`**, então a chave do front se cria no dashboard.
- Chave restrita aceita `acl`, `indexes` (com curinga), `referers`, `maxQueriesPerIPPerHour`, `maxHitsPerQuery`,
  `queryParameters` e `validity`. O rate limit por IP vale em cada um dos 3 servidores do cluster: dividir a meta
  por 3. Referer é falsificável; a defesa real é o rate limit. Secured API keys herdam as restrições da base.

## MCP oficial ([overview](https://www.algolia.com/doc/guides/model-context-protocol))

Três servidores gerenciados (Public, Productivity, DevEx) e o DocSearch MCP (beta desde 06/08/2026). "Uso conta
no plano" está escrito só para o Public MCP. Plano mínimo não documentado, mas o **Productivity MCP funciona no
Free**: habilitado e conectado no app da demo em 07/10/2026.

- **Public MCP** ([doc](https://www.algolia.com/doc/guides/model-context-protocol/public-mcp)): página MCP
  servers do dashboard com o app selecionado. Até 5 índices + modelos de Recommend por servidor, até 5 servidores
  por app; só leitura; o cliente não autentica (vale a search API key). URL
  `https://{APP_ID}.algolia.net/mcp/1/{UNIQ_ID}/mcp`. Tools `algolia_search_{index}`,
  `algolia_search_for_facet_values`, `algolia_recommendations`.
- **Productivity MCP** ([doc](https://www.algolia.com/doc/guides/model-context-protocol/productivity-mcp)):
  `https://mcp.algolia.com/mcp`, **só leitura**. Antes de conectar, **habilitar uma vez por conta** em Dashboard >
  Generative AI > MCP Servers > Productivity. OAuth com o login da Algolia (registro dinâmico de cliente, PKCE,
  refresh token; sem client ID). O escopo é a **conta inteira**: o app é o parâmetro `applicationId` das tools.
  Claude Code: `claude mcp add --transport http algolia https://mcp.algolia.com/mcp` e depois `claude mcp login
  algolia` (ou `/mcp`). A doc lista 16 tools diretas (3 de busca, `algolia_recommendations` e 12 de analytics).
  **Observado no servidor em 07/10/2026 é outra coisa:** 3 meta-tools (`algolia_discover_tools`,
  `algolia_describe_tool`, `algolia_call_read_tool`) que dão acesso a **33 operações, todas de leitura**: as 16 da
  doc mais `algolia_index_get_settings`, `algolia_synonym_list`/`_get`, `algolia_rule_list`/`_get`,
  `algolia_application_list`/`_get_info` (plano e região), `algolia_whoami`, `algolia_analytics_status`,
  `…_list_tags`, `…_top_filter_values`, `…_click_through_rate`, `…_conversion_rate`, `…_add_to_cart_rate`,
  `…_purchase_rate`, `…_revenue` e `…_average_click_position`. Analytics em UTC, atraso de 1 a 4 h; segundo o
  próprio servidor, **índice inexistente não dá erro, volta `null`/0** (o contrário do que o MCP do merchandiser
  deve fazer). No MCP Registry é `io.github.algolia/algolia-productivity`, v1.19.0 em 06/10/2026 (8 versões em uma
  semana: tratar a lista como volátil). **[não confirmado]:** se as buscas pelo MCP contam na cota de 10K e entram
  no Search Analytics do índice.
- **DevEx MCP:** `https://mcp.algolia.com/1/snippets/mcp`, sem login e sem acesso a dados; devolve snippets na
  versão exata de cada client (Python, JavaScript…).
- `algolia/mcp-node` não existe mais (404); `algolia/mcp-servers` e `algolia/docker-mcp-registry` são forks.

## Agent Studio ([doc](https://www.algolia.com/doc/guides/algolia-ai/agent-studio))

- GA no changelog em **15/07/2026**; guardrails, cost controls e prompt suggestions em 28/07/2026.
- Agente = instruções + tools (Algolia Search, client-side, **MCP só Streamable HTTP, timeout 10 s**) + modelo.
  Também pelo CLI `algobot-ai` (npm, MIT, v2.0.0), que **fixa o host EU** do Agent Studio: com o app fora da EU,
  `algobot agents list` volta vazio (skill `algobot-cli`, seção Gotchas).
- **Modelo de linguagem:** a Algolia não fornece o LLM em produção. Oferece **GPT-4.1 grátis só para teste**
  (cota **[não confirmada]**); para publicar, conecta-se um provedor próprio (BYO key): Anthropic, OpenAI,
  Azure OpenAI, Gemini, DeepSeek ou compatível com OpenAI
  ([llm-providers](https://algolia.com/doc/guides/algolia-ai/agent-studio/how-to/llm-providers)).
- Exposição: REST `https://{APP_ID}.algolia.net/agent-studio/1/agents/{AGENT_ID}/completions` com streaming,
  AI SDK UI, ou widget **`Chat`** do InstantSearch. A spec OpenAPI marca `compatibilityMode` como obrigatório; a
  skill `algobot-cli` cita outro host (`agent-studio.<região>.algolia.com`): conferir antes de codar o front. Approved domains por agente; rate limit global e por IP;
  limites de tokens e de passos. 3.000 completions/min e 500 agentes por app. Cada busca do agente conta na cota.

### Observado no app da demo (08–09/10/2026)

- **Endpoint que funciona:** `https://{APP_ID}.algolia.net/agent-studio/1/agents/{id}/completions?stream=false&`
  `compatibilityMode=ai-sdk-4` (ou `ai-sdk-5`, o que o widget `Chat` usa). `GET .../agents/{id}` devolve a
  configuração publicada (modelo, instruções, `tools`, `config.max_iterations`/`max_tokens`) com a Write key. Sem
  header `User-Agent`, o Cloudflare responde **1010**; sem `Origin` de um approved domain, **403** "Request blocked
  for this domain". `stream=true` mostra cada passo (chamada e resultado da ferramenta), útil para diagnóstico.
- **Agente sem a ferramenta de busca** (`tools: []`, o template "blank" nasce assim) escreve a chamada como texto e
  **inventa produtos**; instrução nenhuma impede. Conferir `tools` no GET depois de publicar.
- A ferramenta Algolia Search devolve **7 hits** por busca, não o total: o agente não pode tratar a amostra como
  contagem.
- **Chave enviada ao agente:** a search key com **referer e limite por IP** toma **401** ("Invalid or unauthorized
  API key"); uma chave só com `search`, índices, `maxHitsPerQuery` e validade funciona. A doc de segurança lista
  índices, query params e TTL e desaconselha restrição por IP. Hipótese **[não confirmada]**: o agente valida e
  busca a partir dos servidores da Algolia, sem o referer do navegador.
- **Max steps per completion** (Safety Controls, igual a `config.max_iterations` no GET): com 5, a resposta foi
  cortada logo depois da 1ª busca; com 10, depois de 3 buscas e da resposta pronta; com 15, ok. A contagem da
  plataforma é maior que a de passos visíveis (causa **[não confirmada]**; talvez as sugestões de follow-up).
- **Modelo:** com as mesmas instruções, o Claude Haiku 4.5 inventou "todas em promoção", respondeu em português a
  pergunta em inglês e passou de 3 produtos; o Claude Sonnet 5 seguiu as regras.
- **Prompt Suggestions** (searchable) procura o índice `{índice}_prompt_suggestions`, que só existe depois de
  gerado no dashboard (antes, 404 nos logs). O widget `PromptSuggestions` (react-instantsearch 7.51) gera
  sugestões chamando o agente a cada busca da loja.
- **Widget `Chat`** (react-instantsearch 7.51, instantsearch-ui-components 0.42): usa a chave do search client,
  salvo com `transport` próprio; precisa do `ChatTrigger` para abrir; guarda a conversa no `sessionStorage` com
  chave pelo **`agentId`** (a prop `id` não muda isso); o cabeçalho do carrossel ("N of N results", "View all") é
  fixo em inglês, trocável pela prop `tools` com `createCarouselToolComponent`; feedback 👍/👎 é opt-in (`feedback`)
  e usaria a chave do search client.
- **Tool MCP no agente** (12/10/2026): a tela "Configure MCP server" recebe a URL Streamable HTTP, lista as tools
  do servidor para escolher e tem "Tool approval" ("Never require approval" usado aqui). No `GET` do agente aparece
  como `type: mcp_tools`, com `url`, `transport: streamable_http` e `allowedTools`. O agente chamou a tool em
  produção e a resposta chegou em 1,7 s, voltando da suspensão do Fly. Um servidor stateless com resposta JSON
  (sem SSE) funcionou.
- **Editor das instruções:** ao colar Markdown, tira os marcadores de lista ("-", "1."); o texto fica igual.

## Plugin de skills para Claude Code ([algolia/skills](https://github.com/algolia/skills), MIT)

`claude plugin marketplace add algolia/skills` e `claude plugin install <nome>@algolia-skills`. Plugins:
`algolia-mcp`, `algolia-cli` (imports, settings, rules, synonyms, keys), `algobot-cli`, `instantsearch`,
`algolia-crawler`, `algolia-migration`, `algolia-quickstart`, `algolia-vercel`. Suíte `algolia-implementation`:
discovery-planning, audit, search-implementation, data-modeling, index-configuration, ui-libraries,
instantsearch-ui, autocomplete, events-insights, neuralsearch, agent-studio, release-qa. HEAD de main em
`0953d1b` (22/09/2026).

- **Nenhum plugin registra servidor MCP nem hooks.** O `algolia-mcp` traz só a skill-guia das tools e o comando
  `mcp-connect` (que faz o mesmo `claude mcp add`). Todas as entradas usam a raiz do repo como fonte, então os
  comandos `cli-setup` e `mcp-connect` aparecem em todo plugin instalado (conferido com `claude plugin details`).
- O `cli-setup` está desatualizado: só cobre brew e apt e usa `algolia profile add` (deprecado, grava a chave em
  texto puro). O caminho atual da CLI é `algolia auth login` (OAuth, segredo no keychain).
- A skill `instantsearch` não documenta `Chat`/`aiMode`; nenhuma skill trata de idioma (a regra `pt` é nossa).
- O README do repo mede que, no tier mais alto de modelo, as skills acrescentam disciplina de escopo e não
  conhecimento, com mais tempo de execução.

## Algolia CLI

[`algolia/cli`](https://github.com/algolia/cli) v1.17.0 (02/09/2026, MIT); no npm, `@algolia/cli` 5.17.0. Instalar
por `npm i -g @algolia/cli` (ou `npx`) ou pelo tar.gz de Linux; os pacotes AUR estão órfãos e desatualizados.
Autenticação por OAuth (`algolia auth login`); ao selecionar o app, a CLI cria uma chave de escrita própria
("Algolia CLI"), não usa a Admin key. `apikeys create` não define rate limit nem `maxHitsPerQuery`. Telemetria
ligada por padrão (`ALGOLIA_CLI_TELEMETRY=0` desliga).

## Front-end (npm, MIT)

`react-instantsearch` 7.51.0 · `react-instantsearch-nextjs` 1.4.12 · `algoliasearch` 5.59.0 (`liteClient`).
Autocomplete é widget nativo do react-instantsearch. Recommend nativo: `RelatedProducts`,
`FrequentlyBoughtTogether`, `TrendingItems`, `LookingSimilar`, `TrendingFacets`. Conversacional: `Chat`,
`ChatTrigger`, `PromptSuggestions`, `FilterSuggestions`, `CompareBar`, `ResultCard`, `aiMode` no SearchBox
([Chat](https://www.algolia.com/doc/api-reference/widgets/chat/react)). Starters MIT:
`algolia/algolia-search-starter` (Next.js, 20 produtos), `algolia/instantsearch` `examples/react/e-commerce` e
`next-app-router`.

## Português ([supported languages](https://www.algolia.com/doc/guides/managing-results/optimize-search-results/handling-natural-languages-nlp/in-depth/supported-languages))

- `pt`: plurais "Good", stop words sim. `pt-br`: plurais **"No support"**. ⇒ usar `["pt"]`.
- **Rule com `{facet:...}`** (applying a filter if the query matches a facet value): o exemplo da doc aplica
  `automaticFacetFilters` mas **não tira a palavra da busca**; para "tênis 39" a demo tornou o tamanho em estoque
  pesquisável e pôs "tamanho"/"size" em `optionalWords` (08/10/2026).
- Sem decompounding para pt; stemming não documentado (o mecanismo é dicionário de plurais).
- NeuralSearch em pt **[não confirmado]**; o modelo multilíngue aberto da Algolia (v2410) não lista pt.

## Recommend e eventos

Mínimos de eventos ([fonte](https://support.algolia.com/hc/en-us/articles/13952242763409-How-many-events-do-I-need-to-use-Algolia-features)):
Related items ≥10K, Frequently Bought Together ≥1K conversões, Trending ≥250. `LookingSimilar` não exige eventos.
Eventos gerados para a demo têm de ser declarados como sintéticos.
- **`eventName` da Insights API:** só ASCII visível, de 1 a 64 caracteres; com acento a API recusa o lote inteiro
  ("EventName must contain only visible ascii characters, and be between 1 and 64 characters long", 12/10/2026).

## Dataset

[`algolia/datasets` ecommerce-federated](https://github.com/algolia/datasets/tree/master/ecommerce-federated):
1.787 produtos de moda com `available_sizes`, `color`, `gender`, `hierarchical_categories`, `image_urls`, preço
em EUR, configuração e Query Suggestions prontas. Sem arquivo LICENSE; o README convida a usar os dados "to help
you build something with Algolia". **As fotos (Cloudinary da Algolia) saíram do ar: 1.787 de 1.787 dão 404 (08/10/2026).** Os SKUs do dataset vêm
dos dados de exemplo [Sunrise da commercetools](https://github.com/commercetools/commercetools-sunrise-data)
(Apache-2.0), cujas fotos seguem no S3 da commercetools: 1.787 de 1.787 respondem 200 e os nomes batem; o catálogo
usa essas (ver `catalog/README.md`). O dataset de exemplo do onboarding
(`https://dashboard.algolia.com/api/1/sample_datasets?type=apparel`, público, sem login; também em
`algolia/quickstarts/sample-data`, MIT) tem 1.000 records com fotos que respondem, mas sem marca, tamanho, gênero,
estoque, moeda nem calçado.
Perfil medido em 07/10/2026 (commit `32bfb56`): cada record é **referência × cor** (`parentID` = 1.030
referências), `variants` = tamanhos com `in_stock` (13.453, 21% em estoque); `created_at` e `units_in_stock`
sempre 0; promoção só em acessórios. **O record original passa do limite de 10 KB do Free** (p90 14,5 KB, máximo
39 KB) por causa de `related_products` aninhado; sem ele, o máximo é 3,6 KB. A grade é a grade-modelo inteira de
cada sistema aplicada a todo produto. Modelagem e conversões em [`../CONTRATO-INDICE.md`](../CONTRATO-INDICE.md)
e `catalog/README.md`; VTEX em [`vtex.md`](./vtex.md).

## Brasil e ecossistema

- Clientes confirmados pela Algolia: MadeiraMadeira (PR 09/06/2026), Leroy Merlin Brasil (migrou do
  Elasticsearch), Zoom/Buscapé.
- Integrações oficiais: Adobe Commerce/Magento, BigCommerce, Salesforce B2C, Shopify, commercetools.
  **Sem VTEX.** A VTEX tem busca própria (Intelligent Search, ex-Biggy, 2020).
- Concorrentes de busca vistos no varejo BR: busca nativa da VTEX, Linx Impulse, SmartHint, Elasticsearch interno.
