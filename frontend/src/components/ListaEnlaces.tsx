import { ExternalLink, Link2 } from "lucide-react";
import type { EnlaceExterno } from "@/lib/types";

/**
 * «Enlaces relacionados» al pie de una ficha.
 *
 * Estaba suelto dentro de `MedidaDetalle` y se extrajo al añadir los enlaces de las noticias: es
 * el mismo bloque, y duplicarlo habría duplicado también el `rel="noopener noreferrer"`, que es
 * lo que impide que la página destino toque `window.opener`.
 *
 * Sirve a las dos fichas aunque el backend las guarde distinto —en `Medida` es un `JSONField` y
 * en `Noticia` una tabla—, porque el API entrega las mismas dos claves en los dos casos.
 *
 * Si no hay enlaces **no pinta nada**, ni siquiera el encabezado: a diferencia de la norma sin
 * `url_oficial`, aquí nadie prometió que la sección existiera, y anunciar la ausencia insinuaría
 * un olvido del editor donde no lo hay.
 */
export default function ListaEnlaces({
  enlaces,
  titulo = "Enlaces relacionados",
}: {
  enlaces: EnlaceExterno[];
  titulo?: string;
}) {
  if (!enlaces.length) return null;

  return (
    <section className="mt-8">
      <h2 className="flex items-center gap-2 font-display font-semibold text-mountain-900 mb-3">
        <Link2 className="w-4 h-4 text-mountain-700" />
        {titulo}
      </h2>
      <ul className="space-y-2">
        {enlaces.map((e, i) => (
          // La clave lleva el índice porque nada impide dar de alta dos veces la misma URL desde
          // el inline del admin, y una clave repetida es un aviso de React en consola —que el
          // e2e trata como fallo—.
          <li key={`${e.url}-${i}`}>
            <a
              href={e.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-sm"
            >
              {e.titulo}
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}
