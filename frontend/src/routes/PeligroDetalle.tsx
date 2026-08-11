import { Suspense, lazy } from "react";
import { useParams, Link } from "react-router-dom";
import { MapPin } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import { useApi } from "@/lib/api";
import type { CentroPobladoDetalle, TipoPeligroApi } from "@/lib/types";
import SemaforoChip from "@/components/SemaforoChip";
import SourceLink from "@/components/SourceLink";
import EmptyState from "@/components/EmptyState";

// Diferido como en el visor: el chunk de MapLibre pesa ~840 KB y no se paga hasta abrir una
// ficha. Quien llega desde /peligros ya lo tiene en caché.
const MapaPunto = lazy(() => import("@/components/MapaPunto"));

export default function PeligroDetalle() {
  const { codigo } = useParams();
  // La ficha trae sus clasificaciones anidadas: una petición en vez de cruzar dos datasets.
  const detalle = useApi<CentroPobladoDetalle>(codigo ? `/ccpp/${codigo}/` : null);
  // El catálogo trae el ícono y el orden de cada peligro: el mapa los necesita para dibujar la
  // corona igual que el visor.
  const catalogo = useApi<TipoPeligroApi[]>("/peligros/tipos/");

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
      {/* Aquí había tres cifras: población, altitud y coordenadas. La primera salió por falta
          de fuente (ADR-A19) y las otras dos porque el mapa de abajo sitúa el punto mejor que un
          par de decimales. Altitud y coordenadas **siguen en el API** —el mapa necesita lat/lon—:
          es una decisión de presentación, no de datos. */}

      {cp.lat != null && cp.lon != null && (
        <section>
          <div className="card p-1 h-[320px] overflow-hidden">
            <Suspense
              fallback={
                <div className="h-full grid place-items-center text-ink-600">Cargando mapa…</div>
              }
            >
              <MapaPunto
                lat={cp.lat}
                lon={cp.lon}
                nombre={cp.nombre}
                clasificaciones={clasifs}
                tipos={catalogo.status === "ok" ? catalogo.data : []}
              />
            </Suspense>
          </div>
        </section>
      )}

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
                  <th className="text-center px-4 py-3">Nivel</th>
                  <th className="text-left px-4 py-3 hidden md:table-cell">Fuente</th>
                </tr>
              </thead>
              <tbody>
                {clasifs.map((p, i) => (
                  <tr key={i} className="border-t border-ink-300/20">
                    <td className="px-4 py-3 font-medium">{p.peligro}</td>
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
