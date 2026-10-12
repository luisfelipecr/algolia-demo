import { Loja } from "@/app/components/Loja";
import { SoNoCliente } from "@/app/components/SoNoCliente";

export default function PaginaIngles() {
  return (
    <SoNoCliente reserva={<p className="carregando">Loading the store…</p>}>
      <Loja idioma="en" />
    </SoNoCliente>
  );
}
