import type { Metadata } from "next";

// A loja em inglês. O <html> do layout raiz é pt-BR (a loja é brasileira); o lang="en" aqui vale para todo o
// conteúdo da página, que é o que leitores de tela e tradutores automáticos usam. Vários root layouts dariam
// <html lang="en">, mas exigiriam o 404 global experimental do Next.
export const metadata: Metadata = {
  title: "Loja Demo: Algolia search for a Brazilian store, in English",
  description: "Search demo for fashion and footwear retail, built on Algolia, in Portuguese and English.",
  alternates: { languages: { "pt-BR": "/", en: "/en" } },
};

export default function LayoutIngles({ children }: LayoutProps<"/en">) {
  return <div lang="en">{children}</div>;
}
