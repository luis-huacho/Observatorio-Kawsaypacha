import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { MapPin } from "lucide-react";
import { useApi } from "@/lib/api";
import type { InversionDetalleResponse } from "@/lib/types";
import { formatPct, formatSoles } from "@/lib/semaforo";
import EmptyState from "@/components/EmptyState";
import KPI from "@/components/KPI";
import PageHeader from "@/components/PageHeader";

/**
 * Ficha de una municipalidad (`/inversion/:codigo`).
 *
 * La llave es el **código MEF de la entidad ejecutora**, no el ubigeo: la unidad de esta
 * ventana es la municipalidad, y las mancomunidades y el gobierno regional no tienen distrito.
 *
 * Es donde vive la comparación entre años a nivel de una sola entidad: la serie completa de
 * ejercicios publicados, con su corte y su fuente. La vista «Comparar ejercicios» del listado
 * responde la otra mitad de la pregunta —quién subió y quién bajó en toda la región—.
 */
export default function InversionDetalle() {
  const { codigo } = useParams();
  const [params] = useSearchParams();
  const anio = params.get("anio") || "";
  // «Volver» devuelve al listado tal como estaba —ejercicio, provincia, orden, comparación—,
  // no a su estado por defecto. Los filtros llegan aquí en la propia URL.
  const volverA = `/inversion${params.toString() ? `?${params}` : ""}`;
  const detalle = useApi<InversionDetalleResponse>(
    codigo ? `/inversion/entidades/${codigo}/` : null,
    { anio: anio || undefined }
  );

  if (detalle.status === "loading") return <div className="container-page py-12">Cargando…</div>;

  // Un 404 se trata como «no existe», no como error del sitio: los enlaces compartidos
  // circulan y una entidad puede desaparecer de una carga a otra.
  const d = detalle.status === "ok" && detalle.data.disponible ? detalle.data : null;
  if (!d) {
    const enPreparacion =
      detalle.status === "ok" && !detalle.data.disponible ? detalle.data.motivo : "";
    return (
      <div className="container-page py-12">
        <EmptyState
          title={enPreparacion ? "Información en preparación" : "Municipalidad no encontrada"}
          message={
            enPreparacion ||
            "No hay ninguna entidad ejecutora con ese código en los datos publicados."
          }
          action={
            <Link className="btn-primary" to={volverA}>
              Ver todas las municipalidades
            </Link>
          }
        />
      </div>
    );
  }

  const e = d.entidad;
  const actual = d.serie.find((s) => s.anio === d.anio);
  const procesos = [
    ...d.procesos.filter((p) => p.pim > 0).map((p) => ({
      nombre: p.nombre, monto: p.pim, color: p.color || "#007480",
    })),
    ...(d.sin_clasificar.pim > 0
      ? [{ nombre: "Sin clasificar", monto: d.sin_clasificar.pim, color: "#9CA3AF" }]
      : []),
  ];

  return (
    <>
      <PageHeader
        titulo={e.nombre}
        eyebrow={e.ambito_nombre}
        descripcion={
          e.provincia
            ? `${e.distrito ? `${e.distrito}, ` : ""}provincia de ${e.provincia}. Presupuesto del Programa Presupuestal 0068.`
            : "Presupuesto del Programa Presupuestal 0068."
        }
        backTo={volverA}
        backLabel="Volver a Inversión"
        badge={
          e.ubigeo_distrito && (
            <Link
              to={`/peligros?distrito=${e.ubigeo_distrito}`}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/15 text-white text-sm font-medium border border-white/25 transition hover:bg-white/25 no-underline"
            >
              <MapPin className="w-4 h-4" />
              Ver la exposición de su distrito
            </Link>
          )
        }
      />

      <div className="container-page py-8">
        {e.sin_territorio && (
          <p className="mb-6 rounded-lg border border-level-2/40 bg-level-2/10 px-4 py-3 text-sm text-yellow-900">
            Esta municipalidad <strong>no casa con ningún distrito del padrón</strong>. Sus cifras
            cuentan en los totales, pero no se pueden cruzar con datos territoriales.
          </p>
        )}
        {d.es_parcial && (
          <p className="mb-6 rounded-lg border border-level-2/40 bg-level-2/10 px-4 py-3 text-sm text-yellow-900">
            <strong>Corte a {d.corte}.</strong> El devengado del ejercicio {d.anio} no cubre el
            año completo.
          </p>
        )}

        {actual && (
          <section className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <KPI label={`PIM del PP 0068 · ${d.anio}`} value={formatSoles(actual.pim)} />
            <KPI
              label="Devengado"
              value={formatSoles(actual.devengado)}
              sub={
                actual.pct_ejecucion === null
                  ? "sin PIM"
                  : `${formatPct(actual.pct_ejecucion)} de ejecución`
              }
            />
            <KPI label="Saldo por ejecutar" value={formatSoles(actual.saldo)} />
            <KPI
              label="Peso sobre su presupuesto"
              value={
                actual.pct_0068_institucional === null
                  ? "Sin dato"
                  : formatPct(actual.pct_0068_institucional)
              }
              sub={
                actual.pim_institucional === null
                  ? "sin total institucional en el archivo"
                  : `de ${formatSoles(actual.pim_institucional)} institucionales`
              }
            />
          </section>
        )}

        <section className="card p-5 mb-6 overflow-x-auto">
          <h2 className="font-display font-semibold text-mountain-900 mb-2">
            Historia presupuestal
          </h2>
          <p className="text-xs text-ink-600 mb-4">
            Un ejercicio por fila. Los años en los que esta municipalidad no tuvo presupuesto del
            0068 no aparecen: no participar del programa no es participar con cero soles.
          </p>
          <table className="w-full text-sm min-w-[40rem]">
            <thead className="text-xs uppercase text-ink-600">
              <tr>
                <th className="text-left py-2">Ejercicio</th>
                <th className="text-right py-2">PIA</th>
                <th className="text-right py-2">PIM</th>
                <th className="text-right py-2">Devengado</th>
                <th className="text-right py-2">% Ejec.</th>
                <th className="text-right py-2">Saldo</th>
                <th className="text-right py-2 hidden lg:table-cell">Variación PIA-PIM</th>
              </tr>
            </thead>
            <tbody>
              {d.serie.map((s) => (
                <tr
                  key={s.anio}
                  className={`border-t border-ink-300/20 ${s.anio === d.anio ? "bg-mountain-100/40" : ""}`}
                >
                  <td className="py-2">
                    {s.anio}
                    {s.es_parcial && (
                      <span className="text-xs text-yellow-800" title={`Corte a ${s.corte}`}>
                        {" "}*
                      </span>
                    )}
                  </td>
                  <td className="py-2 text-right font-mono">{formatSoles(s.pia)}</td>
                  <td className="py-2 text-right font-mono">{formatSoles(s.pim)}</td>
                  <td className="py-2 text-right font-mono">{formatSoles(s.devengado)}</td>
                  <td className="py-2 text-right font-mono">
                    {s.pct_ejecucion === null ? "—" : formatPct(s.pct_ejecucion)}
                  </td>
                  <td className="py-2 text-right font-mono">{formatSoles(s.saldo)}</td>
                  <td className="py-2 text-right font-mono hidden lg:table-cell">
                    {formatSoles(s.variacion_pia_pim)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {d.serie.some((s) => s.es_parcial) && (
            <p className="text-xs text-ink-600 mt-3">
              * Ejercicio con corte parcial: su % de ejecución no se compara con el de un año
              cerrado.
            </p>
          )}
        </section>

        {procesos.length > 0 && (
          <section className="card p-5 mb-6">
            <h2 className="font-display font-semibold text-mountain-900 mb-2">
              ¿En qué invierte? — procesos de la GRD, {d.anio}
            </h2>
            <div className="h-56">
              <ResponsiveContainer>
                <BarChart data={procesos} layout="vertical" margin={{ left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E0E0E0" />
                  <XAxis
                    type="number"
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v) => `S/ ${(v / 1e3).toFixed(0)}k`}
                  />
                  <YAxis type="category" dataKey="nombre" width={140} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v: number) => formatSoles(v)} />
                  <Bar dataKey="monto">
                    {procesos.map((p) => (
                      <Cell key={p.nombre} fill={p.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>
        )}

        <section className="card p-5 overflow-x-auto">
          <h2 className="font-display font-semibold text-mountain-900 mb-2">
            Actividades y proyectos, {d.anio}
          </h2>
          <p className="text-xs text-ink-600 mb-4">
            El desglose del que salen las cifras de arriba: {d.actividades.length} línea(s)
            presupuestales del programa.
          </p>
          {d.actividades.length === 0 ? (
            <EmptyState
              title="Sin líneas presupuestales"
              message={`Esta municipalidad no tiene presupuesto del PP 0068 en ${d.anio}.`}
            />
          ) : (
            <table className="w-full text-sm min-w-[44rem]">
              <thead className="text-xs uppercase text-ink-600">
                <tr>
                  <th className="text-left py-2">Actividad o proyecto</th>
                  <th className="text-left py-2 hidden md:table-cell">Proceso</th>
                  <th className="text-right py-2">PIM</th>
                  <th className="text-right py-2">Devengado</th>
                  <th className="text-right py-2">% Ejec.</th>
                </tr>
              </thead>
              <tbody>
                {d.actividades.map((a) => (
                  <tr key={a.codigo} className="border-t border-ink-300/20">
                    <td className="py-2 pr-3">
                      <span className="font-mono text-xs text-ink-600">{a.codigo}</span>{" "}
                      {a.nombre}
                      {a.origen === "proyecto" && (
                        <span className="ml-2 text-xs px-1.5 py-0.5 rounded bg-sky-100 text-sky-800">
                          proyecto
                        </span>
                      )}
                    </td>
                    <td className="py-2 hidden md:table-cell text-ink-600">
                      {/* «Sin clasificar» explícito: el catálogo es editable y este hueco es la
                          señal de que a alguien le falta imputarla. */}
                      {a.proceso ?? <span className="text-yellow-800">Sin clasificar</span>}
                    </td>
                    <td className="py-2 text-right font-mono">{formatSoles(a.pim)}</td>
                    <td className="py-2 text-right font-mono">{formatSoles(a.devengado)}</td>
                    <td className="py-2 text-right font-mono">
                      {a.pct_ejecucion === null ? "—" : formatPct(a.pct_ejecucion)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>
    </>
  );
}
