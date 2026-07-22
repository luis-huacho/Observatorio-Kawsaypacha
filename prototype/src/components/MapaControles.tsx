import { useEffect } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import { toPng } from "html-to-image";
import type { CentroPoblado } from "@/lib/types";

/**
 * Buscador de centros poblados sobre el mapa. Filtra por nombre y, al elegir
 * un resultado, vuela hacia el punto y lo resalta. Usa los datos ya cargados
 * (sin geocoder externo).
 */
export function BuscarLugarControl({ ccpp }: { ccpp: CentroPoblado[] }) {
  const map = useMap();
  useEffect(() => {
    const conCoords = ccpp.filter((c) => c.lat != null && c.lon != null);
    let marcador: L.CircleMarker | null = null;

    const ctrl = new L.Control({ position: "topright" });
    ctrl.onAdd = () => {
      const div = L.DomUtil.create("div", "leaflet-bar leaflet-control");
      div.style.background = "#fff";
      div.style.overflow = "hidden";

      const input = L.DomUtil.create("input", "", div) as HTMLInputElement;
      input.type = "text";
      input.placeholder = "Buscar centro poblado…";
      input.style.cssText = "border:none;outline:none;padding:7px 9px;width:210px;font:13px system-ui;display:block";

      const list = L.DomUtil.create("ul", "", div) as HTMLUListElement;
      list.style.cssText = "list-style:none;margin:0;padding:0;max-height:220px;overflow:auto;background:#fff";

      const render = (q: string) => {
        list.innerHTML = "";
        const term = q.trim().toLowerCase();
        if (term.length < 2) return;
        const matches = conCoords
          .filter((c) => c.nombre.toLowerCase().includes(term))
          .slice(0, 8);
        for (const c of matches) {
          const li = L.DomUtil.create("li", "", list);
          li.style.cssText =
            "padding:6px 9px;cursor:pointer;border-top:1px solid #eee;font:12px system-ui";
          li.innerHTML = `<strong>${c.nombre}</strong><br><span style="color:#666">${c.distrito}, ${c.provincia}</span>`;
          L.DomEvent.on(li, "mouseover", () => (li.style.background = "#E5F4EE"));
          L.DomEvent.on(li, "mouseout", () => (li.style.background = "#fff"));
          L.DomEvent.on(li, "click", () => {
            const lat = c.lat as number;
            const lon = c.lon as number;
            map.flyTo([lat, lon], 13);
            if (marcador) marcador.remove();
            marcador = L.circleMarker([lat, lon], {
              radius: 10,
              color: "#0B3B26",
              weight: 3,
              fillColor: "#5BBB5D",
              fillOpacity: 0.6,
            })
              .addTo(map)
              .bindPopup(`<strong>${c.nombre}</strong><br>${c.distrito}, ${c.provincia}`)
              .openPopup();
            list.innerHTML = "";
            input.value = c.nombre;
          });
        }
      };

      L.DomEvent.on(input, "input", () => render(input.value));
      L.DomEvent.disableClickPropagation(div);
      L.DomEvent.disableScrollPropagation(div);
      return div;
    };
    ctrl.addTo(map);

    return () => {
      if (marcador) marcador.remove();
      ctrl.remove();
    };
  }, [map, ccpp]);
  return null;
}

/**
 * Herramienta de medición. Clic para añadir vértices; doble clic para terminar.
 * Muestra distancia acumulada y, con 3+ puntos, el área (fórmula esférica).
 */
export function MedirControl() {
  const map = useMap();
  useEffect(() => {
    const pts: L.LatLng[] = [];
    const group = L.featureGroup().addTo(map);
    let activo = false;
    let btnLink: HTMLAnchorElement | null = null;
    let labelDiv: HTMLElement | null = null;

    const toRad = (d: number) => (d * Math.PI) / 180;
    const areaEsferica = (ll: L.LatLng[]) => {
      const R = 6378137;
      let a = 0;
      const n = ll.length;
      if (n < 3) return 0;
      for (let i = 0; i < n; i++) {
        const p1 = ll[i];
        const p2 = ll[(i + 1) % n];
        a += toRad(p2.lng - p1.lng) * (2 + Math.sin(toRad(p1.lat)) + Math.sin(toRad(p2.lat)));
      }
      return Math.abs((a * R * R) / 2);
    };
    const distancia = (ll: L.LatLng[]) => {
      let d = 0;
      for (let i = 1; i < ll.length; i++) d += map.distance(ll[i - 1], ll[i]);
      return d;
    };
    const fmtDist = (m: number) => (m >= 1000 ? (m / 1000).toFixed(2) + " km" : Math.round(m) + " m");
    const fmtArea = (m2: number) => (m2 >= 1e6 ? (m2 / 1e6).toFixed(2) + " km²" : (m2 / 10000).toFixed(2) + " ha");

    const limpiar = () => {
      pts.length = 0;
      group.clearLayers();
      updateLabel();
    };

    const updateLabel = () => {
      if (!labelDiv) return;
      if (pts.length === 0) {
        labelDiv.style.display = "none";
        labelDiv.innerHTML = "";
        return;
      }
      labelDiv.style.display = "block";
      const d = distancia(pts);
      const a = pts.length >= 3 ? areaEsferica(pts) : 0;
      labelDiv.innerHTML =
        `<div style="font-weight:600;margin-bottom:2px">Medición</div>` +
        `<div>Distancia: <strong>${fmtDist(d)}</strong></div>` +
        (a > 0 ? `<div>Área: <strong>${fmtArea(a)}</strong></div>` : "") +
        `<div style="margin-top:3px;color:#888;font-size:10px">Doble clic para terminar</div>` +
        `<a href="#" id="med-limpiar" style="color:#007480;font-size:11px">Limpiar</a>`;
      const clear = labelDiv.querySelector("#med-limpiar");
      if (clear)
        L.DomEvent.on(clear as HTMLElement, "click", (e) => {
          L.DomEvent.preventDefault(e);
          limpiar();
        });
    };

    const redraw = () => {
      group.clearLayers();
      pts.forEach((p) =>
        L.circleMarker(p, { radius: 4, color: "#7A4A28", fillColor: "#B8753C", fillOpacity: 1, weight: 1 }).addTo(group),
      );
      if (pts.length >= 3) {
        L.polygon(pts, { color: "#7A4A28", weight: 2, fillColor: "#B8753C", fillOpacity: 0.15, dashArray: "4" }).addTo(group);
      } else if (pts.length === 2) {
        L.polyline(pts, { color: "#7A4A28", weight: 2, dashArray: "4" }).addTo(group);
      }
      updateLabel();
    };

    const onClick = (e: L.LeafletMouseEvent) => {
      pts.push(e.latlng);
      redraw();
    };
    const onDbl = (e: L.LeafletMouseEvent) => {
      L.DomEvent.stop(e.originalEvent);
      setActivo(false);
    };

    const setActivo = (v: boolean) => {
      activo = v;
      const c = map.getContainer();
      if (v) {
        c.style.cursor = "crosshair";
        map.on("click", onClick);
        map.on("dblclick", onDbl);
        map.doubleClickZoom.disable();
        if (btnLink) btnLink.style.background = "#5BBB5D";
      } else {
        c.style.cursor = "";
        map.off("click", onClick);
        map.off("dblclick", onDbl);
        map.doubleClickZoom.enable();
        if (btnLink) btnLink.style.background = "";
      }
    };

    const btn = new L.Control({ position: "topleft" });
    btn.onAdd = () => {
      const div = L.DomUtil.create("div", "leaflet-bar leaflet-control");
      const a = L.DomUtil.create("a", "", div) as HTMLAnchorElement;
      a.href = "#";
      a.title = "Medir distancia / área";
      a.innerHTML = "📐";
      a.style.fontSize = "15px";
      btnLink = a;
      L.DomEvent.disableClickPropagation(div);
      L.DomEvent.on(a, "click", (e) => {
        L.DomEvent.preventDefault(e);
        setActivo(!activo);
      });
      return div;
    };
    btn.addTo(map);

    const label = new L.Control({ position: "bottomleft" });
    label.onAdd = () => {
      const div = L.DomUtil.create("div", "leaflet-control");
      div.style.cssText =
        "background:rgba(255,255,255,0.92);padding:6px 10px;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,0.2);font:12px system-ui;color:#1A1A1A;display:none";
      labelDiv = div;
      L.DomEvent.disableClickPropagation(div);
      return div;
    };
    label.addTo(map);

    return () => {
      setActivo(false);
      group.remove();
      btn.remove();
      label.remove();
    };
  }, [map]);
  return null;
}

/** Descarga la vista actual del mapa como PNG (sin los controles). */
export function DescargarPNGControl() {
  const map = useMap();
  useEffect(() => {
    const ctrl = new L.Control({ position: "topleft" });
    ctrl.onAdd = () => {
      const div = L.DomUtil.create("div", "leaflet-bar leaflet-control");
      const a = L.DomUtil.create("a", "", div) as HTMLAnchorElement;
      a.href = "#";
      a.title = "Descargar vista (PNG)";
      a.innerHTML = "⤓";
      a.style.fontSize = "16px";
      a.style.fontWeight = "bold";
      L.DomEvent.disableClickPropagation(div);
      L.DomEvent.on(a, "click", async (e) => {
        L.DomEvent.preventDefault(e);
        const previo = a.innerHTML;
        a.innerHTML = "…";
        try {
          const dataUrl = await toPng(map.getContainer(), {
            cacheBust: true,
            pixelRatio: 2,
            skipFonts: true,
            filter: (el) =>
              !(el instanceof HTMLElement && el.classList.contains("leaflet-control-container")),
          });
          const link = document.createElement("a");
          link.download = "observatorio-mapa-cusco.png";
          link.href = dataUrl;
          link.click();
        } catch (err) {
          console.error("No se pudo exportar el PNG:", err);
        } finally {
          a.innerHTML = previo;
        }
      });
      return div;
    };
    ctrl.addTo(map);
    return () => {
      ctrl.remove();
    };
  }, [map]);
  return null;
}
