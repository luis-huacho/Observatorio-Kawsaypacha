"""Las metas Open Graph que el servidor inyecta en el HTML de la SPA.

**Por qué esto necesita pruebas de servidor y no de navegador.** Lo que se protege es justo lo que
un navegador NO ve: el HTML antes de que React se ejecute. WhatsApp, Facebook y LinkedIn leen eso y
nada más. Una prueba con Playwright que mirara `document.querySelector('meta[property=og:title]')`
pasaría en verde aunque las metas las pusiera JavaScript — y entonces no serviría para nada, porque
los rastreadores no lo ejecutan.

Y el segundo modo de fallo, más callado: que la inyección **rompa el HTML** y la SPA deje de
arrancar. Por eso varias pruebas comprueban que los `<script>` del bundle siguen ahí.
"""
import datetime

from django.test import Client

import pytest

pytestmark = pytest.mark.django_db

#: Un `index.html` con la misma forma que el de Vite: un bundle con hash y un `<title>` genérico.
INDEX = """<!doctype html>
<html lang="es-PE">
  <head>
    <meta charset="UTF-8" />
    <meta name="description" content="Descripción genérica del sitio." />
    <title>Observatorio Kallpachakuy — GRD y ACC en Cusco</title>
  </head>
  <body><div id="root"></div>
    <script type="module" src="/assets/index-a1b2c3d4.js"></script>
  </body>
</html>
"""


@pytest.fixture(autouse=True)
def spa(settings, tmp_path):
    """Un `dist/` de mentira, porque en desarrollo no existe: la SPA la sirve Vite."""
    (tmp_path / "index.html").write_text(INDEX, encoding="utf-8")
    settings.SPA_DIST_DIR = tmp_path
    settings.SITE_URL = "https://observatorio.example.pe"
    # El módulo cachea el index por `mtime`; se limpia para no arrastrar el de otra prueba.
    from apps.sitio import vistas_html

    vistas_html.RAIZ_SPA = tmp_path
    vistas_html._cache = None
    yield


@pytest.fixture
def cliente():
    return Client(headers={"host": "localhost"})


@pytest.fixture
def noticia():
    from apps.contenidos.models import Noticia

    return Noticia.objects.create(
        slug="huaicos-en-quispicanchi",
        titulo="Huaicos en Quispicanchi dejan viviendas afectadas",
        bajada="Las lluvias del fin de semana activaron quebradas en tres distritos.",
        fecha=datetime.date(2026, 3, 15),
        estado="publicado",
    )


def _metas(html: str) -> dict:
    import re

    encontrado = re.findall(
        r'<meta (?:property|name)="([\w:]+)" content="([^"]*)"', html
    )
    return dict(encontrado)


# --- Lo que ve un rastreador ------------------------------------------------


def test_una_noticia_se_comparte_con_su_titulo_y_su_bajada(cliente, noticia):
    respuesta = cliente.get(f"/noticias/{noticia.slug}")
    html = respuesta.content.decode()
    metas = _metas(html)

    assert respuesta.status_code == 200
    assert metas["og:title"] == noticia.titulo
    assert metas["og:description"] == noticia.bajada
    assert metas["og:type"] == "article"
    assert metas["twitter:card"] == "summary_large_image"
    assert f"<title>{noticia.titulo} | Observatorio Kallpachakuy</title>" in html


def test_el_canonical_apunta_a_la_url_publica(cliente, noticia):
    """Con el dominio de la SPA, no con el del API: son distintos (ADR-A14)."""
    html = cliente.get(f"/noticias/{noticia.slug}").content.decode()

    esperado = f"https://observatorio.example.pe/noticias/{noticia.slug}"
    assert f'<link rel="canonical" href="{esperado}" />' in html
    assert _metas(html)["og:url"] == esperado


def test_sin_portada_propia_se_comparte_una_imagen_que_los_rastreadores_entienden(cliente, noticia):
    """Las ilustraciones por defecto del sitio son SVG, y ni Facebook ni WhatsApp los renderizan."""
    imagen = _metas(cliente.get(f"/noticias/{noticia.slug}").content.decode())["og:image"]

    assert not imagen.endswith(".svg")
    assert imagen.startswith("http")


def test_el_titulo_generico_no_se_queda_duplicado(cliente, noticia):
    """Dos `<title>` no son un error de sintaxis, pero cada rastreador elige uno distinto."""
    html = cliente.get(f"/noticias/{noticia.slug}").content.decode()

    assert html.count("<title>") == 1
    assert "Descripción genérica del sitio." not in html


def test_la_spa_sigue_arrancando(cliente, noticia):
    """El modo de fallo callado: inyectar mal y dejar el sitio en blanco."""
    html = cliente.get(f"/noticias/{noticia.slug}").content.decode()

    assert '<script type="module" src="/assets/index-a1b2c3d4.js"></script>' in html
    assert '<div id="root"></div>' in html
    assert html.count("</head>") == 1


def test_una_norma_encabeza_con_su_numero(cliente):
    """El título de una norma llega a 300 caracteres; el número la identifica en 16."""
    from apps.normativa.models import Norma

    Norma.objects.create(
        slug="ds-048-2011-pcm", titulo="Reglamento de la Ley 29664, Ley del SINAGERD",
        numero="DS 048-2011-PCM", tipo="DS", ambito="nacional",
        fecha=datetime.date(2011, 5, 26), resumen="Aprueba el reglamento.", estado="publicado",
    )

    metas = _metas(cliente.get("/normativa/ds-048-2011-pcm").content.decode())

    assert metas["og:title"].startswith("DS 048-2011-PCM — ")


def test_un_titulo_larguisimo_se_recorta_por_palabras(cliente):
    """Los rastreadores cortan por su cuenta, pero a mitad de palabra."""
    from apps.normativa.models import Norma

    Norma.objects.create(
        slug="larga", titulo="Decreto Supremo que declara el Estado de Emergencia " * 5,
        tipo="DS", ambito="nacional", fecha=datetime.date(2026, 1, 1),
        resumen="x", estado="publicado",
    )

    titulo = _metas(cliente.get("/normativa/larga").content.decode())["og:title"]

    assert len(titulo) <= 111
    assert titulo.endswith("…")
    assert not titulo[:-1].endswith(" ")


def test_una_ficha_en_borrador_no_expone_su_contenido(cliente):
    """El estado editorial manda también aquí: un borrador compartido filtraría lo no publicado."""
    from apps.contenidos.models import Noticia

    Noticia.objects.create(slug="secreta", titulo="Todavía no", bajada="No publicar",
                           fecha=datetime.date.today(), estado="borrador")

    metas = _metas(cliente.get("/noticias/secreta").content.decode())

    assert "Todavía no" not in metas["og:title"]
    assert metas["og:title"] == "Observatorio Kallpachakuy — GRD y ACC en Cusco"


def test_una_ficha_inexistente_devuelve_la_spa_y_no_un_404(cliente):
    """El «no encontrado» lo pinta el router de React; un 404 aquí lo sustituiría por el de nginx."""
    respuesta = cliente.get("/noticias/no-existe")

    assert respuesta.status_code == 200
    assert '<div id="root"></div>' in respuesta.content.decode()


def test_el_html_no_se_puede_inyectar_desde_el_contenido(cliente):
    """El título lo escribe un editor, y acaba dentro de un atributo HTML."""
    from apps.contenidos.models import Noticia

    Noticia.objects.create(
        slug="traviesa", titulo='Comillas " y <script>alert(1)</script>',
        bajada="x", fecha=datetime.date.today(), estado="publicado",
    )

    html = cliente.get("/noticias/traviesa").content.decode()
    metas = _metas(html)

    # Las etiquetas se eliminan, no se escapan: una `og:description` no lleva marcado, y dejarla
    # con `&lt;script&gt;` dentro solo ensuciaría la previsualización.
    assert "alert(1)" in metas["og:title"] and "<script" not in metas["og:title"]
    # La comilla sí se escapa, que es lo que impide salirse del atributo.
    assert "&quot;" in html
    assert html.count("</head>") == 1, "el head sigue siendo válido"


# --- Sitemap ----------------------------------------------------------------


def test_el_sitemap_lista_las_fichas_publicadas(cliente, noticia):
    respuesta = cliente.get("/sitemap.xml")
    xml = respuesta.content.decode()

    assert respuesta["Content-Type"].startswith("application/xml")
    assert f"<loc>https://observatorio.example.pe/noticias/{noticia.slug}</loc>" in xml
    assert "<loc>https://observatorio.example.pe/normativa</loc>" in xml


def test_el_sitemap_no_anuncia_lo_que_esta_fuera_del_menu(cliente):
    """`/comparar` sigue viva pero fuera del menú (ADR-P2): anunciarla la reactivaría de tapadillo."""
    xml = cliente.get("/sitemap.xml").content.decode()

    assert "/comparar" not in xml
    assert "/prioridades" not in xml


def test_el_sitemap_no_lista_borradores(cliente):
    from apps.contenidos.models import Noticia

    Noticia.objects.create(slug="secreta", titulo="Todavía no", bajada="",
                           fecha=datetime.date.today(), estado="borrador")

    assert "/noticias/secreta" not in cliente.get("/sitemap.xml").content.decode()
