"use client";

import { useEffect, useState } from "react";
import {
  ClearRefinements,
  Configure,
  CurrentRefinements,
  HierarchicalMenu,
  Hits,
  InstantSearch,
  Pagination,
  PoweredBy,
  RangeInput,
  RefinementList,
  SearchBox,
  SortBy,
  Stats,
  ToggleRefinement,
  useInstantSearch,
} from "react-instantsearch";

import { ordemTamanho, searchClient } from "@/lib/algolia";
import { type Idioma, ProvedorIdioma, useLocal } from "@/lib/idioma";
import { Assistente } from "./Assistente";
import { Atalhos, Faixa, Marca, Rodape } from "./Cabecalho";
import { CartaoProduto } from "./CartaoProduto";
import { Inicio, useEstadoInicial } from "./Inicio";

// Tudo o que vai para widget fica no nível do módulo (aqui ou em lib/idioma.tsx, uma vez por língua). O
// useConnector do React InstantSearch compara as props com dequal, e função entra por referência: transformItems
// ou translations recriados a cada render contam como widget novo, que dispara outra busca, que re-renderiza...
// (loop de CPU e de cota).
const ATRIBUTOS_CATEGORIA = ["categorias.lvl0", "categorias.lvl1", "categorias.lvl2"];
const DESTACAR = ["nome", "marca"];

function ordenarTamanhos<T extends { value: string }>(itens: T[]): T[] {
  return [...itens].sort((a, b) => ordemTamanho(a.value) - ordemTamanho(b.value));
}

function Painel({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <section className="painel">
      <h2>{titulo}</h2>
      {children}
    </section>
  );
}

/** Mensagem ao lado dos resultados, nunca no lugar deles: desmontar Hits e Pagination dispararia outra busca. */
function SemResultados() {
  const { results, indexUiState, status } = useInstantSearch();
  const { loja } = useLocal();
  if (status === "error") {
    return (
      <div className="sem-resultados" role="alert">
        <p>{loja.erroBusca.titulo}</p>
        <p>{loja.erroBusca.dica}</p>
      </div>
    );
  }
  if (!results.__isArtificial && results.nbHits === 0) {
    const texto = loja.semResultados(indexUiState.query ?? "");
    return (
      <div className="sem-resultados">
        <p>{texto.titulo}</p>
        <p>{texto.dica}</p>
      </div>
    );
  }
  return null;
}

function Filtros() {
  const { widgets, loja } = useLocal();
  const p = loja.paineis;
  return (
    <>
      <CurrentRefinements transformItems={widgets.rotularRefinamentos} />
      <ClearRefinements translations={widgets.limpar} />
      <Painel titulo={p.categoria}>
        <HierarchicalMenu
          attributes={ATRIBUTOS_CATEGORIA}
          showMore
          translations={widgets.mostrarMais}
        />
      </Painel>
      <Painel titulo={p.tamanho}>
        <RefinementList
          attribute="tamanhos_disponiveis"
          limit={20}
          transformItems={ordenarTamanhos}
        />
      </Painel>
      <Painel titulo={p.cor}>
        <RefinementList attribute="grupo_cor" limit={8} showMore translations={widgets.mostrarMais} />
      </Painel>
      <Painel titulo={p.marca}>
        <RefinementList
          attribute="marca"
          searchable
          searchablePlaceholder={p.buscarMarca}
          showMore
          translations={widgets.marca}
        />
      </Painel>
      <Painel titulo={p.preco}>
        <RangeInput
          attribute="preco"
          precision={0}
          translations={widgets.preco}
        />
      </Painel>
      <Painel titulo={p.genero}>
        <RefinementList attribute="genero" />
      </Painel>
      <Painel titulo={p.oferta}>
        <ToggleRefinement attribute="em_promocao" label={p.emPromocao} />
      </Painel>
    </>
  );
}

/** Só este componente assina o estado da busca para decidir se mostra a home; o resto da página não re-renderiza. */
function VitrineInicial() {
  const { loja } = useLocal();
  if (!useEstadoInicial()) return null;
  return (
    <>
      <Inicio />
      <h2 className="titulo-secao titulo-todos">{loja.todosProdutos}</h2>
    </>
  );
}

// Busca só no navegador (InstantSearch, sem o SSR do InstantSearchNext): a search key pública é restrita por
// referer e por limite de buscas por IP. Do servidor da Vercel a busca sairia sem referer (403) e com os IPs de
// todos os visitantes somados no mesmo limite.
function Corpo() {
  const [filtrosAbertos, setFiltrosAbertos] = useState(false);
  const { widgets, loja } = useLocal();

  useEffect(() => {
    if (!filtrosAbertos) return;
    const fechar = (e: KeyboardEvent) => e.key === "Escape" && setFiltrosAbertos(false);
    window.addEventListener("keydown", fechar);
    return () => window.removeEventListener("keydown", fechar);
  }, [filtrosAbertos]);

  return (
    <>
      <Faixa />
      <div className="cabecalho">
      <header className="topo">
        <Marca />
        <div className="busca">
          <SearchBox placeholder={loja.placeholder} translations={widgets.busca} />
          <PoweredBy />
        </div>
      </header>
      <Atalhos />
      </div>

      <VitrineInicial />

      <div className="barra">
        <button
          type="button"
          className="botao-filtros"
          aria-expanded={filtrosAbertos}
          aria-controls="painel-filtros"
          onClick={() => setFiltrosAbertos(true)}
        >
          {loja.filtros}
        </button>
        <Stats translations={widgets.stats} />
        <SortBy items={widgets.ordenacoes} />
      </div>

      <div className="conteudo">
        <aside id="painel-filtros" className={filtrosAbertos ? "filtros aberto" : "filtros"} aria-label={loja.filtros}>
          <div className="filtros-topo">
            <h2>{loja.filtros}</h2>
            <button type="button" onClick={() => setFiltrosAbertos(false)}>
              {loja.verProdutos}
            </button>
          </div>
          <Filtros />
        </aside>
        <main className="resultados">
          <SemResultados />
          <Hits hitComponent={CartaoProduto} />
          <Pagination translations={widgets.paginacao} />
        </main>
      </div>
      <Rodape />
    </>
  );
}

export function Loja({ idioma }: { idioma: Idioma }) {
  return (
    <ProvedorIdioma idioma={idioma}>
      <BuscaDaLoja />
    </ProvedorIdioma>
  );
}

function BuscaDaLoja() {
  const { indice } = useLocal();
  return (
    <InstantSearch searchClient={searchClient} indexName={indice} routing insights>
      <Configure hitsPerPage={24} attributesToHighlight={DESTACAR} />
      <Corpo />
      <Assistente />
    </InstantSearch>
  );
}
