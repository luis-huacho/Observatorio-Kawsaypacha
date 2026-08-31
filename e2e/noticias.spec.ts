/**
 * `/noticias` — el listado editorial y su ficha.
 *
 * Lo que se protege son cosas que **se ven bien aunque estén mal**: el orden con el que llegan
 * las publicaciones (una pantalla mal ordenada no da ningún error), que el cuerpo de la ficha se
 * pinte como HTML y no como el texto de sus etiquetas, y que un anexo descargue el archivo y no
 * el `index.html` de la SPA.
 */
import { expect, test } from "./fixtures";

import { esperarApi, irEsperando, vigilarConsola } from "./apoyo";

test.describe("Noticias", () => {
  test("las destacadas encabezan el listado", async ({ page }) => {
    const datos = await (await irEsperando(page, "/noticias", "/api/noticias/")).json();

    if (datos.count === 0) test.skip(true, "no hay noticias publicadas (seed sin --demo)");

    const destacadas = datos.results.filter((n: { destacada: boolean }) => n.destacada);
    if (destacadas.length === 0) test.skip(true, "ninguna noticia está marcada como destacada");

    // El API es la fuente del orden; aquí se comprueba que la grilla lo respeta y no reordena.
    const enlaces = page.locator('a[href^="/noticias/"]');
    await expect(enlaces.first()).toBeVisible();

    const primeros = datos.results
      .slice(0, destacadas.length)
      .map((n: { slug: string }) => n.slug);
    for (const [i, slug] of primeros.entries()) {
      await expect(enlaces.nth(i)).toHaveAttribute("href", `/noticias/${slug}`);
    }

    // Y dentro del bloque destacado manda la fecha, la más reciente arriba.
    const fechas = destacadas.map((n: { fecha: string }) => n.fecha);
    expect(fechas).toEqual([...fechas].sort().reverse());
  });

  test("el cuerpo de la ficha se pinta como HTML, no como texto", async ({ page }) => {
    const errores = vigilarConsola(page);

    const datos = await (await irEsperando(page, "/noticias", "/api/noticias/")).json();
    if (datos.count === 0) test.skip(true, "no hay noticias publicadas (seed sin --demo)");

    await page.locator('a[href^="/noticias/"]').first().click();

    // El fallo que cierra esta prueba: la ficha imprimía el HTML de CKEditor tal cual, así que en
    // pantalla se leían las etiquetas. Un `<p>` real dentro del contenedor demuestra lo contrario.
    const cuerpo = page.locator(".contenido-rico");
    await expect(cuerpo).toBeVisible();
    expect(await cuerpo.locator("p").count()).toBeGreaterThan(0);

    expect(await page.locator("body").innerText()).not.toContain("<p>");
    expect(errores, `errores en consola:\n${errores.join("\n")}`).toEqual([]);
  });

  test("la ilustración por defecto de cada tipo existe y carga", async ({ page }) => {
    // Es la ÚNICA red que mira el archivo de verdad. El valor crudo del tipo es el nombre del SVG
    // (`/img/default/<tipo>.svg`), y el backend no puede comprobar que exista: los SVG viven en el
    // bundle del frontend y su contenedor solo monta `./backend`.
    //
    // Se mide con `naturalWidth`, NO con el código de estado: el `try_files $uri /index.html` de la
    // SPA —y el dev server de Vite— responden **200 con HTML** a un archivo que no existe, así que
    // mirar el status daba verde siempre. Un HTML servido donde iba una imagen no decodifica, y
    // eso sí se ve.
    const datos = await (await irEsperando(page, "/noticias", "/api/noticias/")).json();
    if (datos.count === 0) test.skip(true, "no hay noticias publicadas (seed sin --demo)");

    // Las portadas se piden con carga diferida: hay que llegar al pie para que entren todas.
    await page.mouse.wheel(0, 20000);
    await page.waitForLoadState("networkidle");

    const ilustraciones = page.locator('img[src*="/img/default/"]');
    // Si no hubiera ninguna, la prueba no estaría midiendo nada.
    expect(await ilustraciones.count()).toBeGreaterThan(0);

    const rotas = await page.evaluate(() =>
      Array.from(document.querySelectorAll("img"))
        .filter((img) => img.src.includes("/img/default/"))
        .filter((img) => !img.complete || img.naturalWidth === 0)
        .map((img) => img.src),
    );

    expect(rotas, `ilustraciones que no cargan:\n${rotas.join("\n")}`).toEqual([]);
  });

  test("el anexo descarga el archivo, no el HTML de la SPA", async ({ page, request }) => {
    // Es la misma trampa que mide el caso de las ilustraciones con `naturalWidth`, y por el mismo
    // motivo: el `try_files $uri /index.html` de la SPA —y el dev server de Vite— responden **200
    // con HTML** a una ruta que no existe, así que comprobar el código de estado da verde siempre.
    // Aquí se mira lo único que distingue las dos respuestas: el tipo y los primeros bytes.
    //
    // El fallo que cierra: una URL relativa en el serializer. El enlace se pinta, se pulsa, no da
    // error y no descarga nada — porque se resuelve contra el dominio de la SPA, no el del API.
    // La ficha se pide navegando y no con `request.get` a una URL montada a mano: el origen del
    // API cambia entre el dev server y la corrida sobre nginx, y aquí interesa el que use la SPA.
    const datos = await (await irEsperando(page, "/noticias", "/api/noticias/")).json();
    if (datos.count === 0) test.skip(true, "no hay noticias publicadas (seed sin --demo)");

    const detalle = esperarApi(page, /\/api\/noticias\/[^/]+\/$/);
    detalle.catch(() => {});
    await page.locator('a[href^="/noticias/"]').first().click();
    const ficha = await (await detalle).json();

    if (!ficha.archivos.length) test.skip(true, "la primera noticia no trae adjuntos");

    // La URL viene absoluta del serializer, así que esto vale igual contra el dev server o nginx.
    const adjunto = ficha.archivos[0];
    const respuesta = await request.get(adjunto.archivo);

    expect(respuesta.status()).toBe(200);
    expect(respuesta.headers()["content-type"] ?? "").not.toContain("text/html");
    // La firma del formato es lo que de verdad separa un PDF de una página de error con 200.
    const cuerpo = await respuesta.body();
    expect(cuerpo.subarray(0, 4).toString()).toBe("%PDF");
    expect(cuerpo.length).toBe(adjunto.peso_bytes);
  });

  test("los anexos van al pie, entre el cuerpo y las palabras clave", async ({ page }) => {
    const errores = vigilarConsola(page);

    const datos = await (await irEsperando(page, "/noticias", "/api/noticias/")).json();
    if (datos.count === 0) test.skip(true, "no hay noticias publicadas (seed sin --demo)");

    await page.locator('a[href^="/noticias/"]').first().click();
    await expect(page.locator(".contenido-rico")).toBeVisible();

    const enlaces = page.getByRole("heading", { name: "Enlaces relacionados" });
    if ((await enlaces.count()) === 0) test.skip(true, "la primera noticia no trae anexos");

    const cuerpo = await page.locator(".contenido-rico").boundingBox();
    const bloque = await enlaces.boundingBox();
    expect(bloque!.y).toBeGreaterThan(cuerpo!.y);

    // Los enlaces externos abren fuera y sin dejar que el destino toque `window.opener`.
    const externo = page.locator('section a[target="_blank"]').first();
    await expect(externo).toHaveAttribute("rel", /noopener/);

    // Cazaría, entre otras cosas, la clave repetida de React si dos enlaces comparten URL.
    expect(errores, `errores en consola:\n${errores.join("\n")}`).toEqual([]);
  });

  test("una noticia sin anexos no pinta bloques vacíos", async ({ page }) => {
    // Fija la decisión: aquí el vacío NO se declara. A diferencia de una norma sin `url_oficial`
    // —donde la ficha promete un acceso al documento oficial y su ausencia es información—, nadie
    // prometió que una noticia tuviera anexos, y anunciarlo insinuaría un olvido del editor.
    const datos = await (await irEsperando(page, "/noticias", "/api/noticias/")).json();
    if (datos.count === 0) test.skip(true, "no hay noticias publicadas (seed sin --demo)");

    const sinAnexos = datos.results.find((n: { destacada: boolean }) => !n.destacada);
    if (!sinAnexos) test.skip(true, "todas las noticias del seed están destacadas");

    await page.goto(`/noticias/${sinAnexos.slug}`);
    await expect(page.locator(".contenido-rico")).toBeVisible();

    await expect(page.getByRole("heading", { name: "Enlaces relacionados" })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Documentos" })).toHaveCount(0);
  });
});
