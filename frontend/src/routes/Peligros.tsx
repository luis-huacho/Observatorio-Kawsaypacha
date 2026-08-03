import { useCallback, useEffect, useMemo, useRef, useState, Suspense, lazy } from "react";
import { Link } from "react-router-dom";
import { ChevronLeft, ChevronRight, FileText, Filter } from "lucide-react";
import { useJsonData } from "@/lib/useJsonData";
import type {
  CentroPoblado,
  ClasificacionPeligro,
  FrecuenciaDistrito,
  Nivel,
} from "@/lib/types";
import { PELIGROS } from "@/lib/types";
import { NIVEL_BG, NIVEL_LABEL, formatNumber } from "@/lib/semaforo";
import GeoSelector from "@/components/GeoSelector";
import SemaforoChip from "@/components/SemaforoChip";
import EmptyState from "@/components/EmptyState";
import PageHeader from "@/components/PageHeader";
import FrecuenciaEmergencias from "@/components/FrecuenciaEmergencias";
import ReporteImpresion from "@/components/ReporteImpresion";
import type { MapaPeligrosHandle } from "@/components/MapaPeligros";

const MapaPeligros = lazy(() => import("@/components/MapaPeligros"));

const POR_PAGINA = 50;

/** Datos congelados en el momento de pulsar "ayuda memoria". */
type Reporte = { mapaPng: string | null; mapaBase: string; generadoEn: Date };

export default function Peligros() {
  const ccpp = useJsonData<CentroPoblado[]>("/data/ccpp.json");
  const peligros = useJsonData<ClasificacionPeligro[]>("/data/peligros.json");
  const frecuencia = useJsonData<FrecuenciaDistrito[]>("/data/frecuencia.json");

  const [provincia, setProvincia] = useState("");
  const [distrito, setDistrito] = useState("");
  // El selector guarda el slug del catálogo PELIGROS; el filtro sobre las clasificaciones
  // compara por nombre, así que hace falta traducirlo.
  const [slug, setSlug] = useState("");
  const [nivelMin, setNivelMin] = useState(0);
  const [pagina, setPagina] = useState(1);

  const nombrePeligro = useMemo(
    () => PELIGROS.find((p) => p.slug === slug)?.nombre ?? "",
    [slug]
  );

  // Solo para citarlo en la ayuda memoria imprimible; el GeoSelector trabaja con nombres.
  // Se acota por provincia además de por distrito: buscar solo por nombre daba el ubigeo
  // equivocado ante distritos homónimos de provincias distintas.
  const ubigeoDistrito = useMemo(() => {
    if (ccpp.status !== "ok" || !distrito) return "";
    return (
      ccpp.data.find(
        (c) => c.distrito === distrito && (!provincia || c.provincia === provincia)
      )?.ubigeo_distrito ?? ""
    );
  }, [ccpp, distrito, provincia]);

  const ccppFiltrados = useMemo(() => {
    if (ccpp.status !== "ok") return [];
    return ccpp.data.filter((c) => {
      if (provincia && c.provincia !== provincia) return false;
      if (distrito && c.distrito !== distrito) return false;
      return true;
    });
  }, [ccpp, provincia, distrito]);

  const peligrosFiltrados = useMemo(() => {
    if (peligros.status !== "ok") return [];
    const codigos = new Set(ccppFiltrados.map((c) => c.codigo));
    return peligros.data.filter((p) => {
      if (!codigos.has(p.codigo_ccpp)) return false;
      if (nombrePeligro && p.peligro !== nombrePeligro) return false;
      if (nivelMin && p.nivel < nivelMin) return false;
      return true;
    });
  }, [peligros, ccppFiltrados, nombrePeligro, nivelMin]);

  // Nivel máximo por centro poblado, precalculado una vez: la tabla lo leía con un filter()
  // por fila, lo que con 10,978 clasificaciones se notaba al teclear en los filtros.
  const nivelMaxPorCcpp = useMemo(() => {
    const max = new Map<string, Nivel>();
    for (const p of peligrosFiltrados) {
      const actual = max.get(p.codigo_ccpp);
      if (actual === undefined || p.nivel > actual) max.set(p.codigo_ccpp, p.nivel as Nivel);
    }
    return max;
  }, [peligrosFiltrados]);

  // Se cuenta cada centro poblado una sola vez, en su nivel más alto: es la misma unidad que la
  // tabla de abajo y que el mapa. Contar clasificaciones daba 225 donde la tabla mostraba 75 CCPP,
  // porque los 75 centros poblados de ACOMAYO tienen 3 peligros evaluados cada uno.
  const stats = useMemo(() => {
    const counts: Record<Nivel, number> = { 1: 0, 2: 0, 3: 0, 4: 0 };
    for (const nivel of nivelMaxPorCcpp.values()) counts[nivel]++;
    return counts;
  }, [nivelMaxPorCcpp]);

  // La tabla lista solo los clasificados, ordenados por gravedad: incluir el padrón completo la
  // convertía en una lista de "sin dato" (5,730 de 8,968 en toda la región). Emparejar aquí el
  // centro poblado con su nivel deja el tipo como Nivel y no Nivel | undefined.
  const filasTabla = useMemo(() => {
    return ccppFiltrados
      .flatMap((c) => {
        const nivel = nivelMaxPorCcpp.get(c.codigo);
        return nivel ? [{ ccpp: c, nivel }] : [];
      })
      .sort((a, b) => b.nivel - a.nivel || a.ccpp.nombre.localeCompare(b.ccpp.nombre, "es"));
  }, [ccppFiltrados, nivelMaxPorCcpp]);

  const sinClasificar = ccppFiltrados.length - filasTabla.length;

  // Los puntos del mapa se arman aquí y no desde el tile vectorial: el clustering de MapLibre solo
  // opera sobre fuentes GeoJSON. Partir de `ccppFiltrados` y `nivelMaxPorCcpp` hace además que el
  // visor herede exactamente los mismos filtros que la tabla — antes el mapa solo sabía del
  // distrito, así que al elegir únicamente una provincia seguía dibujando toda la región.
  const puntosMapa = useMemo<GeoJSON.FeatureCollection<GeoJSON.Point>>(() => {
    // El popup necesita el desglose por peligro; agruparlo una vez evita recorrer las
    // clasificaciones por cada centro poblado.
    const porCcpp = new Map<string, { peligro: string; nivel: Nivel }[]>();
    for (const p of peligrosFiltrados) {
      const lista = porCcpp.get(p.codigo_ccpp);
      const item = { peligro: p.peligro, nivel: p.nivel as Nivel };
      if (lista) lista.push(item);
      else porCcpp.set(p.codigo_ccpp, [item]);
    }

    const features = ccppFiltrados.flatMap<GeoJSON.Feature<GeoJSON.Point>>((c) => {
      if (c.lat == null || c.lon == null) return [];
      const clasif = (porCcpp.get(c.codigo) ?? []).sort((a, b) => b.nivel - a.nivel);
      return [
        {
          type: "Feature",
          geometry: { type: "Point", coordinates: [c.lon, c.lat] },
          properties: {
            codigo: c.codigo,
            nombre: c.nombre,
            categoria: c.categoria,
            distrito: c.distrito,
            provincia: c.provincia,
            poblacion: c.poblacion ?? 0,
            altitud: c.altitud ?? null,
            // 0 = sin clasificación; el mapa lo pinta gris en vez de tratarlo como nivel bajo.
            nivel: nivelMaxPorCcpp.get(c.codigo) ?? 0,
            // Serializado: las propiedades que sobreviven al worker de clustering son escalares.
            clasif: JSON.stringify(clasif),
          },
        },
      ];
    });

    return { type: "FeatureCollection", features };
  }, [ccppFiltrados, nivelMaxPorCcpp, peligrosFiltrados]);

  const totalPaginas = Math.max(1, Math.ceil(filasTabla.length / POR_PAGINA));
  const desde = (pagina - 1) * POR_PAGINA;
  const visibles = filasTabla.slice(desde, desde + POR_PAGINA);

  // Cualquier cambio de filtro deja la paginación sin sentido.
  useEffect(() => {
    setPagina(1);
  }, [provincia, distrito, slug, nivelMin]);

  const cargando = ccpp.status === "loading" || peligros.status === "loading";

  // --- Ayuda memoria imprimible --------------------------------------------------------------
  const mapaRef = useRef<MapaPeligrosHandle>(null);
  const [reporte, setReporte] = useState<Reporte | null>(null);
  const [generando, setGenerando] = useState(false);

  const frecuenciaDistrito = useMemo(
    () =>
      frecuencia.status === "ok" && distrito
        ? frecuencia.data.find((d) => d.distrito === distrito)
        : undefined,
    [frecuencia, distrito]
  );

  const generarAyudaMemoria = useCallback(async () => {
    setGenerando(true);
    let mapaPng: string | null = null;
    let mapaBase = "";
    try {
      mapaPng = (await mapaRef.current?.capturarPNG()) ?? null;
      mapaBase = mapaRef.current?.mapaBaseActivo() ?? "";
    } catch (err) {
      // Un mapa base sin CORS contamina el canvas. El documento sigue teniendo valor sin la
      // imagen, así que se ofrece continuar en vez de abortar la descarga entera.
      console.error("No se pudo capturar el mapa:", err);
      const seguir = window.confirm(
        "No se pudo incluir la imagen del mapa: el mapa base actual no permite exportarla. " +
          "¿Generar la ayuda memoria sin el mapa?"
      );
      if (!seguir) {
        setGenerando(false);
        return;
      }
    }
    setReporte({ mapaPng, mapaBase, generadoEn: new Date() });
  }, []);

  // El diálogo de impresión debe abrirse cuando el documento ya está en el DOM y la imagen del
  // mapa decodificada; si no, el PDF sale con el hueco en blanco.
  useEffect(() => {
    if (!reporte) return;
    let cancelado = false;

    const limpiar = () => {
      setGenerando(false);
      setReporte(null);
    };

    const imprimir = async () => {
      const img = document.querySelector<HTMLImageElement>(".solo-impresion img[alt^='Mapa']");
      if (img) {
        try {
          await img.decode();
        } catch {
          /* Si la imagen no decodifica, se imprime igual: el resto del documento es válido. */
        }
      }
      if (cancelado) return;
      // El listener va antes del print(): en algunos navegadores la llamada es bloqueante y
      // afterprint se dispara sin que print() haya retornado. Desmontar el documento a mano
      // después de print() puede vaciarlo antes de que el diálogo lo haya leído.
      window.addEventListener("afterprint", limpiar, { once: true });
      window.print();
    };

    imprimir();
    return () => {
      cancelado = true;
      window.removeEventListener("afterprint", limpiar);
    };
  }, [reporte]);

  return (
    <>
      <PageHeader
        titulo="Exposición a peligros naturales"
        descripcion="Mapa de exposición a peligros climáticos y geodinámicos en los centros poblados de Cusco. Datos provenientes de SIGRID-CENEPRED. Activa o desactiva las capas geográficas (lagunas, ríos, glaciares) desde el control superior derecho del mapa."
        badge={
          <button
            type="button"
            onClick={generarAyudaMemoria}
            disabled={!distrito || generando}
            title={
              distrito
                ? `Genera un documento imprimible del distrito de ${distrito} con los filtros actuales`
                : "Selecciona un distrito para generar la ayuda memoria"
            }
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white text-mountain-900 text-sm font-medium transition hover:bg-mountain-100 disabled:bg-white/25 disabled:text-white/70 disabled:cursor-not-allowed"
          >
            <FileText className="w-4 h-4" />
            {generando ? "Generando…" : "Ayuda memoria (PDF)"}
          </button>
        }
      />

      {/* El documento imprimible: oculto en pantalla, es lo único que se ve al imprimir. */}
      {reporte && (
        <ReporteImpresion
          ccpp={ccppFiltrados}
          clasificaciones={peligrosFiltrados}
          stats={stats}
          frecuencia={frecuenciaDistrito}
          provincia={provincia}
          distrito={distrito}
          ubigeoDistrito={ubigeoDistrito}
          nombrePeligro={nombrePeligro}
          nivelMin={nivelMin}
          mapaPng={reporte.mapaPng}
          mapaBase={reporte.mapaBase}
          generadoEn={reporte.generadoEn}
        />
      )}

      <div className="container-page py-8 no-imprimir">
      <div className="grid lg:grid-cols-[280px_1fr] gap-6">
        {/* Filtros */}
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
              <label className="block text-xs font-medium text-ink-600 mb-1">Tipo de peligro</label>
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
              <label className="block text-xs font-medium text-ink-600 mb-1">
                Nivel mínimo
              </label>
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

            <div className="pt-3 border-t border-ink-300/30">
              {/* Decir la unidad evita leer estos conteos como número de clasificaciones: cada
                  centro poblado aparece una sola vez, en el más alto de sus peligros evaluados. */}
              <div className="text-xs text-ink-600">Distribución</div>
              <div className="text-[10px] text-ink-300 mb-2">
                por centro poblado (nivel máximo)
              </div>
              <div className="space-y-1">
                {([4, 3, 2, 1] as Nivel[]).map((n) => (
                  <div key={n} className="flex items-center justify-between text-xs">
                    <SemaforoChip nivel={n} />
                    <span className="font-mono font-semibold">{formatNumber(stats[n])}</span>
                  </div>
                ))}
              </div>
              <div className="flex items-center justify-between text-xs mt-2 pt-2 border-t border-ink-300/30">
                <span className="text-ink-600">Total</span>
                <span className="font-mono font-semibold">
                  {formatNumber(filasTabla.length)} CCPP
                </span>
              </div>
            </div>
          </div>
        </aside>

        {/* Mapa */}
        <section>
          <div className="mb-2">
            <span className="text-xs text-ink-600">
              Capas geográficas activables: lagunas, ríos y glaciares.
            </span>
          </div>
          <div className="card p-1 h-[600px] overflow-hidden">
            {cargando ? (
              <div className="h-full grid place-items-center text-ink-600">Cargando mapa…</div>
            ) : ccpp.status === "ok" && peligros.status === "ok" ? (
              <Suspense fallback={<div className="h-full grid place-items-center text-ink-600">Cargando mapa…</div>}>
                <MapaPeligros
                  ref={mapaRef}
                  ccpp={ccpp.data}
                  puntos={puntosMapa}
                  peligroSlug={slug || null}
                  ambitoAcotado={Boolean(provincia || distrito)}
                />
              </Suspense>
            ) : (
              <EmptyState title="Error al cargar datos" message="No pudimos leer los datasets de centros poblados." />
            )}
          </div>

          {/* Frecuencia histórica de emergencias del distrito seleccionado */}
          <FrecuenciaEmergencias
            frecuencia={frecuencia.status === "ok" ? frecuencia.data : []}
            distrito={distrito}
          />

          {/* Lista compacta */}
          <div className="card mt-4 p-5">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
              <h2 className="font-display font-semibold text-mountain-900">
                Centros poblados con clasificación de peligro
              </h2>
              <span className="text-sm text-ink-600">
                {formatNumber(filasTabla.length)} CCPP
                {/* Decirlo evita que la tabla se lea como el padrón completo: no tener
                    clasificación no es lo mismo que no tener riesgo. */}
                {sinClasificar > 0 && (
                  <span className="text-ink-300">
                    {" · "}
                    {formatNumber(sinClasificar)} sin clasificación
                  </span>
                )}
              </span>
            </div>
            {filasTabla.length === 0 ? (
              <EmptyState
                title={
                  sinClasificar > 0 ? "Sin clasificaciones registradas" : "Sin centros poblados"
                }
                message={
                  sinClasificar > 0
                    ? `Los ${formatNumber(sinClasificar)} centros poblados del ámbito no tienen ` +
                      "clasificación de peligro para los filtros aplicados. La ausencia de dato no " +
                      "equivale a ausencia de riesgo."
                    : "Ningún centro poblado coincide con los filtros actuales."
                }
              />
            ) : (
              <>
                <div className="-mx-2 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="text-xs text-ink-600 uppercase tracking-wide">
                      <tr>
                        <th className="text-left px-2 py-2">Centro poblado</th>
                        <th className="text-left px-2 py-2 hidden sm:table-cell">Distrito</th>
                        <th className="text-right px-2 py-2">Población</th>
                        <th className="text-center px-2 py-2">Nivel</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibles.map(({ ccpp: c, nivel }) => (
                        <tr key={c.codigo} className="border-t border-ink-300/20 hover:bg-mountain-100/40">
                          <td className="px-2 py-2">
                            <Link className="text-mountain-900 hover:text-mountain-700 no-underline" to={`/peligros/${c.codigo}`}>
                              {c.nombre}
                            </Link>
                            <div className="text-xs text-ink-600">{c.categoria}</div>
                          </td>
                          <td className="px-2 py-2 hidden sm:table-cell text-ink-600">{c.distrito}</td>
                          <td className="px-2 py-2 text-right font-mono">
                            {c.poblacion != null ? formatNumber(c.poblacion) : "—"}
                          </td>
                          <td className="px-2 py-2 text-center">
                            <span className={`chip border ${NIVEL_BG[nivel]}`}>
                              {NIVEL_LABEL[nivel]}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-3 mt-3 pt-3 border-t border-ink-300/30">
                  <span className="text-xs text-ink-600">
                    Mostrando {formatNumber(desde + 1)}–
                    {formatNumber(Math.min(desde + POR_PAGINA, filasTabla.length))} de{" "}
                    {formatNumber(filasTabla.length)} centros poblados clasificados
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setPagina((p) => Math.max(1, p - 1))}
                      disabled={pagina === 1}
                      className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded border border-ink-300/40 text-ink-600 hover:bg-mountain-100 disabled:opacity-40 disabled:hover:bg-transparent"
                    >
                      <ChevronLeft className="w-3.5 h-3.5" />
                      Anterior
                    </button>
                    <span className="text-xs text-ink-600 font-mono">
                      {pagina} / {formatNumber(totalPaginas)}
                    </span>
                    <button
                      onClick={() => setPagina((p) => Math.min(totalPaginas, p + 1))}
                      disabled={pagina >= totalPaginas}
                      className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded border border-ink-300/40 text-ink-600 hover:bg-mountain-100 disabled:opacity-40 disabled:hover:bg-transparent"
                    >
                      Siguiente
                      <ChevronRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </section>
      </div>
      </div>
    </>
  );
}
