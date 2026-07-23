import { useEffect, useMemo } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, Tooltip, LayersControl, GeoJSON, ScaleControl, useMap } from "react-leaflet";
import L from "leaflet";
import type { Layer, PathOptions } from "leaflet";
import type { Feature } from "geojson";
import type { CentroPoblado, ClasificacionPeligro, Nivel } from "@/lib/types";
import { NIVEL_COLOR, NIVEL_LABEL, formatNumber } from "@/lib/semaforo";
import { useJsonData } from "@/lib/useJsonData";
import { BuscarLugarControl, MedirControl, DescargarPNGControl } from "@/components/MapaControles";
import { Link } from "react-router-dom";

type Props = {
  ccpp: CentroPoblado[];
  peligros: ClasificacionPeligro[];
  tipoPeligroFiltro: string | null;
};

type CapaGeo = {
  type: "FeatureCollection";
  features: Feature[];
};

// Centro aproximado de Cusco
const CENTER: [number, number] = [-13.5, -72.0];
const ZOOM_INICIAL = 8;

// Estilos de las capas geográficas (paleta del proyecto)
const ESTILO_LAGUNAS: PathOptions = { color: "#007480", weight: 1, fillColor: "#0095A4", fillOpacity: 0.55 };
const ESTILO_RIOS: PathOptions = { color: "#007480", weight: 2, opacity: 0.85 };
const ESTILO_NEVADOS: PathOptions = { color: "#7A93A6", weight: 1, fillColor: "#CFE4F2", fillOpacity: 0.7 };

function bindNombre(feature: Feature | undefined, layer: Layer) {
  const nombre = (feature?.properties as { nombre?: string } | undefined)?.nombre;
  if (nombre) layer.bindTooltip(nombre, { sticky: true });
}

/** Crea un botón de control Leaflet con un ícono y una acción. */
function useBotonControl(
  posicion: L.ControlPosition,
  titulo: string,
  html: string,
  onClick: (map: L.Map) => void,
) {
  const map = useMap();
  useEffect(() => {
    const ctrl = new L.Control({ position: posicion });
    ctrl.onAdd = () => {
      const div = L.DomUtil.create("div", "leaflet-bar leaflet-control");
      const a = L.DomUtil.create("a", "", div) as HTMLAnchorElement;
      a.href = "#";
      a.title = titulo;
      a.setAttribute("aria-label", titulo);
      a.innerHTML = html;
      a.style.fontSize = "16px";
      a.style.fontWeight = "bold";
      L.DomEvent.disableClickPropagation(div);
      L.DomEvent.on(a, "click", (e) => {
        L.DomEvent.preventDefault(e);
        onClick(map);
      });
      return div;
    };
    ctrl.addTo(map);
    return () => {
      ctrl.remove();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map]);
  return null;
}

/** Botón: volver a la vista inicial de la región. */
function VistaInicialControl() {
  return useBotonControl("topleft", "Vista inicial (toda la región)", "⌂", (map) => {
    map.setView(CENTER, ZOOM_INICIAL);
  });
}

/** Botón: pantalla completa del mapa (API nativa del navegador). */
function PantallaCompletaControl() {
  return useBotonControl("topleft", "Pantalla completa", "⛶", (map) => {
    const el = map.getContainer();
    if (!document.fullscreenElement) {
      el.requestFullscreen?.();
    } else {
      document.exitFullscreen?.();
    }
    window.setTimeout(() => map.invalidateSize(), 250);
  });
}

/** Leyenda de niveles de exposición (esquina inferior derecha). */
function LeyendaControl() {
  const map = useMap();
  useEffect(() => {
    const ctrl = new L.Control({ position: "bottomright" });
    ctrl.onAdd = () => {
      const div = L.DomUtil.create("div", "leaflet-control");
      div.style.background = "rgba(255,255,255,0.92)";
      div.style.padding = "8px 10px";
      div.style.borderRadius = "8px";
      div.style.boxShadow = "0 1px 4px rgba(0,0,0,0.2)";
      div.style.font = "11px/1.4 system-ui, sans-serif";
      div.style.color = "#1A1A1A";
      const filas = ([1, 2, 3, 4] as Nivel[])
        .map(
          (n) =>
            `<div style="display:flex;align-items:center;gap:6px;margin-top:2px">
               <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:${NIVEL_COLOR[n]}"></span>
               <span>${NIVEL_LABEL[n]}</span>
             </div>`,
        )
        .join("");
      div.innerHTML = `<div style="font-weight:600;margin-bottom:2px">Nivel de exposición</div>${filas}`;
      return div;
    };
    ctrl.addTo(map);
    return () => {
      ctrl.remove();
    };
  }, [map]);
  return null;
}

export default function MapaPeligros({ ccpp, peligros, tipoPeligroFiltro }: Props) {
  // Para cada CCPP, buscar el máximo nivel del peligro filtrado (o de todos)
  const ccppNivel = useMemo(() => {
    const map = new Map<string, Nivel | null>();
    for (const c of ccpp) {
      if (c.lat == null || c.lon == null) continue;
      map.set(c.codigo, null);
    }
    for (const p of peligros) {
      if (tipoPeligroFiltro && p.peligro !== tipoPeligroFiltro) continue;
      const cur = map.get(p.codigo_ccpp);
      if (cur === undefined) continue; // CCPP sin coords
      if (cur == null || p.nivel > cur) map.set(p.codigo_ccpp, p.nivel as Nivel);
    }
    return map;
  }, [ccpp, peligros, tipoPeligroFiltro]);

  const peligrosByCcpp = useMemo(() => {
    const map = new Map<string, ClasificacionPeligro[]>();
    for (const p of peligros) {
      if (!map.has(p.codigo_ccpp)) map.set(p.codigo_ccpp, []);
      map.get(p.codigo_ccpp)!.push(p);
    }
    return map;
  }, [peligros]);

  // Capas geográficas de prueba (geoJSON). En Fase 1 se reemplazan por las oficiales.
  const lagunas = useJsonData<CapaGeo>("/data/geo/lagunas.demo.geojson");
  const rios = useJsonData<CapaGeo>("/data/geo/rios.demo.geojson");
  const nevados = useJsonData<CapaGeo>("/data/geo/nevados.demo.geojson");

  return (
    <MapContainer
      center={CENTER}
      zoom={ZOOM_INICIAL}
      scrollWheelZoom={true}
      className="w-full h-full rounded-lg"
      preferCanvas={true}
    >
      {/* Herramientas del visor */}
      <ScaleControl position="bottomleft" imperial={false} />
      <VistaInicialControl />
      <PantallaCompletaControl />
      <MedirControl />
      <DescargarPNGControl />
      <BuscarLugarControl ccpp={ccpp} />
      <LeyendaControl />

      <LayersControl position="topright">
        {/* Mapas base */}
        <LayersControl.BaseLayer checked name="Mapa claro">
          <TileLayer
            crossOrigin="anonymous"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
            url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
          />
        </LayersControl.BaseLayer>
        <LayersControl.BaseLayer name="Satélite">
          <TileLayer
            crossOrigin="anonymous"
            attribution='Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics'
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
          />
        </LayersControl.BaseLayer>
        <LayersControl.BaseLayer name="OpenStreetMap">
          <TileLayer
            crossOrigin="anonymous"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
        </LayersControl.BaseLayer>

        {/* Capas geográficas */}
        <LayersControl.Overlay checked name="Lagunas">
          {lagunas.status === "ok" ? (
            <GeoJSON key="lagunas" data={lagunas.data} style={() => ESTILO_LAGUNAS} onEachFeature={bindNombre} />
          ) : (
            <span />
          )}
        </LayersControl.Overlay>
        <LayersControl.Overlay checked name="Ríos">
          {rios.status === "ok" ? (
            <GeoJSON key="rios" data={rios.data} style={() => ESTILO_RIOS} onEachFeature={bindNombre} />
          ) : (
            <span />
          )}
        </LayersControl.Overlay>
        <LayersControl.Overlay checked name="Nevados">
          {nevados.status === "ok" ? (
            <GeoJSON key="nevados" data={nevados.data} style={() => ESTILO_NEVADOS} onEachFeature={bindNombre} />
          ) : (
            <span />
          )}
        </LayersControl.Overlay>
      </LayersControl>
      {ccpp.map((c) => {
        if (c.lat == null || c.lon == null) return null;
        const nivel = ccppNivel.get(c.codigo);
        const color = nivel ? NIVEL_COLOR[nivel] : "#BDBDBD";
        const radius = nivel ? 4 + nivel * 0.8 : 3;
        const allP = peligrosByCcpp.get(c.codigo) ?? [];

        return (
          <CircleMarker
            key={c.codigo}
            center={[c.lat, c.lon]}
            radius={radius}
            pathOptions={{
              color,
              weight: 1,
              fillColor: color,
              fillOpacity: nivel ? 0.7 : 0.35,
            }}
          >
            <Tooltip direction="top" opacity={0.95}>
              <strong>{c.nombre}</strong>
              <br />
              {c.distrito} / {c.provincia}
            </Tooltip>
            <Popup>
              <div className="text-sm">
                <div className="font-bold text-base">{c.nombre}</div>
                <div className="text-ink-600 text-xs">
                  {c.categoria} — {c.distrito}, {c.provincia}
                </div>
                <div className="mt-2 text-xs">
                  <div>Población: <strong>{c.poblacion != null ? formatNumber(c.poblacion) : "s/d"}</strong></div>
                  <div>Altitud: <strong>{c.altitud != null ? `${formatNumber(c.altitud)} msnm` : "s/d"}</strong></div>
                </div>
                {allP.length > 0 ? (
                  <div className="mt-2">
                    <div className="text-xs font-semibold text-ink-900">Peligros clasificados:</div>
                    <ul className="text-xs mt-1 space-y-0.5">
                      {allP.map((p, i) => (
                        <li key={i}>
                          <span
                            className="inline-block w-2 h-2 rounded-full mr-1.5 align-middle"
                            style={{ background: NIVEL_COLOR[p.nivel] }}
                          />
                          {p.peligro}: <strong>{NIVEL_LABEL[p.nivel]}</strong>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <div className="mt-2 text-xs italic text-ink-600">
                    Sin clasificación de peligro registrada.
                  </div>
                )}
                <Link
                  to={`/peligros/${c.codigo}`}
                  className="block mt-3 text-xs font-medium text-mountain-700"
                >
                  Ver detalle →
                </Link>
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}
