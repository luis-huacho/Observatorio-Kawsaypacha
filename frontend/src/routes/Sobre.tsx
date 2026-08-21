import { Link } from "react-router-dom";
import {
  Activity, Sprout, FileText, Landmark, Building2, Users, GraduationCap,
  Handshake, Newspaper, BookOpen, UserRound, Eye, ShieldCheck, Unlock,
  Brain, Globe2, ArrowRight,
} from "lucide-react";
import PageHeader from "@/components/PageHeader";
import Reveal from "@/components/Reveal";
import { useBloque } from "@/lib/sitio";

const PROPOSITOS = [
  {
    icon: Activity,
    titulo: "Monitorear los riesgos",
    texto:
      "Seguir la evolución de los riesgos asociados a los principales peligros que afectan a la región Cusco.",
  },
  {
    icon: Sprout,
    titulo: "Visibilizar lo que funciona",
    texto:
      "Difundir medidas, experiencias y buenas prácticas que han demostrado reducir el riesgo y aportar a la adaptación al cambio climático.",
  },
  {
    icon: FileText,
    titulo: "Facilitar información oficial",
    texto:
      "Acercar la información pública sobre inversión, normativa e instrumentos de gestión vinculados a la GRD y la ACC.",
  },
];

const AUDIENCIAS = [
  { icon: Landmark, label: "Gobiernos regional, provinciales y distritales" },
  { icon: Building2, label: "Entidades públicas de GRD y cambio climático" },
  { icon: Users, label: "Comunidades campesinas y organizaciones sociales" },
  { icon: GraduationCap, label: "Academia y centros de investigación" },
  { icon: Handshake, label: "Cooperación y organizaciones de desarrollo" },
  { icon: Newspaper, label: "Periodistas y comunicadores" },
  { icon: BookOpen, label: "Estudiantes" },
  { icon: UserRound, label: "Ciudadanía interesada en su territorio" },
];

const PREGUNTAS = [
  { to: "/peligros", texto: "¿A qué peligros está expuesto mi territorio?" },
  { to: "/medidas", texto: "¿Qué medidas están funcionando para reducir esos riesgos?" },
  { to: "/inversion", texto: "¿Cuánto y cómo se invierte en gestión del riesgo?" },
  { to: "/normativa", texto: "¿Qué normas orientan la GRD y la adaptación al cambio climático?" },
];

const PRINCIPIOS = [
  { icon: Eye, titulo: "Transparencia", texto: "Información pública y fuentes oficiales." },
  { icon: ShieldCheck, titulo: "Rigor técnico", texto: "Calidad y actualización permanente de los datos." },
  { icon: Unlock, titulo: "Acceso abierto", texto: "Cualquier persona puede consultar y usar los contenidos." },
  { icon: Brain, titulo: "Gestión del conocimiento", texto: "Intercambio de aprendizajes entre instituciones y comunidades." },
  { icon: Globe2, titulo: "Interculturalidad", texto: "Valora el conocimiento ancestral y las prácticas de las comunidades andinas." },
  { icon: Handshake, titulo: "Colaboración", texto: "Articula Estado, academia, sociedad civil y cooperación." },
];

export default function Sobre() {
  const mision = useBloque(
    "sobre.mision",
    "<p>Es un espacio que integra, organiza y difunde información relevante sobre la GRD y la " +
      "ACC en Cusco. Su propósito es convertir información dispersa en conocimiento útil para la " +
      "toma de decisiones: datos confiables, mapas, indicadores, normativa, experiencias " +
      "exitosas y herramientas al alcance de autoridades, comunidades, instituciones, " +
      "investigadores y ciudadanía, para comprender mejor los riesgos del territorio y " +
      "fortalecer la resiliencia de la población.</p>"
  );

  return (
    <>
      <PageHeader
        eyebrow="GRD y ACC en la región Cusco"
        titulo="Sobre el Observatorio Kallpachakuy"
        descripcion="Plataforma pública de información, monitoreo y gestión del conocimiento sobre la Gestión del Riesgo de Desastres (GRD) y la Adaptación al Cambio Climático (ACC) en la región Cusco, impulsada por PREDES."
      />
      <div className="container-page py-8 max-w-4xl">
        {/* ¿Qué es? — texto administrable desde `BloqueTexto` (clave `sobre.mision`). El
            respaldo es el texto del prototipo aprobado, para que la página nunca salga vacía. */}
        <section>
          <h2 className="font-display text-2xl font-bold text-mountain-900 mb-3">
            ¿Qué es el observatorio?
          </h2>
          <div
            className="text-ink-600 leading-relaxed contenido-rico"
            dangerouslySetInnerHTML={{ __html: mision }}
          />
        </section>

        {/* ¿Por qué nace? */}
        <section className="mt-8 callout">
          <h2 className="font-display text-xl font-bold text-mountain-700">¿Por qué nace?</h2>
          <p className="text-ink-600 mt-2">
            Es una iniciativa de <strong>PREDES</strong> en el marco de los proyectos financiados 
            por <strong>Pan para el Mundo</strong> (Brot für die Welt) que busca fortalecer 
            la resiliencia de la región Cusco frente al cambio climático. 
            El observatorio nace para <strong>actualizar y compartir información confiable</strong> 
            sobre peligros, inversión pública, normativa y experiencias que contribuyen a reducir 
            la vulnerabilidad del territorio.
          </p>
        </section>

        {/* ¿Para qué sirve? */}
        <section className="mt-10">
          <h2 className="font-display text-2xl font-bold text-mountain-900 mb-4">
            ¿Para qué sirve?
          </h2>
          <div className="grid md:grid-cols-3 gap-4">
            {PROPOSITOS.map((p, i) => (
              <Reveal key={p.titulo} delay={i * 70}>
              <div className="card h-full p-5">
                <div className="w-11 h-11 rounded-full bg-mountain-100 text-mountain-700 grid place-items-center mb-3">
                  <p.icon className="w-5 h-5" />
                </div>
                <div className="font-display font-bold text-mountain-900">{p.titulo}</div>
                <p className="text-sm text-ink-600 mt-1">{p.texto}</p>
              </div>
              </Reveal>
            ))}
          </div>
        </section>

        {/* ¿Para quién? */}
        <section className="mt-10">
          <h2 className="font-display text-2xl font-bold text-mountain-900 mb-4">
            ¿Para quién está dirigido?
          </h2>
          <div className="grid sm:grid-cols-2 gap-3">
            {AUDIENCIAS.map((a, i) => (
              <Reveal key={a.label} delay={(i % 2) * 70}>
                <div className="flex items-center gap-3 card h-full p-4">
                  <div className="w-9 h-9 rounded-full bg-mountain-100 text-mountain-700 grid place-items-center shrink-0">
                    <a.icon className="w-4 h-4" />
                  </div>
                  <span className="text-sm text-ink-900">{a.label}</span>
                </div>
              </Reveal>
            ))}
          </div>
          <p className="text-ink-600 text-sm mt-4">
            Al ser una plataforma pública, cualquier persona puede acceder libremente a la
            información y usarla en procesos de planificación, investigación, educación e
            incidencia.
          </p>
        </section>

        {/* ¿Cómo funciona? */}
        <section className="mt-10">
          <h2 className="font-display text-2xl font-bold text-mountain-900 mb-3">
            ¿Cómo funciona?
          </h2>
          <p className="text-ink-600 leading-relaxed">
            El observatorio integra información de fuentes oficiales nacionales y regionales, y la
            complementa con los conocimientos y experiencias generados en los territorios donde
            interviene PREDES. La información se organiza en componentes temáticos que responden
            preguntas clave:
          </p>
          <div className="mt-4 grid sm:grid-cols-2 gap-3">
            {PREGUNTAS.map((q) => (
              <Link
                key={q.to}
                to={q.to}
                className="card p-4 flex items-center justify-between gap-3 hover:shadow-md transition no-underline"
              >
                <span className="text-sm font-medium text-mountain-900">{q.texto}</span>
                <ArrowRight className="w-4 h-4 text-mountain-700 shrink-0" />
              </Link>
            ))}
          </div>
          <p className="text-ink-600 text-sm mt-4">
            Además incorpora productos de comunicación, análisis, mapas interactivos y materiales
            de divulgación pensados para distintos públicos.
          </p>
        </section>

        {/* Principios */}
        <section className="mt-10">
          <h2 className="font-display text-2xl font-bold text-mountain-900 mb-4">
            Principios que lo orientan
          </h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {PRINCIPIOS.map((p, i) => (
              <Reveal key={p.titulo} delay={(i % 3) * 70}>
                <div className="card h-full p-5">
                  <div className="flex items-center gap-2 text-mountain-700">
                    <p.icon className="w-5 h-5" />
                    <span className="font-display font-bold text-mountain-900">{p.titulo}</span>
                  </div>
                  <p className="text-sm text-ink-600 mt-2">{p.texto}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}
