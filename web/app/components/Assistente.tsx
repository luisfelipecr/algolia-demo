"use client";

import {
  ArrowRightIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  type ClientSideToolComponentProps,
  createButtonComponent,
  createCarouselToolComponent,
  getApplyFiltersParamsFromToolInput,
  type Pragma,
} from "instantsearch-ui-components";
import Link from "next/link";
import { createElement, Fragment, useEffect, useMemo, useRef, useState } from "react";
import { Chat, ChatTrigger, SearchIndexToolType } from "react-instantsearch";

import type { Produto } from "@/lib/algolia";
import { useLocal } from "@/lib/idioma";

// Assistente de compras do Agent Studio, no widget Chat do React InstantSearch.
//
// Chave própria: o widget mandaria ao agente a search key do site, que é restrita por referer e por IP, e o
// agente busca a partir dos servidores da Algolia (sem o referer do navegador): 401. A chave do chat só tem
// `search`, os índices produtos_* e limite de hits; o gasto com o LLM fica protegido pelo rate limit e pelos
// approved domains do agente (Safety Controls) e pelo teto da chave do provedor.
const APP_ID = process.env.NEXT_PUBLIC_ALGOLIA_APP_ID;
const AGENTE = process.env.NEXT_PUBLIC_ALGOLIA_AGENT_ID;
const CHAVE_CHAT = process.env.NEXT_PUBLIC_ALGOLIA_CHAT_KEY;

// Constante de módulo: o widget compara as props por referência (ver Loja.tsx).
const TRANSPORTE =
  APP_ID && AGENTE && CHAVE_CHAT
    ? {
        api: `https://${APP_ID}.algolia.net/agent-studio/1/agents/${AGENTE}/completions?compatibilityMode=ai-sdk-5`,
        headers: { "x-algolia-application-id": APP_ID, "x-algolia-api-key": CHAVE_CHAT },
      }
    : undefined;

// O widget guarda a conversa na sessão por agente, não por língua: sem isto, a loja em inglês abriria a conversa
// em português (e vice-versa). Antes de o Chat ler o histórico, se a conversa salva for de outra língua, ela é
// apagada. A chave é a `CACHE_KEY` de instantsearch.js (lib/chat/chat.js, 4.x), que o pacote não exporta pelo
// caminho público: conferir ao atualizar o react-instantsearch.
const CONVERSA = `instantsearch-chat-initial-messages-${AGENTE}`;
const LINGUA_DA_CONVERSA = "loja-demo-chat-idioma";

function conversaNaLingua(idioma: string) {
  try {
    if (sessionStorage.getItem(LINGUA_DA_CONVERSA) !== idioma) {
      sessionStorage.removeItem(CONVERSA);
      sessionStorage.setItem(LINGUA_DA_CONVERSA, idioma);
    }
  } catch {
    // sessão indisponível (modo privado, armazenamento bloqueado): o widget também não terá o que restaurar
  }
  return idioma;
}

type Item = Partial<Produto> & { objectID: string; __position?: number; __queryID?: string };

/** Produto citado pelo agente: o mesmo dado do índice, com link para a página do produto na língua da loja. */
function ProdutoNoChat({ item }: { item: Item }) {
  const { prefixo, formatarPreco, chat, produto } = useLocal();
  return (
    <Link href={`${prefixo}/produto/${encodeURIComponent(item.objectID)}`} className="chat-produto">
      {item.imagem && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={item.imagem} alt="" loading="lazy" />
      )}
      <span className="chat-produto-marca">{item.marca}</span>
      <span className="chat-produto-nome">{item.nome}</span>
      {typeof item.preco === "number" && (
        <span className="chat-produto-preco">{formatarPreco(item.preco)}</span>
      )}
      {/* o carrossel mostra todos os hits da busca do agente, inclusive esgotados (o texto da resposta não) */}
      {item.em_estoque === false && <span className="chat-produto-esgotado">{produto.semEstoque}</span>}
      <span className="chat-produto-ver">{chat.verProduto}</span>
    </Link>
  );
}

// A ferramenta de busca do widget, com o mesmo carrossel e o mesmo "ver todos" (aplica na loja os filtros que o
// agente usou), mas com o cabeçalho traduzido: o padrão escreve "7 of 7 results" e "View all" fixo em inglês.
// O pacote tipa o renderer no formato do Preact; em runtime é o createElement do React, como o próprio
// react-instantsearch passa a ele.
const h = createElement as unknown as Pragma;
const Carrossel = createCarouselToolComponent({ createElement: h, Fragment, useEffect, useMemo, useRef, useState });
const Botao = createButtonComponent({ createElement: h });

type Cabecalho = Parameters<NonNullable<Parameters<typeof Carrossel>[0]["headerComponent"]>>[0];

function CabecalhoDaBusca(p: Cabecalho) {
  const { chat } = useLocal();
  if (p.nbItems < 1) return <></>;
  const verTodos = () => {
    if (!p.input || !p.applyFilters) return;
    const params = p.applyFilters(getApplyFiltersParamsFromToolInput(p.input, p.resolvedSearchParams));
    const destino = p.getSearchPageURL?.(params);
    // fora da página de busca (ex.: no produto), vai para a busca; nela, os filtros já foram aplicados
    if (destino && new URL(destino, window.location.href).pathname !== window.location.pathname) {
      window.location.href = destino;
    }
    p.onClose();
  };
  return (
    <div className="ais-ChatToolSearchIndexCarouselHeader">
      <div className="ais-ChatToolSearchIndexCarouselHeaderResults">
        {p.nbHits ? (
          <div className="ais-ChatToolSearchIndexCarouselHeaderCount">{chat.resultados(p.nbItems, p.nbHits)}</div>
        ) : null}
        <Botao variant="ghost" size="sm" onClick={verTodos} className="ais-ChatToolSearchIndexCarouselHeaderViewAll">
          {chat.verTodos}
          <ArrowRightIcon createElement={h} />
        </Botao>
      </div>
      {p.nbItems > 2 && (
        <div className="ais-ChatToolSearchIndexCarouselHeaderScrollButtons">
          <Botao
            variant="outline"
            size="sm"
            iconOnly
            onClick={p.scrollLeft}
            disabled={!p.canScrollLeft}
            aria-label={chat.anterior}
            className="ais-ChatToolSearchIndexCarouselHeaderScrollButton"
          >
            <ChevronLeftIcon createElement={h} />
          </Botao>
          <Botao
            variant="outline"
            size="sm"
            iconOnly
            onClick={p.scrollRight}
            disabled={!p.canScrollRight}
            aria-label={chat.proximos}
            className="ais-ChatToolSearchIndexCarouselHeaderScrollButton"
          >
            <ChevronRightIcon createElement={h} />
          </Botao>
        </div>
      )}
    </div>
  );
}

function BuscaNoChat(toolProps: ClientSideToolComponentProps) {
  const { chat } = useLocal();
  return (
    <Carrossel
      toolProps={toolProps}
      itemComponent={ProdutoNoChat}
      headerComponent={CabecalhoDaBusca}
      headerProps={{ showViewAll: true }}
      getSearchPageURL={chat.paginaDeBusca}
    />
  );
}

const FERRAMENTAS = { [SearchIndexToolType]: { layoutComponent: BuscaNoChat } };

type Vazio = { sendMessage?: (mensagem: { text: string }) => unknown };

/** Tela inicial do chat: o que o assistente faz e três perguntas de exemplo (fixas, sem chamada de LLM). */
function Saudacao({ sendMessage }: Vazio) {
  const { chat } = useLocal();
  return (
    <div className="chat-saudacao">
      <p className="chat-saudacao-titulo">{chat.saudacao.titulo}</p>
      <p>{chat.saudacao.texto}</p>
      <ul>
        {chat.saudacao.exemplos.map((texto) => (
          <li key={texto}>
            <button type="button" onClick={() => sendMessage?.({ text: texto })}>
              {texto}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function Assistente() {
  const { chat, idioma } = useLocal();
  // inicializador do useState: roda uma vez, antes de o Chat montar e ler a conversa salva
  useState(() => conversaNaLingua(idioma));
  if (!TRANSPORTE || !AGENTE) return null;
  return (
    <>
      <ChatTrigger aria-label={chat.abrir} />
      <Chat
        agentId={AGENTE}
        transport={TRANSPORTE}
        translations={chat.traducoes}
        itemComponent={ProdutoNoChat}
        emptyComponent={Saudacao}
        tools={FERRAMENTAS}
        getSearchPageURL={chat.paginaDeBusca}
      />
    </>
  );
}
