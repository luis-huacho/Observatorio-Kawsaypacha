/**
 * `/peligros` — el visor, que es el corazón del Observatorio.
 *
 * Todo lo que se prueba aquí es invisible para las pruebas de API: que el mapa pinte de verdad,
 * que los filtros lleguen a la pantalla, y que la ayuda memoria se descargue. Los tres fallan en
 * silencio —la página carga, el API responde 200— así que solo un navegador los detecta.
 */
import { expect, test } from "./fixtures";

import { aNumero, esperarApi, esperarMapaPintado, vigilarConsola } from "./apoyo";

import type { Page } from "@playwright/test";

/**
 * Deja marcada una sola opción de un filtro de checklist.
 *
 * Va por el atajo «Ninguno» y luego marca la que interesa: **dos interacciones en vez de nueve**.
 * Desmarcar una a una parece más natural, pero cada clic cambia el estado y dispara resumen,
 * tabla y geojson —2 MB este último—, así que dejaba treinta y tantas peticiones en vuelo y la
 * prueba se caía por timeout de forma intermitente. Con el filtro vacío la página no pide nada
 * (su estado vacío), de modo que el camino corto además no genera consultas intermedias.
 */
async function soloUna(page: Page, filtro: string, opcion: string) {
  const grupo = page.getByRole("group", { name: filtro });
  const atajo = grupo.getByRole("button");
  if ((await atajo.textContent())?.trim() === "Todos") await atajo.click(); // ya había alguna fuera
  await atajo.click(); // "Ninguno"
  await grupo.getByRole("checkbox", { name: opcion, exact: true }).check();
}

const soloPeligro = (page: Page, nombre: string) => soloUna(page, "Tipo de peligro", nombre);
const soloNivel = (page: Page, nombre: string) => soloUna(page, "Nivel de peligro", nombre);

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

  test("las cifras de los resultados salen del servidor, no de las filas cargadas", async ({
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

  test("los resultados son una grilla por tipo, y cuentan centros poblados", async ({ page }) => {
    // La grilla es lo que sustituyó al panel «Distribución», que vivía dentro del `aside` de
    // filtros y se leía como una leyenda del mapa en vez de como la respuesta a la consulta.
    await page.goto("/peligros");
    const resumen = await (await esperarApi(page, "/api/peligros/resumen/")).json();

    const bloque = page.getByRole("region", { name: "Resultados" });
    await expect(bloque).toBeVisible();
    await expect(bloque.getByRole("columnheader", { name: "Centros poblados" })).toBeVisible();

    // Dentro de una fila, «clasificaciones» y «centros poblados» son la misma cifra: la base
    // impide dos clasificaciones del mismo peligro en un mismo centro poblado.
    for (const fila of resumen.por_peligro.slice(0, 3)) {
      const suma = Object.values<number>(fila.niveles).reduce((a, b) => a + b, 0);
      expect(fila.centros_poblados).toBe(suma);
      await expect(bloque.getByRole("row", { name: new RegExp(fila.peligro) })).toBeVisible();
    }
  });

  test("/peligros ya no pide la frecuencia de emergencias", async ({ page }) => {
    // La frecuencia es el otro eje de la fuente —lo que ya ocurrió, por distrito y con otra
    // taxonomía—, y mezclarla aquí hacía que los filtros de esta pantalla no la afectaran y la
    // página pareciera mal calculada. Su endpoint sigue vivo; esta ruta no lo consume.
    const pedidas: string[] = [];
    page.on("request", (r) => {
      if (r.url().includes("/api/peligros/frecuencia/")) pedidas.push(r.url());
    });

    await page.goto("/peligros");
    await esperarApi(page, "/api/territorio/distritos/");
    await page.getByLabel("Provincia").selectOption({ index: 1 });
    await esperarApi(page, "provincia=");
    await page.getByLabel("Distrito").selectOption({ index: 1 });
    await esperarApi(page, "distrito=");

    expect(pedidas, `la página pidió la frecuencia:\n${pedidas.join("\n")}`).toEqual([]);
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

    await soloPeligro(page, "Heladas");
    await esperarApi(page, "peligros=heladas");
    await soloNivel(page, "Muy alto");
    await esperarApi(page, "niveles=4");

    await expect
      .poll(async () => aNumero(await contador.textContent()), {
        message: "el filtro no redujo el total de la tabla",
      })
      .toBeLessThan(antes);
  });

  test("los niveles son una selección, no un umbral", async ({ page }) => {
    // Con el «nivel mínimo» de antes, pedir «Muy alto y Bajo» sin lo de en medio era
    // inexpresable. Es la consulta que distingue un checklist de un deslizador.
    await page.goto("/peligros");
    await esperarApi(page, "/api/peligros/resumen/");

    await soloPeligro(page, "Sismo");
    await esperarApi(page, "peligros=sismo");
    await soloNivel(page, "Muy alto");
    await page.getByRole("checkbox", { name: "Bajo" }).check();

    // Hay que nombrar el endpoint: la tabla, el mapa y el resumen viajan con el mismo filtro,
    // así que un `includes("niveles=1,4")` a secas se queda con la primera de las tres.
    const respuesta = await esperarApi(page, /peligros\/resumen\/.*niveles=1,4/);
    const resumen = await respuesta.json();
    const sismo = resumen.por_peligro.find((p: { slug: string }) => p.slug === "sismo");
    expect(sismo.niveles["2"]).toBe(0);
    expect(sismo.niveles["3"]).toBe(0);
    expect(sismo.niveles["1"] + sismo.niveles["4"]).toBe(sismo.centros_poblados);
  });

  test("desde la grilla se llega a la relación de centros poblados", async ({ page }) => {
    await page.goto("/peligros");
    await esperarApi(page, "/api/peligros/resumen/");

    const fila = page.getByRole("row", { name: /Inundación/ });
    await fila.getByRole("button", { name: /Ver centros poblados/ }).click();
    await esperarApi(page, "peligros=inundacion");

    // El control visible tiene que reflejar lo que se ve: si el filtro se aplicara solo a la
    // tabla, el checklist mentiría sobre el recorte y el mapa mostraría otra cosa.
    await expect(page.getByRole("checkbox", { name: "Inundación" })).toBeChecked();
    await expect(page.getByRole("checkbox", { name: "Sismo" })).not.toBeChecked();
  });

  test("desmarcar todos los peligros no muestra todo, sino nada", async ({ page }) => {
    // Un checklist vacío significa «ninguno». Interpretarlo como «todos» sorprendería a quien
    // acaba de desmarcarlo: pediría nada y se le devolvería la región entera.
    await page.goto("/peligros");
    await esperarApi(page, "/api/peligros/resumen/");

    await page
      .getByRole("group", { name: "Tipo de peligro" })
      .getByRole("button", { name: "Ninguno" })
      .click();

    await expect(page.getByText(/Sin filtros que aplicar/i)).toBeVisible();
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

    await soloPeligro(page, "Heladas");
    await esperarApi(page, "peligros=heladas");
    await soloNivel(page, "Muy alto");
    await esperarApi(page, "niveles=4");

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
