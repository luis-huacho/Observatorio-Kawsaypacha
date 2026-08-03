import { useState } from "react";

import { useApi, useApiPaginado } from "@/lib/api";
import { formatFecha } from "@/lib/semaforo";
import type { TipoPeligroApi, Video as TVideo } from "@/lib/types";
import EmptyState from "@/components/EmptyState";
import PageHeader from "@/components/PageHeader";
import Reveal from "@/components/Reveal";
import Video from "@/components/Video";

/**
 * Repositorio de videos (requisito 6 del TDR).
 *
 * Los embeds se montan directamente y no tras un clic: son pocos por página y el usuario viene a
 * ver, no a decidir. `Video` ya resuelve la URL de YouTube o Vimeo a su forma incrustable.
 */
export default function Videos() {
  const [tema, setTema] = useState("");
  const temas = useApi<TipoPeligroApi[]>("/peligros/tipos/");
  const videos = useApiPaginado<TVideo>("/videos/", { tema });

  return (
    <>
      <PageHeader
        titulo="Videos"
        descripcion="Registro audiovisual del observatorio: experiencias de campo, capacitaciones y material de difusión sobre gestión del riesgo y adaptación al cambio climático."
      />
      <div className="container-page py-8">
        <div className="mb-6 max-w-xs">
          <label className="block text-xs font-medium text-ink-600 mb-1">Tema</label>
          <select
            value={tema}
            onChange={(e) => setTema(e.target.value)}
            className="control w-full"
          >
            <option value="">Todos los temas</option>
            {temas.status === "ok" &&
              temas.data.map((t) => (
                <option key={t.slug} value={t.slug}>
                  {t.nombre}
                </option>
              ))}
          </select>
        </div>

        {videos.cargando && !videos.resultados.length ? (
          <p className="text-sm text-ink-600">Cargando videos…</p>
        ) : videos.resultados.length === 0 ? (
          <EmptyState
            title="Sin videos publicados"
            message={
              tema
                ? "No hay videos publicados para ese tema."
                : "PREDES aún no ha publicado videos en el observatorio."
            }
          />
        ) : (
          <>
            <div className="grid md:grid-cols-2 gap-6">
              {videos.resultados.map((v, i) => (
                <Reveal key={v.id} delay={(i % 2) * 70}>
                  <article className="card overflow-hidden h-full">
                    <Video url={v.url} titulo={v.titulo} />
                    <div className="p-5">
                      <div className="flex flex-wrap items-center gap-2 mb-2 text-xs text-ink-600">
                        {v.tema && (
                          <span className="chip bg-mountain-100 text-mountain-900 border border-mountain-500/20">
                            {v.tema}
                          </span>
                        )}
                        <span>{formatFecha(v.fecha)}</span>
                        {v.duracion && <span>{v.duracion}</span>}
                      </div>
                      <h2 className="font-display font-bold text-mountain-900 leading-tight">
                        {v.titulo}
                      </h2>
                      {v.descripcion && (
                        <p className="mt-2 text-sm text-ink-600">{v.descripcion}</p>
                      )}
                    </div>
                  </article>
                </Reveal>
              ))}
            </div>
            {videos.hayMas && (
              <div className="mt-8 text-center">
                <button type="button" onClick={videos.cargarMas} className="btn-ghost">
                  Ver más ({videos.resultados.length} de {videos.total})
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}
