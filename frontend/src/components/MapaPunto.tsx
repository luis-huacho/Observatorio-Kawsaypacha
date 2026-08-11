import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import {
  RANURAS,
  desplazamientoRanura,
  iconoDe,
  registrarIconos,
} from "@/lib/iconosPeligro";
import type { ClasificacionPeligro, TipoPeligroApi } from "@/lib/types";

type Props = {
  lat: number;
  lon: number;
  nombre: string;
  /** Las clasificaciones de la ficha, tal cual las devuelve `/api/ccpp/{codigo}/`. */
  clasificaciones: ClasificacionPeligro[];
  /** Catálogo de `/api/peligros/tipos/`: de ahí salen los íconos y el orden de desempate. */
  tipos: TipoPeligroApi[];
};

const ZOOM = 13;

/**
 * Sitúa **un** centro poblado, con la misma corona de íconos que el visor.
 *
 * Es un componente aparte y no `MapaPeligros` reutilizado: aquel tiene seis props obligatorias
 * y ningún interruptor, y arrastraría clustering, buscador, medidor, panel de capas y una
 * leyenda de tres bloques que aquí no significan nada. Lo que sí se reutiliza es lo que importa
 * —`registrarIconos`, `corona` y `desplazamientoRanura`—, de modo que la ficha y el visor
 * dibujan exactamente el mismo símbolo.
 *
 * Tampoco es una imagen renderizada en servidor: el repo tiene ese camino (`informes/mapa.py`,
 * Chromium headless para el PDF), pero cuesta segundos por captura y obligaría a cachear una
 * imagen por cada uno de los 3,238 centros poblados clasificados e invalidarlas en cada
 * importación.
 */
export default function MapaPunto({ lat, lon, nombre, clasificaciones, tipos }: Props) {
  const contenedor = useRef<HTMLDivElement>(null);
  const mapa = useRef<maplibregl.Map | null>(null);
  const cajaIconos = useRef<HTMLDivElement>(null);
  const [listo, setListo] = useState(false);

  /**
   * El mismo orden con el que el backend arma las ranuras del visor: nivel descendente y, a
   * igualdad, el orden del catálogo. Sin esto la ficha podría poner arriba un peligro distinto
   * del que el mapa grande enseña para el mismo lugar.
   */
  const ordenadas = useMemo(() => {
    const orden = new Map(tipos.map((t) => [t.slug, t.orden]));
    return [...clasificaciones].sort(
      (a, b) =>
        b.nivel - a.nivel ||
        (orden.get(a.peligro_slug) ?? 99) - (orden.get(b.peligro_slug) ?? 99)
    );
  }, [clasificaciones, tipos]);

  const punto = useMemo<GeoJSON.FeatureCollection<GeoJSON.Point>>(() => {
    // Las mismas propiedades numeradas que emite `/api/ccpp/geojson/`, porque las capas leen
    // `s<k>` / `n_<k>` y el offset se calcula sobre `clasificaciones`.
    const properties: Record<string, string | number> = {
      nombre,
      clasificaciones: ordenadas.length,
    };
    ordenadas.slice(0, RANURAS).forEach((c, i) => {
      properties[`s${i}`] = c.peligro_slug;
      properties[`n_${i}`] = c.nivel;
    });
    return {
      type: "FeatureCollection",
      features: [
        { type: "Feature", geometry: { type: "Point", coordinates: [lon, lat] }, properties },
      ],
    };
  }, [lat, lon, nombre, ordenadas]);

  useEffect(() => {
    if (!contenedor.current || mapa.current) return;
    const map = new maplibregl.Map({
      container: contenedor.current,
      center: [lon, lat],
      // Zoom fijo: con un solo punto no hay `fitBounds` que valga —sobre un bounds degenerado
      // se va directo al `maxZoom`— y 13 es la escala a la que se reconoce el entorno.
      zoom: ZOOM,
      // Igual que el visor. Aquí no hay export PNG, pero sin esto el canvas no se puede leer
      // con `readPixels` tras el swap, y esa lectura es la única forma de comprobar que el
      // mapa **pintó de verdad**: un canvas en blanco pasa cualquier comprobación de
      // visibilidad. El coste en un mapa estático de una ficha es nulo.
      preserveDrawingBuffer: true,
      attributionControl: { compact: true },
      style: {
        version: 8,
        glyphs: "/fonts/glyphs/{fontstack}/{range}.pbf",
        sources: {
          base: {
            type: "raster",
            // Las mismas teselas que el mapa base «Claro» del visor: si la ficha usara otro
            // proveedor, el mismo lugar se vería distinto en las dos pantallas.
            tiles: [
              "https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png",
              "https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png",
              "https://c.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png",
            ],
            tileSize: 256,
            maxzoom: 20,
            attribution:
              '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
          },
          punto: { type: "geojson", data: punto },
        },
        layers: [
          { id: "base", type: "raster", source: "base" },
          // Punto gris para los que no tienen ninguna clasificación: sin ícono, igual que en
          // el visor, porque «sin dato» no es un peligro.
          {
            id: "punto-sin-dato",
            type: "circle",
            source: "punto",
            filter: ["==", ["get", "clasificaciones"], 0],
            paint: {
              "circle-radius": 6,
              "circle-color": "#BDBDBD",
              "circle-stroke-width": 2,
              "circle-stroke-color": "#ffffff",
            },
          },
        ],
      },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.on("load", () => setListo(true));
    mapa.current = map;
    return () => {
      map.remove();
      mapa.current = null;
    };
    // Solo al montar: un cambio de coordenadas llega con la ruta, que remonta el componente.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Datos y capas de la corona, una vez rasterizados los íconos.
  useEffect(() => {
    const map = mapa.current;
    if (!map || !listo || !tipos.length) return;
    let cancelado = false;

    const caja = cajaIconos.current;
    const svgPorSlug: Record<string, string> = {};
    if (caja) {
      for (const t of tipos) {
        const svg = caja.querySelector<SVGSVGElement>(`[data-slug="${t.slug}"] svg`);
        if (svg) svgPorSlug[t.slug] = new XMLSerializer().serializeToString(svg);
      }
    }

    registrarIconos(map, tipos, svgPorSlug).then(() => {
      if (cancelado || !mapa.current || map.getLayer("punto-peligro-0")) return;
      for (let k = 0; k < RANURAS; k++) {
        map.addLayer({
          id: `punto-peligro-${k}`,
          type: "symbol",
          source: "punto",
          filter: ["has", `s${k}`],
          layout: {
            "icon-image": [
              "concat", "peligro-", ["get", `s${k}`], "-",
              ["to-string", ["coalesce", ["get", `n_${k}`], 0]],
            ],
            "icon-offset": desplazamientoRanura(k),
            // Sin esto MapLibre descarta por colisión los íconos de la corona, que se rozan
            // por diseño, y el punto se ve incompleto sin dar ningún error.
            "icon-allow-overlap": true,
            "icon-ignore-placement": true,
          },
        });
      }
    });

    return () => {
      cancelado = true;
    };
  }, [listo, tipos]);

  useEffect(() => {
    const map = mapa.current;
    if (!map || !listo) return;
    (map.getSource("punto") as maplibregl.GeoJSONSource | undefined)?.setData(punto);
  }, [listo, punto]);

  return (
    <div className="relative w-full h-full">
      <div ref={contenedor} className="w-full h-full rounded-md overflow-hidden" />
      {/* Fuente de los SVG que se rasterizan como imágenes del mapa; oculta y fuera del flujo. */}
      <div
        ref={cajaIconos}
        aria-hidden
        className="absolute w-0 h-0 overflow-hidden pointer-events-none"
      >
        {tipos.map((t) => {
          const Icono = iconoDe(t.icono);
          return (
            <span key={t.slug} data-slug={t.slug}>
              <Icono strokeWidth={2.5} color="#ffffff" />
            </span>
          );
        })}
      </div>
    </div>
  );
}
