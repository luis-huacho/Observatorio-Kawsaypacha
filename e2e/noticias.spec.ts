/**
 * `/noticias` — el listado editorial y su ficha.
 *
 * Lo que se protege son dos cosas que **se ven bien aunque estén mal**: el orden con el que llegan
 * las publicaciones (una pantalla mal ordenada no da ningún error) y que el cuerpo de la ficha se
 * pinte como HTML y no como el texto de sus etiquetas.
 */
import { expect, test } from "./fixtures";

import { irEsperando, vigilarConsola } from "./apoyo";

test.describe("Noticias", () => {
  test("las destacadas encabezan el listado", async ({ page }) => {
    const datos = await (await irEsperando(page, "/noticias", "/api/noticias/")).json();

    if (datos.count === 0) test.skip(true, "no hay noticias publicadas (seed sin --demo)");

    const destacadas = datos.results.filter((n: { destacada: boolean }) => n.destacada);
    if (destacadas.length === 0) test.skip(true, "ninguna noticia está marcada como destacada");

    // El API es la fuente del orden; aquí se comprueba que la grilla lo respeta y no reordena.
    const enlaces = page.locator('a[href^="/noticias/"]');
    await expect(enlaces.first()).toBeVisible();

    const primeros = datos.results
      .slice(0, destacadas.length)
      .map((n: { slug: string }) => n.slug);
    for (const [i, slug] of primeros.entries()) {
      await expect(enlaces.nth(i)).toHaveAttribute("href", `/noticias/${slug}`);
    }

    // Y dentro del bloque destacado manda la fecha, la más reciente arriba.
    const fechas = destacadas.map((n: { fecha: string }) => n.fecha);
    expect(fechas).toEqual([...fechas].sort().reverse());
  });

  test("el cuerpo de la ficha se pinta como HTML, no como texto", async ({ page }) => {
    const errores = vigilarConsola(page);

    const datos = await (await irEsperando(page, "/noticias", "/api/noticias/")).json();
    if (datos.count === 0) test.skip(true, "no hay noticias publicadas (seed sin --demo)");

    await page.locator('a[href^="/noticias/"]').first().click();

    // El fallo que cierra esta prueba: la ficha imprimía el HTML de CKEditor tal cual, así que en
    // pantalla se leían las etiquetas. Un `<p>` real dentro del contenedor demuestra lo contrario.
    const cuerpo = page.locator(".contenido-rico");
    await expect(cuerpo).toBeVisible();
    expect(await cuerpo.locator("p").count()).toBeGreaterThan(0);

    expect(await page.locator("body").innerText()).not.toContain("<p>");
    expect(errores, `errores en consola:\n${errores.join("\n")}`).toEqual([]);
  });

  test("la ilustración por defecto de cada tipo existe y carga", async ({ page }) => {
    // Es la ÚNICA red que mira el archivo de verdad. El valor crudo del tipo es el nombre del SVG
    // (`/img/default/<tipo>.svg`), y el backend no puede comprobar que exista: los SVG viven en el
    // bundle del frontend y su contenedor solo monta `./backend`.
    //
    // Se mide con `naturalWidth`, NO con el código de estado: el `try_files $uri /index.html` de la
    // SPA —y el dev server de Vite— responden **200 con HTML** a un archivo que no existe, así que
    // mirar el status daba verde siempre. Un HTML servido donde iba una imagen no decodifica, y
    // eso sí se ve.
    const datos = await (await irEsperando(page, "/noticias", "/api/noticias/")).json();
    if (datos.count === 0) test.skip(true, "no hay noticias publicadas (seed sin --demo)");

    // Las portadas se piden con carga diferida: hay que llegar al pie para que entren todas.
    await page.mouse.wheel(0, 20000);
    await page.waitForLoadState("networkidle");

    const ilustraciones = page.locator('img[src*="/img/default/"]');
    // Si no hubiera ninguna, la prueba no estaría midiendo nada.
    expect(await ilustraciones.count()).toBeGreaterThan(0);

    const rotas = await page.evaluate(() =>
      Array.from(document.querySelectorAll("img"))
        .filter((img) => img.src.includes("/img/default/"))
        .filter((img) => !img.complete || img.naturalWidth === 0)
        .map((img) => img.src),
    );

    expect(rotas, `ilustraciones que no cargan:\n${rotas.join("\n")}`).toEqual([]);
  });
});
