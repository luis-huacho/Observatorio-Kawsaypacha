import { Download, ExternalLink, FileX2 } from "lucide-react";
import type { Norma } from "@/lib/types";

/** Quién publica la norma, según su ámbito. Es el dato que busca quien arma un expediente. */
export const PUBLICA: Record<Norma["ambito"], string> = {
  nacional: "Gobierno Nacional",
  regional: "Gobierno Regional",
  local: "Gobierno Local",
};

type Props = {
  url: string | null;
  /** Variante de texto para el listado; la de la ficha es un botón. */
  compacta?: boolean;
};

/**
 * Acceso a la publicación oficial de una norma.
 *
 * Tres estados, porque los tres se dan: un PDF que se descarga, una página del portal del
 * organismo, o ninguna de las dos. PREDES cargará normas antes de tener a mano su publicación,
 * así que la ausencia tiene que decirse y no dejar un hueco.
 */
export default function EnlaceNorma({ url, compacta = false }: Props) {
  if (!url) {
    return (
      <span
        className={`inline-flex items-center gap-1.5 text-ink-300 ${compacta ? "text-xs" : "text-sm"}`}
      >
        <FileX2 className={compacta ? "w-3.5 h-3.5" : "w-4 h-4"} />
        Sin enlace oficial registrado
      </span>
    );
  }

  // Un portal de gob.pe es una página, no una descarga: llamarla "descargar" sería impreciso.
  const esPdf = url.toLowerCase().split("?")[0].endsWith(".pdf");
  const Icono = esPdf ? Download : ExternalLink;
  const etiqueta = esPdf ? "Descargar norma (PDF)" : "Ver norma oficial";

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className={
        compacta
          ? "inline-flex items-center gap-1.5 text-xs text-mountain-700 hover:text-mountain-900"
          : "btn-primary no-underline"
      }
    >
      <Icono className={compacta ? "w-3.5 h-3.5" : "w-4 h-4"} />
      {etiqueta}
    </a>
  );
}
