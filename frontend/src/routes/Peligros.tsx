import { useMemo, useRef, useState, Suspense, lazy } from "react";
import { Link } from "react-router-dom";
import { ChevronRight, Download, FileText, Filter, RotateCcw } from "lucide-react";
import { urlApi, useApi, useApiPaginado } from "@/lib/api";
import { registrarAyudaMemoria, registrarExport } from "@/lib/metricas";
import type {
  CapaMapa,
  CentroPoblado,
  Distrito,
  Nivel,
  Provincia,
  ResumenPeligros,
  TipoPeligroApi,
} from "@/lib/types";
import { iconoDe } from "@/lib/iconosPeligro";
import { NIVEL_BG, NIVEL_COLOR, NIVEL_LABEL, formatNumber } from "@/lib/semaforo";
import GeoSelector from "@/components/GeoSelector";
import ChecklistFiltro from "@/components/ChecklistFiltro";
import ResultadosExposicion from "@/components/ResultadosExposicion";
import ListaPeligrosCcpp from "@/components/ListaPeligrosCcpp";
import EmptyState from "@/components/EmptyState";
import PageHeader from "@/components/PageHeader";
import type { MapaPeligrosHandle } from "@/components/MapaPeligros";

const MapaPeligros = lazy(() => import("@/components/MapaPeligros"));

/**
 * Filas por página de la tabla.
 *
 * **Se manda al API.** Antes era un literal decorativo que solo salía en el texto del botón
 * mientras el servidor paginaba por su `PAGE_SIZE` de 50: cambiarlo aquí no cambiaba nada.
 * `apps/api/paginacion.py` acepta `page_size` por querystring, con tope 200.
 */
const POR_PAGINA = 20;
/** De más grave a menos: es el orden en que se lee un semáforo de riesgo. */
const NIVELES: Nivel[] = [4, 3, 2, 1];

/**
 * Exposición a peligros: qué centros poblados están expuestos, a qué y en qué nivel.
 *
 * La página responde **una sola pregunta**. La frecuencia histórica de emergencias —el otro eje
 * de la fuente, que cuenta lo que ya ocurrió, por distrito y con otra taxonomía— se retiró de
 * aquí: mezclarlas hacía que los filtros de esta pantalla no afectaran a aquel panel y la
 * pantalla pareciera mal calculada. Sus modelos, endpoints y el PDF siguen intactos, a la
 * espera de dónde reubicarla.
 */
export default function Peligros() {
  const [provincia, setProvincia] = useState("");
  const [distrito, setDistrito] = useState("");
  // Selección múltiple. `null` = "aún no se ha tocado", que se resuelve a "todos" en cuanto
  // llega el catálogo: sin esto el primer render filtraría por una lista vacía.
  const [tipos, setTipos] = useState<string[] | null>(null);
  const [niveles, setNiveles] = useState<Nivel[]>(NIVELES);

  const tablaRef = useRef<HTMLDivElement>(null);

  // Catálogo territorial para el GeoSelector: 13 + 112 filas, sin paginar. Va ANTES de
  // `filtros`: ese memo traduce nombre → ubigeo leyendo estas listas, y declararlas después
  // dejaba a `provincias` en la zona muerta temporal. No fallaba hasta elegir una provincia,
  // porque sin nombre la traducción cortocircuitaba antes de tocarla.
  const provincias = useApi<Provincia[]>("/territorio/provincias/");
  const distritos = useApi<Distrito[]>("/territorio/distritos/");

  // Catálogo de peligros: nombre, orden, color e **ícono**. Sustituye a la constante `PELIGROS`
  // del cliente para que añadir un peligro en el admin no exija desplegar el frontend.
  const catalogo = useApi<TipoPeligroApi[]>("/peligros/tipos/");
  const peligros = useMemo(
    () => (catalogo.status === "ok" ? catalogo.data : []),
    [catalogo.status, catalogo.status === "ok" ? catalogo.data : null]
  );
  const seleccionTipos = tipos ?? peligros.map((p) => p.slug);

  const nombreAUbigeoProvincia = useMemo(() => {
    const mapa = new Map<string, string>();
    if (provincias.status === "ok") {
      for (const p of provincias.data) mapa.set(p.nombre, p.ubigeo);
    }
    return mapa;
  }, [provincias.status, provincias.status === "ok" ? provincias.data : null]);

  /**
   * Nombre de distrito → ubigeo, **acotando por provincia**.
   *
   * Buscar solo por nombre devuelve el primer homónimo de cualquier provincia. En Cusco hoy no
   * hay colisiones, pero la suposición era implícita y basta una fusión de distritos para que
   * deje de cumplirse.
   */
  const ubigeoDistrito = useMemo(() => {
    if (distritos.status !== "ok" || !distrito) return "";
    const candidatos = distritos.data.filter((d) => d.nombre === distrito);
    if (candidatos.length === 1) return candidatos[0].ubigeo;
    return candidatos.find((d) => d.provincia === provincia)?.ubigeo ?? "";
  }, [distritos.status, distritos.status === "ok" ? distritos.data : null, distrito, provincia]);

  /**
   * Desmarcar todo es un estado real y significa «nada», no «todo».
   *
   * Mandar la lista completa o no mandarla es equivalente para el API, así que cuando están
   * todas marcadas se omite el parámetro: así la vista sin filtros comparte entrada de caché
   * con la de arranque en vez de duplicarla.
   */
  const vacio = seleccionTipos.length === 0 || niveles.length === 0;

  const filtros = useMemo(
    () => ({
      provincia: nombreAUbigeoProvincia.get(provincia) ?? "",
      distrito: ubigeoDistrito,
      peligros:
        seleccionTipos.length && seleccionTipos.length < peligros.length
          ? [...seleccionTipos].sort().join(",")
          : undefined,
      niveles:
        niveles.length && niveles.length < 4 ? [...niveles].sort().join(",") : undefined,
    }),
    [nombreAUbigeoProvincia, provincia, ubigeoDistrito, seleccionTipos, niveles, peligros.length]
  );

  // Cifras de la grilla de resultados. Vienen agregadas: contarlas en el cliente exigiría
  // descargar las 10,978 clasificaciones (spec 06).
  const resumen = useApi<ResumenPeligros>(vacio ? null : "/peligros/resumen/", filtros);
  // Tabla: solo los clasificados, paginados de 50 en 50 por el servidor.
  const tabla = useApiPaginado<CentroPoblado>(vacio ? null : "/ccpp/", {
    ...filtros,
    clasificados: 1,
    page_size: POR_PAGINA,
  });
  // Puntos del visor: FeatureCollection ya filtrado (ADR-A13). El mapa hereda exactamente los
  // mismos filtros que la tabla porque los dos salen de `filtros`.
  const puntos = useApi<GeoJSON.FeatureCollection<GeoJSON.Point>>(
    vacio ? null : "/ccpp/geojson/",
    filtros
  );
  // Capas de contexto del catálogo del admin: solo las que tienen tiles listos. Reemplazar una
  // capa o cambiarle el color es editarla ahí, sin desplegar (requisito 1 del TDR).
  const capas = useApi<CapaMapa[]>("/mapas/capas/");

  const cifras = resumen.status === "ok" ? resumen.data : null;

  const puntosMapa = useMemo<GeoJSON.FeatureCollection<GeoJSON.Point>>(
    () =>
      puntos.status === "ok" ? puntos.data : { type: "FeatureCollection", features: [] },
    [puntos.status, puntos.status === "ok" ? puntos.data : null]
  );

  const verRelacion = (slug: string) => {
    setTipos([slug]);
    tablaRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  // --- Descargas -----------------------------------------------------------------------------
  const mapaRef = useRef<MapaPeligrosHandle>(null);

  /**
   * La ayuda memoria la genera el **servidor** (spec 02): el mapa se renderiza allí con un
   * navegador headless, así que el documento es reproducible a partir de sus parámetros y se
   * puede pedir desde el admin o por lotes, sin depender de que alguien tenga el visor abierto.
   */
  const urlAyudaMemoria = ubigeoDistrito
    ? urlApi(`/distritos/${ubigeoDistrito}/ayuda-memoria.pdf`, {
        peligros: filtros.peligros,
        niveles: filtros.niveles,
      })
    : "";
  const urlExport = urlApi("/ccpp/export.xlsx", { ...filtros, clasificados: 1 });

  return (
    <>
      <PageHeader
        titulo="Exposición a peligros naturales"
        descripcion="Mapa de exposición a peligros climáticos y geodinámicos en los centros poblados de Cusco. Datos provenientes de SIGRID-CENEPRED. Activa o desactiva las capas geográficas (lagunas, ríos, glaciares) desde el control superior derecho del mapa."
        badge={
          <div className="flex flex-wrap gap-2">
            {urlAyudaMemoria ? (
              <a
                href={urlAyudaMemoria}
                // La métrica lleva el ubigeo: es la que dice a PREDES qué distritos se están
                // llevando a mesas técnicas (spec 06).
                onClick={() => registrarAyudaMemoria(ubigeoDistrito)}
                title={`Ayuda memoria del distrito de ${distrito} con los filtros actuales`}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white text-mountain-900 text-sm font-medium transition hover:bg-mountain-100 no-underline"
              >
                <FileText className="w-4 h-4" />
                Ayuda memoria (PDF)
              </a>
            ) : (
              <span
                title="Selecciona un distrito para generar la ayuda memoria"
                className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/25 text-white/70 text-sm font-medium cursor-not-allowed"
              >
                <FileText className="w-4 h-4" />
                Ayuda memoria (PDF)
              </span>
            )}
            <a
              href={urlExport}
              onClick={() => registrarExport("/peligros", ubigeoDistrito || provincia || "region")}
              title="Descarga los centros poblados clasificados con los filtros actuales"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/15 text-white text-sm font-medium border border-white/25 transition hover:bg-white/25 no-underline"
            >
              <Download className="w-4 h-4" />
              Excel
            </a>
          </div>
        }
      />

      <div className="container-page py-8 no-imprimir">
        <div className="grid lg:grid-cols-[280px_1fr] gap-6">
          {/* Filtros: ubicación, tipo, nivel. Y nada más — los resultados viven al lado. */}
          <aside className="card p-5 h-fit lg:sticky lg:top-20">
            <div className="flex items-center justify-between gap-2 mb-4">
              <span className="flex items-center gap-2">
                <Filter className="w-4 h-4 text-mountain-700" />
                <span className="font-display font-semibold text-mountain-900">Filtros</span>
              </span>
              {/* Recarga la página en vez de reponer el estado a mano. Aquí los filtros viven
                  en `useState` y no en la URL, así que recargar **es** el reset completo:
                  ubicación, peligros, niveles y el encuadre del mapa. Reponerlos uno a uno
                  sería la misma lista escrita dos veces, y la segunda copia se olvidaría el
                  día que se añada un filtro. */}
              <button
                type="button"
                onClick={() => window.location.reload()}
                title="Vuelve a todas las provincias, todos los peligros y todos los niveles"
                className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded border border-ink-300/40 text-ink-600 hover:bg-mountain-100"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Reiniciar
              </button>
            </div>

            <div className="space-y-5">
              <div>
                <label className="block text-xs font-medium text-ink-600 mb-1">Ubicación</label>
                <GeoSelector
                  provincias={provincias.status === "ok" ? provincias.data : []}
                  distritos={distritos.status === "ok" ? distritos.data : []}
                  provincia={provincia}
                  distrito={distrito}
                  onChange={(p, d) => {
                    setProvincia(p);
                    setDistrito(d);
                  }}
                />
              </div>

              <ChecklistFiltro
                titulo="Tipo de peligro"
                seleccion={seleccionTipos}
                onChange={setTipos}
                opciones={peligros.map((p) => {
                  const Icono = iconoDe(p.icono);
                  return {
                    valor: p.slug,
                    etiqueta: p.nombre,
                    adorno: (
                      <Icono className="w-4 h-4 shrink-0 text-mountain-700" aria-hidden />
                    ),
                  };
                })}
              />

              <ChecklistFiltro
                titulo="Nivel de peligro"
                seleccion={niveles.map(String)}
                onChange={(valores) => setNiveles(valores.map(Number) as Nivel[])}
                opciones={NIVELES.map((n) => ({
                  valor: String(n),
                  etiqueta: NIVEL_LABEL[n],
                  adorno: (
                    <span
                      className="w-3 h-3 rounded-sm shrink-0"
                      style={{ backgroundColor: NIVEL_COLOR[n] }}
                      aria-hidden
                    />
                  ),
                }))}
              />
            </div>
          </aside>

          <section>
            {vacio ? (
              <EmptyState
                title="Sin filtros que aplicar"
                message="No hay ningún tipo de peligro o ningún nivel marcado. Marca al menos uno para ver los centros poblados expuestos."
              />
            ) : (
              <>
                <ResultadosExposicion
                  cifras={cifras}
                  tipos={peligros}
                  totalClasificados={tabla.total}
                  cargando={resumen.status === "loading"}
                  onVerRelacion={verRelacion}
                />

                <div className="mb-2">
                  <span className="text-xs text-ink-600">
                    Capas geográficas activables: lagunas, ríos y glaciares.
                  </span>
                </div>
                <div className="card p-1 h-[600px] overflow-hidden">
                  {puntos.status === "loading" ? (
                    <div className="h-full grid place-items-center text-ink-600">
                      Cargando mapa…
                    </div>
                  ) : puntos.status === "ok" ? (
                    <Suspense
                      fallback={
                        <div className="h-full grid place-items-center text-ink-600">
                          Cargando mapa…
                        </div>
                      }
                    >
                      <MapaPeligros
                        ref={mapaRef}
                        capas={capas.status === "ok" ? capas.data : []}
                        puntos={puntosMapa}
                        tipos={peligros}
                        ambitoAcotado={Boolean(provincia || distrito)}
                      />
                    </Suspense>
                  ) : (
                    <EmptyState
                      title="No se pudo cargar el mapa"
                      message={puntos.error?.message}
                    />
                  )}
                </div>

                {/* Relación de centros poblados */}
                <div ref={tablaRef} className="card mt-4 p-5 scroll-mt-24">
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
                    <h2 className="font-display font-semibold text-mountain-900">
                      Centros poblados con clasificación de peligro
                    </h2>
                    <span className="text-sm text-ink-600">
                      {formatNumber(tabla.total)} CCPP
                    </span>
                  </div>

                  {/* Leyenda del color. La tabla ya no tiene columna «Nivel» —el nivel viaja
                      en el color de cada ícono—, así que sin esto el código de color solo se
                      podría descifrar buscándolo en la leyenda del mapa. */}
                  <p className="flex flex-wrap items-center gap-x-3 gap-y-1 mb-3 text-xs text-ink-600">
                    <span>Color del ícono = nivel:</span>
                    {NIVELES.map((n) => (
                      <span key={n} className="inline-flex items-center gap-1">
                        <span
                          className="w-2.5 h-2.5 rounded-full"
                          style={{ backgroundColor: NIVEL_COLOR[n] }}
                          aria-hidden
                        />
                        {NIVEL_LABEL[n]}
                      </span>
                    ))}
                  </p>
                  {tabla.resultados.length === 0 ? (
                    <EmptyState
                      title="Sin clasificaciones registradas"
                      message="Ningún centro poblado del ámbito tiene clasificación de peligro para los filtros aplicados. La ausencia de dato no equivale a ausencia de riesgo."
                    />
                  ) : (
                    <>
                      <div className="-mx-2 overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead className="text-xs text-ink-600 uppercase tracking-wide">
                            <tr>
                              <th className="text-left px-2 py-2">Distrito</th>
                              <th className="text-left px-2 py-2">Centro poblado</th>
                              <th className="text-left px-2 py-2">Peligros</th>
                            </tr>
                          </thead>
                          <tbody>
                            {tabla.resultados.map((c) => (
                              <tr
                                key={c.codigo}
                                className="border-t border-ink-300/20 hover:bg-mountain-100/40 align-top"
                              >
                                <td className="px-2 py-2 text-ink-600 whitespace-nowrap">
                                  {c.distrito}
                                </td>
                                <td className="px-2 py-2">
                                  <Link
                                    className="text-mountain-900 hover:text-mountain-700 no-underline"
                                    to={`/peligros/${c.codigo}`}
                                  >
                                    {c.nombre}
                                  </Link>
                                  {/* La categoría cede el sitio en móvil: es el detalle menos
                                      decisivo de la fila, y el distrito ya no puede ocultarse
                                      porque encabeza la tabla. */}
                                  <div className="text-xs text-ink-600 hidden sm:block">
                                    {c.categoria}
                                  </div>
                                </td>
                                <td className="px-2 py-2">
                                  <ListaPeligrosCcpp
                                    peligros={c.peligros ?? []}
                                    tipos={peligros}
                                  />
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>

                      {/* Paginación del SERVIDOR, acumulando páginas. Se pasó de «anterior/
                          siguiente» a «cargar más» porque ahora cada página es una petición: con
                          los botones de antes, retroceder volvía a pedir lo recién visto. */}
                      <div className="flex flex-wrap items-center justify-between gap-3 mt-3 pt-3 border-t border-ink-300/30">
                        <span className="text-xs text-ink-600">
                          Mostrando {formatNumber(tabla.resultados.length)} de{" "}
                          {formatNumber(tabla.total)} centros poblados clasificados
                        </span>
                        {tabla.hayMas && (
                          <button
                            onClick={tabla.cargarMas}
                            disabled={tabla.cargando}
                            className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded border border-ink-300/40 text-ink-600 hover:bg-mountain-100 disabled:opacity-40 disabled:hover:bg-transparent"
                          >
                            {tabla.cargando ? "Cargando…" : "Ver más"}
                            <ChevronRight className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </>
                  )}
                </div>
              </>
            )}
          </section>
        </div>
      </div>
    </>
  );
}
