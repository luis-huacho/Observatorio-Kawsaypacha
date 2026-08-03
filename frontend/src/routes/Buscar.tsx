import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AlertTriangle, ArrowRight, Search } from "lucide-react";

import { formatNumber } from "@/lib/semaforo";
import { buscarGlobal, type RespuestaBusqueda } from "@/lib/search";
import EmptyState from "@/components/EmptyState";
import PageHeader from "@/components/PageHeader";

/**
 * Búsqueda global, agrupada por tipo de contenido.
 *
 * Va directa a Meilisearch con la llave search-only y cae a `/api/buscar/` si el servicio no
 * responde (spec 04). En el prototipo esta página solo buscaba centros poblados filtrando el
 * padrón en memoria; ahora cubre medidas, normativa, noticias, documentos, videos y eventos.
 */
export default function Buscar() {
  const [sp, setSp] = useSearchParams();
  const q = (sp.get("q") ?? "").trim();
  const [texto, setTexto] = useState(q);
  const [respuesta, setRespuesta] = useState<RespuestaBusqueda | null>(null);
  const [buscando, setBuscando] = useState(false);

  useEffect(() => {
    setTexto(q);
    if (!q) {
      setRespuesta(null);
      return;
    }
    let vigente = true;
    setBuscando(true);
    void buscarGlobal(q)
      .then((r) => vigente && setRespuesta(r))
      .finally(() => vigente && setBuscando(false));
    return () => {
      vigente = false;
    };
  }, [q]);

  function enviar(e: React.FormEvent) {
    e.preventDefault();
    const termino = texto.trim();
    // La consulta vive en la URL: así el resultado se puede compartir y el botón «atrás»
    // devuelve a la búsqueda anterior en vez de a una página en blanco.
    setSp(termino ? { q: termino } : {});
  }

  const grupos = respuesta?.grupos ?? [];
  const total = respuesta?.total ?? 0;

  return (
    <>
      <PageHeader
        eyebrow="Búsqueda"
        titulo={q ? `Resultados para «${q}»` : "Buscar en el observatorio"}
        descripcion={
          buscando
            ? "Buscando…"
            : q
              ? `${formatNumber(total)} resultado(s) en medidas, normativa, noticias, documentos, videos y eventos.`
              : "Busca por medida, norma, noticia, documento o centro poblado."
        }
      />

      <div className="container-page py-8">
        <form onSubmit={enviar} className="max-w-xl flex gap-2 mb-8">
          <div className="flex-1 flex items-center gap-2 control">
            <Search className="w-4 h-4 text-ink-600 shrink-0" />
            <input
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              placeholder="Qochas, heladas, SINAGERD, Ollantaytambo…"
              className="flex-1 bg-transparent border-0 outline-none text-sm"
              aria-label="Términos de búsqueda"
            />
          </div>
          <button type="submit" className="btn-primary">
            Buscar
          </button>
        </form>

        {/* Modo degradado: sin facetas ni tolerancia a errores de tecleo. Se avisa porque una
            búsqueda que devuelve menos de lo esperado sin explicación se lee como un fallo. */}
        {respuesta?.motor === "drf" && (
          <div className="mb-6 flex items-start gap-2 rounded-lg border border-earth-500/30 bg-earth-200/40 px-4 py-3 text-sm text-earth-700">
            <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>
              El buscador está en modo básico: no tolera errores de tecleo ni acentos omitidos.
              Prueba con la palabra exacta.
            </span>
          </div>
        )}

        {q && !buscando && grupos.length === 0 && (
          <EmptyState
            title="Sin coincidencias"
            message="Prueba con otra palabra, o con el nombre de un distrito o centro poblado."
            action={
              <Link to="/peligros" className="btn-primary">
                Ir al visor
              </Link>
            }
          />
        )}

        <div className="space-y-8">
          {grupos.map((grupo) => (
            <section key={grupo.indice}>
              <div className="flex items-baseline gap-3 mb-3">
                <h2 className="font-display text-xl font-bold text-mountain-900">
                  {grupo.etiqueta}
                </h2>
                <span className="text-sm text-ink-600">
                  {formatNumber(grupo.total)}
                  {grupo.total > grupo.resultados.length &&
                    ` · mostrando ${grupo.resultados.length}`}
                </span>
              </div>
              <ul className="grid gap-2 md:grid-cols-2">
                {grupo.resultados.map((r) => (
                  <li key={`${grupo.indice}-${r.url}-${r.titulo}`}>
                    <Link
                      to={r.url}
                      className="card p-4 flex items-start justify-between gap-3 h-full hover:shadow-md transition no-underline"
                    >
                      <div className="min-w-0">
                        <div className="font-semibold text-mountain-900">{r.titulo}</div>
                        {r.detalle && (
                          <p className="text-sm text-ink-600 mt-1 line-clamp-2">{r.detalle}</p>
                        )}
                        {r.extra && (
                          <span className="inline-block mt-2 text-xs text-ink-600">{r.extra}</span>
                        )}
                      </div>
                      <ArrowRight className="w-4 h-4 text-mountain-700 mt-1 shrink-0" />
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </div>
    </>
  );
}
