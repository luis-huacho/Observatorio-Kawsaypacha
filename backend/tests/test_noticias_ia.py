"""Redacción de una noticia desde su URL de origen (ADR-D7).

Lo que protege son las tres formas que tiene esto de fallar **sin dar ningún error**:

1. Que la casilla deje de eximir de los obligatorios y el editor no pueda guardar — o al revés, que
   los exima siempre y se cuelen noticias sin título.
2. Que el candado se salte, o que se cierre cuando no debía: un timeout no puede inutilizar el
   registro para siempre.
3. Que la tarea pise lo que un editor escribió mientras estaba en cola, que es el peor resultado
   posible de una función que se llama «de ayuda».

La red no se toca: el cliente de OpenRouter y la descarga de la URL son falsos.
"""
import datetime
import json

import pytest

from apps.contenidos import redaccion
from apps.contenidos.models import Noticia
from apps.core.models import EstadoIA

pytestmark = pytest.mark.django_db

PAGINA = """<html><head>
<meta property="og:image" content="https://medio.pe/foto.jpg">
<script>rastreador()</script><style>.a{color:red}</style>
</head><body><nav>Portada</nav>
<h1>Huaicos en Quispicanchi</h1>
<p>Las lluvias del fin de semana activaron quebradas en tres distritos de la provincia de
Quispicanchi, con daños en viviendas y vías de acceso segun el reporte del COER Cusco.</p>
<p>Las autoridades locales evaluan la declaratoria de emergencia mientras continua el monitoreo
de las quebradas activas y se habilitan albergues temporales para las familias afectadas.</p>
</body></html>"""

FICHA = {
    "titulo": "Huaicos en Quispicanchi dejan viviendas afectadas",
    "bajada": "Las lluvias activaron quebradas en tres distritos.",
    "cuerpo": "<p>Las lluvias activaron quebradas en Quispicanchi.</p>",
    "tipo": "noticia",
    "autor": "Redacción",
    "fecha": "2026-03-15",
    "palabras_clave": ["huaicos", "Quispicanchi", "COER"],
    "imagen_titulo": "Quebrada activada en Quispicanchi",
}


@pytest.fixture
def ia(monkeypatch, settings):
    """La IA responde la ficha que se le diga, o revienta. Sin red y sin descargas."""
    settings.OPENROUTER_API_KEY = "llave-de-prueba"
    llamadas = []

    def instalar(ficha=FICHA, error=None, html=PAGINA):
        monkeypatch.setattr(
            redaccion.lectura_web, "descargar", lambda url, **kw: (html.encode("utf-8"), "text/html")
        )
        monkeypatch.setattr(redaccion.lectura_web, "descargar_imagen", lambda html, url: None)

        def completar(mensajes, **opciones):
            llamadas.append({"mensajes": mensajes, **opciones})
            if error is not None:
                raise error
            return type(
                "R", (), {"texto": json.dumps(ficha), "modelo": "modelo/de-prueba", "costo": 0.0001}
            )()

        monkeypatch.setattr(redaccion.openrouter, "completar", completar)
        return llamadas

    return instalar


@pytest.fixture
def formulario(rf, admin_user):
    """Construye el formulario **como lo hace el admin**, no a pelo.

    `NoticiaForm` declara `fields = "__all__"`, pero el admin nunca lo usa así: `get_form` deriva
    la lista de `get_fieldsets()` y `WorkflowAdmin.get_exclude()` saca `estado`. Instanciarlo
    directamente mete campos que en pantalla no existen, y la prueba mediría algo que no ocurre.
    """
    from django.contrib import admin as django_admin

    from apps.contenidos.admin import NoticiaAdmin

    modelo_admin = NoticiaAdmin(Noticia, django_admin.site)

    def construir(datos, instance=None):
        peticion = rf.get("/")
        peticion.user = admin_user
        Form = modelo_admin.get_form(peticion, obj=instance, change=instance is not None)
        return Form(datos, instance=instance)

    return construir


def _noticia_en_proceso(**extra):
    """Una noticia recién guardada con la casilla marcada, como la deja `save_model`."""
    campos = {
        "slug": "medio-pe-abcd1234",
        "titulo": "(redactando) medio.pe",
        "bajada": "",
        "fecha": datetime.date.today(),
        "url_origen": "https://medio.pe/nota",
        "ia_estado": EstadoIA.PROCESANDO,
    }
    campos.update(extra)
    return Noticia.objects.create(**campos)


# --- El formulario ----------------------------------------------------------


def test_con_la_casilla_marcada_no_hacen_falta_titulo_bajada_ni_fecha(formulario):
    form = formulario(
        {"url_origen": "https://medio.pe/nota", "procesar_con_ia": True, "tipo": "noticia"}
    )

    assert form.is_valid(), form.errors


def test_sin_la_casilla_los_obligatorios_siguen_siendolo(formulario):
    """La relajación es de `__init__` y vale siempre; lo que la revierte es `clean()`.

    Si esta prueba cae, el formulario deja crear noticias sin título ni fecha a mano, que es
    exactamente lo que la relajación NO puede provocar.
    """
    form = formulario({"tipo": "noticia"})

    assert not form.is_valid()
    assert set(form.errors) >= {"titulo", "slug", "bajada", "fecha"}


def test_la_casilla_sin_url_no_pasa(formulario):
    form = formulario({"procesar_con_ia": True, "tipo": "noticia"})

    assert not form.is_valid()
    assert "url_origen" in form.errors


def test_una_noticia_ya_redactada_no_puede_volver_a_pedir_la_ia(formulario):
    """El candado. `disabled` además hace que Django ignore lo que llegue por POST."""
    noticia = _noticia_en_proceso(redactada_por_ia=True, ia_estado=EstadoIA.OK)

    form = formulario(
        {"procesar_con_ia": True, "titulo": "A mano", "slug": "a-mano", "bajada": "b",
         "fecha": "2026-01-01", "tipo": "noticia"},
        instance=noticia,
    )

    assert form.fields["procesar_con_ia"].disabled is True
    assert form.is_valid(), form.errors
    assert form.cleaned_data["procesar_con_ia"] is False


# --- La tarea ---------------------------------------------------------------


def test_la_tarea_rellena_los_campos_y_cierra_el_candado(ia):
    ia()
    noticia = _noticia_en_proceso()

    from apps.contenidos.tasks import redactar_noticia_desde_url

    redactar_noticia_desde_url.func(pk=noticia.pk)

    noticia.refresh_from_db()
    assert noticia.titulo == FICHA["titulo"]
    assert noticia.bajada == FICHA["bajada"]
    assert noticia.fecha == datetime.date(2026, 3, 15)
    assert noticia.palabras_clave == FICHA["palabras_clave"]
    assert noticia.redactada_por_ia is True
    assert noticia.ia_estado == EstadoIA.OK
    # El slug provisional se sustituye por uno legible derivado del título.
    assert noticia.slug == "huaicos-en-quispicanchi-dejan-viviendas-afectadas"
    assert "Revísala" in noticia.log_ia


def test_un_fallo_deja_el_candado_ABIERTO(ia):
    """Decisión explícita: el intento se gasta solo si la IA llegó a escribir.

    Con el candado cerrado por un timeout, la única salida sería borrar la noticia y crearla otra
    vez — un corte de red no puede costar eso.
    """
    ia(error=RuntimeError("el proveedor no responde"))
    noticia = _noticia_en_proceso()

    from apps.contenidos.tasks import redactar_noticia_desde_url

    redactar_noticia_desde_url.func(pk=noticia.pk)

    noticia.refresh_from_db()
    assert noticia.ia_estado == EstadoIA.ERROR
    assert noticia.redactada_por_ia is False
    assert "el proveedor no responde" in noticia.log_ia
    assert "reintentar" in noticia.log_ia


def test_la_tarea_no_pisa_lo_que_escribio_una_persona(ia):
    """La ventana entre el encolado y la escritura es real y hay que respetarla."""
    ia()
    noticia = _noticia_en_proceso(bajada="Bajada escrita a mano por el editor.")

    from apps.contenidos.tasks import redactar_noticia_desde_url

    redactar_noticia_desde_url.func(pk=noticia.pk)

    noticia.refresh_from_db()
    assert noticia.bajada == "Bajada escrita a mano por el editor."
    # Pero el título provisional NO cuenta como edición humana: lo puso la máquina.
    assert noticia.titulo == FICHA["titulo"]
    assert "Se conservó" in noticia.log_ia


def test_la_clasificacion_de_la_ia_se_aplica_aunque_tipo_traiga_su_default(ia):
    """`tipo` siempre tiene valor, así que «¿está lleno?» no distingue elección de default.

    Sin esto la IA nunca podía marcar un texto como artículo u opinión —el campo llegaba con
    «noticia» y se leía como escrito a mano—, y el registro lo declaraba «conservado». Un valor
    distinto del default sí es una decisión del editor y se respeta.
    """
    ia(ficha={**FICHA, "tipo": "opinion"})
    noticia = _noticia_en_proceso()  # nace con tipo="noticia", el default

    from apps.contenidos.tasks import redactar_noticia_desde_url

    redactar_noticia_desde_url.func(pk=noticia.pk)

    noticia.refresh_from_db()
    assert noticia.tipo == "opinion"
    assert "tipo" not in noticia.log_ia


def test_un_tipo_elegido_a_mano_si_se_respeta(ia):
    ia(ficha={**FICHA, "tipo": "noticia"})
    noticia = _noticia_en_proceso(tipo="articulo")

    from apps.contenidos.tasks import redactar_noticia_desde_url

    redactar_noticia_desde_url.func(pk=noticia.pk)

    noticia.refresh_from_db()
    assert noticia.tipo == "articulo"


def test_una_noticia_ya_redactada_no_se_reprocesa_aunque_se_encole(ia):
    llamadas = ia()
    noticia = _noticia_en_proceso(redactada_por_ia=True, titulo="Definitivo")

    from apps.contenidos.tasks import redactar_noticia_desde_url

    redactar_noticia_desde_url.func(pk=noticia.pk)

    noticia.refresh_from_db()
    assert noticia.titulo == "Definitivo"
    assert llamadas == []


# --- La llamada -------------------------------------------------------------


def test_la_llamada_es_UNA_y_fija_el_proveedor(ia):
    """Dos invariantes de coste y de fiabilidad en la misma prueba.

    **Una sola llamada**: encadenar una por campo multiplicaría el coste por el mismo texto de
    entrada, que es lo caro. **`require_parameters`**: del mismo modelo hay proveedores sin salida
    estructurada, y OpenRouter enruta cada petición por separado, así que sin fijarlo la función
    falla una de cada tantas veces y siempre por una causa distinta.
    """
    llamadas = ia()

    redaccion.redactar("https://medio.pe/nota", con_imagen=False)

    assert len(llamadas) == 1
    llamada = llamadas[0]
    assert llamada["extra_body"]["provider"]["require_parameters"] is True
    assert llamada["response_format"]["type"] == "json_schema"
    # Extraer campos no mejora razonando y sí se paga; `None` no bastaría porque el modelo por
    # defecto razona salvo que se le diga que no.
    assert llamada["razonamiento"] is False


@pytest.mark.parametrize(
    ("crudo", "esperado"),
    [
        ({**FICHA, "tipo": "cronica"}, "noticia"),   # fuera de las opciones del modelo
        ({**FICHA, "tipo": "opinion"}, "opinion"),
    ],
)
def test_un_tipo_inventado_cae_a_noticia(ia, crudo, esperado):
    """El modelo propone y se equivoca; un valor fuera de `choices` reventaría al guardar."""
    ia(ficha=crudo)

    assert redaccion.redactar("https://medio.pe/nota", con_imagen=False).tipo == esperado


def test_una_fecha_ilegible_cae_a_hoy(ia):
    ia(ficha={**FICHA, "fecha": "el martes pasado"})

    assert redaccion.redactar("https://medio.pe/nota", con_imagen=False).fecha == datetime.date.today()


def test_las_palabras_clave_se_recortan_al_maximo_del_campo(ia):
    """`ArrayField(CharField(max_length=60))`: una más larga rompe al guardar, en el worker."""
    ia(ficha={**FICHA, "palabras_clave": ["x" * 200]})

    claves = redaccion.redactar("https://medio.pe/nota", con_imagen=False).palabras_clave
    assert len(claves[0]) == 60


def test_una_pagina_sin_texto_se_rechaza_con_un_motivo_util(ia):
    ia(html="<html><body><div id='app'></div></body></html>")

    with pytest.raises(ValueError, match="muro de pago|JavaScript"):
        redaccion.redactar("https://medio.pe/nota")


# --- El sondeo que refresca la ficha ----------------------------------------


def test_el_endpoint_de_estado_exige_sesion_de_staff(client):
    """El `log_ia` lleva la URL de origen y el detalle de errores del servidor: no es público."""
    noticia = _noticia_en_proceso()

    respuesta = client.get(_url_estado(noticia.pk))

    assert respuesta.status_code in (302, 403)


def test_el_endpoint_de_estado_responde_lo_justo(admin_client):
    noticia = _noticia_en_proceso(log_ia="en curso")

    datos = admin_client.get(_url_estado(noticia.pk)).json()

    assert datos == {"estado": "procesando", "redactada": False, "log": "en curso"}


def test_el_endpoint_va_declarado_ANTES_del_admin(admin_client):
    """`AdminSite` termina con un `catch_all_view` que casa con todo bajo su prefijo y da 404.

    Una ruta declarada después **nunca se alcanza**, y el síntoma es un 404 que no parece un
    problema de orden de URLs: es lo que dejó la subida de imágenes de CKEditor rota en su día. Lo
    que se comprueba aquí es que la vista responde, no un detalle de `urls.py`.
    """
    noticia = _noticia_en_proceso()

    assert admin_client.get(_url_estado(noticia.pk)).status_code == 200
    assert admin_client.get(_url_estado(noticia.pk + 9999)).status_code == 404


def _url_estado(pk):
    from django.urls import reverse

    return reverse("estado-ia", args=["contenidos", "noticia", pk])
