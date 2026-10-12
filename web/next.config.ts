import type { NextConfig } from "next";

// cacheComponents (padrão do create-next-app 16) fica desligado: foi testado com o InstantSearchNext (o prerender
// quebrava com "headers must not be used within a client component"); a loja hoje busca só no navegador.
const nextConfig: NextConfig = {};

export default nextConfig;
