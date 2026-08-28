"""Flujo editorial (spec 03): transiciones, permisos y avisos por correo.

Desde ADR-P3 el flujo es **borrador → publicado**, sin paso de revisión, y cualquier editor
publica. Lo que se protege aquí es lo que sigue pudiendo fallar en silencio: que solo se pueda
llegar a `publicado` por una transición —y no editando el campo, que no dispara nada—, que no
publique quien no tiene el permiso, y que el aviso llegue a alguien. Los tres fallos son mudos
—el contenido se guarda, la operación «funciona»— así que sin pruebas no se notan hasta que
alguien pregunta por un correo que nunca llegó.
"""
from django.core import mail

import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture
def medida(db, usuarios):
    from apps.medidas.models import Medida
    from apps.peligros.models import TipoPeligro

    return Medida.objects.create(
        slug="zanjas-de-infiltracion",
        titulo="Zanjas de infiltración en Chumbivilcas",
        tipo_peligro=TipoPeligro.objects.get(slug="sequia"),
        ambito=Medida.Ambito.COMUNAL,
        resultado=Medida.Resultado.EXITO,
        resumen_corto="Recarga de acuíferos con trabajo comunal.",
        creado_por=usuarios["editor"],
    )


def _correos_encolados():
    """Ejecuta las tareas de correo pendientes y devuelve los mensajes enviados.

    Las tareas se encolan en la base (django-tasks): aquí se corren en línea, porque lo que
    interesa es **a quién se escribe y con qué texto**, no que exista una fila en la cola. Se
    ejecuta la tarea real con sus argumentos reales, así que la prueba cubre el camino completo
    desde `transicionar()` hasta el mensaje.
    """
    from django.apps import apps

    from apps.core.tasks import notificar_transicion_editorial

    DBTaskResult = apps.get_model("django_tasks_database", "DBTaskResult")
    pendientes = DBTaskResult.objects.filter(
        task_path__endswith="notificar_transicion_editorial"
    ).order_by("enqueued_at")
    for fila in pendientes:
        notificar_transicion_editorial.func(**fila.args_kwargs["kwargs"])
        fila.delete()
    return mail.outbox


# --- Transiciones -----------------------------------------------------------


def test_se_publica_directo_desde_borrador(medida, usuarios):
    """El cambio de ADR-P3: ya no hay paso intermedio.

    Antes esto lanzaba «Transición inválida» y era el punto del flujo. Ahora el punto es el
    contrario, y esta prueba existe para que reintroducir la revisión sin decirlo se note.
    """
    medida.transicionar("publicado", usuario=usuarios["editor"])

    assert medida.estado == "publicado"


def test_revision_ya_no_es_un_estado(medida, usuarios):
    """No queda ni como destino alcanzable ni como valor válido."""
    with pytest.raises(ValueError):
        medida.transicionar("revision", usuario=usuarios["publicador"])

    medida.refresh_from_db()
    assert medida.estado == "borrador"
    assert "revision" not in dict(medida.Estado.choices)


def test_el_camino_completo_funciona(medida, usuarios):
    medida.transicionar("publicado", usuario=usuarios["editor"])
    assert medida.estado == "publicado"

    medida.transicionar("archivado", usuario=usuarios["publicador"])
    assert medida.estado == "archivado"

    medida.transicionar("borrador", usuario=usuarios["publicador"])
    assert medida.estado == "borrador"


def test_publicar_sella_la_fecha(medida, usuarios):
    """`publicado_en` ordena los listados y sale en las fichas: no puede quedarse vacío."""
    medida.transicionar("publicado", usuario=usuarios["publicador"])

    assert medida.publicado_en is not None
    assert medida.revisado_por == usuarios["publicador"]


def test_un_editor_publica_lo_que_escribio(medida, usuarios):
    """Decisión de ADR-P3: sin paso de revisión, el editor se quedaba sin ninguna acción.

    El precio está escrito en el ADR: nadie mira el contenido antes de que salga al público.
    """
    medida.transicionar("publicado", usuario=usuarios["editor"])

    assert medida.estado == "publicado"


def test_un_usuario_de_staff_sin_grupo_no_publica(medida, db):
    """`TRANSICIONES_RESERVADAS` sigue sirviendo para algo.

    Ya no separa al editor del publicador —los tres grupos tienen el permiso—, pero es lo único
    que impide que una cuenta de staff recién creada, todavía sin grupo, publique al sitio.
    """
    from django.contrib.auth import get_user_model

    suelto = get_user_model().objects.create_user(
        username="sin-grupo", email="suelto@predes.test", password="x", is_staff=True
    )

    with pytest.raises(PermissionError):
        medida.transicionar("publicado", usuario=suelto)

    medida.refresh_from_db()
    assert medida.estado == "borrador"


def test_las_transiciones_posibles_se_filtran_por_permiso(medida, usuarios, db):
    from django.contrib.auth import get_user_model

    suelto = get_user_model().objects.create_user(
        username="sin-grupo-2", email="suelto2@predes.test", password="x", is_staff=True
    )

    assert "publicado" in medida.transiciones_posibles(usuarios["editor"])
    assert "publicado" not in medida.transiciones_posibles(suelto)


def test_un_superusuario_puede_publicar_sin_estar_en_el_grupo(medida):
    from django.contrib.auth import get_user_model

    admin = get_user_model().objects.create_superuser(
        username="admin-pruebas", email="admin@predes.test", password="x"
    )
    medida.transicionar("publicado", usuario=admin)

    assert medida.estado == "publicado"


# --- Avisos por correo ------------------------------------------------------


def test_publicar_avisa_a_quien_lo_escribio(medida, usuarios):
    """Cuando publica **otra persona**, el autor se entera."""
    mail.outbox.clear()

    medida.transicionar("publicado", usuario=usuarios["publicador"])
    enviados = _correos_encolados()

    assert len(enviados) == 1
    assert enviados[0].to == [usuarios["editor"].email]
    assert medida.titulo in enviados[0].subject + enviados[0].body


def test_no_se_avisa_a_quien_se_avisaria_a_si_mismo(medida, usuarios):
    """Desde ADR-P3 el autor suele ser quien publica.

    Sin esta regla, cada publicación le mandaría un correo contándole lo que acaba de hacer él, y
    en dos semanas nadie leería ninguno — que es como se estropea un sistema de avisos.
    """
    mail.outbox.clear()

    medida.transicionar("publicado", usuario=usuarios["editor"])

    assert _correos_encolados() == []


def test_retirar_del_sitio_lleva_las_observaciones_en_el_correo(medida, usuarios):
    """Es el único sitio donde se le puede explicar al autor qué corregir.

    Si la nota no viajara en el correo, el autor vería su contenido de vuelta en borrador sin
    saber por qué, y tendría que entrar al admin a buscarla.
    """
    medida.transicionar("publicado", usuario=usuarios["publicador"])
    _correos_encolados()
    mail.outbox.clear()

    medida.nota_revision = "Falta citar la fuente de la cifra de familias."
    medida.transicionar("borrador", usuario=usuarios["publicador"])
    enviados = _correos_encolados()

    assert len(enviados) == 1
    assert enviados[0].to == [usuarios["editor"].email]
    assert "Falta citar la fuente" in enviados[0].body


def test_archivar_no_llena_la_bandeja_de_nadie(medida, usuarios):
    """Solo las transiciones que le importan a una persona generan correo.

    Un aviso que se ignora deja de ser un aviso.
    """
    medida.transicionar("publicado", usuario=usuarios["publicador"])
    _correos_encolados()
    mail.outbox.clear()

    medida.transicionar("archivado", usuario=usuarios["publicador"])

    assert _correos_encolados() == []


def test_sin_destinatario_la_transicion_sigue_adelante(medida, usuarios):
    """Un buzón mal configurado no puede impedir publicar.

    Queda registrado en el log —es el síntoma de un contenido sin autor o de un usuario sin
    correo— pero la operación editorial no se bloquea por ello.
    """
    usuarios["editor"].email = ""
    usuarios["editor"].save()
    mail.outbox.clear()

    medida.transicionar("publicado", usuario=usuarios["publicador"])

    assert medida.estado == "publicado"
    assert _correos_encolados() == []


# --- Publicación y visibilidad ---------------------------------------------


def test_el_manager_publicados_es_el_unico_filtro_de_visibilidad(medida, usuarios):
    from apps.medidas.models import Medida

    for estado in ("borrador", "archivado"):
        Medida.objects.filter(pk=medida.pk).update(estado=estado)
        assert not Medida.publicados.filter(pk=medida.pk).exists()

    Medida.objects.filter(pk=medida.pk).update(estado="publicado")
    assert Medida.publicados.filter(pk=medida.pk).exists()


def test_el_html_se_sanea_al_guardar(medida):
    """ADR-D2: el frontend inyecta con `dangerouslySetInnerHTML` y no puede ser la última defensa.

    Se conserva `<oembed>`, que es cómo CKEditor 5 representa un video incrustado.
    """
    medida.contenido = (
        '<p>Texto legítimo</p><script>alert(1)</script>'
        '<figure class="media"><oembed url="https://youtu.be/abc"></oembed></figure>'
    )
    medida.save()
    medida.refresh_from_db()

    assert "<script>" not in medida.contenido
    assert "alert(1)" not in medida.contenido
    assert "Texto legítimo" in medida.contenido
    assert "oembed" in medida.contenido
