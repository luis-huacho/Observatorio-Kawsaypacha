import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowRight, Download, FileText } from "lucide-react";
import { urlApi, useApiPaginado } from "@/lib/api";
import { registrarExport } from "@/lib/metricas";
import type { Norma } from "@/lib/types";
import { formatFecha } from "@/lib/semaforo";
import EmptyState from "@/components/EmptyState";
import PageHeader from "@/components/PageHeader";
import FiltroTema from "@/components/FiltroTema";
import EnlaceNorma, { PUBLICA } from "@/components/EnlaceNorma";

export default function NormativaView() {
  const [tipo, setTipo] = useState("");
  const [ambito, setAmbito] = useState("");
  const [params, setParams] = useSearchParams();
  const tema = params.get("tema") ?? "";

  const filtros = { tipo, ambito, tema };
  const normas = useApiPaginado<Norma>("/normativa/", filtros);
  const filtradas = normas.resultados;
  // El export respeta los filtros que el usuario tiene puestos: un Excel que no cuadra con lo
  // que había en pantalla es peor que no tener export.
  const urlExport = urlApi("/normativa/export.xlsx", filtros);

  if (normas.status === "loading" && !filtradas.length)
    return <div className="container-page py-12">Cargando…</div>;
  if (normas.status === "error")
    return (
      <div className="container-page py-12">
        <EmptyState title="No se pudo cargar la normativa" message={normas.error?.message} />
      </div>
    );

  return (
    <>
      <PageHeader
        titulo="Normativa"
        descripcion="Repositorio de normativa reciente de GRD y ACC, con análisis y recomendaciones de PREDES. Cada norma enlaza a su publicación oficial en el portal del organismo que la emite."
      />
      <div className="container-page py-8">
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
            <li key={n.slug} className="card p-5">
              <div className="flex items-start gap-4">
                <FileText className="w-5 h-5 text-mountain-700 mt-0.5 shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2 mb-1">
                    <span className="chip bg-mountain-100 text-mountain-900 border border-mountain-500/20">
                      {n.tipo}
                    </span>
                    {/* El número es lo que identifica la norma —«DS 048-2011-PCM»— y viaja en el
                        serializer desde siempre sin pintarse en ninguna parte. Aquí gana su sitio:
                        es lo que deja recortar el título sin que el usuario pierda de qué norma se
                        trata. */}
                    {n.numero && (
                      <span className="chip bg-mountain-100 text-mountain-900 border border-mountain-500/20">
                        {n.numero}
                      </span>
                    )}
                    <span className="chip bg-sky-200/40 text-sky-700 border border-sky-500/20">
                      {PUBLICA[n.ambito]}
                    </span>
                    <span className="text-xs text-ink-600">{formatFecha(n.fecha)}</span>
                  </div>
                  {/* Los tres bloques van recortados por CSS, no por JS: el texto entero sigue en
                      el DOM para el lector de pantalla y para Google, y `title` lo enseña al pasar
                      el ratón. `break-words` porque un código de norma sin espacios desborda la
                      tarjeta y `min-w-0` no lo evita —deja encoger, no parte la palabra—. */}
                  <h3 className="font-display font-bold text-mountain-900 leading-tight">
                    <Link
                      to={`/normativa/${n.slug}`}
                      title={n.titulo}
                      className="text-mountain-900 hover:text-mountain-700 no-underline line-clamp-2 break-words"
                    >
                      {n.titulo}
                    </Link>
                  </h3>
                  <p className="text-sm text-ink-600 mt-1 line-clamp-3 break-words">{n.resumen}</p>
                  {n.analisis_predes && (
                    <div className="mt-3 callout p-3 text-sm line-clamp-2 break-words">
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
