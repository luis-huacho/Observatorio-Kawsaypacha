/**
 * El mapa base «Claro» de CARTO, en un solo sitio.
 *
 * Vive en un módulo compartido y no en cada componente **porque desde que CARTO exige llave, la
 * URL lleva una credencial dentro**. Estaba escrita dos veces carácter por carácter —la entrada
 * `claro` del visor y el fondo de la ficha del centro poblado—, y duplicar una credencial es
 * duplicar el sitio donde se olvida de actualizarla. Mismo motivo que llevó `pmtiles.ts` a `lib/`.
 *
 * **El estilo es `light_all` y se queda así.** CARTO recomienda `rastertiles/voyager` en su aviso
 * de la llave, pero eso cambiaría el diseño: `voyager` va a color y `light_all` es el gris casi
 * liso sobre el que está construido el visor —es el fondo que mejor deja leer el semáforo (spec
 * 05), y `MapaPeligros` afina el halo de los puntos a 0.5 px **solo** sobre este fondo justamente
 * porque es liso—. Comprobado que `light_all` con la llave responde 200 y sin marca de agua: no
 * hay ninguna razón para cambiar de estilo.
 */

/**
 * Sin llave las URL quedan **exactamente como estaban**, no con un `?key=` colgando: el mapa sigue
 * pintando, con la marca de agua de CARTO encima. Es la degradación que mantiene `npm run dev`
 * usable para quien no tenga la llave a mano.
 *
 * Va horneada en el bundle, así que es pública por diseño — como `VITE_MEILI_SEARCH_KEY`. Cambiarla
 * exige **reconstruir** el frontend, no reiniciarlo.
 */
const LLAVE: string = import.meta.env.VITE_CARTO_KEY ?? "";
const SUFIJO = LLAVE ? `?key=${LLAVE}` : "";

/** Los tres subdominios de siempre; los tres aceptan la llave. */
export const CARTO_CLARO = {
  tiles: ["a", "b", "c"].map(
    (s) => `https://${s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png${SUFIJO}`
  ),
  atribucion:
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
  maxzoom: 20,
};
