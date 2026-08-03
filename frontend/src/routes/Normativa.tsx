import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowRight, FileText } from "lucide-react";
import { useJsonData } from "@/lib/useJsonData";
import type { Norma } from "@/lib/types";
import { formatFecha } from "@/lib/semaforo";
import EmptyState from "@/components/EmptyState";
import PageHeader from "@/components/PageHeader";
import FiltroTema from "@/components/FiltroTema";
import EnlaceNorma, { PUBLICA } from "@/components/EnlaceNorma";

export default function NormativaView() {
  const data = useJsonData<Norma[]>("/data/normativa.mock.json");
  const [tipo, setTipo] = useState("");
  const [ambito, setAmbito] = useState("");
  const [params, setParams] = useSearchParams();
  const tema = params.get("tema") ?? "";

  const filtradas = useMemo(() => {
    if (data.status !== "ok") return [];
    return data.data
      .filter((n) => (tipo ? n.tipo === tipo : true))
      .filter((n) => (ambito ? n.ambito === ambito : true))
      .filter((n) => (tema ? n.palabras_clave.includes(tema) : true))
      .sort((a, b) => b.fecha.localeCompare(a.fecha));
  }, [data, tipo, ambito, tema]);

  if (data.status === "loading") return <div className="container-page py-12">Cargando…</div>;
  if (data.status !== "ok") return <div className="container-page py-12"><EmptyState /></div>;

  return (
    <>
      <PageHeader
        titulo="Normativa"
        descripcion="Repositorio de normativa reciente de GRD y ACC, con análisis y recomendaciones de PREDES. Cada norma enlaza a su publicación oficial en el portal del organismo que la emite."
      />
      <div className="container-page py-8">
      <p className="text-xs text-ink-600 mb-5">
        En este prototipo los enlaces a las publicaciones oficiales son de ejemplo y apuntan al
        portal del organismo emisor. En la plataforma final cada norma llevará el enlace o el PDF
        que cargue el equipo de PREDES.
      </p>
      <div className="grid sm:grid-cols-2 gap-3 mb-6 max-w-xl">
        <select
          value={tipo}
          onChange={(e) => setTipo(e.target.value)}
          className="control"
        >
          <option value="">Todos los tipos</option>
          {["Ley", "DS", "RM", "RJ", "Ordenanza"].map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <select
          value={ambito}
          onChange={(e) => setAmbito(e.target.value)}
          className="control"
        >
          <option value="">Todos los ámbitos</option>
          <option value="nacional">Nacional</option>
          <option value="regional">Regional</option>
          <option value="local">Local</option>
        </select>
      </div>

      <FiltroTema tema={tema} onLimpiar={() => setParams({})} />

      {filtradas.length === 0 ? (
        <EmptyState
          title="Sin normas con esos filtros"
          message="Prueba con otro tipo, ámbito o palabra clave."
        />
      ) : (
        <ul className="space-y-3">
          {filtradas.map((n) => (
            /* La tarjeta tiene dos destinos —la ficha y la publicación oficial—, así que no puede
               ser un <Link> envolvente: anidar anclas es HTML inválido. Enlaza el título. */
            <li key={n.id} className="card p-5">
              <div className="flex items-start gap-4">
                <FileText className="w-5 h-5 text-mountain-700 mt-0.5 shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2 mb-1">
                    <span className="chip bg-mountain-100 text-mountain-900 border border-mountain-500/20">
                      {n.tipo}
                    </span>
                    <span className="chip bg-sky-200/40 text-sky-700 border border-sky-500/20">
                      {PUBLICA[n.ambito]}
                    </span>
                    <span className="text-xs text-ink-600">{formatFecha(n.fecha)}</span>
                  </div>
                  <h3 className="font-display font-bold text-mountain-900 leading-tight">
                    <Link
                      to={`/normativa/${n.slug}`}
                      className="text-mountain-900 hover:text-mountain-700 no-underline"
                    >
                      {n.titulo}
                    </Link>
                  </h3>
                  <p className="text-sm text-ink-600 mt-1">{n.resumen}</p>
                  {n.analisis_predes && (
                    <div className="mt-3 callout p-3 text-sm">
                      <span className="font-semibold text-mountain-900">Análisis PREDES: </span>
                      {n.analisis_predes}
                    </div>
                  )}
                  <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 pt-3 border-t border-ink-300/25">
                    <EnlaceNorma url={n.url_oficial} compacta />
                    <Link
                      to={`/normativa/${n.slug}`}
                      className="inline-flex items-center gap-1 text-xs text-mountain-700 hover:text-mountain-900"
                    >
                      Ver ficha completa <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
      </div>
    </>
  );
}
