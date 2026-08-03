import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { CalendarDays } from "lucide-react";
import { useJsonData } from "@/lib/useJsonData";
import type { Noticia } from "@/lib/types";
import { TIPOS_NOTICIA } from "@/lib/types";
import { formatFecha } from "@/lib/semaforo";
import PageHeader from "@/components/PageHeader";
import EmptyState from "@/components/EmptyState";
import Reveal from "@/components/Reveal";

/** Un color por tipo, para distinguir de un vistazo lo informativo de lo editorializado. */
export const TIPO_ESTILO: Record<Noticia["tipo"], string> = {
  noticia: "bg-mountain-100 text-mountain-900 border border-mountain-500/20",
  articulo: "bg-sky-200/40 text-sky-700 border border-sky-500/20",
  opinion: "bg-earth-200/50 text-earth-700 border border-earth-500/25",
};

export default function Noticias() {
  const data = useJsonData<Noticia[]>("/data/noticias.mock.json");
  const [tipo, setTipo] = useState("");

  const filtradas = useMemo(() => {
    if (data.status !== "ok") return [];
    return data.data
      .filter((n) => (tipo ? n.tipo === tipo : true))
      .sort((a, b) => b.fecha.localeCompare(a.fecha));
  }, [data, tipo]);

  if (data.status === "loading") return <div className="container-page py-12">Cargando…</div>;
  if (data.status !== "ok")
    return (
      <div className="container-page py-12">
        <EmptyState title="Error al cargar las noticias" />
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

        {filtradas.length === 0 ? (
          <EmptyState
            title="Sin publicaciones de ese tipo"
            message="Prueba con otro tipo de publicación o consulta todas."
            action={
              <button type="button" onClick={() => setTipo("")} className="btn-primary">
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
      </div>
    </>
  );
}

/** Se usa también en el teaser de la portada. */
export function TarjetaNoticia({ noticia: n }: { noticia: Noticia }) {
  return (
    <Link
      to={`/noticias/${n.slug}`}
      className="card block h-full p-5 hover:shadow-md hover:-translate-y-0.5 transition duration-300 no-underline"
    >
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
    </Link>
  );
}
