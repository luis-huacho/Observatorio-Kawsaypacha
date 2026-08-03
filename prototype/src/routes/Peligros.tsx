import { useEffect, useMemo, useState, Suspense, lazy } from "react";
import { Link } from "react-router-dom";
import { ChevronLeft, ChevronRight, Filter } from "lucide-react";
import { useJsonData } from "@/lib/useJsonData";
import type {
  CentroPoblado,
  ClasificacionPeligro,
  FrecuenciaDistrito,
  Nivel,
} from "@/lib/types";
import { PELIGROS } from "@/lib/types";
import { NIVEL_BG, NIVEL_LABEL, formatNumber } from "@/lib/semaforo";
import GeoSelector from "@/components/GeoSelector";
import SemaforoChip from "@/components/SemaforoChip";
import EmptyState from "@/components/EmptyState";
import PageHeader from "@/components/PageHeader";
import FrecuenciaEmergencias from "@/components/FrecuenciaEmergencias";

const MapaPeligros = lazy(() => import("@/components/MapaPeligros"));

const POR_PAGINA = 50;

export default function Peligros() {
  const ccpp = useJsonData<CentroPoblado[]>("/data/ccpp.json");
  const peligros = useJsonData<ClasificacionPeligro[]>("/data/peligros.json");
  const frecuencia = useJsonData<FrecuenciaDistrito[]>("/data/frecuencia.json");

  const [provincia, setProvincia] = useState("");
  const [distrito, setDistrito] = useState("");
  // Un único identificador de peligro: el mapa filtra el tile por `nivel_<slug>` y la tabla
  // filtra el JSON por nombre. Ambos salen del catálogo PELIGROS.
  const [slug, setSlug] = useState("");
  const [nivelMin, setNivelMin] = useState(0);
  const [pagina, setPagina] = useState(1);

  const nombrePeligro = useMemo(
    () => PELIGROS.find((p) => p.slug === slug)?.nombre ?? "",
    [slug]
  );

  // El tile filtra por ubigeo; el GeoSelector trabaja con nombres.
  const ubigeoDistrito = useMemo(() => {
    if (ccpp.status !== "ok" || !distrito) return "";
    return ccpp.data.find((c) => c.distrito === distrito)?.ubigeo_distrito ?? "";
  }, [ccpp, distrito]);

  const ccppFiltrados = useMemo(() => {
    if (ccpp.status !== "ok") return [];
    return ccpp.data.filter((c) => {
      if (provincia && c.provincia !== provincia) return false;
      if (distrito && c.distrito !== distrito) return false;
      return true;
    });
  }, [ccpp, provincia, distrito]);

  const peligrosFiltrados = useMemo(() => {
    if (peligros.status !== "ok") return [];
    const codigos = new Set(ccppFiltrados.map((c) => c.codigo));
    return peligros.data.filter((p) => {
      if (!codigos.has(p.codigo_ccpp)) return false;
      if (nombrePeligro && p.peligro !== nombrePeligro) return false;
      if (nivelMin && p.nivel < nivelMin) return false;
      return true;
    });
  }, [peligros, ccppFiltrados, nombrePeligro, nivelMin]);

  const stats = useMemo(() => {
    const counts: Record<Nivel, number> = { 1: 0, 2: 0, 3: 0, 4: 0 };
    for (const p of peligrosFiltrados) counts[p.nivel as Nivel]++;
    return counts;
  }, [peligrosFiltrados]);

  // Nivel máximo por centro poblado, precalculado una vez: la tabla lo leía con un filter()
  // por fila, lo que con 10,978 clasificaciones se notaba al teclear en los filtros.
  const nivelMaxPorCcpp = useMemo(() => {
    const max = new Map<string, Nivel>();
    for (const p of peligrosFiltrados) {
      const actual = max.get(p.codigo_ccpp);
      if (actual === undefined || p.nivel > actual) max.set(p.codigo_ccpp, p.nivel as Nivel);
    }
    return max;
  }, [peligrosFiltrados]);

  // Los peor clasificados primero; los 5,730 CCPP sin dato al final, que encabezar la tabla
  // con ellos no dice nada.
  const ccppOrdenados = useMemo(() => {
    return [...ccppFiltrados].sort((a, b) => {
      const na = nivelMaxPorCcpp.get(a.codigo) ?? 0;
      const nb = nivelMaxPorCcpp.get(b.codigo) ?? 0;
      return nb - na || a.nombre.localeCompare(b.nombre, "es");
    });
  }, [ccppFiltrados, nivelMaxPorCcpp]);

  const totalPaginas = Math.max(1, Math.ceil(ccppOrdenados.length / POR_PAGINA));
  const desde = (pagina - 1) * POR_PAGINA;
  const visibles = ccppOrdenados.slice(desde, desde + POR_PAGINA);

  // Cualquier cambio de filtro deja la paginación sin sentido.
  useEffect(() => {
    setPagina(1);
  }, [provincia, distrito, slug, nivelMin]);

  const cargando = ccpp.status === "loading" || peligros.status === "loading";

  return (
    <>
      <PageHeader
        titulo="Exposición a peligros naturales"
        descripcion="Mapa de exposición a peligros climáticos y geodinámicos en los centros poblados de Cusco. Datos provenientes de SIGRID-CENEPRED. Activa o desactiva las capas geográficas (lagunas, ríos, glaciares) desde el control superior derecho del mapa."
      />
      <div className="container-page py-8">
      <div className="grid lg:grid-cols-[280px_1fr] gap-6">
        {/* Filtros */}
        <aside className="card p-5 h-fit lg:sticky lg:top-20">
          <div className="flex items-center gap-2 mb-4">
            <Filter className="w-4 h-4 text-mountain-700" />
            <span className="font-display font-semibold text-mountain-900">Filtros</span>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-ink-600 mb-1">Ubicación</label>
              <GeoSelector
                ccpp={ccpp.status === "ok" ? ccpp.data : []}
                provincia={provincia}
                distrito={distrito}
                onChange={(p, d) => {
                  setProvincia(p);
                  setDistrito(d);
                }}
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-ink-600 mb-1">Tipo de peligro</label>
              <select
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                className="control w-full"
              >
                <option value="">Todos (nivel máximo)</option>
                {PELIGROS.map((p) => (
                  <option key={p.slug} value={p.slug}>{p.nombre}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-ink-600 mb-1">
                Nivel mínimo
              </label>
              <div className="flex gap-1 bg-mountain-100/60 rounded-full p-1">
                {[0, 1, 2, 3, 4].map((n) => (
                  <button
                    key={n}
                    onClick={() => setNivelMin(n)}
                    className={`flex-1 py-1.5 text-sm rounded-full transition ${
                      nivelMin === n
                        ? "bg-mountain-700 text-white shadow-sm"
                        : "text-ink-600 hover:bg-white"
                    }`}
                  >
                    {n === 0 ? "Todos" : n}
                  </button>
                ))}
              </div>
            </div>

            <div className="pt-3 border-t border-ink-300/30">
              <div className="text-xs text-ink-600 mb-2">Distribución</div>
              <div className="space-y-1">
                {([4, 3, 2, 1] as Nivel[]).map((n) => (
                  <div key={n} className="flex items-center justify-between text-xs">
                    <SemaforoChip nivel={n} />
                    <span className="font-mono font-semibold">{formatNumber(stats[n])}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </aside>

        {/* Mapa */}
        <section>
          <div className="mb-2">
            <span className="text-xs text-ink-600">
              Capas geográficas activables: lagunas, ríos y glaciares.
            </span>
          </div>
          <div className="card p-1 h-[600px] overflow-hidden">
            {cargando ? (
              <div className="h-full grid place-items-center text-ink-600">Cargando mapa…</div>
            ) : ccpp.status === "ok" && peligros.status === "ok" ? (
              <Suspense fallback={<div className="h-full grid place-items-center text-ink-600">Cargando mapa…</div>}>
                <MapaPeligros
                  ccpp={ccpp.data}
                  peligroSlug={slug || null}
                  nivelMin={nivelMin}
                  ubigeoDistrito={ubigeoDistrito}
                />
              </Suspense>
            ) : (
              <EmptyState title="Error al cargar datos" message="No pudimos leer los datasets de centros poblados." />
            )}
          </div>

          {/* Frecuencia histórica de emergencias del distrito seleccionado */}
          <FrecuenciaEmergencias
            frecuencia={frecuencia.status === "ok" ? frecuencia.data : []}
            distrito={distrito}
          />

          {/* Lista compacta */}
          <div className="card mt-4 p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-display font-semibold text-mountain-900">
                Centros poblados en el filtro actual
              </h2>
              <span className="text-sm text-ink-600">
                {formatNumber(ccppOrdenados.length)} CCPP
              </span>
            </div>
            {ccppOrdenados.length === 0 ? (
              <EmptyState
                title="Sin centros poblados"
                message="Ningún centro poblado coincide con los filtros actuales."
              />
            ) : (
              <>
                <div className="-mx-2 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="text-xs text-ink-600 uppercase tracking-wide">
                      <tr>
                        <th className="text-left px-2 py-2">Centro poblado</th>
                        <th className="text-left px-2 py-2 hidden sm:table-cell">Distrito</th>
                        <th className="text-right px-2 py-2">Población</th>
                        <th className="text-center px-2 py-2">Nivel</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibles.map((c) => {
                        const max = nivelMaxPorCcpp.get(c.codigo) ?? null;
                        return (
                          <tr key={c.codigo} className="border-t border-ink-300/20 hover:bg-mountain-100/40">
                            <td className="px-2 py-2">
                              <Link className="text-mountain-900 hover:text-mountain-700 no-underline" to={`/peligros/${c.codigo}`}>
                                {c.nombre}
                              </Link>
                              <div className="text-xs text-ink-600">{c.categoria}</div>
                            </td>
                            <td className="px-2 py-2 hidden sm:table-cell text-ink-600">{c.distrito}</td>
                            <td className="px-2 py-2 text-right font-mono">
                              {c.poblacion != null ? formatNumber(c.poblacion) : "—"}
                            </td>
                            <td className="px-2 py-2 text-center">
                              {max ? (
                                <span className={`chip border ${NIVEL_BG[max]}`}>
                                  {NIVEL_LABEL[max]}
                                </span>
                              ) : (
                                <span className="text-xs text-ink-300">sin dato</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-3 mt-3 pt-3 border-t border-ink-300/30">
                  <span className="text-xs text-ink-600">
                    Mostrando {formatNumber(desde + 1)}–
                    {formatNumber(Math.min(desde + POR_PAGINA, ccppOrdenados.length))} de{" "}
                    {formatNumber(ccppOrdenados.length)} centros poblados
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setPagina((p) => Math.max(1, p - 1))}
                      disabled={pagina === 1}
                      className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded border border-ink-300/40 text-ink-600 hover:bg-mountain-100 disabled:opacity-40 disabled:hover:bg-transparent"
                    >
                      <ChevronLeft className="w-3.5 h-3.5" />
                      Anterior
                    </button>
                    <span className="text-xs text-ink-600 font-mono">
                      {pagina} / {formatNumber(totalPaginas)}
                    </span>
                    <button
                      onClick={() => setPagina((p) => Math.min(totalPaginas, p + 1))}
                      disabled={pagina >= totalPaginas}
                      className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded border border-ink-300/40 text-ink-600 hover:bg-mountain-100 disabled:opacity-40 disabled:hover:bg-transparent"
                    >
                      Siguiente
                      <ChevronRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </section>
      </div>
      </div>
    </>
  );
}
