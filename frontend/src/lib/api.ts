/**
 * Cliente del API del Observatorio.
 *
 * Mismo contrato que el `useJsonData` del prototipo —`{ status, data, error }`— para que la
 * migración cambie la URL de cada página y no su lógica. Es el **único punto de integración**
 * con el backend.
 *
 * El API vive en otro dominio (`obs.predes.org.pe`, ADR-A14), así que `VITE_API_URL` es una URL
 * absoluta y las peticiones son cross-origin. No se manda ningún credential: el API público es
 * de solo lectura y anónimo.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const API_URL: string = import.meta.env.VITE_API_URL ?? "/api";

export type Params = Record<string, string | number | boolean | undefined | null>;

export type Estado<T> =
  | { status: "loading"; data: null; error: null }
  | { status: "ok"; data: T; error: null }
  | { status: "error"; data: null; error: Error };

/** Respuesta paginada de DRF. */
export type Pagina<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

/**
 * Caché por URL, viva mientras dure la sesión de la SPA.
 *
 * Guarda la *promesa* y no el valor: si dos componentes piden lo mismo en el mismo render
 * —pasa en `/peligros`, donde la tabla y el mapa comparten filtros— se dispara una sola
 * petición en vez de dos idénticas.
 */
const cache = new Map<string, Promise<unknown>>();

export function construirUrl(ruta: string, params?: Params): string {
  const base = `${API_URL}${ruta.startsWith("/") ? ruta : `/${ruta}`}`;
  if (!params) return base;
  const qs = new URLSearchParams();
  // Las claves se ordenan para que dos llamadas con los mismos filtros en distinto orden
  // compartan entrada de caché en vez de duplicar la petición.
  for (const clave of Object.keys(params).sort()) {
    const valor = params[clave];
    if (valor === undefined || valor === null || valor === "" || valor === false) continue;
    qs.set(clave, String(valor));
  }
  const cadena = qs.toString();
  return cadena ? `${base}?${cadena}` : base;
}

export class ErrorApi extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly url: string
  ) {
    super(message);
    this.name = "ErrorApi";
  }
}

async function traer<T>(url: string): Promise<T> {
  const respuesta = await fetch(url, { headers: { Accept: "application/json" } });
  if (!respuesta.ok) {
    // El backend manda `{"detail": …}` en sus errores; se aprovecha para que el mensaje que se
    // muestre diga algo concreto en vez de "500".
    let detalle = `${respuesta.status} ${respuesta.statusText}`;
    try {
      const cuerpo = await respuesta.json();
      if (cuerpo?.detail) detalle = String(cuerpo.detail);
    } catch {
      /* la respuesta no era JSON: nos quedamos con el código */
    }
    throw new ErrorApi(detalle, respuesta.status, url);
  }
  return (await respuesta.json()) as T;
}

/** Petición suelta, sin hook. La usan los handlers (descargas, envío de métricas). */
export function apiFetch<T>(ruta: string, params?: Params): Promise<T> {
  const url = construirUrl(ruta, params);
  const enCache = cache.get(url);
  if (enCache) return enCache as Promise<T>;
  const promesa = traer<T>(url).catch((err) => {
    // Un fallo no se cachea: si la red falló, el siguiente intento debe volver a probar.
    cache.delete(url);
    throw err;
  });
  cache.set(url, promesa);
  return promesa as Promise<T>;
}

/** URL absoluta de un recurso del API, para enlaces de descarga. */
export function urlApi(ruta: string, params?: Params): string {
  return construirUrl(ruta, params);
}

export function useApi<T>(ruta: string | null, params?: Params): Estado<T> {
  // `params` suele ser un objeto literal, que cambia de identidad en cada render; se depende de
  // la URL construida, no del objeto, o el efecto se relanzaría en bucle.
  const url = useMemo(
    () => (ruta === null ? null : construirUrl(ruta, params)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [ruta, JSON.stringify(params ?? {})]
  );

  const [estado, setEstado] = useState<Estado<T>>({ status: "loading", data: null, error: null });

  useEffect(() => {
    if (url === null) return;
    // `vigente` descarta la respuesta si el componente se desmontó o la URL cambió. La petición
    // en vuelo **no se aborta**: la primera versión de esto sí lo hacía, y con el doble montaje
    // de StrictMode el segundo efecto encontraba en caché la promesa que el primero acababa de
    // abortar, la esperaba y recibía un AbortError. Como los aborts no se muestran como error,
    // la página se quedaba en «cargando» para siempre — y en el caso de `/api/sitio/` eso no se
    // notaba, porque el fallback estático hacía que el sitio se viera bien.
    let vigente = true;

    const enCache = cache.get(url);
    if (enCache) {
      enCache
        .then((data) => vigente && setEstado({ status: "ok", data: data as T, error: null }))
        .catch((error: Error) => vigente && setEstado({ status: "error", data: null, error }));
      return () => {
        vigente = false;
      };
    }

    setEstado({ status: "loading", data: null, error: null });
    const promesa = traer<T>(url).catch((err) => {
      // Un fallo no se cachea: el siguiente montaje debe volver a intentarlo.
      cache.delete(url);
      throw err;
    });
    cache.set(url, promesa);
    promesa
      .then((data) => vigente && setEstado({ status: "ok", data, error: null }))
      .catch((error: Error) => vigente && setEstado({ status: "error", data: null, error }));

    return () => {
      vigente = false;
    };
  }, [url]);

  return estado;
}

/**
 * Listado paginado con acumulación de páginas.
 *
 * Devuelve los resultados de todas las páginas cargadas y un `cargarMas()`. Es lo que necesita
 * la tabla del visor, que va de 50 en 50 sobre 8,968 centros poblados: cargar todo de golpe son
 * varios MB y paginar sin acumular pierde el scroll en cada avance.
 */
export function useApiPaginado<T>(ruta: string | null, params?: Params) {
  const clave = useMemo(
    // eslint-disable-next-line react-hooks/exhaustive-deps
    () => JSON.stringify({ ruta, params: params ?? {} }),
    [ruta, JSON.stringify(params ?? {})]
  );

  const [pagina, setPagina] = useState(1);
  const [acumulado, setAcumulado] = useState<T[]>([]);
  const claveAnterior = useRef(clave);

  // Al cambiar los filtros se empieza de cero: seguir acumulando mezclaría resultados de dos
  // consultas distintas en la misma lista.
  if (claveAnterior.current !== clave) {
    claveAnterior.current = clave;
    if (pagina !== 1) setPagina(1);
    if (acumulado.length) setAcumulado([]);
  }

  const estado = useApi<Pagina<T>>(ruta, { ...params, page: pagina });

  useEffect(() => {
    if (estado.status !== "ok") return;
    setAcumulado((previo) => (pagina === 1 ? estado.data.results : [...previo, ...estado.data.results]));
  }, [estado.status, estado.status === "ok" ? estado.data : null, pagina]);

  const cargarMas = useCallback(() => setPagina((p) => p + 1), []);

  return {
    status: estado.status,
    error: estado.status === "error" ? estado.error : null,
    resultados: acumulado,
    total: estado.status === "ok" ? estado.data.count : 0,
    hayMas: estado.status === "ok" && Boolean(estado.data.next),
    cargando: estado.status === "loading",
    pagina,
    cargarMas,
    irAPagina: setPagina,
  };
}

/** Vacía la caché. La usan los tests y el reintento tras un error de red. */
export function limpiarCache(): void {
  cache.clear();
}
