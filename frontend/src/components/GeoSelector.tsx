import { useMemo } from "react";
import type { Distrito, Provincia } from "@/lib/types";

/**
 * Selects dependientes de provincia y distrito.
 *
 * Se alimenta de `/api/territorio/*` (13 + 112 filas) y no del padrón de centros poblados: antes
 * derivaba las listas de los 8,968 CCPP, que es descargar 2 MB para llenar dos `<select>`.
 * El autocompletado con Meilisearch es lo del buscador del mapa, no lo de aquí (spec 06).
 */
type Props = {
  provincias: Provincia[];
  distritos: Distrito[];
  provincia: string;
  distrito: string;
  onChange: (provincia: string, distrito: string) => void;
};

export default function GeoSelector({
  provincias: provinciasApi,
  distritos: distritosApi,
  provincia,
  distrito,
  onChange,
}: Props) {
  const provincias = useMemo(
    () => provinciasApi.map((p) => p.nombre).sort((a, b) => a.localeCompare(b, "es")),
    [provinciasApi]
  );
  const distritos = useMemo(() => {
    if (!provincia) return [];
    return distritosApi
      .filter((d) => d.provincia === provincia)
      .map((d) => d.nombre)
      .sort((a, b) => a.localeCompare(b, "es"));
  }, [distritosApi, provincia]);

  // Apilados siempre, y con `min-w-0`. Antes era `flex-col sm:flex-row`, pero ese breakpoint
  // mira el ancho de la **ventana** y no el del contenedor: en escritorio ponía los dos selects
  // en fila dentro del panel de filtros de 280 px, donde no caben. Sin `min-w-0` un `<select>`
  // no encoge por debajo de su opción más larga, así que el segundo se salía de la tarjeta y se
  // superponía a los resultados; con él cabían, pero ilegibles a ~125 px cada uno.
  return (
    <div className="flex flex-col gap-2 w-full">
      {/* `aria-label` en los dos: el rótulo «Ubicación» que hay encima describe el par, no cada
          select, así que un lector de pantalla anunciaría dos combos sin nombre. */}
      <select
        aria-label="Provincia"
        value={provincia}
        onChange={(e) => onChange(e.target.value, "")}
        className="control min-w-0 flex-1"
      >
        <option value="">Todas las provincias</option>
        {provincias.map((p) => (
          <option key={p} value={p}>{p}</option>
        ))}
      </select>
      <select
        aria-label="Distrito"
        value={distrito}
        onChange={(e) => onChange(provincia, e.target.value)}
        disabled={!provincia}
        className="control min-w-0 flex-1"
      >
        <option value="">Todos los distritos</option>
        {distritos.map((d) => (
          <option key={d} value={d}>{d}</option>
        ))}
      </select>
    </div>
  );
}
