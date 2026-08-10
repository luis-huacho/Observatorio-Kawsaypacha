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
import type { Map as MapaMaplibre } from "maplibre-gl";
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

/** Identificador de la imagen registrada en el mapa para un tipo y un nivel. */
export function idImagen(slug: string, nivel: number): string {
  return `peligro-${slug}-${nivel}`;
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

/** Disco del color del nivel, anillo blanco y el glifo del peligro encima, en blanco. */
async function pintar(svg: string, color: string): Promise<ImageData> {
  const lado = LADO * 2;
  const lienzo = document.createElement("canvas");
  lienzo.width = lado;
  lienzo.height = lado;
  const ctx = lienzo.getContext("2d");
  if (!ctx) throw new Error("sin contexto 2d");

  const centro = lado / 2;
  const radio = centro - 3;
  ctx.beginPath();
  ctx.arc(centro, centro, radio, 0, Math.PI * 2);
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
