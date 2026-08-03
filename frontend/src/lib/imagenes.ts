import type { Noticia } from "@/lib/types";
import { PELIGROS } from "@/lib/types";

/**
 * Claves de imagen por defecto. Coinciden con los nombres de archivo en `public/img/default/`.
 * Las medidas usan `peligro-{slug}`, que resuelve `portadaMedida()`.
 */
export type TipoConPortada = Noticia["tipo"] | "norma" | "medida" | `peligro-${string}`;

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

/**
 * Clave de portada de una medida a partir del nombre de su peligro.
 *
 * La ilustración va por peligro y no por resultado porque es el eje con el que se explora la
 * sección. Si el nombre no casa con el catálogo —dato viejo o un peligro nuevo— cae en la
 * reserva `medida`, que es preferible a un 404 de imagen.
 */
export function claveMedida(nombrePeligro: string): TipoConPortada {
  const p = PELIGROS.find((x) => x.nombre === nombrePeligro);
  return p ? `peligro-${p.slug}` : "medida";
}
