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
});
