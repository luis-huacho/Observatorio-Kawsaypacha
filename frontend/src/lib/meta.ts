import { useEffect } from "react";

const SUFIJO = "Observatorio Kallpachakuy";

/**
 * Los títulos de norma llegan a 300 caracteres, así que se recortan por palabra. El servidor hace
 * lo mismo y con el mismo límite (`_recortar` en `apps/sitio/vistas_html.py`): si divergieran, la
 * pestaña del navegador y la previsualización al compartir dirían cosas distintas de la misma
 * ficha. Google además corta el título sobre los 60 caracteres al pintarlo.
 */
const MAXIMO = 110;

function recortar(texto: string) {
  if (texto.length <= MAXIMO) return texto;
  return texto.slice(0, MAXIMO).replace(/\s+\S*$/, "") + "…";
}

/**
 * Pone el `<title>` y la `description` de la página actual.
 *
 * **Qué arregla y qué no.** Hasta ahora *todas* las rutas compartían el mismo `<title>`, así que
 * las pestañas del navegador, el historial y los marcadores del visitante decían lo mismo en las
 * veinte páginas, y Google indexaba todas con el mismo titular.
 *
 * Lo que esto **no** arregla es la previsualización al compartir: WhatsApp, Facebook y LinkedIn no
 * ejecutan JavaScript, así que nada de lo que pase por aquí les llega. Eso lo resuelve el servidor
 * inyectando las metas en el HTML de las fichas (`apps/sitio/vistas_html.py`), y por eso este hook
 * **no toca `og:*`**: dos sitios escribiendo las mismas metas es la forma segura de que un día
 * discrepen. Aquí solo lo que sirve al navegador y a Google, que sí ejecuta JS.
 *
 * Se hace a mano y no con `react-helmet` porque son estas quince líneas contra una dependencia más
 * en el bundle.
 */
export function useMetaPagina(titulo: string | null | undefined, descripcion?: string | null) {
  useEffect(() => {
    if (!titulo) return; // aún cargando: se deja el título anterior antes que parpadear
    const previo = document.title;
    document.title = `${recortar(titulo)} | ${SUFIJO}`;

    const meta = document.querySelector('meta[name="description"]');
    const previaDescripcion = meta?.getAttribute("content") ?? null;
    if (meta && descripcion) meta.setAttribute("content", descripcion);

    return () => {
      document.title = previo;
      if (meta && previaDescripcion !== null) meta.setAttribute("content", previaDescripcion);
    };
  }, [titulo, descripcion]);
}

/**
 * Título y descripción de las rutas fijas, en un solo sitio.
 *
 * Las fichas no están aquí: su título es su contenido y lo pone cada ruta llamando al hook. Esto
 * cubre la portada y los listados, que son estáticos y hasta ahora compartían el título del sitio.
 */
export const META_RUTAS: Record<string, { titulo: string; descripcion: string }> = {
  "/": {
    titulo: "Inicio",
    descripcion:
      "Monitoreo de gestión del riesgo de desastres y adaptación al cambio climático en la región Cusco.",
  },
  "/peligros": {
    titulo: "Peligros",
    descripcion:
      "Exposición a peligros de los centros poblados de Cusco y emergencias registradas por distrito.",
  },
  "/medidas": {
    titulo: "Buenas prácticas",
    descripcion:
      "Experiencias de adaptación al cambio climático y gestión del riesgo implementadas en Cusco.",
  },
  "/inversion": {
    titulo: "Inversión",
    descripcion:
      "Presupuesto del programa 0068 de reducción de vulnerabilidad ejecutado por las municipalidades de Cusco.",
  },
  "/normativa": {
    titulo: "Normativa",
    descripcion:
      "Normativa de GRD y ACC vigente, con el análisis y las recomendaciones de PREDES.",
  },
  "/noticias": {
    titulo: "Noticias",
    descripcion: "Actualidad, artículos y opinión sobre gestión del riesgo y cambio climático en Cusco.",
  },
  "/recursos": { titulo: "Recursos", descripcion: "Biblioteca de documentos técnicos de GRD y ACC." },
  "/videos": { titulo: "Videos", descripcion: "Material audiovisual del Observatorio Kallpachakuy." },
  "/eventos": { titulo: "Eventos", descripcion: "Agenda de actividades de GRD y ACC en la región Cusco." },
  "/sobre": {
    titulo: "Sobre el observatorio",
    descripcion: "Qué es el Observatorio Kallpachakuy, quién lo hace y de dónde salen sus datos.",
  },
  "/buscar": { titulo: "Buscar", descripcion: "Busca en todo el contenido del Observatorio." },
};
