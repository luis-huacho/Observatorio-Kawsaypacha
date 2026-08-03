import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Lightbulb, Sprout, AlertTriangle, MapPin } from "lucide-react";
import { useApiPaginado } from "@/lib/api";
import { facetasDe, type Facetas } from "@/lib/search";
import type { Medida } from "@/lib/types";
import { PELIGROS } from "@/lib/types";
import EmptyState from "@/components/EmptyState";
import PageHeader from "@/components/PageHeader";
import Reveal from "@/components/Reveal";
import FiltroTema from "@/components/FiltroTema";

/** Se exporta porque la ficha muestra el mismo chip de resultado. */
export const RESULTADO_ESTILO: Record<
  Medida["resultado"],
  { label: string; color: string; Icon: typeof Lightbulb }
> = {
  exito: { label: "Práctica exitosa", color: "bg-level-1/15 text-level-1 border-level-1/30", Icon: Sprout },
  leccion: { label: "Lección aprendida", color: "bg-level-2/20 text-yellow-800 border-level-2/40", Icon: Lightbulb },
  mal_adaptacion: { label: "Mal-adaptación", color: "bg-level-4/15 text-level-4 border-level-4/30", Icon: AlertTriangle },
};

export default function Medidas() {
  // El selector guarda el SLUG del peligro, que es lo que filtra el API. Antes guardaba el
  // nombre y la constante listaba nombres que no existían en los datos, así que el filtro
  // devolvía cero resultados (spec 06).
  const [peligro, setPeligro] = useState("");
  const [ambito, setAmbito] = useState("");
  const [resultado, setResultado] = useState("");
  const [params, setParams] = useSearchParams();
  const tema = params.get("tema") ?? "";

  const medidas = useApiPaginado<Medida>("/medidas/", { peligro, ambito, resultado, tema });
  const filtradas = medidas.resultados;

  // Conteos por faceta desde Meilisearch. Si no está disponible, `facetasDe` devuelve {} y los
  // selectores se muestran sin números: el filtro sigue funcionando contra el API.
  const [facetas, setFacetas] = useState<Facetas>({});
  useEffect(() => {
    let vigente = true;
    void facetasDe("medidas", ["peligro", "ambito", "resultado", "provincia"]).then((f) => {
      if (vigente) setFacetas(f);
    });
    return () => {
      vigente = false;
    };
  }, []);

  // Sin estas guardas, durante el fetch `filtradas` es [] y se pinta "Sin medidas con esos
  // filtros": un falso negativo que las demás rutas ya evitaban.
  if (medidas.status === "loading" && !filtradas.length)
    return <div className="container-page py-12">Cargando…</div>;
  if (medidas.status === "error")
    return (
      <div className="container-page py-12">
        <EmptyState title="No se pudieron cargar las medidas" message={medidas.error?.message} />
      </div>
    );

  return (
    <>
      <PageHeader
        titulo="Medidas"
        descripcion="¿Qué prácticas están funcionando para enfrentar peligros climáticos? Experiencias documentadas por PREDES y otras organizaciones: casos de éxito, lecciones aprendidas y advertencias de mal-adaptación."
      />
      <div className="container-page py-8">
      <div className="grid md:grid-cols-3 gap-3 mb-6">
        <Select
          label="Peligro"
          value={peligro}
          onChange={setPeligro}
          // Valor = slug (lo que filtra el API), etiqueta = nombre del catálogo.
          options={PELIGROS.map((p) => ({ value: p.slug, label: p.nombre }))}
          conteos={facetas.peligro}
        />
        <Select
          label="Ámbito"
          value={ambito}
          onChange={setAmbito}
          options={[
            { value: "comunal", label: "Comunal" },
            { value: "distrital", label: "Distrital" },
            { value: "provincial", label: "Provincial" },
            { value: "regional", label: "Regional" },
          ]}
          conteos={facetas.ambito}
        />
        <Select
          label="Resultado"
          value={resultado}
          onChange={setResultado}
          options={[
            { value: "exito", label: "Éxito" },
            { value: "leccion", label: "Lección aprendida" },
            { value: "mal_adaptacion", label: "Mala adaptación" },
          ]}
          conteos={facetas.resultado}
        />
      </div>

      <FiltroTema tema={tema} onLimpiar={() => setParams({})} />

      {filtradas.length === 0 ? (
        <EmptyState
          title="Sin medidas con esos filtros"
          message="Prueba con otro peligro, ámbito o palabra clave."
        />
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filtradas.map((m, i) => {
            const r = RESULTADO_ESTILO[m.resultado];
            return (
              <Reveal key={m.slug} delay={(i % 3) * 70}>
                <Link
                  to={`/medidas/${m.slug}`}
                  className="card block h-full overflow-hidden hover:shadow-md hover:-translate-y-0.5 transition duration-300 no-underline"
                >
                  <img
                    src={m.imagen_portada}
                    alt={m.titulo}
                    loading="lazy"
                    className="w-full aspect-[3/2] object-cover"
                  />
                  <div className="p-5">
                    <div className="flex items-center gap-2 mb-3">
                      <span className={`chip border ${r.color}`}>
                        <r.Icon className="w-3 h-3" />
                        {r.label}
                      </span>
                    </div>
                    <h3 className="font-display font-bold text-mountain-900 text-lg leading-tight">
                      {m.titulo}
                    </h3>
                    <div className="mt-2 flex items-center gap-1 text-xs text-ink-600">
                      <MapPin className="w-3 h-3" />
                      {m.comunidad}
                    </div>
                    <p className="mt-3 text-sm text-ink-600">{m.resumen_corto}</p>
                    <div className="mt-4 flex flex-wrap gap-1">
                      {m.palabras_clave.slice(0, 3).map((t) => (
                        <span key={t} className="chip bg-mountain-100 text-mountain-900 border border-mountain-500/20">
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                </Link>
              </Reveal>
            );
          })}
        </div>
      )}
      </div>
    </>
  );
}

function Select({
  label, value, onChange, options, conteos,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: readonly (string | { value: string; label: string })[];
  /**
   * Conteos por faceta de Meilisearch, indexados por la ETIQUETA que devuelve el índice (que es
   * la legible: "Comunal", "Sequía"), no por el valor del filtro. Si Meilisearch no está,
   * llega vacío y el selector se muestra sin números.
   */
  conteos?: Record<string, number>;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-ink-600 mb-1">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="control w-full"
      >
        <option value="">Todos</option>
        {options.map((o) => {
          const v = typeof o === "string" ? o : o.value;
          const l = typeof o === "string" ? o : o.label;
          const n = conteos?.[l];
          return (
            <option key={v} value={v}>
              {l}
              {n === undefined ? "" : ` (${n})`}
            </option>
          );
        })}
      </select>
    </div>
  );
}
