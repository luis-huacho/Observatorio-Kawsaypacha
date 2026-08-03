import { X } from "lucide-react";

type Props = {
  tema: string;
  onLimpiar: () => void;
};

/**
 * Aviso del filtro por palabra clave. Sin él, quien llega desde una ficha ve el listado
 * recortado y no entiende por qué: el filtro está en la URL, no en ningún control visible.
 */
export default function FiltroTema({ tema, onLimpiar }: Props) {
  if (!tema) return null;

  return (
    <div className="mb-5 flex flex-wrap items-center gap-3 rounded-xl border border-mountain-500/25 bg-mountain-100/60 px-4 py-2.5">
      <span className="text-sm text-ink-900">
        Filtrando por palabra clave: <strong>{tema}</strong>
      </span>
      <button
        type="button"
        onClick={onLimpiar}
        className="inline-flex items-center gap-1 text-xs text-mountain-700 hover:text-mountain-900"
      >
        <X className="w-3.5 h-3.5" />
        Quitar filtro
      </button>
    </div>
  );
}
