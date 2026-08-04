/**
 * Contexto del cascarón del sitio: menú, textos, marca y hero (spec 06).
 *
 * `Layout` pide `/api/sitio/` **una vez** y de ahí salen Header, Footer, la portada y `/sobre`.
 * Un endpoint por pieza añadiría cuatro round-trips al primer render.
 *
 * Mientras carga —y si el API no responde— se usan los valores por defecto de abajo, que son los
 * textos del prototipo aprobado. Dos razones para tenerlos:
 *
 * 1. **Sin fallback, el sitio parpadea**: el menú aparecería vacío durante la primera petición y
 *    saltaría a su sitio al llegar la respuesta.
 * 2. **Un fallo del API no debe dejar el sitio sin navegación.** El visor y las fichas seguirían
 *    roto, pero al menos se puede navegar y entender qué es esto.
 */
import { createContext, useContext } from "react";

import { useApi } from "./api";
import type { SitioPayload } from "./types";

const POR_DEFECTO: SitioPayload = {
  config: {
    nombre_sitio: "Observatorio Kallpachakuy",
    descripcion_footer:
      "Monitoreo y seguimiento de la gestión del riesgo de desastres y la adaptación al cambio " +
      "climático en la región Cusco, Perú. Operado por PREDES.",
    email_contacto: "",
    telefono: "",
    direccion: "",
    redes: {},
    mensaje_banner: "",
    logo: null,
  },
  bloques: {},
  menu: {
    header: [
      { texto: "Exposición a peligros", url: "/peligros", grupo: "", orden: 1 },
      { texto: "Medidas", url: "/medidas", grupo: "", orden: 2 },
      { texto: "Inversión", url: "/inversion", grupo: "", orden: 3 },
      { texto: "Normativa", url: "/normativa", grupo: "", orden: 4 },
      // «Comparar distritos» no va en el menú (ADR-P2). La ruta sigue viva y se llega por URL,
      // pero tampoco se anuncia aquí: este respaldo se pinta mientras carga `/api/sitio/` y si el
      // API no responde, así que dejarla haría parpadear el enlace en cada carga.
      { texto: "Sobre", url: "/sobre", grupo: "", orden: 6 },
    ],
    footer: [
      { texto: "Exposición a peligros", url: "/peligros", grupo: "Secciones", orden: 1 },
      { texto: "Medidas", url: "/medidas", grupo: "Secciones", orden: 2 },
      { texto: "Inversión", url: "/inversion", grupo: "Secciones", orden: 3 },
      { texto: "Normativa", url: "/normativa", grupo: "Más", orden: 5 },
      { texto: "Noticias", url: "/noticias", grupo: "Más", orden: 6 },
      { texto: "Videos", url: "/videos", grupo: "Más", orden: 7 },
      { texto: "Eventos", url: "/eventos", grupo: "Más", orden: 8 },
      { texto: "Recursos", url: "/recursos", grupo: "Más", orden: 9 },
      { texto: "Sobre el observatorio", url: "/sobre", grupo: "Más", orden: 10 },
    ],
  },
  hero: [],
};

type ValorContexto = {
  sitio: SitioPayload;
  /** `true` mientras se resuelve la primera petición: la UI puede atenuar lo administrable. */
  cargando: boolean;
  /** `true` si el API no respondió y se están usando los valores por defecto. */
  degradado: boolean;
};

const SitioContext = createContext<ValorContexto>({
  sitio: POR_DEFECTO,
  cargando: true,
  degradado: false,
});

export function ProveedorSitio({ children }: { children: React.ReactNode }) {
  const estado = useApi<SitioPayload>("/sitio/");
  const valor: ValorContexto = {
    sitio: estado.status === "ok" ? estado.data : POR_DEFECTO,
    cargando: estado.status === "loading",
    degradado: estado.status === "error",
  };
  return <SitioContext.Provider value={valor}>{children}</SitioContext.Provider>;
}

export function useSitio(): ValorContexto {
  return useContext(SitioContext);
}

/**
 * Texto administrable por su clave, con respaldo.
 *
 * Devuelve el HTML del bloque o el respaldo si PREDES aún no lo ha creado. Una clave que no
 * existe **no es un error**: significa que el editor todavía no ha escrito ese texto, y el sitio
 * tiene que verse bien igualmente.
 */
export function useBloque(clave: string, respaldo = ""): string {
  const { sitio } = useSitio();
  return sitio.bloques[clave]?.cuerpo || respaldo;
}

/** Enlaces del pie agrupados por columna, preservando el orden que fijó el admin. */
export function agruparPie(enlaces: SitioPayload["menu"]["footer"]) {
  const grupos = new Map<string, SitioPayload["menu"]["footer"]>();
  for (const enlace of enlaces) {
    const clave = enlace.grupo || "Secciones";
    if (!grupos.has(clave)) grupos.set(clave, []);
    grupos.get(clave)!.push(enlace);
  }
  return [...grupos.entries()].map(([titulo, items]) => ({ titulo, items }));
}
