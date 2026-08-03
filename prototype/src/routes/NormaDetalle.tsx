import { Link, useParams } from "react-router-dom";
import { CalendarDays, ExternalLink, Globe2 } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import { useJsonData } from "@/lib/useJsonData";
import type { Norma } from "@/lib/types";
import { formatFecha } from "@/lib/semaforo";
import EmptyState from "@/components/EmptyState";
import Portada from "@/components/Portada";
import PalabrasClave from "@/components/PalabrasClave";

export default function NormaDetalle() {
  const { slug } = useParams();
  const normas = useJsonData<Norma[]>("/data/normativa.mock.json");

  if (normas.status === "loading") return <div className="container-page py-12">Cargando…</div>;
  if (normas.status !== "ok")
    return (
      <div className="container-page py-12">
        <EmptyState title="Error al cargar la normativa" />
      </div>
    );

  const n = normas.data.find((x) => x.slug === slug);
  if (!n) {
    return (
      <div className="container-page py-12">
        <EmptyState
          title="Norma no encontrada"
          message="La norma que buscas no existe o fue retirada del repositorio."
          action={
            <Link to="/normativa" className="btn-primary">
              Ver toda la normativa
            </Link>
          }
        />
      </div>
    );
  }

  return (
    <>
      <PageHeader
        eyebrow={n.tipo}
        titulo={n.titulo}
        backTo="/normativa"
        backLabel="Volver a normativa"
      />
      <article className="container-page py-8 max-w-3xl">
        <div className="flex flex-wrap items-center gap-4 text-sm text-ink-600">
          <span className="inline-flex items-center gap-1">
            <CalendarDays className="w-4 h-4" />
            {formatFecha(n.fecha)}
          </span>
          <span className="inline-flex items-center gap-1 capitalize">
            <Globe2 className="w-4 h-4" />
            Ámbito {n.ambito}
          </span>
        </div>

        <Portada tipo="norma" imagen={n.imagen_portada} pie={n.imagen_titulo} alt={n.titulo} />

        <p className="mt-6 text-lg text-ink-900 leading-relaxed">{n.resumen}</p>
        <div className="mt-4 text-ink-600 leading-relaxed whitespace-pre-line">{n.contenido}</div>

        {n.analisis_predes && (
          <div className="mt-6 callout p-4 text-sm">
            <span className="font-semibold text-mountain-900">Análisis PREDES: </span>
            {n.analisis_predes}
          </div>
        )}

        {/* El enlace a la norma oficial vive aquí y ya no en el listado: allí la tarjeta entera
            es un enlace y anidar anclas es HTML inválido. */}
        {n.url_oficial && (
          <a
            href={n.url_oficial}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-6 inline-flex items-center gap-1 text-sm"
          >
            Ver norma oficial <ExternalLink className="w-3 h-3" />
          </a>
        )}

        <PalabrasClave palabras={n.palabras_clave} base="/normativa" />
      </article>
    </>
  );
}
