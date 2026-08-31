"""Redacción de una norma desde el enlace a su publicación oficial (ADR-D8).

Espejo de `test_noticias_ia.py`, con lo que aquí es distinto: **la rama PDF**. Lo que protege son
las formas que esto tiene de fallar **sin dar ningún error**:

1. Que la casilla deje de eximir de los obligatorios y el editor no pueda guardar — o al revés, que
   los exima siempre y se cuelen normas sin título.
2. Que el candado se salte, o que se cierre cuando no debía: un timeout no puede inutilizar el
   registro para siempre.
3. Que la tarea pise lo que un editor escribió mientras estaba en cola, o que escriba lo que **no**
   le toca: `analisis_predes` es la voz de PREDES y `url_oficial` presenta un enlace como oficial.
4. Que un PDF entre por la rama de HTML y la IA redacte a partir de basura binaria.
5. Que un PDF escaneado devuelva una ficha vacía y se guarde **con el candado cerrado**, dejando la
   norma inservible y sin forma de reintentar.

La red no se toca: el cliente de OpenRouter y la descarga son falsos.
"""
import datetime
import json

import pytest

from apps.core.models import EstadoIA
from apps.normativa import redaccion
from apps.normativa.models import EntidadEmisora, Norma

pytestmark = pytest.mark.django_db

PAGINA = """<html><head>
<meta property="og:image" content="https://busquedas.elperuano.pe/portada.jpg">
<script>rastreador()</script>
</head><body><nav>Inicio</nav>
<h1>Decreto Supremo 048-2011-PCM</h1>
<p>Aprueban el Reglamento de la Ley 29664, que crea el Sistema Nacional de Gestion del Riesgo de
Desastres, estableciendo las competencias de los gobiernos regionales y locales en los procesos
de estimacion, prevencion y reduccion del riesgo.</p>
<p>El reglamento fija plazos para la conformacion de los grupos de trabajo de la GRD y para la
elaboracion de los planes de prevencion y reduccion del riesgo de desastres.</p>
</body></html>"""

PDF = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"

FICHA = {
    "titulo": "Reglamento de la Ley 29664, Ley del SINAGERD",
    "numero": "DS 048-2011-PCM",
    "tipo": "DS",
    "ambito": "nacional",
    "fecha": "2011-05-26",
    "resumen": "Aprueba el reglamento de la Ley del SINAGERD y fija las competencias de los "
               "gobiernos regionales y locales en los procesos de la GRD.",
    "contenido": "<p>El reglamento desarrolla los siete procesos de la GRD.</p>",
    "palabras_clave": ["SINAGERD", "marco normativo", "competencias"],
    "estado_vigencia": "vigente",
    "imagen_titulo": "Portada de la edición de El Peruano",
}


@pytest.fixture
def ia(monkeypatch, settings):
    """La IA responde la ficha que se le diga, o revienta. Sin red y sin descargas."""
    settings.OPENROUTER_API_KEY = "llave-de-prueba"
    settings.OPENROUTER_PDF_ENGINE = "pdf-text"
    llamadas = []

    def instalar(ficha=FICHA, error=None, crudo=None, content_type="text/html"):
        cuerpo = PAGINA.encode("utf-8") if crudo is None else crudo
        monkeypatch.setattr(
            redaccion.lectura_web, "descargar", lambda url, **kw: (cuerpo, content_type)
        )
        monkeypatch.setattr(redaccion.lectura_web, "descargar_imagen", lambda html, url: None)

        def completar(mensajes, **opciones):
            llamadas.append({"mensajes": mensajes, **opciones})
            if error is not None:
                raise error
            return type(
                "R", (), {"texto": json.dumps(ficha), "modelo": "modelo/de-prueba", "costo": 0.0002}
            )()

        monkeypatch.setattr(redaccion.openrouter, "completar", completar)
        return llamadas

    return instalar


@pytest.fixture
def formulario(rf, admin_user):
    """Construye el formulario **como lo hace el admin**, no a pelo.

    `NormaForm` declara `fields = "__all__"`, pero el admin nunca lo usa así: `get_form` deriva la
    lista de `get_fieldsets()` y `WorkflowAdmin.get_exclude()` saca `estado`. Instanciarlo
    directamente mete campos que en pantalla no existen, y la prueba mediría algo que no ocurre.
    """
    from django.contrib import admin as django_admin

    from apps.normativa.admin import NormaAdmin

    modelo_admin = NormaAdmin(Norma, django_admin.site)

    def construir(datos, instance=None):
        peticion = rf.get("/")
        peticion.user = admin_user
        Form = modelo_admin.get_form(peticion, obj=instance, change=instance is not None)
        return Form(datos, instance=instance)

    return construir


@pytest.fixture
def entidades(db):
    """Las entidades que ya sembró `seed --solo-catalogos` para toda la sesión (`conftest`).

    No se crean aquí: son catálogo, y crearlas de nuevo chocaría con la unicidad del nombre.
    """
    return {e.slug: e for e in EntidadEmisora.objects.all()}


def _norma_en_proceso(**extra):
    """Una norma recién guardada con la casilla marcada, como la deja `save_model`."""
    campos = {
        "slug": "elperuano-pe-abcd1234",
        "titulo": "(redactando) busquedas.elperuano.pe",
        "tipo": "",
        "ambito": "",
        "fecha": datetime.date.today(),
        "resumen": "",
        "url_origen": "https://busquedas.elperuano.pe/normas/ds-048-2011",
        "ia_estado": EstadoIA.PROCESANDO,
    }
    campos.update(extra)
    return Norma.objects.create(**campos)


# --- El formulario ----------------------------------------------------------

BASE = {"url_origen": "https://busquedas.elperuano.pe/normas/ds-048-2011"}


def test_con_la_casilla_marcada_no_hace_falta_nada_mas(formulario):
    """Son cinco obligatorios, y `tipo` y `ambito` no los tiene una noticia."""
    form = formulario({**BASE, "procesar_con_ia": "on", "palabras_clave": ""})

    assert form.is_valid(), form.errors


def test_sin_la_casilla_los_obligatorios_siguen_siendolo(formulario):
    form = formulario({**BASE, "palabras_clave": ""})

    assert not form.is_valid()
    assert set(form.errors) == {"titulo", "slug", "tipo", "ambito", "fecha", "resumen"}


def test_la_casilla_sin_url_no_pasa(formulario):
    form = formulario({"procesar_con_ia": "on", "palabras_clave": ""})

    assert not form.is_valid()
    assert "url_origen" in form.errors


def test_una_norma_ya_redactada_no_puede_volver_a_pedir_la_ia(formulario):
    """El candado es por registro, y no se salta manipulando el POST.

    Django ignora lo que llegue en un campo `disabled`, que es justo por lo que se usa `disabled` y
    no `readonly_fields`.
    """
    norma = _norma_en_proceso(redactada_por_ia=True, ia_estado=EstadoIA.OK)
    form = formulario(
        {**BASE, "procesar_con_ia": "on", "titulo": "Reglamento", "slug": "reglamento",
         "tipo": "DS", "ambito": "nacional", "fecha": "2011-05-26", "resumen": "x",
         "palabras_clave": ""},
        instance=norma,
    )

    assert form.is_valid(), form.errors
    assert form.cleaned_data["procesar_con_ia"] is False


# --- La tarea ---------------------------------------------------------------


def test_la_tarea_rellena_los_campos_y_cierra_el_candado(ia):
    ia()
    norma = _norma_en_proceso()

    from apps.normativa.tasks import redactar_norma_desde_url

    redactar_norma_desde_url.func(norma.pk)
    norma.refresh_from_db()

    assert norma.titulo == FICHA["titulo"]
    assert norma.numero == "DS 048-2011-PCM"
    assert norma.tipo == Norma.Tipo.DS
    assert norma.ambito == Norma.Ambito.NACIONAL
    assert norma.fecha == datetime.date(2011, 5, 26)
    assert norma.estado_vigencia == "vigente"
    assert norma.palabras_clave == FICHA["palabras_clave"]
    assert norma.redactada_por_ia is True
    assert norma.ia_estado == EstadoIA.OK
    # El slug provisional se sustituye por uno derivado del título de verdad.
    assert norma.slug.startswith("reglamento-de-la-ley-29664")


def test_un_fallo_deja_el_candado_ABIERTO(ia):
    """Un corte de red no puede inutilizar una norma para siempre."""
    ia(error=RuntimeError("timeout"))
    norma = _norma_en_proceso()

    from apps.normativa.tasks import redactar_norma_desde_url

    redactar_norma_desde_url.func(norma.pk)
    norma.refresh_from_db()

    assert norma.redactada_por_ia is False
    assert norma.ia_estado == EstadoIA.ERROR
    assert "timeout" in norma.log_ia


def test_la_tarea_no_pisa_lo_que_escribio_una_persona(ia):
    ia()
    norma = _norma_en_proceso(titulo="Título que escribió el editor", tipo=Norma.Tipo.LEY)

    from apps.normativa.tasks import redactar_norma_desde_url

    redactar_norma_desde_url.func(norma.pk)
    norma.refresh_from_db()

    assert norma.titulo == "Título que escribió el editor"
    assert norma.tipo == Norma.Tipo.LEY
    # Lo que estaba vacío sí se rellena.
    assert norma.ambito == Norma.Ambito.NACIONAL
    assert "titulo" in norma.log_ia and "tipo" in norma.log_ia


def test_la_tarea_no_pisa_la_entidad_que_ELIGIO_EL_EDITOR(ia, entidades):
    """La FK entra en `CAMPOS_REDACTADOS`, así que le aplica la misma regla que al resto: si ya
    hay algo puesto a mano, la IA no lo toca."""
    ia({**FICHA, "entidad_emisora": "minam"})
    norma = _norma_en_proceso(entidad_emisora=entidades["pcm"])

    from apps.normativa.tasks import redactar_norma_desde_url

    redactar_norma_desde_url.func(norma.pk)
    norma.refresh_from_db()

    assert norma.entidad_emisora == entidades["pcm"]
    assert "entidad_emisora" in norma.log_ia


def test_la_tarea_rellena_la_entidad_cuando_estaba_vacia(ia, entidades):
    ia({**FICHA, "entidad_emisora": "minam"})
    norma = _norma_en_proceso()

    from apps.normativa.tasks import redactar_norma_desde_url

    redactar_norma_desde_url.func(norma.pk)
    norma.refresh_from_db()

    assert norma.entidad_emisora == entidades["minam"]


def test_la_tarea_NO_escribe_el_analisis_de_predes_ni_la_url_oficial(ia):
    """Los dos campos que la IA no toca, y no por olvido.

    `analisis_predes` es la nota que firma la organización en el listado; `url_oficial` presenta un
    enlace como publicación oficial y no puede acabar apuntando a lo que el editor pegó arriba.
    """
    ia({**FICHA, "analisis_predes": "inventado", "url_oficial": "https://otro.pe"})
    norma = _norma_en_proceso()

    from apps.normativa.tasks import redactar_norma_desde_url

    redactar_norma_desde_url.func(norma.pk)
    norma.refresh_from_db()

    assert not norma.analisis_predes
    assert not norma.url_oficial


def test_una_norma_ya_redactada_no_se_reprocesa_aunque_se_encole(ia):
    llamadas = ia()
    norma = _norma_en_proceso(redactada_por_ia=True, titulo="Ya redactada")

    from apps.normativa.tasks import redactar_norma_desde_url

    redactar_norma_desde_url.func(norma.pk)
    norma.refresh_from_db()

    assert llamadas == []
    assert norma.titulo == "Ya redactada"


# --- La llamada -------------------------------------------------------------


def test_la_llamada_es_UNA_y_fija_el_proveedor(ia):
    """Un campo por llamada multiplicaría por nada el coste del texto de entrada, que es lo caro.

    Y sin `require_parameters`, OpenRouter puede enrutar a un proveedor sin salida estructurada y
    la llamada falla de forma intermitente.
    """
    llamadas = ia()

    redaccion.redactar("https://busquedas.elperuano.pe/normas/ds-048-2011")

    assert len(llamadas) == 1
    unica = llamadas[0]
    assert unica["razonamiento"] is False
    assert unica["response_format"]["type"] == "json_schema"
    assert unica["extra_body"]["provider"]["require_parameters"] is True
    # La rama HTML no lleva el parser de archivos.
    assert "plugins" not in unica["extra_body"]


def test_un_pdf_va_como_adjunto_en_UNA_sola_llamada(ia):
    """La diferencia real con noticias: media Perú publica sus normas como PDF.

    Por la rama de HTML, el extractor le pasaría al modelo basura binaria decodificada.
    """
    llamadas = ia(crudo=PDF, content_type="application/pdf")

    redaccion.redactar("https://busquedas.elperuano.pe/download/url/ds-048-2011")

    assert len(llamadas) == 1
    unica = llamadas[0]
    partes = unica["mensajes"][1]["content"]
    assert [parte["type"] for parte in partes] == ["text", "file"]
    assert partes[1]["file"]["file_data"].startswith("data:application/pdf;base64,")
    assert unica["extra_body"]["plugins"] == [
        {"id": "file-parser", "pdf": {"engine": "pdf-text"}}
    ]
    # El proveedor se sigue fijando: el plugin no sustituye a la guarda.
    assert unica["extra_body"]["provider"]["require_parameters"] is True


def test_un_pdf_escaneado_falla_con_un_motivo_util_en_vez_de_guardarse_vacio(ia):
    """`pdf-text` no lee un escaneo y el modelo contesta en blanco, sin quejarse.

    Sin esta guarda la ficha se guardaría vacía **y con el candado cerrado**, que es el peor
    resultado posible: una norma inservible que además no se puede reintentar.
    """
    ia({**FICHA, "titulo": ""}, crudo=PDF, content_type="application/pdf")

    with pytest.raises(ValueError, match="capa de texto"):
        redaccion.redactar("https://busquedas.elperuano.pe/download/url/ds-048-2011")


def test_una_pagina_que_no_identifica_la_norma_se_rechaza(ia):
    ia({**FICHA, "titulo": ""})

    with pytest.raises(ValueError, match="no permitió identificar"):
        redaccion.redactar("https://busquedas.elperuano.pe/normas/ds-048-2011")


def test_una_pagina_sin_texto_se_rechaza_con_un_motivo_util(ia):
    ia(crudo=b"<html><body>hola</body></html>")

    with pytest.raises(ValueError, match="texto legible"):
        redaccion.redactar("https://busquedas.elperuano.pe/normas/ds-048-2011")


# --- Normalización ----------------------------------------------------------


@pytest.mark.parametrize("campo", ["tipo", "ambito"])
def test_un_tipo_o_un_ambito_inventado_se_deja_VACIO(ia, campo):
    """Sin repliegue inventado: un valor fuera del catálogo se deja vacío para que el editor elija.

    Replegar a una opción cualquiera pondría una clasificación falsa que nadie revisaría, porque
    el campo se vería lleno.
    """
    ia({**FICHA, campo: "Decreto de Urgencia"})

    propuesta = redaccion.redactar("https://busquedas.elperuano.pe/normas/x")

    assert getattr(propuesta, campo) == ""


def test_la_entidad_del_catalogo_se_resuelve_a_su_fila(ia, entidades):
    ia({**FICHA, "entidad_emisora": "pcm"})

    propuesta = redaccion.redactar("https://busquedas.elperuano.pe/normas/x")

    assert propuesta.entidad_emisora == entidades["pcm"]


def test_una_entidad_fuera_del_catalogo_se_deja_VACIA_y_lo_avisa(ia, entidades):
    """Misma doctrina que `tipo` y `ambito`, y un motivo más: crear la que falta llenaría el
    catálogo de variantes del mismo nombre, que es justo lo que un catálogo existe para evitar."""
    ia({**FICHA, "entidad_emisora": "municipalidad-de-echarati"})

    propuesta = redaccion.redactar("https://busquedas.elperuano.pe/normas/x")

    assert propuesta.entidad_emisora is None
    assert any("municipalidad-de-echarati" in a for a in propuesta.avisos)
    # Y no se ha creado por el camino.
    assert not EntidadEmisora.objects.filter(slug="municipalidad-de-echarati").exists()


def test_el_enum_de_entidades_sale_del_CATALOGO_VIVO(ia, entidades):
    """Escrita a mano, la lista se desincronizaría en cuanto PREDES diera de alta una entidad
    desde el admin, y la IA no podría elegirla nunca."""
    llamadas = ia()
    EntidadEmisora.objects.create(
        slug="entidad-recien-creada", nombre="Entidad recién creada en el admin"
    )

    redaccion.redactar("https://busquedas.elperuano.pe/normas/x")

    esquema = llamadas[0]["response_format"]["json_schema"]
    opciones = esquema["schema"]["properties"]["entidad_emisora"]["enum"]
    assert set(opciones) == set(EntidadEmisora.objects.values_list("slug", flat=True)) | {""}
    assert "entidad-recien-creada" in opciones


def test_un_estado_de_vigencia_inventado_se_deja_vacio(ia):
    ia({**FICHA, "estado_vigencia": "en revisión"})

    assert redaccion.redactar("https://busquedas.elperuano.pe/normas/x").estado_vigencia == ""


def test_el_resumen_se_recorta_al_maximo_del_campo(ia):
    """700 caracteres: pasarse reventaría al guardar, en el worker, donde el editor no lo ve."""
    ia({**FICHA, "resumen": "a" * 900})

    assert len(redaccion.redactar("https://busquedas.elperuano.pe/normas/x").resumen) == 700


def test_una_fecha_ilegible_cae_a_hoy(ia):
    ia({**FICHA, "fecha": "sin fecha"})

    fecha = redaccion.redactar("https://busquedas.elperuano.pe/normas/x").fecha
    assert fecha == datetime.date.today()


def test_las_palabras_clave_se_recortan_al_maximo_del_campo(ia):
    ia({**FICHA, "palabras_clave": ["x" * 90, "  ", "SINAGERD"]})

    claves = redaccion.redactar("https://busquedas.elperuano.pe/normas/x").palabras_clave
    assert claves == ["x" * 60, "SINAGERD"]


# --- El admin ---------------------------------------------------------------


def test_guardar_con_la_casilla_deja_provisionales_y_encola(rf, admin_user, settings, monkeypatch):
    """Relajar los obligatorios en el formulario no basta: `slug` y `fecha` son NOT NULL."""
    from django.contrib import admin as django_admin

    from apps.normativa.admin import NormaAdmin

    settings.OPENROUTER_API_KEY = "llave-de-prueba"
    encoladas = []
    monkeypatch.setattr(
        NormaAdmin, "encolar_ia", lambda self, obj: encoladas.append(obj.pk)
    )

    modelo_admin = NormaAdmin(Norma, django_admin.site)
    peticion = rf.post("/")
    peticion.user = admin_user
    peticion._messages = _MensajesFalsos()
    Form = modelo_admin.get_form(peticion, obj=None, change=False)
    form = Form({**BASE, "procesar_con_ia": "on", "palabras_clave": ""})
    assert form.is_valid(), form.errors

    modelo_admin.save_model(peticion, form.save(commit=False), form, change=False)

    norma = Norma.objects.get()
    assert norma.titulo.startswith(Norma.PREFIJO_PROVISIONAL)
    assert norma.slug and norma.fecha == datetime.date.today()
    assert norma.ia_estado == EstadoIA.PROCESANDO
    assert encoladas == [norma.pk]


def test_sin_llave_no_se_encola_y_se_avisa_al_editor(rf, admin_user, settings, monkeypatch):
    """En el worker el editor no vería nunca por qué no pasó nada."""
    from django.contrib import admin as django_admin

    from apps.normativa.admin import NormaAdmin

    settings.OPENROUTER_API_KEY = ""
    monkeypatch.setattr(NormaAdmin, "encolar_ia", lambda self, obj: pytest.fail("no debía encolar"))

    modelo_admin = NormaAdmin(Norma, django_admin.site)
    peticion = rf.post("/")
    peticion.user = admin_user
    peticion._messages = _MensajesFalsos()
    Form = modelo_admin.get_form(peticion, obj=None, change=False)
    form = Form({**BASE, "procesar_con_ia": "on", "palabras_clave": ""})
    assert form.is_valid(), form.errors

    modelo_admin.save_model(peticion, form.save(commit=False), form, change=False)

    assert Norma.objects.get().ia_estado == EstadoIA.PENDIENTE
    assert "OPENROUTER_API_KEY" in peticion._messages.textos[0]


class _MensajesFalsos:
    """`message_user` necesita el almacén de mensajes, que un `RequestFactory` no monta."""

    def __init__(self):
        self.textos = []

    def add(self, nivel, mensaje, extra_tags=""):
        self.textos.append(str(mensaje))


# --- El sondeo que refresca la ficha ----------------------------------------


def test_el_endpoint_de_estado_exige_sesion_de_staff(client):
    """El `log_ia` lleva la URL de origen y el detalle de errores del servidor. No es público."""
    norma = _norma_en_proceso()

    respuesta = client.get(_url_estado(norma.pk))

    assert respuesta.status_code in (302, 403)


def test_el_endpoint_de_estado_responde_lo_justo(admin_client):
    norma = _norma_en_proceso(log_ia="lo que sea")

    datos = admin_client.get(_url_estado(norma.pk)).json()

    assert set(datos) == {"estado", "redactada", "log"}
    assert datos["estado"] == EstadoIA.PROCESANDO


def test_el_endpoint_va_declarado_ANTES_del_admin(admin_client):
    """El `catch_all_view` del AdminSite responde 404 a todo lo que cuelgue de su prefijo.

    Una ruta declarada después nunca se alcanza, y el fallo no se parece a lo que es: el refresco
    automático deja de funcionar sin que nada más falle.
    """
    norma = _norma_en_proceso()

    assert admin_client.get(_url_estado(norma.pk)).status_code == 200
    assert admin_client.get(_url_estado(norma.pk + 9999)).status_code == 404


def test_un_modelo_fuera_de_la_lista_blanca_no_se_puede_consultar(admin_client):
    """La ruta es genérica; qué se puede leer lo decide la lista blanca, no el patrón."""
    from django.urls import reverse

    url = reverse("estado-ia", args=["biblioteca", "documento", 1])

    assert admin_client.get(url).status_code == 404


def test_los_dos_admin_declaran_el_js_que_refresca_la_ficha():
    """Sin el JS, el editor guarda y se queda mirando una ficha que no cambia sola.

    Se mira `media` y no el HTML servido a propósito: el `class Media` está en un **mixin**, y que
    Django lo recoja desde ahí es justo lo que puede romperse en silencio al reorganizar las bases.
    Renderizar la página, además, obligaría a haber corrido `collectstatic` para pasar.
    """
    from django.contrib import admin as django_admin

    from apps.contenidos.admin import NoticiaAdmin
    from apps.contenidos.models import Noticia
    from apps.core.admin_ia import JS_REDACCION_IA
    from apps.normativa.admin import NormaAdmin

    for ModeloAdmin, Modelo in ((NormaAdmin, Norma), (NoticiaAdmin, Noticia)):
        media = ModeloAdmin(Modelo, django_admin.site).media
        assert JS_REDACCION_IA in media._js, ModeloAdmin.__name__


def _url_estado(pk):
    from django.urls import reverse

    return reverse("estado-ia", args=["normativa", "norma", pk])


def test_un_contenido_en_texto_plano_se_envuelve_en_parrafos(ia):
    """Aquí tampoco había red hasta ahora, y es donde más se notó.

    Medido el 28/08/2026 con `deepseek/deepseek-v4-flash-0731` contra el API real: de tres normas
    pedidas, **dos volvieron sin una sola etiqueta** —una de ellas la del PDF, en 255 caracteres—
    y se guardaron tal cual. La tercera, la misma URL que una de esas dos, sí vino formateada:
    es el mismo modelo dando dos resultados distintos para la misma entrada.
    """
    ia({**FICHA, "contenido": "Primer párrafo.\n\nSegundo párrafo."})
    propuesta = redaccion.redactar("https://busquedas.elperuano.pe/normas/ds-048-2011")

    assert propuesta.contenido == "<p>Primer párrafo.</p><p>Segundo párrafo.</p>"
    assert any("sin formato" in aviso for aviso in propuesta.avisos)


def test_un_contenido_que_ya_viene_en_html_no_se_toca(ia):
    ia()
    propuesta = redaccion.redactar("https://busquedas.elperuano.pe/normas/ds-048-2011")

    assert propuesta.contenido == FICHA["contenido"]
    assert not any("sin formato" in aviso for aviso in propuesta.avisos)


def test_el_aviso_de_formato_llega_a_la_bitacora_del_editor(ia):
    """Envolver sin avisar no sirve de nada: el editor tiene que enterarse de que hubo que
    rescatar el contenido, porque es la señal de que conviene revisar la maqueta."""
    ia({**FICHA, "contenido": "Un solo párrafo corrido."})
    norma = _norma_en_proceso()

    from apps.normativa.tasks import redactar_norma_desde_url

    redactar_norma_desde_url.func(norma.pk)
    norma.refresh_from_db()

    assert "sin formato" in norma.log_ia
