import { useMemo } from "react";
import type { CentroPoblado } from "@/lib/types";

type Props = {
  ccpp: CentroPoblado[];
  provincia: string;
  distrito: string;
  onChange: (provincia: string, distrito: string) => void;
};

export default function GeoSelector({ ccpp, provincia, distrito, onChange }: Props) {
  const provincias = useMemo(
    () => Array.from(new Set(ccpp.map((c) => c.provincia))).sort(),
    [ccpp]
  );
  const distritos = useMemo(() => {
    if (!provincia) return [];
    return Array.from(
      new Set(ccpp.filter((c) => c.provincia === provincia).map((c) => c.distrito))
    ).sort();
  }, [ccpp, provincia]);

  return (
    <div className="flex flex-col sm:flex-row gap-2">
      <select
        value={provincia}
        onChange={(e) => onChange(e.target.value, "")}
        className="rounded-md border border-ink-300/60 bg-white px-3 py-2 text-sm"
      >
        <option value="">Todas las provincias</option>
        {provincias.map((p) => (
          <option key={p} value={p}>{p}</option>
        ))}
      </select>
      <select
        value={distrito}
        onChange={(e) => onChange(provincia, e.target.value)}
        disabled={!provincia}
        className="rounded-md border border-ink-300/60 bg-white px-3 py-2 text-sm disabled:bg-ink-300/10 disabled:text-ink-600"
      >
        <option value="">Todos los distritos</option>
        {distritos.map((d) => (
          <option key={d} value={d}>{d}</option>
        ))}
      </select>
    </div>
  );
}
