/**
 * `/inversion` — la ventana diferida (ADR-D3).
 *
 * El cliente aún no tiene claridad sobre la data, así que la sección existe con su maqueta lista y
 * un estado vacío honesto. Se prueba porque la tentación al implementarla era rellenarla con ceros:
 * un «S/ 0» sería una afirmación falsa sobre la inversión pública en gestión del riesgo.
 */
import { expect, test } from "./fixtures";

import { esperarApi, vigilarConsola } from "./apoyo";
import { abrirMenu } from "./fixtures";

test.describe("Inversión (diferida)", () => {
  test("muestra el estado vacío, no un cero ni un gráfico en blanco", async ({ page }) => {
    // ADR-D3. Un «0 soles» sería una afirmación falsa sobre la inversión pública; un gráfico
    // vacío se lee como avería. El texto explica que la información está en preparación.
    const errores = vigilarConsola(page);

    await page.goto("/inversion");
    await esperarApi(page, "/api/inversion/");

    await expect(page.getByText(/informaci.n en preparaci.n/i)).toBeVisible();
    await expect(page.locator("canvas")).toHaveCount(0);
    await expect(page.getByText(/^S\/\s*0$|^0$/)).toHaveCount(0);
    expect(errores, `errores en consola:\n${errores.join("\n")}`).toEqual([]);
  });

  test("la sección sigue anunciada en el menú", async ({ page }) => {
    // Diferida no es oculta: si desapareciera del menú, nadie sabría que está prevista.
    await page.goto("/");
    await esperarApi(page, "/api/sitio/");
    // En móvil la navegación vive detrás del botón de hamburguesa.
    await abrirMenu(page);

    // `:visible` porque el enlace existe dos veces —nav de escritorio y panel móvil— y solo una
    // de las dos se muestra según el ancho. Sin esto, `.first()` cae siempre en la de escritorio.
    await expect(page.locator('a[href="/inversion"]:visible').first()).toBeVisible();
  });
});
