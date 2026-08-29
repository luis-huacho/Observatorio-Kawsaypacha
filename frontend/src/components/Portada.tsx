import { pieDeImagen, portada } from "@/lib/imagenes";

type Props = {
  /** URL ya resuelta por el API: propia o ilustración institucional del tipo de contenido. */
  imagen: string | null;
  pie: string | null;
  /** Texto alternativo: el título de la pieza, no el pie. */
  alt: string;
};

/** Imagen de cabecera de una ficha, con su pie. */
export default function Portada({ imagen, pie, alt }: Props) {
  return (
    <figure className="mt-6">
      {/* Sin `loading="lazy"`: es la imagen de cabecera de la ficha, o sea la LCP de esta página,
          y diferirla la retrasa. `width`/`height` van en la proporción real (3:2) para que el
          navegador reserve el hueco antes de descargarla; el tamaño lo sigue mandando el CSS. */}
      <img
        src={portada(imagen)}
        alt={alt}
        width={1200}
        height={800}
        decoding="async"
        className="w-full aspect-[3/2] object-cover rounded-xl border border-mountain-900/10"
      />
      <figcaption className="mt-2 text-xs text-ink-600">{pieDeImagen(pie)}</figcaption>
    </figure>
  );
}
