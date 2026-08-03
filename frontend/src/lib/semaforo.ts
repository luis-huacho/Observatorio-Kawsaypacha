import type { Nivel } from "./types";

export const NIVEL_LABEL: Record<Nivel, string> = {
  1: "Bajo",
  2: "Medio",
  3: "Alto",
  4: "Muy alto",
};

export const NIVEL_COLOR: Record<Nivel, string> = {
  1: "#5BBB5D",
  2: "#EBB320",
  3: "#F57C15",
  4: "#970A00",
};

export const NIVEL_BG: Record<Nivel, string> = {
  1: "bg-level-1/15 text-level-1 border-level-1/30",
  2: "bg-level-2/20 text-yellow-800 border-level-2/40",
  3: "bg-level-3/20 text-level-3 border-level-3/40",
  4: "bg-level-4/15 text-level-4 border-level-4/30",
};

export function nivelFromScore(score: number): "bajo" | "medio" | "alto" {
  if (score >= 0.66) return "alto";
  if (score >= 0.33) return "medio";
  return "bajo";
}

export function colorFromNivelStr(n: "bajo" | "medio" | "alto"): string {
  return n === "alto" ? "#970A00" : n === "medio" ? "#EBB320" : "#5BBB5D";
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat("es-PE").format(n);
}

/**
 * Fecha ISO ("2026-07-28") a texto legible.
 *
 * Se descompone a mano en vez de usar `new Date(iso)`: esa forma se interpreta como medianoche
 * UTC y en Lima (UTC-5) acaba mostrando el día anterior.
 */
export function formatFecha(iso: string): string {
  const [anio, mes, dia] = iso.split("-").map(Number);
  return new Intl.DateTimeFormat("es-PE", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date(anio, mes - 1, dia));
}

export function formatSoles(n: number): string {
  return new Intl.NumberFormat("es-PE", {
    style: "currency",
    currency: "PEN",
    maximumFractionDigits: 0,
  }).format(n);
}

export function formatPct(n: number): string {
  return new Intl.NumberFormat("es-PE", {
    style: "percent",
    maximumFractionDigits: 1,
  }).format(n);
}
