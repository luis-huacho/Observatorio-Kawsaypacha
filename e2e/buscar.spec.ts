/**
 * Buscador.
 *
 * El navegador consulta Meilisearch **directamente** con la llave search-only (ADR-A4). Aquí se
 * comprueban las dos rutas: la normal y la degradada. La segunda importa tanto como la primera —un
 * sitio que responde «no se pudo buscar» se lee como roto, no como degradado, y el buscador es la
 * puerta de entrada al contenido.
 */
import { expect, test } from "./fixtures";

import { vigilarConsola } from "./apoyo";

const CONSULTA = "cusco";

test.describe("Búsqueda", () => {
  test("una búsqueda devuelve resultados agrupados por tipo", async ({ page }) => {
    const errores = vigilarConsola(page);

    await page.goto(`/buscar?q=${CONSULTA}`);

    await expect(page.getByText(new RegExp(`Resultados para .${CONSULTA}`, "i"))).toBeVisible();
    // Al menos un grupo con resultados; los grupos vacíos no se pintan.
    await expect(page.locator("a").filter({ hasText: /.+/ }).first()).toBeVisible();
    expect(errores, `errores en consola:\n${errores.join("\n")}`).toEqual([]);
  });

  test("se puede buscar desde la caja y la URL guarda la consulta", async ({ page }) => {
    // La URL con `?q=` es lo que permite compartir una búsqueda, que es cómo se pasa un hallazgo
    // entre dos personas de PREDES.
    await page.goto("/buscar");

    // Por su rótulo accesible y no por el placeholder: el buscador de la cabecera comparte
    // placeholder y en móvil está oculto, así que el localizador daba dos coincidencias.
    const caja = page.getByLabel("Términos de búsqueda");
    await caja.fill("heladas");
    await caja.press("Enter");

    await expect(page).toHaveURL(/q=heladas/);
  });

  test("una consulta sin resultados lo dice y ofrece a dónde ir", async ({ page }) => {
    await page.goto("/buscar?q=zzzqwertyxyz");

    await expect(page.getByText(/sin coincidencias/i).first()).toBeVisible();
    // Un vacío sin salida deja al visitante en un callejón: el estado vacío propone el visor.
    await expect(page.getByRole("link", { name: /visor/i }).first()).toBeVisible();
  });

  test("cuando Meilisearch está disponible, se usa Meilisearch", async ({ page }) => {
    // La prueba que faltaba. El proxy `/search/` llevaba **todas** las peticiones a la raíz de
    // Meilisearch —una variable en `proxy_pass` desactiva la sustitución del prefijo—, así que el
    // buscador caía al fallback de DRF en cada búsqueda: sin facetas, sin tolerancia a errores de
    // tecleo y sin un solo error a la vista, porque el fallback funciona.
    // Se observa qué hace la página en vez de preguntar antes por el estado del servicio: la URL
    // del API depende del entorno (en desarrollo vive en otro puerto), así que consultarla desde
    // la prueba obligaría a duplicar aquí la configuración del frontend.
    //
    // Y se miran los **status**, no solo que la petición se haya hecho. En su primera versión esta
    // prueba comprobaba que se llamara a `multi-search` y pasaba con la llave caducada: la llamada
    // se hacía, Meilisearch devolvía 403 y el sitio se iba al fallback igualmente. Una prueba que
    // comprueba la intención en vez del resultado es el mismo error que dar por bueno el buscador
    // porque `GET /search/health` respondía 200.
    const multiSearch: number[] = [];
    const otrasDeMeili: string[] = [];
    const fallback: string[] = [];
    page.on("response", (r) => {
      if (r.url().includes("multi-search")) multiSearch.push(r.status());
      else if (r.url().includes("/search/") || /:7700\//.test(r.url()))
        otrasDeMeili.push(`${r.status()} ${r.url()}`);
      else if (r.url().includes("/api/buscar/")) fallback.push(r.url());
    });

    await page.goto(`/buscar?q=${CONSULTA}`);
    await expect(page.getByText(new RegExp(`Resultados para .${CONSULTA}`, "i"))).toBeVisible();
    await expect.poll(() => multiSearch.length + fallback.length).toBeGreaterThan(0);

    if (!multiSearch.length && !otrasDeMeili.length) {
      test.skip(true, "Meilisearch no está configurado en este entorno: se usó el fallback de DRF");
    }

    expect(
      multiSearch,
      `se habló con Meilisearch pero no por multi-search:\n${otrasDeMeili.join("\n")}`,
    ).not.toEqual([]);
    expect(
      multiSearch.filter((s) => s === 200),
      "multi-search respondió, pero no con 200. Un 401/403 significa que la llave con la que se " +
        `construyó el bundle ya no existe en Meilisearch. Status: ${multiSearch.join(", ")}`,
    ).not.toEqual([]);
    // La confirmación desde la pantalla: el aviso solo se pinta con `motor === "drf"`.
    await expect(page.getByText(/modo básico/i)).toHaveCount(0);
  });

  test("con Meilisearch inalcanzable el fallback de DRF responde igual", async ({ page }) => {
    // Se corta el tráfico al buscador desde el navegador: es exactamente lo que pasa cuando el
    // servicio está caído o reindexándose.
    await page.route("**/search/**", (ruta) => ruta.abort());
    await page.route("**:7700/**", (ruta) => ruta.abort());

    const respuestas: string[] = [];
    page.on("response", (r) => {
      if (r.url().includes("/api/buscar/")) respuestas.push(r.url());
    });

    await page.goto(`/buscar?q=${CONSULTA}`);

    await expect
      .poll(() => respuestas.length, { message: "no se llamó al fallback /api/buscar/" })
      .toBeGreaterThan(0);
    await expect(page.getByText(new RegExp(`Resultados para .${CONSULTA}`, "i"))).toBeVisible();
    // Y sigue habiendo contenido: el fallback devuelve la misma forma, sin facetas.
    await expect(page.locator("main a").first()).toBeVisible();
  });

  test("la «X» vacía la caja sin cancelar la búsqueda", async ({ page }) => {
    // Es la decisión de producto: se borra **para escribir otra cosa**, así que los resultados
    // anteriores siguen en pantalla hasta que se envíe la nueva búsqueda. Sin esta prueba,
    // «mejorar» el botón limpiando también la URL parece un arreglo y es un cambio de conducta.
    const busquedas: string[] = [];
    page.on("request", (r) => {
      if (/multi-search|\/api\/buscar\//.test(r.url())) busquedas.push(r.url());
    });

    await page.goto(`/buscar?q=${CONSULTA}`);
    const caja = page.getByLabel("Términos de búsqueda");
    await expect(caja).toHaveValue(CONSULTA);
    const resultados = page.locator("main section h2");
    await expect(resultados.first()).toBeVisible();
    const cuantos = await resultados.count();

    const limpiar = page.getByRole("button", { name: "Limpiar búsqueda" });
    await expect(limpiar).toBeVisible();
    const antes = busquedas.length;
    const url = page.url();
    await limpiar.click();

    await expect(caja).toHaveValue("");
    // El foco vuelve al campo: sin eso hay que hacer clic otra vez para escribir, que es el trabajo
    // manual que el botón venía a quitar.
    await expect(caja).toBeFocused();
    await expect(limpiar).toHaveCount(0);
    // Y lo que no debe pasar: ni relanzar la búsqueda (el botón está dentro de un `<form>`, y sin
    // `type="button"` lo enviaría) ni perder los resultados.
    expect(page.url(), "la «X» no debe tocar la URL").toBe(url);
    expect(busquedas.length, "la «X» no debe relanzar la búsqueda").toBe(antes);
    await expect(resultados).toHaveCount(cuantos);
  });

  test("el buscador de lugares del visor lleva a un centro poblado y se puede vaciar", async ({
    page,
  }) => {
    await page.goto("/peligros");

    // El control lo añade MapLibre cuando el mapa está listo, así que hay que **esperarlo**: la
    // primera versión de esta prueba miraba el DOM antes de eso y se saltaba siempre, de modo que
    // el buscador de lugares no estaba cubierto por nadie.
    const buscador = page.getByPlaceholder("Buscar centro poblado…");
    const aparecio = await buscador
      .waitFor({ state: "visible", timeout: 30_000 })
      .then(() => true)
      .catch(() => false);
    if (!aparecio) {
      test.skip(true, "el control de búsqueda del mapa no llegó a montarse en este entorno");
    }

    await buscador.fill("Písac");
    const sugerencias = page.locator(".maplibregl-ctrl li");
    await expect(sugerencias.first()).toBeVisible();

    // La «X» del control: vacía la caja y las sugerencias. El marcador del mapa **no** se toca.
    const limpiar = page.locator('.maplibregl-ctrl button[aria-label="Limpiar búsqueda"]');
    await expect(limpiar).toBeVisible();
    await limpiar.click();
    await expect(buscador).toHaveValue("");
    await expect(sugerencias).toHaveCount(0);
    await expect(limpiar).toBeHidden();
  });
});
