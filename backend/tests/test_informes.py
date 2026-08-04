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
    filtrado = ayuda_memoria.reunir_datos(distrito, peligro="sismo", nivel_min=4)
    # «Friaje» no está en las hojas de la muestra: el filtro tiene que dejar la tabla vacía, no
    # ignorarse y devolver todo.
    sin_coincidencias = ayuda_memoria.reunir_datos(distrito, peligro="friaje")

    assert filtrado["total_clasificados"] <= completo["total_clasificados"]
    assert sin_coincidencias["total_clasificados"] == 0
    assert sin_coincidencias["total_ambito"] == completo["total_ambito"]
    assert filtrado["nombre_peligro"] == "Sismo"
    # Los filtros aplicados se imprimen en el documento: si no, el papel no dice de qué habla.
    assert "Sismo" in filtrado["filtros"]
    assert "Nivel mínimo: 4" in filtrado["filtros"]
    assert filtrado["filtros"] != completo["filtros"]


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
        "/api/informes/visor-mapa/", {"distrito": "080101", "peligro": "sismo", "nivel_min": "3"}
    )
    contexto = respuesta.context_data

    assert respuesta.status_code == 200
    for clave in ("url_geojson", "url_capas"):
        assert contexto[clave].startswith("/api/"), contexto[clave]
        assert "no-existe.invalid" not in contexto[clave]
    # Y los filtros viajan, o el mapa del documento no coincidiría con la pantalla que lo pidió.
    assert "distrito=080101" in contexto["url_geojson"]
    assert "peligro=sismo" in contexto["url_geojson"]
    assert "nivel_min=3" in contexto["url_geojson"]


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
