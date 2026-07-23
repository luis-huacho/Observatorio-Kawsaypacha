import { useEffect, useState } from "react";

/**
 * Cliente del API Django. Mismo contrato que useJsonData para migración gradual:
 * cada ruta cambia `useJsonData("/data/x.json")` por `useApi("/x/")` cuando el
 * endpoint esté disponible.
 *
 * Mapeo previsto ruta → endpoint:
 *   /            → /peligros/resumen/, /sitio/
 *   /peligros    → /territorio/provincias/, /territorio/distritos/, /ccpp/, /peligros/tipos/, /peligros/resumen/, /peligros/frecuencia/
 *   /peligros/:codigo → /ccpp/{codigo}/
 *   /medidas     → /medidas/            /medidas/:slug → /medidas/{slug}/
 *   /inversion   → /inversion/
 *   /normativa   → /normativa/
 *   /recursos    → /biblioteca/
 *   /buscar      → Meilisearch multi-search vía VITE_SEARCH_URL
 *   Header/Footer/Hero/Sobre → /sitio/
 */

const API_URL: string = import.meta.env.VITE_API_URL ?? "/api";

type State<T> =
  | { status: "loading"; data: null; error: null }
  | { status: "ok"; data: T; error: null }
  | { status: "error"; data: null; error: Error };

const cache = new Map<string, unknown>();

function buildUrl(path: string, params?: Record<string, string | number | undefined>): string {
  const url = `${API_URL}${path.startsWith("/") ? path : `/${path}`}`;
  if (!params) return url;
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") qs.set(k, String(v));
  }
  const s = qs.toString();
  return s ? `${url}?${s}` : url;
}

export async function apiFetch<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const url = buildUrl(path, params);
  if (cache.has(url)) return cache.get(url) as T;
  const r = await fetch(url, { headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  const data = (await r.json()) as T;
  cache.set(url, data);
  return data;
}

export function useApi<T>(path: string, params?: Record<string, string | number | undefined>): State<T> {
  const url = buildUrl(path, params);
  const [state, setState] = useState<State<T>>(() => {
    if (cache.has(url)) {
      return { status: "ok", data: cache.get(url) as T, error: null };
    }
    return { status: "loading", data: null, error: null };
  });

  useEffect(() => {
    let active = true;
    if (cache.has(url)) {
      setState({ status: "ok", data: cache.get(url) as T, error: null });
      return;
    }
    setState({ status: "loading", data: null, error: null });
    apiFetch<T>(path, params)
      .then((data) => {
        if (active) setState({ status: "ok", data, error: null });
      })
      .catch((err: Error) => {
        if (active) setState({ status: "error", data: null, error: err });
      });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]);

  return state;
}
