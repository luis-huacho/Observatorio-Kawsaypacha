/**
 * El menú superior.
 *
 * Dos cosas que solo un navegador puede afirmar:
 *
 * 1. Que «Comparar distritos» ya no se ofrece en la navegación (ADR-P2). El enlace vive en tres
 *    sitios —la semilla del backend, la base ya sembrada y el menú de respaldo del frontend—, así
 *    que se puede quitar de uno y seguir apareciendo.
 * 2. Que en escritorio el menú **cabe en una línea**. Es una medida en píxeles: la barra tiene
 *    altura fija, de modo que un enlace partido en dos líneas se sale por arriba y por abajo sin
 *    que falle nada más.
 *
 * Ojo con cómo se mide lo segundo: `elemento.getClientRects().length` **no sirve**. Los enlaces del
 * menú son bloques, así que devuelven un solo rectángulo aunque su texto se parta en dos líneas —se
 * comprobó con la geometría anterior al cambio: el enlace medía 56 px de alto y seguía informando
 * de un rectángulo—. Lo que cuenta las líneas de verdad es un `Range` sobre el contenido del
 * elemento: devuelve un rectángulo por caja de línea.
 */
import { expect, test } from "./fixtures";

import { esperarApi } from "./apoyo";
import { abrirMenu } from "./fixtures";

test.describe("Menú superior", () => {
  test("comparar distritos no se ofrece en la navegación", async ({ page }) => {
    await page.goto("/");
    await esperarApi(page, "/api/sitio/");
    // En móvil los enlaces viven detrás del botón de hamburguesa: sin abrirlo, la comprobación
    // pasaría por estar el panel cerrado y no por la decisión que se quiere fijar.
    await abrirMenu(page);

    await expect(page.locator('a[href="/comparar"]')).toHaveCount(0);
    // Y el resto del menú sigue ahí: si el respaldo o la semilla se quedaran vacíos, la prueba de
    // arriba pasaría igual.
    await expect(page.locator('a[href="/peligros"]:visible').first()).toBeVisible();
  });

  test("la caja de búsqueda de la cabecera se vacía con la «X»", async ({ page }) => {
    await page.goto("/");
    // En móvil la caja vive dentro del panel de la hamburguesa.
    await abrirMenu(page);

    const caja = page.locator('header input[aria-label="Buscar"]:visible').first();
    const limpiar = page.locator('header button[aria-label="Limpiar búsqueda"]:visible');

    // Con la caja vacía no hay nada que limpiar y el botón no se pinta.
    await expect(limpiar).toHaveCount(0);

    await caja.fill("heladas");
    await expect(limpiar).toHaveCount(1);
    await limpiar.click();

    await expect(caja).toHaveValue("");
    await expect(caja).toBeFocused();
    // La caja de la cabecera envía la búsqueda con Enter: la «X» no puede navegar a /buscar.
    await expect(page).toHaveURL(/\/$/);
  });

  test("el menú de escritorio cabe en una línea", async ({ page, isMobile }) => {
    test.skip(!!isMobile, "en móvil el menú es un panel vertical, por diseño");

    await page.goto("/");
    await esperarApi(page, "/api/sitio/");
    const menu = page.getByRole("navigation", { name: "Principal" });
    const enlaces = menu.locator("a");
    await expect(enlaces.first()).toBeVisible();

    // 1024 es donde aparece el menú (`lg`) y el caso más apretado; 1280 es el viewport del
    // proyecto «escritorio»; 1440 es una pantalla holgada.
    for (const ancho of [1024, 1280, 1440]) {
      await page.setViewportSize({ width: ancho, height: 800 });

      const medidas = await enlaces.evaluateAll((elementos) =>
        elementos.map((el) => {
          const rango = document.createRange();
          rango.selectNodeContents(el);
          return {
            texto: el.textContent?.trim() ?? "",
            lineas: rango.getClientRects().length,
            top: Math.round(el.getBoundingClientRect().top),
          };
        }),
      );

      expect(medidas.length, `a ${ancho}px no se pintó ningún enlace`).toBeGreaterThan(3);
      const partidos = medidas.filter((m) => m.lineas !== 1).map((m) => m.texto);
      expect(partidos, `enlaces partidos en varias líneas a ${ancho}px`).toEqual([]);
      const tops = [...new Set(medidas.map((m) => m.top))];
      expect(tops, `el menú ocupa más de una fila a ${ancho}px`).toHaveLength(1);

      // Un menú que no envuelve pero desborda la ventana no está arreglado, solo escondido.
      const desborde = await page.evaluate(
        () => document.documentElement.scrollWidth - window.innerWidth,
      );
      expect(desborde, `la página desborda a lo ancho a ${ancho}px`).toBeLessThanOrEqual(1);
    }
  });
});
