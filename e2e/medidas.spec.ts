/**
 * `/medidas` — el catálogo de buenas prácticas, con sus filtros y su ficha.
 *
 * Es la sección donde PREDES publica su propio conocimiento, así que lo que se prueba es el camino
 * del editor visto desde fuera: que lo publicado aparezca, que los filtros recorten, y que la
 * ficha abra con su contenido y su galería.
 */
import { expect, test } from "./fixtures";

import { esperarApi, vigilarConsola } from "./apoyo";

test.describe("Medidas", () => {
  test("el listado sale del API y cada tarjeta tiene su imagen", async ({ page }) => {
    const errores = vigilarConsola(page);

    await page.goto("/medidas");
    const datos = await (await esperarApi(page, "/api/medidas/")).json();

    if (datos.count === 0) test.skip(true, "no hay medidas publicadas (seed sin --demo)");

    const tarjetas = page.locator('a[href^="/medidas/"]');
    await expect(tarjetas.first()).toBeVisible();

    // La portada llega **resuelta por el servidor**: si el registro no tiene imagen propia, el
    // API devuelve la ilustración institucional. Nunca debe quedar un hueco.
    const imagen = page.locator("img").first();
    await expect(imagen).toBeVisible();
    expect(await imagen.getAttribute("src")).toBeTruthy();

    expect(errores, `errores en consola:\n${errores.join("\n")}`).toEqual([]);
  });

  test("elegir un peligro llega al API y recorta el listado", async ({ page }) => {
    await page.goto("/medidas");
    const datos = await (await esperarApi(page, "/api/medidas/")).json();
    if (datos.count === 0) test.skip(true, "no hay medidas publicadas (seed sin --demo)");

    const selectores = page.locator("select");
    if ((await selectores.count()) === 0) test.skip(true, "la sección no tiene filtros de select");

    // El selector guarda el **slug** del peligro, que es lo que filtra el API. Cuando guardaba
    // el nombre, el filtro devolvía cero resultados siempre y parecía que no había contenido.
    await selectores.first().selectOption({ index: 1 });
    const respuesta = await esperarApi(page, /\/api\/medidas\/\?.*peligro=/);
    const filtrada = await respuesta.json();

    const enviado = new URL(respuesta.url()).searchParams.get("peligro");
    expect(enviado).toBeTruthy();
    expect(enviado).not.toContain(" ");
    expect(filtrada.count).toBeLessThanOrEqual(datos.count);
  });

  test("la ficha abre con su contenido", async ({ page }) => {
    await page.goto("/medidas");
    const datos = await (await esperarApi(page, "/api/medidas/")).json();
    if (datos.count === 0) test.skip(true, "no hay medidas publicadas (seed sin --demo)");

    const primera = page.locator('a[href^="/medidas/"]').first();
    const destino = await primera.getAttribute("href");
    await primera.click();

    await expect(page).toHaveURL(new RegExp(`${destino}$`));
    await expect(page.locator("h1")).toBeVisible();
    // El HTML del contenido va saneado en el servidor (ADR-D2) y el cliente lo inyecta tal cual.
    await expect(page.locator("script[data-inyectado]")).toHaveCount(0);
  });

  test("una medida que no existe no deja la página en blanco", async ({ page }) => {
    await page.goto("/medidas/esta-medida-no-existe");

    await expect(
      page.getByText(/no (se )?(encontr|existe)|no disponible|404/i).first(),
    ).toBeVisible();
  });

  test("los chips de palabras clave llevan al listado recortado", async ({ page }) => {
    await page.goto("/medidas");
    const datos = await (await esperarApi(page, "/api/medidas/")).json();
    if (datos.count === 0) test.skip(true, "no hay medidas publicadas (seed sin --demo)");

    const chips = page.locator('a[href*="tema="]');
    if ((await chips.count()) === 0) test.skip(true, "las medidas publicadas no tienen temas");

    await chips.first().click();
    await expect(page).toHaveURL(/tema=/);
  });
});
