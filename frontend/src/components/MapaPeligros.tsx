/**
 * Visor de exposición sobre MapLibre GL.
 *
 * Sustituye a la versión Leaflet, donde cada cambio de peligro o de nivel rehacía 8,968
 * CircleMarker desde React. Aquí los centros poblados son una fuente GeoJSON agrupada
 * (clustering) que la página arma ya filtrada, y el dibujo lo resuelve la GPU con expresiones
 * de estilo — sin marcadores en el DOM y sin re-render de React.
 *
 * La fuente no puede ser un tile vectorial: MapLibre solo agrupa fuentes `geojson`. Por lo mismo
 * el filtrado no se hace con `setFilter` (los clusters se calculan sobre la fuente entera, antes
 * del filtro de capa) sino reemplazando los datos con `setData`.
 *
 * Las capas de contexto —lagunas, ríos y glaciares— sí siguen en PMTiles, generadas con
 * `prototype/scripts/build_tiles.sh` y servidas desde `public/tiles/`.
 */
import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import maplibregl, { type LayerSpecification } from "maplibre-gl";
import { Protocol } from "pmtiles";
import "maplibre-gl/dist/maplibre-gl.css";
import { Layers } from "lucide-react";
import type { CapaMapa, Nivel } from "@/lib/types";
import { NIVEL_COLOR, NIVEL_LABEL, formatNumber } from "@/lib/semaforo";
import { buscarLugares } from "@/lib/search";
import {
  BuscarLugarControl,
  DescargarPNGControl,
  MedirControl,
  VistaInicialControl,
  capturarPNG,
} from "@/components/MapaControles";

const CENTRO: [number, number] = [-72.0, -13.5];
const ZOOM_INICIAL = 7;
const SIN_DATO = "#BDBDBD";
const VACIO: GeoJSON.FeatureCollection<GeoJSON.Point> = {
  type: "FeatureCollection",
  features: [],
};

/**
 * Símbolos proporcionales a la población.
 *
 * La población de los centros poblados es muy asimétrica —mediana 23 habitantes, máximo 111,930 en
 * la ciudad del Cusco— así que una escala lineal deja el 90% de los puntos indistinguibles y una
 * raíz continua no se puede leyendar. Clases graduadas: cada peldaño abarca un orden de magnitud y
 * el radio crece con la raíz del área para que la comparación visual sea honesta.
 */
const CLASES_POBLACION: { desde: number; radio: number; etiqueta: string }[] = [
  { desde: 0, radio: 2.5, etiqueta: "sin dato" },
  { desde: 1, radio: 4, etiqueta: "1 – 49" },
  { desde: 50, radio: 6, etiqueta: "50 – 199" },
  { desde: 200, radio: 8.5, etiqueta: "200 – 999" },
  { desde: 1000, radio: 12, etiqueta: "1 mil – 10 mil" },
  { desde: 10000, radio: 17, etiqueta: "más de 10 mil" },
];

/** `step` de MapLibre: valor por defecto y luego pares (umbral, salida). */
function escalaPorPoblacion(campo: maplibregl.ExpressionSpecification) {
  const [primera, ...resto] = CLASES_POBLACION;
  return [
    "step",
    campo,
    primera.radio,
    ...resto.flatMap((c) => [c.desde, c.radio]),
  ] as maplibregl.ExpressionSpecification;
}

/**
 * Los clusters usan la misma lógica sobre la población agregada del grupo, desplazada hacia
 * arriba: un cluster siempre pesa más que cualquiera de sus puntos y debe leerse como tal.
 */
const RADIO_CLUSTER: maplibregl.ExpressionSpecification = [
  "step",
  ["get", "pob"],
  8,
  200, 11,
  1000, 14,
  10000, 18,
  100000, 24,
];

// El protocolo pmtiles:// se registra una sola vez por sesión, no por instancia de mapa.
let protocoloRegistrado = false;

/**
 * Toda mutación del estilo (paint, datos, visibilidad) exige que el estilo esté cargado.
 * El estado `listo` basta en el flujo normal, pero tras un hot reload React conserva el estado
 * mientras el mapa se reconstruye, así que se comprueba también contra el propio mapa.
 *
 * No sirve esperar el evento `load`: cuando el efecto corre justo después de que React reaccionara
 * a ese mismo evento, `isStyleLoaded()` todavía puede devolver false —hay cambios de estilo en
 * vuelo— y un `once("load")` sobre un mapa que ya cargó no se ejecuta jamás, así que el efecto se
 * pierde en silencio. `styledata` tampoco basta por sí solo: sus últimas emisiones pueden llegar
 * con el estilo aún sin asentar y después no vuelve a haber ninguna. `idle` cierra el hueco —se
 * emite cuando ya no queda nada pendiente por cargar ni dibujar— y ambos se limpian solos con
 * `map.remove()`.
 */
function cuandoListo(map: maplibregl.Map, fn: () => void) {
  if (map.isStyleLoaded()) {
    fn();
    return;
  }
  const reintentar = () => {
    if (!map.isStyleLoaded()) return;
    map.off("styledata", reintentar);
    map.off("idle", reintentar);
    fn();
  };
  map.on("styledata", reintentar);
  map.on("idle", reintentar);
}

type MapaBase = {
  id: string;
  nombre: string;
  tiles: string[];
  atribucion: string;
  /** Último zoom que sirve la fuente; MapLibre sobre-escala a partir de ahí en vez de dar 404. */
  maxzoom: number;
};

/**
 * El primero es el que arranca visible. OpenTopoMap es un servicio voluntario con política de uso
 * restrictiva: sirve para el prototipo, pero en producción hay que sustituirlo (ver spec 05).
 */
const MAPAS_BASE: MapaBase[] = [
  {
    id: "osm",
    nombre: "OpenStreetMap",
    tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
    atribucion:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxzoom: 19,
  },
  {
    id: "claro",
    nombre: "Claro",
    tiles: [
      "https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png",
      "https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png",
      "https://c.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png",
    ],
    atribucion:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
    maxzoom: 20,
  },
  {
    id: "satelite",
    nombre: "Satélite",
    // Ojo al orden: Esri sirve las teselas como /{z}/{y}/{x}, no /{z}/{x}/{y}.
    tiles: [
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    ],
    atribucion: "Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics",
    maxzoom: 19,
  },
  {
    id: "topografico",
    nombre: "Topográfico",
    tiles: [
      "https://a.tile.opentopomap.org/{z}/{x}/{y}.png",
      "https://b.tile.opentopomap.org/{z}/{x}/{y}.png",
      "https://c.tile.opentopomap.org/{z}/{x}/{y}.png",
    ],
    atribucion:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> — Relieve: <a href="https://opentopomap.org">OpenTopoMap</a> (CC-BY-SA)',
    maxzoom: 17,
  },
];

const BASE_POR_DEFECTO = MAPAS_BASE[0].id;

type CapaContexto = {
  id: string;
  nombre: string;
  ids: string[];
};

/**
 * Traduce una capa del catálogo a las capas de MapLibre que la dibujan.
 *
 * Un polígono necesita dos —relleno y contorno—, una línea solo una. El `source-layer` es el
 * slug porque así se nombra la capa dentro del tile (lo fija tippecanoe con `-l`).
 */
function capasDeContexto(c: CapaMapa): LayerSpecification[] {
  const e = (c.estilo ?? {}) as Record<string, unknown>;
  const comun = { source: c.slug, "source-layer": c.slug, minzoom: c.min_zoom || 0 };

  if (c.tipo_geometria === "linea") {
    return [
      {
        ...comun,
        id: `${c.slug}-line`,
        type: "line",
        paint: {
          "line-color": (e["line-color"] as string) ?? "#0095A4",
          "line-width": (e["line-width"] ?? 0.8) as never,
          "line-opacity": (e["line-opacity"] ?? 0.75) as never,
        },
      },
    ];
  }
  return [
    {
      ...comun,
      id: `${c.slug}-fill`,
      type: "fill",
      paint: {
        "fill-color": (e["fill-color"] as string) ?? "#0095A4",
        "fill-opacity": (e["fill-opacity"] ?? 0.35) as never,
      },
    },
    {
      ...comun,
      id: `${c.slug}-line`,
      type: "line",
      paint: {
        "line-color": (e["line-color"] as string) ?? "#007480",
        "line-width": (e["line-width"] ?? 0.6) as never,
      },
    },
  ];
}

/** Ids de las capas de MapLibre que corresponden a una capa del catálogo. */
function idsDeCapa(c: CapaMapa): string[] {
  return capasDeContexto(c).map((l) => l.id);
}

type Props = {
  /**
   * Capas de contexto, del catálogo del admin (`/api/mapas/capas/`).
   *
   * Antes estaban cableadas aquí, con una ruta relativa `/tiles/…` que en desarrollo resolvía
   * contra el servidor de Vite y devolvía el `index.html` — de ahí el «Wrong magic number for
   * PMTiles archive». Ahora la URL, el estilo y el orden los pone el admin, que es el requisito
   * de reemplazo de capas del TDR: PREDES sube un GeoJSON nuevo y el visor lo dibuja sin que
   * nadie toque código.
   */
  capas: CapaMapa[];
  /** Centros poblados a dibujar, ya filtrados por la página. `nivel` 0 = sin clasificación. */
  puntos: GeoJSON.FeatureCollection<GeoJSON.Point>;
  /** Slug del peligro activo, o null para "todos". Solo rotula la leyenda. */
  peligroSlug: string | null;
  /** Si hay algún filtro geográfico activo, la cámara se ciñe a los puntos recibidos. */
  ambitoAcotado: boolean;
};

/** Lo que la página puede pedirle al mapa de forma imperativa. */
export type MapaPeligrosHandle = {
  /** PNG de la vista actual, para incrustarlo en la ayuda memoria imprimible. */
  capturarPNG: () => Promise<string>;
  /** Nombre legible del mapa base activo, para citarlo al pie de la imagen. */
  mapaBaseActivo: () => string;
};

const MapaPeligros = forwardRef<MapaPeligrosHandle, Props>(function MapaPeligros(
  { capas, puntos, peligroSlug, ambitoAcotado },
  ref
) {
  const contenedor = useRef<HTMLDivElement>(null);
  const mapa = useRef<maplibregl.Map | null>(null);
  // El popup se construye una sola vez dentro del efecto de montaje, así que necesita una
  // referencia estable para navegar sin recrear el mapa.
  const navigate = useNavigate();
  const navegar = useRef(navigate);
  navegar.current = navigate;
  const [listo, setListo] = useState(false);
  const [base, setBase] = useState(BASE_POR_DEFECTO);
  // El conmutador y su estado inicial se derivan del catálogo: `visible_por_defecto` lo decide
  // el admin, no el código.
  const listaConmutador = useMemo(
    () => capas.map((c) => ({ id: c.slug, nombre: c.nombre, ids: idsDeCapa(c) })),
    [capas]
  );
  const [visibles, setVisibles] = useState<Record<string, boolean>>({});
  useEffect(() => {
    setVisibles((previo) => {
      const siguiente = { ...previo };
      for (const c of capas) {
        // Solo se inicializa lo que no estaba: si el usuario apagó una capa, un re-render del
        // catálogo no debe volver a encenderla.
        if (!(c.slug in siguiente)) siguiente[c.slug] = c.visible_por_defecto;
      }
      return siguiente;
    });
  }, [capas]);
  const [abierto, setAbierto] = useState(false);

  useImperativeHandle(
    ref,
    () => ({
      capturarPNG: () => {
        const map = mapa.current;
        if (!map) return Promise.reject(new Error("El mapa todavía no está listo"));
        return capturarPNG(map);
      },
      mapaBaseActivo: () => MAPAS_BASE.find((m) => m.id === base)?.nombre ?? "",
    }),
    [base]
  );

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
        // Auto-hospedados: fonts.openmaptiles.org dejó de servir glifos y responde un HTML con
        // status 200, que MapLibre intenta parsear como protobuf ("Unimplemented type: 4"). Los
        // rótulos de los grupos solo usan dígitos y la abreviatura k/M, así que basta el rango
        // 0-255 — 168 KB en total y sin depender de terceros.
        glyphs: "/fonts/glyphs/{fontstack}/{range}.pbf",
        sources: {
          // Una fuente por mapa base. Las que no tienen ninguna capa visible no descargan
          // teselas, y el control de atribución solo publica las que están en uso: al conmutar,
          // la firma legal del pie cambia sola.
          ...Object.fromEntries(
            MAPAS_BASE.map((m) => [
              `base-${m.id}`,
              {
                type: "raster" as const,
                tiles: m.tiles,
                tileSize: 256,
                maxzoom: m.maxzoom,
                attribution: m.atribucion,
              },
            ])
          ),
          // Una fuente vectorial por capa del catálogo. `capa.url` es absoluta y apunta al
          // dominio del backend, que sirve los .pmtiles con Range y CORS (ADR-A14).
          ...Object.fromEntries(
            capas.map((c) => [
              c.slug,
              { type: "vector" as const, url: `pmtiles://${c.url}` },
            ])
          ),
          // Arranca vacía: los datos llegan por prop y se inyectan con setData.
          ccpp: {
            type: "geojson",
            data: VACIO,
            cluster: true,
            clusterRadius: 50,
            // Pasado este zoom los grupos se abren y se ve el centro poblado individual.
            clusterMaxZoom: 12,
            clusterProperties: {
              // El tamaño del grupo lo da la población que concentra, no cuántos puntos son.
              pob: ["+", ["coalesce", ["get", "poblacion"], 0]],
              // Y el color, el peor nivel del grupo: un cluster no puede verse más benigno que
              // el centro poblado más expuesto que contiene.
              nivelMax: ["max", ["coalesce", ["get", "nivel"], 0]],
            },
          },
        },
        layers: [
          // Al fondo de la pila y todas ocultas menos la de por defecto.
          ...MAPAS_BASE.map((m) => ({
            id: `base-${m.id}`,
            type: "raster" as const,
            source: `base-${m.id}`,
            layout: {
              visibility: (m.id === BASE_POR_DEFECTO ? "visible" : "none") as "visible" | "none",
            },
          })),

          // El paint sale del JSON `estilo` de cada capa: recolorear o cambiar el grosor de
          // una capa es editarla en el admin, no desplegar.
          ...capas.flatMap((c) => capasDeContexto(c)),

          // Puntos sueltos debajo de los grupos: a zoom intermedio conviven ambos y el grupo,
          // que resume más información, debe quedar por encima.
          {
            id: "ccpp-puntos", type: "circle", source: "ccpp",
            filter: ["!", ["has", "point_count"]],
            paint: {
              "circle-radius": escalaPorPoblacion(["coalesce", ["get", "poblacion"], 0]),
              "circle-color": SIN_DATO,
              "circle-opacity": 0.75,
              "circle-stroke-width": 0.5,
              "circle-stroke-color": "#ffffff",
            },
          },
          {
            id: "ccpp-clusters", type: "circle", source: "ccpp",
            filter: ["has", "point_count"],
            paint: {
              "circle-radius": RADIO_CLUSTER,
              "circle-color": SIN_DATO,
              "circle-opacity": 0.85,
              "circle-stroke-width": 1.5,
              "circle-stroke-color": "#ffffff",
            },
          },
          {
            id: "ccpp-clusters-num", type: "symbol", source: "ccpp",
            filter: ["has", "point_count"],
            layout: {
              "text-field": ["get", "point_count_abbreviated"],
              "text-font": ["Noto Sans Bold"],
              // Acompaña al radio para que el número no desborde los grupos pequeños.
              "text-size": ["step", ["get", "point_count"], 10, 100, 11, 1000, 12],
              "text-allow-overlap": true,
            },
            paint: {
              "text-color": "#ffffff",
              "text-halo-color": "rgba(0,0,0,0.35)",
              "text-halo-width": 1,
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
    // El buscador consulta el índice `ccpp` de Meilisearch. Si no está disponible,
    // `buscarLugares` devuelve [] y el control simplemente no sugiere nada: el resto del visor
    // sigue funcionando.
    map.addControl(new BuscarLugarControl(buscarLugares), "top-right");
    map.addControl(new maplibregl.ScaleControl({ maxWidth: 100, unit: "metric" }), "bottom-left");

    map.on("load", () => setListo(true));

    // Popup con la ficha del centro poblado. El enlace al detalle no puede ser un <a> normal:
    // recargaría la SPA entera, así que se delega al router.
    map.on("click", "ccpp-puntos", (e) => {
      const f = e.features?.[0];
      if (!f) return;
      const p = f.properties as Record<string, unknown>;

      const clasificados = leerClasificaciones(p.clasif);

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
                  `${c.peligro}: <strong>${NIVEL_LABEL[c.nivel]}</strong></li>`
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

    // Un grupo no tiene ficha propia: al pulsarlo se acerca la cámara hasta el zoom en que
    // supercluster lo descompone, que es lo que el usuario está pidiendo al hacer clic.
    map.on("click", "ccpp-clusters", async (e) => {
      const f = e.features?.[0];
      if (!f) return;
      const fuente = map.getSource("ccpp") as maplibregl.GeoJSONSource;
      const zoom = await fuente.getClusterExpansionZoom(f.properties.cluster_id as number);
      map.easeTo({
        center: (f.geometry as GeoJSON.Point).coordinates as [number, number],
        zoom,
        duration: 500,
      });
    });

    for (const capa of ["ccpp-puntos", "ccpp-clusters"]) {
      map.on("mouseenter", capa, () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", capa, () => (map.getCanvas().style.cursor = ""));
    }

    mapa.current = map;
    return () => {
      map.remove();
      mapa.current = null;
    };
    // El buscador se alimenta del padrón completo, que no cambia con los filtros.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- Datos: con clustering el filtro vive en la fuente, no en la capa ----------------------
  // `setFilter` no serviría aquí: supercluster agrupa la fuente entera antes de que la capa filtre,
  // así que un cluster seguiría contando puntos ya descartados. La página entrega los centros
  // poblados ya filtrados y aquí solo se reemplazan.
  useEffect(() => {
    const map = mapa.current;
    if (!map || !listo) return;
    cuandoListo(map, () => {
      (map.getSource("ccpp") as maplibregl.GeoJSONSource | undefined)?.setData(puntos);
    });
  }, [listo, puntos]);

  // --- Color del semáforo ---------------------------------------------------------------------
  useEffect(() => {
    const map = mapa.current;
    if (!map || !listo) return;

    cuandoListo(map, () => {
      const semaforo = (nivel: maplibregl.ExpressionSpecification) =>
        [
          "match",
          nivel,
          1, NIVEL_COLOR[1],
          2, NIVEL_COLOR[2],
          3, NIVEL_COLOR[3],
          4, NIVEL_COLOR[4],
          SIN_DATO,
        ] as maplibregl.ExpressionSpecification;

      // coalesce(…, 0) hace que "sin dato" sea un valor propio y no un nivel bajo.
      const nivel: maplibregl.ExpressionSpecification = ["coalesce", ["get", "nivel"], 0];
      map.setPaintProperty("ccpp-puntos", "circle-color", semaforo(nivel));
      map.setPaintProperty(
        "ccpp-clusters",
        "circle-color",
        semaforo(["coalesce", ["get", "nivelMax"], 0])
      );

      // Los sin dato se atenúan para que el semáforo destaque. Hay que bajar también el borde:
      // `circle-stroke-opacity` es independiente de `circle-opacity` y vale 1 por defecto, así
      // que un relleno translúcido con anillo opaco convierte los 5,730 puntos sin clasificar
      // en una masa blanca, sobre todo encima de la ortofoto.
      const atenuar: maplibregl.ExpressionSpecification = [
        "case", [">", nivel, 0], 0.85, 0.3,
      ];
      map.setPaintProperty("ccpp-puntos", "circle-opacity", atenuar);
      map.setPaintProperty("ccpp-puntos", "circle-stroke-opacity", atenuar);
    });
  }, [listo]);

  // --- Encuadre al acotar el ámbito -----------------------------------------------------------
  // Sin mover la cámara, filtrar deja al usuario mirando toda la región. Los límites salen de los
  // puntos ya filtrados, así que el encuadre funciona igual para provincia sola que para distrito.
  useEffect(() => {
    const map = mapa.current;
    if (!map || !listo) return;
    if (!ambitoAcotado) {
      map.flyTo({ center: CENTRO, zoom: ZOOM_INICIAL });
      return;
    }
    const coords = puntos.features.map((f) => f.geometry.coordinates as [number, number]);
    if (!coords.length) return;
    const limites = coords.reduce(
      (b, c) => b.extend(c),
      new maplibregl.LngLatBounds(coords[0], coords[0])
    );
    map.fitBounds(limites, { padding: 60, maxZoom: 12, duration: 800 });
  }, [listo, ambitoAcotado, puntos]);

  // --- Mapa base -----------------------------------------------------------------------------
  useEffect(() => {
    const map = mapa.current;
    if (!map || !listo) return;
    cuandoListo(map, () => {
      for (const m of MAPAS_BASE) {
        map.setLayoutProperty(`base-${m.id}`, "visibility", m.id === base ? "visible" : "none");
      }
      // El halo blanco separa el punto del fondo. Sobre el gris casi liso de CARTO basta un
      // trazo fino; sobre OSM, ortofoto o relieve el fondo tiene textura y etiquetas y hace
      // falta algo más. Pasado ~1 px el anillo se come el relleno a zoom bajo.
      map.setPaintProperty("ccpp-puntos", "circle-stroke-width", base === "claro" ? 0.5 : 0.8);
    });
  }, [listo, base]);

  // --- Conmutador de capas de contexto -------------------------------------------------------
  useEffect(() => {
    const map = mapa.current;
    if (!map || !listo) return;
    cuandoListo(map, () => {
      for (const capa of listaConmutador) {
        for (const id of capa.ids) {
          map.setLayoutProperty(id, "visibility", visibles[capa.id] ? "visible" : "none");
        }
      }
    });
  }, [listo, visibles]);

  return (
    <div className="relative w-full h-full">
      <div ref={contenedor} className="w-full h-full rounded-lg" />

      {/* Mapa base y capas de contexto, con la misma disposición que el LayersControl de
          Leaflet: bases arriba (radios), superposiciones abajo (casillas). */}
      <div className="absolute top-2 right-2 z-10" style={{ marginTop: 78 }}>
        <button
          type="button"
          onClick={() => setAbierto((v) => !v)}
          className="bg-white rounded shadow px-2 py-1.5 flex items-center gap-1.5 text-xs text-ink-900 hover:bg-mountain-100"
          title={`Mapa base: ${MAPAS_BASE.find((m) => m.id === base)?.nombre ?? ""}`}
        >
          <Layers className="w-3.5 h-3.5" />
          Capas
        </button>
        {abierto && (
          <div className="mt-1 bg-white rounded shadow p-2 min-w-[9.5rem]">
            <div className="text-[10px] uppercase tracking-wide text-ink-600 mb-1">Mapa base</div>
            <div className="space-y-1">
              {MAPAS_BASE.map((m) => (
                <label key={m.id} className="flex items-center gap-2 text-xs cursor-pointer">
                  <input
                    type="radio"
                    name="mapa-base"
                    checked={base === m.id}
                    onChange={() => setBase(m.id)}
                  />
                  {m.nombre}
                </label>
              ))}
            </div>

            <div className="text-[10px] uppercase tracking-wide text-ink-600 mt-3 mb-1 pt-2 border-t border-ink-300/40">
              Capas
            </div>
            <div className="space-y-1">
              {listaConmutador.map((c) => (
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
          </div>
        )}
      </div>

      {/* Leyenda semáforo */}
      {/* bg-white/95: la escala de opacidad de Tailwind va de 5 en 5, así que un /92 no genera
          ninguna clase y la leyenda se queda sin fondo. */}
      <div className="absolute bottom-8 right-2 z-10 bg-white/95 rounded-lg shadow px-3 py-2">
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

        {/* El tamaño codifica una segunda variable, así que necesita su propia clave: sin ella
            un círculo grande se lee como "más peligroso" en vez de "más gente expuesta". */}
        <div className="text-[11px] font-semibold text-ink-900 mt-2 pt-2 border-t border-ink-300/40">
          Población
        </div>
        <div className="space-y-0.5 mt-1">
          {CLASES_POBLACION.filter((c) => c.desde > 0).map((c) => (
            <div key={c.desde} className="flex items-center gap-1.5 text-[11px] text-ink-600">
              <span className="w-[34px] flex justify-center shrink-0">
                <span
                  className="rounded-full border border-white bg-ink-300"
                  style={{ width: c.radio * 2, height: c.radio * 2 }}
                />
              </span>
              {c.etiqueta}
            </div>
          ))}
        </div>
        <div className="text-[10px] text-ink-300 mt-1 max-w-[9rem] leading-tight">
          Los grupos suman la población de los centros poblados que contienen.
        </div>
      </div>
    </div>
  );
});

export default MapaPeligros;

/**
 * Las propiedades de una fuente GeoJSON agrupada tienen que ser escalares para sobrevivir al
 * worker de clustering, así que el desglose por peligro viaja serializado.
 */
function leerClasificaciones(valor: unknown): { peligro: string; nivel: Nivel }[] {
  if (typeof valor !== "string") return [];
  try {
    const lista = JSON.parse(valor);
    return Array.isArray(lista) ? lista : [];
  } catch {
    return [];
  }
}
