import { Link } from "react-router-dom";
import { Tag } from "lucide-react";

type Props = {
  palabras: string[];
  /** Listado al que llevan los chips: "/noticias" o "/normativa". */
  base: string;
};

/**
 * Palabras clave de una ficha. Cada una enlaza a su listado filtrado por ese término
 * (`?tema=…`), que es el único filtro del prototipo que vive en la URL.
 */
export default function PalabrasClave({ palabras, base }: Props) {
  if (!palabras.length) return null;

  return (
    <div className="mt-8 pt-5 border-t border-ink-300/30">
      <div className="flex items-center gap-1.5 text-xs text-ink-600 mb-2">
        <Tag className="w-3.5 h-3.5" />
        Palabras clave
      </div>
      <div className="flex flex-wrap gap-1.5">
        {palabras.map((p) => (
          <Link
            key={p}
            to={`${base}?tema=${encodeURIComponent(p)}`}
            className="chip bg-mountain-100 text-mountain-900 border border-mountain-500/20 hover:bg-mountain-500/20 transition no-underline"
          >
            {p}
          </Link>
        ))}
      </div>
    </div>
  );
}
