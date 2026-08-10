import { useParams, Link } from "react-router-dom";
import { MapPin } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import { useApi } from "@/lib/api";
import type { CentroPobladoDetalle } from "@/lib/types";
import SemaforoChip from "@/components/SemaforoChip";
import SourceLink from "@/components/SourceLink";
import EmptyState from "@/components/EmptyState";
import KPI from "@/components/KPI";
import { formatNumber } from "@/lib/semaforo";

export default function PeligroDetalle() {
  const { codigo } = useParams();
  // La ficha trae sus clasificaciones anidadas: una petición en vez de cruzar dos datasets.
  const detalle = useApi<CentroPobladoDetalle>(codigo ? `/ccpp/${codigo}/` : null);

  if (detalle.status === "loading") {
    return <div className="container-page py-12 text-ink-600">Cargando…</div>;
  }

  const cp = detalle.status === "ok" ? detalle.data : null;
  if (!cp) {
    return (
      <div className="container-page py-12">
        <EmptyState
          title="Centro poblado no encontrado"
          action={<Link to="/peligros" className="btn-primary">Volver al mapa</Link>}
        />
      </div>
    );
  }

  const clasifs = cp.clasificaciones;

  return (
    <>
      <PageHeader
        eyebrow={cp.categoria}
        titulo={cp.nombre}
        descripcion={
          <span className="inline-flex items-center gap-2">
            <MapPin className="w-4 h-4" />
            {cp.distrito} · {cp.provincia} · {cp.departamento}
          </span>
        }
        badge={<span className="font-mono text-xs text-white/70">CCPP {cp.codigo}</span>}
        backTo="/peligros"
        backLabel="Volver al mapa"
      />
      <div className="container-page py-8">
      <section className="grid sm:grid-cols-3 gap-4">
        <KPI label="Población" value={cp.poblacion != null ? formatNumber(cp.poblacion) : "s/d"} sub="habitantes" />
        <KPI label="Altitud" value={cp.altitud != null ? formatNumber(cp.altitud) : "s/d"} sub="msnm" />
        <KPI
          label="Coordenadas"
          value={cp.lat != null && cp.lon != null ? `${cp.lat.toFixed(4)}, ${cp.lon.toFixed(4)}` : "s/d"}
          sub="lat, lon"
          mono
        />
      </section>

      <section className="mt-8">
        <h2 className="font-display text-xl font-bold text-mountain-900 mb-3">
          Peligros clasificados
        </h2>
        {clasifs.length === 0 ? (
          <EmptyState
            title="Sin clasificaciones registradas"
            message="Este centro poblado no tiene niveles de peligro clasificados en la base actual del SIGRID-CENEPRED."
          />
        ) : (
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-mountain-700 text-xs uppercase tracking-wide text-white/90">
                <tr>
                  <th className="text-left px-4 py-3">Peligro</th>
                  <th className="text-left px-4 py-3 hidden sm:table-cell">Tipo / Detalle</th>
                  <th className="text-center px-4 py-3">Nivel</th>
                  <th className="text-left px-4 py-3 hidden md:table-cell">Fuente</th>
                </tr>
              </thead>
              <tbody>
                {clasifs.map((p, i) => (
                  <tr key={i} className="border-t border-ink-300/20">
                    <td className="px-4 py-3 font-medium">{p.peligro}</td>
                    <td className="px-4 py-3 text-ink-600 hidden sm:table-cell">{p.tipo ?? "—"}</td>
                    <td className="px-4 py-3 text-center">
                      <SemaforoChip nivel={p.nivel} />
                    </td>
                    <td className="px-4 py-3 hidden md:table-cell">
                      {p.fuente ? <SourceLink fuente={p.fuente} url={p.fuente_url} /> : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      </div>
    </>
  );
}
