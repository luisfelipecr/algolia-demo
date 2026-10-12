"use client";

import { useState } from "react";

import { SemFoto } from "./SemFoto";

type Props = { src: string; alt: string; categoria: string; amostraCor: string; cor: string };

// Fotos hotlinkadas dos dados de exemplo Sunrise da commercetools; se uma sair do ar, cai no SemFoto.
// <img> simples em vez de next/image: evita o otimizador de imagens da Vercel para um host de terceiros.
export function Foto({ src, alt, categoria, amostraCor, cor }: Props) {
  const [falhou, setFalhou] = useState(false);
  if (!src || falhou) return <SemFoto categoria={categoria} amostraCor={amostraCor} cor={cor} />;
  // nas fotos do Sunrise o calçado ocupa só a parte de baixo do quadro: a classe amplia ancorando embaixo
  const classe = /Calçados|Shoes/.test(categoria) ? "foto calcado" : "foto";
  // eslint-disable-next-line @next/next/no-img-element
  return <img className={classe} src={src} alt={alt} loading="lazy" onError={() => setFalhou(true)} />;
}
