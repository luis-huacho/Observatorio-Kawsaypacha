import { Link } from "react-router-dom";

import { agruparPie, useBloque, useSitio } from "@/lib/sitio";

/**
 * Pie de página, con todo su contenido administrable (spec 06).
 *
 * El menú sale de `EnlaceMenu` agrupado por columna, y los textos de `BloqueTexto`. Los
 * respaldos que van en `useBloque` son los del prototipo aprobado: si PREDES aún no ha escrito
 * un texto, el pie se ve completo igualmente.
 */
export default function Footer() {
  const { sitio } = useSitio();
  const columnas = agruparPie(sitio.menu.footer);
  const fuentes = useBloque(
    "footer.fuentes",
    "<p>Datos provenientes de SIGRID-CENEPRED, INEI, MEF (PPR 0068), SENAMHI, INGEMMET, IGP, " +
      "ANA, INAIGEM.</p>"
  );
  const creditos = useBloque(
    "footer.creditos",
    "<p>PREDES — Centro de Estudios y Prevención de Desastres</p>"
  );

  return (
    <footer className="mt-16">
      {/* Curva superior estilo predes.org.pe */}
      <svg
        className="block w-full h-10 md:h-14 -mb-px"
        viewBox="0 0 1920 64"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <path d="M0,64 L0,48 C480,-16 1440,-16 1920,48 L1920,64 Z" fill="#0B3B26" />
      </svg>
      <div className="bg-mountain-900 text-mountain-100">
        <div className="container-page py-10 grid gap-8 md:grid-cols-4">
          <div className="md:col-span-2">
            <img
              src={sitio.config.logo ?? "/logo-predes-white.svg"}
              alt="PREDES — Centro de Estudios y Prevención de Desastres"
              className="h-12 w-auto mb-4"
            />
            <div className="font-display text-lg font-bold text-white">
              {sitio.config.nombre_sitio}
            </div>
            <p className="text-sm mt-2 text-mountain-100/80 max-w-md">
              {sitio.config.descripcion_footer}
            </p>
            <div
              className="mt-3 text-xs text-mountain-100/60 [&_p]:m-0"
              dangerouslySetInnerHTML={{ __html: fuentes }}
            />
            {sitio.config.email_contacto && (
              <a
                href={`mailto:${sitio.config.email_contacto}`}
                className="inline-block mt-3 text-sm text-mountain-100 hover:text-white"
              >
                {sitio.config.email_contacto}
              </a>
            )}
          </div>

          {columnas.map((columna) => (
            <div key={columna.titulo}>
              <div className="text-xs uppercase tracking-wider text-mountain-100/60 mb-3">
                {columna.titulo}
              </div>
              <ul className="space-y-2 text-sm">
                {columna.items.map((enlace) => (
                  <li key={enlace.url}>
                    <Link
                      className="text-mountain-100 hover:text-white no-underline"
                      to={enlace.url}
                    >
                      {enlace.texto}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="border-t border-mountain-700/50">
          <div className="container-page py-4 text-xs text-mountain-100/60 flex flex-wrap gap-x-2">
            <span>© {new Date().getFullYear()}</span>
            <span className="[&_p]:m-0" dangerouslySetInnerHTML={{ __html: creditos }} />
          </div>
        </div>
      </div>
    </footer>
  );
}
