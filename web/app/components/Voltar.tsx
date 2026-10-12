"use client";

import { useRouter } from "next/navigation";

import { useLocal } from "@/lib/idioma";

// Volta para a busca de onde o cliente veio (com filtros e página); sem histórico, vai para a loja.
export function Voltar() {
  const router = useRouter();
  const { prefixo, produto } = useLocal();
  return (
    <button
      type="button"
      className="voltar"
      onClick={() => (window.history.length > 1 ? router.back() : router.push(prefixo || "/"))}
    >
      {produto.voltarBusca}
    </button>
  );
}
