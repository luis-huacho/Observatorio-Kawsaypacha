import { useState } from "react";
import { Check, Facebook, Link2, Linkedin, Share2 } from "lucide-react";

type Props = {
  /** Titular de la pieza. Va en el texto que WhatsApp y X preponen al enlace. */
  titulo: string;
  /** Etiqueta del bloque; por defecto, la de una publicación. */
  etiqueta?: string;
};

/**
 * Barra de compartir al pie de una ficha.
 *
 * **La previsualización no la hace esto.** Lo que WhatsApp, Facebook o LinkedIn enseñan al pegar el
 * enlace sale de las metas Open Graph que inyecta el servidor (`apps/sitio/vistas_html.py`), no de
 * aquí: esos rastreadores no ejecutan JavaScript, así que nada que ponga React puede alcanzarlos.
 * Este componente solo abre el destino con la URL correcta.
 *
 * En móvil se usa `navigator.share`, que abre el menú del sistema y ofrece también los destinos que
 * el visitante tenga instalados —Telegram, correo, notas— en vez de imponer una lista nuestra. Los
 * botones de red son el repliegue de escritorio, donde esa API casi no existe.
 *
 * X no está: `twitter.com/intent` sigue funcionando pero el nombre y el icono de la marca cambiaron
 * y `lucide-react` ya retiró el suyo. Antes que pintar un logotipo desactualizado en una web
 * institucional, se deja «copiar enlace», que sirve para cualquier destino.
 */
export default function Compartir({ titulo, etiqueta = "Compartir esta publicación" }: Props) {
  const [copiado, setCopiado] = useState(false);
  // `window.location.href` y no una URL construida: es exactamente lo que el visitante está
  // mirando, incluidos los parámetros de filtro si los hubiera.
  const url = typeof window === "undefined" ? "" : window.location.href;

  const nativo = typeof navigator !== "undefined" && typeof navigator.share === "function";

  async function compartirNativo() {
    try {
      await navigator.share({ title: titulo, url });
    } catch {
      // El usuario canceló el diálogo, que no es un error. Cancelar y que salte un aviso sería
      // peor que no hacer nada.
    }
  }

  async function copiar() {
    try {
      await navigator.clipboard.writeText(url);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    } catch {
      // `clipboard` exige contexto seguro (HTTPS) y puede estar denegado. Se selecciona el enlace
      // para que el visitante lo copie a mano: mejor que un botón que no hace nada.
      window.prompt("Copia el enlace:", url);
    }
  }

  const destinos = [
    {
      nombre: "WhatsApp",
      // `text` lleva el título y el enlace juntos: WhatsApp no compone el mensaje por su cuenta.
      href: `https://wa.me/?text=${encodeURIComponent(`${titulo} ${url}`)}`,
      icono: <Share2 className="w-4 h-4" aria-hidden="true" />,
    },
    {
      nombre: "Facebook",
      href: `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`,
      icono: <Facebook className="w-4 h-4" aria-hidden="true" />,
    },
    {
      nombre: "LinkedIn",
      href: `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`,
      icono: <Linkedin className="w-4 h-4" aria-hidden="true" />,
    },
  ];

  return (
    // `no-imprimir`: compartir es cromo de la web; el PDF y la impresión llevan su propia portada.
    <section className="no-imprimir mt-10 pt-6 border-t border-ink-300/30">
      <h2 className="text-sm font-semibold text-mountain-900">{etiqueta}</h2>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {nativo && (
          <button type="button" onClick={compartirNativo} className="chip-accion">
            <Share2 className="w-4 h-4" aria-hidden="true" /> Compartir
          </button>
        )}
        {destinos.map((d) => (
          <a
            key={d.nombre}
            href={d.href}
            target="_blank"
            rel="noopener noreferrer"
            className="chip-accion no-underline"
          >
            {d.icono} {d.nombre}
          </a>
        ))}
        <button type="button" onClick={copiar} className="chip-accion">
          {copiado ? (
            <>
              <Check className="w-4 h-4" aria-hidden="true" /> Enlace copiado
            </>
          ) : (
            <>
              <Link2 className="w-4 h-4" aria-hidden="true" /> Copiar enlace
            </>
          )}
        </button>
      </div>
    </section>
  );
}
