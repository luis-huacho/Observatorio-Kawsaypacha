import { useState } from "react";
import { Download, ExternalLink, FileText, Search } from "lucide-react";

import { useApi, useApiPaginado } from "@/lib/api";
import { registrarDescargaDocumento } from "@/lib/metricas";
import type { CategoriaDocumento, Documento } from "@/lib/types";
import EmptyState from "@/components/EmptyState";
import PageHeader from "@/components/PageHeader";

const RECURSOS = [
  {
    categoria: "Fuentes oficiales nacionales",
    items: [
      { nombre: "SIGRID — CENEPRED", desc: "Sistema de Información para la Gestión del Riesgo de Desastres.", url: "https://sigrid.cenepred.gob.pe/" },
      { nombre: "INEI", desc: "Censos de población y centros poblados.", url: "https://www.inei.gob.pe/" },
      { nombre: "MEF — Consulta Amigable", desc: "Seguimiento del PPR 0068 y otros programas presupuestales.", url: "https://apps5.mineco.gob.pe/transparencia/Navegador/default.aspx" },
      { nombre: "SENAMHI", desc: "Servicio Nacional de Meteorología e Hidrología — datos climáticos y pronósticos.", url: "https://www.senamhi.gob.pe/" },
      { nombre: "INGEMMET", desc: "Estudios de peligros geológicos y geodinámicos.", url: "https://www.gob.pe/ingemmet" },
      { nombre: "IGP", desc: "Instituto Geofísico del Perú — sismicidad y vulcanismo.", url: "https://www.gob.pe/igp" },
      { nombre: "ANA", desc: "Autoridad Nacional del Agua — recursos hídricos.", url: "https://www.gob.pe/ana" },
      { nombre: "INAIGEM", desc: "Glaciares, ecosistemas de montaña.", url: "https://www.gob.pe/inaigem" },
    ],
  },
  {
    categoria: "Marco normativo",
    items: [
      { nombre: "Ley 29664 — SINAGERD", desc: "Sistema Nacional de Gestión del Riesgo de Desastres.", url: "https://www.gob.pe/institucion/cenepred/normas-legales/103045-29664" },
      { nombre: "Marco Sendai 2015-2030", desc: "Marco internacional para la reducción del riesgo de desastres.", url: "https://www.undrr.org/implementing-sendai-framework/what-sendai-framework" },
    ],
  },
  {
    categoria: "PREDES",
    items: [
      { nombre: "Sitio institucional PREDES", desc: "Centro de Estudios y Prevención de Desastres.", url: "https://www.predes.org.pe/" },
    ],
  },
];

export default function Recursos() {
  const [categoria, setCategoria] = useState("");
  const [buscar, setBuscar] = useState("");
  const categorias = useApi<CategoriaDocumento[]>("/biblioteca/categorias/");
  const documentos = useApiPaginado<Documento>("/biblioteca/", { categoria, buscar });

  return (
    <>
      <PageHeader
        titulo="Recursos"
        descripcion="Biblioteca de documentos del observatorio y directorio de fuentes oficiales relacionadas con la GRD y la ACC."
      />
      <div className="container-page py-8">

      {/* --- Biblioteca: lo que sube PREDES desde el admin --- */}
      <section className="mb-12">
        <h2 className="font-display text-xl font-bold text-mountain-900 mb-3">
          Biblioteca del observatorio
        </h2>

        <div className="grid sm:grid-cols-[1fr_240px] gap-3 mb-5 max-w-2xl">
          <div className="flex items-center gap-2 control">
            <Search className="w-4 h-4 text-ink-600 shrink-0" />
            <input
              value={buscar}
              onChange={(e) => setBuscar(e.target.value)}
              placeholder="Buscar por título, resumen o institución…"
              className="flex-1 bg-transparent border-0 outline-none text-sm"
              aria-label="Buscar documentos"
            />
          </div>
          <select
            value={categoria}
            onChange={(e) => setCategoria(e.target.value)}
            className="control"
            aria-label="Categoría"
          >
            <option value="">Todas las categorías</option>
            {categorias.status === "ok" &&
              categorias.data.map((c) => (
                <option key={c.slug} value={c.slug}>
                  {c.nombre}
                </option>
              ))}
          </select>
        </div>

        {documentos.cargando && !documentos.resultados.length ? (
          <p className="text-sm text-ink-600">Cargando documentos…</p>
        ) : documentos.resultados.length === 0 ? (
          <EmptyState
            title="Sin documentos publicados"
            message={
              buscar || categoria
                ? "No hay documentos que coincidan con la búsqueda."
                : "PREDES aún no ha publicado documentos en la biblioteca."
            }
          />
        ) : (
          <>
            <div className="grid md:grid-cols-2 gap-3">
              {documentos.resultados.map((d) => (
                <TarjetaDocumento key={d.id} documento={d} />
              ))}
            </div>
            {documentos.hayMas && (
              <div className="mt-5 text-center">
                <button type="button" onClick={documentos.cargarMas} className="btn-ghost">
                  Ver más ({documentos.resultados.length} de {documentos.total})
                </button>
              </div>
            )}
          </>
        )}
      </section>

      {/* --- Directorio externo ---
          Sigue siendo estático a propósito: es una lista curada de sitios de terceros, no
          contenido del observatorio. Meterla en la base obligaría a PREDES a mantener fichas de
          organismos que no cambian, y a nosotros a un modelo más para nada. */}
      <div className="space-y-8">
        {RECURSOS.map((cat) => (
          <section key={cat.categoria}>
            <h2 className="font-display text-xl font-bold text-mountain-900 mb-3">{cat.categoria}</h2>
            <div className="grid md:grid-cols-2 gap-3">
              {cat.items.map((r) => (
                <a
                  key={r.nombre}
                  href={r.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="card p-4 hover:shadow-md transition no-underline"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="font-semibold text-mountain-900">{r.nombre}</div>
                      <p className="text-sm text-ink-600 mt-1">{r.desc}</p>
                    </div>
                    <ExternalLink className="w-4 h-4 text-mountain-700 mt-1 shrink-0" />
                  </div>
                </a>
              ))}
            </div>
          </section>
        ))}
      </div>
      </div>
    </>
  );
}

/** Tarjeta de un documento de la biblioteca: PDF alojado o enlace externo. */
function TarjetaDocumento({ documento: d }: { documento: Documento }) {
  const destino = d.archivo ?? d.url_externa ?? "";
  const esLocal = Boolean(d.archivo);
  return (
    <a
      href={destino}
      target="_blank"
      rel="noopener noreferrer"
      onClick={() => registrarDescargaDocumento(d.titulo)}
      className="card p-4 hover:shadow-md transition no-underline flex items-start gap-3"
    >
      <FileText className="w-5 h-5 text-mountain-700 mt-0.5 shrink-0" />
      <div className="min-w-0 flex-1">
        <div className="font-semibold text-mountain-900">{d.titulo}</div>
        <div className="flex flex-wrap items-center gap-2 mt-1 text-xs text-ink-600">
          <span className="chip bg-mountain-100 text-mountain-900 border border-mountain-500/20">
            {d.categoria}
          </span>
          {d.autor_institucion && <span>{d.autor_institucion}</span>}
          {d.fecha_publicacion && <span>{d.fecha_publicacion.slice(0, 4)}</span>}
        </div>
        {d.resumen && <p className="text-sm text-ink-600 mt-2 line-clamp-3">{d.resumen}</p>}
        {/* Se declara cuando el resumen lo redactó la IA: el lector tiene derecho a saber que
            no lo escribió una persona, aunque un editor lo haya revisado. */}
        {d.resumen_generado_por_ia && (
          <p className="mt-1 text-xs text-ink-600 italic">Resumen generado con asistencia de IA.</p>
        )}
      </div>
      {esLocal ? (
        <Download className="w-4 h-4 text-mountain-700 mt-1 shrink-0" />
      ) : (
        <ExternalLink className="w-4 h-4 text-mountain-700 mt-1 shrink-0" />
      )}
    </a>
  );
}
