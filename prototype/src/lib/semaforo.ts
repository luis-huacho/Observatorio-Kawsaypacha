import type { Nivel } from "./types";

export const NIVEL_LABEL: Record<Nivel, string> = {
  1: "Bajo",
  2: "Medio",
  3: "Alto",
  4: "Muy alto",
};

export const NIVEL_COLOR: Record<Nivel, string> = {
  1: "#4CAF50",
  2: "#FFC107",
  3: "#FF7043",
  4: "#D32F2F",
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
  return n === "alto" ? "#D32F2F" : n === "medio" ? "#FFC107" : "#4CAF50";
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat("es-PE").format(n);
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
