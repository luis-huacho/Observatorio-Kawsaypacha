import { useState } from "react";
import { Link, NavLink, useNavigate, useLocation } from "react-router-dom";
import { Search, Menu, X, Mountain } from "lucide-react";

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
    <header className="sticky top-0 z-40 bg-white/95 backdrop-blur border-b border-ink-300/40">
      <div className="container-page flex items-center gap-6 h-16">
        <Link to="/" className="flex items-center gap-2 text-mountain-900 no-underline">
          <Mountain className="w-7 h-7 text-mountain-700" />
          <span className="font-display text-lg font-bold leading-none">
            Kawsaypacha
            <span className="block text-xs text-ink-600 font-medium tracking-wide">
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
                    ? "text-mountain-900 bg-mountain-100"
                    : "text-ink-600 hover:text-mountain-900 hover:bg-mountain-100/60"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <form
          onSubmit={onSubmit}
          className="hidden md:flex items-center ml-auto bg-paper rounded-lg border border-ink-300/50 px-3 py-1.5 focus-within:border-mountain-500 transition"
        >
          <Search className="w-4 h-4 text-ink-600" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar distrito, peligro, medida…"
            className="bg-transparent border-0 outline-none text-sm ml-2 w-56"
            aria-label="Buscar"
          />
        </form>

        <button
          aria-label="Menú"
          className="lg:hidden ml-auto p-2 rounded-md hover:bg-mountain-100"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {open && (
        <div className="lg:hidden border-t border-ink-300/40 bg-white">
          <div className="container-page py-3 flex flex-col gap-1">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setOpen(false)}
                className={({ isActive }) =>
                  `px-3 py-2 rounded-md text-sm font-medium no-underline ${
                    isActive ? "bg-mountain-100 text-mountain-900" : "text-ink-600"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
            <form onSubmit={onSubmit} className="flex items-center gap-2 mt-2 pt-2 border-t border-ink-300/40">
              <Search className="w-4 h-4 text-ink-600" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Buscar…"
                className="flex-1 bg-paper rounded-md px-3 py-2 text-sm border border-ink-300/40"
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
