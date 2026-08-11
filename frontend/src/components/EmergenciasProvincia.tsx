import { useMemo } from "react";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CalendarRange, Info, TriangleAlert } from "lucide-react";
import { formatNumber } from "@/lib/semaforo";
import type { FrecuenciaProvincia } from "@/lib/types";
import EmptyState from "@/components/EmptyState";
import SourceLink from "@/components/SourceLink";

/**
 * Color por familia de evento. Son tokens del diseño, escritos en hex porque recharts necesita
 * el valor y no la clase de Tailwind: `earth-700`, `level-4`, `sky-500`, `level-3`.
 */
const COLOR_FAMILIA: Record<string, string> = {
  geodinamica_externa: "#7A4A28",
  geodinamica_interna: "#970A00",
  meteorologico: "#0095A4",
  inducido_humano: "#F57C15",
};
const COLOR_POR_DEFECTO = "#555555";

type Props = {
  datos: FrecuenciaProvincia | null;
  /** Nombre de la provincia elegida en los filtros; vacío = ninguna. */
  provincia: string;
  cargando: boolean;
  /**
   * `"evento"` = Huayco, Deslizamiento… (21). `"tipo"` = Geodinámica externa, Meteorológicos…
   * (4). Las palabras son las de la pantalla, que van al revés que los modelos del backend.
   */
  agrupacion: "evento" | "tipo";
};

/**
 * Emergencias registradas en una provincia.
 *
 * Es el **otro eje** de la fuente: cuenta lo que ya ocurrió, por distrito y con su propia
 * taxonomía de 21 tipos de evento, frente a los 9 peligros de exposición del resto de la
 * página. Por eso vive en su propio bloque, se enciende aparte y **no responde a los filtros
 * de peligro ni de nivel**: no hay forma de convertir una taxonomía en la otra —`INCENDIO
 * FORESTAL` es «inducido por acción humana» aquí y «meteorológico» allí—, y presentarlas juntas
 * hacía que la pantalla pareciera mal calculada.
 */
export default function EmergenciasProvincia({ datos, provincia, cargando, agrupacion }: Props) {
  const barras = useMemo(() => {
    if (!datos) return [];
    if (agrupacion === "tipo") {
      return datos.familias.map((f) => ({
        nombre: f.categoria,
        conteo: f.conteo,
        familia: f.categoria,
        color: COLOR_FAMILIA[f.slug] ?? COLOR_POR_DEFECTO,
      }));
    }
    return datos.eventos.map((e) => ({
      nombre: e.evento,
      conteo: e.conteo,
      familia: e.categoria,
      color: COLOR_FAMILIA[e.categoria_slug] ?? COLOR_POR_DEFECTO,
    }));
  }, [datos, agrupacion]);

  // El alto crece con el número de barras. Con uno fijo, las 20 de una provincia grande salen
  // aplastadas y las etiquetas del eje dejan de leerse.
  const alto = Math.max(180, barras.length * 26 + 40);

  if (!provincia) {
    return (
      <Marco>
        <p className="text-sm text-ink-600">
          Elige una provincia en los filtros para ver las emergencias registradas en ella.
        </p>
      </Marco>
    );
  }

  if (cargando) {
    return (
      <Marco provincia={provincia}>
        <p className="text-sm text-ink-600 py-6 text-center">Calculando…</p>
      </Marco>
    );
  }

  if (!datos || datos.total === 0) {
    return (
      <Marco provincia={provincia}>
        <EmptyState
          title="Sin emergencias registradas"
          message={`La fuente no incluye emergencias para ningún distrito de ${provincia}. Ausencia de registro no es ausencia de emergencias.`}
        />
      </Marco>
    );
  }

  const cobertura = datos.distritos_con_registro < datos.distritos_en_provincia;
  const faltanEventos = agrupacion === "evento" && datos.total_sin_desglose > 0;

  return (
    <Marco provincia={provincia}>
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 mb-1">
        <span className="font-mono text-2xl font-semibold text-mountain-900">
          {formatNumber(agrupacion === "tipo" ? datos.total : datos.total - datos.total_sin_desglose)}
        </span>
        <span className="text-sm text-ink-600">emergencias registradas</span>
        {datos.periodo && (
          <span className="inline-flex items-center gap-1 text-xs text-ink-600">
            <CalendarRange className="w-3.5 h-3.5" />
            {datos.periodo}
            {datos.periodos_distintos > 1 && (
              <span
                className="text-ink-300"
                title="Cada distrito trae su propio periodo de observación; este es el rango que los abarca a todos, no una ventana común."
              >
                {" "}
                ({datos.periodos_distintos} periodos distintos)
              </span>
            )}
          </span>
        )}
      </div>

      {/* La cobertura, que es lo que hace legible la cifra. Sin ella una provincia con un solo
          distrito registrado parece la más tranquila de la región. */}
      <p className={`text-xs mb-3 ${cobertura ? "text-earth-700" : "text-ink-600"}`}>
        {cobertura && <TriangleAlert className="inline w-3.5 h-3.5 mr-1 -mt-0.5" />}
        {formatNumber(datos.distritos_con_registro)} de{" "}
        {formatNumber(datos.distritos_en_provincia)} distritos con registro
        {cobertura && " — la cifra subestima lo ocurrido en la provincia"}
      </p>

      {faltanEventos && (
        <p className="flex items-start gap-2 text-xs text-ink-600 bg-earth-200/40 border border-earth-500/30 rounded p-2 mb-3">
          <Info className="w-4 h-4 shrink-0 mt-px" />
          <span>
            {formatNumber(datos.total_sin_desglose)} emergencias de{" "}
            {datos.sin_desglose.map((d) => d.distrito).join(", ")} no aparecen aquí: la fuente
            las declara por tipo de evento pero no dice de qué evento fueron. Agrupando por tipo
            de evento sí se cuentan.
          </span>
        </p>
      )}

      <div style={{ height: alto }} className="-ml-2">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={barras}
            layout="vertical"
            margin={{ top: 4, right: 16, bottom: 4, left: 8 }}
          >
            <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
            <YAxis
              type="category"
              dataKey="nombre"
              width={150}
              interval={0}
              tick={{ fontSize: 11 }}
            />
            <Tooltip
              cursor={{ fill: "rgba(0,0,0,0.04)" }}
              formatter={(v: number, _n, item) => [
                `${formatNumber(v)} emergencias`,
                item?.payload?.familia ?? "",
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

      {agrupacion === "evento" && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3 pt-3 border-t border-ink-300/30">
          {datos.familias.map((f) => (
            <span key={f.slug} className="inline-flex items-center gap-1.5 text-xs text-ink-600">
              <span
                className="w-2.5 h-2.5 rounded-sm"
                style={{ backgroundColor: COLOR_FAMILIA[f.slug] ?? COLOR_POR_DEFECTO }}
              />
              {f.categoria}
            </span>
          ))}
        </div>
      )}

      {datos.fuente && <SourceLink fuente={datos.fuente} url={datos.fuente_url} />}
    </Marco>
  );
}

function Marco({ provincia, children }: { provincia?: string; children: React.ReactNode }) {
  return (
    <section className="card mt-4 p-5" aria-labelledby="titulo-emergencias">
      <h2 id="titulo-emergencias" className="font-display font-semibold text-mountain-900">
        Emergencias registradas{provincia ? ` — provincia de ${provincia}` : ""}
      </h2>
      <p className="text-xs text-ink-600 mb-3">
        Ocurrencia histórica por distrito, según SIGRID-CENEPRED. Es un eje distinto de la
        exposición: no lo afectan los filtros de tipo de peligro ni de nivel.
      </p>
      {children}
    </section>
  );
}
