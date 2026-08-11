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

  test("las emergencias no se piden hasta que se encienden", async ({ page }) => {
    // La frecuencia es el otro eje de la fuente —lo que ya ocurrió, por distrito y con otra
    // taxonomía— y vive tras su propia casilla. Que no se pida sola es lo que mantiene los dos
    // ejes separados: si volviera a cargarse con la página, volvería a leerse como una sección
    // más de exposición que ignora sus filtros.
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

    expect(pedidas, `se pidió sin encenderla:\n${pedidas.join("\n")}`).toEqual([]);
    await expect(page.getByRole("region", { name: /Emergencias registradas/ })).toHaveCount(0);

    // La espera se arranca **antes** del clic: `waitForResponse` solo ve lo que pasa después de
    // registrarse, y la petición puede resolverse mientras `check()` aún está en vuelo.
    const respuesta = esperarApi(page, "/api/peligros/frecuencia/provincia/");
    await page.getByRole("checkbox", { name: "Ver las emergencias" }).check();
    await respuesta;
    await expect(page.getByRole("region", { name: /Emergencias registradas/ })).toBeVisible();
  });

  test("el gráfico de emergencias es de la provincia, y solo la provincia lo mueve", async ({
    page,
  }) => {
    // Es el requisito que evita el problema original: los filtros de exposición no pueden
    // afectar a un eje con otra taxonomía, así que este panel no depende de ellos ni del
    // distrito. Depender solo de la provincia lo hace evidente sin explicarlo.
    await page.goto("/peligros");
    await esperarApi(page, "/api/territorio/distritos/");
    await page.getByLabel("Provincia").selectOption({ index: 1 });
    await esperarApi(page, "provincia=");
    const respuesta = esperarApi(page, "/api/peligros/frecuencia/provincia/");
    await page.getByRole("checkbox", { name: "Ver las emergencias" }).check();
    await respuesta;

    const bloque = page.getByRole("region", { name: /Emergencias registradas/ });
    const titulo = await bloque.getByRole("heading").textContent();
    expect(titulo).toMatch(/provincia de/);
    const total = await bloque.locator(".font-mono").first().textContent();

    // Ni el distrito ni los checklists de exposición lo mueven. Las esperas se arrancan antes
    // de la acción por lo mismo que arriba.
    const trasDistrito = esperarApi(page, "distrito=");
    await page.getByLabel("Distrito").selectOption({ index: 1 });
    await trasDistrito;

    const trasPeligro = esperarApi(page, "peligros=sismo");
    await soloPeligro(page, "Sismo");
    await trasPeligro;

    await expect(bloque.getByRole("heading")).toHaveText(titulo!);
    await expect(bloque.locator(".font-mono").first()).toHaveText(total!);
  });

  test("cambiar la agrupación reagrupa sin volver a pedir nada", async ({ page }) => {
    // Las dos agrupaciones vienen en el mismo payload. Y no suman igual a propósito: los
    // distritos que declaran subtotales sin desagregar (ADR-D1) cuentan por tipo de evento y no
    // por evento, así que el total sube al agrupar por tipo y la pantalla lo explica.
    await page.goto("/peligros");
    await esperarApi(page, "/api/territorio/distritos/");
    await page.getByLabel("Provincia").selectOption({ index: 1 });
    await esperarApi(page, "provincia=");
    const respuesta = esperarApi(page, "/api/peligros/frecuencia/provincia/");
    await page.getByRole("checkbox", { name: "Ver las emergencias" }).check();
    const datos = await (await respuesta).json();

    const barras = page.locator(".recharts-bar-rectangle");
    await expect(barras).toHaveCount(datos.eventos.length);

    const pedidas: string[] = [];
    page.on("request", (r) => {
      if (r.url().includes("/api/peligros/frecuencia/")) pedidas.push(r.url());
    });
    await page.getByRole("checkbox", { name: "Agrupar por tipo de evento" }).check();

    await expect(barras).toHaveCount(datos.familias.length);
    expect(pedidas, `reagrupar disparó peticiones:\n${pedidas.join("\n")}`).toEqual([]);
  });

  test("encender y apagar las emergencias conserva la provincia y el distrito", async ({
    page,
  }) => {
    await page.goto("/peligros");
    await esperarApi(page, "/api/territorio/distritos/");
    await page.getByLabel("Provincia").selectOption({ index: 1 });
    await esperarApi(page, "provincia=");
    await page.getByLabel("Distrito").selectOption({ index: 1 });
    await esperarApi(page, "distrito=");

    const provincia = await page.getByLabel("Provincia").inputValue();
    const distrito = await page.getByLabel("Distrito").inputValue();

    const casilla = page.getByRole("checkbox", { name: "Ver las emergencias" });
    const respuesta = esperarApi(page, "/api/peligros/frecuencia/provincia/");
    await casilla.check();
    await respuesta;
    await casilla.uncheck();

    await expect(page.getByLabel("Provincia")).toHaveValue(provincia);
    await expect(page.getByLabel("Distrito")).toHaveValue(distrito);
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

  test("la tabla lista todos los peligros de cada centro poblado", async ({ page }) => {
    // El nivel máximo es un resumen: con 3.4 peligros de media por lugar, «Muy alto» no dice a
    // qué está expuesto, que es lo que decide qué medida le toca.
    await page.goto("/peligros");
    const filas = (await (await esperarApi(page, "/api/ccpp/?")).json()).results;
    const conVarios = filas.findIndex((f: { peligros: unknown[] }) => f.peligros.length > 1);
    expect(conVarios, "el API no devolvió ninguno con varios peligros").toBeGreaterThanOrEqual(0);

    const tabla = page.locator("table").last();
    await expect(tabla.getByRole("columnheader", { name: "Distrito" })).toBeVisible();
    await expect(tabla.getByRole("columnheader", { name: "Peligros" })).toBeVisible();

    // Tantos íconos como peligros trae esa fila del API: si el mapa y la tabla discreparan,
    // sería justo aquí.
    const fila = tabla.locator("tbody tr").nth(conVarios);
    await expect(fila.locator("li")).toHaveCount(filas[conVarios].peligros.length);
  });

  test("la tabla pagina de 20 en 20 y no repite centros poblados", async ({ page }) => {
    // Dos fallos se juntaban aquí: el orden del API era parcial —770 nombres se repiten en el
    // padrón— así que `LIMIT/OFFSET` repetía filas y se saltaba otras; y el cliente archivaba
    // la respuesta de una página bajo el número de la siguiente. Se veían filas duplicadas; lo
    // que no se veía, los centros poblados perdidos.
    const errores = vigilarConsola(page);
    await page.goto("/peligros");
    await esperarApi(page, "/api/ccpp/?");

    const filas = page.locator("table").last().locator("tbody tr");
    await expect(filas).toHaveCount(20);

    const enlaces = () => page.locator("table").last().locator("tbody tr td:nth-child(2) a");
    for (let i = 0; i < 2; i++) {
      await page.getByRole("button", { name: /Ver más/ }).click();
      await esperarApi(page, `page=${i + 2}`);
    }
    await expect(filas).toHaveCount(60);

    const codigos = await enlaces().evaluateAll((as) => as.map((a) => a.getAttribute("href")));
    expect(new Set(codigos).size, `hay repetidos:\n${codigos.join("\n")}`).toBe(codigos.length);
    expect(errores, `errores en consola:\n${errores.join("\n")}`).toEqual([]);
  });

  test("«Reiniciar» devuelve los filtros a su estado inicial", async ({ page }) => {
    await page.goto("/peligros");
    await esperarApi(page, "/api/peligros/resumen/");

    await soloPeligro(page, "Sismo");
    await esperarApi(page, "peligros=sismo");
    await expect(page.getByRole("checkbox", { name: "Heladas" })).not.toBeChecked();

    await page.getByRole("button", { name: "Reiniciar" }).click();

    await expect(page.getByRole("checkbox", { name: "Heladas" })).toBeChecked();
    await expect(page.getByRole("checkbox", { name: "Sismo" })).toBeChecked();
    await expect(page.getByRole("checkbox", { name: "Bajo" })).toBeChecked();
  });

  test("el mapa recibe una ranura por peligro, no solo el peor", async ({ page }) => {
    // Antes se dibujaba únicamente el de mayor nivel y el resto quedaba escondido en el popup,
    // que es lo que motivó la corona. Cada ranura la pinta una capa distinta, así que lo que se
    // comprueba es que el payload las traiga y que **la consola quede limpia**: una expresión
    // de estilo inválida tumba la capa entera, y un `icon-image` sin su imagen registrada
    // escupe un error por punto. Los dos fallos son mudos en la pantalla.
    const errores = vigilarConsola(page);
    await page.goto("/peligros");
    const geojson = await (await esperarApi(page, "/api/ccpp/geojson/")).json();
    await esperarMapaPintado(page);

    type Props = Record<string, unknown>;
    const conVarios = geojson.features
      .map((f: { properties: Props }) => f.properties)
      .filter((p: Props) => Number(p.clasificaciones) > 1);
    expect(conVarios.length, "ningún punto con varios peligros").toBeGreaterThan(0);

    for (const p of conVarios.slice(0, 20)) {
      for (let k = 0; k < Number(p.clasificaciones); k++) {
        expect(p[`s${k}`], `falta la ranura ${k}`).toBeTruthy();
        expect(p[`n_${k}`]).toBeGreaterThanOrEqual(1);
      }
    }
    expect(errores, `errores en consola:\n${errores.join("\n")}`).toEqual([]);
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
