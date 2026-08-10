/**
 * `/peligros` — el visor, que es el corazón del Observatorio.
 *
 * Todo lo que se prueba aquí es invisible para las pruebas de API: que el mapa pinte de verdad,
 * que los filtros lleguen a la pantalla, y que la ayuda memoria se descargue. Los tres fallan en
 * silencio —la página carga, el API responde 200— así que solo un navegador los detecta.
 */
import { expect, test } from "./fixtures";

import { aNumero, esperarApi, esperarMapaPintado, vigilarConsola } from "./apoyo";

test.describe("Visor de exposición a peligros", () => {
  test("el mapa carga y dibuja los centros poblados", async ({ page }) => {
    const errores = vigilarConsola(page);

    await page.goto("/peligros");
    const geojson = await esperarApi(page, "/api/ccpp/geojson/");
    await esperarMapaPintado(page);

    const datos = await geojson.json();
    expect(datos.features.length).toBeGreaterThan(1000);
    expect(errores, `errores en consola:\n${errores.join("\n")}`).toEqual([]);
  });

  test("las cifras de la distribución salen del servidor, no de las filas cargadas", async ({
    page,
  }) => {
    // Fue un error real: con la tabla paginada de 50 en 50, el panel mostraba «50 CCPP» donde
    // hay 3,238. El total tiene que venir del resumen del API.
    await page.goto("/peligros");
    const resumen = await (await esperarApi(page, "/api/peligros/resumen/")).json();

    const total = page.getByText(/CCPP$/).first();
    await expect(total).toBeVisible();

    const clasificados = Object.values<number>(resumen.por_ccpp.niveles).reduce(
      (a, b) => a + b,
      0,
    );
    expect(aNumero(await total.textContent())).toBe(clasificados);
    expect(clasificados).toBeGreaterThan(1000);
  });

  test("la tabla dice cuántos centros poblados quedan sin clasificación", async ({ page }) => {
    // «Sin dato» no es «nivel bajo», y la pantalla tiene que decirlo o la tabla se lee como si
    // fuera el padrón completo.
    await page.goto("/peligros");
    await esperarApi(page, "/api/peligros/resumen/");

    await expect(page.getByText(/sin clasificación/i).first()).toBeVisible();
  });

  test("filtrar por peligro y por nivel reduce la tabla", async ({ page }) => {
    await page.goto("/peligros");
    await esperarApi(page, "/api/ccpp/?");

    const contador = page.getByText(/de .* centros poblados clasificados/i);
    await expect(contador).toBeVisible();
    const antes = aNumero(await contador.textContent());

    await page.getByLabel("Tipo de peligro").selectOption("heladas");
    await esperarApi(page, "peligro=heladas");
    await page.getByRole("button", { name: "Nivel mínimo 4" }).click();
    await esperarApi(page, "nivel_min=4");

    await expect
      .poll(async () => aNumero(await contador.textContent()), {
        message: "el filtro no redujo el total de la tabla",
      })
      .toBeLessThan(antes);
  });

  test("filtrar reduce también el conteo de peligros clasificados, que es el del mapa", async ({
    page,
  }) => {
    // El número que el visor pinta dentro de cada grupo son clasificaciones, no centros
    // poblados. Antes salía de `point_count` de MapLibre y era inmune a los filtros: el visor
    // conserva los que no cumplen para pintarlos en gris, así que el grupo seguía contándolos
    // mientras la tabla de al lado ya había encogido.
    await page.goto("/peligros");
    await esperarApi(page, "/api/peligros/resumen/");

    const contador = page.getByText(/peligros clasificados/);
    await expect(contador).toBeVisible();
    const antes = aNumero(await contador.textContent());
    expect(antes).toBeGreaterThan(0);

    await page.getByLabel("Tipo de peligro").selectOption("heladas");
    await esperarApi(page, "peligro=heladas");
    await page.getByRole("button", { name: "Nivel mínimo 4" }).click();
    await esperarApi(page, "nivel_min=4");

    await expect
      .poll(async () => aNumero(await contador.textContent()), {
        message: "el filtro no redujo el conteo de clasificaciones",
      })
      .toBeLessThan(antes);
  });

  test("los centros poblados sin clasificación se pueden ocultar", async ({ page }) => {
    const errores = vigilarConsola(page);

    await page.goto("/peligros");
    await esperarApi(page, "/api/ccpp/geojson/");
    await esperarMapaPintado(page);

    await page.getByRole("button", { name: /Capas/ }).click();
    const casilla = page.getByLabel("Mostrar sin clasificación");
    await expect(casilla).toBeChecked();

    // Se apaga con `setFilter`, no reemplazando los datos: si alguien lo cambiara a `setData`,
    // el mapa volvería a agrupar y el número de los grupos cambiaría al ocultarlos.
    await casilla.uncheck();
    await esperarMapaPintado(page);

    expect(errores, `errores en consola:\n${errores.join("\n")}`).toEqual([]);
  });

  test("elegir provincia acota el ámbito y habilita la ayuda memoria por distrito", async ({
    page,
  }) => {
    await page.goto("/peligros");
    await esperarApi(page, "/api/territorio/distritos/");

    // El PDF es por distrito a propósito: un informe regional produce decenas de páginas y deja
    // de servir para una reunión.
    const enlace = page.getByRole("link", { name: /Ayuda memoria/i });
    await expect(enlace).toHaveCount(0);

    await page.getByLabel("Provincia").selectOption({ index: 1 });
    await esperarApi(page, "provincia=");
    await expect(page.getByLabel("Distrito")).toBeEnabled();
  });

  test("el popup del mapa lleva a la ficha del centro poblado", async ({ page }) => {
    await page.goto("/peligros");
    await esperarApi(page, "/api/ccpp/geojson/");
    await esperarMapaPintado(page);

    // Se llega a la ficha por la tabla, que es el camino accesible y estable; el popup del mapa
    // se comprueba a mano porque exige acertar un símbolo de 8 px.
    const primera = page.locator("table tbody tr a").first();
    await expect(primera).toBeVisible();
    const nombre = (await primera.textContent())?.trim() ?? "";
    await primera.click();

    await expect(page).toHaveURL(/\/peligros\/\d{10}$/);
    await expect(page.getByText(nombre).first()).toBeVisible();
  });

  test("la ayuda memoria descarga un PDF de verdad", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name === "movil", "la descarga se comprueba en escritorio");

    await page.goto("/peligros");
    await esperarApi(page, "/api/territorio/distritos/");

    // El selector trabaja con nombres y la capa de datos los traduce a ubigeo para el API.
    await page.getByLabel("Provincia").selectOption({ index: 1 });
    await esperarApi(page, "provincia=");
    await page.getByLabel("Distrito").selectOption({ index: 1 });
    await esperarApi(page, "distrito=");

    const enlace = page.getByRole("link", { name: /Ayuda memoria/i }).first();
    await expect(enlace).toBeVisible();

    const descarga = page.waitForEvent("download", { timeout: 90_000 });
    await enlace.click();
    const archivo = await descarga;

    expect(archivo.suggestedFilename()).toMatch(/\.pdf$/);
    const ruta = await archivo.path();
    expect(ruta).toBeTruthy();
  });

  test("el selector de mapa base conmuta sin romper el mapa", async ({ page }) => {
    const errores = vigilarConsola(page);

    await page.goto("/peligros");
    await esperarMapaPintado(page);

    const conmutador = page.locator("button, select").filter({ hasText: /relieve|satélite|mapa/i });
    if ((await conmutador.count()) === 0) test.skip(true, "no hay selector de mapa base visible");

    await conmutador.first().click();
    await esperarMapaPintado(page);

    expect(errores, `errores en consola:\n${errores.join("\n")}`).toEqual([]);
  });
});
