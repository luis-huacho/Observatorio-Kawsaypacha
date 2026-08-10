import { iconoDe } from "@/lib/iconosPeligro";
import { NIVEL_COLOR, NIVEL_LABEL } from "@/lib/semaforo";
import type { PeligroDeCcpp, TipoPeligroApi } from "@/lib/types";

type Props = {
  peligros: PeligroDeCcpp[];
  /** Catálogo del API: de ahí sale el ícono de cada tipo. */
  tipos: TipoPeligroApi[];
};

/**
 * Los peligros de un centro poblado, con **el mismo lenguaje visual que el mapa**: la forma
 * dice el tipo y el color dice el nivel.
 *
 * Se listan todos y no solo el máximo. Un lugar con «Muy alto» no dice a qué está expuesto, y
 * es a lo que está expuesto lo que decide qué medida le toca; con 3.4 peligros de media por
 * centro poblado, el resumen escondía la mayor parte de lo evaluado.
 *
 * Cada ícono lleva su nivel en el `title` y en un texto solo para lectores de pantalla: el
 * color no puede ser el único canal que distinga «Muy alto» de «Bajo».
 */
export default function ListaPeligrosCcpp({ peligros, tipos }: Props) {
  if (!peligros.length) {
    return <span className="text-xs text-ink-300">Sin clasificación</span>;
  }
  const iconoPorSlug = new Map(tipos.map((t) => [t.slug, t.icono]));

  return (
    <ul className="flex flex-wrap gap-x-3 gap-y-1 m-0 p-0 list-none">
      {peligros.map((p) => {
        const Icono = iconoDe(iconoPorSlug.get(p.slug));
        return (
          <li
            key={p.slug}
            title={`${p.nombre}: ${NIVEL_LABEL[p.nivel]}`}
            className="flex items-center gap-1 text-xs"
          >
            <Icono
              className="w-4 h-4 shrink-0"
              style={{ color: NIVEL_COLOR[p.nivel] }}
              aria-hidden
            />
            <span className="text-ink-900">{p.nombre}</span>
            <span className="sr-only">: {NIVEL_LABEL[p.nivel]}</span>
          </li>
        );
      })}
    </ul>
  );
}
