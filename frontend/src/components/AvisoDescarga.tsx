import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Loader2, TriangleAlert, X } from "lucide-react";

/**
 * El aviso fijo que acompaña a una descarga en curso.
 *
 * Existe porque **los botones de descarga viven en el `PageHeader`**, arriba del todo: en cuanto
 * el visitante se desplaza a la tabla o al mapa deja de verlos, y con ellos el único indicio de
 * que algo está pasando. El estado dentro del botón resuelve el primer segundo; este resuelve los
 * otros tres.
 *
 * Dos comportamientos deliberadamente distintos:
 *
 * - **Generando** — se va solo al terminar. La descarga en sí es la confirmación; un «listo» que
 *   hay que cerrar sobra.
 * - **Error** — se queda hasta que se cierra. Un error que se autodestruye a los tres segundos es
 *   un error que nadie llega a leer, y el caso que más importa aquí (el 429 del límite de
 *   descargas) hoy no produce ningún texto en la página.
 *
 * **Este es el `aria-live` de la descarga, y el botón no lo lleva**: con los dos, un lector de
 * pantalla anunciaría lo mismo dos veces.
 */

const ID_CONTENEDOR = "avisos-descarga";

/**
 * El contenedor único, creado a demanda.
 *
 * Con un portal por aviso al `body` a secas, dos descargas simultáneas —se puede lanzar el PDF y
 * después el Excel, cada botón solo se bloquea a sí mismo— pintarían los dos avisos encima del
 * mismo punto. Con un contenedor `flex-col` se apilan solos, y no hace falta un proveedor global
 * de notificaciones para dos casos.
 *
 * `no-imprimir` porque un aviso de la interfaz impreso en un papel es basura, y `z-50` para quedar
 * por encima de la barra superior, que va a `z-40`.
 */
function contenedor(): HTMLElement {
  const existente = document.getElementById(ID_CONTENEDOR);
  if (existente) return existente;
  const nuevo = document.createElement("div");
  nuevo.id = ID_CONTENEDOR;
  nuevo.className =
    "no-imprimir fixed bottom-4 right-4 z-50 flex flex-col gap-2 items-end max-w-[calc(100vw-2rem)]";
  document.body.appendChild(nuevo);
  return nuevo;
}

export type AvisoDescargaProps = {
  /** Qué se está generando, en palabras: «la ayuda memoria de SICUANI». */
  descripcion: string;
  /** Si viene, el aviso es de error y no se va solo. */
  error?: string;
  onCerrar: () => void;
};

export default function AvisoDescarga({ descripcion, error, onCerrar }: AvisoDescargaProps) {
  // El contenedor se resuelve en un efecto y no en el render: en el primer render del servidor
  // —o de cualquier prerenderizado— no hay `document`, y crearlo aquí reventaría.
  const [destino, setDestino] = useState<HTMLElement | null>(null);
  useEffect(() => setDestino(contenedor()), []);
  if (!destino) return null;

  return createPortal(
    <div
      role={error ? "alert" : "status"}
      className={`flex items-start gap-2.5 rounded-lg border px-4 py-3 text-sm shadow-lg ${
        error
          ? "border-level-2/40 bg-level-2/10 text-yellow-900"
          : "border-ink-300/40 bg-white text-ink-600"
      }`}
    >
      {error ? (
        <TriangleAlert className="w-4 h-4 shrink-0 mt-0.5" />
      ) : (
        <Loader2 className="w-4 h-4 shrink-0 mt-0.5 motion-safe:animate-spin" />
      )}
      <span className="min-w-0">{error ?? `Generando ${descripcion}…`}</span>
      {/* Cerrar solo en el error: el aviso de «generando» se retira solo, y un botón que sugiere
          cancelar sin cancelar nada mentiría sobre lo que hace. */}
      {error && (
        <button
          type="button"
          onClick={onCerrar}
          aria-label="Cerrar el aviso"
          className="shrink-0 -mr-1 -mt-0.5 p-1 rounded hover:bg-level-2/20"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>,
    destino
  );
}
