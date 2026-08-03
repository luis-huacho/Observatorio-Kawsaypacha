/**
 * Visor de exposición sobre MapLibre GL + PMTiles.
 *
 * La diferencia de fondo con `MapaPeligros.tsx` (Leaflet) es dónde vive el filtrado. Ahí cada
 * cambio de peligro o de nivel rehace 8,968 CircleMarker desde React; aquí los puntos llegan en
 * un tile vectorial con una propiedad `nivel_<slug>` por peligro, y filtrar es reescribir una
 * expresión sobre el tile ya descargado — sin red y sin re-render.
 */
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import maplibregl from "maplibre-gl";
import { Protocol } from "pmtiles";
import "maplibre-gl/dist/maplibre-gl.css";
import { Layers } from "lucide-react";
import type { CentroPoblado, Nivel } from "@/lib/types";
import { PELIGROS } from "@/lib/types";
import { NIVEL_COLOR, NIVEL_LABEL, formatNumber } from "@/lib/semaforo";
import {
  BuscarLugarControl,
  DescargarPNGControl,
  MedirControl,
  VistaInicialControl,
} from "@/components/MapaControlesGL";

const CENTRO: [number, number] = [-72.0, -13.5];
const ZOOM_INICIAL = 7;
const TILES = "/tiles";
const SIN_DATO = "#BDBDBD";

// El protocolo pmtiles:// se registra una sola vez por sesión, no por instancia de mapa.
let protocoloRegistrado = false;

/**
 * Toda mutación del estilo (paint, filtros, visibilidad) exige que el estilo esté cargado.
 * El estado `listo` basta en el flujo normal, pero tras un hot reload React conserva el estado
 * mientras el mapa se reconstruye, así que se comprueba también contra el propio mapa.
 */
function cuandoListo(map: maplibregl.Map, fn: () => void) {
  if (map.isStyleLoaded()) fn();
  else map.once("load", fn);
}

type CapaContexto = {
  id: string;
  nombre: string;
  ids: string[];
};

const CAPAS_CONTEXTO: CapaContexto[] = [
  { id: "lagunas", nombre: "Lagunas", ids: ["lagunas-fill", "lagunas-line"] },
  { id: "rios", nombre: "Ríos", ids: ["rios-line"] },
  { id: "glaciares", nombre: "Glaciares", ids: ["glaciares-fill", "glaciares-line"] },
];

type Props = {
  /** Solo para el buscador de lugares; los puntos del mapa vienen del tile. */
  ccpp: CentroPoblado[];
  /** Slug del peligro activo, o null para "todos" (usa nivel_max). */
  peligroSlug: string | null;
  nivelMin: number;
  /** Ubigeo del distrito seleccionado, o "" para toda la región. */
  ubigeoDistrito: string;
};

export default function MapaPeligrosGL({ ccpp, peligroSlug, nivelMin, ubigeoDistrito }: Props) {
  const contenedor = useRef<HTMLDivElement>(null);
  const mapa = useRef<maplibregl.Map | null>(null);
  // El popup se construye una sola vez dentro del efecto de montaje, así que necesita una
  // referencia estable para navegar sin recrear el mapa.
  const navigate = useNavigate();
  const navegar = useRef(navigate);
  navegar.current = navigate;
  const [listo, setListo] = useState(false);
  const [visibles, setVisibles] = useState<Record<string, boolean>>({
    lagunas: true,
    rios: true,
    glaciares: true,
  });
  const [abierto, setAbierto] = useState(false);

  // --- Construcción del mapa (una sola vez) --------------------------------------------------
  useEffect(() => {
    if (!contenedor.current || mapa.current) return;

    if (!protocoloRegistrado) {
      maplibregl.addProtocol("pmtiles", new Protocol().tile);
      protocoloRegistrado = true;
    }

    const map = new maplibregl.Map({
      container: contenedor.current,
      center: CENTRO,
      zoom: ZOOM_INICIAL,
      // Necesario para poder leer el canvas en el export PNG.
      preserveDrawingBuffer: true,
      attributionControl: { compact: true },
      style: {
        version: 8,
        glyphs: "https://fonts.openmaptiles.org/{fontstack}/{range}.pbf",
        sources: {
          base: {
            type: "raster",
            tiles: ["https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png"],
            tileSize: 256,
            attribution:
              '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
          },
          lagunas: { type: "vector", url: `pmtiles://${TILES}/lagunas.pmtiles` },
          rios: { type: "vector", url: `pmtiles://${TILES}/rios.pmtiles` },
          glaciares: { type: "vector", url: `pmtiles://${TILES}/glaciares.pmtiles` },
          ccpp: { type: "vector", url: `pmtiles://${TILES}/ccpp.pmtiles` },
        },
        layers: [
          { id: "base", type: "raster", source: "base" },

          {
            id: "lagunas-fill", type: "fill", source: "lagunas", "source-layer": "lagunas",
            paint: { "fill-color": "#0095A4", "fill-opacity": 0.35 },
          },
          {
            id: "lagunas-line", type: "line", source: "lagunas", "source-layer": "lagunas",
            paint: { "line-color": "#007480", "line-width": 0.6 },
          },
          {
            id: "rios-line", type: "line", source: "rios", "source-layer": "rios",
            paint: {
              "line-color": "#0095A4",
              // Los cauces menores se afinan al alejarse para no emborronar la región.
              "line-width": ["interpolate", ["linear"], ["zoom"], 6, 0.4, 12, 1.6],
              "line-opacity": 0.75,
            },
          },
          {
            id: "glaciares-fill", type: "fill", source: "glaciares", "source-layer": "glaciares",
            paint: { "fill-color": "#CCEAED", "fill-opacity": 0.8 },
          },
          {
            id: "glaciares-line", type: "line", source: "glaciares", "source-layer": "glaciares",
            paint: { "line-color": "#007480", "line-width": 0.5 },
          },

          {
            id: "ccpp-puntos", type: "circle", source: "ccpp", "source-layer": "ccpp",
            paint: {
              "circle-radius": ["interpolate", ["linear"], ["zoom"], 5, 2.5, 9, 4, 14, 7],
              "circle-color": SIN_DATO,
              "circle-opacity": 0.75,
              "circle-stroke-width": 0.5,
              "circle-stroke-color": "#ffffff",
            },
          },
        ],
      },
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");
    map.addControl(new VistaInicialControl(CENTRO, ZOOM_INICIAL), "top-left");
    map.addControl(new maplibregl.FullscreenControl(), "top-left");
    map.addControl(new MedirControl(), "top-left");
    map.addControl(new DescargarPNGControl(), "top-left");
    map.addControl(new BuscarLugarControl(ccpp), "top-right");
    map.addControl(new maplibregl.ScaleControl({ maxWidth: 100, unit: "metric" }), "bottom-left");

    map.on("load", () => setListo(true));

    // Popup con la ficha del centro poblado. El enlace al detalle no puede ser un <a> normal:
    // recargaría la SPA entera, así que se delega al router.
    map.on("click", "ccpp-puntos", (e) => {
      const f = e.features?.[0];
      if (!f) return;
      const p = f.properties as Record<string, unknown>;

      const clasificados = Object.entries(p)
        .filter(([k, v]) => k.startsWith("nivel_") && k !== "nivel_max" && typeof v === "number")
        .map(([k, v]) => ({ slug: k.slice("nivel_".length), nivel: v as Nivel }));

      const nodo = document.createElement("div");
      nodo.className = "text-sm";
      nodo.innerHTML =
        `<div class="font-bold text-base">${p.nombre}</div>` +
        `<div class="text-ink-600 text-xs">${p.categoria || "s/c"} — ${p.distrito}, ${p.provincia}</div>` +
        `<div class="mt-2 text-xs">` +
        `<div>Población: <strong>${p.poblacion != null ? formatNumber(Number(p.poblacion)) : "s/d"}</strong></div>` +
        `<div>Altitud: <strong>${p.altitud != null ? `${formatNumber(Number(p.altitud))} msnm` : "s/d"}</strong></div>` +
        `</div>` +
        (clasificados.length
          ? `<div class="mt-2"><div class="text-xs font-semibold text-ink-900">Peligros clasificados:</div>` +
            `<ul class="text-xs mt-1 space-y-0.5">` +
            clasificados
              .map(
                (c) =>
                  `<li><span style="display:inline-block;width:8px;height:8px;border-radius:9999px;margin-right:6px;vertical-align:middle;background:${NIVEL_COLOR[c.nivel]}"></span>` +
                  `${nombreDePeligro(c.slug)}: <strong>${NIVEL_LABEL[c.nivel]}</strong></li>`
              )
              .join("") +
            `</ul></div>`
          : `<div class="mt-2 text-xs italic text-ink-600">Sin clasificación de peligro registrada.</div>`) +
        `<button type="button" class="block mt-3 text-xs font-medium text-mountain-700 bg-transparent border-0 p-0 cursor-pointer">Ver detalle →</button>`;

      nodo.querySelector("button")?.addEventListener("click", () => {
        navegar.current(`/peligros/${p.codigo}`);
      });

      new maplibregl.Popup({ offset: 8, maxWidth: "260px" })
        .setLngLat(e.lngLat)
        .setDOMContent(nodo)
        .addTo(map);
    });

    map.on("mouseenter", "ccpp-puntos", () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", "ccpp-puntos", () => (map.getCanvas().style.cursor = ""));

    mapa.current = map;
    return () => {
      map.remove();
      mapa.current = null;
    };
    // El buscador se alimenta del padrón completo, que no cambia con los filtros.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- Filtro y color: la parte que antes obligaba a rehacer los marcadores ------------------
  useEffect(() => {
    const map = mapa.current;
    if (!map || !listo) return;

    cuandoListo(map, () => {
      const campo = peligroSlug ? `nivel_${peligroSlug}` : "nivel_max";
      // coalesce(…, 0) hace que "sin dato" sea un valor propio y no un nivel bajo.
      const nivel: maplibregl.ExpressionSpecification = ["coalesce", ["get", campo], 0];

      map.setPaintProperty("ccpp-puntos", "circle-color", [
        "match",
        nivel,
        1, NIVEL_COLOR[1],
        2, NIVEL_COLOR[2],
        3, NIVEL_COLOR[3],
        4, NIVEL_COLOR[4],
        SIN_DATO,
      ] as maplibregl.ExpressionSpecification);

      map.setPaintProperty("ccpp-puntos", "circle-opacity", [
        "case", [">", nivel, 0], 0.8, 0.35,
      ] as maplibregl.ExpressionSpecification);

      const condiciones: maplibregl.ExpressionSpecification[] = [];
      if (nivelMin > 0) condiciones.push([">=", nivel, nivelMin]);
      if (ubigeoDistrito) condiciones.push(["==", ["get", "ubigeo_distrito"], ubigeoDistrito]);

      map.setFilter(
        "ccpp-puntos",
        condiciones.length ? (["all", ...condiciones] as maplibregl.FilterSpecification) : null
      );
    });
  }, [listo, peligroSlug, nivelMin, ubigeoDistrito]);

  // --- Encuadre al elegir un distrito --------------------------------------------------------
  // El filtro de arriba oculta los puntos de fuera, pero sin mover la cámara el usuario se queda
  // mirando toda la región. Los límites salen del padrón, que ya está en memoria.
  useEffect(() => {
    const map = mapa.current;
    if (!map || !listo) return;
    if (!ubigeoDistrito) {
      map.flyTo({ center: CENTRO, zoom: ZOOM_INICIAL });
      return;
    }
    const puntos = ccpp.filter(
      (c) => c.ubigeo_distrito === ubigeoDistrito && c.lat != null && c.lon != null
    );
    if (!puntos.length) return;
    const limites = puntos.reduce(
      (b, c) => b.extend([c.lon as number, c.lat as number]),
      new maplibregl.LngLatBounds(
        [puntos[0].lon as number, puntos[0].lat as number],
        [puntos[0].lon as number, puntos[0].lat as number]
      )
    );
    map.fitBounds(limites, { padding: 60, maxZoom: 12, duration: 800 });
  }, [listo, ubigeoDistrito, ccpp]);

  // --- Conmutador de capas de contexto -------------------------------------------------------
  useEffect(() => {
    const map = mapa.current;
    if (!map || !listo) return;
    cuandoListo(map, () => {
      for (const capa of CAPAS_CONTEXTO) {
        for (const id of capa.ids) {
          map.setLayoutProperty(id, "visibility", visibles[capa.id] ? "visible" : "none");
        }
      }
    });
  }, [listo, visibles]);

  return (
    <div className="relative w-full h-full">
      <div ref={contenedor} className="w-full h-full rounded-lg" />

      {/* Conmutador de capas */}
      <div className="absolute top-2 right-2 z-10" style={{ marginTop: 78 }}>
        <button
          type="button"
          onClick={() => setAbierto((v) => !v)}
          className="bg-white rounded shadow px-2 py-1.5 flex items-center gap-1.5 text-xs text-ink-900 hover:bg-mountain-100"
          title="Capas geográficas"
        >
          <Layers className="w-3.5 h-3.5" />
          Capas
        </button>
        {abierto && (
          <div className="mt-1 bg-white rounded shadow p-2 space-y-1">
            {CAPAS_CONTEXTO.map((c) => (
              <label key={c.id} className="flex items-center gap-2 text-xs cursor-pointer">
                <input
                  type="checkbox"
                  checked={visibles[c.id]}
                  onChange={(e) => setVisibles((v) => ({ ...v, [c.id]: e.target.checked }))}
                />
                {c.nombre}
              </label>
            ))}
          </div>
        )}
      </div>

      {/* Leyenda semáforo */}
      <div className="absolute bottom-8 right-2 z-10 bg-white/92 rounded-lg shadow px-3 py-2">
        <div className="text-[11px] font-semibold text-ink-900 mb-1">
          Nivel de peligro{peligroSlug ? "" : " (máximo)"}
        </div>
        <div className="space-y-0.5">
          {([4, 3, 2, 1] as Nivel[]).map((n) => (
            <div key={n} className="flex items-center gap-1.5 text-[11px] text-ink-600">
              <span
                className="w-2.5 h-2.5 rounded-full"
                style={{ backgroundColor: NIVEL_COLOR[n] }}
              />
              {NIVEL_LABEL[n]}
            </div>
          ))}
          <div className="flex items-center gap-1.5 text-[11px] text-ink-600">
            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: SIN_DATO }} />
            Sin dato
          </div>
        </div>
      </div>
    </div>
  );
}

/** Los tiles guardan el slug; para el popup hace falta el nombre legible del catálogo. */
const NOMBRE_POR_SLUG = new Map<string, string>(PELIGROS.map((p) => [p.slug, p.nombre]));

function nombreDePeligro(slug: string): string {
  return NOMBRE_POR_SLUG.get(slug) ?? slug.replace(/_/g, " ");
}
