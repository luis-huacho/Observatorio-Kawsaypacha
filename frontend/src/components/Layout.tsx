import { useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { useMetricaPagina } from "@/lib/metricas";
import { ProveedorSitio, useSitio } from "@/lib/sitio";

import Footer from "./Footer";
import Header from "./Header";

export default function Layout() {
  return (
    // El proveedor envuelve todo el árbol: Header, Footer y las páginas leen el mismo payload
    // de `/api/sitio/`, pedido una sola vez.
    <ProveedorSitio>
      <Estructura />
    </ProveedorSitio>
  );
}

function Estructura() {
  const { pathname } = useLocation();
  const { sitio } = useSitio();
  useMetricaPagina();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  return (
    <div className="flex flex-col min-h-screen">
      {/* Aviso administrable: si PREDES deja el campo vacío, la franja no existe. */}
      {sitio.config.mensaje_banner && (
        <div className="bg-earth-200 text-earth-700 text-sm">
          <div className="container-page py-2">{sitio.config.mensaje_banner}</div>
        </div>
      )}
      <Header />
      <main className="flex-1">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
