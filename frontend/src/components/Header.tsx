import { useState } from "react";
import { Link, NavLink, useNavigate, useLocation } from "react-router-dom";
import { Menu, Search, X } from "lucide-react";

import { registrarBusqueda } from "@/lib/metricas";
import { useSitio } from "@/lib/sitio";
import CajaBusqueda from "@/components/CajaBusqueda";

export default function Header() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const navigate = useNavigate();
  const location = useLocation();
  // El menú lo controla `EnlaceMenu` desde el admin: PREDES reordena y oculta sin tocar código,
  // y Prioridades vive ahí con visible=false (ADR-P1).
  const { sitio } = useSitio();
  const top = sitio.menu.top;
  const nav = sitio.menu.header;

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const termino = q.trim();
    if (!termino) return;
    registrarBusqueda(termino);
    navigate(`/buscar?q=${encodeURIComponent(termino)}`);
  }

  return (
    <header className="sticky top-0 z-40">
      <div className="bg-mountain-500 text-white">
        <div className="container-page flex items-center justify-end gap-5 h-8 text-xs font-medium">
          {top.map((item) =>
            item.url.startsWith("http") ? (
              <a
                key={item.url}
                href={item.url}
                target="_blank"
                rel="noreferrer"
                className="text-white/90 hover:text-white no-underline"
              >
                {item.texto}
              </a>
            ) : (
              <Link
                key={item.url}
                to={item.url}
                className="text-white/90 hover:text-white no-underline"
              >
                {item.texto}
              </Link>
            )
          )}
          {sitio.config.email_contacto ? (
            <a
              href={`mailto:${sitio.config.email_contacto}`}
              className="text-white/90 hover:text-white no-underline"
            >
              Contacto
            </a>
          ) : (
            <Link to="/sobre" className="text-white/90 hover:text-white no-underline">
              Contacto
            </Link>
          )}
        </div>
      </div>

      <div className="bg-mountain-700 text-white">
        <div className="container-page flex items-center gap-4 xl:gap-6 h-16">
          <Link to="/" className="flex items-center gap-3 shrink-0 text-white no-underline">
            <img src="/logo-predes-white.svg" alt="PREDES" className="h-8 w-auto" />
            <span className="font-display text-lg font-bold leading-none border-l border-white/30 pl-3">
              Kallpachakuy
              <span className="block text-xs text-white/80 font-medium tracking-wide">
                Observatorio Cusco
              </span>
            </span>
          </Link>

          {/* En escritorio el menú va en **una sola línea**: `whitespace-nowrap` para que ningún
              enlace parta su texto en dos, y `shrink-0` aquí (con `min-w-0` en el buscador) para
              que cuando falte sitio ceda el campo de búsqueda y no el menú. Por debajo de `xl` se
              recorta el espaciado, que es lo que falta a 1024 px. */}
          <nav aria-label="Principal" className="hidden lg:flex items-center gap-0.5 xl:gap-1 ml-1 xl:ml-2 shrink-0">
            {nav.map((item) => (
              <NavLink
                key={item.url}
                to={item.url}
                className={({ isActive }) =>
                  `px-2.5 xl:px-3 py-2 rounded-md text-sm font-medium whitespace-nowrap no-underline transition ${
                    isActive
                      ? "text-white bg-white/15 font-semibold"
                      : "text-white/85 hover:text-white hover:bg-white/10"
                  }`
                }
              >
                {item.texto}
              </NavLink>
            ))}
          </nav>

          {/* El buscador es el que cede el espacio: `min-w-0` aquí y en el input —un `<input>` trae
              ancho mínimo intrínseco y sin eso no bajaría de `w-56`, comprimiendo el menú. Las
              clases visuales de la caja viven en el tono «cabecera» de `CajaBusqueda`; este `form`
              solo la coloca.

              Pero ceder tiene un límite: entre `lg` y `xl` el menú y el campo ya no caben juntos
              —con las etiquetas actuales el `nav` mide 555 px a 1024 px y al campo le quedaban
              63 px, que no dan para escribir—, así que ahí el campo se retira y deja una lupa. De
              `md` a `lg` sí se muestra, porque el menú está detrás de la hamburguesa y sobra
              sitio; desde `xl` vuelve entero. */}
          <form onSubmit={onSubmit} className="hidden md:flex lg:hidden xl:flex ml-auto min-w-0">
            <CajaBusqueda
              value={q}
              onChange={setQ}
              placeholder="Buscar distrito, peligro, medida…"
              etiqueta="Buscar"
              tono="cabecera"
            />
          </form>

          {/* `aria-label` de «ir al buscador» y no de «buscar»: esto navega, no busca en sitio.
              Además evita chocar con el `input[aria-label="Buscar"]` que localizan las pruebas. */}
          <Link
            to="/buscar"
            aria-label="Ir al buscador"
            className="hidden lg:flex xl:hidden ml-auto items-center justify-center p-2 rounded-md text-white hover:bg-white/10 no-underline"
          >
            <Search className="w-5 h-5" />
          </Link>

          <button
            aria-label="Menú"
            className="lg:hidden ml-auto p-2 rounded-md text-white hover:bg-white/10"
            onClick={() => setOpen((v) => !v)}
          >
            {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {open && (
        <div className="lg:hidden border-t border-white/20 bg-mountain-700 text-white">
          <div className="container-page py-3 flex flex-col gap-1">
            {nav.map((item) => (
              <NavLink
                key={item.url}
                to={item.url}
                onClick={() => setOpen(false)}
                className={({ isActive }) =>
                  `px-3 py-2 rounded-md text-sm font-medium no-underline ${
                    isActive ? "bg-white/15 text-white" : "text-white/85"
                  }`
                }
              >
                {item.texto}
              </NavLink>
            ))}
            <form onSubmit={onSubmit} className="flex mt-2 pt-2 border-t border-white/20">
              <CajaBusqueda
                value={q}
                onChange={setQ}
                placeholder="Buscar…"
                etiqueta="Buscar"
                tono="cabecera-movil"
                className="flex-1"
              />
            </form>
          </div>
        </div>
      )}

      {/* hack: refresca isActive cuando cambia la ruta — útil con search params */}
      <span className="hidden">{location.pathname}</span>
    </header>
  );
}
