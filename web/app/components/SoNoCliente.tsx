"use client";

import { useSyncExternalStore } from "react";

const nada = () => () => {};

/** Renderiza os filhos só no navegador; no servidor, a reserva. A loja inteira usa isso (ver Loja.tsx). */
export function SoNoCliente({ children, reserva = null }: { children: React.ReactNode; reserva?: React.ReactNode }) {
  const noCliente = useSyncExternalStore(
    nada,
    () => true,
    () => false,
  );
  return noCliente ? <>{children}</> : <>{reserva}</>;
}
