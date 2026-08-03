import { Images } from "lucide-react";
import type { MedidaImagen } from "@/lib/types";

/**
 * Galería de una medida: grilla de figuras con su pie.
 *
 * Sin lightbox a propósito — abrir la foto a pantalla completa es alcance aparte y arrastra
 * manejo de foco y teclado que aquí no aporta a la validación.
 */
export default function GaleriaMedida({ imagenes }: { imagenes: MedidaImagen[] }) {
  if (!imagenes.length) return null;

  const ordenadas = [...imagenes].sort((a, b) => a.orden - b.orden);

  return (
    <section className="mt-8">
      <h2 className="flex items-center gap-2 font-display font-semibold text-mountain-900 mb-3">
        <Images className="w-4 h-4 text-mountain-700" />
        Galería
      </h2>
      <div className="grid sm:grid-cols-2 gap-4">
        {ordenadas.map((img) => (
          <figure key={img.imagen + img.orden}>
            <img
              src={img.imagen}
              alt={img.pie}
              loading="lazy"
              className="w-full aspect-[3/2] object-cover rounded-xl border border-mountain-900/10"
            />
            <figcaption className="mt-2 text-xs text-ink-600">{img.pie}</figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}
