import type { InversionEjercicio } from "./types";

/**
 * Cómo se NOMBRA un ejercicio en pantalla.
 *
 * La ventana solo decía qué **no** era el dato («no comparable con el de un ejercicio
 * cerrado») y obligaba a deducir por descarte que el año que se está mirando es el corriente.
 * Aquí se decide una vez cómo se llama, para que el selector, la banda de aviso, la tendencia y
 * la ficha de la municipalidad no lo redacten cada una a su manera.
 *
 * La palabra «cerrado» no aparece a propósito: es jerga contable —año fiscal terminado y
 * liquidado— y define el dato por su contrario. Donde hace falta el término de comparación se
 * dice «un año completo» o «un año ya terminado».
 */

/** «junio de 2026» ⇒ «junio». Vacío si el ejercicio no tiene corte que nombrar. */
export function mesDelCorte({ corte_legible }: InversionEjercicio): string {
  return corte_legible.split(" de ")[0] || "";
}

/**
 * El estado del ejercicio en dos palabras, o `""` si el año está completo.
 *
 * `en_curso` y `es_parcial` no son lo mismo: un corte a junio de un año ya pasado es parcial sin
 * estar en curso, y el backend los distingue justo para que aquí no se llame «en curso» a algo
 * que ya terminó.
 */
export function estadoEjercicio(e: InversionEjercicio): string {
  if (e.en_curso) return "año fiscal en curso";
  if (e.es_parcial) return "datos parciales";
  return "";
}

/** La opción del desplegable: «2026 · en curso (a junio)». Un `AAAA-MM` crudo no lo lee nadie. */
export function etiquetaEjercicio(e: InversionEjercicio): string {
  if (!e.es_parcial) return String(e.anio);
  const estado = e.en_curso ? "en curso" : "parcial";
  const hasta = mesDelCorte(e);
  return `${e.anio} · ${estado}${hasta ? ` (a ${hasta})` : ""}`;
}

/** El pie de las tablas de tendencia, en el tablero y en la ficha de la municipalidad. */
export const PIE_EJERCICIO_PARCIAL =
  "* Ejercicio en curso o con corte parcial: el devengado no cubre el año completo, así que su " +
  "% de ejecución no se compara con el de un año ya terminado.";
