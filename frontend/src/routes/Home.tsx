import { Link } from "react-router-dom";
import {
  MapPin, Lightbulb, Coins, Search, ArrowRight, Mountain
} from "lucide-react";
import { useApi, type Pagina } from "@/lib/api";
import { useBloque } from "@/lib/sitio";
import Reveal from "@/components/Reveal";
import type { Distrito, Noticia, Norma, ResumenPeligros, InversionResponse } from "@/lib/types";
import { formatNumber, formatFecha } from "@/lib/semaforo";
import { TarjetaNoticiaCompacta } from "@/routes/Noticias";

const SECCIONES = [
  {
    to: "/peligros",
    icon: MapPin,
    titulo: "Exposición a peligros naturales",
    pregunta: "¿Qué peligros afectan más a mi distrito?",
    color: "from-level-4/80 to-level-3/70",
  },
  {
    to: "/medidas",
    icon: Lightbulb,
    titulo: "Buenas prácticas",
    pregunta: "¿Qué medidas están funcionando?",
    color: "from-mountain-700 to-mountain-500",
  },
  {
    to: "/inversion",
    icon: Coins,
    titulo: "Inversión",
    pregunta: "Cuánto y en qué se invirte el PP0068",
    color: "from-sky-700 to-sky-500",
  },
];

export default function Home() {
  // Las cifras vienen agregadas del servidor: calcularlas en el cliente exigiría descargar las
  // 10,978 clasificaciones solo para contar (spec 06).
  const resumen = useApi<ResumenPeligros>("/peligros/resumen/");
  const distritosApi = useApi<Distrito[]>("/territorio/distritos/");
  const medidasExito = useApi<Pagina<unknown>>("/medidas/", { resultado: "exito", page_size: 1 });
  const inversion = useApi<InversionResponse>("/inversion/");

  const cifras = resumen.status === "ok" ? resumen.data : null;
  const distritos = distritosApi.status === "ok" ? distritosApi.data.length : null;
  const experienciasExitosas = medidasExito.status === "ok" ? medidasExito.data.count : null;
  // Sin ejercicio visible el tablero responde `disponible: false` (ADR-D3): la cifra se queda en
  // `null` y la tarjeta muestra "…", igual que mientras carga.
  const municipiosConEjecucion =
    inversion.status === "ok" && inversion.data.disponible
      ? inversion.data.agregados.entidades_con_devengado
      : null;
  // Centros poblados, no clasificaciones: es la unidad de `por_ccpp` y la que cuadra con la
  // tabla del visor. Sumar por peligro contaría cada CCPP tantas veces como peligros tenga.
  const ccppAltos = cifras
    ? Number(cifras.por_ccpp.niveles["3"]) + Number(cifras.por_ccpp.niveles["4"])
    : null;

  // Bloque de actualidad: lo más reciente de cada sección editorial. El API ya ordena por fecha
  // descendente, así que basta pedir la primera página con tres elementos.
  const noticias = useApi<Pagina<Noticia>>("/noticias/", { page_size: 3 });
  const normas = useApi<Pagina<Norma>>("/normativa/", { page_size: 3 });

  const ultimasNoticias = noticias.status === "ok" ? noticias.data.results : [];
  const ultimasNormas = normas.status === "ok" ? normas.data.results : [];

  // Hero administrable: el título y el subtítulo salen de `BloqueTexto`, con los del prototipo
  // como respaldo mientras carga.
  const heroTitulo = useBloque(
    "home.hero.titulo",
    "<p>Observatorio para la Gestión del riesgo de desastres y la adaptación al cambio climático.</p>"
  );
  const heroSubtitulo = useBloque(
    "home.hero.subtitulo",
    "<p>Monitoreamos y facilitamos información sobre los peligros, inversión, normativa, medidas " +
      "y buenas prácticas para la gestión del riesgo y la adaptación climática.</p>"
  );

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
            <span className="chip bg-white/15 text-white border border-white/20 mb-4 animate-fade-up">
              <Mountain className="w-3 h-3" /> Cusco, Perú
            </span>
            {/* Título y subtítulo administrables. `[&>p]:m-0` porque el bloque llega envuelto
                en <p> desde CKEditor y aquí el margen lo pone el contenedor. */}
            <h1
              className="font-display text-4xl md:text-6xl font-extrabold leading-tight animate-fade-up [&>p]:m-0"
              style={{ animationDelay: "80ms" }}
              dangerouslySetInnerHTML={{ __html: heroTitulo }}
            />
            <div
              className="mt-5 text-lg md:text-xl text-mountain-100/90 max-w-2xl animate-fade-up [&>p]:m-0"
              style={{ animationDelay: "160ms" }}
              dangerouslySetInnerHTML={{ __html: heroSubtitulo }}
            />
            <div className="mt-8 flex flex-wrap gap-3 animate-fade-up" style={{ animationDelay: "240ms" }}>
              <Link to="/sobre" className="btn-ghost text-white hover:bg-white/10">
                Sobre el observatorio
              </Link>
              <Link to="/peligros" className="btn-primary bg-white text-mountain-900 hover:bg-paper">
                Explorar mi distrito <ArrowRight className="w-4 h-4" />
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
        <Reveal>
          <div className="card grid grid-cols-2 md:grid-cols-4 divide-x divide-ink-300/30 overflow-hidden">
            <Stat label="Distritos cubiertos" value={distritos != null ? String(distritos) : "…"} />
            <Stat label="CCPP con peligro alto/muy alto" value={ccppAltos != null ? formatNumber(ccppAltos) : "…"} accent />
            <Stat label="Nº de experiencias exitosas" value={experienciasExitosas != null ? formatNumber(experienciasExitosas) : "…"} />
            <Stat label="Nº de municipios con presupuesto ejecutado" value={municipiosConEjecucion != null ? formatNumber(municipiosConEjecucion) : "…"} />
          </div>
        </Reveal>
      </section>

      {/* Secciones */}
      <section className="container-page mt-16">
        <h2 className="font-display text-3xl font-bold text-mountain-700 text-center">Explora el observatorio</h2>
        <p className="text-ink-600 mt-2 max-w-2xl mx-auto text-center">
          De lo general al detalle — partimos de un mapa regional y llegamos a la actividad presupuestal
          de una municipalidad.
        </p>
        <div className="mt-8 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {SECCIONES.map((v, i) => (
            <Reveal key={v.to} delay={i * 80}>
              <Link
                to={v.to}
                className={`relative block h-full overflow-hidden rounded-xl bg-gradient-to-br ${v.color} text-white p-6 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition duration-300 no-underline`}
              >
                <v.icon className="w-9 h-9 mb-3" />
                <div className="font-display font-bold text-lg">{v.titulo}</div>
                <p className="text-sm text-white/90 mt-1">{v.pregunta}</p>
                <ArrowRight className="absolute bottom-5 right-5 w-5 h-5 opacity-80" />
              </Link>
            </Reveal>
          ))}
        </div>
      </section>

      {/* Búsqueda */}
      <section className="container-page mt-16">
        <Reveal>
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
        </Reveal>
      </section>

      {/* Casos */}
      <section className="container-page mt-16">
        <h2 className="font-display text-3xl font-bold text-mountain-700 text-center">Casos recientes</h2>
        <p className="text-ink-600 mt-1 text-center">Prácticas comunales y distritales con resultados.</p>
        <div className="mt-8 grid gap-5 md:grid-cols-3">
          {/* Cada tarjeta lleva a su ficha, no al listado genérico. */}
          {[
            { slug: "qochas-pampallacta", img: "/img/caso-qochas.jpg", titulo: "Qochas comunales en Pampallacta", peligro: "Sequía" },
            { slug: "viviendas-heladas-chahuaytiri", img: "/img/caso-chahuaytiri.jpg", titulo: "Acondicionamiento térmico en Chahuaytiri", peligro: "Heladas" },
            { slug: "brigadas-incendios-calca", img: "/img/caso-calca.jpg", titulo: "Brigadas contra incendios en Calca", peligro: "Incendios forestales" },
          ].map((c, i) => (
            <Reveal key={c.slug} delay={i * 80}>
              <CasoPreview slug={c.slug} img={c.img} titulo={c.titulo} peligro={c.peligro} />
            </Reveal>
          ))}
        </div>
        <div className="mt-8 text-center">
          <Link to="/medidas" className="btn-primary">Ver todas las medidas</Link>
        </div>
      </section>

      {/* Actualidad — noticias y normativa a dos columnas. Van juntas y no como dos bandas
          apiladas: la portada ya encadena tres grillas de tarjetas y agruparlas las lee
          como lo que son, un solo bloque de lo más reciente. */}
      <section className="container-page mt-16 mb-4">
        <div className="grid lg:grid-cols-2 gap-10 lg:gap-12">
          <div>
            <div className="flex items-baseline justify-between gap-4 mb-1">
              <h2 className="font-display text-2xl font-bold text-mountain-700">
                Últimas noticias
              </h2>
              <Link
                to="/noticias"
                className="inline-flex items-center gap-1 text-sm text-mountain-700 shrink-0"
              >
                Ver todas <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
            <p className="text-ink-600 text-sm">
              Publicaciones y artículos del observatorio.
            </p>
            <div className="mt-5 space-y-4">
              {ultimasNoticias.map((n, i) => (
                <Reveal key={n.slug} delay={i * 70}>
                  <TarjetaNoticiaCompacta noticia={n} />
                </Reveal>
              ))}
            </div>
          </div>

          <div>
            <div className="flex items-baseline justify-between gap-4 mb-1">
              <h2 className="font-display text-2xl font-bold text-mountain-700">
                Últimas normas
              </h2>
              <Link
                to="/normativa"
                className="inline-flex items-center gap-1 text-sm text-mountain-700 shrink-0"
              >
                Ver todas <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
            <p className="text-ink-600 text-sm">
              Marco normativo de la GRD con el análisis de PREDES.
            </p>
            <div className="mt-5 space-y-4">
              {ultimasNormas.map((n, i) => (
                <Reveal key={n.slug} delay={i * 70}>
                  <NormaPreview norma={n} />
                </Reveal>
              ))}
            </div>
          </div>
        </div>
      </section>

    </>
  );
}

/** Mismos chips y fecha en mono que la lista de /normativa, para que la norma se vea igual
    en los dos sitios. */
function NormaPreview({ norma: n }: { norma: Norma }) {
  return (
    <Link
      to={`/normativa/${n.slug}`}
      className="card block p-5 hover:shadow-md transition no-underline"
    >
      <div className="flex flex-wrap items-center gap-2 mb-1">
        <span className="chip bg-mountain-100 text-mountain-900 border border-mountain-500/20">
          {n.tipo}
        </span>
        <span className="chip bg-sky-200/40 text-sky-700 border border-sky-500/20 capitalize">
          {n.ambito}
        </span>
        <span className="text-xs text-ink-600">{formatFecha(n.fecha)}</span>
      </div>
      <h3 className="font-display font-bold text-mountain-900 leading-tight">{n.titulo}</h3>
      <p className="text-sm text-ink-600 mt-1">{n.resumen}</p>
    </Link>
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
  slug, img, titulo, peligro,
}: { slug: string; img: string; titulo: string; peligro: string }) {
  return (
    <Link to={`/medidas/${slug}`} className="card block h-full overflow-hidden hover:shadow-md hover:-translate-y-0.5 transition duration-300 no-underline">
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
