import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CalendarDays } from "lucide-react";
import { useApiPaginado } from "@/lib/api";
import type { Noticia } from "@/lib/types";
import { TIPOS_NOTICIA } from "@/lib/types";
import { formatFecha } from "@/lib/semaforo";
import PageHeader from "@/components/PageHeader";
import EmptyState from "@/components/EmptyState";
import Reveal from "@/components/Reveal";
import FiltroTema from "@/components/FiltroTema";

/** Un color por tipo, para distinguir de un vistazo lo informativo de lo editorializado. */
export const TIPO_ESTILO: Record<Noticia["tipo"], string> = {
  noticia: "bg-mountain-100 text-mountain-900 border border-mountain-500/20",
  articulo: "bg-sky-200/40 text-sky-700 border border-sky-500/20",
  opinion: "bg-earth-200/50 text-earth-700 border border-earth-500/25",
  publicacion: "bg-mountain-500/15 text-mountain-800 border border-mountain-700/25",
  base_datos: "bg-ink-300/25 text-ink-900 border border-ink-600/25",
};

export default function Noticias() {
  const [tipo, setTipo] = useState("");
  const [params, setParams] = useSearchParams();
  const tema = params.get("tema") ?? "";

  // El filtrado lo hace el servidor: `?tipo=` y `?tema=` van al API en vez de recortar en
  // memoria una lista que ya no se descarga completa.
  const noticias = useApiPaginado<Noticia>("/noticias/", { tipo, tema });
  const filtradas = noticias.resultados;

  if (noticias.status === "loading" && !filtradas.length)
    return <div className="container-page py-12">Cargando…</div>;
  if (noticias.status === "error")
    return (
      <div className="container-page py-12">
        <EmptyState
          title="No se pudieron cargar las noticias"
          message={noticias.error?.message}
        />
      </div>
    );

  return (
    <>
      <PageHeader
        titulo="Noticias y artículos"
        descripcion="Publicaciones del Observatorio Kallpachakuy sobre la gestión del riesgo de desastres y la adaptación al cambio climático en la región Cusco."
      />
      <div className="container-page py-8">
        <div className="mb-6 max-w-xs">
          <label className="block text-xs font-medium text-ink-600 mb-1">Tipo de publicación</label>
          <select
            value={tipo}
            onChange={(e) => setTipo(e.target.value)}
            className="control w-full"
          >
            <option value="">Todas</option>
            {Object.entries(TIPOS_NOTICIA).map(([valor, etiqueta]) => (
              <option key={valor} value={valor}>{etiqueta}</option>
            ))}
          </select>
        </div>

        <FiltroTema tema={tema} onLimpiar={() => setParams({})} />

        {filtradas.length === 0 ? (
          <EmptyState
            title="Sin publicaciones con esos filtros"
            message="Prueba con otro tipo de publicación o quita la palabra clave."
            action={
              <button
                type="button"
                onClick={() => {
                  setTipo("");
                  setParams({});
                }}
                className="btn-primary"
              >
                Ver todas
              </button>
            }
          />
        ) : (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
            {filtradas.map((n, i) => (
              <Reveal key={n.slug} delay={(i % 3) * 70}>
                <TarjetaNoticia noticia={n} />
              </Reveal>
            ))}
          </div>
        )}

        {noticias.hayMas && (
          <div className="mt-8 text-center">
            <button type="button" onClick={noticias.cargarMas} className="btn-ghost"
                    disabled={noticias.cargando}>
              {noticias.cargando ? "Cargando…" : `Ver más (${filtradas.length} de ${noticias.total})`}
            </button>
          </div>
        )}
      </div>
    </>
  );
}

/** Tarjeta del listado: portada arriba, como `CasoPreview` de la portada. */
export function TarjetaNoticia({ noticia: n }: { noticia: Noticia }) {
  return (
    <Link
      to={`/noticias/${n.slug}`}
      className="card block h-full overflow-hidden hover:shadow-md hover:-translate-y-0.5 transition duration-300 no-underline"
    >
      <img
        src={n.imagen_portada}
        alt={n.titulo}
        loading="lazy"
        decoding="async"
        width={600}
        height={400}
        className="w-full aspect-[3/2] object-cover"
      />
      <div className="p-5">
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <span className={`chip ${TIPO_ESTILO[n.tipo]}`}>{TIPOS_NOTICIA[n.tipo]}</span>
          <span className="inline-flex items-center gap-1 text-xs text-ink-600">
            <CalendarDays className="w-3 h-3" />
            {formatFecha(n.fecha)}
          </span>
        </div>
        <h3 className="font-display font-bold text-mountain-900 text-lg leading-tight">
          {n.titulo}
        </h3>
        <p className="mt-2 text-sm text-ink-600">{n.bajada}</p>
      </div>
    </Link>
  );
}

/** Variante compacta para el bloque de actualidad de la portada, donde la columna es estrecha. */
export function TarjetaNoticiaCompacta({ noticia: n }: { noticia: Noticia }) {
  return (
    <Link
      to={`/noticias/${n.slug}`}
      className="card flex gap-4 p-4 hover:shadow-md transition no-underline"
    >
      <img
        src={n.imagen_portada}
        alt={n.titulo}
        loading="lazy"
        decoding="async"
        width={96}
        height={96}
        className="w-24 h-24 shrink-0 object-cover rounded-lg"
      />
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <span className={`chip ${TIPO_ESTILO[n.tipo]}`}>{TIPOS_NOTICIA[n.tipo]}</span>
          <span className="text-xs text-ink-600">{formatFecha(n.fecha)}</span>
        </div>
        <h3 className="font-display font-bold text-mountain-900 leading-tight">{n.titulo}</h3>
        <p className="mt-1 text-sm text-ink-600 line-clamp-2">{n.bajada}</p>
      </div>
    </Link>
  );
}
