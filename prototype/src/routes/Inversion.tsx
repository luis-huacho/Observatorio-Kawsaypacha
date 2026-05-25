import { useMemo, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, CartesianGrid, Legend,
} from "recharts";
import { useJsonData } from "@/lib/useJsonData";
import type { Inversion } from "@/lib/types";
import { formatPct, formatSoles } from "@/lib/semaforo";
import MockBadge from "@/components/MockBadge";
import EmptyState from "@/components/EmptyState";

export default function InversionView() {
  const inv = useJsonData<Inversion>("/data/inversion.mock.json");
  const [orden, setOrden] = useState<"pim" | "ejecucion" | "prevencion">("pim");

  const distritos = useMemo(() => {
    if (inv.status !== "ok") return [];
    const arr = [...inv.data.por_distrito];
    if (orden === "pim") arr.sort((a, b) => b.pim - a.pim);
    if (orden === "ejecucion") arr.sort((a, b) => b.devengado / b.pim - a.devengado / a.pim);
    if (orden === "prevencion") arr.sort((a, b) => b.pct_prevencion - a.pct_prevencion);
    return arr;
  }, [inv, orden]);

  if (inv.status === "loading") return <div className="container-page py-12">Cargando…</div>;
  if (inv.status !== "ok") return <div className="container-page py-12"><EmptyState /></div>;

  const d = inv.data;
  const compData = [
    { tipo: "Prevención", monto: d.comparacion_prevencion_respuesta.prevencion_total },
    { tipo: "Respuesta",  monto: d.comparacion_prevencion_respuesta.respuesta_total },
  ];

  return (
    <div className="container-page py-8">
      <header className="mb-6 flex flex-wrap items-start gap-3 justify-between">
        <div>
          <h1 className="font-display text-3xl md:text-4xl font-bold text-mountain-900">
            Ventana 3 — Inversión PPR 0068
          </h1>
          <p className="text-ink-600 mt-2 max-w-3xl">
            ¿Cuánto y cómo invierten los gobiernos locales en reducción de vulnerabilidad y atención
            de emergencias? Programa Presupuestal 0068 — ejercicio {d.anio}.
          </p>
        </div>
        <MockBadge label="Sección con datos referenciales" />
      </header>

      <section className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <KPI label="PIM total Cusco" value={formatSoles(d.agregados.pim_total)} />
        <KPI label="Ejecutado" value={formatSoles(d.agregados.ejecutado)} sub={formatPct(d.agregados.porcentaje_ejecucion)} />
        <KPI label="Municipios con PPR 0068" value={String(d.agregados.municipios_con_ppr_0068)} sub="de 108 totales" />
        <KPI
          label="Prevención vs Respuesta"
          value={`${formatPct(d.comparacion_prevencion_respuesta.prevencion_total / (d.comparacion_prevencion_respuesta.prevencion_total + d.comparacion_prevencion_respuesta.respuesta_total))}`}
          sub="prevención"
        />
      </section>

      <section className="grid lg:grid-cols-2 gap-6">
        <div className="card p-5">
          <h2 className="font-display font-semibold text-mountain-900 mb-2">
            Tendencia 2021-2025
          </h2>
          <p className="text-xs text-ink-600 mb-4">PIM vs Devengado (millones de soles)</p>
          <div className="h-64">
            <ResponsiveContainer>
              <LineChart data={d.tendencia.map((t) => ({ anio: t.anio, PIM: t.pim / 1e6, Devengado: t.devengado / 1e6 }))}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E0E0E0" />
                <XAxis dataKey="anio" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip formatter={(v: number) => `S/ ${v.toFixed(1)}M`} />
                <Legend />
                <Line type="monotone" dataKey="PIM" stroke="#1F5F8A" strokeWidth={2.5} />
                <Line type="monotone" dataKey="Devengado" stroke="#6BA585" strokeWidth={2.5} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-5">
          <h2 className="font-display font-semibold text-mountain-900 mb-2">
            Prevención vs Respuesta — {d.anio}
          </h2>
          <p className="text-xs text-ink-600 mb-4">Gasto agregado por finalidad</p>
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={compData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E0E0E0" />
                <XAxis dataKey="tipo" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `S/ ${(v / 1e6).toFixed(0)}M`} />
                <Tooltip formatter={(v: number) => formatSoles(v)} />
                <Bar dataKey="monto" fill="#6BA585" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>

      <section className="mt-8">
        <div className="flex flex-wrap items-end justify-between gap-3 mb-3">
          <h2 className="font-display text-xl font-bold text-mountain-900">Distritos</h2>
          <div className="flex items-center gap-2 text-sm">
            <span className="text-ink-600">Ordenar por:</span>
            <select
              value={orden}
              onChange={(e) => setOrden(e.target.value as typeof orden)}
              className="rounded-md border border-ink-300/60 bg-white px-3 py-1.5"
            >
              <option value="pim">Mayor PIM</option>
              <option value="ejecucion">Mayor ejecución %</option>
              <option value="prevencion">Mayor % prevención</option>
            </select>
          </div>
        </div>

        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-mountain-100/60 text-xs uppercase tracking-wide text-ink-600">
              <tr>
                <th className="text-left px-4 py-3">Distrito</th>
                <th className="text-left px-4 py-3 hidden md:table-cell">Provincia</th>
                <th className="text-right px-4 py-3">PIM</th>
                <th className="text-right px-4 py-3">Devengado</th>
                <th className="text-right px-4 py-3">% Ejec.</th>
                <th className="text-right px-4 py-3 hidden sm:table-cell">% Prev.</th>
              </tr>
            </thead>
            <tbody>
              {distritos.map((r) => {
                const ejec = r.devengado / r.pim;
                return (
                  <tr key={r.ubigeo} className="border-t border-ink-300/20 hover:bg-mountain-100/40">
                    <td className="px-4 py-3 font-medium">{r.distrito}</td>
                    <td className="px-4 py-3 text-ink-600 hidden md:table-cell">{r.provincia}</td>
                    <td className="px-4 py-3 text-right font-mono">{formatSoles(r.pim)}</td>
                    <td className="px-4 py-3 text-right font-mono">{formatSoles(r.devengado)}</td>
                    <td className="px-4 py-3 text-right font-mono">{formatPct(ejec)}</td>
                    <td className="px-4 py-3 text-right font-mono hidden sm:table-cell">{formatPct(r.pct_prevencion)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function KPI({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card p-5">
      <div className="text-xs text-ink-600">{label}</div>
      <div className="mt-2 font-display font-extrabold text-2xl text-mountain-900">{value}</div>
      {sub && <div className="text-xs text-ink-600 mt-1">{sub}</div>}
    </div>
  );
}
