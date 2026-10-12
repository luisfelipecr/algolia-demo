"use client";

import { createContext, useContext } from "react";

// A loja em duas línguas: `/` em português (padrão) e `/en` em inglês. Cada língua tem o seu índice (o padrão da
// Algolia para várias línguas: plural, stop words e sinônimos do idioma), com os mesmos objectIDs, preços e
// tamanhos. Preço em R$ e grade brasileira nas duas: é a mesma loja brasileira.
//
// Tudo o que vai para widget do InstantSearch (translations, transformItems, items) é montado aqui, uma vez por
// língua, no nível do módulo: referência estável, sem loop de re-render (ver Loja.tsx).

export type Idioma = "pt" | "en";

const INDICES: Record<Idioma, string> = {
  pt: process.env.NEXT_PUBLIC_ALGOLIA_INDEX ?? "produtos_ptbr",
  en: process.env.NEXT_PUBLIC_ALGOLIA_INDEX_EN ?? "produtos_en",
};
const PREFIXOS: Record<Idioma, string> = { pt: "", en: "/en" };
const LOCALES: Record<Idioma, string> = { pt: "pt-BR", en: "en-US" };

/** Link para a busca com o estado na URL (routing padrão do InstantSearch: parâmetros com o nome do índice). */
function urlBusca(idioma: Idioma, estado: Record<string, string>): string {
  const params = new URLSearchParams();
  for (const [chave, valor] of Object.entries(estado)) params.set(`${INDICES[idioma]}${chave}`, valor);
  return `${PREFIXOS[idioma] || "/"}?${params.toString()}`;
}
const busca = (idioma: Idioma, q: string) => urlBusca(idioma, { "[query]": q });
const categoria = (idioma: Idioma, valor: string) =>
  urlBusca(idioma, { "[hierarchicalMenu][categorias.lvl0][0]": valor });

function rotulador(rotulos: Record<string, string>) {
  return <T extends { attribute: string; label: string }>(itens: T[]): T[] =>
    itens.map((item) => ({ ...item, label: rotulos[item.attribute] ?? item.label }));
}

function textos(idioma: Idioma) {
  const numero = new Intl.NumberFormat(LOCALES[idioma]);
  const reais = new Intl.NumberFormat(LOCALES[idioma], { style: "currency", currency: "BRL" });
  const indice = INDICES[idioma];
  const pt = idioma === "pt";

  const rotulos: Record<string, string> = pt
    ? {
        "categorias.lvl0": "Categoria",
        tamanhos_disponiveis: "Tamanho",
        grupo_cor: "Cor",
        marca: "Marca",
        preco: "Preço",
        genero: "Gênero",
        em_promocao: "Promoção",
      }
    : {
        "categorias.lvl0": "Category",
        tamanhos_disponiveis: "Size",
        grupo_cor: "Color",
        marca: "Brand",
        preco: "Price",
        genero: "Gender",
        em_promocao: "Sale",
      };
  const mostrarMais = {
    showMoreButtonText: ({ isShowingMore }: { isShowingMore: boolean }) =>
      pt ? (isShowingMore ? "Mostrar menos" : "Mostrar mais") : isShowingMore ? "Show less" : "Show more",
  };

  return {
    idioma,
    indice,
    prefixo: PREFIXOS[idioma],
    formatarPreco: (valor: number) => reais.format(valor),

    // widgets
    widgets: {
      mostrarMais,
      marca: { ...mostrarMais, noResultsText: pt ? "Nenhuma marca" : "No brand found" },
      limpar: { resetButtonText: pt ? "Limpar filtros" : "Clear filters" },
      preco: { separatorElementText: pt ? "até" : "to", submitButtonText: "OK" },
      busca: pt
        ? { submitButtonTitle: "Buscar", resetButtonTitle: "Limpar busca" }
        : { submitButtonTitle: "Search", resetButtonTitle: "Clear search" },
      stats: {
        rootElementText: ({ nbHits }: { nbHits: number }) =>
          `${numero.format(nbHits)} ${pt ? (nbHits === 1 ? "produto" : "produtos") : nbHits === 1 ? "product" : "products"}`,
      },
      paginacao: {
        firstPageItemText: "«",
        previousPageItemText: "‹",
        nextPageItemText: "›",
        lastPageItemText: "»",
        firstPageItemAriaLabel: pt ? "Primeira página" : "First page",
        previousPageItemAriaLabel: pt ? "Página anterior" : "Previous page",
        nextPageItemAriaLabel: pt ? "Próxima página" : "Next page",
        lastPageItemAriaLabel: pt ? "Última página" : "Last page",
      },
      ordenacoes: [
        { label: pt ? "Mais relevantes" : "Most relevant", value: indice },
        { label: pt ? "Menor preço" : "Lowest price", value: `${indice}_preco_asc` },
        { label: pt ? "Maior preço" : "Highest price", value: `${indice}_preco_desc` },
      ],
      rotularRefinamentos: rotulador(rotulos),
    },

    loja: pt
      ? {
          placeholder: "Busque tênis, bolsas, jaquetas, marcas…",
          filtros: "Filtros",
          verProdutos: "Ver produtos",
          todosProdutos: "Todos os produtos",
          paineis: {
            categoria: "Categoria",
            tamanho: "Tamanho em estoque",
            cor: "Cor",
            marca: "Marca",
            buscarMarca: "Buscar marca",
            preco: "Preço (R$)",
            genero: "Gênero",
            oferta: "Oferta",
            emPromocao: "Em promoção",
          },
          semResultados: (q: string) =>
            q
              ? {
                  titulo: <>Nenhum produto encontrado para <strong>“{q}”</strong>.</>,
                  dica: "Confira a grafia, tire um filtro ou busque por algo mais amplo (por exemplo, “tênis” ou “bolsa”).",
                }
              : { titulo: <>Nenhum produto com esses filtros.</>, dica: "Tire um filtro para ver mais produtos." },
          erroBusca: {
            titulo: "Não foi possível buscar agora.",
            dica: "Tente de novo em instantes. Esta loja de demonstração tem um limite de buscas por visitante.",
          },
        }
      : {
          placeholder: "Search sneakers, bags, jackets, brands…",
          filtros: "Filters",
          verProdutos: "Show products",
          todosProdutos: "All products",
          paineis: {
            categoria: "Category",
            tamanho: "Size in stock (BR)",
            cor: "Color",
            marca: "Brand",
            buscarMarca: "Search brands",
            preco: "Price (R$)",
            genero: "Gender",
            oferta: "Deals",
            emPromocao: "On sale",
          },
          semResultados: (q: string) =>
            q
              ? {
                  titulo: <>No products found for <strong>“{q}”</strong>.</>,
                  dica: "Check the spelling, remove a filter or try something broader (for example, “sneakers” or “bag”).",
                }
              : { titulo: <>No products match these filters.</>, dica: "Remove a filter to see more products." },
          erroBusca: {
            titulo: "Search is unavailable right now.",
            dica: "Please try again in a moment. This demo store limits searches per visitor.",
          },
        },

    cabecalho: pt
      ? {
          faixa: "Demo de busca em português feita com Algolia. Catálogo ilustrativo: não há venda de verdade.",
          marcaAria: "Loja Demo, página inicial",
          atalhosAria: "Categorias",
          idiomaAria: "Idioma",
          atalhos: [
            { rotulo: "Feminino", href: categoria(idioma, "Feminino") },
            { rotulo: "Masculino", href: categoria(idioma, "Masculino") },
            { rotulo: "Tênis", href: busca(idioma, "tênis") },
            { rotulo: "Bolsas", href: busca(idioma, "bolsa") },
            { rotulo: "Jaquetas", href: busca(idioma, "jaqueta") },
            { rotulo: "Acessórios", href: categoria(idioma, "Acessórios") },
            { rotulo: "Promoções", href: urlBusca(idioma, { "[toggle][em_promocao]": "true" }) },
          ],
          rodape: [
            <>
              <strong>Sobre esta demo.</strong> Catálogo derivado de dados públicos de exemplo (Algolia e
              commercetools), traduzido para o português, com preços convertidos de euro para real por um câmbio
              fixo e estoque sintético. Nenhum dado de loja ou marca real.
            </>,
            <>Busca, filtros e ordenação: Algolia (plano Free). Loja: Next.js com React InstantSearch.</>,
          ],
        }
      : {
          faixa: "Algolia search demo for a Brazilian store, in English. Illustrative catalog: nothing is for sale.",
          marcaAria: "Loja Demo, home page",
          atalhosAria: "Categories",
          idiomaAria: "Language",
          atalhos: [
            { rotulo: "Women", href: categoria(idioma, "Women") },
            { rotulo: "Men", href: categoria(idioma, "Men") },
            { rotulo: "Sneakers", href: busca(idioma, "sneakers") },
            { rotulo: "Bags", href: busca(idioma, "bag") },
            { rotulo: "Jackets", href: busca(idioma, "jacket") },
            { rotulo: "Accessories", href: categoria(idioma, "Accessories") },
            { rotulo: "Sale", href: urlBusca(idioma, { "[toggle][em_promocao]": "true" }) },
          ],
          rodape: [
            <>
              <strong>About this demo.</strong> The catalog comes from public sample data (Algolia and
              commercetools). Prices were converted from euros to Brazilian reais at a fixed rate and stock is
              synthetic. No real store or brand data.
            </>,
            <>Search, filters and sorting: Algolia (Free plan). Store: Next.js with React InstantSearch.</>,
          ],
        },

    // as buscas de exemplo mostram o que a configuração de cada língua resolve
    inicio: pt
      ? {
          sobretitulo: "Busca em português com Algolia",
          titulo: "Ache o tamanho certo, na cor certa.",
          sub: "1.787 produtos de moda e calçados, filtro pelo tamanho que está em estoque e uma busca que entende plural, acento, erro de digitação e “vermelha” ou “vermelho”. Experimente:",
          exemplos: [
            { texto: "tênis feminino", nota: "gênero" },
            { texto: "tênis 39", nota: "tamanho em estoque" },
            { texto: "bolsa vermelha", nota: "concordância" },
            { texto: "tenix", nota: "erro de digitação" },
            { texto: "sneaker", nota: "sinônimo" },
            { texto: "cinto promoção", nota: "regra de promoção" },
          ].map((e) => ({ ...e, href: busca(idioma, e.texto) })),
          diferenciais: [
            { titulo: "Grade brasileira", texto: "PP a XGG e numeração 33 a 44" },
            { titulo: "Estoque por tamanho", texto: "filtre só o que tem no seu número" },
            { titulo: "Preços em reais", texto: "com promoções sinalizadas" },
          ],
          porCategoria: "Comprar por categoria",
          categorias: [
            { rotulo: "Jaquetas", foto: "078866", q: "jaqueta" },
            { rotulo: "Tênis", foto: "085007", q: "tênis", calcado: true },
            { rotulo: "Bolsas", foto: "086651", q: "bolsa" },
            { rotulo: "Vestidos", foto: "082365", q: "vestido" },
            { rotulo: "Camisas masculinas", foto: "079889", q: "camisa masculina" },
            { rotulo: "Óculos de sol", foto: "081951", q: "óculos de sol" },
          ].map((c) => ({ ...c, href: busca(idioma, c.q) })),
        }
      : {
          sobretitulo: "Algolia search, English version",
          titulo: "Find the right size, in the right color.",
          sub: "1,787 fashion and footwear products from a Brazilian store, a filter for the sizes in stock and a search that handles plurals, typos, synonyms and US or UK spelling. Prices in Brazilian reais and Brazilian sizes. Try:",
          exemplos: [
            { texto: "women sneakers", nota: "gender" },
            { texto: "sneakers size 39", nota: "size in stock" },
            { texto: "gray bag", nota: "US spelling" },
            { texto: "sneekers", nota: "typo" },
            { texto: "trainers", nota: "synonym" },
            { texto: "belt sale", nota: "sale rule" },
          ].map((e) => ({ ...e, href: busca(idioma, e.texto) })),
          diferenciais: [
            { titulo: "Brazilian sizes", texto: "PP to XGG (about XS to XXL), shoes 33 to 44" },
            { titulo: "Stock by size", texto: "filter only what is available in your size" },
            { titulo: "Prices in reais (R$)", texto: "with sales clearly flagged" },
          ],
          porCategoria: "Shop by category",
          categorias: [
            { rotulo: "Jackets", foto: "078866", q: "jacket" },
            { rotulo: "Sneakers", foto: "085007", q: "sneakers", calcado: true },
            { rotulo: "Bags", foto: "086651", q: "bag" },
            { rotulo: "Dresses", foto: "082365", q: "dress" },
            { rotulo: "Men's shirts", foto: "079889", q: "men shirt" },
            { rotulo: "Sunglasses", foto: "081951", q: "sunglasses" },
          ].map((c) => ({ ...c, href: busca(idioma, c.q) })),
        },

    // Assistente do Agent Studio (widget Chat). As perguntas de exemplo são fixas: o PromptSuggestions geraria
    // sugestões com uma chamada de LLM a cada busca da loja.
    chat: {
      paginaDeBusca: (ui: { query?: string }) => busca(idioma, ui.query ?? ""),
      traducoes: pt
        ? {
            header: {
              title: "Assistente de compras",
              minimizeLabel: "Minimizar",
              maximizeLabel: "Ampliar",
              closeLabel: "Fechar",
              clearLabel: "Limpar conversa",
            },
            prompt: {
              textareaLabel: "Sua pergunta",
              textareaPlaceholder: "Pergunte por produto, tamanho, cor ou preço…",
              emptyMessageTooltip: "Escreva uma pergunta",
              stopResponseTooltip: "Parar resposta",
              sendMessageTooltip: "Enviar",
              disclaimer: "Respostas geradas por IA a partir do catálogo da loja. Confira preço e estoque no produto.",
            },
            messages: {
              scrollToBottomLabel: "Ir para o fim",
              loaderText: "Buscando no catálogo…",
              copyToClipboardLabel: "Copiar",
              regenerateLabel: "Gerar de novo",
              thumbsUpLabel: "Resposta útil",
              thumbsDownLabel: "Resposta ruim",
              feedbackThankYouText: "Obrigado pelo retorno!",
              sendingFeedbackLabel: "Enviando…",
            },
            message: { messageLabel: "Mensagem", actionsLabel: "Ações", toolErrorRetryText: "Tentar de novo" },
          }
        : {
            header: {
              title: "Shopping assistant",
              minimizeLabel: "Minimize",
              maximizeLabel: "Maximize",
              closeLabel: "Close",
              clearLabel: "Clear conversation",
            },
            prompt: {
              textareaLabel: "Your question",
              textareaPlaceholder: "Ask about a product, size, color or price…",
              emptyMessageTooltip: "Type a question",
              stopResponseTooltip: "Stop response",
              sendMessageTooltip: "Send",
              disclaimer: "AI answers based on the store catalog. Check price and stock on the product page.",
            },
            messages: {
              scrollToBottomLabel: "Scroll to bottom",
              loaderText: "Searching the catalog…",
              copyToClipboardLabel: "Copy",
              regenerateLabel: "Regenerate",
              thumbsUpLabel: "Helpful answer",
              thumbsDownLabel: "Unhelpful answer",
              feedbackThankYouText: "Thanks for the feedback!",
              sendingFeedbackLabel: "Sending…",
            },
            message: { messageLabel: "Message", actionsLabel: "Actions", toolErrorRetryText: "Try again" },
          },
      saudacao: pt
        ? {
            titulo: "Oi! Posso ajudar a achar o produto certo.",
            texto: "Busco no catálogo da loja e só digo o que está lá: preço, tamanhos em estoque e promoção.",
            exemplos: ["Tem tênis feminino 37?", "Bolsa vermelha até R$ 500", "Tem cinto em promoção?"],
          }
        : {
            titulo: "Hi! I can help you find the right product.",
            texto: "I search the store catalog and only tell you what is there: price, sizes in stock and sales.",
            exemplos: ["Women's sneakers in size 38?", "Red bags under R$ 500", "Any discounted belts?"],
          },
      verProduto: pt ? "Ver produto" : "View product",
      abrir: pt ? "Abrir o assistente de compras" : "Open the shopping assistant",
      // cabeçalho do carrossel de produtos que o agente buscou (o padrão do widget é fixo em inglês)
      resultados: (n: number, total: number) =>
        pt
          ? `${n} de ${numero.format(total)} ${total === 1 ? "resultado" : "resultados"}`
          : `${n} of ${numero.format(total)} ${total === 1 ? "result" : "results"}`,
      verTodos: pt ? "Ver na loja" : "See in store",
      anterior: pt ? "Produtos anteriores" : "Previous products",
      proximos: pt ? "Próximos produtos" : "Next products",
    },

    produto: pt
      ? {
          carregando: "Carregando…",
          naoEncontrado: "Produto não encontrado.",
          voltarLoja: "Voltar para a loja",
          voltarBusca: "← Voltar para a busca",
          trilhaAria: "Trilha",
          loja: "Loja",
          cor: "Cor:",
          corNaoInformada: "não informada",
          tamanho: "Tamanho",
          gradeAria: "Grade de tamanhos",
          emEstoque: "Em estoque",
          semEstoque: "Sem estoque",
          tamanhosAria: "Tamanhos em estoque",
          resumoEstoque: (n: number, total: number) =>
            `${n} de ${total} ${total === 1 ? "tamanho" : "tamanhos"} em estoque.`,
          esgotado: "Sem estoque em nenhum tamanho no momento.",
          nota: (nota: number, total: number) =>
            `Nota ${nota} de 5 (${numero.format(total)} ${total === 1 ? "avaliação" : "avaliações"})`,
          aviso: "Loja de demonstração: os produtos não estão à venda.",
          outrasCores: "Outras cores da mesma referência",
          fotoIndisponivel: "foto indisponível",
          fotoAria: (cor: string) => `Foto indisponível. Cor: ${cor || "não informada"}`,
        }
      : {
          carregando: "Loading…",
          naoEncontrado: "Product not found.",
          voltarLoja: "Back to the store",
          voltarBusca: "← Back to search",
          trilhaAria: "Breadcrumb",
          loja: "Store",
          cor: "Color:",
          corNaoInformada: "not specified",
          tamanho: "Size (BR)",
          gradeAria: "Size range",
          emEstoque: "In stock",
          semEstoque: "Out of stock",
          tamanhosAria: "Sizes in stock",
          resumoEstoque: (n: number, total: number) => `${n} of ${total} ${total === 1 ? "size" : "sizes"} in stock.`,
          esgotado: "Out of stock in every size right now.",
          nota: (nota: number, total: number) =>
            `Rated ${nota} out of 5 (${numero.format(total)} ${total === 1 ? "review" : "reviews"})`,
          aviso: "Demo store: these products are not for sale.",
          outrasCores: "Other colors of the same style",
          fotoIndisponivel: "photo unavailable",
          fotoAria: (cor: string) => `Photo unavailable. Color: ${cor || "not specified"}`,
        },
  };
}

export type Local = ReturnType<typeof textos>;

export const LOCAIS: Record<Idioma, Local> = { pt: textos("pt"), en: textos("en") };
export const IDIOMAS = Object.keys(LOCAIS) as Idioma[];
export const NOMES_IDIOMA: Record<Idioma, { curto: string; nome: string }> = {
  pt: { curto: "PT", nome: "Português" },
  en: { curto: "EN", nome: "English" },
};

const LocalContext = createContext<Local>(LOCAIS.pt);

/** O valor é sempre um dos dois objetos de LOCAIS: estável, não re-renderiza quem consome. */
export function ProvedorIdioma({ idioma, children }: { idioma: Idioma; children: React.ReactNode }) {
  return <LocalContext value={LOCAIS[idioma]}>{children}</LocalContext>;
}

export function useLocal(): Local {
  return useContext(LocalContext);
}
