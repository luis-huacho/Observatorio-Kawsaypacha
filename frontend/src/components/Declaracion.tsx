/**
 * La frase que dice lo que el gráfico de encima enseña.
 *
 * Mismo registro que las `.declaracion` del PDF —filete a la izquierda, texto pequeño y gris—
 * porque es literalmente la misma frase: **la redacta el backend** y viaja en el payload
 * (`apps/inversion/declaraciones.py`), que es lo que impide que la pantalla y el documento
 * acaben diciendo cosas distintas. Aquí solo se pinta. **Sin verde ni rojo a propósito**:
 * `Delta` colorea porque compara dos ejercicios que alguien eligió; aquí más presupuesto no es
 * de suyo una buena noticia, y pintarlo de verde sería opinar por el lector.
 *
 * Devuelve `null` con contenido vacío, para que un ámbito sin datos no deje un filete huérfano.
 *
 * Vive aquí y no dentro de `Inversion.tsx` desde que el mapa tiene la suya: era el único gráfico
 * de la página sin una, y la del mapa se pinta dentro de `MapaInversion` para que quede pegada
 * a la caja que describe.
 */
export default function Declaracion({ children }: { children: string | null }) {
  if (!children) return null;
  return (
    <p className="mt-4 border-l-2 border-earth-500 pl-3 text-xs leading-relaxed text-ink-600">
      {children}
    </p>
  );
}
