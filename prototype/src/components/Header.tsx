import { useState } from "react";
import { Link, NavLink, useNavigate, useLocation } from "react-router-dom";
import { Search, Menu, X } from "lucide-react";

const NAV = [
  { to: "/peligros", label: "Peligros" },
  { to: "/medidas", label: "Medidas" },
  { to: "/inversion", label: "Inversión" },
  { to: "/prioridades", label: "Prioridades" },
  { to: "/normativa", label: "Normativa" },
  { to: "/sobre", label: "Sobre" },
];

export default function Header() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const navigate = useNavigate();
  const location = useLocation();

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (q.trim()) navigate(`/buscar?q=${encodeURIComponent(q.trim())}`);
  }

  return (
    <header className="sticky top-0 z-40">
      <div className="bg-mountain-500 text-white">
        <div className="container-page flex items-center justify-end gap-5 h-8 text-xs font-medium">
          <a
            href="https://predes.org.pe/"
            target="_blank"
            rel="noreferrer"
            className="text-white/90 hover:text-white no-underline"
          >
            predes.org.pe
          </a>
          <Link to="/sobre" className="text-white/90 hover:text-white no-underline">
            Contacto
          </Link>
        </div>
      </div>

      <div className="bg-mountain-700 text-white">
        <div className="container-page flex items-center gap-6 h-16">
          <Link to="/" className="flex items-center gap-3 text-white no-underline">
            <img src="/logo-predes-white.svg" alt="PREDES" className="h-8 w-auto" />
            <span className="font-display text-lg font-bold leading-none border-l border-white/30 pl-3">
              Kawsaypacha
              <span className="block text-xs text-white/80 font-medium tracking-wide">
                Observatorio Cusco
              </span>
            </span>
          </Link>

          <nav className="hidden lg:flex items-center gap-1 ml-2">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `px-3 py-2 rounded-md text-sm font-medium no-underline transition ${
                    isActive
                      ? "text-white bg-white/15 font-semibold"
                      : "text-white/85 hover:text-white hover:bg-white/10"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <form
            onSubmit={onSubmit}
            className="hidden md:flex items-center ml-auto bg-white/95 rounded-lg border border-white/30 px-3 py-1.5 focus-within:border-white transition"
          >
            <Search className="w-4 h-4 text-ink-600" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Buscar distrito, peligro, medida…"
              className="bg-transparent border-0 outline-none text-sm ml-2 w-56 text-ink-900"
              aria-label="Buscar"
            />
          </form>

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
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setOpen(false)}
                className={({ isActive }) =>
                  `px-3 py-2 rounded-md text-sm font-medium no-underline ${
                    isActive ? "bg-white/15 text-white" : "text-white/85"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
            <form onSubmit={onSubmit} className="flex items-center gap-2 mt-2 pt-2 border-t border-white/20">
              <Search className="w-4 h-4 text-white/80" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Buscar…"
                className="flex-1 bg-white/95 rounded-md px-3 py-2 text-sm border border-white/30 text-ink-900"
                aria-label="Buscar"
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
