import { Loja } from "./components/Loja";
import { SoNoCliente } from "./components/SoNoCliente";

export default function Pagina() {
  return (
    <SoNoCliente reserva={<p className="carregando">Carregando a loja…</p>}>
      <Loja idioma="pt" />
    </SoNoCliente>
  );
}
