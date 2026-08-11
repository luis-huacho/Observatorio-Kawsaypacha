/**
 * Símbolos del visor: **la forma dice el tipo de peligro y el color dice el nivel**.
 *
 * Antes el mapa codificaba nivel en el color y población en el tamaño. La población salió
 * (ADR-A17): la fuente la trae, pero 948 de los 8,968 centros poblados valen 0 y la mediana es
 * 17 habitantes, así que como escala dejaba invisible justo a la mayoría. El canal que quedó
 * libre lo ocupa el tipo, que es lo que el usuario está filtrando.
 *
 * Qué peligro usa qué ícono **lo decide el API** (`TipoPeligro.icono`, editable en el admin).
 * Este módulo solo sabe dibujar los nombres que conoce, y cae en un ícono genérico si el admin
 * escribe uno que no está: un catálogo mal escrito no puede dejar el mapa en blanco.
 */
import {
  Activity,
  CloudRain,
  Flame,
  Mountain,
  Snowflake,
  SunDim,
  ThermometerSnowflake,
  TriangleAlert,
  Waves,
  Wind,
  type LucideIcon,
} from "lucide-react";
import type { ExpressionSpecification, Map as MapaMaplibre } from "maplibre-gl";
import { NIVEL_COLOR } from "./semaforo";
import type { Nivel, TipoPeligroApi } from "./types";

/**
 * Registro por nombre lucide en kebab-case, que es como viaja en el API.
 *
 * Se importan uno a uno a propósito: `import { icons } from "lucide-react"` mete las ~1,500
 * de la librería en el bundle.
 */
export const ICONOS: Record<string, LucideIcon> = {
  activity: Activity,
  snowflake: Snowflake,
  "thermometer-snowflake": ThermometerSnowflake,
  wind: Wind,
  "sun-dim": SunDim,
  "cloud-rain": CloudRain,
  waves: Waves,
  flame: Flame,
  mountain: Mountain,
};

export const ICONO_GENERICO = TriangleAlert;

export function iconoDe(nombre: string | undefined): LucideIcon {
  return (nombre && ICONOS[nombre]) || ICONO_GENERICO;
}

/**
 * Ranuras de la corona: un ícono por peligro del centro poblado.
 *
 * Nueve, el catálogo entero, igual que en el backend. Antes se dibujaba **solo el de mayor
 * nivel** y los demás quedaban escondidos en el popup — con 3.4 peligros de media por lugar,
 * el mapa ocultaba la mayor parte de lo evaluado.
 */
export const RANURAS = 9;

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
export function corona(total: number): [number, number][] {
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
export function desplazamientoRanura(k: number): ExpressionSpecification {
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
  ] as unknown as ExpressionSpecification;
}

/** Identificador de la imagen registrada en el mapa para un tipo y un nivel. */
export function idImagen(slug: string, nivel: number): string {
  return `peligro-${slug}-${nivel}`;
}

/**
 * Símbolo de la capa de emergencias. **Uno solo para toda la capa**, y a propósito fuera del
 * juego `peligro-*`.
 *
 * Comparte mapa con la exposición y son ejes que no se mezclan —una cuenta lo ocurrido por
 * distrito, la otra a qué está expuesto cada centro poblado—, así que se distingue en los tres
 * canales a la vez: fondo **cuadrado** en vez de círculo, color **fijo** fuera de la escala de
 * niveles, y un ícono que no es ninguno de los nueve peligros. Si compartiera cualquiera de
 * los tres, un ícono de emergencia sobre un distrito se leería como un décimo peligro o como
 * un nivel más.
 */
export const ID_EMERGENCIAS = "emergencias-distrito";
const COLOR_EMERGENCIAS = "#0B3B26"; // mountain-900, ausente de la escala de niveles

/** Registra el símbolo de emergencias. `svg` es el glifo serializado, como en los peligros. */
export async function registrarIconoEmergencias(
  mapa: MapaMaplibre,
  svg: string
): Promise<void> {
  if (!svg || mapa.hasImage(ID_EMERGENCIAS)) return;
  try {
    const datos = await pintar(svg, COLOR_EMERGENCIAS, "cuadrado");
    if (!mapa.getCanvas() || mapa.hasImage(ID_EMERGENCIAS)) return;
    mapa.addImage(ID_EMERGENCIAS, datos, { pixelRatio: 2 });
  } catch {
    // Igual que con los peligros: `styleimagemissing` deja un punto liso en su lugar.
  }
}

const LADO = 44; // px del bitmap; se dibuja a 2x y se declara `pixelRatio: 2`.
const PROPORCION_GLIFO = 0.52;

/**
 * Registra en el mapa una imagen por cada combinación tipo × nivel (9 × 4 = 36).
 *
 * Se rasteriza en vez de usar imágenes SDF —que permitirían recolorear una sola por tipo con
 * `icon-color`— porque SDF resuelve mal los íconos de **trazo** como los de lucide: adelgaza
 * el contorno hasta hacerlo ilegible al tamaño de un punto de mapa. Con 36 bitmaps de 88×88 el
 * coste es despreciable y el control sobre el disco, el anillo y el grosor es total.
 *
 * @param svgPorSlug SVG serializado de cada tipo, tal como lo pinta React. Se pasa desde el
 *   componente en vez de generarlo aquí para no arrastrar `react-dom/server` al bundle.
 */
export async function registrarIconos(
  mapa: MapaMaplibre,
  tipos: TipoPeligroApi[],
  svgPorSlug: Record<string, string>
): Promise<void> {
  await Promise.all(
    tipos.flatMap((tipo) =>
      ([1, 2, 3, 4] as Nivel[]).map(async (nivel) => {
        const id = idImagen(tipo.slug, nivel);
        if (mapa.hasImage(id)) return;
        const svg = svgPorSlug[tipo.slug];
        if (!svg) return;
        try {
          const datos = await pintar(svg, NIVEL_COLOR[nivel]);
          // Entre el `await` y aquí el usuario puede haber cambiado de página.
          if (!mapa.getCanvas() || mapa.hasImage(id)) return;
          mapa.addImage(id, datos, { pixelRatio: 2 });
        } catch {
          // Un ícono que no rasteriza no puede tumbar el visor: `styleimagemissing` de
          // MapaPeligros pone un punto liso en su lugar.
        }
      })
    )
  );
}

/**
 * Fondo del color indicado, anillo blanco y el glifo encima, en blanco.
 *
 * La `forma` es lo que separa los dos ejes de un vistazo: los peligros van en **disco** y las
 * emergencias en **cuadrado redondeado**.
 */
async function pintar(
  svg: string,
  color: string,
  forma: "disco" | "cuadrado" = "disco"
): Promise<ImageData> {
  const lado = LADO * 2;
  const lienzo = document.createElement("canvas");
  lienzo.width = lado;
  lienzo.height = lado;
  const ctx = lienzo.getContext("2d");
  if (!ctx) throw new Error("sin contexto 2d");

  const centro = lado / 2;
  const radio = centro - 3;
  ctx.beginPath();
  if (forma === "disco") {
    ctx.arc(centro, centro, radio, 0, Math.PI * 2);
  } else {
    // Lado algo menor que el diámetro para que los dos símbolos pesen visualmente parecido: a
    // igual medida, un cuadrado ocupa un tercio más de área que su círculo inscrito.
    const l = radio * 1.72;
    ctx.roundRect(centro - l / 2, centro - l / 2, l, l, radio * 0.42);
  }
  ctx.fillStyle = color;
  ctx.fill();
  ctx.lineWidth = 3;
  ctx.strokeStyle = "#ffffff";
  ctx.stroke();

  const glifo = await cargarSvg(svg);
  const tam = lado * PROPORCION_GLIFO;
  ctx.drawImage(glifo, (lado - tam) / 2, (lado - tam) / 2, tam, tam);

  return ctx.getImageData(0, 0, lado, lado);
}

function cargarSvg(svg: string): Promise<HTMLImageElement> {
  return new Promise((resolver, rechazar) => {
    const img = new Image();
    // `encodeURIComponent` y no `btoa`: los SVG de lucide son ASCII hoy, pero `btoa` revienta
    // con cualquier carácter fuera de latin-1 y el fallo sería un ícono en blanco sin más.
    img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
    img.onload = () => resolver(img);
    img.onerror = () => rechazar(new Error("SVG ilegible"));
  });
}
