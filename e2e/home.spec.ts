/**
 * Portada.
 *
 * Lo que se protege: que las cifras **vengan del API** y no de un mock, y que el bloque de
 * actualidad enlace a contenido real. El prototipo leía JSON estáticos, así que una portada que
 * «se ve bien» no demuestra por sí sola que la integración funcione.
 */
import { expect, test } from "./fixtures";

import { aNumero, irEsperando, vigilarConsola } from "./apoyo";
import { abrirMenu } from "./fixtures";

test.describe("Portada", () => {
  test("las cifras salen del API y coinciden con el resumen", async ({ page }) => {
    const errores = vigilarConsola(page);

    const resumen = await (await irEsperando(page, "/", "/api/peligros/resumen/")).json();

    const tarjeta = page.getByText("Centros poblados monitoreados");
    await expect(tarjeta).toBeVisible();

    const bloque = tarjeta.locator("xpath=..");
    await expect
      .poll(async () => aNumero(await bloque.textContent()), {
        message: "la cifra de la portada no llegó a cuadrar con /api/peligros/resumen/",
      })
      .toBe(resumen.total_ccpp);

    expect(resumen.total_ccpp).toBeGreaterThan(1000);
    expect(errores, `errores en consola:\n${errores.join("\n")}`).toEqual([]);
  });

  test("la tarjeta de medidas cuenta TODO lo publicado, no solo los casos de éxito", async ({ page }) => {
    // La cifra sale de `/api/medidas/` sin filtro de resultado: tiene que cuadrar con las filas
    // que lista /medidas. Cuando pedía `resultado=exito` mostraba 4 junto a un listado de 6, y
    // nada en la pantalla explicaba la diferencia. Se espera la petición SIN filtros: la portada
    // hace una segunda a `/medidas/?destacada=true…` para el carrusel de casos, y por subcadena
    // se cogería la que llegue primero.
    const medidas = await (
      await irEsperando(page, "/", /\/medidas\/\?page_size=1$/)
    ).json();

    const tarjeta = page.getByText("Experiencias exitosas");
    await expect(tarjeta).toBeVisible();

    const bloque = tarjeta.locator("xpath=..");
    await expect
      .poll(async () => aNumero(await bloque.textContent()), {
        message: "la cifra de la portada no llegó a cuadrar con /api/medidas/",
      })
      .toBe(medidas.count);
  });

  test("no queda ninguna cifra en el marcador de carga", async ({ page }) => {
    // Las tarjetas muestran «…» mientras cargan: si una se queda así, la petición se perdió y
    // la página no lo dice de ninguna otra forma.
    await irEsperando(page, "/", "/api/peligros/resumen/");

    await expect(page.getByText("…", { exact: true })).toHaveCount(0);
  });

  test("el cascarón del sitio viene de /api/sitio/", async ({ page }) => {
    const sitio = await (await irEsperando(page, "/", "/api/sitio/")).json();

    const enlacesHeader = sitio.menu.header as Array<{ texto: string; url: string }>;
    expect(enlacesHeader.length).toBeGreaterThan(2);
    await abrirMenu(page);

    // El menú se pinta desde ahí: sin esto, ocultar una sección exigiría tocar código.
    for (const enlace of enlacesHeader.slice(0, 3)) {
      // El enlace existe dos veces (escritorio y panel móvil): se comprueba el visible.
      await expect(
        page.locator(`a[href="${enlace.url}"]:visible`).first(),
      ).toBeVisible();
    }
  });

  test("prioridades no aparece en la navegación", async ({ page }) => {
    // ADR-P1: se retira con `visible=False`, no se borra. Si el menú la mostrara, ocultar algo
    // dejaría de ser una decisión de PREDES.
    await irEsperando(page, "/", "/api/sitio/");

    await expect(page.locator('a[href="/prioridades"]')).toHaveCount(0);
  });

  test("el bloque de actualidad enlaza a contenido real", async ({ page }) => {
    await irEsperando(page, "/", "/api/noticias/");

    const enlaces = page.locator('a[href^="/noticias/"], a[href^="/normativa/"]');
    if ((await enlaces.count()) === 0) {
      test.skip(true, "la base no tiene contenido editorial publicado (seed sin --demo)");
    }

    const primero = enlaces.first();
    const destino = await primero.getAttribute("href");
    await primero.click();

    await expect(page).toHaveURL(new RegExp(`${destino}$`));
    await expect(page.locator("h1")).toBeVisible();
  });

  test("una ruta inventada muestra el 404 del sitio, no el de nginx", async ({ page }) => {
    // Comprueba el `try_files` de la SPA: sin él, cualquier ruta profunda recargada a mano da el
    // 404 de nginx y el sitio parece caído.
    const respuesta = await page.goto("/esta-ruta-no-existe");

    expect(respuesta?.status()).toBeLessThan(400);
    await expect(page.getByRole("link", { name: /Observatorio|Inicio|portada/i }).first())
      .toBeVisible();
  });
});
