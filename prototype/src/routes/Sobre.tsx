import { Users, MessageSquare, Brain } from "lucide-react";

const COMPONENTES = [
  {
    icon: Users,
    titulo: "Componente de Gobernanza",
    desc: "Articula a los actores implicados en la implementación del observatorio y define funciones, acciones y resultados por componente.",
    actividades: [
      "Revisar y dar opinión técnica del contenido del observatorio",
      "Generar recomendaciones a partir de la información publicada",
      "Realizar análisis de la nueva normativa de GRD",
    ],
  },
  {
    icon: MessageSquare,
    titulo: "Comunicación y Divulgación",
    desc: "Diseña, coordina y ejecuta actividades de divulgación y comunicación del conocimiento sistematizado.",
    actividades: [
      "Diseño y mantenimiento de la página del observatorio",
      "Elaboración de productos comunicacionales",
      "Organización de espacios de co-aprendizaje",
    ],
  },
  {
    icon: Brain,
    titulo: "Gestión del Conocimiento",
    desc: "Recolecta, procesa y sistematiza la información del observatorio. Genera productos estadísticos y visualizaciones.",
    actividades: [
      "Generación de productos sobre las variables monitoreadas",
      "Actualización periódica de los datasets",
      "Redacción de ayudas memoria explicativas",
      "Apoyo en la generación de visualizaciones",
    ],
  },
];

export default function Sobre() {
  return (
    <div className="container-page py-8 max-w-4xl">
      <header className="mb-8">
        <h1 className="font-display text-3xl md:text-4xl font-bold text-mountain-900">
          Sobre el Observatorio Kawsaypacha
        </h1>
        <p className="text-lg text-ink-600 mt-3">
          Herramienta web para monitorear y dar seguimiento a la gestión del riesgo de desastres
          y la adaptación al cambio climático en la región Cusco, Perú. Operado por
          {" "}
          <a href="https://www.predes.org.pe/" target="_blank" rel="noopener noreferrer">PREDES</a>
          {" "}— Centro de Estudios y Prevención de Desastres.
        </p>
      </header>

      <section className="grid md:grid-cols-3 gap-3 mb-10">
        <Obj titulo="Visibilizar escenarios de riesgo" texto="Identificar centros poblados y comunidades expuestos a peligros climáticos y geodinámicos." />
        <Obj titulo="Difundir prácticas exitosas" texto="Documentar medidas que funcionan, lecciones aprendidas y casos de mal-adaptación." />
        <Obj titulo="Detectar cuellos de botella" texto="Visibilizar dificultades de los gobiernos locales y regionales en GRD y ACC." />
      </section>

      <h2 className="font-display text-2xl font-bold text-mountain-900 mb-4">
        Componentes operativos
      </h2>
      <div className="space-y-5">
        {COMPONENTES.map((c) => (
          <article key={c.titulo} className="card p-5">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-lg bg-mountain-100 text-mountain-700 grid place-items-center shrink-0">
                <c.icon className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-display font-bold text-mountain-900 text-lg">{c.titulo}</h3>
                <p className="text-ink-600 mt-1">{c.desc}</p>
                <ul className="mt-3 text-sm text-ink-900 list-disc list-inside space-y-1">
                  {c.actividades.map((a) => <li key={a}>{a}</li>)}
                </ul>
              </div>
            </div>
          </article>
        ))}
      </div>

      <section className="mt-10 card p-6 bg-mountain-100/60 border-mountain-500/30">
        <h2 className="font-display text-xl font-bold text-mountain-900">Comunidades piloto</h2>
        <p className="text-ink-600 mt-2">
          El observatorio responde inicialmente a las necesidades de las comunidades de
          <strong> Chahuaytiri, Sacaca y Pampallacta</strong>, en el distrito de <strong>Pisac</strong>,
          provincia de <strong>Calca</strong>, región Cusco — con datos a escala regional para todo Cusco.
        </p>
      </section>

      <section className="mt-10">
        <h2 className="font-display text-xl font-bold text-mountain-900 mb-3">Contacto</h2>
        <p className="text-ink-600">
          ¿Quieres aportar al observatorio? Escríbenos a través del sitio institucional de
          <a className="ml-1" href="https://www.predes.org.pe/" target="_blank" rel="noopener noreferrer">PREDES</a>.
        </p>
      </section>
    </div>
  );
}

function Obj({ titulo, texto }: { titulo: string; texto: string }) {
  return (
    <div className="card p-5">
      <div className="font-display font-bold text-mountain-900">{titulo}</div>
      <p className="text-sm text-ink-600 mt-1">{texto}</p>
    </div>
  );
}
