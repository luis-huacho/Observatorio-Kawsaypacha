import { Link, useParams } from "react-router-dom";
import { CalendarDays, Landmark } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import { useJsonData } from "@/lib/useJsonData";
import type { Norma } from "@/lib/types";
import { formatFecha } from "@/lib/semaforo";
import EmptyState from "@/components/EmptyState";
import Portada from "@/components/Portada";
import PalabrasClave from "@/components/PalabrasClave";
import EnlaceNorma, { PUBLICA } from "@/components/EnlaceNorma";

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
          <span className="inline-flex items-center gap-1">
            <Landmark className="w-4 h-4" />
            Publicada por el {PUBLICA[n.ambito]}
          </span>
        </div>

        <Portada tipo="norma" imagen={n.imagen_portada} pie={n.imagen_titulo} alt={n.titulo} />

        <p className="mt-6 text-lg text-ink-900 leading-relaxed">{n.resumen}</p>

        {/* Acción principal de la página: quien llega aquí suele venir a por el documento. */}
        <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-2">
          <EnlaceNorma url={n.url_oficial} />
          <span className="text-xs text-ink-600">
            Enlace de ejemplo en el prototipo; la plataforma apuntará a la publicación oficial.
          </span>
        </div>

        <div className="mt-6 text-ink-600 leading-relaxed whitespace-pre-line">{n.contenido}</div>

        {n.analisis_predes && (
          <div className="mt-6 callout p-4 text-sm">
            <span className="font-semibold text-mountain-900">Análisis PREDES: </span>
            {n.analisis_predes}
          </div>
        )}

        <PalabrasClave palabras={n.palabras_clave} base="/normativa" />
      </article>
    </>
  );
}
