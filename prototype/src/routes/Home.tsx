import { Link } from "react-router-dom";
import {
  MapPin, Lightbulb, Coins, Target, Search, ArrowRight, Mountain
} from "lucide-react";
import { useJsonData } from "@/lib/useJsonData";
import type { CentroPoblado, ClasificacionPeligro } from "@/lib/types";
import { formatNumber } from "@/lib/semaforo";

const VENTANAS = [
  {
    to: "/peligros",
    icon: MapPin,
    titulo: "Ventana 1 — Peligros",
    pregunta: "¿Qué peligros afectan más a mi distrito?",
    color: "from-level-4/80 to-level-3/70",
  },
  {
    to: "/medidas",
    icon: Lightbulb,
    titulo: "Ventana 2 — Medidas",
    pregunta: "¿Qué medidas están funcionando?",
    color: "from-mountain-700 to-mountain-500",
  },
  {
    to: "/inversion",
    icon: Coins,
    titulo: "Ventana 3 — Inversión",
    pregunta: "¿Cuánto y cómo se invierte (PPR 0068)?",
    color: "from-sky-700 to-sky-500",
  },
  {
    to: "/prioridades",
    icon: Target,
    titulo: "Ventana 4 — Prioridades",
    pregunta: "¿Dónde debería invertirse primero?",
    color: "from-earth-700 to-earth-500",
  },
];

export default function Home() {
  const ccpp = useJsonData<CentroPoblado[]>("/data/ccpp.json");
  const peligros = useJsonData<ClasificacionPeligro[]>("/data/peligros.json");

  const totalCcpp = ccpp.status === "ok" ? ccpp.data.length : null;
  const totalClasif = peligros.status === "ok" ? peligros.data.length : null;
  const ccppAltos =
    peligros.status === "ok"
      ? new Set(peligros.data.filter((p) => p.nivel >= 3).map((p) => p.codigo_ccpp)).size
      : null;
  const distritos =
    ccpp.status === "ok"
      ? new Set(ccpp.data.map((c) => c.ubigeo_distrito)).size
      : null;

  return (
    <>
      {/* Hero */}
      <section className="relative text-white overflow-hidden">
        <img
          src="/img/hero-comunidad.jpg"
          alt="Comunidad altoandina construyendo una qocha en Cusco"
          className="absolute inset-0 w-full h-full object-cover"
        />
        <div
          className="absolute inset-0 bg-gradient-to-r from-mountain-900/90 via-mountain-900/70 to-mountain-700/40"
          aria-hidden="true"
        />
        <div className="container-page relative py-16 md:py-24 pb-24 md:pb-32">
          <div className="max-w-3xl">
            <span className="chip bg-white/15 text-white border border-white/20 mb-4">
              <Mountain className="w-3 h-3" /> Cusco, Perú
            </span>
            <h1 className="font-display text-4xl md:text-6xl font-extrabold leading-tight">
              Observatorio del riesgo y la adaptación climática en Cusco.
            </h1>
            <p className="mt-5 text-lg md:text-xl text-mountain-100/90 max-w-2xl">
              Monitoreamos peligros, prácticas que funcionan, inversión pública y prioridades
              de los gobiernos locales y regionales para reducir el riesgo de desastres.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/peligros" className="btn-primary bg-white text-mountain-900 hover:bg-paper">
                Explorar mi distrito <ArrowRight className="w-4 h-4" />
              </Link>
              <Link to="/sobre" className="btn-ghost text-white hover:bg-white/10">
                Sobre el observatorio
              </Link>
            </div>
          </div>
        </div>
        {/* Curva inferior estilo predes.org.pe */}
        <svg
          className="absolute bottom-0 left-0 w-full h-10 md:h-16 pointer-events-none"
          viewBox="0 0 1920 64"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path d="M0,64 L0,48 C480,-16 1440,-16 1920,48 L1920,64 Z" fill="#FAFAF7" />
        </svg>
      </section>

      {/* Cifras */}
      <section className="container-page -mt-10 relative z-10">
        <div className="card grid grid-cols-2 md:grid-cols-4 divide-x divide-ink-300/30 overflow-hidden">
          <Stat label="Centros poblados monitoreados" value={totalCcpp != null ? formatNumber(totalCcpp) : "…"} />
          <Stat label="Distritos cubiertos" value={distritos != null ? String(distritos) : "…"} />
          <Stat label="Clasificaciones de peligro" value={totalClasif != null ? formatNumber(totalClasif) : "…"} />
          <Stat label="CCPP con peligro alto/muy alto" value={ccppAltos != null ? formatNumber(ccppAltos) : "…"} accent />
        </div>
      </section>

      {/* 4 Ventanas */}
      <section className="container-page mt-16">
        <h2 className="font-display text-3xl font-bold text-mountain-700 text-center">Las 4 ventanas del observatorio</h2>
        <p className="text-ink-600 mt-2 max-w-2xl mx-auto text-center">
          De lo general al detalle — partimos de un mapa regional y llegamos a la actividad presupuestal
          de una municipalidad.
        </p>
        <div className="mt-8 grid gap-5 md:grid-cols-2 lg:grid-cols-4">
          {VENTANAS.map((v) => (
            <Link
              key={v.to}
              to={v.to}
              className={`relative overflow-hidden rounded-xl bg-gradient-to-br ${v.color} text-white p-6 shadow-sm hover:shadow-lg transition no-underline`}
            >
              <v.icon className="w-9 h-9 mb-3" />
              <div className="font-display font-bold text-lg">{v.titulo}</div>
              <p className="text-sm text-white/90 mt-1">{v.pregunta}</p>
              <ArrowRight className="absolute bottom-5 right-5 w-5 h-5 opacity-80" />
            </Link>
          ))}
        </div>
      </section>

      {/* Búsqueda */}
      <section className="container-page mt-16">
        <div className="card p-8 md:p-10 flex flex-col md:flex-row items-center gap-6">
          <Search className="w-12 h-12 text-mountain-700 shrink-0" />
          <div className="flex-1">
            <div className="font-display text-xl font-bold text-mountain-900">
              ¿Buscas tu distrito o un peligro específico?
            </div>
            <p className="text-ink-600 mt-1">
              Encuentra rápidamente información de tu localidad o filtra por tipo de peligro.
            </p>
          </div>
          <Link to="/peligros" className="btn-primary shrink-0">
            Ir al buscador <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </section>

      {/* Casos */}
      <section className="container-page mt-16">
        <h2 className="font-display text-3xl font-bold text-mountain-700 text-center">Casos recientes</h2>
        <p className="text-ink-600 mt-1 text-center">Prácticas comunales y distritales con resultados.</p>
        <div className="mt-8 grid gap-5 md:grid-cols-3">
          <CasoPreview img="/img/caso-qochas.jpg" titulo="Qochas comunales en Pampallacta" peligro="Sequía" />
          <CasoPreview img="/img/caso-chahuaytiri.jpg" titulo="Acondicionamiento térmico en Chahuaytiri" peligro="Heladas" />
          <CasoPreview img="/img/caso-calca.jpg" titulo="Brigadas contra incendios en Calca" peligro="Incendios" />
        </div>
        <div className="mt-8 text-center">
          <Link to="/medidas" className="btn-primary">Ver todas las medidas</Link>
        </div>
      </section>

    </>
  );
}

function Stat({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="p-5 md:p-6 text-center">
      <div className={`font-display font-extrabold text-2xl md:text-3xl ${accent ? "text-level-3" : "text-mountain-900"}`}>
        {value}
      </div>
      <div className="text-xs md:text-sm text-ink-600 mt-1">{label}</div>
    </div>
  );
}

function CasoPreview({
  img, titulo, peligro,
}: { img: string; titulo: string; peligro: string }) {
  return (
    <Link to="/medidas" className="card overflow-hidden hover:shadow-md transition no-underline">
      <div className="relative aspect-[3/2]">
        <img src={img} alt={titulo} className="absolute inset-0 w-full h-full object-cover" />
        <span className="chip absolute top-3 left-3 bg-white/90 text-level-3 border border-level-3/30">
          {peligro}
        </span>
      </div>
      <div className="p-5">
        <div className="font-semibold text-mountain-900">{titulo}</div>
      </div>
    </Link>
  );
}
