"use client";

import type { Hit } from "instantsearch.js";
import type { SendEventForHits } from "instantsearch.js/es/lib/utils";
import Link from "next/link";
import { Highlight } from "react-instantsearch";

import { ordemTamanho, type Produto } from "@/lib/algolia";
import { useLocal } from "@/lib/idioma";
import { Foto } from "./Foto";

const MAX_TAMANHOS = 6;

export function Tamanhos({ tamanhos }: { tamanhos: string[] }) {
  const ordenados = [...tamanhos].sort((a, b) => ordemTamanho(a) - ordemTamanho(b));
  const visiveis = ordenados.slice(0, MAX_TAMANHOS);
  const resto = ordenados.length - visiveis.length;
  const { produto } = useLocal();
  return (
    <ul className="tamanhos" aria-label={produto.tamanhosAria}>
      {visiveis.map((t) => (
        <li key={t}>{t}</li>
      ))}
      {resto > 0 && <li className="mais">+{resto}</li>}
    </ul>
  );
}

export function CartaoProduto({ hit, sendEvent }: { hit: Hit<Produto>; sendEvent?: SendEventForHits }) {
  const { prefixo, formatarPreco, produto } = useLocal();
  const destino = `${prefixo}/produto/${encodeURIComponent(hit.objectID)}`;
  return (
    <Link href={destino} className="produto" onClick={() => sendEvent?.("click", hit, "Produto clicado")}>
      <div className="vitrine">
        <Foto
          src={hit.imagem}
          alt=""
          categoria={hit.categorias.lvl1 ?? ""}
          amostraCor={hit.amostra_cor}
          cor={hit.cor}
        />
        {hit.em_promocao && <span className="selo">−{hit.desconto_pct}%</span>}
      </div>
      <p className="marca">
        <Highlight attribute="marca" hit={hit} />
      </p>
      <h3 className="nome">
        <Highlight attribute="nome" hit={hit} />
      </h3>
      <p className="preco">
        <strong>{formatarPreco(hit.preco)}</strong>
        {hit.em_promocao && <s>{formatarPreco(hit.preco_de)}</s>}
      </p>
      {hit.em_estoque ? <Tamanhos tamanhos={hit.tamanhos_disponiveis} /> : <p className="esgotado">{produto.semEstoque}</p>}
    </Link>
  );
}
