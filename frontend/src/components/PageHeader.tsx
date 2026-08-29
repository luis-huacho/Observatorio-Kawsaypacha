import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ChevronLeft } from "lucide-react";

interface Props {
  titulo: string;
  descripcion?: ReactNode;
  eyebrow?: string;
  badge?: ReactNode;
  backTo?: string;
  backLabel?: string;
}

/** Banda de encabezado de página interior, estilo predes.org.pe. */
export default function PageHeader({ titulo, descripcion, eyebrow, badge, backTo, backLabel }: Props) {
  return (
    // `no-imprimir`: la banda de título es cromo de la web. Los documentos imprimibles traen su
    // propio membrete institucional.
    <section className="no-imprimir relative bg-gradient-to-r from-mountain-900 to-mountain-700 text-white">
      <div className="container-page pt-10 md:pt-12 pb-14 md:pb-16 animate-fade-up">
        {backTo && (
          <Link
            to={backTo}
            className="inline-flex items-center gap-1 text-sm text-white/80 hover:text-white no-underline mb-3"
          >
            <ChevronLeft className="w-4 h-4" /> {backLabel ?? "Volver"}
          </Link>
        )}
        <div className="flex flex-wrap items-start gap-3 justify-between">
          {/* `min-w-0` + `break-words`: el título de una norma llega hasta 300 caracteres y aquí se
              pinta a 36 px. Sin esto, un código sin espacios se sale de la banda. */}
          <div className="min-w-0">
            {eyebrow && (
              <div className="text-xs uppercase tracking-wider text-white/70 mb-1">{eyebrow}</div>
            )}
            <h1 className="font-display text-3xl md:text-4xl font-bold break-words">{titulo}</h1>
            {descripcion && <p className="text-white/85 mt-2 max-w-3xl">{descripcion}</p>}
          </div>
          {badge}
        </div>
      </div>
      <svg
        className="absolute bottom-0 left-0 w-full h-6 md:h-8 pointer-events-none"
        viewBox="0 0 1920 64"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <path d="M0,64 L0,48 C480,-16 1440,-16 1920,48 L1920,64 Z" fill="#FAFAF7" />
      </svg>
    </section>
  );
}
