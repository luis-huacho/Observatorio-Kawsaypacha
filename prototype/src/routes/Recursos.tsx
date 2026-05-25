import { ExternalLink } from "lucide-react";

const RECURSOS = [
  {
    categoria: "Fuentes oficiales nacionales",
    items: [
      { nombre: "SIGRID — CENEPRED", desc: "Sistema de Información para la Gestión del Riesgo de Desastres.", url: "https://sigrid.cenepred.gob.pe/" },
      { nombre: "INEI", desc: "Censos de población y centros poblados.", url: "https://www.inei.gob.pe/" },
      { nombre: "MEF — Consulta Amigable", desc: "Seguimiento del PPR 0068 y otros programas presupuestales.", url: "https://apps5.mineco.gob.pe/transparencia/Navegador/default.aspx" },
      { nombre: "SENAMHI", desc: "Servicio Nacional de Meteorología e Hidrología — datos climáticos y pronósticos.", url: "https://www.senamhi.gob.pe/" },
      { nombre: "INGEMMET", desc: "Estudios de peligros geológicos y geodinámicos.", url: "https://www.gob.pe/ingemmet" },
      { nombre: "IGP", desc: "Instituto Geofísico del Perú — sismicidad y vulcanismo.", url: "https://www.gob.pe/igp" },
      { nombre: "ANA", desc: "Autoridad Nacional del Agua — recursos hídricos.", url: "https://www.gob.pe/ana" },
      { nombre: "INAIGEM", desc: "Glaciares, ecosistemas de montaña.", url: "https://www.gob.pe/inaigem" },
    ],
  },
  {
    categoria: "Marco normativo",
    items: [
      { nombre: "Ley 29664 — SINAGERD", desc: "Sistema Nacional de Gestión del Riesgo de Desastres.", url: "https://www.gob.pe/institucion/cenepred/normas-legales/103045-29664" },
      { nombre: "Marco Sendai 2015-2030", desc: "Marco internacional para la reducción del riesgo de desastres.", url: "https://www.undrr.org/implementing-sendai-framework/what-sendai-framework" },
    ],
  },
  {
    categoria: "PREDES",
    items: [
      { nombre: "Sitio institucional PREDES", desc: "Centro de Estudios y Prevención de Desastres.", url: "https://www.predes.org.pe/" },
    ],
  },
];

export default function Recursos() {
  return (
    <div className="container-page py-8">
      <header className="mb-8">
        <h1 className="font-display text-3xl md:text-4xl font-bold text-mountain-900">
          Recursos
        </h1>
        <p className="text-ink-600 mt-2 max-w-3xl">
          Directorio de fuentes oficiales, normativa y herramientas relacionadas a la GRD y ACC.
        </p>
      </header>

      <div className="space-y-8">
        {RECURSOS.map((cat) => (
          <section key={cat.categoria}>
            <h2 className="font-display text-xl font-bold text-mountain-900 mb-3">{cat.categoria}</h2>
            <div className="grid md:grid-cols-2 gap-3">
              {cat.items.map((r) => (
                <a
                  key={r.nombre}
                  href={r.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="card p-4 hover:shadow-md transition no-underline"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="font-semibold text-mountain-900">{r.nombre}</div>
                      <p className="text-sm text-ink-600 mt-1">{r.desc}</p>
                    </div>
                    <ExternalLink className="w-4 h-4 text-mountain-700 mt-1 shrink-0" />
                  </div>
                </a>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
