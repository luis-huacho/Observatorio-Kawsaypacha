import { Link, useParams } from "react-router-dom";
import { CalendarDays, UserRound } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import { useApi } from "@/lib/api";
import type { NoticiaDetalle as TNoticia } from "@/lib/types";
import { TIPOS_NOTICIA } from "@/lib/types";
import { formatFecha } from "@/lib/semaforo";
import EmptyState from "@/components/EmptyState";
import Portada from "@/components/Portada";
import PalabrasClave from "@/components/PalabrasClave";

export default function NoticiaDetalle() {
  const { slug } = useParams();
  const noticia = useApi<TNoticia>(slug ? `/noticias/${slug}/` : null);

  if (noticia.status === "loading") return <div className="container-page py-12">Cargando…</div>;
  // Un 404 del API es "no existe o fue retirada", no un error del sitio: el flujo editorial
  // permite despublicar, y un enlace compartido antes seguirá circulando.
  const n = noticia.status === "ok" ? noticia.data : null;
  if (!n) {
    return (
      <div className="container-page py-12">
        <EmptyState
          title="Publicación no encontrada"
          message="La publicación que buscas no existe o fue retirada."
          action={
            <Link to="/noticias" className="btn-primary">
              Ver todas las publicaciones
            </Link>
          }
        />
      </div>
    );
  }

  return (
    <>
      <PageHeader
        eyebrow={TIPOS_NOTICIA[n.tipo]}
        titulo={n.titulo}
        backTo="/noticias"
        backLabel="Volver a noticias"
      />
      <article className="container-page py-8 max-w-3xl">
        <div className="flex flex-wrap items-center gap-4 text-sm text-ink-600">
          <span className="inline-flex items-center gap-1">
            <CalendarDays className="w-4 h-4" />
            {formatFecha(n.fecha)}
          </span>
          <span className="inline-flex items-center gap-1">
            <UserRound className="w-4 h-4" />
            {n.autor}
          </span>
        </div>

        <Portada imagen={n.imagen_portada} pie={n.imagen_titulo} alt={n.titulo} />

        <p className="mt-6 text-lg text-ink-900 leading-relaxed">{n.bajada}</p>
        {/* whitespace-pre-line respeta los saltos de párrafo del JSON sin necesidad de rich text. */}
        <div className="mt-4 text-ink-600 leading-relaxed whitespace-pre-line">{n.cuerpo}</div>

        <PalabrasClave palabras={n.palabras_clave} base="/noticias" />
      </article>
    </>
  );
}
