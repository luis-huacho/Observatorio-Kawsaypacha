import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Lightbulb, Sprout, AlertTriangle, MapPin } from "lucide-react";
import { useJsonData } from "@/lib/useJsonData";
import type { Medida } from "@/lib/types";
import { TIPOS_PELIGRO } from "@/lib/types";
import MockBadge from "@/components/MockBadge";
import EmptyState from "@/components/EmptyState";

const RESULTADO_ESTILO: Record<Medida["resultado"], { label: string; color: string; Icon: typeof Lightbulb }> = {
  exito: { label: "Práctica exitosa", color: "bg-level-1/15 text-level-1 border-level-1/30", Icon: Sprout },
  leccion: { label: "Lección aprendida", color: "bg-level-2/20 text-yellow-800 border-level-2/40", Icon: Lightbulb },
  mal_adaptacion: { label: "Mal-adaptación", color: "bg-level-4/15 text-level-4 border-level-4/30", Icon: AlertTriangle },
};

export default function Medidas() {
  const medidas = useJsonData<Medida[]>("/data/medidas.mock.json");
  const [peligro, setPeligro] = useState("");
  const [ambito, setAmbito] = useState("");
  const [resultado, setResultado] = useState("");

  const filtradas = useMemo(() => {
    if (medidas.status !== "ok") return [];
    return medidas.data.filter((m) => {
      if (peligro && m.peligro !== peligro) return false;
      if (ambito && m.ambito !== ambito) return false;
      if (resultado && m.resultado !== resultado) return false;
      return true;
    });
  }, [medidas, peligro, ambito, resultado]);

  return (
    <div className="container-page py-8">
      <header className="mb-6 flex flex-wrap items-start gap-3 justify-between">
        <div>
          <h1 className="font-display text-3xl md:text-4xl font-bold text-mountain-900">
            Ventana 2 — Medidas
          </h1>
          <p className="text-ink-600 mt-2 max-w-3xl">
            ¿Qué prácticas están funcionando para enfrentar peligros climáticos? Casos de éxito,
            lecciones aprendidas y advertencias de mal-adaptación.
          </p>
        </div>
        <MockBadge label="Sección con datos referenciales" />
      </header>

      <div className="grid md:grid-cols-3 gap-3 mb-6">
        <Select label="Peligro" value={peligro} onChange={setPeligro} options={TIPOS_PELIGRO} />
        <Select
          label="Ámbito"
          value={ambito}
          onChange={setAmbito}
          options={["comunal", "distrital", "provincial", "regional"]}
        />
        <Select
          label="Resultado"
          value={resultado}
          onChange={setResultado}
          options={[
            { value: "exito", label: "Práctica exitosa" },
            { value: "leccion", label: "Lección aprendida" },
            { value: "mal_adaptacion", label: "Mal-adaptación" },
          ]}
        />
      </div>

      {filtradas.length === 0 ? (
        <EmptyState title="Sin medidas con esos filtros" />
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filtradas.map((m) => {
            const r = RESULTADO_ESTILO[m.resultado];
            return (
              <Link
                to={`/medidas/${m.slug}`}
                key={m.id}
                className="card p-5 hover:shadow-md transition no-underline relative"
              >
                <MockBadge className="absolute top-3 right-3" />
                <div className="flex items-center gap-2 mb-3 mt-1">
                  <span className={`chip border ${r.color}`}>
                    <r.Icon className="w-3 h-3" />
                    {r.label}
                  </span>
                </div>
                <h3 className="font-display font-bold text-mountain-900 text-lg leading-tight pr-16">
                  {m.titulo}
                </h3>
                <div className="mt-2 flex items-center gap-1 text-xs text-ink-600">
                  <MapPin className="w-3 h-3" />
                  {m.comunidad}
                </div>
                <p className="mt-3 text-sm text-ink-600">{m.resumen_corto}</p>
                <div className="mt-4 flex flex-wrap gap-1">
                  {m.tags.slice(0, 3).map((t) => (
                    <span key={t} className="chip bg-mountain-100 text-mountain-900 border border-mountain-500/20">
                      {t}
                    </span>
                  ))}
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Select({
  label, value, onChange, options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: readonly (string | { value: string; label: string })[];
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-ink-600 mb-1">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-ink-300/60 bg-white px-3 py-2 text-sm"
      >
        <option value="">Todos</option>
        {options.map((o) => {
          const v = typeof o === "string" ? o : o.value;
          const l = typeof o === "string" ? o : o.label;
          return <option key={v} value={v}>{l}</option>;
        })}
      </select>
    </div>
  );
}
