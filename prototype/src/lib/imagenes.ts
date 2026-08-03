import type { Noticia } from "@/lib/types";

/**
 * Tipos de contenido que tienen imagen por defecto. Coinciden con los nombres de archivo en
 * `public/img/default/`.
 */
export type TipoConPortada = Noticia["tipo"] | "norma";

const PIE_POR_DEFECTO = "Ilustración del Observatorio Kallpachakuy";

/**
 * Resuelve la portada de una publicación.
 *
 * Mientras PREDES no suba una imagen, el contenido se muestra con la ilustración institucional de
 * su tipo. Es el camino que se ve por defecto —de ahí el nombre— y por eso los mocks lo dejan a
 * `null` en vez de fijar una imagen por pieza.
 */
export function portada(tipo: TipoConPortada, propia: string | null): string {
  return propia ?? `/img/default/${tipo}.svg`;
}

/**
 * Pie de imagen. El genérico deja claro que es una ilustración y no una fotografía de un hecho:
 * cuando el editor suba una foto real pondrá el suyo.
 */
export function pieDeImagen(propio: string | null): string {
  return propio ?? PIE_POR_DEFECTO;
}
