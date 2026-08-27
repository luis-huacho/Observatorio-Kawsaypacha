import { Link, useParams } from "react-router-dom";
import { ExternalLink, Link2, MapPin, PlayCircle } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import { useApi } from "@/lib/api";
import type { MedidaDetalle as TMedida } from "@/lib/types";
import EmptyState from "@/components/EmptyState";
import Portada from "@/components/Portada";
import ContenidoRico from "@/components/ContenidoRico";
import GaleriaMedida from "@/components/GaleriaMedida";
import Video from "@/components/Video";
import PalabrasClave from "@/components/PalabrasClave";
import { RESULTADO_ESTILO } from "@/routes/Medidas";

export default function MedidaDetalle() {
  const { slug } = useParams();
  const medida = useApi<TMedida>(slug ? `/medidas/${slug}/` : null);

  if (medida.status === "loading") return <div className="container-page py-12">Cargando…</div>;

  // Un 404 es "no existe o fue retirada", no un error del sitio.
  const m = medida.status === "ok" ? medida.data : null;
  if (!m) {
    return (
      <div className="container-page py-12">
        <EmptyState
          title="Caso no encontrado"
          message="La experiencia que buscas no existe o fue retirada."
          action={<Link to="/medidas" className="btn-primary">Ver todas las buenas prácticas</Link>}
        />
      </div>
    );
  }

  const r = RESULTADO_ESTILO[m.resultado];

  return (
    <>
      <PageHeader
        eyebrow="Experiencia documentada"
        titulo={m.titulo}
        backTo="/medidas"
        backLabel="Volver a buenas prácticas"
      />
      <article className="container-page py-8 max-w-3xl">
        {/* El resultado es la clasificación que define la sección; hasta ahora la ficha no lo
            mostraba y solo se veía en el listado. */}
        <div className="flex flex-wrap items-center gap-3 text-sm text-ink-600">
          <span className={`chip border ${r.color}`}>
            <r.Icon className="w-3 h-3" />
            {r.label}
          </span>
          <span className="chip bg-mountain-100 text-mountain-900 border border-mountain-500/20">
            {m.peligro}
          </span>
          <span className="inline-flex items-center gap-1">
            <MapPin className="w-3.5 h-3.5" />
            {m.comunidad}
          </span>
          <span className="">Alcance de la experiencia {m.ambito}</span>
        </div>

        <Portada
          imagen={m.imagen_portada}
          pie={m.imagen_titulo}
          alt={m.titulo}
        />

        <p className="mt-6 text-lg text-ink-900 leading-relaxed">{m.resumen_corto}</p>

        <ContenidoRico html={m.contenido} className="mt-6" />

        <GaleriaMedida imagenes={m.galeria} />

        {m.video_url && (
          <section className="mt-8">
            <h2 className="flex items-center gap-2 font-display font-semibold text-mountain-900 mb-3">
              <PlayCircle className="w-4 h-4 text-mountain-700" />
              Video
            </h2>
            <Video url={m.video_url} titulo={m.titulo} />
          </section>
        )}

        {m.enlaces.length > 0 && (
          <section className="mt-8">
            <h2 className="flex items-center gap-2 font-display font-semibold text-mountain-900 mb-3">
              <Link2 className="w-4 h-4 text-mountain-700" />
              Enlaces relacionados
            </h2>
            <ul className="space-y-2">
              {m.enlaces.map((e) => (
                <li key={e.url}>
                  <a
                    href={e.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-sm"
                  >
                    {e.titulo}
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </li>
              ))}
            </ul>
          </section>
        )}

        <PalabrasClave palabras={m.palabras_clave} base="/medidas" />
      </article>
    </>
  );
}
