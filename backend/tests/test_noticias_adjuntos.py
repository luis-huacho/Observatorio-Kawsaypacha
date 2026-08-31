"""Enlaces y archivos adjuntos de una noticia.

Dos colecciones hijas de `Noticia`, administradas con inlines y servidas anidadas en el detalle.
Lo que se protege aquí son los fallos que **no dan error**: una URL relativa que el navegador
resuelve contra el dominio equivocado, una clave que desaparece del JSON en vez de venir vacía, un
orden que Postgres decide por su cuenta cuando el `orden` empata, y un adjunto con extensión
ejecutable servido desde el mismo origen que la sesión del admin.
"""
import datetime

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

pytestmark = pytest.mark.django_db


def _noticia(slug="nota-con-anexos", **extra):
    from apps.contenidos.models import Noticia

    return Noticia.objects.create(
        slug=slug,
        titulo=slug.replace("-", " ").capitalize(),
        tipo=Noticia.Tipo.NOTICIA,
        fecha=datetime.date(2026, 8, 31),
        bajada="…",
        estado=Noticia.Estado.PUBLICADO,
        **extra,
    )


def _archivo(nombre="informe.pdf", contenido=b"%PDF-1.4 una linea"):
    return SimpleUploadedFile(nombre, contenido, content_type="application/pdf")


# --- El contrato del API ----------------------------------------------------


def test_el_detalle_trae_enlaces_y_archivos_y_el_listado_no(api):
    """El listado no los pinta, así que traerlos sería una consulta por tarjeta para nada."""
    from apps.contenidos.models import NoticiaArchivo, NoticiaEnlace

    noticia = _noticia()
    NoticiaEnlace.objects.create(noticia=noticia, titulo="Nota de PREDES", url="https://predes.org.pe/x")
    NoticiaArchivo.objects.create(noticia=noticia, titulo="Informe final", archivo=_archivo())

    detalle = api.get(f"/api/noticias/{noticia.slug}/").json()
    assert [e["titulo"] for e in detalle["enlaces"]] == ["Nota de PREDES"]
    assert [a["titulo"] for a in detalle["archivos"]] == ["Informe final"]

    fila = api.get("/api/noticias/").json()["results"][0]
    assert "enlaces" not in fila and "archivos" not in fila


def test_una_noticia_sin_anexos_devuelve_listas_vacias_no_null(api):
    """La clave ausente o en `null` revienta el `.map()` del cliente; `[]` se pinta como nada."""
    detalle = api.get(f"/api/noticias/{_noticia().slug}/").json()

    assert detalle["enlaces"] == []
    assert detalle["archivos"] == []


def test_la_url_del_adjunto_es_ABSOLUTA(api, settings):
    """La SPA vive en otro dominio (ADR-A14): una URL relativa apuntaría a la propia SPA.

    El fallo es mudo — el enlace existe, se pulsa y la SPA responde su `index.html` con un 200.
    """
    from apps.contenidos.models import NoticiaArchivo

    settings.BACKEND_URL = "https://obs.predes.org.pe"
    noticia = _noticia()
    NoticiaArchivo.objects.create(noticia=noticia, titulo="Informe", archivo=_archivo())

    url = api.get(f"/api/noticias/{noticia.slug}/").json()["archivos"][0]["archivo"]

    assert url.startswith("https://obs.predes.org.pe/")


def test_el_adjunto_declara_su_extension_y_su_peso(api):
    """La ficha pinta «PDF · 2,3 MB»; los dos datos salen del servidor, no del nombre en cliente."""
    from apps.contenidos.models import NoticiaArchivo

    noticia = _noticia()
    NoticiaArchivo.objects.create(
        noticia=noticia, titulo="Informe", archivo=_archivo(contenido=b"x" * 2048)
    )

    adjunto = api.get(f"/api/noticias/{noticia.slug}/").json()["archivos"][0]

    assert adjunto["extension"] == "pdf"
    assert adjunto["peso_bytes"] == 2048


# --- El orden ---------------------------------------------------------------


@pytest.mark.parametrize("modelo,extra", [("NoticiaEnlace", {"url": "https://x.pe"}), ("NoticiaArchivo", {})])
def test_el_orden_es_TOTAL_y_no_lo_decide_postgres(api, modelo, extra):
    """`orden` tiene `default=0`, así que el empate es la norma y no la excepción.

    Sin el remate por `id` el desempate lo elige el planificador, y dos peticiones seguidas
    pueden devolver los anexos en orden distinto sin que nada falle.
    """
    from apps.contenidos import models as m

    Modelo = getattr(m, modelo)
    noticia = _noticia()
    for titulo in ("primero", "segundo", "tercero"):
        campos = dict(extra)
        if modelo == "NoticiaArchivo":
            campos["archivo"] = _archivo(f"{titulo}.pdf")
        Modelo.objects.create(noticia=noticia, titulo=titulo, **campos)

    clave = "enlaces" if modelo == "NoticiaEnlace" else "archivos"
    devueltos = [x["titulo"] for x in api.get(f"/api/noticias/{noticia.slug}/").json()[clave]]

    assert devueltos == ["primero", "segundo", "tercero"]


def test_el_campo_orden_manda_sobre_el_alta(api):
    from apps.contenidos.models import NoticiaEnlace

    noticia = _noticia()
    NoticiaEnlace.objects.create(noticia=noticia, titulo="va segundo", url="https://a.pe", orden=5)
    NoticiaEnlace.objects.create(noticia=noticia, titulo="va primero", url="https://b.pe", orden=1)

    devueltos = [e["titulo"] for e in api.get(f"/api/noticias/{noticia.slug}/").json()["enlaces"]]

    assert devueltos == ["va primero", "va segundo"]


# --- El peso, guardado y no leído del disco ---------------------------------


def test_el_peso_se_calcula_al_guardar():
    """Se guarda en vez de leer `archivo.size` al serializar: un archivo borrado del disco haría
    que `.size` lanzara excepción, o sea un 500 en una página pública por un anexo perdido."""
    from apps.contenidos.models import NoticiaArchivo

    adjunto = NoticiaArchivo.objects.create(
        noticia=_noticia(), titulo="Informe", archivo=_archivo(contenido=b"x" * 1234)
    )

    assert adjunto.peso_bytes == 1234


def test_volver_a_guardar_sin_tocar_el_archivo_no_recalcula_el_peso():
    """Mismo criterio que `ImagenOptimizadaMixin`: `_committed` dice si hay contenido nuevo."""
    from apps.contenidos.models import NoticiaArchivo

    adjunto = NoticiaArchivo.objects.create(
        noticia=_noticia(), titulo="Informe", archivo=_archivo(contenido=b"x" * 99)
    )
    adjunto.titulo = "Informe final"
    adjunto.save()
    adjunto.refresh_from_db()

    assert adjunto.peso_bytes == 99


# --- El validador -----------------------------------------------------------


@pytest.mark.parametrize("nombre", ["pagina.html", "logo.svg", "instalador.exe", "script.js"])
def test_el_validador_rechaza_lo_que_se_ejecuta_en_el_origen_del_admin(nombre):
    """nginx sirve `/media/` como estático público **en el dominio del API**, que es donde vive
    la sesión del admin. Un `.svg` o un `.html` ahí es XSS almacenado, y el `nosniff` del
    `location` no lo cubre: impide adivinar el tipo, no que nginx sirva un `.html` como HTML.
    """
    from apps.core.validadores import validar_adjunto

    with pytest.raises(ValidationError):
        validar_adjunto(_archivo(nombre, b"<svg onload=alert(1)>"))


@pytest.mark.parametrize("nombre", ["informe.pdf", "datos.xlsx", "foto.JPG", "notas.txt"])
def test_el_validador_acepta_los_formatos_del_catalogo(nombre):
    """`foto.JPG` está a propósito: la extensión se compara en minúscula."""
    from apps.core.validadores import validar_adjunto

    validar_adjunto(_archivo(nombre, b"contenido"))


def test_el_validador_rechaza_por_tamano():
    """El tope va por debajo del `client_max_body_size 80M` de nginx: si el límite efectivo fuera
    el de nginx, pasarse daría un 413 crudo en vez de un error de campo con su mensaje."""
    from apps.core import validadores

    grande = _archivo("informe.pdf", b"x" * (validadores.TAMANO_MAXIMO_ADJUNTO_MB * 1024 * 1024 + 1))

    with pytest.raises(ValidationError):
        validadores.validar_adjunto(grande)


def test_el_modelo_aplica_el_validador():
    """El validador está en el campo, así que `full_clean()` lo aplica venga de donde venga."""
    from apps.contenidos.models import NoticiaArchivo

    adjunto = NoticiaArchivo(noticia=_noticia(), titulo="Logo", archivo=_archivo("logo.svg"))

    with pytest.raises(ValidationError):
        adjunto.full_clean()


# --- Integridad y coste -----------------------------------------------------


def test_borrar_la_noticia_borra_sus_anexos():
    from apps.contenidos.models import NoticiaArchivo, NoticiaEnlace

    noticia = _noticia()
    NoticiaEnlace.objects.create(noticia=noticia, titulo="x", url="https://x.pe")
    NoticiaArchivo.objects.create(noticia=noticia, titulo="y", archivo=_archivo())

    noticia.delete()

    assert not NoticiaEnlace.objects.exists()
    assert not NoticiaArchivo.objects.exists()


def test_el_detalle_no_crece_en_consultas_con_mas_anexos(api, django_assert_num_queries):
    """Sin `prefetch_related` cada anexo sería su propia consulta."""
    from apps.contenidos.models import NoticiaArchivo, NoticiaEnlace

    noticia = _noticia()
    for i in range(6):
        NoticiaEnlace.objects.create(noticia=noticia, titulo=f"e{i}", url=f"https://x.pe/{i}")
        NoticiaArchivo.objects.create(noticia=noticia, titulo=f"a{i}", archivo=_archivo(f"a{i}.pdf"))

    with django_assert_num_queries(3):  # noticia + enlaces + archivos
        api.get(f"/api/noticias/{noticia.slug}/")


def test_la_IA_no_redacta_los_anexos():
    """Contrato: «los enlaces y los documentos no tienen de dónde salir —una ficha no trae URL— e
    inventarlos es la alucinación clásica» (spec 00). Hoy se cumple por construcción, porque
    `CAMPOS_REDACTADOS` son campos escalares; esto lo fija por si mañana alguien lo amplía."""
    from apps.contenidos import redaccion
    from apps.contenidos.tasks import CAMPOS_REDACTADOS

    assert {"enlaces", "archivos"}.isdisjoint(CAMPOS_REDACTADOS)

    # Y por el otro lado: el esquema es `json_schema` estricto, así que si las claves no están
    # declaradas el modelo no puede devolverlas. El olvido probable es al revés — alguien las
    # añade «para que la IA rellene también los enlaces» y nada avisa.
    propiedades = redaccion._esquema()["schema"]["properties"]
    assert {"enlaces", "archivos"}.isdisjoint(propiedades)


def test_la_ruta_del_adjunto_no_se_puede_adivinar():
    """nginx sirve `/media/` como estático público: sin un segmento aleatorio, la URL del anexo de
    un borrador se deduce del título y el informe se filtra antes de publicarse.

    No es control de acceso —quien tenga el enlace entra siempre— pero cierra lo adivinable, que
    es la parte barata del problema.
    """
    from apps.contenidos.models import NoticiaArchivo

    noticia = _noticia("informe-de-cierre-2026")
    uno = NoticiaArchivo.objects.create(noticia=noticia, titulo="a", archivo=_archivo("informe.pdf"))
    otro = NoticiaArchivo.objects.create(noticia=noticia, titulo="b", archivo=_archivo("informe.pdf"))

    assert uno.archivo.name != otro.archivo.name
    assert noticia.slug not in uno.archivo.name
    # El nombre original se conserva: el atributo `download` de un `<a>` se ignora cross-origin,
    # así que el visitante guarda el archivo con el nombre que traiga la URL.
    assert uno.archivo.name.endswith("/informe.pdf")


def test_un_adjunto_borrado_del_disco_no_tumba_la_ficha(api):
    """Es el caso que justifica guardar `peso_bytes` en vez de leer `archivo.size` al serializar."""
    import os

    from apps.contenidos.models import NoticiaArchivo

    noticia = _noticia()
    adjunto = NoticiaArchivo.objects.create(
        noticia=noticia, titulo="Informe", archivo=_archivo(contenido=b"x" * 500)
    )
    os.remove(adjunto.archivo.path)

    respuesta = api.get(f"/api/noticias/{noticia.slug}/")

    assert respuesta.status_code == 200
    assert respuesta.json()["archivos"][0]["peso_bytes"] == 500


def test_reguardar_con_el_adjunto_ausente_no_lanza_ni_borra_el_peso():
    """`full_clean()` corre los validadores sobre el archivo ya escrito. Si desapareció del disco,
    `.size` lanza `FileNotFoundError` y el editor vería un 500 al corregir un título."""
    import os

    from apps.contenidos.models import NoticiaArchivo

    adjunto = NoticiaArchivo.objects.create(
        noticia=_noticia(), titulo="Informe", archivo=_archivo(contenido=b"x" * 77)
    )
    os.remove(adjunto.archivo.path)

    adjunto.titulo = "Informe final"
    adjunto.full_clean()
    adjunto.save()
    adjunto.refresh_from_db()

    assert adjunto.peso_bytes == 77
