"use client";

import { useLocal } from "@/lib/idioma";

// Reserva para produto sem foto (ou foto que saiu do ar): amostra da cor e ícone da categoria, nada inventado.

const ICONES: Record<string, string> = {
  // traços simples em viewBox 0 0 24 24
  calcado: "M3 16h13l4 1.5V19H3zM4 16l1-6 4 1 2 3 4 1",
  bolsa: "M5 8h14l-1 12H6zM9 8V6a3 3 0 0 1 6 0v2",
  roupa: "M8 3 4 6l2 4 2-1v12h8V9l2 1 2-4-4-3h-2a2 2 0 0 1-4 0z",
  acessorio: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 8v4l3 2",
};

function icone(categoria: string): string {
  if (/Calçados|Shoes/.test(categoria)) return ICONES.calcado;
  if (/Bolsas|Bags/.test(categoria)) return ICONES.bolsa;
  if (/Roupas|Clothing/.test(categoria)) return ICONES.roupa;
  return ICONES.acessorio;
}

function fundo(amostraCor: string): string {
  // "multicolorido" vem com URL de imagem no lugar do hex
  if (!amostraCor.startsWith("#")) return "conic-gradient(#e10600, #fff200, #00ad4a, #0075bb, #c11271, #e10600)";
  return amostraCor;
}

export function SemFoto({ categoria, amostraCor, cor }: { categoria: string; amostraCor: string; cor: string }) {
  const { produto } = useLocal();
  return (
    <div className="sem-foto" role="img" aria-label={produto.fotoAria(cor)}>
      <span className="amostra" style={{ background: fundo(amostraCor) }} />
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d={icone(categoria)} />
      </svg>
      <span className="aviso">{produto.fotoIndisponivel}</span>
    </div>
  );
}
