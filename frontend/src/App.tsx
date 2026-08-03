import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Home from "./routes/Home";
import Peligros from "./routes/Peligros";
import PeligroDetalle from "./routes/PeligroDetalle";
import Medidas from "./routes/Medidas";
import MedidaDetalle from "./routes/MedidaDetalle";
import Noticias from "./routes/Noticias";
import NoticiaDetalle from "./routes/NoticiaDetalle";
import Inversion from "./routes/Inversion";
// Prioridades NO se registra (ADR-P1): la ventana quedó desactivada por decisión de reunión y
// el componente se conserva sin ruta. Reactivarla es descomentar aquí y poner visible=true en
// su EnlaceMenu.
// import Prioridades from "./routes/Prioridades";
import Videos from "./routes/Videos";
import Eventos from "./routes/Eventos";
import Comparar from "./routes/Comparar";
import Normativa from "./routes/Normativa";
import NormaDetalle from "./routes/NormaDetalle";
import Recursos from "./routes/Recursos";
import Sobre from "./routes/Sobre";
import Buscar from "./routes/Buscar";
import NotFound from "./routes/NotFound";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/peligros" element={<Peligros />} />
        <Route path="/peligros/:codigo" element={<PeligroDetalle />} />
        <Route path="/medidas" element={<Medidas />} />
        <Route path="/medidas/:slug" element={<MedidaDetalle />} />
        {/* Noticias no está en el menú principal: se llega desde la portada y el pie. */}
        <Route path="/noticias" element={<Noticias />} />
        <Route path="/noticias/:slug" element={<NoticiaDetalle />} />
        <Route path="/inversion" element={<Inversion />} />
        <Route path="/videos" element={<Videos />} />
        <Route path="/eventos" element={<Eventos />} />
        <Route path="/comparar" element={<Comparar />} />
        <Route path="/normativa" element={<Normativa />} />
        <Route path="/normativa/:slug" element={<NormaDetalle />} />
        <Route path="/recursos" element={<Recursos />} />
        <Route path="/sobre" element={<Sobre />} />
        <Route path="/buscar" element={<Buscar />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
