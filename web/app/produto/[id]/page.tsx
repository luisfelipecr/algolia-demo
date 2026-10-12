import { Produto } from "@/app/components/Produto";
import { SoNoCliente } from "@/app/components/SoNoCliente";

export default async function PaginaProduto({ params }: PageProps<"/produto/[id]">) {
  const { id } = await params;
  return (
    <SoNoCliente reserva={<p className="carregando">Carregando…</p>}>
      <Produto id={decodeURIComponent(id)} idioma="pt" />
    </SoNoCliente>
  );
}
