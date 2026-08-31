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

import { esperarApi, irEsperando, vigilarConsola } from "./apoyo";
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
 * Ya son tres las `<table>` de la página —el ranking, el cuadro de evolución y el desglose de
 * proyectos—, y un `table tbody tr` suelto empezaría a leer unas por otras sin dar ningún
 * error, porque todas llevan números.
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
    // contra un PIM anual y sin el aviso se lee como una caída de la ejecución. Y el aviso
    // tiene que NOMBRAR el ejercicio, no solo decir con qué no se compara: la versión anterior
    // obligaba a saber qué es un «ejercicio cerrado» para deducir por descarte cuál se mira.
    if (cuerpo.es_parcial) {
      const estado = cuerpo.en_curso ? "año fiscal en curso" : "datos parciales";
      await expect(page.getByText(new RegExp(`Ejercicio ${cuerpo.anio}, ${estado}`, "i"))).toBeVisible();
      await expect(page.getByText(new RegExp(cuerpo.corte_legible, "i")).first()).toBeVisible();
    }
    // La jerga contable no vuelve por la puerta de atrás en el siguiente retoque de copy.
    await expect(page.getByText(/\bcerrado\b/i)).toHaveCount(0);

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

    // Acotado a su tabla: `table tbody tr` suelto ahora cae en el desglose de proyectos, que
    // va antes en el DOM. Para eso existe el helper.
    const primera = tablaDeMunicipalidades(page).locator("tbody tr td:first-child a").first();
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
      await expect(cuadro.getByText(/^\* Ejercicio en curso o con corte parcial/)).toBeVisible();
    }
  });

  test("cada gráfico declara en palabras lo que enseña", async ({ page }) => {
    const cuerpo = await abrir(page, "/inversion");
    test.skip(!cuerpo.disponible, "sin ejercicio publicado");

    // Un gráfico se deja leer pero no concluye. Estas frases son lo que un periodista copia, y
    // sin una prueba se pierden en el siguiente retoque de maquetación sin que nada falle.
    //
    // Se cuentan por su clase COMPLETA y no por `p.border-l-2` a secas: ese selector casaba
    // también con los dos pies del mapa, así que la cuenta pasaba aunque faltara una
    // declaración —justo el fallo que esta prueba existe para ver—. Son cinco desde que el
    // mapa tiene la suya: era el único gráfico de la página sin una.
    const declaraciones = page.locator("p.border-earth-500.border-l-2");
    expect(await declaraciones.count()).toBeGreaterThanOrEqual(5);

    await expect(page.getByText(/entre lo aprobado al abrir el año y lo vigente hoy/i)).toBeVisible();
    await expect(page.getByText(/concentra .* del presupuesto vigente/i).first()).toBeVisible();

    if (cuerpo.tendencia.filter((t: { es_parcial: boolean }) => !t.es_parcial).length >= 2) {
      // Compara los dos últimos COMPLETOS. Comparar contra el corte a mitad de año daría una
      // caída del devengado que no mide una caída: mide medio año contra un año entero.
      await expect(page.getByText(/los dos últimos ejercicios completos/i)).toBeVisible();
    }
  });

  test("el desglose de proyectos dice de quién es el dinero", async ({ page }) => {
    const cuerpo = await abrir(page, "/inversion");
    test.skip(!cuerpo.disponible, "sin ejercicio publicado");

    const seccion = page
      .locator("section")
      .filter({ has: page.getByRole("heading", { name: /Proyectos de inversión frente a/i }) });

    const { con_proyectos: con, de, entidades } = cuerpo.proyectos;
    await expect(page.getByText(new RegExp(`${con} de las ${de} municipalidades`, "i"))).toBeVisible();
    // El ámbito es municipal y el porcentaje en obra se atribuye al Gobierno Regional si no se
    // dice. Es la lectura equivocada que este bloque existe para corregir.
    await expect(seccion.getByText(/El Gobierno Regional no entra en este ámbito/i)).toBeVisible();

    if (con > 0) {
      await expect(seccion.locator("tbody tr")).toHaveCount(con);
      // Ordenado por importe: la primera fila es la que más obra tiene, que es la que se busca.
      await expect(seccion.locator("tbody tr").first()).toContainText(entidades[0].entidad);
    } else {
      await expect(seccion.locator("table")).toHaveCount(0);
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

  test("el diagrama de caja enseña el reparto que el color aplana", async ({ page }) => {
    // Los quintiles son la escala correcta para un mapa, pero su último tramo se traga la cola:
    // con el PIM distrital de 2026 arranca en S/ 216.445, así que un distrito de 220 mil y otro
    // de 9,3 millones salen del mismo color. La caja es lo que dice que la mediana es S/ 73.510.
    const respuesta = esperarApi(page, API_MAPA);
    await page.goto("/inversion");
    const mapa = await (await respuesta).json();
    test.skip(!mapa.disponible, "sin ejercicio publicado");

    const visor = page.locator("section", { hasText: /Dónde está el presupuesto/ }).first();
    const caja = visor.locator("figure svg");
    await expect(caja).toBeVisible();

    // Un punto suelto a la derecha no dice nada; con el nombre dice quién es. Los `<title>` del
    // SVG dan el tooltip sin una línea de JavaScript.
    const atipicos = mapa.distribucion.pim.atipicos;
    await expect(caja.locator("circle")).toHaveCount(atipicos.length);
    if (atipicos.length) {
      await expect(caja.locator("title").first()).toHaveText(
        new RegExp(atipicos[0].nombre.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
      );
    }
    // Y la frase, que es lo que se copia a un informe.
    await expect(visor.getByText(/La mitad de los \d+ distritos está entre/)).toBeVisible();
  });

  test("el porcentaje de ejecución cambia la caja de escala y de unidades", async ({ page }) => {
    // El dinero va en escala logarítmica —en un eje lineal la caja del PIM mide 9 píxeles— pero
    // un porcentaje no tiene cola que comprimir: va lineal de 0 a 100 y el 0 % sí cabe, así que
    // no debe arrastrar la advertencia de los valores que no entran en la escala.
    const respuesta = esperarApi(page, API_MAPA);
    await page.goto("/inversion");
    const mapa = await (await respuesta).json();
    test.skip(!mapa.disponible, "sin ejercicio publicado");

    const visor = page.locator("section", { hasText: /Dónde está el presupuesto/ }).first();
    await expect(visor.getByText(/escala logarítmica/i)).toBeVisible();

    await visor.getByRole("button", { name: "% de ejecución" }).click();

    await expect(visor.getByText(/escala logarítmica/i)).toHaveCount(0);
    await expect(visor.getByText(/no entran? en la escala/i)).toHaveCount(0);
    // La frase pasa a hablar en porcentajes, no en soles.
    await expect(visor.getByText(/La mitad de los \d+ distritos está entre \d/)).toBeVisible();
  });

  test("a nivel provincial la caja se recalcula sobre las trece provincias", async ({ page }) => {
    const respuesta = esperarApi(page, API_MAPA);
    await page.goto("/inversion?nivel=provincial");
    const mapa = await (await respuesta).json();
    test.skip(!mapa.disponible, "sin ejercicio publicado");

    const visor = page.locator("section", { hasText: /Dónde está el presupuesto/ }).first();
    // Concuerda en género: «los 13 provincias» es el descuido que delata una frase generada.
    await expect(visor.getByText(/La mitad de las \d+ provincias está entre/)).toBeVisible();
    await expect(visor.locator("figure svg circle")).toHaveCount(
      mapa.distribucion.pim.atipicos.length
    );
  });

  test("el pie del mapa no explica dos veces lo mismo", async ({ page }) => {
    // Eran ~150 palabras alrededor del mapa, con los 13 distritos capital explicados en los dos
    // pies con palabras distintas. El lector no llegaba al final.
    const respuesta = esperarApi(page, API_MAPA);
    await page.goto("/inversion");
    const mapa = await (await respuesta).json();
    test.skip(!mapa.disponible, "sin ejercicio publicado");

    const visor = page.locator("section", { hasText: /Dónde está el presupuesto/ }).first();

    // La entradilla que había encima del mapa se retiró: lo que decía ya está en la línea de
    // alcance de la cabecera y en el pie de «no aparecen en el mapa».
    await expect(visor.getByText(/no es de territorios|no de territorios/i)).toHaveCount(0);
    // Y las dos frases que se justificaban a sí mismas ante el lector.
    await expect(visor.getByText(/por eso mismo/i)).toHaveCount(0);
    await expect(visor.getByText(/porque este mapa se cita suelto/i)).toHaveCount(0);
    // El plural entre paréntesis leía como una circular.
    await expect(visor.getByText(/\(es\)/)).toHaveCount(0);
    expect(mapa.no_ubicado.motivo).not.toContain("(es)");
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

  test("declara qué está viendo cuando no se ha filtrado nada", async ({ page }) => {
    // Sin filtros la página sirve el ejercicio publicado más reciente y TODA la región, y no lo
    // decía en ninguna parte: el encabezado ponía «ejercicio 2026» sin declarar que era un valor
    // por defecto ni cuál era el ámbito territorial. Un total de región leído como el de una
    // provincia no falla, solo es falso.
    const cuerpo = await abrir(page, "/inversion");
    test.skip(!cuerpo.disponible, "sin ejercicio publicado");

    await expect(page.getByText(/todas las municipalidades de la región Cusco/i)).toBeVisible();
    await expect(page.getByText(new RegExp(`ejercicio ${cuerpo.anio}`, "i")).first()).toBeVisible();

    // Con una provincia puesta, el ámbito cambia de nombre. Lo que nunca puede pasar es que
    // siga diciendo «toda la región» mientras la tabla enseña una sola provincia.
    const provincia = await page.locator("select").nth(1).locator("option").nth(1).getAttribute("value");
    test.skip(!provincia, "el catálogo de provincias no llegó");
    await irEsperando(page, `/inversion?provincia=${provincia}`, API_TABLERO);

    await expect(page.getByText(/las municipalidades de la provincia de/i)).toBeVisible();
    await expect(page.getByText(/todas las municipalidades de la región Cusco/i)).toHaveCount(0);
  });

  test("comparar ejercicios dice para qué sirve antes de pedir el segundo año", async ({ page }) => {
    // Al entrar solo estaba «Elige un ejercicio para comparar», que explica cómo usar la pestaña
    // pero no qué se gana usándola: la tendencia del tablero ya da el total de la región, y lo
    // que esta vista añade es el detalle por municipalidad.
    const cuerpo = await abrir(page, "/inversion?vista=comparar");
    test.skip(!cuerpo.disponible, "sin ejercicio publicado");

    await expect(page.getByText(/municipalidad por municipalidad/i)).toBeVisible();
    await expect(page.getByText(/qui.n entr. o sali. del programa/i)).toBeVisible();
  });

  test("comparar ejercicios advierte cuando los cortes no son comparables", async ({ page }) => {
    // Se decidió mostrar el Δ de % de ejecución aunque uno de los dos sea un corte parcial. La
    // advertencia es lo que hace legítima esa decisión, así que se prueba que está.
    const cuerpo = await abrir(page, "/inversion?vista=comparar");
    test.skip(!cuerpo.disponible || cuerpo.ejercicios.length < 2, "hace falta más de un ejercicio");

    const otro = cuerpo.ejercicios.find((e: { anio: number }) => e.anio !== cuerpo.anio)!;
    await irEsperando(page, `/inversion?vista=comparar&comparar_con=${otro.anio}`, /comparar_con/);

    await expect(page.getByRole("heading", { name: new RegExp(`frente a ${otro.anio}`) })).toBeVisible();
    if (cuerpo.es_parcial !== otro.es_parcial) {
      await expect(page.getByText(/variación del % de ejecución no es comparable/i)).toBeVisible();
    }
  });

  test("el Excel avisa mientras se prepara y no deja el botón bloqueado", async ({
    page,
  }, testInfo) => {
    test.skip(testInfo.project.name === "movil", "las descargas se comprueban en escritorio");

    // El Excel de /inversion es la descarga **rápida** del sitio (~0,1 s), y está aquí a
    // propósito: el mismo componente tiene que servir para los 4 s del PDF y para esto, sin
    // dejar un botón atenuado ni un aviso colgado cuando el servidor responde al instante.
    const cuerpo = await abrir(page, "/inversion");
    test.skip(!cuerpo.disponible, "sin ejercicio publicado");

    const descarga = page.waitForEvent("download", { timeout: 60_000 });
    await page.getByRole("link", { name: /^Excel$/i }).click();
    const archivo = await descarga;

    // El nombre real lo pone `Content-Disposition`, que cross-origin solo se lee si el servidor
    // la expone (`CORS_EXPOSE_HEADERS`). Sin ella el archivo se guardaría con el id del blob.
    expect(archivo.suggestedFilename()).toMatch(/\.xlsx$/);
    await expect(page.getByRole("link", { name: /^Excel$/i })).toBeVisible();
    await expect(page.locator("#avisos-descarga").getByRole("status")).toHaveCount(0);
  });

  test("Ctrl+clic en una descarga sigue abriendo en otra pestaña", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name === "movil", "no hay Ctrl+clic en un teléfono");

    // El botón se pide con `fetch` para poder enseñar el estado, pero **sigue siendo un `<a>`** y
    // los clics con modificador se dejan pasar al navegador. Con un `<button>` se habrían
    // perdido «abrir en pestaña nueva» y «guardar enlace como», que hoy funcionan.
    const cuerpo = await abrir(page, "/inversion");
    test.skip(!cuerpo.disponible, "sin ejercicio publicado");

    const enlace = page.getByRole("link", { name: /Reporte \(PDF\)/i });
    await expect(enlace).toHaveAttribute("href", /\/inversion\/reporte\.pdf/);

    // Que se abra una pestaña es la prueba: significa que el `onClick` del componente dejó pasar
    // el clic en vez de hacer `preventDefault()`. **No se afirma sobre su URL**: el reporte se
    // sirve con `Content-Disposition: attachment`, así que el navegador lo descarga y la pestaña
    // se queda en `about:blank`. Es el comportamiento correcto y no dice nada de este cambio.
    const nueva = page.context().waitForEvent("page", { timeout: 30_000 });
    await enlace.click({ modifiers: ["ControlOrMeta"] });
    const pestana = await nueva;

    // Y el componente NO se activó: el clic no era suyo.
    await expect(page.getByRole("link", { name: /Generando PDF/i })).toHaveCount(0);
    await expect(page.locator("#avisos-descarga").getByRole("status")).toHaveCount(0);
    await pestana.close();
  });

  test("el reporte en PDF se ofrece y se descarga de verdad", async ({ page, request }) => {
    const cuerpo = await abrir(page, "/inversion");
    test.skip(!cuerpo.disponible, "sin ejercicio publicado");

    const boton = page.getByRole("link", { name: /Reporte \(PDF\)/i });
    await expect(boton).toBeVisible();

    // El enlace tiene que arrastrar el ejercicio y la vista del mapa: es lo que hace que el
    // documento sea reproducible desde la misma URL con la que se pidió.
    const url = await boton.getAttribute("href");
    expect(url).toContain("/inversion/reporte.pdf");
    expect(url).toContain("nivel=");
    expect(url).toContain("metrica=");

    // Se comprueba la RESPUESTA, no el visor de PDF del navegador: lo que puede romperse es la
    // generación en el servidor, y el visor sería una dependencia ajena al fallo.
    const respuesta = await request.get(`${url}&sin_mapa=1`);
    expect(respuesta.status()).toBe(200);
    expect(respuesta.headers()["content-type"]).toContain("application/pdf");
    expect((await respuesta.body()).subarray(0, 4).toString()).toBe("%PDF");
  });

  test("la sección sigue anunciada en el menú", async ({ page }) => {
    await irEsperando(page, "/", "/api/sitio/");
    // En móvil la navegación vive detrás del botón de hamburguesa.
    await abrirMenu(page);

    // `:visible` porque el enlace existe dos veces —nav de escritorio y panel móvil— y solo una
    // de las dos se muestra según el ancho. Sin esto, `.first()` cae siempre en la de escritorio.
    await expect(page.locator('a[href="/inversion"]:visible').first()).toBeVisible();
  });
});
