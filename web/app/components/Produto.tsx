"use client";

import Link from "next/link";
import { Configure, Hits, Index, InstantSearch, useHits, useInstantSearch } from "react-instantsearch";

import { Faixa, Marca, Rodape } from "@/app/components/Cabecalho";
import { Assistente } from "@/app/components/Assistente";
import { CartaoProduto } from "@/app/components/CartaoProduto";
import { Foto } from "@/app/components/Foto";
import { Voltar } from "@/app/components/Voltar";
import { ordemTamanho, type Produto as TProduto, searchClient } from "@/lib/algolia";
import { type Idioma, ProvedorIdioma, useLocal } from "@/lib/idioma";

function Detalhe() {
  const { items, results } = useHits<TProduto>();
  const { status } = useInstantSearch();
  const { indice, prefixo, formatarPreco, produto: t, loja } = useLocal();
  const p = items[0];
  if (!p) {
    if (status === "error") {
      return (
        <div className="pdp-vazio" role="alert">
          <p>{loja.erroBusca.titulo}</p>
          <p>{loja.erroBusca.dica}</p>
        </div>
      );
    }
    if (results?.__isArtificial) return <p className="carregando">{t.carregando}</p>;
    return (
      <div className="pdp-vazio">
        <p>{t.naoEncontrado}</p>
        <Link href={prefixo || "/"}>{t.voltarLoja}</Link>
      </div>
    );
  }

  const skus = [...p.skus].sort((a, b) => ordemTamanho(a.tamanho) - ordemTamanho(b.tamanho));
  return (
    <>
      <nav className="trilha" aria-label={t.trilhaAria}>
        <Link href={prefixo || "/"}>{t.loja}</Link>
        {p.categorias.lvl2?.split(" > ").map((parte) => <span key={parte}>{parte}</span>) ??
          p.categorias.lvl1?.split(" > ").map((parte) => <span key={parte}>{parte}</span>)}
      </nav>
      <article className="pdp">
        <div className="pdp-foto">
          <Foto src={p.imagem} alt={p.nome} categoria={p.categorias.lvl1 ?? ""} amostraCor={p.amostra_cor} cor={p.cor} />
        </div>
        <div className="pdp-info">
          <p className="marca">{p.marca}</p>
          <h1>{p.nome}</h1>
          <p className="pdp-preco">
            <strong>{formatarPreco(p.preco)}</strong>
            {p.em_promocao && (
              <>
                <s>{formatarPreco(p.preco_de)}</s>
                <span className="selo">−{p.desconto_pct}%</span>
              </>
            )}
          </p>
          <p className="pdp-cor">
            {t.cor} <span className="pdp-amostra" style={{ background: p.amostra_cor.startsWith("#") ? p.amostra_cor : undefined }} />{" "}
            {p.cor || t.corNaoInformada}
          </p>
          <h2>{t.tamanho}</h2>
          <ul className="grade" aria-label={t.gradeAria}>
            {skus.map((s) => (
              <li key={s.id} className={s.em_estoque ? "" : "esgotado"} title={s.em_estoque ? t.emEstoque : t.semEstoque}>
                {s.tamanho}
              </li>
            ))}
          </ul>
          <p className="pdp-estoque">
            {p.em_estoque ? t.resumoEstoque(p.tamanhos_disponiveis.length, skus.length) : t.esgotado}
          </p>
          {p.descricao && <p className="pdp-descricao">{p.descricao}</p>}
          {p.avaliacoes > 0 && (
            <p className="pdp-nota">{t.nota(p.nota, p.avaliacoes)}</p>
          )}
          <p className="pdp-aviso">{t.aviso}</p>
        </div>
      </article>

      <section className="relacionados">
        <Index indexName={indice} indexId="mesma-referencia">
          <Configure
            filters={`referencia:"${p.referencia}" AND NOT objectID:"${p.objectID}"`}
            hitsPerPage={8}
            analytics={false}
          />
          <OutrasCores />
        </Index>
      </section>
    </>
  );
}

function OutrasCores() {
  const { items } = useHits<TProduto>();
  const { produto } = useLocal();
  if (!items.length) return null;
  return (
    <>
      <h2>{produto.outrasCores}</h2>
      <Hits hitComponent={CartaoProduto} />
    </>
  );
}

export function Produto({ id, idioma }: { id: string; idioma: Idioma }) {
  return (
    <ProvedorIdioma idioma={idioma}>
      <PaginaDoProduto id={id} />
    </ProvedorIdioma>
  );
}

function PaginaDoProduto({ id }: { id: string }) {
  const { indice } = useLocal();
  return (
    <InstantSearch searchClient={searchClient} indexName={indice} insights>
      {/* consultas internas da página: fora do analytics, que é das buscas dos clientes */}
      <Configure filters={`objectID:"${id.replace(/["\\]/g, "")}"`} hitsPerPage={1} analytics={false} />
      <Faixa produtoId={id} />
      <div className="cabecalho">
        <header className="topo topo-simples">
          <Marca />
          <Voltar />
        </header>
      </div>
      <main className="pagina-produto">
        <Detalhe />
      </main>
      <Rodape />
      <Assistente />
    </InstantSearch>
  );
}
