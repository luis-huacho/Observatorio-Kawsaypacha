/**
 * `/inversion` — el tablero del PP 0068 por municipalidad.
 *
 * La ventana tiene **dos modos legítimos** y los dos se prueban en la misma corrida, según lo que
 * responda el API del entorno: con un ejercicio publicado se dibuja el tablero, y sin ninguno
 * vuelve a su estado «información en preparación». El segundo no es un residuo de cuando la
 * sección estaba diferida: es lo que se ve mientras PREDES revisa un ejercicio recién importado,
 * y sigue siendo la razón por la que no se rellena con ceros. Un «S/ 0» sería una afirmación
 * falsa sobre la inversión pública en gestión del riesgo.
 */
import type { Page } from "@playwright/test";

import { expect, test } from "./fixtures";

import { esperarApi, vigilarConsola } from "./apoyo";
import { abrirMenu } from "./fixtures";

/**
 * El tablero y el listado comparten prefijo, y `esperarApi` casa por subcadena: pedir
 * `/api/inversion/` atraparía la respuesta de `/api/inversion/entidades/`, cuyo cuerpo no tiene
 * `disponible` y haría que el test creyera que la ventana está vacía.
 */
const API_TABLERO = /\/api\/inversion\/(\?|$)/;
const API_LISTADO = /\/api\/inversion\/entidades\//;
const API_MAPA = /\/api\/inversion\/mapa\//;

/**
 * Abre la ruta **armando la espera antes de navegar**.
 *
 * `page.goto` resuelve al `load`, y la petición del tablero puede haber terminado ya para
 * entonces: pedirla después es una carrera que se pierde en cuanto la respuesta viene de caché.
 * Los otros specs no lo notan porque sus páginas hacen varias peticiones al mismo prefijo.
 */
async function abrir(page: Page, ruta: string, api: RegExp = API_TABLERO) {
  const respuesta = esperarApi(page, api);
  await page.goto(ruta);
  return (await respuesta).json();
}

/**
 * La tabla de municipalidades, acotada a su sección.
 *
 * Desde que el cuadro de evolución existe hay dos `<table>` en la página, y un `table tbody tr`
 * suelto empezaría a leer las cifras por año como si fueran filas del ranking — sin dar ningún
 * error, porque también son números.
 */
function tablaDeMunicipalidades(page: Page) {
  return page
    .locator("section")
    .filter({ has: page.getByRole("heading", { name: "Municipalidades" }) })
    .locator("table");
}

test.describe("Inversión (PP 0068)", () => {
  test("dibuja el tablero, o su estado vacío si no hay ejercicio publicado", async ({ page }) => {
    const errores = vigilarConsola(page);

    const cuerpo = await abrir(page, "/inversion");

    if (!cuerpo.disponible) {
      await expect(page.getByText(/informaci.n en preparaci.n/i)).toBeVisible();
      // Ni un gráfico en blanco —que se lee como avería— ni un cero, que sería mentira.
      await expect(page.locator("canvas")).toHaveCount(0);
      await expect(page.getByText(/^S\/\s*0$|^0$/)).toHaveCount(0);
      expect(errores, `errores en consola:\n${errores.join("\n")}`).toEqual([]);
      return;
    }

    // La unidad es la municipalidad, no el distrito: si el encabezado dijera «Distritos», la
    // tabla estaría prometiendo una cifra distrital que ninguna fuente respalda.
    await expect(page.getByRole("heading", { name: "Municipalidades" })).toBeVisible();
    await expect(page.getByText(/PIM del PP 0068/)).toBeVisible();
    await expect(page.getByRole("heading", { name: /se ejecuta lo proyectado/i })).toBeVisible();
    await expect(page.getByRole("heading", { name: /procesos de la GRD/i })).toBeVisible();

    const filas = page.locator("table tbody tr");
    await expect(filas.first()).toBeVisible();
    expect(await filas.count()).toBeGreaterThan(1);

    // Un corte a mitad de año tiene que avisarlo en pantalla: su % de ejecución se calcula
    // contra un PIM anual y sin el aviso se lee como una caída de la ejecución.
    if (cuerpo.es_parcial) {
      await expect(page.getByText(new RegExp(`Corte a ${cuerpo.corte}`, "i"))).toBeVisible();
    }

    expect(errores, `errores en consola:\n${errores.join("\n")}`).toEqual([]);
  });

  test("el ranking ordena de verdad por la columna elegida", async ({ page }) => {
    // Son los tres rankings que pide la hoja «Campos» del cliente: PIM, % de ejecución y saldo
    // pendiente. Comprobar que el `select` cambia no basta: lo que puede romperse en silencio es
    // que la tabla siga ordenada por lo anterior, y con 116 filas nadie lo nota a ojo.
    //
    // El orden lo resuelve el **servidor** desde que la tabla se pagina, así que cambiar el
    // `select` dispara una petición: hay que esperarla antes de leer el DOM.
    const cuerpo = await abrir(page, "/inversion");
    test.skip(!cuerpo.disponible, "no hay ejercicio publicado en este entorno");
    // Acotado a su sección: la página tiene dos tablas desde que existe el cuadro de evolución,
    // y `table tbody tr` a secas leería las cifras por año como si fueran municipalidades.
    const listado = tablaDeMunicipalidades(page);
    await expect(listado.locator("tbody tr").first()).toBeVisible();

    // `textContent` y no `innerText`: las columnas que se ocultan por ancho siguen en el DOM,
    // pero `innerText` de un nodo con `display:none` devuelve cadena vacía.
    const columna = async (n: number) =>
      (await listado.locator(`tbody tr td:nth-child(${n})`).allTextContents()).map((t) =>
        Number(t.replace(/[^\d-]/g, "")),
      );
    const noCreciente = (valores: number[]) => valores.every((v, i) => i === 0 || valores[i - 1] >= v);

    expect(noCreciente(await columna(4)), "por defecto la tabla va ordenada por PIM").toBe(true);

    await Promise.all([
      esperarApi(page, /ordenar=saldo/),
      page.getByLabel("Ordenar por:").or(page.locator("select").last()).selectOption("saldo"),
    ]);
    await expect
      .poll(async () => noCreciente(await columna(7)), { timeout: 10_000 })
      .toBe(true);
  });

  test("la tabla se pagina y dice cuántas municipalidades muestra", async ({ page }) => {
    // El pie es el contrato de la paginación: si dijera el total como si fuera lo cargado,
    // nadie notaría que solo está viendo las 50 primeras de 116.
    const cuerpo = await abrir(page, "/inversion");
    test.skip(!cuerpo.disponible, "no hay ejercicio publicado en este entorno");

    const pie = page.getByText(/Mostrando .* de .* municipalidades/i);
    await expect(pie).toBeVisible();
    const listado = tablaDeMunicipalidades(page);
    const antes = await listado.locator("tbody tr").count();

    const boton = page.getByRole("button", { name: /Ver \d+ más/ });
    test.skip(!(await boton.isVisible()), "el entorno tiene una sola página de municipalidades");

    await boton.click();
    await expect.poll(async () => listado.locator("tbody tr").count()).toBeGreaterThan(antes);
  });

  test("la ficha de una municipalidad se abre y conserva el ejercicio al volver", async ({
    page,
  }) => {
    // Los filtros viven en la URL justamente para esto: sin ellos, volver del detalle dejaría
    // al usuario en el ejercicio por defecto y no en el que estaba mirando.
    const cuerpo = await abrir(page, "/inversion?anio=2026");
    test.skip(!cuerpo.disponible || cuerpo.anio !== 2026, "el entorno no publica 2026");

    const primera = page.locator("table tbody tr td:first-child a").first();
    const nombre = (await primera.textContent())!.trim();
    await primera.click();

    // El enlace arrastra los filtros, así que la URL de la ficha lleva query string.
    await expect(page).toHaveURL(/\/inversion\/\d+\?/);
    await expect(page.locator("h1")).toContainText(nombre);
    await expect(page.getByRole("heading", { name: /Historia presupuestal/i })).toBeVisible();

    await page.getByRole("link", { name: /Volver a Inversión/i }).click();
    await expect(page).toHaveURL(/anio=2026/);
  });

  test("el cuadro de evolución trae una fila por ejercicio publicado", async ({ page }) => {
    const cuerpo = await abrir(page, "/inversion");
    test.skip(!cuerpo.disponible, "sin ejercicio publicado");

    const cuadro = page.locator("section", { hasText: /^Tendencia/ }).first();
    await expect(cuadro.locator("tbody tr")).toHaveCount(cuerpo.tendencia.length);
    // El PIA es la tercera serie: sin él, la distancia hasta el PIM —la variación— no se ve.
    await expect(cuadro.getByText("PIA", { exact: true }).first()).toBeVisible();
    if (cuerpo.tendencia.some((t: { es_parcial: boolean }) => t.es_parcial)) {
      await expect(cuadro.getByText(/^\* Ejercicio con corte parcial/)).toBeVisible();
    }
  });

  test("el visor declara el dinero que no puede pintar", async ({ page }) => {
    // Se afirma sobre la leyenda y el pie, que son DOM real. El canvas de MapLibre no se
    // inspecciona: un `expect` sobre píxeles falla por razones que no son el fallo que importa.
    const respuesta = esperarApi(page, API_MAPA);
    await page.goto("/inversion");
    const mapa = await (await respuesta).json();
    test.skip(!mapa.disponible, "sin ejercicio publicado");

    const visor = page.locator("section", { hasText: /Dónde está el presupuesto/ }).first();
    await expect(visor.locator("canvas")).toBeVisible();
    await expect(visor.getByRole("button", { name: "Devengado" })).toBeVisible();

    // ADR-D6: a nivel distrital las municipalidades provinciales no se pintan, y su importe se
    // declara. Que el pie exista es lo que impide que el mapa se lea como el total del programa.
    expect(mapa.no_ubicado.entidades).toBeGreaterThan(0);
    await expect(visor.getByText(/no aparecen en el mapa/i)).toBeVisible();
    await expect(visor.getByText(/sin municipalidad \(\d+\)/)).toBeVisible();
  });

  test("cambiar el visor a provincia no deja nada fuera del mapa", async ({ page }) => {
    const respuesta = esperarApi(page, API_MAPA);
    await page.goto("/inversion?nivel=provincial");
    const mapa = await (await respuesta).json();
    test.skip(!mapa.disponible, "sin ejercicio publicado");

    // Todas las municipalidades caen dentro de alguna provincia, así que a este nivel el mapa
    // cubre el ámbito entero y el pie de «no aparecen» desaparece.
    expect(mapa.no_ubicado.entidades).toBe(0);
    const visor = page.locator("section", { hasText: /Dónde está el presupuesto/ }).first();
    await expect(visor.getByText(/no aparecen en el mapa/i)).toHaveCount(0);
  });

  test("una municipalidad que no existe no deja la página en blanco", async ({ page }) => {
    await page.goto("/inversion/000000");

    await expect(
      page.getByText(/no (se )?(encontr|existe)|no disponible|404/i).first(),
    ).toBeVisible();
  });

  test("comparar ejercicios advierte cuando los cortes no son comparables", async ({ page }) => {
    // Se decidió mostrar el Δ de % de ejecución aunque uno de los dos sea un corte parcial. La
    // advertencia es lo que hace legítima esa decisión, así que se prueba que está.
    const cuerpo = await abrir(page, "/inversion?vista=comparar");
    test.skip(!cuerpo.disponible || cuerpo.ejercicios.length < 2, "hace falta más de un ejercicio");

    const otro = cuerpo.ejercicios.find((e: { anio: number }) => e.anio !== cuerpo.anio)!;
    await page.goto(`/inversion?vista=comparar&comparar_con=${otro.anio}`);
    await esperarApi(page, /comparar_con/);

    await expect(page.getByRole("heading", { name: new RegExp(`frente a ${otro.anio}`) })).toBeVisible();
    if (cuerpo.es_parcial !== otro.es_parcial) {
      await expect(page.getByText(/variación del % de ejecución no es comparable/i)).toBeVisible();
    }
  });

  test("la sección sigue anunciada en el menú", async ({ page }) => {
    await page.goto("/");
    await esperarApi(page, "/api/sitio/");
    // En móvil la navegación vive detrás del botón de hamburguesa.
    await abrirMenu(page);

    // `:visible` porque el enlace existe dos veces —nav de escritorio y panel móvil— y solo una
    // de las dos se muestra según el ancho. Sin esto, `.first()` cae siempre en la de escritorio.
    await expect(page.locator('a[href="/inversion"]:visible').first()).toBeVisible();
  });
});
