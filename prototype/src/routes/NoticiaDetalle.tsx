import { Link, useParams } from "react-router-dom";
import { CalendarDays, UserRound } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import { useJsonData } from "@/lib/useJsonData";
import type { Noticia } from "@/lib/types";
import { TIPOS_NOTICIA } from "@/lib/types";
import { formatFecha } from "@/lib/semaforo";
import EmptyState from "@/components/EmptyState";
import Portada from "@/components/Portada";
import PalabrasClave from "@/components/PalabrasClave";

export default function NoticiaDetalle() {
  const { slug } = useParams();
  const noticias = useJsonData<Noticia[]>("/data/noticias.mock.json");

  if (noticias.status === "loading") return <div className="container-page py-12">Cargando…</div>;
  if (noticias.status !== "ok")
    return (
      <div className="container-page py-12">
        <EmptyState title="Error al cargar las noticias" />
      </div>
    );

  const n = noticias.data.find((x) => x.slug === slug);
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

        <Portada tipo={n.tipo} imagen={n.imagen_portada} pie={n.imagen_titulo} alt={n.titulo} />

        <p className="mt-6 text-lg text-ink-900 leading-relaxed">{n.bajada}</p>
        {/* whitespace-pre-line respeta los saltos de párrafo del JSON sin necesidad de rich text. */}
        <div className="mt-4 text-ink-600 leading-relaxed whitespace-pre-line">{n.cuerpo}</div>

        <PalabrasClave palabras={n.palabras_clave} base="/noticias" />
      </article>
    </>
  );
}
