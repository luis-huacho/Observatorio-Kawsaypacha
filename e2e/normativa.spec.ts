/**
 * `/normativa` — el filtro por entidad emisora y la ficha.
 *
 * Lo que se protege son dos cosas que **se ven bien aunque estén mal**: que el desplegable de
 * entidades filtre de verdad —un `<select>` que no llega a la consulta deja la misma lista en
 * pantalla y nadie lo nota— y que la ficha nombre a la institución cuando consta, replegando al
 * nivel de gobierno cuando no. El repliegue es la mitad que se rompe en silencio: si desapareciera,
 * la línea entera se iría de las normas sin entidad y la ficha perdería un dato sin dar error.
 */
import { expect, test } from "./fixtures";

import { esperarApi, irEsperando, vigilarConsola } from "./apoyo";

/**
 * El listado, y **solo** el listado: `/api/normativa/entidades/` lleva esa misma cadena dentro, así
 * que esperar por el prefijo casa con la que llegue primero. Cuando casaba con el catálogo, `datos`
 * era un array sin `results` y la prueba fallaba de forma intermitente.
 */
const LISTADO = /\/api\/normativa\/(\?|$)/;

type Norma = {
  slug: string;
  entidad_emisora: { slug: string; nombre: string; sigla: string } | null;
};

test.describe("Normativa", () => {
  test("el desplegable de entidades filtra el listado", async ({ page }) => {
    const errores = vigilarConsola(page);

    const datos = await (await irEsperando(page, "/normativa", LISTADO)).json();
    if (datos.count === 0) test.skip(true, "no hay normativa publicada (seed sin --demo)");

    const conEntidad = (datos.results as Norma[]).filter((n) => n.entidad_emisora);
    if (conEntidad.length === 0)
      test.skip(true, "ninguna norma publicada tiene entidad emisora asignada");

    const entidad = conEntidad[0].entidad_emisora!;
    const select = page.getByLabel("Entidad emisora");
    await expect(select).toBeVisible();

    // El filtro tiene que llegar al servidor: comprobarlo solo en pantalla dejaría pasar un
    // `<select>` que cambia de estado y no toca la consulta.
    const respuesta = esperarApi(page, `entidad=${entidad.slug}`);
    await select.selectOption(entidad.slug);
    const filtrado = await (await respuesta).json();

    expect(filtrado.count).toBeGreaterThan(0);
    expect(filtrado.count).toBeLessThanOrEqual(datos.count);
    for (const n of filtrado.results as Norma[]) {
      expect(n.entidad_emisora?.slug).toBe(entidad.slug);
    }

    // Y la grilla enseña lo que devolvió el API, no lo de antes.
    const enlaces = page.locator('a[href^="/normativa/"]');
    await expect(enlaces.first()).toHaveAttribute(
      "href",
      `/normativa/${(filtrado.results as Norma[])[0].slug}`,
    );

    expect(errores).toEqual([]);
  });

  test("la ficha nombra a la entidad, y repliega al ámbito cuando no consta", async ({ page }) => {
    const datos = await (await irEsperando(page, "/normativa", LISTADO)).json();
    if (datos.count === 0) test.skip(true, "no hay normativa publicada (seed sin --demo)");

    const normas = datos.results as Norma[];
    const con = normas.find((n) => n.entidad_emisora);
    const sin = normas.find((n) => !n.entidad_emisora);

    if (con) {
      await irEsperando(page, `/normativa/${con.slug}`, `/api/normativa/${con.slug}`);
      await expect(page.getByText(`Emitida por ${con.entidad_emisora!.nombre}`)).toBeVisible();
    }

    if (sin) {
      await irEsperando(page, `/normativa/${sin.slug}`, `/api/normativa/${sin.slug}`);
      // El repliegue: sin entidad la línea no desaparece, dice el nivel de gobierno.
      await expect(page.getByText(/Publicada por el Gobierno/)).toBeVisible();
    }

    if (!con && !sin) test.skip(true, "no hay normas para comprobar los dos estados");
  });
});
