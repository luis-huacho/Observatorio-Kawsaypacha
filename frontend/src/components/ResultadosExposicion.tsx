import { ChevronRight } from "lucide-react";
import { iconoDe } from "@/lib/iconosPeligro";
import { NIVEL_COLOR, NIVEL_LABEL, formatNumber } from "@/lib/semaforo";
import type { Nivel, ResumenPeligros, TipoPeligroApi } from "@/lib/types";

type Props = {
  cifras: ResumenPeligros | null;
  tipos: TipoPeligroApi[];
  /** Total de centros poblados clasificados que devuelve la tabla, con los mismos filtros. */
  totalClasificados: number;
  cargando: boolean;
  /** Deja marcado solo ese peligro y lleva el foco a la relación de centros poblados. */
  onVerRelacion: (slug: string) => void;
};

const NIVELES: Nivel[] = [4, 3, 2, 1];

/**
 * Resultados de la consulta, por tipo de exposición.
 *
 * Vive en la columna principal y no en el panel de filtros. Cuando estaba dentro del `aside`,
 * debajo de los controles, se leía como una leyenda del mapa en vez de como la respuesta a lo
 * que el usuario acababa de preguntar.
 *
 * Cada fila cuenta **centros poblados** sin ambigüedad: la base impide dos clasificaciones del
 * mismo peligro en un mismo centro poblado, así que dentro de un tipo «clasificaciones» y
 * «centros poblados» son la misma cifra. Lo que no se puede leer como centros poblados es la
 * **suma** de la columna —ahí un mismo lugar aparece una vez por peligro evaluado—, y por eso
 * el pie declara las dos unidades en lugar de rematar la tabla con un total a secas.
 */
export default function ResultadosExposicion({
  cifras,
  tipos,
  totalClasificados,
  cargando,
  onVerRelacion,
}: Props) {
  const filas = cifras?.por_peligro ?? [];
  const iconoPorSlug = new Map(tipos.map((t) => [t.slug, t.icono]));
  const totalClasificaciones = filas.reduce((total, f) => total + f.centros_poblados, 0);
  const mayor = Math.max(1, ...filas.map((f) => f.centros_poblados));

  return (
    <section className="card p-5 mb-4" aria-labelledby="titulo-resultados">
      <div className="flex flex-wrap items-baseline justify-between gap-2 mb-3">
        <h2 id="titulo-resultados" className="font-display font-semibold text-mountain-900">
          Resultados
        </h2>
        <span className="text-xs text-ink-600">
          Centros poblados expuestos, por tipo de peligro
        </span>
      </div>

      {cargando ? (
        <p className="text-sm text-ink-600 py-6 text-center">Calculando…</p>
      ) : filas.length === 0 ? (
        <p className="text-sm text-ink-600 py-6 text-center">
          Ningún tipo de peligro seleccionado.
        </p>
      ) : (
        <>
          <div className="-mx-2 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-ink-600 uppercase tracking-wide">
                <tr>
                  <th className="text-left px-2 py-2">Tipo de exposición</th>
                  <th className="text-right px-2 py-2 whitespace-nowrap">Centros poblados</th>
                  <th className="text-left px-2 py-2 hidden sm:table-cell">Por nivel</th>
                  <th className="px-2 py-2">
                    <span className="sr-only">Ver la relación</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {filas.map((fila) => {
                  const Icono = iconoDe(iconoPorSlug.get(fila.slug));
                  return (
                    <tr
                      key={fila.slug}
                      className="border-t border-ink-300/20 hover:bg-mountain-100/40"
                    >
                      <td className="px-2 py-2">
                        <span className="flex items-center gap-2">
                          <Icono className="w-4 h-4 text-mountain-700 shrink-0" aria-hidden />
                          <span className="text-ink-900">{fila.peligro}</span>
                        </span>
                      </td>
                      <td className="px-2 py-2 text-right font-mono font-semibold">
                        {formatNumber(fila.centros_poblados)}
                      </td>
                      <td className="px-2 py-2 hidden sm:table-cell">
                        <span
                          className="flex h-3 rounded-sm overflow-hidden bg-mountain-100"
                          style={{ width: `${(fila.centros_poblados / mayor) * 100}%` }}
                          title={NIVELES.map(
                            (n) => `${NIVEL_LABEL[n]}: ${formatNumber(fila.niveles[String(n) as "1"])}`
                          ).join(" · ")}
                        >
                          {NIVELES.map((n) => {
                            const valor = fila.niveles[String(n) as "1"];
                            if (!valor) return null;
                            return (
                              <span
                                key={n}
                                style={{
                                  backgroundColor: NIVEL_COLOR[n],
                                  width: `${(valor / Math.max(1, fila.centros_poblados)) * 100}%`,
                                }}
                              />
                            );
                          })}
                        </span>
                      </td>
                      <td className="px-2 py-2 text-right">
                        <button
                          type="button"
                          onClick={() => onVerRelacion(fila.slug)}
                          className="inline-flex items-center gap-0.5 text-xs text-mountain-700 hover:text-mountain-900 whitespace-nowrap"
                        >
                          Ver centros poblados
                          <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Las dos unidades, reconciliadas (ADR-A16). El mapa rotula sus grupos con la
              segunda, así que sumar los círculos tiene que dar esta cifra y no la de la tabla. */}
          <p className="text-xs text-ink-600 mt-3 pt-3 border-t border-ink-300/30">
            <strong className="font-mono">{formatNumber(totalClasificados)}</strong> centros
            poblados distintos con clasificación
            <span
              className="text-ink-300"
              title="Un centro poblado aporta una clasificación por cada peligro evaluado; es la cifra que el mapa muestra dentro de cada grupo."
            >
              {" · "}
              <span className="font-mono">{formatNumber(totalClasificaciones)}</span> peligros
              clasificados
            </span>
            {cifras && cifras.por_ccpp.sin_clasificar > 0 && (
              <span className="text-ink-300">
                {" · "}
                <span className="font-mono">
                  {formatNumber(cifras.por_ccpp.sin_clasificar)}
                </span>{" "}
                sin clasificación
              </span>
            )}
          </p>
        </>
      )}
    </section>
  );
}
