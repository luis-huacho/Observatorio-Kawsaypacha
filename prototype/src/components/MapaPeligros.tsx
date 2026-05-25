import { useMemo } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, Tooltip } from "react-leaflet";
import type { CentroPoblado, ClasificacionPeligro, Nivel } from "@/lib/types";
import { NIVEL_COLOR, NIVEL_LABEL, formatNumber } from "@/lib/semaforo";
import { Link } from "react-router-dom";

type Props = {
  ccpp: CentroPoblado[];
  peligros: ClasificacionPeligro[];
  tipoPeligroFiltro: string | null;
};

// Centro aproximado de Cusco
const CENTER: [number, number] = [-13.5, -72.0];

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

  return (
    <MapContainer
      center={CENTER}
      zoom={8}
      scrollWheelZoom={true}
      className="w-full h-full rounded-lg"
      preferCanvas={true}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
        url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
      />
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
