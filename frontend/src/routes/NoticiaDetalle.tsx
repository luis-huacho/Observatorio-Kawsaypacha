import { Link, useParams } from "react-router-dom";
import { CalendarDays, UserRound } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import { useApi } from "@/lib/api";
import type { NoticiaDetalle as TNoticia } from "@/lib/types";
import { TIPOS_NOTICIA } from "@/lib/types";
import { formatFecha } from "@/lib/semaforo";
import EmptyState from "@/components/EmptyState";
import Portada from "@/components/Portada";
import ContenidoRico from "@/components/ContenidoRico";
import PalabrasClave from "@/components/PalabrasClave";
import Compartir from "@/components/Compartir";
import ListaEnlaces from "@/components/ListaEnlaces";
import ListaArchivos from "@/components/ListaArchivos";
import { useMetaPagina } from "@/lib/meta";

export default function NoticiaDetalle() {
  const { slug } = useParams();
  const noticia = useApi<TNoticia>(slug ? `/noticias/${slug}/` : null);

  // El hook va **antes de cualquier `return`**: los de abajo son condicionales, y llamarlo
  // después haría que React viera un número distinto de hooks entre el render de carga y
  // el de datos. Con la ficha aún sin llegar recibe `undefined` y no hace nada.
  const n = noticia.status === "ok" ? noticia.data : null;
  useMetaPagina(n?.titulo, n?.bajada);

  if (noticia.status === "loading") return <div className="container-page py-12">Cargando…</div>;
  // Un 404 del API es "no existe o fue retirada", no un error del sitio: el flujo editorial
  // permite despublicar, y un enlace compartido antes seguirá circulando.
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
        {/* `cuerpo` es el HTML de CKEditor, ya saneado en el servidor (ADR-D2). Va por
            ContenidoRico como en las fichas de norma y de medida: además de pintarlo, devuelve
            tamaño a los encabezados y viñetas a las listas —que el Preflight de Tailwind
            resetea— y convierte el `<oembed>` del editor en un iframe. */}
        <ContenidoRico html={n.cuerpo} className="mt-4" />

        {/* Los anexos van después del cuerpo y antes de las palabras clave, que es donde la
            ficha de medida coloca los suyos. Cada bloque se pinta solo si tiene contenido. */}
        <ListaEnlaces enlaces={n.enlaces} />
        <ListaArchivos archivos={n.archivos} />

        <PalabrasClave palabras={n.palabras_clave} base="/noticias" />
        <Compartir titulo={n.titulo} />
      </article>
    </>
  );
}
