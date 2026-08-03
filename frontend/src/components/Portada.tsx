import { portada, pieDeImagen, type TipoConPortada } from "@/lib/imagenes";

type Props = {
  tipo: TipoConPortada;
  imagen: string | null;
  pie: string | null;
  /** Texto alternativo: el título de la pieza, no el pie. */
  alt: string;
};

/** Imagen de cabecera de una ficha, con su pie. Resuelve el default cuando no hay imagen propia. */
export default function Portada({ tipo, imagen, pie, alt }: Props) {
  return (
    <figure className="mt-6">
      <img
        src={portada(tipo, imagen)}
        alt={alt}
        className="w-full aspect-[3/2] object-cover rounded-xl border border-mountain-900/10"
      />
      <figcaption className="mt-2 text-xs text-ink-600">{pieDeImagen(pie)}</figcaption>
    </figure>
  );
}
