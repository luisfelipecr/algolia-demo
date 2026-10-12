import { liteClient as algoliasearch } from "algoliasearch/lite";

// Declarado fora dos componentes: a referência estável preserva o cache interno do client.
export const searchClient = algoliasearch(
  process.env.NEXT_PUBLIC_ALGOLIA_APP_ID!,
  process.env.NEXT_PUBLIC_ALGOLIA_SEARCH_KEY!,
);

export type Produto = {
  objectID: string;
  nome: string;
  marca: string;
  imagem: string;
  url: string;
  preco: number;
  preco_de: number;
  em_promocao: boolean;
  desconto_pct: number;
  tamanhos_disponiveis: string[];
  em_estoque: boolean;
  cor: string;
  amostra_cor: string;
  categorias: { lvl0: string; lvl1?: string; lvl2?: string };
  nota: number;
  avaliacoes: number;
  referencia: string;
  descricao: string;
  skus: { id: string; tamanho: string; em_estoque: boolean }[];
};

const LETRAS = ["PP", "P", "M", "G", "GG", "XGG"];

/** Ordem da grade brasileira: letras PP…XGG, depois números crescentes, U no fim. */
export function ordemTamanho(tamanho: string): number {
  const letra = LETRAS.indexOf(tamanho);
  if (letra >= 0) return letra;
  if (tamanho === "U") return 10_000;
  return 100 + Number(tamanho);
}
