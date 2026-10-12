import type { Metadata } from "next";
import { Fraunces, Inter } from "next/font/google";
import "instantsearch.css/themes/satellite.css";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--fonte" });
const fraunces = Fraunces({ subsets: ["latin"], variable: "--fonte-titulo", style: ["normal", "italic"] });

export const metadata: Metadata = {
  title: "Loja Demo: busca em português com Algolia",
  description: "Demo de busca para varejo de moda e calçados em português, construída sobre a Algolia.",
  alternates: { languages: { "pt-BR": "/", en: "/en" } },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="pt-BR" className={`${inter.variable} ${fraunces.variable}`}>
      <body>{children}</body>
    </html>
  );
}
