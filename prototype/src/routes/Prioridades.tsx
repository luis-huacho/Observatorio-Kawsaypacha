import { useMemo, useState } from "react";
import { useJsonData } from "@/lib/useJsonData";
import type { Prioridades, PrioridadDistrito } from "@/lib/types";
import { colorFromNivelStr, formatPct } from "@/lib/semaforo";
import MockBadge from "@/components/MockBadge";
import EmptyState from "@/components/EmptyState";

const VAR_LABEL: Record<keyof PrioridadDistrito["variables"], string> = {
  exposicion: "Exposición al peligro",
  poblacion_expuesta: "Población expuesta",
  pobreza: "Pobreza",
  infraestructura: "Infraestructura crítica",
  agua: "Disponibilidad de agua",
  frecuencia: "Frecuencia de emergencias",
};

export default function PrioridadesView() {
  const p = useJsonData<Prioridades>("/data/prioridades.mock.json");
  const [pesos, setPesos] = useState<PrioridadDistrito["variables"] | null>(null);

  const activos = useMemo(() => {
    if (p.status !== "ok") return null;
    return pesos ?? p.data.pesos_default;
  }, [p, pesos]);

  const recalculado = useMemo(() => {
    if (p.status !== "ok" || !activos) return [];
    const sum = Object.values(activos).reduce((a, b) => a + b, 0) || 1;
    const norm = Object.fromEntries(
      Object.entries(activos).map(([k, v]) => [k, v / sum])
    ) as PrioridadDistrito["variables"];

    const scores = p.data.scores.map((d) => {
      const s =
        d.variables.exposicion * norm.exposicion +
        d.variables.poblacion_expuesta * norm.poblacion_expuesta +
        d.variables.pobreza * norm.pobreza +
        d.variables.infraestructura * norm.infraestructura +
        d.variables.agua * norm.agua +
        d.variables.frecuencia * norm.frecuencia;
      const nivel = s >= 0.66 ? "alto" : s >= 0.33 ? "medio" : "bajo";
      return { ...d, score: s, nivel: nivel as PrioridadDistrito["nivel"] };
    });
    scores.sort((a, b) => b.score - a.score);
    return scores;
  }, [p, activos]);

  if (p.status === "loading") return <div className="container-page py-12">Cargando…</div>;
  if (p.status !== "ok") return <div className="container-page py-12"><EmptyState /></div>;

  return (
    <div className="container-page py-8">
      <header className="mb-6 flex flex-wrap items-start gap-3 justify-between">
        <div>
          <h1 className="font-display text-3xl md:text-4xl font-bold text-mountain-900">
            Ventana 4 — Prioridades
          </h1>
          <p className="text-ink-600 mt-2 max-w-3xl">
            ¿Dónde debería invertirse primero? Scoring multicriterio por distrito.
            Ajusta los pesos a tu criterio para explorar escenarios.
          </p>
        </div>
        <MockBadge label="Sección con datos referenciales" />
      </header>

      <div className="grid lg:grid-cols-[320px_1fr] gap-6">
        <aside className="card p-5 h-fit lg:sticky lg:top-20">
          <h2 className="font-display font-semibold text-mountain-900 mb-3">Pesos de las variables</h2>
          <p className="text-xs text-ink-600 mb-4">
            Mueve los sliders para re-calcular el ranking de prioridad.
          </p>
          <div className="space-y-3">
            {(Object.keys(VAR_LABEL) as Array<keyof typeof VAR_LABEL>).map((k) => (
              <div key={k}>
                <div className="flex justify-between text-xs">
                  <label className="text-ink-900">{VAR_LABEL[k]}</label>
                  <span className="font-mono text-ink-600">
                    {((activos?.[k] ?? 0) * 100).toFixed(0)}%
                  </span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={50}
                  step={1}
                  value={Math.round((activos?.[k] ?? 0) * 100)}
                  onChange={(e) => {
                    const newPesos: PrioridadDistrito["variables"] = {
                      ...(activos ?? p.data.pesos_default),
                      [k]: Number(e.target.value) / 100,
                    };
                    setPesos(newPesos);
                  }}
                  className="w-full accent-mountain-700"
                />
              </div>
            ))}
          </div>
          <button
            onClick={() => setPesos(null)}
            className="mt-5 w-full btn-ghost border border-ink-300/40 justify-center"
          >
            Restablecer pesos
          </button>
          <p className="text-xs text-ink-600 mt-4 pt-3 border-t border-ink-300/30">
            <strong>Metodología:</strong> {p.data.metodologia}
          </p>
        </aside>

        <section>
          <div className="card p-5">
            <h2 className="font-display font-semibold text-mountain-900 mb-3">
              Ranking de distritos por prioridad
            </h2>
            <ol className="space-y-2">
              {recalculado.map((d, i) => (
                <li
                  key={d.ubigeo}
                  className="flex items-center gap-3 p-3 rounded-md hover:bg-mountain-100/60"
                >
                  <span className="font-display font-extrabold text-ink-300 w-8 text-right">
                    {i + 1}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-mountain-900">{d.distrito}</div>
                    <div className="text-xs text-ink-600">{d.provincia}</div>
                  </div>
                  <div className="w-40 hidden sm:block">
                    <div className="h-2 bg-ink-300/20 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${Math.min(100, d.score * 100)}%`,
                          background: colorFromNivelStr(d.nivel),
                        }}
                      />
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono font-semibold">{formatPct(d.score)}</div>
                    <div className="text-xs capitalize" style={{ color: colorFromNivelStr(d.nivel) }}>
                      {d.nivel}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>
      </div>
    </div>
  );
}
