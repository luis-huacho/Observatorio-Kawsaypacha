import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { registrarProtocoloPmtiles } from "@/lib/pmtiles";
import { formatPct, formatSoles } from "@/lib/semaforo";
import CajaDistribucion from "./CajaDistribucion";
import Declaracion from "./Declaracion";
import type { CapaMapa, InversionMapa, InversionMapaFila, MetricaMapa } from "@/lib/types";

/**
 * Coroplético del PP 0068, por distrito o por provincia.
 *
 * **La regla que lo gobierna es ADR-D6**: se pinta el dinero que se puede atribuir al polígono
 * sin inventarlo, y lo que no se puede ubicar se declara al pie en vez de repartirse. Por eso
 * las trece capitales de provincia salen en gris a nivel distrital: su municipalidad es la
 * provincial, y su presupuesto es de toda la provincia.
 *
 * Es un componente propio y no `MapaPeligros` reutilizado, por el mismo motivo que `MapaPunto`:
 * aquel arrastraría clustering, buscador, medidor y una leyenda de tres bloques que aquí no
 * significan nada.
 *
 * Dos decisiones de implementación que no son cosméticas:
 *
 * - **El color se calcula en JavaScript y se inyecta como un `match` sobre el ubigeo**, no con
 *   un `step` sobre una propiedad del tile: los tiles solo traen geometría y códigos, el dinero
 *   llega por el API. Se descartó `feature-state`, que exigiría `promoteId` y volver a aplicar
 *   el estado en cada `sourcedata` — y que solo alcanza a los tiles ya cargados.
 * - **Las dos capas se montan a la vez y se conmuta su visibilidad.** Reconstruir la fuente al
 *   cambiar de nivel deja una ventana en la que el estilo aún no está cargado y las mutaciones
 *   de paint se pierden en silencio.
 */

const CENTRO: [number, number] = [-72.0, -13.5];
const ZOOM_INICIAL = 7;

/**
 * «Sin municipalidad» se pinta **en blanco**, no en un gris claro.
 *
 * No es cosmética: el primer intento usaba un gris muy claro y era indistinguible del tramo más
 * bajo de la rampa, justo la diferencia que este mapa existe para enseñar —«aquí no hay
 * municipalidad que ejecute» contra «aquí hay poco presupuesto»—. Con el blanco y un contorno
 * gris, un polígono vacío se lee como vacío.
 */
const SIN_MUNICIPALIDAD = "#FFFFFF";
/** Distinto del anterior: hay municipalidad, pero con PIM cero no hay avance que calcular. */
const NO_CALCULABLE = "#DCDCD8";

/** Rampa secuencial de la paleta (sky → mountain). Cinco tramos, uno por quintil. */
const RAMPA_DINERO = ["#D8EDF0", "#A8D8DF", "#5FBAC5", "#0095A4", "#00606B"];

/**
 * El % de ejecución usa la escala del semáforo del sitio y **cortes fijos**, no quintiles: es un
 * porcentaje, y con una escala relativa el mismo 90 % se pintaría de verde o de rojo según con
 * quién le tocara compartir la vista.
 */
const RAMPA_EJECUCION = ["#970A00", "#F57C15", "#EBB320", "#5BBB5D", "#009257"];
const CORTES_EJECUCION = [0.25, 0.5, 0.75, 0.9];

const CAPAS: Record<
  InversionMapa["nivel"],
  { slug: string; propiedad: string; etiqueta: string }
> = {
  distrital: { slug: "limites-distritales", propiedad: "UBIGEO", etiqueta: "Distrito" },
  provincial: { slug: "limites-provinciales", propiedad: "IDPROV", etiqueta: "Provincia" },
};

const METRICAS: { clave: MetricaMapa; etiqueta: string }[] = [
  { clave: "pia", etiqueta: "PIA" },
  { clave: "pim", etiqueta: "PIM" },
  { clave: "devengado", etiqueta: "Devengado" },
  { clave: "pct_ejecucion", etiqueta: "% de ejecución" },
];

/** El tramo (0-4) al que pertenece un valor, o -1 si no se puede calcular. */
function tramo(valor: number | null, cortes: number[]): number {
  if (valor === null) return -1;
  let i = 0;
  while (i < cortes.length && valor > cortes[i]) i += 1;
  return i;
}

function rangos(cortes: number[], metrica: MetricaMapa): string[] {
  const f = (v: number) => (metrica === "pct_ejecucion" ? formatPct(v) : formatSoles(v));
  return [
    `hasta ${f(cortes[0])}`,
    `${f(cortes[0])} – ${f(cortes[1])}`,
    `${f(cortes[1])} – ${f(cortes[2])}`,
    `${f(cortes[2])} – ${f(cortes[3])}`,
    `más de ${f(cortes[3])}`,
  ];
}

type Props = {
  datos: InversionMapa;
  /** Catálogo de `/api/mapas/capas/`: de ahí sale la URL de los .pmtiles de límites. */
  capas: CapaMapa[];
  metrica: MetricaMapa;
  onMetrica: (m: MetricaMapa) => void;
  onNivel: (n: InversionMapa["nivel"]) => void;
  /** Qué hacer al pulsar un polígono. La ruta decide: ficha o filtro de provincia. */
  onSeleccionar: (fila: InversionMapaFila) => void;
};

export default function MapaInversion({
  datos,
  capas,
  metrica,
  onMetrica,
  onNivel,
  onSeleccionar,
}: Props) {
  const contenedor = useRef<HTMLDivElement>(null);
  const mapa = useRef<maplibregl.Map | null>(null);
  const [listo, setListo] = useState(false);
  const [encima, setEncima] = useState<InversionMapaFila | null>(null);

  const porUbigeo = useMemo(
    () => new Map(datos.filas.map((f) => [f.ubigeo, f])),
    [datos.filas]
  );
  const cortes = metrica === "pct_ejecucion" ? CORTES_EJECUCION : datos.cortes[metrica];
  const rampa = metrica === "pct_ejecucion" ? RAMPA_EJECUCION : RAMPA_DINERO;

  // Las callbacks se leen desde los manejadores de MapLibre, que se registran una sola vez.
  const ultimo = useRef({ porUbigeo, onSeleccionar });
  ultimo.current = { porUbigeo, onSeleccionar };

  const urlDe = (slug: string) => capas.find((c) => c.slug === slug)?.url;

  // --- Construcción del mapa (una sola vez, con las dos capas montadas) -----------------------
  useEffect(() => {
    if (!contenedor.current || mapa.current) return;
    const urls = Object.values(CAPAS).map((c) => urlDe(c.slug));
    if (urls.some((u) => !u)) return; // el catálogo aún no ha llegado

    registrarProtocoloPmtiles();
    const map = new maplibregl.Map({
      container: contenedor.current,
      style: {
        version: 8,
        glyphs: "https://fonts.openmaptiles.org/{fontstack}/{range}.pbf",
        sources: Object.fromEntries(
          Object.entries(CAPAS).map(([nivel, c]) => [
            nivel,
            { type: "vector" as const, url: `pmtiles://${urlDe(c.slug)}` },
          ])
        ),
        layers: Object.entries(CAPAS).flatMap(([nivel, c]) => [
          {
            id: `${nivel}-fill`,
            type: "fill" as const,
            source: nivel,
            "source-layer": c.slug,
            paint: { "fill-color": SIN_MUNICIPALIDAD, "fill-opacity": 0.9 },
          },
          {
            id: `${nivel}-line`,
            type: "line" as const,
            source: nivel,
            "source-layer": c.slug,
            paint: { "line-color": "#8F8F8A", "line-width": 0.6, "line-opacity": 0.8 },
          },
        ]),
      },
      center: CENTRO,
      zoom: ZOOM_INICIAL,
      attributionControl: false,
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.addControl(
      new maplibregl.AttributionControl({
        compact: true,
        customAttribution: "INEI · límites distritales y provinciales",
      })
    );

    for (const nivel of Object.keys(CAPAS)) {
      const capa = `${nivel}-fill`;
      map.on("mousemove", capa, (e) => {
        const clave = CAPAS[nivel as InversionMapa["nivel"]].propiedad;
        const ubigeo = e.features?.[0]?.properties?.[clave] as string | undefined;
        map.getCanvas().style.cursor = ubigeo && ultimo.current.porUbigeo.has(ubigeo) ? "pointer" : "";
        setEncima(ubigeo ? ultimo.current.porUbigeo.get(ubigeo) ?? null : null);
      });
      map.on("mouseleave", capa, () => {
        map.getCanvas().style.cursor = "";
        setEncima(null);
      });
      map.on("click", capa, (e) => {
        const clave = CAPAS[nivel as InversionMapa["nivel"]].propiedad;
        const ubigeo = e.features?.[0]?.properties?.[clave] as string | undefined;
        const fila = ubigeo ? ultimo.current.porUbigeo.get(ubigeo) : undefined;
        if (fila) ultimo.current.onSeleccionar(fila);
      });
    }

    map.on("load", () => setListo(true));
    mapa.current = map;
    return () => {
      map.remove();
      mapa.current = null;
      setListo(false);
    };
    // `capas` es lo único que puede faltar en el primer render; el resto se aplica por efectos.
  }, [capas]);

  // --- Color y visibilidad ------------------------------------------------------------------
  useEffect(() => {
    const map = mapa.current;
    if (!map || !listo || !map.isStyleLoaded()) return;

    for (const [nivel, capa] of Object.entries(CAPAS)) {
      const visible = nivel === datos.nivel;
      for (const sufijo of ["fill", "line"]) {
        map.setLayoutProperty(`${nivel}-${sufijo}`, "visibility", visible ? "visible" : "none");
      }
      if (!visible) continue;

      const pares = datos.filas.flatMap((f) => {
        const t = tramo(f[metrica], cortes);
        return [f.ubigeo, t < 0 ? NO_CALCULABLE : rampa[t]];
      });
      map.setPaintProperty(
        `${nivel}-fill`,
        "fill-color",
        // `match` exige al menos una rama: sin filas, color plano de «sin municipalidad».
        pares.length
          ? (["match", ["get", capa.propiedad], ...pares, SIN_MUNICIPALIDAD] as never)
          : SIN_MUNICIPALIDAD
      );
    }
  }, [listo, datos, metrica, cortes, rampa]);

  const etiquetas = rangos(cortes, metrica);
  const nombreMetrica = METRICAS.find((m) => m.clave === metrica)?.etiqueta ?? "";

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div className="flex flex-wrap gap-1" role="group" aria-label="Métrica del mapa">
          {METRICAS.map((m) => (
            <button
              key={m.clave}
              type="button"
              onClick={() => onMetrica(m.clave)}
              aria-pressed={metrica === m.clave}
              className={`px-3 py-1.5 text-sm rounded border ${
                metrica === m.clave
                  ? "bg-sky-700 text-white border-sky-700"
                  : "bg-white text-ink-900 border-ink-300 hover:bg-mountain-100"
              }`}
            >
              {m.etiqueta}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm text-ink-600">
          Ver por:
          <select
            value={datos.nivel}
            onChange={(e) => onNivel(e.target.value as InversionMapa["nivel"])}
            className="control py-1.5"
          >
            <option value="distrital">Distrito</option>
            <option value="provincial">Provincia</option>
          </select>
        </label>
      </div>

      <div className="relative">
        <div ref={contenedor} className="h-[28rem] w-full rounded border border-ink-300" />
        {encima && (
          <div className="absolute top-3 left-3 bg-white/95 rounded shadow px-3 py-2 text-xs max-w-[16rem] pointer-events-none">
            <p className="font-semibold text-mountain-900">{encima.nombre}</p>
            <p className="text-ink-600 mb-1">
              {datos.nivel === "distrital" ? encima.entidad : `${encima.entidades} municipalidades`}
            </p>
            <dl className="grid grid-cols-2 gap-x-2">
              <dt className="text-ink-600">PIA</dt>
              <dd className="text-right font-mono">{formatSoles(encima.pia)}</dd>
              <dt className="text-ink-600">PIM</dt>
              <dd className="text-right font-mono">{formatSoles(encima.pim)}</dd>
              <dt className="text-ink-600">Devengado</dt>
              <dd className="text-right font-mono">{formatSoles(encima.devengado)}</dd>
              <dt className="text-ink-600">Ejecución</dt>
              <dd className="text-right font-mono">
                {encima.pct_ejecucion === null ? "—" : formatPct(encima.pct_ejecucion)}
              </dd>
            </dl>
          </div>
        )}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px] text-ink-600">
        <span className="font-semibold text-ink-900">{nombreMetrica}</span>
        {rampa.map((color, i) => (
          <span key={color} className="flex items-center gap-1.5">
            <span
              className="w-4 h-4 rounded-[3px] border border-ink-300 shrink-0"
              style={{ backgroundColor: color }}
            />
            {etiquetas[i]}
          </span>
        ))}
        <span className="flex items-center gap-1.5">
          <span
            className="w-4 h-4 rounded-[3px] border border-ink-300 shrink-0"
            style={{ backgroundColor: SIN_MUNICIPALIDAD }}
          />
          sin municipalidad ({datos.poligonos.sin_dato})
        </span>
      </div>

      {/* El reparto, que es lo que el color no puede enseñar: los quintiles son la escala
          correcta para un mapa, pero su último tramo se traga la cola. Va aquí y no en
          `Inversion.tsx` para quedar pegada a la leyenda que explica, y antes de los pies, que
          hablan de lo que NO se pinta. */}
      <CajaDistribucion
        caja={datos.distribucion[metrica]}
        metrica={metrica}
        unidad={CAPAS[datos.nivel].etiqueta.toLowerCase()}
        etiquetaMetrica={nombreMetrica}
      />
      <Declaracion>{datos.distribucion[metrica].frase}</Declaracion>

      {metrica === "pct_ejecucion" && datos.es_parcial && (
        // Se repite aquí y no solo arriba porque este mapa se cita suelto, fuera de la página.
        <p className="text-xs text-ink-600 mt-2 border-l-2 border-level-2 pl-3">
          El ejercicio {datos.anio} va al corte {datos.corte_legible || datos.corte}, pero el % se
          calcula contra un PIM anual: un 50 % a mitad de año no es media ejecución perdida.
        </p>
      )}

      {metrica !== "pct_ejecucion" && (
        <p className="text-[11px] text-ink-600 mt-2">
          Los cinco tramos son quintiles de esta vista: al acotar por provincia, un mismo distrito
          puede cambiar de tono.
        </p>
      )}

      {datos.no_ubicado.entidades > 0 && (
        <p className="text-xs text-ink-600 mt-2 border-l-2 border-earth-500 pl-3">
          <strong className="text-ink-900">
            {formatSoles(datos.no_ubicado[metrica === "pct_ejecucion" ? "pim" : metrica])}
          </strong>{" "}
          no aparecen en el mapa. {datos.no_ubicado.motivo}
        </p>
      )}
      {datos.poligonos.sin_dato > 0 && (
        <p className="text-xs text-ink-600 mt-1.5 border-l-2 border-ink-300 pl-3">
          {datos.poligonos.motivo}
        </p>
      )}
    </div>
  );
}
