/**
 * Utilidades compartidas por las especificaciones E2E.
 *
 * La más importante es `sinErroresDeConsola`: un error de JavaScript no rompe la página de forma
 * visible —React sigue pintando lo que puede— así que sin vigilar la consola se puede dar por
 * bueno un visor que perdió su capa de puntos.
 */
import { expect, type Page, type Response } from "@playwright/test";

/** Errores de consola que no indican un problema del sitio. */
const RUIDO = [
  // MapLibre avisa de esto con algunos estilos de mapa base; no afecta al render.
  /Failed to load resource.*favicon/i,
  /WebGL.*deprecated/i,
];

/**
 * Descarta el beacon de métricas: el tráfico de las pruebas **no es uso real** y no debe acabar
 * en el panel del admin. Se aplica a todas las pruebas desde `apoyo.ts`, no caso por caso.
 *
 * Fue así como salió a la luz que el límite del beacon estaba bajo: con dos proyectos en paralelo
 * desde una sola IP, el navegador empezó a registrar 429 en consola. Una oficina detrás de un NAT
 * habría hecho lo mismo.
 */
export async function sinMetricas(page: Page): Promise<void> {
  await page.route("**/api/metricas/**", (ruta) => ruta.fulfill({ status: 204, body: "" }));
}

/**
 * Falla la prueba si la página registró errores de consola o excepciones no capturadas.
 * Devuelve la lista, por si el caso quiere afinar la comprobación.
 */
export function vigilarConsola(page: Page): string[] {
  const errores: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() !== "error") return;
    const texto = msg.text();
    if (!RUIDO.some((patron) => patron.test(texto))) errores.push(texto);
  });
  page.on("pageerror", (error) => errores.push(String(error)));
  return errores;
}

/** El API responde JSON y no un HTML de error: distingue «vacío» de «roto». */
export async function esperarApi(page: Page, ruta: string | RegExp): Promise<Response> {
  // Se compara contra la URL **decodificada**: `URLSearchParams` codifica la coma de los filtros
  // de lista (`niveles=1,4` → `niveles=1%2C4`), y obligar a cada prueba a escribir `%2C` las
  // vuelve ilegibles y frágiles sin ganar nada.
  const legible = (r: Response) => {
    try {
      return decodeURIComponent(r.url());
    } catch {
      return r.url();
    }
  };
  const respuesta = await page.waitForResponse(
    (r) => (typeof ruta === "string" ? legible(r).includes(ruta) : ruta.test(legible(r))),
    { timeout: 30_000 },
  );
  expect(respuesta.status(), `${respuesta.url()} respondió ${respuesta.status()}`).toBeLessThan(400);
  return respuesta;
}

/**
 * Navega **y** espera la respuesta del API, en ese orden pero registrando la escucha antes.
 *
 * `esperarApi` después de un `page.goto()` es una carrera perdida de antemano: `goto` resuelve con
 * el evento `load`, que espera a la imagen del hero, mientras React ya montó y disparó sus
 * peticiones. Cuando se registra el escucha, las respuestas **ya pasaron** y la espera se agota a
 * los 30 s como si el sitio estuviera roto. Es lo que tenía en rojo tres pruebas de la portada, con
 * el sitio funcionando perfectamente.
 *
 * Funciona porque `page.waitForResponse()` engancha su escucha de forma síncrona: llamar a
 * `esperarApi` **sin `await`** deja la promesa pendiente con el escucha ya puesto, y solo entonces
 * se navega.
 *
 * Para las esperas que siguen a un clic o a un cambio de filtro sigue valiendo `esperarApi` a
 * secas: ahí la interacción es posterior al registro y no hay carrera.
 */
export async function irEsperando(
  page: Page,
  destino: string,
  ruta: string | RegExp,
): Promise<Response> {
  const respuesta = esperarApi(page, ruta);
  // Marca la promesa como atendida sin consumirla: si `goto` falla antes de que se llegue al
  // `return`, Node avisaría de un rechazo sin gestionar y ensuciaría la salida con un aviso que no
  // es el fallo. El rechazo sigue vivo y salta igual al esperarla abajo.
  respuesta.catch(() => {});
  await page.goto(destino);
  return respuesta;
}

/** El canvas de MapLibre existe **y ha pintado algo**: un canvas en blanco pasa cualquier `toBeVisible`. */
export async function esperarMapaPintado(page: Page): Promise<void> {
  const canvas = page.locator("canvas.maplibregl-canvas");
  await expect(canvas).toBeVisible({ timeout: 30_000 });

  await expect
    .poll(
      async () =>
        canvas.evaluate((el: HTMLCanvasElement) => {
          const gl =
            el.getContext("webgl2", { preserveDrawingBuffer: true }) ||
            el.getContext("webgl", { preserveDrawingBuffer: true });
          if (!gl) return -1;
          const ancho = Math.min(el.width, 300);
          const alto = Math.min(el.height, 300);
          const pixeles = new Uint8Array(ancho * alto * 4);
          gl.readPixels(0, 0, ancho, alto, gl.RGBA, gl.UNSIGNED_BYTE, pixeles);
          // Cuántos colores distintos hay: un canvas en blanco o de un solo color plano no es
          // un mapa dibujado.
          const colores = new Set<number>();
          for (let i = 0; i < pixeles.length; i += 4) {
            colores.add((pixeles[i] << 16) | (pixeles[i + 1] << 8) | pixeles[i + 2]);
          }
          return colores.size;
        }),
      { message: "el canvas del mapa no llegó a pintar", timeout: 40_000 },
    )
    .toBeGreaterThan(3);
}

/** Número que el sitio muestra con separador de miles, como entero. */
export function aNumero(texto: string | null): number {
  return Number((texto ?? "").replace(/[^\d]/g, ""));
}
