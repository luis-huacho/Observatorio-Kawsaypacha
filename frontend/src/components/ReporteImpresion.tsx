/**
 * Ayuda memoria imprimible del visor de exposición.
 *
 * Es el entregable que pide el TDR ("ayudas memoria PDF por distrito, para mesas técnicas") en
 * su versión de prototipo: se maqueta en HTML y se materializa con `window.print()`. En la
 * plataforma real el mismo documento lo generará WeasyPrint en el servidor a partir de una
 * plantilla equivalente (ADR-A9, endpoint `/api/distritos/{ubigeo}/ayuda-memoria.pdf`), así que
 * conviene que este marcado siga siendo portable: nada de trucos que dependan del navegador.
 *
 * Vive oculto en el DOM y solo se revela en `@media print` (clase `solo-impresion`).
 */
import type {
  CentroPoblado,
  ClasificacionPeligro,
  FrecuenciaDistrito,
  Nivel,
} from "@/lib/types";
import { NIVEL_COLOR, NIVEL_LABEL, formatNumber } from "@/lib/semaforo";

type Props = {
  /** Centros poblados del ámbito, ya filtrados por la página. */
  ccpp: CentroPoblado[];
  /** Clasificaciones que sobreviven a los filtros activos. */
  clasificaciones: ClasificacionPeligro[];
  stats: Record<Nivel, number>;
  frecuencia?: FrecuenciaDistrito;
  provincia: string;
  distrito: string;
  ubigeoDistrito: string;
  /** Nombre del peligro filtrado, o "" si están todos. */
  nombrePeligro: string;
  nivelMin: number;
  /** PNG de la vista del mapa; null si la captura falló. */
  mapaPng: string | null;
  mapaBase: string;
  generadoEn: Date;
};

export default function ReporteImpresion({
  ccpp,
  clasificaciones,
  stats,
  frecuencia,
  provincia,
  distrito,
  ubigeoDistrito,
  nombrePeligro,
  nivelMin,
  mapaPng,
  mapaBase,
  generadoEn,
}: Props) {
  const porCodigo = new Map(ccpp.map((c) => [c.codigo, c]));

  // Una fila por centro poblado clasificado, con sus peligros agrupados. Los que no tienen
  // clasificación quedan fuera de la tabla: se cuentan en el texto como vacío de información.
  const filas = agruparPorCentroPoblado(clasificaciones, porCodigo);

  const totalClasificados = filas.length;
  const totalAmbito = ccpp.length;
  const sinDato = totalAmbito - totalClasificados;
  const poblacionExpuesta = filas.reduce((s, f) => s + (f.ccpp.poblacion ?? 0), 0);
  const criticos = filas.filter((f) => f.nivelMax >= 3).length;

  const fecha = generadoEn.toLocaleDateString("es-PE", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
  // 24 h: en un documento formal "22:45 h" se lee mejor que "10:45 p. m.".
  const hora = generadoEn.toLocaleTimeString("es-PE", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

  const fuentes = [...new Set(clasificaciones.map((c) => c.fuente).filter(Boolean))];

  return (
    <div className="solo-impresion text-ink-900">
      {/* --- Membrete -------------------------------------------------------------------
          Deliberadamente <div> y no <header>: la regla de impresión oculta header/footer para
          quitar el cromo del sitio, y rescatarlos aquí obligaría a pelear con la cascada. */}
      <div className="flex items-start justify-between gap-6 border-b-2 border-mountain-700 pb-3">
        <div>
          <img src="/logo-predes-green.svg" alt="PREDES" style={{ height: 40 }} />
          <div className="text-[11px] text-ink-600 mt-1">
            Centro de Estudios y Prevención de Desastres
          </div>
        </div>
        <div className="text-right">
          <div className="font-display font-bold text-mountain-900">
            Observatorio Kallpachakuy
          </div>
          {/* Dos líneas explícitas: en una sola, "Cusco" se queda solo al final. */}
          <div className="text-[11px] text-ink-600 leading-tight">
            Gestión del Riesgo de Desastres
            <br />y Adaptación al Cambio Climático · Región Cusco
          </div>
        </div>
      </div>

      <h1 className="font-display text-xl font-bold text-mountain-900 mt-4">
        Ayuda memoria — Exposición a peligros naturales
      </h1>

      {/* --- Ámbito y trazabilidad ------------------------------------------------------ */}
      <table className="w-full text-[11px] mt-3 evitar-corte">
        <tbody>
          <Dato etiqueta="Ámbito">
            Distrito de {distrito}, provincia de {provincia}, región Cusco
          </Dato>
          <Dato etiqueta="Ubigeo">{ubigeoDistrito}</Dato>
          <Dato etiqueta="Filtros aplicados">
            {[
              nombrePeligro ? `Peligro: ${nombrePeligro}` : "Todos los peligros",
              nivelMin ? `Nivel mínimo: ${nivelMin} (${NIVEL_LABEL[nivelMin as Nivel]})` : null,
            ]
              .filter(Boolean)
              .join(" · ")}
          </Dato>
          <Dato etiqueta="Generado">
            {fecha}, {hora} h
          </Dato>
        </tbody>
      </table>

      {/* --- Texto de presentación, redactado con las cifras del propio filtro ---------- */}
      <section className="mt-4 text-[12px] leading-relaxed evitar-corte">
        <p>
          El distrito de <strong>{distrito}</strong> (provincia de {provincia}, región Cusco)
          registra <strong>{formatNumber(totalAmbito)}</strong>{" "}
          {plural(totalAmbito, "centro poblado", "centros poblados")} en el padrón del
          Observatorio. De ellos, <strong>{formatNumber(totalClasificados)}</strong>{" "}
          {plural(totalClasificados, "cuenta", "cuentan")} con clasificación de nivel de peligro
          {nombrePeligro ? <> frente a <strong>{nombrePeligro.toLowerCase()}</strong></> : null}
          {nivelMin ? <> en nivel {NIVEL_LABEL[nivelMin as Nivel].toLowerCase()} o superior</> : null}
          , según la información de SIGRID-CENEPRED.
        </p>
        {totalClasificados > 0 && (
          <p className="mt-2">
            {criticos > 0 ? (
              <>
                <strong>{formatNumber(criticos)}</strong> de esos centros poblados{" "}
                {plural(criticos, "presenta", "presentan")} al menos un peligro clasificado en
                nivel <strong>alto o muy alto</strong>.{" "}
              </>
            ) : null}
            La población registrada en los centros poblados clasificados asciende a{" "}
            <strong>{formatNumber(poblacionExpuesta)}</strong> habitantes según el padrón vigente.
          </p>
        )}
        {frecuencia && frecuencia.total > 0 && (
          <p className="mt-2">
            El distrito acumula <strong>{formatNumber(frecuencia.total)}</strong> emergencias
            registradas
            {frecuencia.rango_fecha ? <> en el periodo {frecuencia.rango_fecha}</> : null}
            {frecuencia.desglose_disponible ? (
              <>
                , siendo <strong>{eventoMasFrecuente(frecuencia)}</strong> el evento más recurrente
              </>
            ) : (
              <> (la fuente reporta el total sin desagregar por tipo de evento)</>
            )}
            .
          </p>
        )}
        {sinDato > 0 && (
          <p className="mt-2">
            Cabe señalar que <strong>{formatNumber(sinDato)}</strong>{" "}
            {plural(sinDato, "centro poblado", "centros poblados")} del distrito{" "}
            {plural(sinDato, "no cuenta", "no cuentan")} con clasificación de peligro en la base
            consultada. Esta ausencia no equivale a ausencia de riesgo: constituye un vacío de
            información que se recomienda cubrir mediante evaluación técnica.
          </p>
        )}
      </section>

      {/* --- Mapa ---------------------------------------------------------------------- */}
      {mapaPng && (
        <section className="mt-4 evitar-corte">
          <h2 className="font-display font-semibold text-mountain-900 text-sm mb-1">
            Mapa de exposición
          </h2>
          <img
            src={mapaPng}
            alt={`Mapa de exposición a peligros del distrito de ${distrito}`}
            className="w-full border border-ink-300/50 rounded"
          />
          <div className="text-[10px] text-ink-600 mt-1">
            Vista generada desde el visor del Observatorio. Mapa base: {mapaBase}. Los círculos
            representan centros poblados coloreados por nivel de peligro.
          </div>
        </section>
      )}

      {/* --- Distribución por nivel ----------------------------------------------------- */}
      <section className="mt-4 evitar-corte">
        <h2 className="font-display font-semibold text-mountain-900 text-sm mb-1">
          Distribución de centros poblados por nivel máximo
        </h2>
        <table className="w-full text-[11px] border-collapse">
          <thead>
            <tr className="bg-mountain-100">
              {([4, 3, 2, 1] as Nivel[]).map((n) => (
                <th key={n} className="border border-ink-300/50 px-2 py-1 text-left font-medium">
                  <span
                    className="inline-block w-2 h-2 rounded-full align-middle mr-1"
                    style={{ backgroundColor: NIVEL_COLOR[n] }}
                  />
                  {NIVEL_LABEL[n]}
                </th>
              ))}
              <th className="border border-ink-300/50 px-2 py-1 text-left font-medium">Total</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              {([4, 3, 2, 1] as Nivel[]).map((n) => (
                <td key={n} className="border border-ink-300/50 px-2 py-1 font-mono">
                  {formatNumber(stats[n])}
                </td>
              ))}
              <td className="border border-ink-300/50 px-2 py-1 font-mono font-semibold">
                {formatNumber(stats[1] + stats[2] + stats[3] + stats[4])}
              </td>
            </tr>
          </tbody>
        </table>
        <div className="text-[10px] text-ink-600 mt-1">
          Cada centro poblado se cuenta una sola vez, en el más alto de sus peligros evaluados. El
          total de arriba resume {formatNumber(clasificaciones.length)}{" "}
          {clasificaciones.length === 1 ? "clasificación" : "clasificaciones"} (una por cada peligro
          evaluado en cada centro poblado).
        </div>
      </section>

      {/* --- Frecuencia de emergencias -------------------------------------------------- */}
      {frecuencia && frecuencia.total > 0 && (
        <section className="mt-4 evitar-corte">
          <h2 className="font-display font-semibold text-mountain-900 text-sm mb-1">
            Emergencias registradas
            {frecuencia.rango_fecha ? ` (${frecuencia.rango_fecha})` : ""}
          </h2>
          {!frecuencia.desglose_disponible && (
            <p className="text-[10px] text-earth-700 mb-1">
              La fuente declara estos totales pero no los desagrega por tipo de evento.
            </p>
          )}
          {/* table-fixed: sin él la columna de eventos empuja el total fuera de la caja. */}
          <table className="w-full table-fixed text-[11px] border-collapse">
            <thead>
              <tr className="bg-mountain-100">
                <th className="w-2/12 border border-ink-300/50 px-2 py-1 text-left font-medium">
                  Categoría
                </th>
                <th className="border border-ink-300/50 px-2 py-1 text-left font-medium">
                  Eventos
                </th>
                <th className="w-[8%] border border-ink-300/50 px-2 py-1 text-right font-medium">
                  Total
                </th>
              </tr>
            </thead>
            <tbody>
              {frecuencia.categorias
                .filter((c) => c.total > 0)
                .map((c) => (
                  <tr key={c.slug}>
                    <td className="border border-ink-300/50 px-2 py-1">{c.categoria}</td>
                    <td className="border border-ink-300/50 px-2 py-1">
                      {c.eventos.length
                        ? c.eventos.map((e) => `${e.evento} (${e.conteo})`).join(", ")
                        : "—"}
                    </td>
                    <td className="border border-ink-300/50 px-2 py-1 text-right font-mono">
                      {formatNumber(c.total)}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </section>
      )}

      {/* --- Tabla de centros poblados -------------------------------------------------- */}
      <section className="mt-4">
        <h2 className="font-display font-semibold text-mountain-900 text-sm mb-1">
          Centros poblados con clasificación de peligro ({formatNumber(totalClasificados)})
        </h2>
        {totalClasificados === 0 ? (
          <p className="text-[11px] text-ink-600">
            Ningún centro poblado del ámbito cuenta con clasificación para los filtros aplicados.
          </p>
        ) : (
          <table className="w-full table-fixed text-[10px] border-collapse">
            <thead>
              <tr className="bg-mountain-100">
                <th className="w-[20%] border border-ink-300/50 px-1.5 py-1 text-left font-medium">
                  Centro poblado
                </th>
                <th className="w-[13%] border border-ink-300/50 px-1.5 py-1 text-left font-medium">
                  Categoría
                </th>
                <th className="w-[9%] border border-ink-300/50 px-1.5 py-1 text-right font-medium">
                  Población
                </th>
                <th className="w-[9%] border border-ink-300/50 px-1.5 py-1 text-right font-medium">
                  Altitud
                </th>
                <th className="border border-ink-300/50 px-1.5 py-1 text-left font-medium">
                  Peligros clasificados
                </th>
              </tr>
            </thead>
            <tbody>
              {filas.map((f) => (
                <tr key={f.ccpp.codigo}>
                  <td className="border border-ink-300/50 px-1.5 py-1">{f.ccpp.nombre}</td>
                  <td className="border border-ink-300/50 px-1.5 py-1">
                    {f.ccpp.categoria || "—"}
                  </td>
                  <td className="border border-ink-300/50 px-1.5 py-1 text-right font-mono">
                    {f.ccpp.poblacion != null ? formatNumber(f.ccpp.poblacion) : "—"}
                  </td>
                  <td className="border border-ink-300/50 px-1.5 py-1 text-right font-mono">
                    {f.ccpp.altitud != null ? `${formatNumber(f.ccpp.altitud)} m` : "—"}
                  </td>
                  <td className="border border-ink-300/50 px-1.5 py-1">
                    {f.peligros.map((p, i) => (
                      <span key={p.peligro}>
                        {i > 0 ? "; " : ""}
                        <span
                          className="inline-block w-1.5 h-1.5 rounded-full align-middle mr-1"
                          style={{ backgroundColor: NIVEL_COLOR[p.nivel] }}
                        />
                        {p.peligro}: {NIVEL_LABEL[p.nivel]}
                      </span>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* --- Fuentes y firma ------------------------------------------------------------ */}
      <div className="mt-6 pt-3 border-t border-ink-300/50 text-[10px] text-ink-600 evitar-corte">
        <p>
          <strong>Fuentes.</strong> Niveles de peligro y registro de emergencias:{" "}
          {fuentes.length ? fuentes.join(", ") : "SIGRID-CENEPRED"}. Padrón de centros poblados:
          INEI. Los enlaces a los estudios de respaldo por centro poblado están disponibles en el
          visor en línea del Observatorio.
        </p>
        <p className="mt-2">
          <strong>PREDES — Centro de Estudios y Prevención de Desastres.</strong> Observatorio
          Kallpachakuy: plataforma pública de información, monitoreo y gestión del conocimiento
          sobre la Gestión del Riesgo de Desastres y la Adaptación al Cambio Climático en la región
          Cusco. Iniciativa desarrollada en el marco de los proyectos financiados por Pan para el
          Mundo (Brot für die Welt) en comunidades altoandinas de Cusco.
        </p>
        <p className="mt-2">
          Documento generado automáticamente desde el Observatorio Kallpachakuy el {fecha} a las{" "}
          {hora} h. Refleja el estado de la base de datos en esa fecha.
        </p>
      </div>
    </div>
  );
}

function Dato({ etiqueta, children }: { etiqueta: string; children: React.ReactNode }) {
  return (
    <tr>
      <th className="text-left font-medium text-ink-600 align-top pr-3 py-0.5 whitespace-nowrap w-32">
        {etiqueta}
      </th>
      <td className="py-0.5">{children}</td>
    </tr>
  );
}

type FilaReporte = {
  ccpp: CentroPoblado;
  peligros: Array<{ peligro: string; nivel: Nivel }>;
  nivelMax: Nivel;
};

/** Agrupa las clasificaciones por centro poblado y ordena por gravedad. */
function agruparPorCentroPoblado(
  clasificaciones: ClasificacionPeligro[],
  porCodigo: Map<string, CentroPoblado>
): FilaReporte[] {
  const mapa = new Map<string, FilaReporte>();

  for (const c of clasificaciones) {
    const ccpp = porCodigo.get(c.codigo_ccpp);
    if (!ccpp) continue;
    let fila = mapa.get(c.codigo_ccpp);
    if (!fila) {
      fila = { ccpp, peligros: [], nivelMax: c.nivel };
      mapa.set(c.codigo_ccpp, fila);
    }
    fila.peligros.push({ peligro: c.peligro, nivel: c.nivel });
    if (c.nivel > fila.nivelMax) fila.nivelMax = c.nivel;
  }

  for (const fila of mapa.values()) {
    fila.peligros.sort((a, b) => b.nivel - a.nivel || a.peligro.localeCompare(b.peligro, "es"));
  }

  return [...mapa.values()].sort(
    (a, b) => b.nivelMax - a.nivelMax || a.ccpp.nombre.localeCompare(b.ccpp.nombre, "es")
  );
}

/** El reporte es un documento formal: "1 centros poblados cuentan" no puede salir impreso. */
function plural(n: number, singular: string, plural: string): string {
  return n === 1 ? singular : plural;
}

function eventoMasFrecuente(f: FrecuenciaDistrito): string {
  const todos = f.categorias.flatMap((c) => c.eventos);
  if (!todos.length) return "—";
  const top = todos.reduce((a, b) => (b.conteo > a.conteo ? b : a));
  return `${top.evento.toLowerCase()} (${top.conteo} registros)`;
}
