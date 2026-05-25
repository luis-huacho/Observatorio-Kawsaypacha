import { useParams, Link } from "react-router-dom";
import { ChevronLeft, MapPin } from "lucide-react";
import { useJsonData } from "@/lib/useJsonData";
import type { CentroPoblado, ClasificacionPeligro } from "@/lib/types";
import SemaforoChip from "@/components/SemaforoChip";
import SourceLink from "@/components/SourceLink";
import EmptyState from "@/components/EmptyState";
import { formatNumber } from "@/lib/semaforo";

export default function PeligroDetalle() {
  const { codigo } = useParams();
  const ccpp = useJsonData<CentroPoblado[]>("/data/ccpp.json");
  const peligros = useJsonData<ClasificacionPeligro[]>("/data/peligros.json");

  if (ccpp.status === "loading" || peligros.status === "loading") {
    return <div className="container-page py-12 text-ink-600">Cargando…</div>;
  }
  if (ccpp.status !== "ok" || peligros.status !== "ok") {
    return <div className="container-page py-12"><EmptyState title="Error al cargar datos." /></div>;
  }

  const cp = ccpp.data.find((c) => c.codigo === codigo);
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

  const clasifs = peligros.data.filter((p) => p.codigo_ccpp === codigo);

  return (
    <div className="container-page py-8">
      <Link to="/peligros" className="inline-flex items-center gap-1 text-sm text-ink-600 hover:text-mountain-700 no-underline mb-4">
        <ChevronLeft className="w-4 h-4" /> Volver al mapa
      </Link>

      <header className="flex flex-col md:flex-row md:items-end gap-4 justify-between">
        <div>
          <div className="text-xs uppercase tracking-wide text-ink-600">{cp.categoria}</div>
          <h1 className="font-display text-3xl md:text-4xl font-bold text-mountain-900">
            {cp.nombre}
          </h1>
          <div className="mt-2 text-ink-600 flex items-center gap-2">
            <MapPin className="w-4 h-4" />
            {cp.distrito} · {cp.provincia} · {cp.departamento}
          </div>
        </div>
        <div className="font-mono text-xs text-ink-600">CCPP {cp.codigo}</div>
      </header>

      <section className="mt-6 grid sm:grid-cols-3 gap-4">
        <Card label="Población" value={cp.poblacion != null ? formatNumber(cp.poblacion) : "s/d"} sub="habitantes" />
        <Card label="Altitud" value={cp.altitud != null ? formatNumber(cp.altitud) : "s/d"} sub="msnm" />
        <Card
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
              <thead className="bg-mountain-100/60 text-xs uppercase tracking-wide text-ink-600">
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
  );
}

function Card({ label, value, sub, mono = false }: { label: string; value: string; sub: string; mono?: boolean }) {
  return (
    <div className="card p-5">
      <div className="text-xs text-ink-600">{label}</div>
      <div className={`mt-1 font-display font-extrabold text-2xl text-mountain-900 ${mono ? "font-mono text-base" : ""}`}>
        {value}
      </div>
      <div className="text-xs text-ink-600">{sub}</div>
    </div>
  );
}
