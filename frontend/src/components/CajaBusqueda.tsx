import { useRef } from "react";
import { Search, X } from "lucide-react";

/**
 * Caja de búsqueda con botón de limpiar.
 *
 * Existe para que el comportamiento viva en un solo sitio, porque el sitio tiene cuatro cajas en
 * React —`/buscar`, el filtro de la biblioteca y las dos de la cabecera— y las cuatro necesitan lo
 * mismo:
 *
 * - La «X» **solo cuando hay texto**, y con `type="button"`: dos de las cajas viven dentro de un
 *   `<form>` y un botón sin `type` lo enviaría al pulsarlo.
 * - **El foco vuelve al input** al limpiar. Sin eso hay que hacer clic otra vez para escribir, que
 *   es justo el trabajo manual que el botón venía a quitar.
 * - `Escape` limpia también, que es lo que espera cualquiera de un buscador. Cuando la caja ya está
 *   vacía no hace nada: la tecla sigue su camino en vez de quedarse aquí.
 *
 * La quinta caja —el buscador de centros poblados del visor— es un control de MapLibre construido
 * a mano y lleva su propia versión de esto en `MapaControles.ts`.
 *
 * `tono` **no cambia el comportamiento, solo el aspecto**: son las clases que cada caja ya tenía,
 * agrupadas para que ninguna cambie de pinta al pasar por aquí.
 */
type Tono = "claro" | "cabecera" | "cabecera-movil";

const TONOS: Record<Tono, { caja: string; icono: string; input: string; boton: string }> = {
  // Páginas: la clase `.control` del sistema de formularios.
  claro: {
    caja: "flex items-center gap-2 control",
    icono: "w-4 h-4 text-ink-600 shrink-0",
    input: "flex-1 min-w-0 bg-transparent border-0 outline-none text-sm",
    boton: "shrink-0 text-ink-600 hover:text-ink-900",
  },
  // Cabecera en escritorio. `w-40 xl:w-56` y los `min-w-0` son lo que mantiene el menú en una
  // línea: el buscador es el que cede espacio cuando falta (ver Header.tsx).
  cabecera: {
    caja:
      "flex items-center min-w-0 bg-white/95 rounded-lg border border-white/30 px-3 py-1.5 " +
      "focus-within:border-white transition",
    icono: "w-4 h-4 shrink-0 text-ink-600",
    input: "bg-transparent border-0 outline-none text-sm ml-2 w-40 xl:w-56 min-w-0 text-ink-900",
    boton: "shrink-0 ml-1 text-ink-600 hover:text-ink-900",
  },
  // Panel móvil: la píldora blanca a todo el ancho. El icono y la «X» van **dentro**, como en las
  // demás cajas; antes el icono vivía fuera, sobre el verde, y una «X» ahí se leería como un botón
  // ajeno al campo en vez de como «vaciar esto».
  "cabecera-movil": {
    caja:
      "flex items-center gap-2 min-w-0 bg-white/95 rounded-md px-3 py-2 border border-white/30",
    icono: "w-4 h-4 shrink-0 text-ink-600",
    input: "flex-1 min-w-0 bg-transparent border-0 outline-none text-sm text-ink-900",
    boton: "shrink-0 text-ink-600 hover:text-ink-900",
  },
};

type Props = {
  value: string;
  onChange: (valor: string) => void;
  placeholder: string;
  /** `aria-label` del input: cada caja busca en una cosa distinta y hay que decirlo. */
  etiqueta: string;
  tono?: Tono;
  /** Ancho o posición de la caja dentro de su contenedor. */
  className?: string;
};

export default function CajaBusqueda({
  value,
  onChange,
  placeholder,
  etiqueta,
  tono = "claro",
  className = "",
}: Props) {
  const campo = useRef<HTMLInputElement>(null);
  const estilo = TONOS[tono];

  function limpiar() {
    onChange("");
    campo.current?.focus();
  }

  return (
    <div className={`${estilo.caja} ${className}`.trim()}>
      <Search className={estilo.icono} />
      <input
        ref={campo}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Escape" && value) {
            e.preventDefault();
            limpiar();
          }
        }}
        placeholder={placeholder}
        className={estilo.input}
        aria-label={etiqueta}
      />
      {value && (
        <button
          type="button"
          onClick={limpiar}
          className={estilo.boton}
          aria-label="Limpiar búsqueda"
          title="Limpiar búsqueda"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}
