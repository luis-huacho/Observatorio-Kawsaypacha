import { useMemo } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { useJsonData } from "@/lib/useJsonData";
import type { CentroPoblado } from "@/lib/types";
import EmptyState from "@/components/EmptyState";
import { formatNumber } from "@/lib/semaforo";

export default function Buscar() {
  const [sp] = useSearchParams();
  const q = (sp.get("q") ?? "").trim().toLowerCase();
  const ccpp = useJsonData<CentroPoblado[]>("/data/ccpp.json");

  const matches = useMemo(() => {
    if (!q || ccpp.status !== "ok") return [];
    return ccpp.data
      .filter(
        (c) =>
          c.nombre.toLowerCase().includes(q) ||
          c.distrito.toLowerCase().includes(q) ||
          c.provincia.toLowerCase().includes(q)
      )
      .slice(0, 100);
  }, [ccpp, q]);

  return (
    <div className="container-page py-8">
      <h1 className="font-display text-2xl md:text-3xl font-bold text-mountain-900">
        Resultados para “{q}”
      </h1>
      <p className="text-ink-600 mt-1">
        {ccpp.status === "ok"
          ? `${formatNumber(matches.length)} centro(s) poblado(s) encontrado(s)`
          : "Cargando…"}
      </p>

      {ccpp.status === "ok" && matches.length === 0 ? (
        <div className="mt-6">
          <EmptyState
            title="Sin coincidencias"
            message="Probá con el nombre del distrito, provincia o centro poblado."
            action={<Link to="/peligros" className="btn-primary">Ir al mapa</Link>}
          />
        </div>
      ) : (
        <ul className="mt-6 grid gap-2 md:grid-cols-2">
          {matches.map((c) => (
            <li key={c.codigo}>
              <Link
                to={`/peligros/${c.codigo}`}
                className="card p-4 flex items-center justify-between hover:shadow-md transition no-underline"
              >
                <div>
                  <div className="font-semibold text-mountain-900">{c.nombre}</div>
                  <div className="text-xs text-ink-600">{c.distrito} · {c.provincia}</div>
                </div>
                <span className="text-xs text-ink-300 font-mono">{c.categoria}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
