import { useMemo, useState, Suspense, lazy } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Filter } from "lucide-react";
import { useJsonData } from "@/lib/useJsonData";
import type { CentroPoblado, ClasificacionPeligro, FrecuenciaDistrito, Nivel } from "@/lib/types";
import { TIPOS_PELIGRO } from "@/lib/types";
import { NIVEL_BG, NIVEL_LABEL, formatNumber } from "@/lib/semaforo";
import GeoSelector from "@/components/GeoSelector";
import SemaforoChip from "@/components/SemaforoChip";
import EmptyState from "@/components/EmptyState";
import PageHeader from "@/components/PageHeader";
import FrecuenciaEmergencias from "@/components/FrecuenciaEmergencias";

const MapaPeligros = lazy(() => import("@/components/MapaPeligros"));

export default function Peligros() {
  const ccpp = useJsonData<CentroPoblado[]>("/data/ccpp.json");
  const peligros = useJsonData<ClasificacionPeligro[]>("/data/peligros.json");
  const frecuencia = useJsonData<FrecuenciaDistrito[]>("/data/frecuencia.json");

  const [provincia, setProvincia] = useState("");
  const [distrito, setDistrito] = useState("");
  const [tipo, setTipo] = useState<string>("");
  const [nivelMin, setNivelMin] = useState(0);

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
      if (tipo && p.peligro !== tipo) return false;
      if (nivelMin && p.nivel < nivelMin) return false;
      return true;
    });
  }, [peligros, ccppFiltrados, tipo, nivelMin]);

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

  const cargando = ccpp.status === "loading" || peligros.status === "loading";

  return (
    <>
      <PageHeader
        titulo="Exposición a peligros naturales"
        descripcion="Mapa de exposición a peligros climáticos y geodinámicos en los centros poblados de Cusco. Datos provenientes de SIGRID-CENEPRED. Activa o desactiva las capas geográficas (lagunas, ríos, nevados) desde el control superior derecho del mapa."
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
                value={tipo}
                onChange={(e) => setTipo(e.target.value)}
                className="control w-full"
              >
                <option value="">Todos los peligros</option>
                {TIPOS_PELIGRO.map((t) => (
                  <option key={t} value={t}>{t}</option>
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
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs text-ink-600">
              Capas geográficas activables: lagunas, ríos y nevados.
            </span>
            {/* La demo depende de tiles que no se versionan: solo existe en desarrollo. */}
            {import.meta.env.DEV && (
              <Link
                to="/peligros/mapa-nuevo"
                className="inline-flex items-center gap-1 text-xs text-sky-700 hover:text-mountain-700"
              >
                Ver visor MapLibre + PMTiles (evaluación técnica)
                <ArrowRight className="w-3 h-3" />
              </Link>
            )}
          </div>
          <div className="card p-1 h-[600px] overflow-hidden">
            {cargando ? (
              <div className="h-full grid place-items-center text-ink-600">Cargando mapa…</div>
            ) : ccpp.status === "ok" && peligros.status === "ok" ? (
              <Suspense fallback={<div className="h-full grid place-items-center text-ink-600">Cargando mapa…</div>}>
                <MapaPeligros
                  ccpp={ccppFiltrados}
                  peligros={peligrosFiltrados}
                  tipoPeligroFiltro={tipo || null}
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
                {formatNumber(ccppFiltrados.length)} CCPP
              </span>
            </div>
            <div className="max-h-[300px] overflow-y-auto -mx-2">
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
                  {ccppFiltrados.slice(0, 100).map((c) => {
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
              {ccppFiltrados.length > 100 && (
                <div className="text-xs text-ink-600 text-center py-3">
                  Mostrando primeros 100. Refina filtros para ver el resto.
                </div>
              )}
            </div>
          </div>
        </section>
      </div>
      </div>
    </>
  );
}
