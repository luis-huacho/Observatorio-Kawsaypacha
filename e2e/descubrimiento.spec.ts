/**
 * Lo que el sitio publica para que lo descubra una máquina.
 *
 * **Ninguna de estas pruebas abre una página**, y es a propósito: todo lo que se comprueba aquí son
 * respuestas HTTP —cabeceras, tipos de contenido, códigos— que ningún navegador enseña. Es la misma
 * razón que en `compartir.spec.ts`: `page.request.get()` pide sin ejecutar JavaScript, que es como
 * pide un agente.
 *
 * Y por eso solo tienen sentido contra el modo producción (`compose.local.yml` o el servidor): en
 * `npm run dev` la SPA la sirve Vite, nginx no está delante y Django no ve ninguna de estas rutas.
 * Contra el servidor de desarrollo se saltan solas en vez de fallar — un rojo ahí diría «el sitio
 * está mal» cuando lo que pasa es que ese modo no monta esta pieza.
 */
import { expect, test } from "./fixtures";

test.describe("descubrimiento", () => {
  test("el robots.txt anuncia el sitemap de ESTE dominio", async ({ page, baseURL }) => {
    const respuesta = await page.request.get(new URL("/robots.txt", baseURL!).toString());
    const cuerpo = await respuesta.text();

    // En modo dev lo sirve Vite desde `public/`, que es la red y no lleva señales de contenido.
    test.skip(!cuerpo.includes("Content-Signal:"), "este entorno sirve el robots.txt estático (modo dev)");

    // La regresión que fundó todo esto: la línea estaba escrita a mano con otro dominio, que
    // además no resolvía. El sitemap funcionaba y no lo leía nadie.
    const anunciado = cuerpo.match(/^Sitemap:\s*(\S+)$/m)?.[1] ?? "";
    expect(anunciado).toBe(new URL("/sitemap.xml", baseURL!).toString());

    // Y el sitemap anunciado tiene que existir de verdad: anunciar uno que no responde gasta el
    // presupuesto de rastreo y deja al buscador sin la lista de URL.
    const sitemap = await page.request.get(anunciado);
    expect(sitemap.headers()["content-type"]).toContain("xml");

    expect(cuerpo).toContain("Content-Signal: ai-train=no, search=yes, ai-input=yes");
  });

  test("el catálogo de API llega como linkset+json y sus enlaces están vivos", async ({
    page,
    baseURL,
  }) => {
    const respuesta = await page.request.get(new URL("/.well-known/api-catalog", baseURL!).toString());
    const tipo = respuesta.headers()["content-type"] ?? "";
    test.skip(!tipo.includes("linkset"), "este entorno no pasa /.well-known/ por Django (modo dev)");

    const contexto = (await respuesta.json()).linkset[0];
    expect(contexto.anchor).toContain("/api/");

    // El modo de fallo del caso: un catálogo que existe y apunta a URLs muertas se ve exactamente
    // igual que uno bueno. Solo se nota pidiéndolas.
    const destinos = ["service-desc", "service-doc", "status"].flatMap((rel) =>
      contexto[rel].map((enlace: { href: string }) => enlace.href),
    );
    for (const url of [contexto.anchor, ...destinos]) {
      expect((await page.request.get(url)).status(), `${url} no responde 200`).toBe(200);
    }
  });

  test("lo que no publicamos responde 404, y no 200 con el HTML de la SPA", async ({
    page,
    baseURL,
  }) => {
    const catalogo = await page.request.get(new URL("/.well-known/api-catalog", baseURL!).toString());
    test.skip(
      !(catalogo.headers()["content-type"] ?? "").includes("linkset"),
      "este entorno no pasa /.well-known/ por Django (modo dev)",
    );

    // El `try_files $uri /index.html` de la SPA devolvía 200 con HTML a cualquier ruta de aquí
    // abajo, así que cuatro documentos que no existen parecían existir y estar rotos.
    for (const ruta of [
      "/.well-known/openid-configuration",
      "/.well-known/agent-skills/index.json",
      "/.well-known/ai-catalog.json",
    ]) {
      const r = await page.request.get(new URL(ruta, baseURL!).toString(), {
        failOnStatusCode: false,
      });
      expect(r.status(), `${ruta} debería ser 404`).toBe(404);
    }
  });

  test("la portada trae la cabecera Link con el catálogo", async ({ page, baseURL }) => {
    const respuesta = await page.request.get(new URL("/", baseURL!).toString());
    const enlace = respuesta.headers()["link"] ?? "";
    test.skip(!enlace, "este entorno sirve la SPA sin nginx delante (modo dev)");

    expect(enlace).toContain('rel="api-catalog"');
  });
});
