"""Ayuda memoria PDF (spec 02).

Es el entregable que se lleva impreso a una mesa técnica, así que las dos cosas que se prueban son
que **se genera** y que **dice lo mismo que la pantalla desde la que se pidió**. Un PDF que
contradice al sitio es peor que no tener PDF: viaja en papel, sin fecha ni contexto, y nadie puede
comprobarlo en la reunión.

Con `sin_mapa=1` para no depender de Chromium en cada corrida; la captura del mapa se prueba
aparte, marcada `lento`.
"""
import pytest

pytestmark = pytest.mark.django_db


def _pdf(api, ubigeo, extra=""):
    respuesta = api.get(f"/api/distritos/{ubigeo}/ayuda-memoria.pdf?sin_mapa=1{extra}")
    contenido = (
        b"".join(respuesta.streaming_content)
        if hasattr(respuesta, "streaming_content")
        else respuesta.content
    )
    return respuesta, contenido


def test_se_genera_un_pdf_de_verdad(api, datos_muestra, sin_throttling):
    respuesta, contenido = _pdf(api, "080101")

    assert respuesta.status_code == 200
    assert respuesta["Content-Type"] == "application/pdf"
    assert contenido.startswith(b"%PDF")
    assert len(contenido) > 5000


def test_el_nombre_del_archivo_identifica_el_distrito(api, datos_muestra, sin_throttling):
    """Quien descarga varios necesita distinguirlos en su carpeta de descargas."""
    respuesta, _ = _pdf(api, "080101")

    assert "attachment" in respuesta["Content-Disposition"]
    assert "cusco" in respuesta["Content-Disposition"].lower()


def test_un_distrito_inexistente_es_404(api, datos_muestra, sin_throttling):
    respuesta, _ = _pdf(api, "089999")

    assert respuesta.status_code == 404


def test_el_pdf_se_genera_para_un_distrito_sin_emergencias(api, datos_muestra, sin_throttling):
    """ACOPIA no tiene datos de emergencias: el documento sale igual, diciéndolo.

    Si el PDF fallara por eso, los distritos con vacíos de información —justo los que más
    necesitan que alguien los mire— serían los únicos sin ayuda memoria.
    """
    from apps.territorio.models import Distrito

    acopia = Distrito.objects.get(nombre__iexact="ACOPIA")
    respuesta, contenido = _pdf(api, acopia.ubigeo)

    assert respuesta.status_code == 200
    assert contenido.startswith(b"%PDF")


def test_el_pdf_lee_de_las_mismas_consultas_que_el_api(api, datos_muestra, sin_throttling):
    """El PDF y la pantalla comparten `peligros.consultas`, no dos consultas parecidas.

    Es la única forma de garantizar que coinciden: dos implementaciones «equivalentes» divergen
    en cuanto una se toca.
    """
    from apps.informes import ayuda_memoria
    from apps.peligros import consultas
    from apps.territorio.models import Distrito

    distrito = Distrito.objects.get(ubigeo="080101")
    datos = ayuda_memoria.reunir_datos(distrito)
    del_api = api.get("/api/peligros/resumen/?distrito=080101").json()

    assert datos["total_ambito"] == del_api["total_ccpp"]
    # El PDF cuenta **centros poblados**, la misma unidad que la tabla de la que se descarga.
    por_nivel = {f["nivel"]: f["conteo"] for f in datos["niveles"]}
    assert por_nivel == {
        int(nivel): conteo for nivel, conteo in del_api["por_ccpp"]["niveles"].items()
    }
    assert datos["sin_dato"] == del_api["por_ccpp"]["sin_clasificar"]
    assert datos["frecuencia"] == consultas.frecuencia(distrito)


def test_los_filtros_del_visor_llegan_al_pdf(api, datos_muestra, sin_throttling):
    """Se descarga desde `/peligros` con unos filtros puestos: el PDF tiene que respetarlos.

    Un documento que ignora el filtro con el que se pidió es un documento que dice otra cosa que
    la pantalla, y quien lo imprimió no tiene forma de notarlo.
    """
    from apps.informes import ayuda_memoria
    from apps.territorio.models import Distrito

    distrito = Distrito.objects.get(ubigeo="080101")
    completo = ayuda_memoria.reunir_datos(distrito)
    filtrado = ayuda_memoria.reunir_datos(distrito, peligros=["sismo"], niveles=[4])
    # «Friaje» no está en las hojas de la muestra: el filtro tiene que dejar la tabla vacía, no
    # ignorarse y devolver todo.
    sin_coincidencias = ayuda_memoria.reunir_datos(distrito, peligros=["friaje"])
    # Selección múltiple y no contigua, que es lo que el umbral de antes no podía expresar.
    dos_peligros = ayuda_memoria.reunir_datos(
        distrito, peligros=["sismo", "inundacion"], niveles=[1, 4]
    )

    assert filtrado["total_clasificados"] <= completo["total_clasificados"]
    assert sin_coincidencias["total_clasificados"] == 0
    assert sin_coincidencias["total_ambito"] == completo["total_ambito"]
    assert filtrado["nombre_peligro"] == "Sismo"
    # Los filtros aplicados se imprimen en el documento: si no, el papel no dice de qué habla.
    # Y con selección múltiple tienen que nombrarse todos: un pie que dice «nivel mínimo 1»
    # donde se pidió «Muy alto y Bajo» describe un recorte que no es el que se hizo.
    assert "Sismo" in filtrado["filtros"]
    assert "muy alto" in filtrado["filtros"]
    assert filtrado["filtros"] != completo["filtros"]
    assert "Sismo" in dos_peligros["filtros"] and "Inundación" in dos_peligros["filtros"]
    assert "muy alto" in dos_peligros["filtros"] and "bajo" in dos_peligros["filtros"]
    # Los intermedios no se cuelan: es la selección literal, no un rango desde el mínimo.
    assert dos_peligros["niveles_pedidos"] == [4, 1]


def test_la_ayuda_memoria_no_publica_la_altitud(api, datos_muestra, sin_throttling):
    """Se quitó de la ficha, del Excel y del PDF: la altitud no aporta a una mesa de incidencia.

    El dato sigue en la base —lo trae el padrón y es real, a diferencia de la población
    (ADR-A19)—, así que lo que se comprueba es que **no se publica**, no que no exista.
    """
    from apps.informes import ayuda_memoria
    from apps.territorio.models import Distrito

    datos = ayuda_memoria.reunir_datos(Distrito.objects.get(ubigeo="080101"))

    assert datos["filas"], "la muestra debería traer centros poblados clasificados"
    assert all("altitud" not in fila for fila in datos["filas"])


def test_el_visor_del_mapa_pide_los_datos_a_su_propio_origen(client, settings):
    """La prueba que faltaba, y sin la que el PDF salía sin mapa en producción.

    El navegador headless corre **dentro del contenedor** y abre esta página por la URL interna
    (`RENDER_MAPA_BASE_URL`). Sus `fetch` tienen que ir al mismo origen, así que las URL del
    contexto son **relativas**. Antes se construían con `BACKEND_URL` —la URL con la que el
    visitante alcanza el backend— y en producción local eso era `http://localhost`, el puerto 80
    del propio contenedor, donde no escucha nadie: «Failed to fetch», y el documento salía sin
    mapa. En desarrollo funcionaba por casualidad, porque allí `BACKEND_URL` sí es el puerto de
    este contenedor.

    Por eso `BACKEND_URL` se pone aquí a un host inalcanzable: si vuelve a colarse en estas URL,
    esta prueba falla en vez de fallar el PDF de alguien.
    """
    settings.BACKEND_URL = "http://no-existe.invalid:9999"

    respuesta = client.get(
        "/api/informes/visor-mapa/",
        {"distrito": "080101", "peligros": "sismo,inundacion", "niveles": "3,4"},
    )
    contexto = respuesta.context_data

    assert respuesta.status_code == 200
    for clave in ("url_geojson", "url_capas"):
        assert contexto[clave].startswith("/api/"), contexto[clave]
        assert "no-existe.invalid" not in contexto[clave]
    # Y los filtros viajan, o el mapa del documento no coincidiría con la pantalla que lo pidió.
    assert "distrito=080101" in contexto["url_geojson"]
    assert "peligros=sismo,inundacion" in contexto["url_geojson"]
    assert "niveles=3,4" in contexto["url_geojson"]


def _chromium_disponible() -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    try:
        with sync_playwright() as p:
            p.chromium.launch(args=["--no-sandbox"]).close()
        return True
    except Exception:  # noqa: BLE001 — sin navegador la prueba se salta, no falla
        return False


@pytest.mark.lento
def test_con_el_mapa_tambien_sale(api, datos_muestra, sin_throttling):
    """El camino completo: con Chromium disponible, el PDF **tiene que traer el mapa**.

    La primera versión de esta prueba solo comprobaba que el PDF se generara, y toleraba que
    viniera sin mapa —«degradación prevista»—. Con eso, el documento salió meses sin mapa en
    producción local sin que la suite dijera nada: el fallo se veía como el camino degradado. Ahora
    la degradación se comprueba en su propia prueba (`sin_mapa=1`, arriba) y aquí se exige el mapa.

    Si el navegador no está en la imagen, se salta: es una limitación del entorno, no del código.
    """
    if not _chromium_disponible():
        pytest.skip("Chromium no está disponible en esta imagen")

    respuesta = api.get("/api/distritos/080101/ayuda-memoria.pdf")
    contenido = (
        b"".join(respuesta.streaming_content)
        if hasattr(respuesta, "streaming_content")
        else respuesta.content
    )

    assert respuesta.status_code == 200
    assert contenido.startswith(b"%PDF")
    # El mapa es la única imagen rasterizada del documento —el logotipo es vectorial—, así que
    # contarlas es la forma de saber si el mapa llegó.
    assert contenido.count(b"/Subtype /Image") >= 1, "el PDF salió sin el mapa"


@pytest.mark.lento
def test_sin_mapa_el_pdf_no_lleva_ninguna_imagen(api, datos_muestra, sin_throttling):
    """La contraparte de la prueba anterior: sin ella, contar imágenes no significaría nada."""
    _, contenido = _pdf(api, "080101")

    assert contenido.count(b"/Subtype /Image") == 0


# --- Reporte de Inversión (PP 0068) ---------------------------------------------------------
#
# Mismo criterio que la ayuda memoria: lo que se prueba no es que salga un PDF, sino que diga lo
# mismo que la pantalla. Aquí hay además una obligación propia —ADR-D6—: el documento tiene que
# declarar el dinero que su mapa no puede pintar, porque en papel no hay pantalla al lado que lo
# compense.


@pytest.fixture
def inversion_publicada(importar, datos_muestra):
    from apps.datasets.models import DatasetUpload
    from apps.inversion.models import Ejercicio
    from tests.rutas import MUESTRA_INVERSION, MUESTRA_INVERSION_INSTITUCIONAL

    importar(tipo=DatasetUpload.Tipo.INVERSION, archivo=MUESTRA_INVERSION)
    importar(tipo=DatasetUpload.Tipo.INVERSION, archivo=MUESTRA_INVERSION_INSTITUCIONAL)
    Ejercicio.objects.update(visible=True)


def _reporte(api, extra=""):
    respuesta = api.get(f"/api/inversion/reporte.pdf?sin_mapa=1{extra}")
    contenido = (
        b"".join(respuesta.streaming_content)
        if hasattr(respuesta, "streaming_content")
        else respuesta.content
    )
    return respuesta, contenido


def test_el_reporte_de_inversion_se_genera(api, inversion_publicada, sin_throttling):
    respuesta, contenido = _reporte(api)

    assert respuesta.status_code == 200
    assert respuesta["Content-Type"] == "application/pdf"
    assert contenido.startswith(b"%PDF")
    assert "attachment" in respuesta["Content-Disposition"]
    assert "reporte-inversion-pp0068" in respuesta["Content-Disposition"]


def test_el_reporte_lee_de_las_mismas_consultas_que_el_api(api, inversion_publicada):
    """El papel y la pantalla comparten `inversion.consultas`, no dos consultas parecidas.

    Es la única forma de garantizar que coinciden: dos implementaciones «equivalentes» divergen
    en cuanto una se toca, y un documento impreso no se puede comprobar en mitad de una reunión.
    """
    from apps.informes import reporte_inversion
    from apps.inversion import consultas

    datos = reporte_inversion.reunir_datos()
    ejercicio = consultas.ejercicio_para()

    assert datos["agregados"] == consultas.agregados(ejercicio)
    assert datos["procesos"] == consultas.procesos(ejercicio)["procesos"]
    assert [f["codigo"] for f in datos["filas"]] == [
        f["codigo"] for f in consultas.por_entidad(consultas.listado(ejercicio))
    ]


def test_el_total_de_la_tabla_es_el_agregado_del_ambito(api, inversion_publicada):
    """La fila de total sale de `agregados`, y la tabla de `listado`: son dos caminos distintos
    hasta la misma cifra. Si se separaran, el documento se contradiría a sí mismo en la misma
    página y nadie lo notaría sin sumar 116 filas a mano."""
    from apps.informes import reporte_inversion

    datos = reporte_inversion.reunir_datos()

    assert datos["agregados"]["pim"] == pytest.approx(sum(f["pim"] for f in datos["filas"]))
    assert datos["agregados"]["devengado"] == pytest.approx(
        sum(f["devengado"] for f in datos["filas"])
    )


def test_el_reporte_declara_el_dinero_que_su_mapa_no_pinta(api, inversion_publicada):
    """ADR-D6 llevado al papel.

    En pantalla, quien mira el mapa tiene el pie debajo; en un PDF que circula por correo, si la
    declaración no viaja dentro del documento no viaja en absoluto.
    """
    from apps.informes import reporte_inversion

    datos = reporte_inversion.reunir_datos(nivel="distrital")

    assert datos["mapa"]["no_ubicado"]["entidades"] > 0
    assert datos["mapa"]["no_ubicado"]["motivo"]

    _, contenido = _reporte(api, "&nivel=distrital")
    assert contenido.startswith(b"%PDF")


def test_el_reporte_avisa_del_corte_parcial(api, inversion_publicada):
    """Un % de ejecución de medio año contra un PIM anual no es media ejecución perdida."""
    from apps.informes import reporte_inversion

    parcial = reporte_inversion.reunir_datos(anio=2026)
    cerrado = reporte_inversion.reunir_datos(anio=2025)

    assert parcial["es_parcial"] is True
    assert parcial["corte"] == "2026-06"
    assert cerrado["es_parcial"] is False


def test_el_reporte_llama_en_curso_solo_a_lo_que_lo_esta(api, inversion_publicada):
    """El aviso del PDF decía «está en curso» sobre `es_parcial` a secas.

    Es cierto hoy —el único parcial es el del año corriente— y falso el día que se cargue un
    corte a junio de un año ya pasado: seguiría siendo parcial sin estar en curso, y el
    documento afirmaría en negrita algo que no es. Se renderiza el HTML y no el PDF porque lo
    que se comprueba es la frase, y WeasyPrint tarda segundos en cada corrida.
    """
    from django.template.loader import render_to_string

    from apps.informes import reporte_inversion
    from apps.inversion.models import Ejercicio

    contexto = reporte_inversion.reunir_datos(anio=2026)
    assert contexto["en_curso"] is True
    assert contexto["corte_legible"] == "junio de 2026"
    assert "está en curso" in render_to_string("informes/reporte_inversion.html", contexto)

    Ejercicio.objects.filter(anio=2025).update(es_parcial=True, corte="2025-06")
    pasado = reporte_inversion.reunir_datos(anio=2025)
    assert pasado["es_parcial"] is True
    assert pasado["en_curso"] is False

    html = render_to_string("informes/reporte_inversion.html", pasado)
    assert "está en curso" not in html
    # Sigue advirtiendo de que el dato es parcial: lo que cambia es cómo se llama, no si se avisa.
    assert "junio de 2025" in html


def test_sin_ejercicio_publicado_el_reporte_explica_el_vacio_y_no_es_404(
    api, inversion_publicada, sin_throttling
):
    """Un PDF vacío se leería como «no hay inversión pública en gestión del riesgo».

    Es el mismo criterio con el que el Excel trae su hoja «Sin datos» en vez de un libro en
    blanco.
    """
    from apps.inversion.models import Ejercicio

    Ejercicio.objects.update(visible=False)

    respuesta, contenido = _reporte(api)

    assert respuesta.status_code == 200
    assert contenido.startswith(b"%PDF")


def test_acotar_por_provincia_recorta_la_tabla_y_el_total_a_la_vez(api, inversion_publicada):
    """Recortar uno sin el otro daría un documento con un total que no es de lo que enseña."""
    from apps.informes import reporte_inversion

    region = reporte_inversion.reunir_datos()
    cusco = reporte_inversion.reunir_datos(provincia="CUSCO")

    assert len(cusco["filas"]) <= len(region["filas"])
    assert cusco["agregados"]["pim"] == pytest.approx(sum(f["pim"] for f in cusco["filas"]))
    assert cusco["provincia"] == "CUSCO"


def test_la_leyenda_del_mapa_usa_la_escala_compartida(api, inversion_publicada):
    """La leyenda y el mapa leen la rampa del mismo módulo (`informes/escalas.py`).

    Si cada uno tuviera la suya, el documento podría pintar un tramo de un color y describirlo
    de otro sin que nada fallara.
    """
    from apps.informes import escalas, reporte_inversion

    dinero = reporte_inversion.reunir_datos(metrica="pim")
    ejecucion = reporte_inversion.reunir_datos(metrica="pct_ejecucion")

    assert [t["color"] for t in dinero["leyenda"]] == escalas.RAMPA_DINERO
    assert [t["color"] for t in ejecucion["leyenda"]] == escalas.RAMPA_EJECUCION
    # Los rangos van en soles / en porcentaje, nunca en «bajo/alto»: el color de las métricas de
    # dinero es relativo a la vista, así que sin las cifras no se sabe de qué habla el mapa.
    assert "S/" in dinero["leyenda"][0]["etiqueta"]
    assert "%" in ejecucion["leyenda"][0]["etiqueta"]


def test_una_metrica_inventada_cae_a_la_de_por_defecto(api, inversion_publicada):
    from apps.informes import reporte_inversion

    assert reporte_inversion.reunir_datos(metrica="loquesea")["metrica"] == "pim"


@pytest.mark.lento
def test_el_reporte_con_mapa_trae_el_mapa(api, inversion_publicada, sin_throttling):
    """Con Chromium disponible, el reporte **tiene que traer** su mapa.

    Mismo aprendizaje que en la ayuda memoria: tolerar el camino degradado dejó el documento
    meses sin mapa en producción sin que la suite dijera nada.
    """
    if not _chromium_disponible():
        pytest.skip("Chromium no está disponible en esta imagen")

    respuesta = api.get("/api/inversion/reporte.pdf")
    contenido = (
        b"".join(respuesta.streaming_content)
        if hasattr(respuesta, "streaming_content")
        else respuesta.content
    )

    assert respuesta.status_code == 200
    assert contenido.count(b"/Subtype /Image") >= 1, "el reporte salió sin el mapa"


@pytest.mark.lento
def test_sin_mapa_el_reporte_no_lleva_ninguna_imagen(api, inversion_publicada, sin_throttling):
    """La contraparte de la anterior, y además la prueba de que **las gráficas son vectoriales**:
    si se generaran como PNG, esta cuenta no daría cero y la de arriba no significaría nada."""
    _, contenido = _reporte(api)

    assert contenido.count(b"/Subtype /Image") == 0


# --- Los visores que captura el navegador ---------------------------------------------------


def test_el_visor_de_peligros_conserva_todos_sus_filtros(api, datos_muestra):
    """Django escapa `&` como `&amp;` dentro de `{{ … }}`, y una URL en un `fetch` de JavaScript
    no lleva entidades HTML: del segundo parámetro en adelante se perdían todos.

    El daño era silencioso y grave: el PDF decía «Peligros: Sismo · Niveles: muy alto» en su
    línea de filtros y **el mapa de al lado mostraba el distrito entero**. Ningún error, ningún
    aviso, y un documento que se contradice a sí mismo en la misma página.
    """
    html = api.get(
        "/api/informes/visor-mapa/?distrito=080101&peligros=sismo&niveles=4"
    ).content.decode()

    assert "&amp;" not in html
    assert "peligros=sismo" in html
    assert "niveles=4" in html


def test_el_visor_de_inversion_conserva_el_nivel(api, inversion_publicada):
    """El mismo fallo, aquí con consecuencia visible: sin `nivel`, el API cae a `distrital` y
    devuelve ubigeos de seis dígitos que **ningún polígono provincial puede casar**. El mapa
    salía en blanco, con sus contornos dibujados y su leyenda correcta al lado."""
    html = api.get(
        "/api/informes/visor-mapa-inversion/?anio=2026&ambito=municipal&nivel=provincial"
    ).content.decode()

    assert "&amp;" not in html
    assert "nivel=provincial" in html
    assert "ambito=municipal" in html


def test_los_visores_no_dejan_escapar_comillas_a_la_cadena_de_javascript(api, datos_muestra):
    """La URL se compone con parámetros de la petición, y va dentro de una cadena de JS.

    El escapado HTML que causaba el fallo anterior **también** impedía esto por accidente;
    quitarlo sin más habría abierto una inyección. Por eso la URL se arma con `urlencode` y se
    imprime con `escapejs`, no con `|safe`.
    """
    html = api.get('/api/informes/visor-mapa/?distrito=080101"+alert(1)+"').content.decode()

    assert '"+alert(1)+"' not in html
