import { useMemo } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Tooltip,
  XAxis, YAxis,
} from "recharts";
import { ChevronRight, Download, FileText } from "lucide-react";
import { urlApi, useApi, useApiPaginado } from "@/lib/api";
import { registrar, registrarExport } from "@/lib/metricas";
import { useBloque } from "@/lib/sitio";
import type {
  CapaMapa,
  Inversion,
  InversionEntidad,
  InversionMapaResponse,
  InversionResponse,
  MetricaMapa,
} from "@/lib/types";
import { formatNumber, formatPct, formatSoles } from "@/lib/semaforo";
import {
  PIE_EJERCICIO_PARCIAL,
  estadoEjercicio,
  etiquetaEjercicio,
  mesDelCorte,
} from "@/lib/inversion";
import BotonDescarga from "@/components/BotonDescarga";
import Declaracion from "@/components/Declaracion";
import EmptyState from "@/components/EmptyState";
import KPI from "@/components/KPI";
import MapaInversion from "@/components/MapaInversion";
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

const METRICAS_MAPA: MetricaMapa[] = ["pia", "pim", "devengado", "pct_ejecucion"];

export default function InversionView() {
  const [params, setParams] = useSearchParams();
  const navegar = useNavigate();
  const anio = params.get("anio") || "";
  const provincia = params.get("provincia") || "";
  const comparando = params.get("vista") === "comparar";
  const compararCon = comparando ? params.get("comparar_con") || "" : "";
  const orden = params.get("ordenar") || (comparando ? "variacion" : "pim");
  // El nivel y la métrica del mapa también viven en la URL: así el visor es enlazable con la
  // vista puesta, que es la forma en que estas cifras se citan en una reunión.
  const nivelMapa = params.get("nivel") === "provincial" ? "provincial" : "distrital";
  const metricaMapa = (
    METRICAS_MAPA.includes(params.get("metrica") as MetricaMapa)
      ? params.get("metrica")
      : "pim"
  ) as MetricaMapa;

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
  // Aparte del tablero, y a propósito: si el mapa falla, la ventana sigue sirviendo sus cifras.
  const mapa = useApi<InversionMapaResponse>("/inversion/mapa/", {
    anio: anio || undefined,
    provincia: provincia || undefined,
    nivel: nivelMapa,
  });
  const capasMapa = useApi<CapaMapa[]>("/mapas/capas/");
  const textoEnPreparacion = useBloque(
    "inversion.en_preparacion",
    "<p>PREDES está consolidando los datos de inversión del PP 0068. La sección se publicará " +
      "en cuanto la información esté disponible.</p>"
  );

  const datos = inv.status === "ok" && inv.data.disponible ? inv.data : null;
  const mapaDatos = mapa.status === "ok" && mapa.data.disponible ? mapa.data : null;

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
  // Nunca dice «toda la región» mientras hay una provincia filtrada: el catálogo puede no haber
  // llegado todavía, y equivocar el ámbito es peor que nombrarlo de forma genérica.
  const nombreProvincia = provincias.find((p) => p.ubigeo === provincia)?.nombre;
  const ambitoTexto = !provincia
    ? "todas las municipalidades de la región Cusco"
    : nombreProvincia
      ? `las municipalidades de la provincia de ${nombreProvincia}`
      : "las municipalidades de la provincia elegida";
  const urlExport = urlApi("/inversion/export.xlsx", {
    anio: d.anio,
    provincia: provincia || undefined,
    ordenar: orden,
    comparar_con: compararCon || undefined,
  });
  // El reporte lleva **también** el nivel y la métrica del mapa: es lo que hace que el documento
  // sea reproducible desde el enlace con el que se pidió, igual que la ayuda memoria de
  // /peligros arrastra sus filtros de peligro y nivel.
  const urlReporte = urlApi("/inversion/reporte.pdf", {
    anio: d.anio,
    provincia: provincia || undefined,
    ordenar: orden,
    nivel: nivelMapa,
    metrica: metricaMapa,
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
          <div className="flex flex-wrap gap-2">
            {/* El reporte tarda ~4 s: renderiza el mapa con un navegador headless. El botón
                lleva su estado y saca un aviso fijo, porque el `PageHeader` deja de verse en
                cuanto se baja a los gráficos. Ver `BotonDescarga`. */}
            <BotonDescarga
              url={urlReporte}
              onDescargar={() => registrar("descarga_pdf", "/inversion", String(d.anio))}
              title="Reporte del tablero con los filtros actuales: gráficas, mapa y la tabla completa"
              descripcion={`el reporte de inversión ${d.anio}`}
              etiquetaEnCurso="Generando PDF…"
              nombreDeReserva="reporte-inversion-pp0068.pdf"
              icono={<FileText className="w-4 h-4" />}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white text-mountain-900 text-sm font-medium transition hover:bg-mountain-100 no-underline"
            >
              Reporte (PDF)
            </BotonDescarga>
            <BotonDescarga
              url={urlExport}
              onDescargar={() => registrarExport("/inversion", String(d.anio))}
              title="Descarga la tabla de municipalidades con los filtros actuales"
              descripcion="el Excel de municipalidades"
              etiquetaEnCurso="Preparando Excel…"
              nombreDeReserva="inversion-pp0068.xlsx"
              icono={<Download className="w-4 h-4" />}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/15 text-white text-sm font-medium border border-white/25 transition hover:bg-white/25 no-underline"
            >
              Excel
            </BotonDescarga>
          </div>
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

        {/* Para qué sirve la pestaña, antes de pedir el segundo año. Hasta aquí no lo decía
            nada: al entrar solo aparecía «Elige un ejercicio para comparar», que dice cómo
            usarla pero no qué se gana usándola. */}
        {comparando && (
          <p className="text-sm text-ink-600 max-w-2xl mb-6">
            Enfrenta dos ejercicios <strong>municipalidad por municipalidad</strong>: cuánto subió
            o bajó su PIM, cuánto más o menos devengó, y quién entró o salió del programa. La
            tendencia del tablero ya da el total de la región; esto es lo que en ella no se ve.
          </p>
        )}

        <section className="flex flex-wrap items-end gap-4 mb-6">
          <label className="text-sm">
            <span className="block text-ink-600 mb-1">Ejercicio</span>
            <select
              value={d.anio}
              onChange={(e) => ponerParam("anio", e.target.value)}
              title="Sin elegir nada se muestra el ejercicio publicado más reciente."
              className="control py-1.5"
            >
              {d.ejercicios.map((e) => (
                <option key={e.anio} value={e.anio}>{etiquetaEjercicio(e)}</option>
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
                    <option key={e.anio} value={e.anio}>{etiquetaEjercicio(e)}</option>
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

          {/* Qué se está viendo. Sin filtros la página servía el ejercicio más reciente y toda
              la región sin decirlo en ninguna parte: el encabezado ponía «ejercicio 2026» y
              nadie declaraba que era un valor por defecto ni cuál era el ámbito territorial.
              La tabla de cabecera del PDF ya lo hacía.

              Aquí estuvo también la unidad («la municipalidad, no el distrito») y el recuento
              de cuántas tienen presupuesto del 0068. Se quitaron para que entre el filtro y la
              primera cifra no haya un párrafo que leer: la unidad la siguen diciendo el
              encabezado «Municipalidades», la columna de la tabla y la leyenda del mapa, y el
              PDF la deja escrita entera. */}
          <p className="text-xs text-ink-600 max-w-md">
            Viendo <strong>{ambitoTexto}</strong>, ejercicio {d.anio}
            {d.es_parcial ? ` al corte de ${mesDelCorte(d)}` : ""}. Fuente: {d.fuente}.
          </p>
        </section>

        {/* El corte parcial se avisa donde se leen las cifras, y NOMBRA el ejercicio: dice qué
            es, no con qué no se compara. La versión anterior solo advertía, y obligaba a saber
            qué es un «ejercicio cerrado» para deducir por descarte que 2026 es el año corriente.

            La banda solo identifica; la explicación de por qué un % de medio año no es media
            ejecución perdida vive al pie del cuadro de tendencia (`PIE_EJERCICIO_PARCIAL`),
            que es donde están los porcentajes que se comparan entre sí, y en el PDF. Estuvo
            también aquí y eran cuatro líneas de aviso antes del primer número. */}
        {d.es_parcial && (
          <p className="mb-6 rounded-lg border border-level-2/40 bg-level-2/10 px-4 py-3 text-sm text-yellow-900">
            <strong>
              Ejercicio {d.anio}, {estadoEjercicio(d)}
            </strong>
            {d.corte_legible ? ` — corte a ${d.corte_legible}.` : "."}
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
                label="Presupuesto institucional (PIM)"
                value={a.pim_institucional === null ? "Sin dato" : formatSoles(a.pim_institucional)}
                sub={
                  a.pct_0068_institucional === null
                    ? "ninguna municipalidad con total institucional"
                    : `PIA ${formatSoles(a.pia_institucional ?? 0)} · el PP 0068 es el ${formatPct(a.pct_0068_institucional)}, sobre ${a.entidades_con_institucional} municipalidad(es)`
                }
              />
            </section>

            <section className="grid lg:grid-cols-2 gap-6">
              <div className="card p-5">
                <h2 className="font-display font-semibold text-mountain-900 mb-2">
                  ¿Se ejecuta lo proyectado? — {d.anio}
                </h2>
                <p className="text-xs text-ink-600 mb-4">
                  De lo aprobado al abrir el año (PIA) a lo gastado.
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
                <Declaracion>{d.declaraciones.ejecucion}</Declaracion>
              </div>

              <div className="card p-5">
                <h2 className="font-display font-semibold text-mountain-900 mb-2">
                  ¿En qué se invierte? — procesos de la GRD
                </h2>
                <p className="text-xs text-ink-600 mb-3">
                  PIM por proceso. El reparto se clasifica por actividad y no por producto: a
                  nivel de producto, «Acciones comunes» y los proyectos se llevan tres cuartas
                  partes y el gráfico no dice nada.
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
                <Declaracion>{d.declaraciones.procesos}</Declaracion>
              </div>
            </section>

            {/* Los proyectos tenían media tarjeta prestada de «¿En qué se invierte?», y su barra
                sola decía «el 40 % va a obra» sin decir de quién. Ese porcentaje se lee como si
                todas las municipalidades hicieran obra, y casi ninguna la hace: en la región son
                24 de 116. El cuadro es la respuesta a «este monto parece alto». */}
            <section className="card p-5 mt-6">
              <h2 className="font-display font-semibold text-mountain-900 mb-2">
                Proyectos de inversión frente a actividades — {d.anio}
              </h2>
              <p className="text-xs text-ink-600 mb-3">
                Un proyecto es una obra —defensas ribereñas, muros de contención—; una actividad
                es gasto recurrente. Los dos son gestión del riesgo, pero no se ejecutan igual ni
                los tiene el mismo número de municipalidades.
              </p>
              <ProyectosVsActividades
                proyectos={a.pim_proyectos}
                actividades={a.pim_actividades}
                pct={a.pct_proyectos}
              />
              <Declaracion>{d.declaraciones.proyectos}</Declaracion>
              <TablaProyectos proyectos={d.proyectos} params={params} />
            </section>

            <section className="card p-5 mt-6">
              <h2 className="font-display font-semibold text-mountain-900 mb-2">
                Tendencia {d.tendencia[0]?.anio}-{d.tendencia[d.tendencia.length - 1]?.anio}
              </h2>
              <p className="text-xs text-ink-600 mb-4">
                PIA, PIM y devengado en millones de soles. Las tres juntas cuentan el ciclo
                completo: lo aprobado al abrir el año, lo que quedó tras las modificaciones y lo
                que se llegó a gastar. La serie combina el comparativo del MEF con la base
                desarrollada por PREDES, y los ejercicios con corte parcial van con asterisco.
              </p>
              <div className="h-64">
                <ResponsiveContainer>
                  <LineChart
                    data={d.tendencia.map((t) => ({
                      etiqueta: t.es_parcial ? `${t.anio}*` : String(t.anio),
                      PIA: t.pia / 1e6,
                      PIM: t.pim / 1e6,
                      Devengado: t.devengado / 1e6,
                    }))}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#E0E0E0" />
                    <XAxis dataKey="etiqueta" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip formatter={(v: number) => `S/ ${v.toFixed(1)}M`} />
                    <Legend />
                    {/* El PIA va punteado: es el punto de partida, no una tercera magnitud del
                        mismo rango — la distancia entre él y el PIM es la variación. */}
                    <Line
                      type="monotone"
                      dataKey="PIA"
                      stroke="#B8753C"
                      strokeWidth={2}
                      strokeDasharray="5 4"
                    />
                    <Line type="monotone" dataKey="PIM" stroke="#007480" strokeWidth={2.5} />
                    <Line type="monotone" dataKey="Devengado" stroke="#009257" strokeWidth={2.5} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <Declaracion>{d.declaraciones.tendencia}</Declaracion>

              <div className="overflow-x-auto mt-5">
                <table className="w-full text-sm min-w-[44rem]">
                  <thead className="text-xs uppercase text-ink-600">
                    <tr>
                      <th className="text-left py-2">Ejercicio</th>
                      <th className="text-right py-2">PIA</th>
                      <th className="text-right py-2">PIM</th>
                      <th className="text-right py-2 hidden lg:table-cell">Variación PIA-PIM</th>
                      <th className="text-right py-2">Devengado</th>
                      <th className="text-right py-2">% Ejec.</th>
                      <th className="text-right py-2">Saldo</th>
                      <th className="text-left py-2 pl-6 hidden lg:table-cell">Fuente</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.tendencia.map((t) => (
                      <tr
                        key={t.anio}
                        className={`border-t border-ink-300/20 ${t.anio === d.anio ? "bg-mountain-100/40" : ""}`}
                      >
                        <td className="py-2">
                          {t.anio}
                          {t.es_parcial && (
                            <span className="text-xs text-yellow-800" title={`Corte a ${t.corte}`}>
                              {" "}
                              *
                            </span>
                          )}
                        </td>
                        <td className="py-2 text-right font-mono">{formatSoles(t.pia)}</td>
                        <td className="py-2 text-right font-mono">{formatSoles(t.pim)}</td>
                        <td className="py-2 text-right font-mono hidden lg:table-cell">
                          {formatSoles(t.pim - t.pia)}
                        </td>
                        <td className="py-2 text-right font-mono">{formatSoles(t.devengado)}</td>
                        <td className="py-2 text-right font-mono">
                          {t.pim === 0 ? "—" : formatPct(t.devengado / t.pim)}
                        </td>
                        <td className="py-2 text-right font-mono">
                          {formatSoles(t.pim - t.devengado)}
                        </td>
                        <td className="py-2 pl-6 text-xs text-ink-600 hidden lg:table-cell">
                          {t.fuente}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {d.tendencia.some((t) => t.es_parcial) && (
                <p className="text-xs text-ink-600 mt-3">{PIE_EJERCICIO_PARCIAL}</p>
              )}
            </section>

            <section className="card p-5 mt-6">
              <h2 className="font-display font-semibold text-mountain-900 mb-2">
                ¿Dónde está el presupuesto? — {d.anio}
              </h2>
              {/* Sin entradilla: «el presupuesto es de municipalidades, no de territorios» ya
                  lo dice la línea de alcance de arriba, y qué no se pinta lo dice el pie. Eran
                  ~150 palabras alrededor de un mapa y el lector no llegaba al final. */}
              {mapaDatos && capasMapa.status === "ok" ? (
                <MapaInversion
                  datos={mapaDatos}
                  capas={capasMapa.data}
                  metrica={metricaMapa}
                  onMetrica={(m) => ponerParam("metrica", m === "pim" ? "" : m)}
                  onNivel={(n) => ponerParam("nivel", n === "distrital" ? "" : n)}
                  onSeleccionar={(fila) => {
                    if (mapaDatos.nivel === "provincial") ponerParam("provincia", fila.ubigeo);
                    else if (fila.codigo_entidad)
                      navegar(`/inversion/${fila.codigo_entidad}?${params.toString()}`);
                  }}
                />
              ) : (
                <p className="text-sm text-ink-600">
                  {mapa.status === "error" || capasMapa.status === "error"
                    ? "El mapa no está disponible ahora mismo. Las cifras de esta página no dependen de él."
                    : "Cargando el mapa…"}
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

/**
 * Proyectos de inversión contra actividades, en una sola barra.
 *
 * Era una frase suelta bajo el gráfico de procesos («el 26 % está en proyectos»), y un
 * porcentaje sin forma no deja ver que en algunos ámbitos la obra pública se come casi todo el
 * programa mientras la gestión corriente se queda sin nada.
 */
/**
 * Quién tiene los proyectos de inversión.
 *
 * Van todas las que tienen, sin recortar a un top N: son 24 en la región entera y 9 en la
 * provincia más cargada, y un «y otras N» no lo podría comprobar nadie. La columna «% de su
 * PIM» es la que distingue a quien hace una obra y poco más de quien reparte en actividades.
 */
function TablaProyectos({
  proyectos,
  params,
}: {
  proyectos: Inversion["proyectos"];
  params: URLSearchParams;
}) {
  if (!proyectos.entidades.length) return null;
  return (
    <div className="overflow-x-auto mt-4">
      <table className="w-full text-sm min-w-[32rem]">
        <thead className="text-xs uppercase text-ink-600">
          <tr>
            <th className="text-left py-2">Municipalidad</th>
            <th className="text-left py-2 hidden sm:table-cell">Provincia</th>
            <th className="text-right py-2">PIM en proyectos</th>
            <th className="text-right py-2">% de su PIM</th>
          </tr>
        </thead>
        <tbody>
          {proyectos.entidades.map((e) => (
            <tr key={e.codigo} className="border-t border-sand-200">
              <td className="py-2">
                <Link to={`/inversion/${e.codigo}?${params.toString()}`} className="hover:underline">
                  {e.entidad}
                </Link>
              </td>
              <td className="py-2 hidden sm:table-cell text-ink-600">{e.provincia || "—"}</td>
              <td className="py-2 text-right tabular-nums">{formatSoles(e.pim_proyectos)}</td>
              <td className="py-2 text-right tabular-nums">
                {e.pct_proyectos === null ? "—" : formatPct(e.pct_proyectos)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ProyectosVsActividades({
  proyectos,
  actividades,
  pct,
}: {
  proyectos: number;
  actividades: number;
  pct: number | null;
}) {
  const total = proyectos + actividades;
  if (total <= 0) return null;
  const anchoProyectos = (proyectos / total) * 100;
  return (
    <div className="mb-4">
      <div className="flex h-5 rounded overflow-hidden border border-ink-300/40">
        <div
          className="bg-sky-700"
          style={{ width: `${anchoProyectos}%` }}
          title={`Proyectos de inversión: ${formatSoles(proyectos)}`}
        />
        <div
          className="bg-earth-200"
          style={{ width: `${100 - anchoProyectos}%` }}
          title={`Actividades: ${formatSoles(actividades)}`}
        />
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-ink-600 mt-1.5">
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-[2px] bg-sky-700 shrink-0" />
          Proyectos de inversión {formatPct(pct ?? 0)} · {formatSoles(proyectos)}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-[2px] bg-earth-200 shrink-0" />
          Actividades · {formatSoles(actividades)}
        </span>
      </div>
    </div>
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
