/// <reference types="vite/client" />

/**
 * Las `VITE_*` del proyecto, declaradas para que `tsc` cace un nombre mal escrito.
 *
 * Sin esto Vite las tipa como `any` y `import.meta.env.VITE_CARTO_KEI` compila tan campante,
 * devuelve `undefined` y el fallo aparece como una marca de agua en el mapa o un buscador que no
 * busca. Todas son opcionales: el código repliega con `?? ""` y el sitio degrada en vez de romper.
 */
interface ImportMetaEnv {
  /** URL absoluta del API; vive en otro dominio (ADR-A14). */
  readonly VITE_API_URL?: string;
  /** Meilisearch, directo desde el navegador. */
  readonly VITE_SEARCH_URL?: string;
  /** Llave *search-only* de Meilisearch: pública por diseño. */
  readonly VITE_MEILI_SEARCH_KEY?: string;
  /** Llave de los mapas base ráster de CARTO. Sin ella las teselas salen con marca de agua. */
  readonly VITE_CARTO_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
