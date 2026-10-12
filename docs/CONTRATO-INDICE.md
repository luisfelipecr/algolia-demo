# Contrato do índice `produtos_ptbr` (07/10/2026)

Decidido com a skill `algolia-implementation:algolia-data-modeling` e implementado em `ingest/`. Settings, sinônimos e Rules como código em `ingest/config/`; o record em `ingest/registro.py`.

## Modelo

- **Um record por referência × cor** (variation-group). Na origem VTEX, um Product por referência × cor com SKUs =
  tamanhos (`catalog/`); o conector agrupa SKUs pela spec `Cor`, então também serve à VTEX canônica (Product com
  SKUs cor × tamanho).
- **Por quê:** a foto é por cor; o filtro cor + tamanho fica exato dentro do record; a demanda perdida por tamanho
  (MCP) sai de `grade` × `tamanhos_disponiveis`. Por SKU daria 7.635 records com duplicata visual; por referência
  perderia foto e exatidão de cor + tamanho.
- **Volume:** 1.787 records (+ replicas de ordenação, que somam records no Free).
- **`objectID`** = `{productId}-{slug da cor}` (ex.: `2787-verde-oliva`): a mesma fórmula serve à loja com produto
  por cor e à canônica, e não muda se o produto ganhar outra cor. `produto_id` e `referencia`
  (`productReference`, usada no `attributeForDistinct`) ficam no record para agrupar e para analytics.

## Campos do record

- Busca (ordem de `searchableAttributes`): `nome`, `marca`, depois sem ordem `categoria`, `categorias.lvl1`, `cor`,
  `grupo_cor`, `genero`, `descricao`, `tamanhos_disponiveis`. Gênero e categoria entram para "tênis feminino" e
  "bolsa" casarem; o tamanho em estoque, para "tênis 39" casar só com quem tem o 39 (antes dava 0: o tamanho era só
  facet e o número virava palavra obrigatória sem par; achado do Luis em 08/10/2026).
- Exibição: `nome`, `marca`, `imagem`, `preco`, `preco_de`, `desconto_pct`, `url`, `nota`, `avaliacoes`.
- Facets: `searchable(marca)`, `categorias.lvl0..2`, `genero`, `grupo_cor`, `tamanhos_disponiveis` (só com
  estoque), `filterOnly(grade)`, `em_promocao`, `em_estoque`, `preco` (facet cheio, para o slider ter stats),
  `filterOnly(referencia)`.
- Ranking (`customRanking`): `desc(em_estoque)`, `desc(avaliacao_bayes)` (média bayesiana com 10 avaliações de
  prior, arredondada a 0,1; em `unretrievableAttributes`, não sai no payload público).
- Aninhado: `skus: [{id, tamanho, em_estoque}]` (sem quantidade exata no índice; quantidade fica na VTEX).
- **Um só preço efetivo** (`preco`, o menor preço de venda do grupo) para exibir, filtrar, ordenar e range facet;
  `preco_de` só para o riscado.
- Replicas padrão `produtos_ptbr_preco_asc` e `_desc` (virtual replicas não existem no Free), com as mesmas
  settings e a ordenação na frente do `ranking`.
- Fora do record: `related_products` da origem (o `LookingSimilar` faz esse papel; aninhado, ele levava o record
  original a 39 KB, acima do limite de 10 KB do Free).
- Tamanho medido: p50 1,1 KB, máximo 1,7 KB.

## Sinônimos e Rules

- 20 sinônimos: tênis/sneaker, moletom/hoodie, puffer, echarpe, loafer, espadrille, óculos escuros, power bank,
  t-shirt e **concordância de gênero** (preto/preta, vermelho/vermelha, feminino/feminina...), que o
  `ignorePlurals` não cobre.
- `optionalWords` "tamanho", "número", "numero", "tam": "tênis tamanho 39" não exige a palavra.
- 3 Rules (o teto real do Free, ver `fontes/algolia.md`): "promoção", "liquidação" e "oferta" filtram `em_promocao:true` e saem da busca. Uma
  Rule por termo porque a edição `remove` apaga só a palavra literal.

## Índice em inglês (`produtos_en`, 08/10/2026)

- Mesmo record e mesmas settings; muda o que é do idioma (`ingest/config/en/indice.json`): `queryLanguages`,
  `indexLanguages`, `ignorePlurals` e `removeStopWords` em `en`, `optionalWords: ["size"]`.
- **Mesmo `objectID` do pt:** a cor entra no `objectID` e vem traduzida ("azul" × "blue"); o conector usa o do pt,
  ligado pelos SKUs (`ingest.indexar --idioma en`). A loja troca de idioma no mesmo produto.
- Texto original em inglês da origem, com correções fixas (`catalog/glossario.py`); valores de facet em inglês
  (`Women > Shoes`, `grey`); preço em R$ e grade BR iguais ao pt.
- 15 sinônimos (grafia US/UK `gray`/`grey`, `trainers`, `tee`, `pants`/`trousers`, hoodie e puffer de mão única…)
  e 3 Rules (`sale`, `deal`, `discount` → `em_promocao:true`).
- Replicas `produtos_en_preco_asc`/`_desc`. Total no app: 6 índices de produto (10.722 records) e o índice dos
  avisos de "quando chegar" (`produtos_ptbr_avisos`).

## Lacunas de dados (declaradas)

- Sem data de lançamento na origem (`created_at` = 0): nada de "novidades" por data.
- Estoque por tamanho é booleano na origem; quantidades da VTEX são sintéticas.
- Promoção só em acessórios (212 records, 10%).
- Sem vendas por produto: a demo usa as avaliações como proxy de popularidade; os eventos de Insights são
  cliques reais da loja e cliques sintéticos declarados (`sintetico/`), sem conversão.

## Consultas de validação (rodadas em 08/10/2026 com a Search key)

1. `tenis` + `tamanhos_disponiveis:40`: 57 resultados, todos com 40 em estoque.
2. `bolsa vermelha`: bolsas de cor "vermelho" (sinônimo de concordância).
3. `jaqueta de couro` na replica `preco_asc`: ordem crescente de preço.
4. `cinto promoção`: a Rule filtra os cintos em promoção.
5. `sneaker` → tênis; `sapatenis` → 0 (não há sapatênis no catálogo: caso de demanda perdida para o MCP).
6. `avaliacao_bayes` ausente do hit; `preco` com `facets_stats`.
7. `tênis 39` (texto, sem filtro): 65 resultados, todos com 39 em estoque (59 tênis e 6 "Tênis slip-on" em
   Mocassins).
