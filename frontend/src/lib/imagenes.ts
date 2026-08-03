/**
 * Portadas del contenido editorial.
 *
 * **La resolución ya no vive aquí.** En el prototipo este módulo elegía la ilustración por
 * defecto en el navegador; en la plataforma lo hace el serializer del API (spec 01/02), así que
 * `imagen_portada` llega siempre con una URL usable —la propia o la institucional del tipo de
 * contenido— y ningún cliente reimplementa la regla.
 *
 * Lo que queda son las dos piezas que el frontend sigue necesitando: el pie por defecto para
 * cuando el API no manda ninguno, y la ilustración de reserva por si un despliegue viejo
 * devolviera `null`.
 */

/** Ilustración de reserva. Solo se usa si el API devolviera una portada vacía. */
const RESERVA = "/img/default/foto-pendiente.svg";

/**
 * El pie genérico dice que es una ilustración a propósito: no debe hacer pasar el gráfico
 * institucional por una fotografía de un hecho real. Cuando el editor sube una foto suya, pone
 * su propio pie.
 */
export const PIE_POR_DEFECTO = "Ilustración del Observatorio Kallpachakuy";

export function portada(url: string | null | undefined): string {
  return url || RESERVA;
}

export function pieDeImagen(propio: string | null | undefined): string {
  return propio || PIE_POR_DEFECTO;
}
