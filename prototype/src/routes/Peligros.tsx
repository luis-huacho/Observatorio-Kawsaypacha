import { useMemo, useState, Suspense, lazy } from "react";
import { Link } from "react-router-dom";
import { Filter } from "lucide-react";
import { useJsonData } from "@/lib/useJsonData";
import type { CentroPoblado, ClasificacionPeligro, Nivel } from "@/lib/types";
import { TIPOS_PELIGRO } from "@/lib/types";
import { NIVEL_BG, NIVEL_LABEL, formatNumber } from "@/lib/semaforo";
import GeoSelector from "@/components/GeoSelector";
import SemaforoChip from "@/components/SemaforoChip";
import EmptyState from "@/components/EmptyState";

const MapaPeligros = lazy(() => import("@/components/MapaPeligros"));

export default function Peligros() {
  const ccpp = useJsonData<CentroPoblado[]>("/data/ccpp.json");
  const peligros = useJsonData<ClasificacionPeligro[]>("/data/peligros.json");

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

  const cargando = ccpp.status === "loading" || peligros.status === "loading";

  return (
    <div className="container-page py-8">
      <header className="mb-6">
        <h1 className="font-display text-3xl md:text-4xl font-bold text-mountain-900">
          Ventana 1 — Peligros
        </h1>
        <p className="text-ink-600 mt-2 max-w-3xl">
          Mapa de exposición a peligros climáticos y geodinámicos en los centros poblados de Cusco.
          Datos provenientes de SIGRID-CENEPRED.
        </p>
      </header>

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
                className="w-full rounded-md border border-ink-300/60 bg-white px-3 py-2 text-sm"
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
              <div className="flex gap-1">
                {[0, 1, 2, 3, 4].map((n) => (
                  <button
                    key={n}
                    onClick={() => setNivelMin(n)}
                    className={`flex-1 py-2 text-sm rounded-md border transition ${
                      nivelMin === n
                        ? "bg-mountain-700 text-white border-mountain-700"
                        : "bg-white text-ink-600 border-ink-300/60 hover:border-mountain-500"
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
                    const niveles = peligrosFiltrados
                      .filter((p) => p.codigo_ccpp === c.codigo)
                      .map((p) => p.nivel as Nivel);
                    const max = niveles.length ? (Math.max(...niveles) as Nivel) : null;
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
  );
}
