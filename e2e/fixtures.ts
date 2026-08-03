/**
 * `test` extendido con lo que toda prueba necesita.
 *
 * Se importa desde aquí en lugar de `@playwright/test` para que nadie tenga que recordar dos
 * preparativos en cada caso: descartar el beacon de métricas y saber si el móvil esconde el menú
 * detrás del botón de hamburguesa.
 */
import { test as base, expect, type Page } from "@playwright/test";

import { sinMetricas } from "./apoyo";

/**
 * Abre la navegación si está colapsada (móvil) y no hace nada si ya está visible (escritorio).
 *
 * Sin esto, cualquier comprobación sobre un enlace del menú falla en móvil con «hidden», que
 * parece un fallo del sitio y es solo un menú cerrado.
 */
export async function abrirMenu(page: Page): Promise<void> {
  // Por el botón, no por «¿se ve algún enlace?»: el logo es un enlace y está visible en móvil,
  // así que esa comprobación daba el menú por abierto y luego fallaba con «hidden».
  const boton = page.getByRole("button", { name: "Menú" });
  if (await boton.isVisible().catch(() => false)) await boton.click();
}

export const test = base.extend({
  page: async ({ page }, use) => {
    await sinMetricas(page);
    await use(page);
  },
});

export { expect };
