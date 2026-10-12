"use client";

import { useInstantSearch } from "react-instantsearch";

import { useLocal } from "@/lib/idioma";

// Fotos dos dados de exemplo Sunrise (commercetools), as mesmas dos produtos
const FOTOS = "https://s3-eu-west-1.amazonaws.com/commercetools-maximilian/products";

/** A vitrine editorial aparece só no estado inicial: sem busca, sem filtro e na primeira página. */
export function useEstadoInicial(): boolean {
  const { indexUiState } = useInstantSearch();
  const filtros = Object.keys(indexUiState).filter((k) => !["query", "page", "configure", "sortBy"].includes(k));
  return !indexUiState.query && !indexUiState.page && filtros.length === 0;
}

export function Inicio() {
  const { inicio } = useLocal();
  return (
    <>
      <section className="capa">
        <div className="capa-texto">
          <p className="sobretitulo">{inicio.sobretitulo}</p>
          <h1>{inicio.titulo}</h1>
          <p className="capa-sub">{inicio.sub}</p>
          <ul className="exemplos">
            {inicio.exemplos.map((e) => (
              <li key={e.texto}>
                <a href={e.href}>
                  {e.texto}
                  <span>{e.nota}</span>
                </a>
              </li>
            ))}
          </ul>
        </div>
        <div className="capa-fotos" aria-hidden="true">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={`${FOTOS}/078868_1_large.jpg`} alt="" />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={`${FOTOS}/086663_1_large.jpg`} alt="" />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={`${FOTOS}/085007_1_large.jpg`} alt="" />
        </div>
      </section>

      <ul className="diferenciais">
        {inicio.diferenciais.map((d) => (
          <li key={d.titulo}>
            <strong>{d.titulo}</strong> {d.texto}
          </li>
        ))}
      </ul>

      <section className="categorias" aria-labelledby="titulo-categorias">
        <h2 id="titulo-categorias">{inicio.porCategoria}</h2>
        <ul>
          {inicio.categorias.map((c) => (
            <li key={c.rotulo}>
              <a href={c.href}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`${FOTOS}/${c.foto}_1_large.jpg`}
                  alt=""
                  loading="lazy"
                  className={c.calcado ? "calcado" : undefined}
                />
                <span>{c.rotulo}</span>
              </a>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
