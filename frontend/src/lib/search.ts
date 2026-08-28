/**
 * Búsqueda: Meilisearch directo, con fallback a DRF (spec 04).
 *
 * El navegador consulta Meilisearch con la **llave search-only**, sin pasar por Django: es
 * segura por diseño (solo búsqueda, solo los índices públicos) y así las facetas y la
 * tolerancia a errores de tecleo no requieren código de servidor.
 *
 * Cuando Meilisearch no responde —está reindexando, o caído— se cae a `/api/buscar/`, que
 * devuelve la misma forma sin facetas ni typo-tolerance. Que el fallback exista es una decisión
 * de producto: el buscador es la puerta de entrada al contenido, y un sitio que responde «no se
 * pudo buscar» se lee como roto, no como degradado.
 *
 * No se usa el SDK de Meilisearch: son dos endpoints y `fetch` basta (spec 04).
 */
import { apiFetch } from "./api";

const SEARCH_URL: string = import.meta.env.VITE_SEARCH_URL ?? "/search";
const SEARCH_KEY: string = import.meta.env.VITE_MEILI_SEARCH_KEY ?? "";

/** Índices de contenido de la búsqueda global. Los CCPP van aparte (autocompletado del mapa). */
export const INDICES_CONTENIDO = [
  { indice: "medidas", etiqueta: "Buenas prácticas" },
  { indice: "normativa", etiqueta: "Normativa" },
  { indice: "noticias", etiqueta: "Noticias" },
  { indice: "documentos", etiqueta: "Documentos" },
  { indice: "videos", etiqueta: "Videos" },
  { indice: "eventos", etiqueta: "Eventos" },
] as const;

export type ResultadoBusqueda = {
  titulo: string;
  detalle: string;
  extra: string;
  url: string;
};

export type GrupoResultados = {
  indice: string;
  etiqueta: string;
  resultados: ResultadoBusqueda[];
  total: number;
};

export type RespuestaBusqueda = {
  q: string;
  grupos: GrupoResultados[];
  total: number;
  /** `meili` o `drf`: la UI avisa cuando está en modo degradado. */
  motor: "meili" | "drf";
};

function cabeceras(): HeadersInit {
  return {
    "Content-Type": "application/json",
    ...(SEARCH_KEY ? { Authorization: `Bearer ${SEARCH_KEY}` } : {}),
  };
}

/** Meilisearch está configurado y responde. Se comprueba una vez por sesión. */
let disponibilidad: Promise<boolean> | null = null;

/** El aviso de llave rechazada se da una vez por sesión, no en cada búsqueda. */
let llaveDenunciada = false;

/**
 * Meilisearch rechazó la llave. **No es lo mismo que estar caído** y hay que distinguirlo: el
 * servicio responde, los índices están, y sin embargo el sitio se degrada en tres sitios a la vez
 * —búsqueda global, conteos de las facetas de `/medidas` y autocompletado de lugares del visor— y
 * solo el primero lo dice en pantalla.
 *
 * Pasa cuando la llave que quedó horneada en el bundle ya no existe en Meilisearch. Las `VITE_*` se
 * hornean en el build, así que la salida es reconstruir el frontend con la llave que imprime
 * `manage.py meili_setup`, no reiniciar nada. Se escribe en consola porque es la única pista que
 * puede seguir quien opera el sitio: `/api/buscar/estado/` y `/search/health` responden que todo
 * está bien —el backend consulta con la master key y `health` no pide credencial—.
 */
function denunciarLlave(estado: number): void {
  if (llaveDenunciada) return;
  llaveDenunciada = true;
  console.error(
    `[buscador] Meilisearch rechazó la llave de búsqueda (${estado}). El sitio queda en modo ` +
      "básico y las facetas se quedan sin conteos. La VITE_MEILI_SEARCH_KEY con la que se " +
      "construyó este bundle ya no existe: copiar la de `manage.py meili_setup` a los dos .env y " +
      "reconstruir el frontend.",
  );
}

/** Una respuesta de Meilisearch que falló por credencial, no por estar caído. */
function esLlaveRechazada(estado: number): boolean {
  return estado === 401 || estado === 403;
}

export function meiliDisponible(): Promise<boolean> {
  if (!SEARCH_KEY) return Promise.resolve(false);
  if (disponibilidad === null) {
    disponibilidad = fetch(`${SEARCH_URL}/health`)
      .then((r) => r.ok)
      .catch(() => false);
  }
  return disponibilidad;
}

/** Extrae de un documento de Meili los cuatro campos que pinta la lista de resultados. */
function aResultado(indice: string, doc: Record<string, unknown>): ResultadoBusqueda {
  const texto = (clave: string) => (doc[clave] == null ? "" : String(doc[clave]));
  const detallePorIndice: Record<string, string> = {
    medidas: texto("resumen_corto"),
    normativa: texto("resumen"),
    noticias: texto("bajada"),
    documentos: texto("resumen"),
    videos: texto("descripcion"),
    eventos: texto("descripcion"),
    ccpp: [texto("distrito"), texto("provincia")].filter(Boolean).join(", "),
  };
  const extraPorIndice: Record<string, string> = {
    medidas: texto("peligro"),
    normativa: [texto("tipo"), texto("anio")].filter(Boolean).join(" · "),
    noticias: texto("tipo"),
    documentos: texto("categoria"),
    videos: texto("tema"),
    eventos: texto("modalidad"),
    ccpp: texto("categoria"),
  };
  return {
    titulo: texto("titulo") || texto("nombre"),
    detalle: (detallePorIndice[indice] ?? "").slice(0, 180),
    extra: extraPorIndice[indice] ?? "",
    url: texto("url"),
  };
}

/** Búsqueda global federada. Un solo `multi-search` para los seis índices. */
export async function buscarGlobal(q: string, limite = 8): Promise<RespuestaBusqueda> {
  const consulta = q.trim();
  if (!consulta) return { q: "", grupos: [], total: 0, motor: "meili" };

  if (await meiliDisponible()) {
    try {
      const respuesta = await fetch(`${SEARCH_URL}/multi-search`, {
        method: "POST",
        headers: cabeceras(),
        body: JSON.stringify({
          queries: INDICES_CONTENIDO.map(({ indice }) => ({
            indexUid: indice,
            q: consulta,
            limit: limite,
          })),
        }),
      });
      if (!respuesta.ok) {
        if (esLlaveRechazada(respuesta.status)) denunciarLlave(respuesta.status);
        throw new Error(`multi-search ${respuesta.status}`);
      }
      const cuerpo = (await respuesta.json()) as {
        results: { indexUid: string; hits: Record<string, unknown>[]; estimatedTotalHits: number }[];
      };
      const grupos = cuerpo.results
        .map((r) => ({
          indice: r.indexUid,
          etiqueta:
            INDICES_CONTENIDO.find((i) => i.indice === r.indexUid)?.etiqueta ?? r.indexUid,
          resultados: r.hits.map((h) => aResultado(r.indexUid, h)),
          total: r.estimatedTotalHits,
        }))
        .filter((g) => g.resultados.length > 0);
      return {
        q: consulta,
        grupos,
        total: grupos.reduce((s, g) => s + g.total, 0),
        motor: "meili",
      };
    } catch {
      // Se cae al fallback en vez de propagar: para quien busca, el detalle de por qué falló
      // Meilisearch es irrelevante mientras haya resultados.
      disponibilidad = Promise.resolve(false);
    }
  }

  return apiFetch<RespuestaBusqueda>("/buscar/", { q: consulta, limite });
}

/**
 * Autocompletado de lugares para el buscador del mapa y el GeoSelector.
 *
 * Sin fallback a `/api/buscar/`: si Meilisearch no está, el visor sigue usando el padrón que ya
 * tiene cargado en memoria para el mapa, que es más rápido que una ida y vuelta al servidor.
 */
export type Lugar = {
  codigo: string;
  nombre: string;
  categoria: string;
  distrito: string;
  provincia: string;
  ubigeo_distrito: string;
  nivel_max: number;
  lat: number | null;
  lon: number | null;
};

export async function buscarLugares(q: string, limite = 8): Promise<Lugar[]> {
  const consulta = q.trim();
  if (!consulta || !(await meiliDisponible())) return [];
  try {
    const respuesta = await fetch(`${SEARCH_URL}/indexes/ccpp/search`, {
      method: "POST",
      headers: cabeceras(),
      body: JSON.stringify({ q: consulta, limit: limite }),
    });
    if (!respuesta.ok) {
      // Aquí la degradación es invisible —el visor sigue usando el padrón que tiene en memoria—,
      // así que la consola es el único aviso.
      if (esLlaveRechazada(respuesta.status)) denunciarLlave(respuesta.status);
      return [];
    }
    const cuerpo = (await respuesta.json()) as { hits: Lugar[] };
    return cuerpo.hits ?? [];
  } catch {
    return [];
  }
}

/** Facetas de un índice, con sus conteos. Alimenta los filtros de `/medidas`. */
export type Facetas = Record<string, Record<string, number>>;

export async function facetasDe(
  indice: string,
  campos: string[],
  filtros: string[] = []
): Promise<Facetas> {
  if (!(await meiliDisponible())) return {};
  try {
    const respuesta = await fetch(`${SEARCH_URL}/indexes/${indice}/search`, {
      method: "POST",
      headers: cabeceras(),
      body: JSON.stringify({ q: "", facets: campos, filter: filtros, limit: 0 }),
    });
    if (!respuesta.ok) {
      // Los filtros se quedan sin conteos y no hay nada en pantalla que lo explique.
      if (esLlaveRechazada(respuesta.status)) denunciarLlave(respuesta.status);
      return {};
    }
    const cuerpo = (await respuesta.json()) as { facetDistribution?: Facetas };
    return cuerpo.facetDistribution ?? {};
  } catch {
    return {};
  }
}
