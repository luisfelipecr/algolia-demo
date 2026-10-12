"use client";

import Link from "next/link";

import { IDIOMAS, NOMES_IDIOMA, useLocal, LOCAIS } from "@/lib/idioma";

/**
 * Faixa de aviso com o seletor de idioma. Na página de produto, o outro idioma abre o mesmo produto (o objectID
 * é o mesmo nos dois índices); na loja, abre a home da outra língua, porque a busca digitada e os valores de
 * filtro não se traduzem. Link comum (não `Link`): a outra língua é outra instância do InstantSearch.
 */
export function Faixa({ produtoId }: { produtoId?: string }) {
  const { idioma, cabecalho } = useLocal();
  return (
    <div className="faixa">
      <p>{cabecalho.faixa}</p>
      <nav className="idiomas" aria-label={cabecalho.idiomaAria}>
        {IDIOMAS.map((outro) => {
          const base = LOCAIS[outro].prefixo;
          const destino = produtoId ? `${base}/produto/${encodeURIComponent(produtoId)}` : base || "/";
          return (
            <a
              key={outro}
              href={destino}
              hrefLang={outro === "pt" ? "pt-BR" : "en"}
              lang={outro === "pt" ? "pt-BR" : "en"}
              aria-current={outro === idioma ? "page" : undefined}
              title={NOMES_IDIOMA[outro].nome}
            >
              {NOMES_IDIOMA[outro].curto}
            </a>
          );
        })}
      </nav>
    </div>
  );
}

export function Marca() {
  const { prefixo, cabecalho } = useLocal();
  return (
    <Link href={prefixo || "/"} className="marca-loja" aria-label={cabecalho.marcaAria}>
      Loja<span>Demo</span>
    </Link>
  );
}

// Atalhos montados como URL do estado da busca (routing padrão do InstantSearch): o link funciona até aberto em
// outra aba, e a página de resultados lê o estado da URL ao carregar.
export function Atalhos() {
  const { cabecalho } = useLocal();
  return (
    <nav className="atalhos" aria-label={cabecalho.atalhosAria}>
      {cabecalho.atalhos.map((a) => (
        <a key={a.rotulo} href={a.href}>
          {a.rotulo}
        </a>
      ))}
    </nav>
  );
}

export function Rodape() {
  const { cabecalho } = useLocal();
  return (
    <footer className="rodape">
      {cabecalho.rodape.map((paragrafo, i) => (
        <p key={i}>{paragrafo}</p>
      ))}
    </footer>
  );
}
