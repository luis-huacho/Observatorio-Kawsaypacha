import { useMemo } from "react";
import { urlEmbed } from "@/lib/video";

type Props = {
  html: string;
  className?: string;
};

/**
 * Renderiza el HTML que produce CKEditor 5 en el admin.
 *
 * Dos cosas hacen falta para que ese HTML se vea bien y no solo "se pinte":
 *
 * 1. **La clase `.contenido-rico`** (ver `index.css`). El Preflight de Tailwind resetea `h1..h6`
 *    a `font-size: inherit` y las listas a `list-style: none`, así que sin esos estilos un `<h2>`
 *    del editor saldría del tamaño de un párrafo y las listas sin viñetas.
 * 2. **Convertir el `<oembed>`**. Para los videos incrustados CKEditor no emite un iframe, sino
 *    `<figure class="media"><oembed url="…"></oembed></figure>`, que ningún navegador pinta.
 *
 * Sobre `dangerouslySetInnerHTML`: en el prototipo el HTML es nuestro. En la plataforma el
 * saneamiento va en el servidor, con lista blanca, antes de guardar — no aquí (ver spec 00).
 */
export default function ContenidoRico({ html, className = "" }: Props) {
  const procesado = useMemo(() => sustituirOembed(html), [html]);

  return (
    <div
      className={`contenido-rico ${className}`}
      dangerouslySetInnerHTML={{ __html: procesado }}
    />
  );
}

/** Cambia cada `<oembed url="…">` por un iframe responsivo; si la URL no se reconoce, un enlace. */
function sustituirOembed(html: string): string {
  return html.replace(
    /<oembed[^>]*\burl="([^"]+)"[^>]*>\s*<\/oembed>/gi,
    (_todo, url: string) => {
      const src = urlEmbed(url);
      if (!src) {
        // Mejor un enlace utilizable que un hueco mudo.
        return `<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`;
      }
      return (
        `<div class="video-embebido">` +
        `<iframe src="${src}" title="Video" allowfullscreen loading="lazy" ` +
        `allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture">` +
        `</iframe></div>`
      );
    }
  );
}
