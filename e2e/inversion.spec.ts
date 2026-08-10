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
import { expect, test } from "./fixtures";

import { esperarApi, vigilarConsola } from "./apoyo";
import { abrirMenu } from "./fixtures";

test.describe("Inversión (PP 0068)", () => {
  test("dibuja el tablero, o su estado vacío si no hay ejercicio publicado", async ({ page }) => {
    const errores = vigilarConsola(page);

    await page.goto("/inversion");
    const respuesta = await esperarApi(page, "/api/inversion/");
    const cuerpo = await respuesta.json();

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
    await page.goto("/inversion");
    const cuerpo = await (await esperarApi(page, "/api/inversion/")).json();
    test.skip(!cuerpo.disponible, "no hay ejercicio publicado en este entorno");

    // `textContent` y no `innerText`: las columnas que se ocultan por ancho siguen en el DOM,
    // pero `innerText` de un nodo con `display:none` devuelve cadena vacía.
    const columna = async (n: number) =>
      (await page.locator(`table tbody tr td:nth-child(${n})`).allTextContents()).map((t) =>
        Number(t.replace(/[^\d-]/g, "")),
      );
    const noCreciente = (valores: number[]) => valores.every((v, i) => i === 0 || valores[i - 1] >= v);

    expect(noCreciente(await columna(4)), "por defecto la tabla va ordenada por PIM").toBe(true);

    await page.locator("select").last().selectOption("saldo");
    await expect
      .poll(async () => noCreciente(await columna(7)), { timeout: 5_000 })
      .toBe(true);
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
