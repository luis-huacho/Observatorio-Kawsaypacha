import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, Info, X } from "lucide-react";

import { useApi } from "@/lib/api";
import { NIVEL_COLOR, NIVEL_LABEL, formatNumber } from "@/lib/semaforo";
import type { ComparadorRespuesta, Distrito, Nivel, Provincia } from "@/lib/types";
import EmptyState from "@/components/EmptyState";
import PageHeader from "@/components/PageHeader";

const MAXIMO = 4;
const NIVELES: Nivel[] = [4, 3, 2, 1];

/**
 * Tablero comparativo entre distritos (requisito 5 del TDR).
 *
 * Entre 2 y 4 distritos. El techo no es arbitrario: son tarjetas lado a lado, y a partir de cinco
 * dejan de caber en pantalla y de leerse en una reunión, que es donde se usa esto.
 *
 * Sin bloque de inversión: su unidad es la municipalidad ejecutora y no el distrito (ADR-D4), así
 * que no hay cifra que poner en una tarjeta distrital sin inventarla.
 */
export default function Comparar() {
  const [seleccion, setSeleccion] = useState<string[]>([]);
  const [provincia, setProvincia] = useState("");

  const provincias = useApi<Provincia[]>("/territorio/provincias/");
  const distritos = useApi<Distrito[]>("/territorio/distritos/");
  const listaDistritos = distritos.status === "ok" ? distritos.data : [];

  const disponibles = useMemo(
    () =>
      listaDistritos
        .filter((d) => (provincia ? d.ubigeo_provincia === provincia : true))
        .filter((d) => !seleccion.includes(d.ubigeo))
        .sort((a, b) => a.nombre.localeCompare(b.nombre, "es")),
    [listaDistritos, provincia, seleccion]
  );

  const porUbigeo = useMemo(
    () => new Map(listaDistritos.map((d) => [d.ubigeo, d])),
    [listaDistritos]
  );

  // Solo se pide con 2 o más: con uno el API responde 400, y pedirlo para recibir un error es
  // ruido en la consola y en el log del servidor.
  const comparacion = useApi<ComparadorRespuesta>(
    seleccion.length >= 2 ? "/comparador/distritos/" : null,
    { ubigeos: seleccion.join(",") }
  );

  function agregar(ubigeo: string) {
    if (!ubigeo || seleccion.length >= MAXIMO) return;
    setSeleccion((s) => [...s, ubigeo]);
  }

  const tarjetas = comparacion.status === "ok" ? comparacion.data.distritos : [];

  return (
    <>
      <PageHeader
        titulo="Comparar distritos"
        descripcion="Pon dos a cuatro distritos lado a lado: exposición a peligros, emergencias registradas y medidas documentadas. Pensado para llevar a una mesa técnica."
      />

      <div className="container-page py-8">
        {/* --- Selector --- */}
        <div className="card p-5 mb-8">
          <div className="grid sm:grid-cols-2 gap-3 max-w-2xl">
            <div>
              <label className="block text-xs font-medium text-ink-600 mb-1">Provincia</label>
              <select
                value={provincia}
                onChange={(e) => setProvincia(e.target.value)}
                className="control w-full"
              >
                <option value="">Todas</option>
                {provincias.status === "ok" &&
                  provincias.data.map((p) => (
                    <option key={p.ubigeo} value={p.ubigeo}>
                      {p.nombre}
                    </option>
                  ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-ink-600 mb-1">
                Añadir distrito {seleccion.length >= MAXIMO && `(máximo ${MAXIMO})`}
              </label>
              <select
                value=""
                onChange={(e) => agregar(e.target.value)}
                disabled={seleccion.length >= MAXIMO}
                className="control w-full"
              >
                <option value="">Elige un distrito…</option>
                {disponibles.map((d) => (
                  <option key={d.ubigeo} value={d.ubigeo}>
                    {d.nombre} ({d.provincia})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {seleccion.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-4">
              {seleccion.map((u) => (
                <span
                  key={u}
                  className="inline-flex items-center gap-1.5 chip bg-mountain-100 text-mountain-900 border border-mountain-500/20"
                >
                  {porUbigeo.get(u)?.nombre ?? u}
                  <button
                    type="button"
                    onClick={() => setSeleccion((s) => s.filter((x) => x !== u))}
                    aria-label={`Quitar ${porUbigeo.get(u)?.nombre ?? u}`}
                    className="hover:text-level-4"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>

        {seleccion.length < 2 ? (
          <EmptyState
            title="Elige al menos dos distritos"
            message="La comparación necesita dos distritos como mínimo y admite hasta cuatro."
          />
        ) : comparacion.status === "loading" ? (
          <p className="text-sm text-ink-600">Comparando…</p>
        ) : comparacion.status === "error" ? (
          <EmptyState title="No se pudo comparar" message={comparacion.error.message} />
        ) : (
          <>
            {/* La advertencia viene del propio API: los periodos de observación son por
                distrito, así que comparar totales de emergencias sin decirlo sería engañoso. */}
            <div className="mb-6 flex items-start gap-2 rounded-lg border border-sky-500/30 bg-sky-200/30 px-4 py-3 text-sm text-sky-700">
              <Info className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{comparacion.data.advertencia_periodos}</span>
            </div>

            <div
              className="grid gap-4"
              style={{
                gridTemplateColumns: `repeat(${Math.min(tarjetas.length, MAXIMO)}, minmax(0, 1fr))`,
              }}
            >
              {tarjetas.map((t) => (
                <article key={t.ubigeo} className="card p-5">
                  <h2 className="font-display text-lg font-bold text-mountain-900 leading-tight">
                    {t.distrito}
                  </h2>
                  <p className="text-xs text-ink-600">{t.provincia}</p>

                  <dl className="mt-4 space-y-2 text-sm">
                    <Dato etiqueta="Centros poblados" valor={formatNumber(t.total_ccpp)} />
                    <Dato
                      etiqueta="Con clasificación"
                      valor={formatNumber(t.total_ccpp - t.por_ccpp.sin_clasificar)}
                    />
                    <Dato etiqueta="Buenas prácticas documentadas" valor={String(t.medidas_publicadas)} />
                  </dl>

                  <h3 className="mt-5 text-xs font-semibold uppercase tracking-wide text-ink-600">
                    Centros poblados por nivel máximo
                  </h3>
                  <ul className="mt-2 space-y-1">
                    {NIVELES.map((n) => (
                      <li key={n} className="flex items-center gap-2 text-sm">
                        <span
                          className="inline-block w-2.5 h-2.5 rounded-full shrink-0"
                          style={{ backgroundColor: NIVEL_COLOR[n] }}
                        />
                        <span className="flex-1">{NIVEL_LABEL[n]}</span>
                        <span className="font-mono">
                          {formatNumber(Number(t.por_ccpp.niveles[String(n) as "1"]))}
                        </span>
                      </li>
                    ))}
                    <li className="flex items-center gap-2 text-sm text-ink-600 pt-1 border-t border-ink-300/30">
                      <span className="inline-block w-2.5 h-2.5 rounded-full bg-ink-300 shrink-0" />
                      <span className="flex-1">Sin dato</span>
                      <span className="font-mono">
                        {formatNumber(t.por_ccpp.sin_clasificar)}
                      </span>
                    </li>
                  </ul>

                  <h3 className="mt-5 text-xs font-semibold uppercase tracking-wide text-ink-600">
                    Emergencias registradas
                  </h3>
                  {t.frecuencia === null ? (
                    // Dos estados vacíos distintos: sin fila en la fuente (esto) y con fila
                    // pero cero emergencias. Colapsarlos ocultaría un vacío de información.
                    <p className="mt-2 flex items-start gap-1.5 text-sm text-earth-700">
                      <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                      La fuente no incluye una fila para este distrito.
                    </p>
                  ) : (
                    <>
                      <p className="mt-2 text-2xl font-display font-bold text-mountain-900">
                        {formatNumber(t.frecuencia.total)}
                      </p>
                      <p className="text-xs text-ink-600">
                        {t.frecuencia.rango_fecha
                          ? `Periodo ${t.frecuencia.rango_fecha}`
                          : "Periodo no declarado por la fuente"}
                        {!t.frecuencia.desglose_disponible && " · sin desglose por evento"}
                      </p>
                    </>
                  )}

                  <Link
                    to={`/peligros`}
                    className="inline-block mt-5 text-sm text-mountain-700"
                  >
                    Ver en el visor
                  </Link>
                </article>
              ))}
            </div>
          </>
        )}
      </div>
    </>
  );
}

function Dato({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <dt className="text-ink-600">{etiqueta}</dt>
      <dd className="font-mono font-medium text-mountain-900">{valor}</dd>
    </div>
  );
}
