/**
 * Controles del visor: buscador de lugares, medición y export PNG, sobre la interfaz `IControl`
 * de MapLibre. La leyenda y el conmutador de capas viven en el componente React porque son
 * UI pura y se estilan con Tailwind.
 */
import type { IControl, Map as MapLibreMap } from "maplibre-gl";
import maplibregl from "maplibre-gl";
import type { CentroPoblado } from "@/lib/types";

const RADIO_TIERRA = 6378137;
const toRad = (d: number) => (d * Math.PI) / 180;

function distanciaHaversine([lon1, lat1]: number[], [lon2, lat2]: number[]): number {
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * RADIO_TIERRA * Math.asin(Math.sqrt(h));
}

/** Área de un polígono sobre la esfera; la misma fórmula que usaba la versión Leaflet. */
function areaEsferica(puntos: number[][]): number {
  const n = puntos.length;
  if (n < 3) return 0;
  let a = 0;
  for (let i = 0; i < n; i++) {
    const [lon1, lat1] = puntos[i];
    const [lon2, lat2] = puntos[(i + 1) % n];
    a += toRad(lon2 - lon1) * (2 + Math.sin(toRad(lat1)) + Math.sin(toRad(lat2)));
  }
  return Math.abs((a * RADIO_TIERRA * RADIO_TIERRA) / 2);
}

const fmtDist = (m: number) => (m >= 1000 ? `${(m / 1000).toFixed(2)} km` : `${Math.round(m)} m`);
const fmtArea = (m2: number) =>
  m2 >= 1e6 ? `${(m2 / 1e6).toFixed(2)} km²` : `${(m2 / 10000).toFixed(2)} ha`;

/** Contenedor con el mismo aspecto que los grupos de botones nativos de MapLibre. */
function grupo(): HTMLDivElement {
  const div = document.createElement("div");
  div.className = "maplibregl-ctrl maplibregl-ctrl-group";
  return div;
}

function boton(titulo: string, contenido: string): HTMLButtonElement {
  const b = document.createElement("button");
  b.type = "button";
  b.title = titulo;
  b.setAttribute("aria-label", titulo);
  b.innerHTML = contenido;
  b.style.fontSize = "15px";
  return b;
}

/** Vuelve a la vista inicial de la región. */
export class VistaInicialControl implements IControl {
  private contenedor?: HTMLDivElement;

  constructor(private centro: [number, number], private zoom: number) {}

  onAdd(map: MapLibreMap) {
    this.contenedor = grupo();
    const b = boton("Vista inicial", "⌂");
    b.addEventListener("click", () => map.flyTo({ center: this.centro, zoom: this.zoom }));
    this.contenedor.appendChild(b);
    return this.contenedor;
  }

  onRemove() {
    this.contenedor?.remove();
  }
}

/**
 * Buscador de centros poblados sobre el mapa. Filtra por nombre sobre los datos ya cargados
 * (sin geocoder externo) y, al elegir un resultado, vuela al punto y lo resalta.
 */
export class BuscarLugarControl implements IControl {
  private contenedor?: HTMLDivElement;
  private marcador?: maplibregl.Marker;

  constructor(private ccpp: CentroPoblado[]) {}

  onAdd(map: MapLibreMap) {
    const conCoords = this.ccpp.filter((c) => c.lat != null && c.lon != null);

    const div = document.createElement("div");
    div.className = "maplibregl-ctrl maplibregl-ctrl-group";
    div.style.cssText = "background:#fff;overflow:hidden";

    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = "Buscar centro poblado…";
    input.style.cssText =
      "border:none;outline:none;padding:7px 9px;width:210px;font:13px system-ui;display:block";

    const lista = document.createElement("ul");
    lista.style.cssText =
      "list-style:none;margin:0;padding:0;max-height:220px;overflow:auto;background:#fff";

    const render = () => {
      lista.innerHTML = "";
      const term = input.value.trim().toLowerCase();
      if (term.length < 2) return;
      for (const c of conCoords.filter((x) => x.nombre.toLowerCase().includes(term)).slice(0, 8)) {
        const li = document.createElement("li");
        li.style.cssText =
          "padding:6px 9px;cursor:pointer;border-top:1px solid #eee;font:12px system-ui";
        li.innerHTML = `<strong>${c.nombre}</strong><br><span style="color:#666">${c.distrito}, ${c.provincia}</span>`;
        li.addEventListener("mouseover", () => (li.style.background = "#E5F4EE"));
        li.addEventListener("mouseout", () => (li.style.background = "#fff"));
        li.addEventListener("click", () => {
          const destino: [number, number] = [c.lon as number, c.lat as number];
          map.flyTo({ center: destino, zoom: 13 });
          this.marcador?.remove();
          this.marcador = new maplibregl.Marker({ color: "#0B3B26" })
            .setLngLat(destino)
            .setPopup(
              new maplibregl.Popup({ offset: 24 }).setHTML(
                `<strong>${c.nombre}</strong><br>${c.distrito}, ${c.provincia}`
              )
            )
            .addTo(map);
          this.marcador.togglePopup();
          lista.innerHTML = "";
          input.value = c.nombre;
        });
        lista.appendChild(li);
      }
    };

    input.addEventListener("input", render);
    // Sin esto, escribir sobre el mapa dispara los atajos de teclado de MapLibre.
    div.addEventListener("keydown", (e) => e.stopPropagation());
    div.addEventListener("click", (e) => e.stopPropagation());

    div.append(input, lista);
    this.contenedor = div;
    return div;
  }

  onRemove() {
    this.marcador?.remove();
    this.contenedor?.remove();
  }
}

/**
 * Medición de distancia y área. Clic para añadir vértices; doble clic para terminar.
 * La geometría se dibuja en una fuente GeoJSON propia en lugar de capas sueltas.
 */
export class MedirControl implements IControl {
  private contenedor?: HTMLDivElement;
  private etiqueta?: HTMLDivElement;
  private mapa?: MapLibreMap;
  private puntos: number[][] = [];
  private activo = false;
  private btn?: HTMLButtonElement;

  private readonly SRC = "medicion";

  onAdd(map: MapLibreMap) {
    this.mapa = map;

    // Los controles se añaden justo después de construir el mapa, cuando el estilo todavía no
    // está cargado y addSource() lanza. Se espera al evento de carga.
    if (map.isStyleLoaded()) this.crearCapas(map);
    else map.once("load", () => this.crearCapas(map));

    // Panel de resultados, anclado abajo a la izquierda sobre el mapa.
    const etiqueta = document.createElement("div");
    etiqueta.style.cssText =
      "position:absolute;left:10px;bottom:34px;z-index:2;background:rgba(255,255,255,0.92);" +
      "padding:6px 10px;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,0.2);" +
      "font:12px system-ui;color:#1A1A1A;display:none";
    map.getContainer().appendChild(etiqueta);
    this.etiqueta = etiqueta;

    this.contenedor = grupo();
    this.btn = boton("Medir distancia / área", "📐");
    this.btn.addEventListener("click", () => this.alternar(!this.activo));
    this.contenedor.appendChild(this.btn);
    return this.contenedor;
  }

  private crearCapas(map: MapLibreMap) {
    if (map.getSource(this.SRC)) return;

    map.addSource(this.SRC, { type: "geojson", data: vacio() });
    map.addLayer({
      id: "medicion-area",
      type: "fill",
      source: this.SRC,
      filter: ["==", "$type", "Polygon"],
      paint: { "fill-color": "#B8753C", "fill-opacity": 0.15 },
    });
    map.addLayer({
      id: "medicion-linea",
      type: "line",
      source: this.SRC,
      filter: ["!=", "$type", "Point"],
      paint: { "line-color": "#7A4A28", "line-width": 2, "line-dasharray": [2, 2] },
    });
    map.addLayer({
      id: "medicion-vertices",
      type: "circle",
      source: this.SRC,
      filter: ["==", "$type", "Point"],
      paint: {
        "circle-radius": 4,
        "circle-color": "#B8753C",
        "circle-stroke-color": "#7A4A28",
        "circle-stroke-width": 1,
      },
    });
  }

  onRemove() {
    this.alternar(false);
    const map = this.mapa;
    if (map) {
      for (const id of ["medicion-area", "medicion-linea", "medicion-vertices"]) {
        if (map.getLayer(id)) map.removeLayer(id);
      }
      if (map.getSource(this.SRC)) map.removeSource(this.SRC);
    }
    this.etiqueta?.remove();
    this.contenedor?.remove();
  }

  private onClick = (e: maplibregl.MapMouseEvent) => {
    this.puntos.push([e.lngLat.lng, e.lngLat.lat]);
    this.redibujar();
  };

  private onDblClick = (e: maplibregl.MapMouseEvent) => {
    e.preventDefault();
    this.alternar(false);
  };

  private alternar(v: boolean) {
    const map = this.mapa;
    if (!map) return;
    this.activo = v;
    if (v) {
      map.getCanvas().style.cursor = "crosshair";
      map.on("click", this.onClick);
      map.on("dblclick", this.onDblClick);
      map.doubleClickZoom.disable();
      if (this.btn) this.btn.style.background = "#5BBB5D";
    } else {
      map.getCanvas().style.cursor = "";
      map.off("click", this.onClick);
      map.off("dblclick", this.onDblClick);
      map.doubleClickZoom.enable();
      if (this.btn) this.btn.style.background = "";
    }
  }

  private limpiar = () => {
    this.puntos = [];
    this.redibujar();
  };

  private redibujar() {
    const map = this.mapa;
    if (!map) return;

    const features: GeoJSON.Feature[] = this.puntos.map((p) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: p },
      properties: {},
    }));
    if (this.puntos.length >= 3) {
      features.push({
        type: "Feature",
        geometry: { type: "Polygon", coordinates: [[...this.puntos, this.puntos[0]]] },
        properties: {},
      });
    } else if (this.puntos.length === 2) {
      features.push({
        type: "Feature",
        geometry: { type: "LineString", coordinates: this.puntos },
        properties: {},
      });
    }

    const src = map.getSource(this.SRC) as maplibregl.GeoJSONSource | undefined;
    src?.setData({ type: "FeatureCollection", features });

    this.actualizarEtiqueta();
  }

  private actualizarEtiqueta() {
    const div = this.etiqueta;
    if (!div) return;
    if (this.puntos.length === 0) {
      div.style.display = "none";
      div.innerHTML = "";
      return;
    }
    let d = 0;
    for (let i = 1; i < this.puntos.length; i++) {
      d += distanciaHaversine(this.puntos[i - 1], this.puntos[i]);
    }
    const a = this.puntos.length >= 3 ? areaEsferica(this.puntos) : 0;

    div.style.display = "block";
    div.innerHTML =
      `<div style="font-weight:600;margin-bottom:2px">Medición</div>` +
      `<div>Distancia: <strong>${fmtDist(d)}</strong></div>` +
      (a > 0 ? `<div>Área: <strong>${fmtArea(a)}</strong></div>` : "") +
      `<div style="margin-top:3px;color:#888;font-size:10px">Doble clic para terminar</div>` +
      `<button type="button" style="color:#007480;font-size:11px;background:none;border:none;padding:0;cursor:pointer">Limpiar</button>`;
    div.querySelector("button")?.addEventListener("click", this.limpiar);
  }
}

/**
 * Devuelve la vista actual del mapa como data URL PNG. MapLibre pinta todo (mapa base incluido)
 * en un único canvas WebGL, así que basta leerlo — no hace falta `html-to-image`. Requiere que
 * el mapa se haya creado con `preserveDrawingBuffer: true`.
 *
 * Lo usan el botón de descarga del propio mapa y la ayuda memoria imprimible.
 */
export function capturarPNG(map: MapLibreMap): Promise<string> {
  return new Promise((resolve, reject) => {
    // Forzar un repintado antes de leer el buffer, si no puede salir en blanco.
    map.triggerRepaint();
    map.once("render", () => {
      // El fallo ocurre en este callback, no en la llamada: si el mapa base no envía cabeceras
      // CORS, sus teselas contaminan el canvas y toDataURL lanza SecurityError. Los cuatro
      // bases actuales lo permiten, pero las capas son administrables.
      try {
        resolve(map.getCanvas().toDataURL("image/png"));
      } catch (err) {
        reject(err);
      }
    });
  });
}

/** Descarga la vista actual como PNG. */
export class DescargarPNGControl implements IControl {
  private contenedor?: HTMLDivElement;

  onAdd(map: MapLibreMap) {
    this.contenedor = grupo();
    const b = boton("Descargar vista (PNG)", "⤓");
    b.style.fontWeight = "bold";
    b.addEventListener("click", async () => {
      const previo = b.innerHTML;
      b.innerHTML = "…";
      try {
        const enlace = document.createElement("a");
        enlace.download = "observatorio-mapa-cusco.png";
        enlace.href = await capturarPNG(map);
        enlace.click();
      } catch (err) {
        console.error("No se pudo exportar el PNG:", err);
        window.alert(
          "No se pudo exportar la imagen: el mapa base actual no permite descargar la vista. " +
            "Prueba con otro mapa base."
        );
      } finally {
        b.innerHTML = previo;
      }
    });
    this.contenedor.appendChild(b);
    return this.contenedor;
  }

  onRemove() {
    this.contenedor?.remove();
  }
}

function vacio(): GeoJSON.FeatureCollection {
  return { type: "FeatureCollection", features: [] };
}
