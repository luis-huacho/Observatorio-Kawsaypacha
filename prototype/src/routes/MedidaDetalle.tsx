import { Link, useParams } from "react-router-dom";
import { ChevronLeft, MapPin } from "lucide-react";
import { useJsonData } from "@/lib/useJsonData";
import type { Medida } from "@/lib/types";
import MockBadge from "@/components/MockBadge";
import EmptyState from "@/components/EmptyState";

export default function MedidaDetalle() {
  const { slug } = useParams();
  const medidas = useJsonData<Medida[]>("/data/medidas.mock.json");

  if (medidas.status === "loading") return <div className="container-page py-12">Cargando…</div>;
  if (medidas.status !== "ok") return <div className="container-page py-12"><EmptyState /></div>;

  const m = medidas.data.find((x) => x.slug === slug);
  if (!m) {
    return (
      <div className="container-page py-12">
        <EmptyState
          title="Caso no encontrado"
          action={<Link to="/medidas" className="btn-primary">Ver todos</Link>}
        />
      </div>
    );
  }

  return (
    <article className="container-page py-8 max-w-3xl">
      <Link to="/medidas" className="inline-flex items-center gap-1 text-sm text-ink-600 hover:text-mountain-700 no-underline mb-4">
        <ChevronLeft className="w-4 h-4" /> Volver a medidas
      </Link>
      <MockBadge className="mb-3" />
      <h1 className="font-display text-3xl md:text-4xl font-bold text-mountain-900 leading-tight">
        {m.titulo}
      </h1>
      <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-ink-600">
        <span className="chip border border-level-3/30 bg-level-3/10 text-level-3">{m.peligro}</span>
        <span><MapPin className="w-3 h-3 inline mr-1" />{m.comunidad}</span>
        <span className="capitalize">Ámbito {m.ambito}</span>
      </div>

      <p className="mt-6 text-lg text-ink-900 leading-relaxed">{m.resumen_corto}</p>
      {m.contenido && (
        <div className="mt-4 text-ink-600 leading-relaxed whitespace-pre-wrap">{m.contenido}</div>
      )}

      <div className="mt-8 flex flex-wrap gap-1">
        {m.tags.map((t) => (
          <span key={t} className="chip bg-mountain-100 text-mountain-900 border border-mountain-500/20">
            {t}
          </span>
        ))}
      </div>
    </article>
  );
}
