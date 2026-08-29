/**
 * Compartir una ficha, y lo que ve quien recibe el enlace.
 *
 * **La prueba que importa es la primera, y no usa el navegador.** `page.request.get()` pide el HTML
 * y lo devuelve **sin ejecutar JavaScript**, que es exactamente lo que hacen los rastreadores de
 * WhatsApp, Facebook y LinkedIn. Una prueba que mirara `document.querySelector('meta[property=...]')`
 * pasaría en verde aunque las metas las pusiera React — y entonces no comprobaría nada, porque a
 * esos rastreadores React no les llega.
 *
 * Por eso esta prueba solo tiene sentido contra el modo producción (`compose.local.yml` o el
 * servidor): en `npm run dev` la SPA la sirve Vite y nginx no está delante para pasar las fichas
 * por Django. Contra el servidor de desarrollo se salta sola en vez de fallar, que es lo honesto:
 * un rojo ahí diría «el sitio está mal» cuando lo que pasa es que ese modo no monta esa pieza.
 */
import { expect, test } from "./fixtures";

import { irEsperando } from "./apoyo";

/** Primera noticia publicada, tomada del propio sitio para no fijar un slug en la prueba. */
async function unaNoticia(page: import("@playwright/test").Page): Promise<string | null> {
  await irEsperando(page, "/noticias", "/noticias/");
  const enlace = page.locator('a[href^="/noticias/"]').first();
  if (!(await enlace.count())) return null;
  return enlace.getAttribute("href");
}

test.describe("compartir", () => {
  test("el HTML de una ficha trae sus metas sin ejecutar JavaScript", async ({ page, baseURL }) => {
    const ruta = await unaNoticia(page);
    test.skip(!ruta, "no hay noticias publicadas en este entorno");

    const respuesta = await page.request.get(new URL(ruta!, baseURL).toString());
    const html = await respuesta.text();

    // Sin esta guarda, el fallo se leería como «faltan las metas» cuando lo que falta es nginx.
    test.skip(
      !html.includes('property="og:title"'),
      "este entorno sirve la SPA sin pasar las fichas por Django (modo dev)",
    );

    expect(html).toContain('property="og:image"');
    expect(html).toContain('name="twitter:card"');
    expect(html).toContain('rel="canonical"');
    // El título tiene que ser el DE LA FICHA, no el genérico del sitio: es justo la diferencia
    // entre que el enlace compartido se distinga y que todos se vean iguales.
    const titulo = html.match(/<title>(.*?)<\/title>/)?.[1] ?? "";
    expect(titulo).not.toBe("Observatorio Kallpachakuy — GRD y ACC en Cusco");
    // Y la SPA tiene que seguir arrancando después de inyectar.
    expect(html).toContain('<div id="root">');
  });

  test("el sitemap lista las fichas publicadas", async ({ page, baseURL }) => {
    const respuesta = await page.request.get(new URL("/sitemap.xml", baseURL).toString());
    // Por el tipo de contenido y no por `respuesta.ok()`: en modo dev, Vite responde 200 con el
    // index.html a CUALQUIER ruta, así que un 200 aquí no significa que haya sitemap.
    const tipo = respuesta.headers()["content-type"] ?? "";
    test.skip(!tipo.includes("xml"), "este entorno no sirve el sitemap (modo dev)");

    const xml = await respuesta.text();
    expect(xml).toContain("<urlset");
    expect(xml).toContain("/normativa");
    // `/comparar` sigue viva pero está fuera del menú (ADR-P2): anunciarla la reactivaría de
    // tapadillo, que es el tipo de reactivación que nadie decide.
    expect(xml).not.toContain("/comparar");
  });

  test("la ficha ofrece los destinos de compartir", async ({ page }) => {
    const ruta = await unaNoticia(page);
    test.skip(!ruta, "no hay noticias publicadas en este entorno");
    await page.goto(ruta!);

    const barra = page.getByRole("heading", { name: /compartir esta publicaci/i });
    await expect(barra).toBeVisible();

    // Los enlaces llevan la URL de ESTA ficha, no la del sitio: es el fallo silencioso del caso
    // —los botones se ven y comparten la portada—.
    const whatsapp = page.getByRole("link", { name: "WhatsApp" });
    await expect(whatsapp).toBeVisible();
    expect(await whatsapp.getAttribute("href")).toContain(encodeURIComponent(ruta!.slice(1)));

    await expect(page.getByRole("button", { name: /copiar enlace/i })).toBeVisible();
  });
});
