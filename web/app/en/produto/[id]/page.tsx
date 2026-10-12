import { Produto } from "@/app/components/Produto";
import { SoNoCliente } from "@/app/components/SoNoCliente";

export default async function PaginaProdutoIngles({ params }: PageProps<"/en/produto/[id]">) {
  const { id } = await params;
  return (
    <SoNoCliente reserva={<p className="carregando">Loading…</p>}>
      <Produto id={decodeURIComponent(id)} idioma="en" />
    </SoNoCliente>
  );
}
