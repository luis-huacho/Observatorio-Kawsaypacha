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
import type { CapaMapa, Nivel, TipoPeligroApi } from "@/lib/types";
import { NIVEL_COLOR, NIVEL_LABEL, formatNumber } from "@/lib/semaforo";
import { iconoDe, idImagen, registrarIconos } from "@/lib/iconosPeligro";
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
 * Tamaño de los grupos: **cuántas clasificaciones concentran**, con los filtros puestos.
 *
 * Aquí estuvo la población, y se fue (ADR-A17). Como escala era ilegible —948 centros poblados
 * valen 0 y la mediana es 17 habitantes, así que la inmensa mayoría quedaba en el peldaño más
 * pequeño— y además hacía que el diámetro y el número del círculo hablaran de cosas distintas.
 * Ahora los dos cuentan lo mismo y el grupo se puede leer sin traducir nada.
 */
const RADIO_CLUSTER: maplibregl.ExpressionSpecification = [
  "step",
  ["coalesce", ["get", "clasif"], 0],
  9,
  10, 13,
  50, 17,
  200, 21,
  1000, 26,
];

/** Peldaños del radio, para la leyenda. */
const CLASES_CONTEO: { desde: number; radio: number; etiqueta: string }[] = [
  { desde: 0, radio: 9, etiqueta: "1 – 9" },
  { desde: 10, radio: 13, etiqueta: "10 – 49" },
  { desde: 50, radio: 17, etiqueta: "50 – 199" },
  { desde: 200, radio: 21, etiqueta: "200 – 999" },
  { desde: 1000, radio: 26, etiqueta: "1,000 o más" },
];

/**
 * El número del círculo son **clasificaciones**, no centros poblados: uno con tres peligros
 * evaluados aporta 3. Es la unidad que se lee sin explicación —«aquí hay 3 peligros»— y la
 * única que reacciona a los filtros; `point_count` no lo hacía, porque los que no cumplen
 * siguen en la fuente para pintarse en gris.
 *
 * Un grupo sin ninguna clasificación se queda sin número: el gris ya dice «sin dato», y un «0»
 * se leería como «evaluado, y sin peligro».
 */
const NUMERO_CLUSTER: maplibregl.ExpressionSpecification = [
  "case",
  ["==", ["get", "clasif"], 0], "",
  ["<", ["get", "clasif"], 1000], ["to-string", ["get", "clasif"]],
  // Un decimal hasta 10 mil: redondeando al millar, a zoom regional media docena de grupos
  // distintos se leían todos "1k". Es lo que hacía `point_count_abbreviated`, y los glifos
  // auto-hospedados (0-255) cubren el punto decimal y la "k".
  ["<", ["get", "clasif"], 10000],
  ["concat", ["to-string", ["/", ["round", ["/", ["get", "clasif"], 100]], 10]], "k"],
  ["concat", ["to-string", ["round", ["/", ["get", "clasif"], 1000]]], "k"],
];

/**
 * Filtros de las tres capas de centros poblados.
 *
 * El conmutador de «sin clasificación» se aplica **aquí** y no reemplazando los datos: los
 * agregados del grupo ya dejan fuera a los sin dato, así que esto solo decide qué se dibuja.
 *
 * Ojo: ocultarlos no reagrupa. Un grupo con 3 sin dato y 2 clasificados sigue siendo un solo
 * círculo en el mismo sitio, rotulado 2 — supercluster agrupa la fuente entera antes de que la
 * capa filtre.
 */
/**
 * Los sueltos sin ninguna clasificación: punto gris.
 *
 * Es un filtro fijo — el conmutador de «mostrar sin clasificación» apaga la capa entera con
 * `visibility`, no con un filtro imposible: MapLibre valida las expresiones de filtro y rechaza
 * una comparación entre dos literales.
 */
const FILTRO_SIN_DATO: maplibregl.ExpressionSpecification = [
  "all",
  ["!", ["has", "point_count"]],
  ["==", ["coalesce", ["get", "clasificaciones"], 0], 0],
];

/** Los sueltos **con** clasificación: llevan ícono del tipo y color del nivel. */
const FILTRO_SIMBOLOS: maplibregl.ExpressionSpecification = [
  "all",
  ["!", ["has", "point_count"]],
  [">", ["coalesce", ["get", "clasificaciones"], 0], 0],
];

/**
 * Ranuras de la corona: un ícono por peligro del centro poblado.
 *
 * Nueve, el catálogo entero, igual que en el backend. Antes se dibujaba **solo el de mayor
 * nivel** y los demás quedaban escondidos en el popup — con 3.4 peligros de media por lugar,
 * el mapa ocultaba la mayor parte de lo evaluado.
 */
const RANURAS = 9;

/** Diámetro visual del símbolo a `icon-size: 1`, que es lo que separa dos íconos vecinos. */
const DIAMETRO_ICONO = 40;

/**
 * Posiciones de los `total` íconos de un punto, en píxeles respecto de su ubicación.
 *
 * Uno solo va centrado; a partir de dos se reparten en un anillo cuyo radio crece con el
 * número de peligros, de modo que la separación entre vecinos sea siempre la misma y no se
 * solapen ni con dos ni con nueve. El primero va arriba, que es el de mayor nivel.
 *
 * `icon-offset` se multiplica por `icon-size`, así que la corona encoge y crece con el
 * símbolo sin necesidad de recalcular nada por zoom.
 */
function corona(total: number): [number, number][] {
  if (total <= 1) return [[0, 0]];
  const radio = DIAMETRO_ICONO / (2 * Math.sin(Math.PI / total));
  const redondear = (n: number) => Math.round(n * 10) / 10;
  return Array.from({ length: total }, (_, k) => {
    const angulo = -Math.PI / 2 + (2 * Math.PI * k) / total;
    return [redondear(radio * Math.cos(angulo)), redondear(radio * Math.sin(angulo))];
  });
}

/**
 * `icon-offset` de la ranura `k`, según cuántos peligros tenga el punto.
 *
 * Es un `match` sobre el total y no una cuenta con `["get","dx"]` porque **MapLibre no sabe
 * construir un array de dos números a partir de dos expresiones**: no hay forma de expresar
 * un par (x, y) calculado. `match`, en cambio, sí devuelve arrays literales, y el total ya
 * viaja en el feature.
 */
function desplazamientoRanura(k: number): maplibregl.ExpressionSpecification {
  // Los pares van envueltos en `["literal", …]`: un array suelto dentro de una expresión se
  // interpreta como llamada a función y MapLibre rechaza la capa entera —«Expression name
  // must be a string, but found number»— sin dibujar un solo símbolo.
  const literal = (par: [number, number]) => ["literal", par];
  const casos: unknown[] = [];
  for (let total = k + 1; total <= RANURAS; total++) {
    casos.push(total, literal(corona(total)[k]));
  }
  return [
    "match",
    ["coalesce", ["get", "clasificaciones"], 1],
    ...casos,
    literal([0, 0]),
  ] as unknown as maplibregl.ExpressionSpecification;
}

/** Ids de las capas de símbolo, una por ranura. */
const CAPAS_PELIGRO = Array.from({ length: RANURAS }, (_, k) => `ccpp-peligro-${k}`);

function filtroClusters(mostrarSinDato: boolean): maplibregl.ExpressionSpecification {
  const grupo: maplibregl.ExpressionSpecification = ["has", "point_count"];
  if (mostrarSinDato) return grupo;
  return ["all", grupo, [">", ["get", "clasif"], 0]];
}

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
  /**
   * Catálogo de peligros (`/api/peligros/tipos/`). De aquí salen los íconos que se registran
   * como imágenes del mapa y la leyenda de formas: el visor no conoce los peligros de antemano.
   */
  tipos: TipoPeligroApi[];
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
  { capas, puntos, tipos, ambitoAcotado },
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
  // Los centros poblados que no cumplen los filtros se pintan en gris por defecto: la ausencia
  // de dato es información, y esconderla haría leer «sin evaluar» como «sin peligro». Aun así se
  // puede apagar, porque con el filtro puesto son mayoría y tapan lo que se está buscando.
  const [mostrarSinDato, setMostrarSinDato] = useState(true);
  /**
   * SVG serializado de cada ícono, para rasterizarlo a las imágenes del mapa.
   *
   * Se leen del DOM de un contenedor oculto que React ya pinta, en vez de renderizarlos a texto
   * con `react-dom/server`: eso metería el renderizador de servidor entero en el bundle del
   * navegador para producir nueve cadenas.
   */
  const svgIconos = useRef<Record<string, string>>({});
  const cajaIconos = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const caja = cajaIconos.current;
    if (!caja) return;
    for (const t of tipos) {
      const svg = caja.querySelector<SVGSVGElement>(`[data-slug="${t.slug}"] svg`);
      if (svg) svgIconos.current[t.slug] = new XMLSerializer().serializeToString(svg);
    }
  }, [tipos]);

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
              // El número y el tamaño: clasificaciones que pasan los filtros. La página no puede
              // recortar la fuente —los que no cumplen se pintan en gris—, así que el recorte se
              // hace aquí, sumando lo que cada punto declara aportar.
              clasif: ["+", ["coalesce", ["get", "clasificaciones"], 0]],
              // Y el color, el peor nivel del grupo: un cluster no puede verse más benigno que
              // el centro poblado más expuesto que contiene.
              nivelMax: ["max", ["coalesce", ["get", "nivel"], 0]],
              // Desglose del grupo por nivel y por tipo. MapLibre solo sabe acumular escalares
              // que ya vengan en el feature, así que sin esto un círculo no puede decir de qué
              // está hecho — que es justo lo que hay que poder responder al pinchar uno.
              niv1: ["+", ["coalesce", ["get", "n1"], 0]],
              niv2: ["+", ["coalesce", ["get", "n2"], 0]],
              niv3: ["+", ["coalesce", ["get", "n3"], 0]],
              niv4: ["+", ["coalesce", ["get", "n4"], 0]],
              ...Object.fromEntries(
                tipos.map((t) => [
                  `t_${t.slug}`,
                  ["+", ["coalesce", ["get", `p_${t.slug}`], 0]],
                ])
              ),
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

          // Los sin clasificar, como punto liso y gris: no tienen tipo que dibujar, y darles un
          // ícono los haría parecer evaluados. Van debajo de todo.
          {
            id: "ccpp-sin-dato", type: "circle", source: "ccpp",
            filter: FILTRO_SIN_DATO,
            paint: {
              "circle-radius": 2.5,
              "circle-color": SIN_DATO,
              "circle-opacity": 0.75,
              "circle-stroke-width": 0.5,
              "circle-stroke-color": "#ffffff",
            },
          },
          {
            id: "ccpp-clusters", type: "circle", source: "ccpp",
            filter: filtroClusters(true),
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
            filter: filtroClusters(true),
            layout: {
              "text-field": NUMERO_CLUSTER,
              "text-font": ["Noto Sans Bold"],
              // Acompaña al radio para que el número no desborde los grupos pequeños.
              "text-size": ["step", ["get", "clasif"], 10, 100, 11, 1000, 12],
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

    // Red de seguridad: si un ícono no llegó a registrarse, MapLibre pediría esa imagen una vez
    // por punto y no dibujaría ninguno. Con un cuadrado blanco de 1 px el símbolo se degrada a
    // un punto liso y el mapa sigue siendo legible.
    map.on("styleimagemissing", (e) => {
      if (map.hasImage(e.id)) return;
      map.addImage(e.id, { width: 1, height: 1, data: new Uint8Array([255, 255, 255, 255]) });
    });

    // Popup con la ficha del centro poblado. El enlace al detalle no puede ser un <a> normal:
    // recargaría la SPA entera, así que se delega al router.
    // Sobre **todas** las ranuras: pinchar cualquiera de los íconos de la corona abre la ficha
    // del centro poblado, que es lo esperable cuando todos representan al mismo lugar.
    // Registrar el manejador antes de que las capas existan es correcto: MapLibre resuelve la
    // capa en el momento del evento, y estas se añaden tras rasterizar los íconos.
    map.on("click", CAPAS_PELIGRO, (e) => {
      const f = e.features?.[0];
      if (!f) return;
      const p = f.properties as Record<string, unknown>;

      const clasificados = leerClasificaciones(p.peligros);

      const nodo = document.createElement("div");
      nodo.className = "text-sm";
      nodo.innerHTML =
        `<div class="font-bold text-base">${p.nombre}</div>` +
        `<div class="text-ink-600 text-xs">${p.categoria || "s/c"} — ${p.distrito}, ${p.provincia}</div>` +
        `<div class="mt-2 text-xs">` +
        `<div>Altitud: <strong>${p.altitud != null ? `${formatNumber(Number(p.altitud))} msnm` : "s/d"}</strong></div>` +
        `</div>` +
        (clasificados.length
          ? `<div class="mt-2"><div class="text-xs font-semibold text-ink-900">Peligros clasificados:</div>` +
            `<ul class="text-xs mt-1 space-y-0.5">` +
            clasificados
              .map(
                (c) =>
                  `<li><span style="display:inline-block;width:8px;height:8px;border-radius:9999px;margin-right:6px;vertical-align:middle;background:${NIVEL_COLOR[c.n]}"></span>` +
                  `${c.p}: <strong>${NIVEL_LABEL[c.n]}</strong></li>`
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

    for (const capa of [...CAPAS_PELIGRO, "ccpp-clusters"]) {
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

  // --- Símbolos: forma = tipo de peligro, color = nivel --------------------------------------
  //
  // La capa `symbol` se añade **después** de registrar las imágenes, y no en el estilo inicial.
  // Un `icon-image` que apunta a una imagen todavía no registrada hace que MapLibre emita un
  // error por cada punto —8,968 líneas en consola— y no dibuje nada; con `styleimagemissing`
  // como red de seguridad, un ícono que falle cae en un punto liso en vez de desaparecer.
  useEffect(() => {
    const map = mapa.current;
    if (!map || !listo || !tipos.length) return;
    let cancelado = false;

    const svgPorSlug = Object.fromEntries(
      tipos.map((t) => [t.slug, svgIconos.current[t.slug] ?? ""])
    );

    registrarIconos(map, tipos, svgPorSlug).then(() => {
      if (cancelado || !mapa.current) return;
      cuandoListo(map, () => {
        if (map.getLayer(CAPAS_PELIGRO[0])) return;
        // Ancla de la corona: cuando los íconos rodean la ubicación en vez de ocuparla, el
        // centro queda vacío y, con centros poblados vecinos, deja de verse de qué corona es
        // cada ícono. Un punto diminuto marca dónde está el lugar de verdad.
        map.addLayer(
          {
            id: "ccpp-ancla",
            type: "circle",
            source: "ccpp",
            filter: ["all", FILTRO_SIMBOLOS, [">", ["get", "clasificaciones"], 1]],
            paint: {
              "circle-radius": 2,
              "circle-color": "#1A1A1A",
              "circle-opacity": 0.55,
              "circle-stroke-width": 1,
              "circle-stroke-color": "#ffffff",
            },
          },
          map.getLayer("ccpp-clusters") ? "ccpp-clusters" : undefined
        );
        // Una capa por ranura. MapLibre dibuja **un símbolo por capa y feature**, así que
        // mostrar los N peligros de un punto exige N capas leyendo N pares de propiedades;
        // no hay forma de que una sola capa itere sobre una lista.
        CAPAS_PELIGRO.forEach((id, k) => {
          map.addLayer(
            {
              id,
              type: "symbol",
              source: "ccpp",
              filter: ["all", FILTRO_SIMBOLOS, ["has", `s${k}`]],
              layout: {
                "icon-image": [
                  "concat",
                  "peligro-",
                  ["get", `s${k}`],
                  "-",
                  ["to-string", ["coalesce", ["get", `n_${k}`], 0]],
                ],
                "icon-offset": desplazamientoRanura(k),
                // Sin esto MapLibre descarta por colisión la mayoría de los símbolos y el
                // visor se ve medio vacío **sin emitir ningún error**: con 3,238 puntos en
                // Cusco, el motor de etiquetado deja pasar apenas unos cientos. Y con la
                // corona el problema se multiplica, porque los íconos de un mismo punto se
                // rozan por diseño.
                "icon-allow-overlap": true,
                "icon-ignore-placement": true,
                "icon-size": [
                  "interpolate", ["linear"], ["zoom"],
                  6, 0.42,
                  12, 0.75,
                  16, 1,
                ],
                // Los más graves por encima: donde se solapan, gana el que hay que ver.
                "symbol-sort-key": ["-", 4, ["coalesce", ["get", `n_${k}`], 0]],
              },
            },
            // Debajo de los grupos, que resumen más información.
            map.getLayer("ccpp-clusters") ? "ccpp-clusters" : undefined
          );
        });
      });
    });

    return () => {
      cancelado = true;
    };
  }, [listo, tipos]);

  // --- Color de los grupos --------------------------------------------------------------------
  useEffect(() => {
    const map = mapa.current;
    if (!map || !listo) return;
    cuandoListo(map, () => {
      // coalesce(…, 0) hace que "sin dato" sea un valor propio y no un nivel bajo. Un grupo no
      // puede verse más benigno que el centro poblado más expuesto que contiene.
      map.setPaintProperty("ccpp-clusters", "circle-color", [
        "match",
        ["coalesce", ["get", "nivelMax"], 0],
        1, NIVEL_COLOR[1],
        2, NIVEL_COLOR[2],
        3, NIVEL_COLOR[3],
        4, NIVEL_COLOR[4],
        SIN_DATO,
      ] as maplibregl.ExpressionSpecification);
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
      map.setPaintProperty("ccpp-sin-dato", "circle-stroke-width", base === "claro" ? 0.5 : 0.8);
    });
  }, [listo, base]);

  // --- Conmutador de los centros poblados sin clasificación ----------------------------------
  useEffect(() => {
    const map = mapa.current;
    if (!map || !listo) return;
    cuandoListo(map, () => {
      map.setLayoutProperty(
        "ccpp-sin-dato",
        "visibility",
        mostrarSinDato ? "visible" : "none"
      );
      for (const capa of ["ccpp-clusters", "ccpp-clusters-num"]) {
        map.setFilter(capa, filtroClusters(mostrarSinDato));
      }
    });
  }, [listo, mostrarSinDato]);

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
      {/* z-20: al abrirse, el panel llega hasta donde empieza la leyenda —que está en la misma
          esquina y va después en el DOM—, y esta le robaba los clics de la última casilla. Un
          desplegable que el usuario acaba de abrir manda sobre lo que hay debajo. */}
      <div className="absolute top-2 right-2 z-20" style={{ marginTop: 78 }}>
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

            <div className="text-[10px] uppercase tracking-wide text-ink-600 mt-3 mb-1 pt-2 border-t border-ink-300/40">
              Centros poblados
            </div>
            <label className="flex items-center gap-2 text-xs cursor-pointer">
              <input
                type="checkbox"
                checked={mostrarSinDato}
                onChange={(e) => setMostrarSinDato(e.target.checked)}
              />
              Mostrar sin clasificación
            </label>
          </div>
        )}
      </div>

      {/* Leyenda semáforo */}
      {/* bg-white/95: la escala de opacidad de Tailwind va de 5 en 5, así que un /92 no genera
          ninguna clase y la leyenda se queda sin fondo. */}
      <div className="absolute bottom-8 right-2 z-10 bg-white/95 rounded-lg shadow px-3 py-2 max-h-[70%] overflow-y-auto">
        {/* Cada canal del símbolo codifica una variable distinta y todas necesitan clave. */}
        <div className="text-[11px] font-semibold text-ink-900 mb-1">Color: nivel</div>
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

        {/* La forma es el canal nuevo: el ícono dice a qué está expuesto el lugar. Con varios
            peligros marcados se dibuja el de mayor nivel, y el popup los lista todos. */}
        <div className="text-[11px] font-semibold text-ink-900 mt-2 pt-2 border-t border-ink-300/40">
          Ícono: tipo de peligro
        </div>
        <div className="space-y-0.5 mt-1">
          {tipos.map((t) => {
            const Icono = iconoDe(t.icono);
            return (
              <div key={t.slug} className="flex items-center gap-1.5 text-[11px] text-ink-600">
                <Icono className="w-3 h-3 shrink-0" aria-hidden />
                {t.nombre}
              </div>
            );
          })}
        </div>

        {/* El número es la clave que más se malinterpreta: se lee como "cuántos pueblos hay". */}
        <div className="text-[11px] font-semibold text-ink-900 mt-2 pt-2 border-t border-ink-300/40">
          Grupos: número y tamaño
        </div>
        <div className="text-[10px] text-ink-600 mt-0.5 max-w-[9rem] leading-tight">
          Peligros clasificados del grupo. Un centro poblado aporta uno por cada peligro evaluado.
        </div>
        <div className="space-y-0.5 mt-1">
          {CLASES_CONTEO.map((c) => (
            <div key={c.desde} className="flex items-center gap-1.5 text-[11px] text-ink-600">
              <span className="w-[34px] flex justify-center shrink-0">
                <span
                  className="rounded-full border border-white bg-ink-300"
                  style={{ width: c.radio, height: c.radio }}
                />
              </span>
              {c.etiqueta}
            </div>
          ))}
        </div>
      </div>

      {/* Fuente de los SVG que se rasterizan como imágenes del mapa. Oculto y fuera del flujo:
          `display:none` impediría medir o serializar el nodo en algunos navegadores. */}
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
});

export default MapaPeligros;

/**
 * Las propiedades de una fuente GeoJSON agrupada tienen que ser escalares para sobrevivir al
 * worker de clustering, así que el desglose por peligro viaja serializado en `peligros`.
 *
 * Las claves son cortas —`s` slug, `p` nombre, `n` nivel— porque esta cadena se repite en 8,968
 * features y los nombres largos se notan en un payload de 2 MB.
 *
 * Ojo: antes esto se llamaba con `p.clasif`, que es una propiedad **de grupo** y no existe en un
 * punto suelto, y además esperaba unas claves `{peligro, nivel}` que el API nunca envió. El
 * resultado era que el popup siempre caía en «sin clasificación registrada», también sobre
 * centros poblados que sí la tenían, sin que nada fallara.
 */
function leerClasificaciones(valor: unknown): { s: string; p: string; n: Nivel }[] {
  if (typeof valor !== "string") return [];
  try {
    const lista = JSON.parse(valor);
    return Array.isArray(lista) ? lista : [];
  } catch {
    return [];
  }
}
