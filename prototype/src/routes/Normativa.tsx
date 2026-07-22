import { useMemo, useState } from "react";
import { ExternalLink, FileText } from "lucide-react";
import { useJsonData } from "@/lib/useJsonData";
import type { Norma } from "@/lib/types";
import MockBadge from "@/components/MockBadge";
import EmptyState from "@/components/EmptyState";
import PageHeader from "@/components/PageHeader";

export default function NormativaView() {
  const data = useJsonData<Norma[]>("/data/normativa.mock.json");
  const [tipo, setTipo] = useState("");
  const [ambito, setAmbito] = useState("");

  const filtradas = useMemo(() => {
    if (data.status !== "ok") return [];
    return data.data
      .filter((n) => (tipo ? n.tipo === tipo : true))
      .filter((n) => (ambito ? n.ambito === ambito : true))
      .sort((a, b) => b.fecha.localeCompare(a.fecha));
  }, [data, tipo, ambito]);

  if (data.status === "loading") return <div className="container-page py-12">Cargando…</div>;
  if (data.status !== "ok") return <div className="container-page py-12"><EmptyState /></div>;

  return (
    <>
      <PageHeader
        titulo="Normativa"
        descripcion="Repositorio de normativa reciente de GRD y ACC, con análisis y recomendaciones de PREDES."
        badge={<MockBadge label="Sección con datos referenciales" />}
      />
      <div className="container-page py-8">
      <div className="grid sm:grid-cols-2 gap-3 mb-6 max-w-xl">
        <select
          value={tipo}
          onChange={(e) => setTipo(e.target.value)}
          className="control"
        >
          <option value="">Todos los tipos</option>
          {["Ley", "DS", "RM", "RJ", "Ordenanza"].map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <select
          value={ambito}
          onChange={(e) => setAmbito(e.target.value)}
          className="control"
        >
          <option value="">Todos los ámbitos</option>
          <option value="nacional">Nacional</option>
          <option value="regional">Regional</option>
          <option value="local">Local</option>
        </select>
      </div>

      <ul className="space-y-3">
        {filtradas.map((n) => (
          <li key={n.id} className="card p-5">
            <div className="flex items-start gap-4">
              <FileText className="w-5 h-5 text-mountain-700 mt-0.5 shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2 mb-1">
                  <span className="chip bg-mountain-100 text-mountain-900 border border-mountain-500/20">
                    {n.tipo}
                  </span>
                  <span className="chip bg-sky-200/40 text-sky-700 border border-sky-500/20 capitalize">
                    {n.ambito}
                  </span>
                  <span className="text-xs text-ink-600 font-mono">{n.fecha}</span>
                </div>
                <h3 className="font-display font-bold text-mountain-900 leading-tight">{n.titulo}</h3>
                <p className="text-sm text-ink-600 mt-1">{n.resumen}</p>
                {n.analisis_predes && (
                  <div className="mt-3 callout p-3 text-sm">
                    <span className="font-semibold text-mountain-900">Análisis PREDES: </span>
                    {n.analisis_predes}
                  </div>
                )}
                {n.url_oficial && (
                  <a
                    href={n.url_oficial}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-3 inline-flex items-center gap-1 text-sm"
                  >
                    Ver norma oficial <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>
            </div>
          </li>
        ))}
      </ul>
      </div>
    </>
  );
}
