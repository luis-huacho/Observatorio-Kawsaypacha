import { useMemo, useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight, ExternalLink, MapPin } from "lucide-react";

import { useApi } from "@/lib/api";
import type { Evento } from "@/lib/types";
import EmptyState from "@/components/EmptyState";
import PageHeader from "@/components/PageHeader";

const DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];
const MODALIDAD: Record<Evento["modalidad"], string> = {
  presencial: "Presencial",
  virtual: "Virtual",
  mixta: "Mixta",
};

/**
 * Calendario público de eventos (requisito 6 del TDR).
 *
 * Vista de mes más lista, porque las dos responden preguntas distintas: la rejilla sirve para
 * «¿qué hay este mes?» y la lista para «¿qué viene ahora?». El API se pide por rango con un
 * margen a cada lado, que es lo que necesita la rejilla para pintar los días que asoman de los
 * meses vecinos.
 */
export default function Eventos() {
  const [mes, setMes] = useState(() => {
    const hoy = new Date();
    return new Date(hoy.getFullYear(), hoy.getMonth(), 1);
  });

  const { desde, hasta, celdas } = useMemo(() => calendario(mes), [mes]);
  const eventos = useApi<Evento[]>("/eventos/", { desde, hasta });
  const lista = eventos.status === "ok" ? eventos.data : [];

  const porDia = useMemo(() => {
    const mapa = new Map<string, Evento[]>();
    for (const e of lista) {
      const clave = e.inicio.slice(0, 10);
      if (!mapa.has(clave)) mapa.set(clave, []);
      mapa.get(clave)!.push(e);
    }
    return mapa;
  }, [lista]);

  const hoy = new Date().toISOString().slice(0, 10);
  const proximos = lista
    .filter((e) => e.inicio.slice(0, 10) >= hoy)
    .sort((a, b) => a.inicio.localeCompare(b.inicio));

  function mover(delta: number) {
    setMes((m) => new Date(m.getFullYear(), m.getMonth() + delta, 1));
  }

  return (
    <>
      <PageHeader
        titulo="Eventos"
        descripcion="Agenda pública del observatorio: mesas técnicas, capacitaciones, presentaciones y actividades de la red de gestión del riesgo en Cusco."
      />
      <div className="container-page py-8 grid lg:grid-cols-[1fr_320px] gap-8">
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-display text-xl font-bold text-mountain-900 capitalize">
              {mes.toLocaleDateString("es-PE", { month: "long", year: "numeric" })}
            </h2>
            <div className="flex items-center gap-1">
              <button
                onClick={() => mover(-1)}
                aria-label="Mes anterior"
                className="p-2 rounded border border-ink-300/40 text-ink-600 hover:bg-mountain-100"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                onClick={() =>
                  setMes(() => {
                    const h = new Date();
                    return new Date(h.getFullYear(), h.getMonth(), 1);
                  })
                }
                className="px-3 py-2 text-xs rounded border border-ink-300/40 text-ink-600 hover:bg-mountain-100"
              >
                Hoy
              </button>
              <button
                onClick={() => mover(1)}
                aria-label="Mes siguiente"
                className="p-2 rounded border border-ink-300/40 text-ink-600 hover:bg-mountain-100"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div className="grid grid-cols-7 gap-1 text-center text-xs text-ink-600 mb-1">
            {DIAS.map((d) => (
              <div key={d} className="py-1 font-medium">
                {d}
              </div>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-1">
            {celdas.map((celda) => {
              const clave = celda.fecha.toISOString().slice(0, 10);
              const delDia = porDia.get(clave) ?? [];
              return (
                <div
                  key={clave}
                  className={`min-h-[76px] rounded-lg border p-1.5 text-left ${
                    celda.delMes
                      ? "border-ink-300/30 bg-white"
                      : "border-transparent bg-mountain-100/30"
                  } ${clave === hoy ? "ring-2 ring-mountain-500" : ""}`}
                >
                  <div
                    className={`text-xs font-mono ${
                      celda.delMes ? "text-ink-900" : "text-ink-300"
                    }`}
                  >
                    {celda.fecha.getDate()}
                  </div>
                  {delDia.map((e) => (
                    <div
                      key={e.id}
                      title={e.titulo}
                      className="mt-1 px-1 py-0.5 rounded bg-mountain-500/15 text-mountain-900 text-[11px] leading-tight line-clamp-2"
                    >
                      {e.titulo}
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        </section>

        <aside>
          <h2 className="font-display text-lg font-bold text-mountain-900 mb-3">Próximos</h2>
          {eventos.status === "loading" ? (
            <p className="text-sm text-ink-600">Cargando…</p>
          ) : proximos.length === 0 ? (
            <EmptyState
              title="Sin eventos próximos"
              message="No hay actividades programadas en este periodo."
            />
          ) : (
            <ul className="space-y-3">
              {proximos.map((e) => (
                <li key={e.id} className="card p-4">
                  <div className="flex items-center gap-2 text-xs text-ink-600 mb-1">
                    <CalendarDays className="w-3.5 h-3.5" />
                    {new Date(e.inicio).toLocaleString("es-PE", {
                      day: "numeric",
                      month: "long",
                      hour: "2-digit",
                      minute: "2-digit",
                      hour12: false,
                    })}
                    {" h"}
                  </div>
                  <div className="font-semibold text-mountain-900 leading-tight">{e.titulo}</div>
                  <div className="flex flex-wrap items-center gap-2 mt-2 text-xs text-ink-600">
                    <span className="chip bg-sky-200/40 text-sky-700 border border-sky-500/20">
                      {MODALIDAD[e.modalidad]}
                    </span>
                    {e.lugar && (
                      <span className="inline-flex items-center gap-1">
                        <MapPin className="w-3 h-3" />
                        {e.lugar}
                      </span>
                    )}
                  </div>
                  {e.descripcion && (
                    <p className="mt-2 text-sm text-ink-600 line-clamp-3">{e.descripcion}</p>
                  )}
                  {e.url_inscripcion && (
                    <a
                      href={e.url_inscripcion}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 mt-3 text-sm text-mountain-700"
                    >
                      Inscribirse <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  )}
                </li>
              ))}
            </ul>
          )}
        </aside>
      </div>
    </>
  );
}

/**
 * Rejilla de seis semanas que empieza en lunes.
 *
 * Se devuelven siempre 42 celdas para que la altura del calendario no cambie al pasar de mes: si
 * varía, el contenido de debajo salta.
 */
function calendario(mes: Date) {
  const primero = new Date(mes.getFullYear(), mes.getMonth(), 1);
  // `getDay()` es 0 para domingo; se rota para que la semana empiece en lunes, como se lee un
  // calendario en Perú.
  const desplazamiento = (primero.getDay() + 6) % 7;
  const inicio = new Date(primero);
  inicio.setDate(primero.getDate() - desplazamiento);

  const celdas = Array.from({ length: 42 }, (_, i) => {
    const fecha = new Date(inicio);
    fecha.setDate(inicio.getDate() + i);
    return { fecha, delMes: fecha.getMonth() === mes.getMonth() };
  });

  return {
    desde: celdas[0].fecha.toISOString().slice(0, 10),
    hasta: celdas[41].fecha.toISOString().slice(0, 10),
    celdas,
  };
}
