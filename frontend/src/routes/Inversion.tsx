import { useMemo, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Tooltip,
  XAxis, YAxis,
} from "recharts";
import { Download } from "lucide-react";
import { urlApi, useApi } from "@/lib/api";
import { registrarExport } from "@/lib/metricas";
import { useBloque } from "@/lib/sitio";
import type { InversionEntidad, InversionResponse } from "@/lib/types";
import { formatPct, formatSoles } from "@/lib/semaforo";
import EmptyState from "@/components/EmptyState";
import PageHeader from "@/components/PageHeader";

/**
 * Ventana de Inversión (PP 0068).
 *
 * Responde a una pregunta concreta: **¿cada municipalidad está ejecutando lo que se le
 * aprobó?** De ahí que el eje sea PIA → PIM → devengado y no un único porcentaje: el PIA dice
 * lo que se proyectó al abrir el año, el PIM lo que quedó tras las modificaciones y el
 * devengado lo gastado. La brecha entre los dos primeros es tan informativa como la del tercero.
 *
 * La unidad es la municipalidad (entidad ejecutora), no el distrito. Y `disponible: false`
 * sigue siendo un modo válido: mientras PREDES no publique un ejercicio, la ruta muestra su
 * estado «información en preparación».
 */
type Orden = "pim" | "ejecucion" | "saldo";

const ORDENES: Record<Orden, { etiqueta: string; comparar: (a: InversionEntidad, b: InversionEntidad) => number }> = {
  pim: { etiqueta: "Mayor PIM", comparar: (a, b) => b.pim - a.pim },
  ejecucion: {
    etiqueta: "Mayor % de ejecución",
    comparar: (a, b) => (b.pct_ejecucion ?? -1) - (a.pct_ejecucion ?? -1),
  },
  saldo: { etiqueta: "Mayor saldo pendiente", comparar: (a, b) => b.saldo - a.saldo },
};

export default function InversionView() {
  const [anio, setAnio] = useState<number | null>(null);
  const [provincia, setProvincia] = useState("");
  const [orden, setOrden] = useState<Orden>("pim");

  const inv = useApi<InversionResponse>("/inversion/", {
    anio: anio ?? undefined,
    provincia: provincia || undefined,
  });
  const textoEnPreparacion = useBloque(
    "inversion.en_preparacion",
    "<p>PREDES está consolidando los datos de inversión del PP 0068. La sección se publicará " +
      "en cuanto la información esté disponible.</p>"
  );

  const datos = inv.status === "ok" && inv.data.disponible ? inv.data : null;

  const filas = useMemo(() => {
    if (!datos) return [];
    return [...datos.por_entidad].sort(ORDENES[orden].comparar);
  }, [datos, orden]);

  const provincias = useMemo(() => {
    if (!datos) return [];
    return [...new Set(datos.por_entidad.map((f) => f.provincia).filter(Boolean))].sort() as string[];
  }, [datos]);

  if (inv.status === "loading") return <div className="container-page py-12">Cargando…</div>;

  if (!datos) {
    const motivo = inv.status === "ok" && !inv.data.disponible ? inv.data.motivo : "";
    return (
      <>
        <PageHeader
          titulo="Inversión"
          descripcion="¿Cuánto y cómo invierten los gobiernos locales en reducción de vulnerabilidad y atención de emergencias? Programa Presupuestal 0068."
        />
        <div className="container-page py-12">
          <EmptyState
            title="Información en preparación"
            message={motivo || "Los datos de inversión aún no están disponibles."}
          />
          <div
            className="mt-6 max-w-2xl mx-auto text-center text-sm text-ink-600 [&_p]:m-0"
            dangerouslySetInnerHTML={{ __html: textoEnPreparacion }}
          />
        </div>
      </>
    );
  }

  const d = datos;
  const a = d.agregados;
  const urlExport = urlApi("/inversion/export.xlsx", {
    anio: d.anio,
    provincia: provincia || undefined,
  });

  const ejecucion = [
    { etapa: "PIA", monto: a.pia, detalle: "lo aprobado al abrir el año" },
    { etapa: "PIM", monto: a.pim, detalle: "tras las modificaciones" },
    { etapa: "Devengado", monto: a.devengado, detalle: "efectivamente gastado" },
  ];
  const procesos = [
    ...d.procesos.map((p) => ({ nombre: p.nombre, monto: p.pim, color: p.color || "#007480" })),
    ...(d.sin_clasificar.pim > 0
      ? [{ nombre: "Sin clasificar", monto: d.sin_clasificar.pim, color: "#9CA3AF" }]
      : []),
  ];

  return (
    <>
      <PageHeader
        titulo="Inversión"
        descripcion={`¿Están las municipalidades de Cusco ejecutando el presupuesto que se les aprobó para reducir el riesgo de desastres? Programa Presupuestal 0068 — ejercicio ${d.anio}.`}
        badge={
          <a
            href={urlExport}
            onClick={() => registrarExport("/inversion", String(d.anio))}
            title="Descarga la tabla de municipalidades con los filtros actuales"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/15 text-white text-sm font-medium border border-white/25 transition hover:bg-white/25 no-underline"
          >
            <Download className="w-4 h-4" />
            Excel
          </a>
        }
      />

      <div className="container-page py-8">
        {/* --- Ejercicio y ámbito ------------------------------------------------------- */}
        <section className="flex flex-wrap items-end gap-4 mb-6">
          <label className="text-sm">
            <span className="block text-ink-600 mb-1">Ejercicio</span>
            <select
              value={d.anio}
              onChange={(e) => setAnio(Number(e.target.value))}
              className="control py-1.5"
            >
              {d.ejercicios.map((e) => (
                <option key={e.anio} value={e.anio}>
                  {e.anio}
                  {e.es_parcial ? ` (corte ${e.corte})` : ""}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            <span className="block text-ink-600 mb-1">Provincia</span>
            <select
              value={provincia}
              onChange={(e) => setProvincia(e.target.value)}
              className="control py-1.5"
            >
              <option value="">Todas</option>
              {provincias.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </label>
          <p className="text-xs text-ink-600 max-w-md">
            Unidad: <strong>municipalidad</strong> ({a.entidades_con_presupuesto} de{" "}
            {a.entidades_en_ambito} con presupuesto del 0068). Fuente: {d.fuente}.
          </p>
        </section>

        {/* El corte parcial se avisa donde se leen las cifras, no en una nota al pie: el % de
            ejecución de medio año se calcula contra un PIM anual. */}
        {d.es_parcial && (
          <p className="mb-6 rounded-lg border border-level-2/40 bg-level-2/10 px-4 py-3 text-sm text-yellow-900">
            <strong>Corte a {d.corte}.</strong> El devengado no cubre el año completo, así que su
            porcentaje de ejecución no es comparable con el de un ejercicio cerrado.
          </p>
        )}

        <section className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <KPI label={`PIM del PP 0068 · ${d.anio}`} value={formatSoles(a.pim)} />
          <KPI
            label="Devengado"
            value={formatSoles(a.devengado)}
            sub={a.pct_ejecucion === null ? "sin PIM" : `${formatPct(a.pct_ejecucion)} de ejecución`}
          />
          <KPI
            label="Saldo por ejecutar"
            value={formatSoles(a.saldo)}
            sub="presupuesto aprobado y aún no gastado"
          />
          <KPI
            label="Peso dentro del presupuesto municipal"
            value={a.pct_0068_institucional === null ? "Sin dato" : formatPct(a.pct_0068_institucional)}
            sub={`sobre ${a.entidades_con_institucional} municipalidad(es) con total institucional`}
          />
        </section>

        <section className="grid lg:grid-cols-2 gap-6">
          <div className="card p-5">
            <h2 className="font-display font-semibold text-mountain-900 mb-2">
              ¿Se ejecuta lo proyectado? — {d.anio}
            </h2>
            <p className="text-xs text-ink-600 mb-4">
              De lo aprobado al abrir el año (PIA) a lo gastado. La variación PIA-PIM del ámbito
              es de {formatSoles(a.variacion_pia_pim)}.
            </p>
            <div className="h-64">
              <ResponsiveContainer>
                <BarChart data={ejecucion}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E0E0E0" />
                  <XAxis dataKey="etapa" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `S/ ${(v / 1e6).toFixed(0)}M`} />
                  <Tooltip formatter={(v: number) => formatSoles(v)} />
                  <Bar dataKey="monto" fill="#007480" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="card p-5">
            <h2 className="font-display font-semibold text-mountain-900 mb-2">
              ¿En qué se invierte? — procesos de la GRD
            </h2>
            <p className="text-xs text-ink-600 mb-4">
              PIM por proceso. {formatPct(a.pct_proyectos ?? 0)} del presupuesto está en proyectos
              de inversión y el resto en actividades.
            </p>
            <div className="h-64">
              <ResponsiveContainer>
                <BarChart data={procesos} layout="vertical" margin={{ left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E0E0E0" />
                  <XAxis
                    type="number"
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v) => `S/ ${(v / 1e6).toFixed(0)}M`}
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
          </div>
        </section>

        <section className="card p-5 mt-6">
          <h2 className="font-display font-semibold text-mountain-900 mb-2">
            Tendencia {d.tendencia[0]?.anio}-{d.tendencia[d.tendencia.length - 1]?.anio}
          </h2>
          <p className="text-xs text-ink-600 mb-4">
            PIM y devengado en millones de soles. La serie combina el comparativo del MEF con la
            base entregada por PREDES, y los ejercicios con corte parcial van marcados con un
            asterisco.
          </p>
          <div className="h-64">
            <ResponsiveContainer>
              <LineChart
                data={d.tendencia.map((t) => ({
                  etiqueta: t.es_parcial ? `${t.anio}*` : String(t.anio),
                  PIM: t.pim / 1e6,
                  Devengado: t.devengado / 1e6,
                }))}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#E0E0E0" />
                <XAxis dataKey="etiqueta" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip formatter={(v: number) => `S/ ${v.toFixed(1)}M`} />
                <Legend />
                <Line type="monotone" dataKey="PIM" stroke="#007480" strokeWidth={2.5} />
                <Line type="monotone" dataKey="Devengado" stroke="#009257" strokeWidth={2.5} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          {d.tendencia.some((t) => t.es_parcial) && (
            <p className="text-xs text-ink-600 mt-2">
              * Ejercicio con corte parcial: el devengado no cubre el año completo.
            </p>
          )}
        </section>

        <section className="mt-8">
          <div className="flex flex-wrap items-end justify-between gap-3 mb-3">
            <h2 className="font-display text-xl font-bold text-mountain-900">Municipalidades</h2>
            <div className="flex items-center gap-2 text-sm">
              <span className="text-ink-600">Ordenar por:</span>
              <select
                value={orden}
                onChange={(e) => setOrden(e.target.value as Orden)}
                className="control py-1.5"
              >
                {Object.entries(ORDENES).map(([clave, { etiqueta }]) => (
                  <option key={clave} value={clave}>{etiqueta}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="card overflow-x-auto">
            <table className="w-full text-sm min-w-[46rem]">
              <thead className="bg-mountain-700 text-xs uppercase tracking-wide text-white/90">
                <tr>
                  <th className="text-left px-4 py-3">Municipalidad</th>
                  <th className="text-left px-4 py-3 hidden md:table-cell">Provincia</th>
                  <th className="text-right px-4 py-3">PIA</th>
                  <th className="text-right px-4 py-3">PIM</th>
                  <th className="text-right px-4 py-3">Devengado</th>
                  <th className="text-right px-4 py-3">% Ejec.</th>
                  <th className="text-right px-4 py-3">Saldo</th>
                  <th className="text-right px-4 py-3 hidden lg:table-cell">% del total</th>
                </tr>
              </thead>
              <tbody>
                {filas.map((f) => (
                  <tr key={f.codigo} className="border-t border-ink-300/20 hover:bg-mountain-100/40">
                    <td className="px-4 py-3 font-medium">{f.entidad}</td>
                    <td className="px-4 py-3 text-ink-600 hidden md:table-cell">{f.provincia ?? "—"}</td>
                    <td className="px-4 py-3 text-right font-mono">{formatSoles(f.pia)}</td>
                    <td className="px-4 py-3 text-right font-mono">{formatSoles(f.pim)}</td>
                    <td className="px-4 py-3 text-right font-mono">{formatSoles(f.devengado)}</td>
                    <td className="px-4 py-3 text-right font-mono">
                      {f.pct_ejecucion === null ? "—" : formatPct(f.pct_ejecucion)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono">{formatSoles(f.saldo)}</td>
                    <td className="px-4 py-3 text-right font-mono hidden lg:table-cell">
                      {/* «—» y no «0 %»: sin total institucional el porcentaje no se puede
                          calcular, que es distinto de que el 0068 no pese nada. */}
                      {f.pct_0068_institucional === null ? "—" : formatPct(f.pct_0068_institucional)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </>
  );
}

function KPI({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card p-5">
      <div className="text-xs text-ink-600">{label}</div>
      <div className="mt-2 font-display font-extrabold text-2xl text-mountain-900">{value}</div>
      {sub && <div className="text-xs text-ink-600 mt-1">{sub}</div>}
    </div>
  );
}
