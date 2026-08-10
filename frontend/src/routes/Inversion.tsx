import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Tooltip,
  XAxis, YAxis,
} from "recharts";
import { ChevronRight, Download } from "lucide-react";
import { urlApi, useApi, useApiPaginado } from "@/lib/api";
import { registrarExport } from "@/lib/metricas";
import { useBloque } from "@/lib/sitio";
import type { InversionEntidad, InversionResponse } from "@/lib/types";
import { formatNumber, formatPct, formatSoles } from "@/lib/semaforo";
import EmptyState from "@/components/EmptyState";
import KPI from "@/components/KPI";
import PageHeader from "@/components/PageHeader";

/**
 * Ventana de Inversión (PP 0068).
 *
 * Responde a una pregunta concreta: **¿cada municipalidad está ejecutando lo que se le
 * aprobó?** De ahí que el eje sea PIA → PIM → devengado y no un único porcentaje.
 *
 * Dos detalles de arquitectura que no son cosméticos:
 *
 * - **Los filtros viven en la URL.** Así la vista de comparación es enlazable y, al volver de
 *   la ficha de una municipalidad, el ejercicio y la provincia elegidos siguen puestos.
 * - **La tabla se pagina en servidor y el orden también.** Ordenar en el cliente ordenaría
 *   solo las filas ya cargadas, que con paginación deja de ser un ranking.
 */
const POR_PAGINA = 50;

const ORDENES: Record<string, string> = {
  pim: "Mayor PIM",
  ejecucion: "Mayor % de ejecución",
  saldo: "Mayor saldo pendiente",
  institucional: "Mayor peso sobre su presupuesto",
};
const ORDENES_COMPARACION: Record<string, string> = {
  variacion: "Mayor variación de PIM",
  ...ORDENES,
};

export default function InversionView() {
  const [params, setParams] = useSearchParams();
  const anio = params.get("anio") || "";
  const provincia = params.get("provincia") || "";
  const comparando = params.get("vista") === "comparar";
  const compararCon = comparando ? params.get("comparar_con") || "" : "";
  const orden = params.get("ordenar") || (comparando ? "variacion" : "pim");

  const ponerParam = (clave: string, valor: string) => {
    const siguientes = new URLSearchParams(params);
    if (valor) siguientes.set(clave, valor);
    else siguientes.delete(clave);
    setParams(siguientes, { replace: true });
  };

  const filtros = {
    anio: anio || undefined,
    provincia: provincia || undefined,
    comparar_con: compararCon || undefined,
  };
  const inv = useApi<InversionResponse>("/inversion/", filtros);
  const tabla = useApiPaginado<InversionEntidad>("/inversion/entidades/", {
    ...filtros,
    ordenar: orden,
  });
  const textoEnPreparacion = useBloque(
    "inversion.en_preparacion",
    "<p>PREDES está consolidando los datos de inversión del PP 0068. La sección se publicará " +
      "en cuanto la información esté disponible.</p>"
  );

  const datos = inv.status === "ok" && inv.data.disponible ? inv.data : null;

  // Del catálogo y no de las filas: con la tabla paginada, un selector construido con lo que
  // se ve solo ofrecería las provincias de la primera página. `/territorio/provincias/` va sin
  // paginar justamente para alimentar selectores (son 13).
  const catalogoProvincias = useApi<Array<{ ubigeo: string; nombre: string }>>(
    "/territorio/provincias/"
  );
  const provincias = useMemo(
    () => (catalogoProvincias.status === "ok" ? catalogoProvincias.data : []),
    [catalogoProvincias.status, catalogoProvincias.status === "ok" ? catalogoProvincias.data : null]
  );

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
  const comparacion = d.comparacion;
  const urlExport = urlApi("/inversion/export.xlsx", {
    anio: d.anio,
    provincia: provincia || undefined,
    ordenar: orden,
    comparar_con: compararCon || undefined,
  });

  const ejecucion = [
    { etapa: "PIA", monto: a.pia },
    { etapa: "PIM", monto: a.pim },
    { etapa: "Devengado", monto: a.devengado },
  ];
  const procesos = [
    ...d.procesos.map((p) => ({ nombre: p.nombre, monto: p.pim, color: p.color || "#007480" })),
    ...(d.sin_clasificar.pim > 0
      ? [{ nombre: "Sin clasificar", monto: d.sin_clasificar.pim, color: "#9CA3AF" }]
      : []),
  ];
  const ordenesDisponibles = comparando ? ORDENES_COMPARACION : ORDENES;

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
        {/* --- Vistas ------------------------------------------------------------------- */}
        <div className="flex flex-wrap gap-2 mb-6" role="tablist">
          <BotonVista activa={!comparando} onClick={() => ponerParam("vista", "")}>
            Ejercicio {d.anio}
          </BotonVista>
          <BotonVista activa={comparando} onClick={() => ponerParam("vista", "comparar")}>
            Comparar ejercicios
          </BotonVista>
        </div>

        <section className="flex flex-wrap items-end gap-4 mb-6">
          <label className="text-sm">
            <span className="block text-ink-600 mb-1">Ejercicio</span>
            <select
              value={d.anio}
              onChange={(e) => ponerParam("anio", e.target.value)}
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

          {comparando && (
            <label className="text-sm">
              <span className="block text-ink-600 mb-1">Comparar con</span>
              <select
                value={compararCon}
                onChange={(e) => ponerParam("comparar_con", e.target.value)}
                className="control py-1.5"
              >
                <option value="">Elige un ejercicio…</option>
                {d.ejercicios
                  .filter((e) => e.anio !== d.anio)
                  .map((e) => (
                    <option key={e.anio} value={e.anio}>
                      {e.anio}
                      {e.es_parcial ? ` (corte ${e.corte})` : ""}
                    </option>
                  ))}
              </select>
            </label>
          )}

          <label className="text-sm">
            <span className="block text-ink-600 mb-1">Provincia</span>
            <select
              value={provincia}
              onChange={(e) => ponerParam("provincia", e.target.value)}
              className="control py-1.5"
            >
              <option value="">Todas</option>
              {provincias.map((p) => (
                <option key={p.ubigeo} value={p.ubigeo}>{p.nombre}</option>
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

        {comparando ? (
          <CabeceraComparacion datos={d} />
        ) : (
          <>
            <section className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
              <KPI label={`PIM del PP 0068 · ${d.anio}`} value={formatSoles(a.pim)} />
              <KPI
                label="Devengado"
                value={formatSoles(a.devengado)}
                sub={
                  a.pct_ejecucion === null ? "sin PIM" : `${formatPct(a.pct_ejecucion)} de ejecución`
                }
              />
              <KPI
                label="Saldo por ejecutar"
                value={formatSoles(a.saldo)}
                sub="presupuesto aprobado y aún no gastado"
              />
              <KPI
                label="Presupuesto institucional total"
                value={a.pim_institucional === null ? "Sin dato" : formatSoles(a.pim_institucional)}
                sub={
                  a.pct_0068_institucional === null
                    ? "ninguna municipalidad con total institucional"
                    : `el PP 0068 es el ${formatPct(a.pct_0068_institucional)}, sobre ${a.entidades_con_institucional} municipalidad(es)`
                }
              />
            </section>

            <section className="grid lg:grid-cols-2 gap-6">
              <div className="card p-5">
                <h2 className="font-display font-semibold text-mountain-900 mb-2">
                  ¿Se ejecuta lo proyectado? — {d.anio}
                </h2>
                <p className="text-xs text-ink-600 mb-4">
                  De lo aprobado al abrir el año (PIA) a lo gastado. La variación PIA-PIM del
                  ámbito es de {formatSoles(a.variacion_pia_pim)}.
                </p>
                <div className="h-64">
                  <ResponsiveContainer>
                    <BarChart data={ejecucion}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#E0E0E0" />
                      <XAxis dataKey="etapa" tick={{ fontSize: 12 }} />
                      <YAxis
                        tick={{ fontSize: 12 }}
                        tickFormatter={(v) => `S/ ${(v / 1e6).toFixed(0)}M`}
                      />
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
                  PIM por proceso. {formatPct(a.pct_proyectos ?? 0)} del presupuesto está en
                  proyectos de inversión y el resto en actividades.
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
                PIM y devengado en millones de soles. La serie combina el comparativo del MEF con
                la base entregada por PREDES, y los ejercicios con corte parcial van marcados con
                un asterisco.
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
          </>
        )}

        <section className="mt-8">
          <div className="flex flex-wrap items-end justify-between gap-3 mb-3">
            <h2 className="font-display text-xl font-bold text-mountain-900">Municipalidades</h2>
            <div className="flex items-center gap-2 text-sm">
              <span className="text-ink-600">Ordenar por:</span>
              <select
                value={orden}
                onChange={(e) => ponerParam("ordenar", e.target.value)}
                className="control py-1.5"
              >
                {Object.entries(ordenesDisponibles).map(([clave, etiqueta]) => (
                  <option key={clave} value={clave}>{etiqueta}</option>
                ))}
              </select>
            </div>
          </div>

          {comparando && !compararCon ? (
            <EmptyState
              title="Elige un ejercicio para comparar"
              message={`Se enfrentará con ${d.anio} para ver qué municipalidades subieron y cuáles bajaron.`}
            />
          ) : (
            <>
              <div className="card overflow-x-auto">
                <table className="w-full text-sm min-w-[46rem]">
                  <thead className="bg-mountain-700 text-xs uppercase tracking-wide text-white/90">
                    <tr>
                      <th className="text-left px-4 py-3">Municipalidad</th>
                      <th className="text-left px-4 py-3 hidden md:table-cell">Provincia</th>
                      {comparando ? (
                        <>
                          <th className="text-right px-4 py-3">PIM {d.anio}</th>
                          <th className="text-right px-4 py-3">PIM {compararCon}</th>
                          <th className="text-right px-4 py-3">Δ PIM</th>
                          <th className="text-right px-4 py-3">Δ %</th>
                          <th className="text-right px-4 py-3 hidden lg:table-cell">Δ % ejec.</th>
                        </>
                      ) : (
                        <>
                          <th className="text-right px-4 py-3">PIA</th>
                          <th className="text-right px-4 py-3">PIM</th>
                          <th className="text-right px-4 py-3">Devengado</th>
                          <th className="text-right px-4 py-3">% Ejec.</th>
                          <th className="text-right px-4 py-3">Saldo</th>
                          <th className="text-right px-4 py-3 hidden xl:table-cell">
                            PIM institucional
                          </th>
                          <th className="text-right px-4 py-3 hidden lg:table-cell">% del total</th>
                        </>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {tabla.resultados.map((f) => (
                      <tr
                        key={f.codigo}
                        className="border-t border-ink-300/20 hover:bg-mountain-100/40"
                      >
                        <td className="px-4 py-3 font-medium">
                          {/* Los filtros viajan con el enlace para que la ficha sepa qué
                              ejercicio mirar y para que «volver» devuelva a esta misma vista,
                              con su orden y su comparación puestos. */}
                          <Link to={`/inversion/${f.codigo}?${params.toString()}`}>
                            {f.entidad}
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-ink-600 hidden md:table-cell">
                          {f.provincia ?? "—"}
                        </td>
                        {comparando ? <CeldasComparacion fila={f} /> : <CeldasEjercicio fila={f} />}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* El pie es el contrato de la paginación: dice cuántas filas se ven de cuántas
                  hay, para que nadie lea el total como si fuera lo cargado. */}
              <div className="flex flex-wrap items-center justify-between gap-3 mt-3 pt-3 border-t border-ink-300/30">
                <span className="text-xs text-ink-600">
                  Mostrando {formatNumber(tabla.resultados.length)} de{" "}
                  {formatNumber(tabla.total)} municipalidades
                </span>
                {tabla.hayMas && (
                  <button
                    onClick={tabla.cargarMas}
                    disabled={tabla.cargando}
                    className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded border border-ink-300/40 text-ink-600 hover:bg-mountain-100 disabled:opacity-40 disabled:hover:bg-transparent"
                  >
                    {tabla.cargando ? "Cargando…" : `Ver ${POR_PAGINA} más`}
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>

              {comparando && comparacion && !comparacion.comparable && (
                <p className="text-xs text-yellow-900 mt-3 bg-level-2/10 border border-level-2/40 rounded-lg px-3 py-2">
                  * Los dos ejercicios tienen cortes distintos —{d.corte} frente a{" "}
                  {comparacion.corte}—, así que <strong>la variación del % de ejecución no es
                  comparable</strong>: no mide una caída, mide medio año contra un año entero. Las
                  variaciones de PIM sí lo son.
                </p>
              )}
            </>
          )}
        </section>
      </div>
    </>
  );
}

function CeldasEjercicio({ fila: f }: { fila: InversionEntidad }) {
  return (
    <>
      <td className="px-4 py-3 text-right font-mono">{formatSoles(f.pia)}</td>
      <td className="px-4 py-3 text-right font-mono">{formatSoles(f.pim)}</td>
      <td className="px-4 py-3 text-right font-mono">{formatSoles(f.devengado)}</td>
      <td className="px-4 py-3 text-right font-mono">
        {f.pct_ejecucion === null ? "—" : formatPct(f.pct_ejecucion)}
      </td>
      <td className="px-4 py-3 text-right font-mono">{formatSoles(f.saldo)}</td>
      <td className="px-4 py-3 text-right font-mono hidden xl:table-cell">
        {f.pim_institucional === null ? "—" : formatSoles(f.pim_institucional)}
      </td>
      {/* «—» y no «0 %»: sin total institucional el porcentaje no se puede calcular, que es
          distinto de que el 0068 no pese nada. */}
      <td className="px-4 py-3 text-right font-mono hidden lg:table-cell">
        {f.pct_0068_institucional === null ? "—" : formatPct(f.pct_0068_institucional)}
      </td>
    </>
  );
}

function CeldasComparacion({ fila: f }: { fila: InversionEntidad }) {
  const c = f.comparacion;
  if (!c) return null;
  return (
    <>
      <td className="px-4 py-3 text-right font-mono">{formatSoles(f.pim)}</td>
      <td className="px-4 py-3 text-right font-mono">
        {/* «Sin presupuesto» y no «S/ 0»: la municipalidad no participó del programa ese año. */}
        {c.sin_presupuesto ? "sin presupuesto" : formatSoles(c.pim ?? 0)}
      </td>
      <td className="px-4 py-3 text-right font-mono">
        {c.delta_pim === null ? "—" : <Delta valor={c.delta_pim} formato={formatSoles} />}
      </td>
      <td className="px-4 py-3 text-right font-mono">
        {c.pct_delta_pim === null ? "—" : <Delta valor={c.pct_delta_pim} formato={formatPct} />}
      </td>
      <td className="px-4 py-3 text-right font-mono hidden lg:table-cell">
        {c.delta_pct_ejecucion === null ? (
          "—"
        ) : (
          <>
            <Delta valor={c.delta_pct_ejecucion} formato={formatPct} />
            {!c.comparable && <span title="Cortes distintos: no es comparable">*</span>}
          </>
        )}
      </td>
    </>
  );
}

function Delta({ valor, formato }: { valor: number; formato: (n: number) => string }) {
  const color = valor > 0 ? "text-mountain-700" : valor < 0 ? "text-level-4" : "text-ink-600";
  return (
    <span className={color}>
      {valor > 0 ? "+" : ""}
      {formato(valor)}
    </span>
  );
}

function CabeceraComparacion({ datos }: { datos: Extract<InversionResponse, { disponible: true }> }) {
  const c = datos.comparacion;
  if (!c) {
    return (
      <p className="text-sm text-ink-600 mb-6">
        Elige con qué ejercicio comparar {datos.anio}.
      </p>
    );
  }
  const a = datos.agregados;
  const filas: Array<[string, number, number, number, ((n: number) => string)]> = [
    ["PIA", a.pia, c.agregados.pia, c.deltas.pia, formatSoles],
    ["PIM", a.pim, c.agregados.pim, c.deltas.pim, formatSoles],
    ["Devengado", a.devengado, c.agregados.devengado, c.deltas.devengado, formatSoles],
  ];
  return (
    <section className="card p-5 mb-8">
      <h2 className="font-display font-semibold text-mountain-900 mb-4">
        {datos.anio}
        {datos.es_parcial ? ` (corte ${datos.corte})` : ""} frente a {c.anio}
        {c.es_parcial ? ` (corte ${c.corte})` : ""}
      </h2>
      <table className="w-full text-sm">
        <thead className="text-xs uppercase text-ink-600">
          <tr>
            <th className="text-left py-2">Concepto</th>
            <th className="text-right py-2">{datos.anio}</th>
            <th className="text-right py-2">{c.anio}</th>
            <th className="text-right py-2">Variación</th>
          </tr>
        </thead>
        <tbody>
          {filas.map(([etiqueta, actual, otro, delta, formato]) => (
            <tr key={etiqueta} className="border-t border-ink-300/20">
              <td className="py-2">{etiqueta}</td>
              <td className="py-2 text-right font-mono">{formato(actual)}</td>
              <td className="py-2 text-right font-mono">{formato(otro)}</td>
              <td className="py-2 text-right font-mono">
                <Delta valor={delta} formato={formato} />
              </td>
            </tr>
          ))}
          <tr className="border-t border-ink-300/20">
            <td className="py-2">
              % de ejecución {!c.comparable && <span className="text-yellow-800">*</span>}
            </td>
            <td className="py-2 text-right font-mono">
              {a.pct_ejecucion === null ? "—" : formatPct(a.pct_ejecucion)}
            </td>
            <td className="py-2 text-right font-mono">
              {c.agregados.pct_ejecucion === null ? "—" : formatPct(c.agregados.pct_ejecucion)}
            </td>
            <td className="py-2 text-right font-mono">
              {c.deltas.pct_ejecucion === null ? (
                "—"
              ) : (
                <Delta valor={c.deltas.pct_ejecucion} formato={formatPct} />
              )}
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  );
}

function BotonVista({
  activa,
  onClick,
  children,
}: {
  activa: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      role="tab"
      aria-selected={activa}
      onClick={onClick}
      className={`px-4 py-2 rounded-full text-sm font-medium transition ${
        activa
          ? "bg-mountain-700 text-white"
          : "border border-ink-300/40 text-ink-600 hover:bg-mountain-100"
      }`}
    >
      {children}
    </button>
  );
}
