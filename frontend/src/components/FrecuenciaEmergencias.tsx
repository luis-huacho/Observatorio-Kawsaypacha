import { useMemo } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { AlertTriangle, CalendarRange } from "lucide-react";
import type { FrecuenciaDistrito } from "@/lib/types";
import { formatNumber } from "@/lib/semaforo";
import EmptyState from "@/components/EmptyState";
import SourceLink from "@/components/SourceLink";

/** Un color por categoría, tomado de la paleta institucional. */
const COLOR_CATEGORIA: Record<string, string> = {
  geodinamica_externa: "#7A4A28",
  geodinamica_interna: "#970A00",
  meteorologico: "#0095A4",
  inducido_humano: "#F57C15",
};

type Props = {
  /**
   * Datos del distrito seleccionado, o `null`.
   *
   * `null` cubre dos situaciones que la UI distingue más abajo: que no haya distrito elegido, y
   * que el distrito **no tenga fila** en el Excel de la fuente (hoy solo Acomayo, que el API
   * responde con 404). Son estados vacíos distintos y el segundo es un dato en sí mismo.
   */
  frecuencia: FrecuenciaDistrito | null;
  /** Nombre del distrito seleccionado en el GeoSelector; vacío = ninguno. */
  distrito: string;
};

export default function FrecuenciaEmergencias({ frecuencia, distrito }: Props) {
  const datos = frecuencia ?? undefined;

  const barras = useMemo(() => {
    if (!datos) return [];
    return datos.categorias
      .flatMap((c) =>
        c.eventos.map((e) => ({
          nombre: e.evento,
          conteo: e.conteo,
          categoria: c.categoria,
          color: COLOR_CATEGORIA[c.slug] ?? "#555555",
        }))
      )
      .sort((a, b) => b.conteo - a.conteo);
  }, [datos]);

  if (!distrito) {
    return (
      <div className="card mt-4 p-5">
        <Encabezado />
        <p className="text-sm text-ink-600">
          Elige una provincia y un distrito en los filtros para ver su historial de emergencias.
        </p>
      </div>
    );
  }

  // 111 de los 112 distritos tienen fila; Acomayo no aparece en el Excel de la fuente.
  if (!datos) {
    return (
      <div className="card mt-4 p-5">
        <Encabezado />
        <EmptyState
          title="Distrito sin registro"
          message={`El registro de emergencias de SIGRID-CENEPRED no incluye una fila para ${distrito}.`}
        />
      </div>
    );
  }

  if (datos.total === 0) {
    return (
      <div className="card mt-4 p-5">
        <Encabezado />
        <EmptyState
          title="Sin emergencias registradas"
          message={`No hay emergencias registradas para ${datos.distrito} en el periodo consultado.`}
        />
      </div>
    );
  }

  return (
    <div className="card mt-4 p-5">
      <Encabezado />

      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 mb-4">
        <div>
          <span className="font-mono text-2xl font-semibold text-mountain-900">
            {formatNumber(datos.total)}
          </span>
          <span className="text-sm text-ink-600 ml-2">
            emergencias en {datos.distrito}
          </span>
        </div>
        {datos.rango_fecha && (
          <span className="inline-flex items-center gap-1 text-xs text-ink-600">
            <CalendarRange className="w-3.5 h-3.5" />
            Periodo {datos.rango_fecha}
          </span>
        )}
      </div>

      {datos.desglose_disponible ? (
        <>
          <div className="h-[280px] -ml-2">
            <ResponsiveContainer>
              <BarChart
                data={barras}
                layout="vertical"
                margin={{ top: 4, right: 16, bottom: 4, left: 8 }}
              >
                <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} />
                <YAxis
                  type="category"
                  dataKey="nombre"
                  width={130}
                  tick={{ fontSize: 11 }}
                  interval={0}
                />
                <Tooltip
                  cursor={{ fill: "rgba(0,0,0,0.04)" }}
                  formatter={(v: number, _n, item) => [
                    `${formatNumber(v)} emergencias`,
                    item?.payload?.categoria ?? "",
                  ]}
                />
                <Bar dataKey="conteo" radius={[0, 3, 3, 0]}>
                  {barras.map((b) => (
                    <Cell key={b.nombre} fill={b.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3 pt-3 border-t border-ink-300/30">
            {datos.categorias
              .filter((c) => c.total > 0)
              .map((c) => (
                <span key={c.slug} className="inline-flex items-center gap-1.5 text-xs text-ink-600">
                  <span
                    className="w-2.5 h-2.5 rounded-sm"
                    style={{ backgroundColor: COLOR_CATEGORIA[c.slug] }}
                  />
                  {c.categoria}
                  <span className="font-mono font-semibold">{formatNumber(c.total)}</span>
                </span>
              ))}
          </div>
        </>
      ) : (
        <>
          {/* Caso del distrito de Cusco: la fuente da los subtotales pero no el detalle. */}
          <div className="flex items-start gap-2 rounded-lg bg-earth-200/40 border border-earth-500/30 p-3 mb-4">
            <AlertTriangle className="w-4 h-4 text-earth-700 shrink-0 mt-0.5" />
            <p className="text-xs text-ink-600">
              La fuente declara estos totales pero <strong>no los desagrega por tipo de evento</strong>,
              así que no es posible mostrar el detalle.
            </p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {datos.categorias.map((c) => (
              <div key={c.slug} className="rounded-lg border border-ink-300/30 p-3">
                <div className="flex items-center gap-1.5 text-xs text-ink-600 mb-1">
                  <span
                    className="w-2.5 h-2.5 rounded-sm"
                    style={{ backgroundColor: COLOR_CATEGORIA[c.slug] }}
                  />
                  {c.categoria}
                </div>
                <div className="font-mono text-xl font-semibold text-mountain-900">
                  {formatNumber(c.total)}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {datos.fuente && (
        <div className="mt-3">
          <SourceLink fuente={datos.fuente} url={datos.fuente_url} />
        </div>
      )}
    </div>
  );
}

function Encabezado() {
  return (
    <div className="mb-3">
      <h2 className="font-display font-semibold text-mountain-900">
        Frecuencia de emergencias
      </h2>
      <p className="text-xs text-ink-600 mt-0.5">
        Emergencias registradas por tipo de evento. Cada distrito tiene su propio periodo de
        observación, así que los totales no son comparables entre distritos sin considerarlo.
      </p>
    </div>
  );
}
