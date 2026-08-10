import type { ReactNode } from "react";

export type OpcionChecklist = {
  valor: string;
  etiqueta: string;
  /** Ícono o punto de color a la izquierda de la etiqueta. */
  adorno?: ReactNode;
  /** Cifra a la derecha (p. ej. cuántos centros poblados aporta la opción). */
  detalle?: ReactNode;
};

type Props = {
  titulo: string;
  opciones: OpcionChecklist[];
  seleccion: string[];
  onChange: (seleccion: string[]) => void;
};

/**
 * Filtro de selección múltiple con casillas de verdad.
 *
 * Casillas y no `aria-pressed` sobre botones: son opciones acumulables, que es exactamente lo
 * que un checkbox comunica a un lector de pantalla y lo que `getByRole("checkbox")` encuentra
 * en las pruebas. La botonera anterior de «nivel mínimo» era un radio disfrazado.
 *
 * Ninguna marcada es un estado legítimo —el usuario acaba de vaciar el filtro— y la página lo
 * trata como «sin resultados», no como «todos»: quien desmarca todo espera no ver nada.
 */
export default function ChecklistFiltro({ titulo, opciones, seleccion, onChange }: Props) {
  const marcadas = new Set(seleccion);
  const todas = marcadas.size === opciones.length;

  const alternar = (valor: string) =>
    onChange(
      marcadas.has(valor) ? seleccion.filter((v) => v !== valor) : [...seleccion, valor]
    );

  // El `role="group"` envuelve **el filtro entero**, atajo incluido, y no solo las casillas: es
  // un único control compuesto, y así el botón de marcar/desmarcar todo queda dentro del mismo
  // grupo accesible que las casillas que altera.
  return (
    <div role="group" aria-label={titulo}>
      <div className="flex items-baseline justify-between mb-1 gap-2">
        <span className="block text-xs font-medium text-ink-600">{titulo}</span>
        <button
          type="button"
          onClick={() => onChange(todas ? [] : opciones.map((o) => o.valor))}
          className="text-[11px] text-mountain-700 hover:text-mountain-900 underline underline-offset-2"
        >
          {todas ? "Ninguno" : "Todos"}
        </button>
      </div>
      <div className="space-y-0.5">
        {opciones.map((o) => (
          <label
            key={o.valor}
            className="flex items-center gap-2 py-1 px-1.5 -mx-1.5 rounded cursor-pointer hover:bg-mountain-100/60"
          >
            <input
              type="checkbox"
              checked={marcadas.has(o.valor)}
              onChange={() => alternar(o.valor)}
              className="shrink-0 w-4 h-4 rounded border-ink-300 text-mountain-700 focus:ring-mountain-700"
            />
            {o.adorno}
            <span className="text-sm text-ink-900 leading-tight min-w-0 flex-1">{o.etiqueta}</span>
            {o.detalle != null && (
              <span className="text-[11px] font-mono text-ink-600 shrink-0">{o.detalle}</span>
            )}
          </label>
        ))}
      </div>
    </div>
  );
}
