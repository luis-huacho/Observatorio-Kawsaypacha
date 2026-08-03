import { useMemo, useState, Suspense, lazy } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Filter, FlaskConical } from "lucide-react";
import { useJsonData } from "@/lib/useJsonData";
import type { CentroPoblado } from "@/lib/types";
import { PELIGROS } from "@/lib/types";
import GeoSelector from "@/components/GeoSelector";
import PageHeader from "@/components/PageHeader";

const MapaPeligrosGL = lazy(() => import("@/components/MapaPeligrosGL"));

/**
 * Vista de evaluación técnica: el mismo visor de exposición, pero sobre MapLibre GL + PMTiles
 * en lugar de Leaflet + GeoJSON. Sirve para comparar rendimiento y acabado antes de migrar
 * `/peligros`. Los tiles no se versionan, así que esta ruta solo existe en desarrollo.
 */
export default function PeligrosMapaNuevo() {
  const ccpp = useJsonData<CentroPoblado[]>("/data/ccpp.json");

  const [provincia, setProvincia] = useState("");
  const [distrito, setDistrito] = useState("");
  const [slug, setSlug] = useState<string>("");
  const [nivelMin, setNivelMin] = useState(0);

  // El tile filtra por ubigeo, no por nombre; el GeoSelector trabaja con nombres.
  const ubigeoDistrito = useMemo(() => {
    if (ccpp.status !== "ok" || !distrito) return "";
    return ccpp.data.find((c) => c.distrito === distrito)?.ubigeo_distrito ?? "";
  }, [ccpp, distrito]);

  return (
    <>
      <PageHeader
        titulo="Visor MapLibre + PMTiles"
        descripcion="Prueba técnica del visor de exposición sobre tiles vectoriales. Los 8,968 centros poblados viajan en un solo archivo PMTiles y el filtrado por peligro y nivel ocurre en el navegador, sin volver a pedir datos."
      />
      <div className="container-page py-8">
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <Link
            to="/peligros"
            className="inline-flex items-center gap-1 text-xs text-ink-600 hover:text-mountain-700"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Volver al visor actual (Leaflet)
          </Link>
          <span className="inline-flex items-center gap-1.5 chip border border-earth-500/40 bg-earth-200/40 text-earth-700 text-xs">
            <FlaskConical className="w-3.5 h-3.5" />
            Evaluación técnica — no forma parte de la plataforma publicada
          </span>
        </div>

        <div className="grid lg:grid-cols-[280px_1fr] gap-6">
          <aside className="card p-5 h-fit lg:sticky lg:top-20">
            <div className="flex items-center gap-2 mb-4">
              <Filter className="w-4 h-4 text-mountain-700" />
              <span className="font-display font-semibold text-mountain-900">Filtros</span>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-ink-600 mb-1">Ubicación</label>
                <GeoSelector
                  ccpp={ccpp.status === "ok" ? ccpp.data : []}
                  provincia={provincia}
                  distrito={distrito}
                  onChange={(p, d) => {
                    setProvincia(p);
                    setDistrito(d);
                  }}
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-ink-600 mb-1">
                  Tipo de peligro
                </label>
                <select
                  value={slug}
                  onChange={(e) => setSlug(e.target.value)}
                  className="control w-full"
                >
                  <option value="">Todos (nivel máximo)</option>
                  {PELIGROS.map((p) => (
                    <option key={p.slug} value={p.slug}>{p.nombre}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-ink-600 mb-1">Nivel mínimo</label>
                <div className="flex gap-1 bg-mountain-100/60 rounded-full p-1">
                  {[0, 1, 2, 3, 4].map((n) => (
                    <button
                      key={n}
                      onClick={() => setNivelMin(n)}
                      className={`flex-1 py-1.5 text-sm rounded-full transition ${
                        nivelMin === n
                          ? "bg-mountain-700 text-white shadow-sm"
                          : "text-ink-600 hover:bg-white"
                      }`}
                    >
                      {n === 0 ? "Todos" : n}
                    </button>
                  ))}
                </div>
              </div>

              <p className="pt-3 border-t border-ink-300/30 text-xs text-ink-600">
                Al cambiar de peligro o de nivel el mapa se recolorea al instante: los niveles de
                los nueve peligros viajan en el propio tile.
              </p>
            </div>
          </aside>

          <section>
            <div className="card p-1 h-[600px] overflow-hidden">
              {ccpp.status === "ok" ? (
                <Suspense
                  fallback={
                    <div className="h-full grid place-items-center text-ink-600">
                      Cargando mapa…
                    </div>
                  }
                >
                  <MapaPeligrosGL
                    ccpp={ccpp.data}
                    peligroSlug={slug || null}
                    nivelMin={nivelMin}
                    ubigeoDistrito={ubigeoDistrito}
                  />
                </Suspense>
              ) : (
                <div className="h-full grid place-items-center text-ink-600">Cargando mapa…</div>
              )}
            </div>

            <p className="mt-3 text-xs text-ink-600">
              Capas de contexto recortadas a Cusco desde las fuentes nacionales: 3,164 tramos de
              río, 2,512 lagunas y 1,155 glaciares. Genera los tiles con{" "}
              <code className="font-mono">bash prototype/scripts/build_tiles.sh</code>.
            </p>
          </section>
        </div>
      </div>
    </>
  );
}
