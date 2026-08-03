"""Flujo editorial (spec 03): transiciones, permisos y avisos por correo.

Lo que se protege aquí es que **la revisión signifique algo**: que no se pueda publicar sin pasar
por ella, que no pueda publicar quien no debe, y que el aviso llegue a alguien. Los tres fallos
de esta familia son silenciosos —el contenido se guarda, la operación «funciona»— así que sin
pruebas no se notan hasta que alguien pregunta por un correo que nunca llegó.
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


def test_no_se_puede_publicar_sin_pasar_por_revision(medida, usuarios):
    """`borrador → publicado` directo no existe. Si existiera, la revisión sería opcional."""
    with pytest.raises(ValueError, match="Transición inválida"):
        medida.transicionar("publicado", usuario=usuarios["publicador"])

    medida.refresh_from_db()
    assert medida.estado == "borrador"


def test_el_camino_completo_funciona(medida, usuarios):
    medida.transicionar("revision", usuario=usuarios["editor"])
    assert medida.estado == "revision"

    medida.transicionar("publicado", usuario=usuarios["publicador"])
    assert medida.estado == "publicado"

    medida.transicionar("archivado", usuario=usuarios["publicador"])
    assert medida.estado == "archivado"


def test_publicar_sella_la_fecha(medida, usuarios):
    """`publicado_en` ordena los listados y sale en las fichas: no puede quedarse vacío."""
    medida.transicionar("revision", usuario=usuarios["editor"])
    medida.transicionar("publicado", usuario=usuarios["publicador"])

    assert medida.publicado_en is not None
    assert medida.revisado_por == usuarios["publicador"]


def test_un_editor_no_puede_publicar_lo_que_escribio(medida, usuarios):
    """Es el punto del flujo: cuatro ojos antes de que algo salga al sitio público."""
    medida.transicionar("revision", usuario=usuarios["editor"])

    with pytest.raises(PermissionError):
        medida.transicionar("publicado", usuario=usuarios["editor"])

    medida.refresh_from_db()
    assert medida.estado == "revision"


def test_el_admin_no_ofrece_transiciones_que_van_a_fallar(medida, usuarios):
    """Las acciones se filtran por permiso: un botón que salta un error no es una opción."""
    medida.estado = "revision"

    assert "publicado" in medida.transiciones_posibles(usuarios["publicador"])
    assert "publicado" not in medida.transiciones_posibles(usuarios["editor"])
    # Devolver a borrador sí puede hacerlo cualquiera de los dos.
    assert "borrador" in medida.transiciones_posibles(usuarios["editor"])


def test_un_superusuario_puede_publicar_sin_estar_en_el_grupo(medida):
    from django.contrib.auth import get_user_model

    admin = get_user_model().objects.create_superuser(
        username="admin-pruebas", email="admin@predes.test", password="x"
    )
    medida.transicionar("revision", usuario=admin)
    medida.transicionar("publicado", usuario=admin)

    assert medida.estado == "publicado"


# --- Avisos por correo ------------------------------------------------------


def test_enviar_a_revision_avisa_a_los_revisores(medida, usuarios):
    """El grupo se resuelve por las constantes de `core.grupos`.

    La primera versión buscaba «Publicadores» mientras el seed creaba «Publicador»: los avisos no
    llegaban a nadie y la tarea terminaba bien, así que el fallo era invisible desde fuera.
    """
    mail.outbox.clear()
    medida.transicionar("revision", usuario=usuarios["editor"])
    enviados = _correos_encolados()

    assert len(enviados) == 1
    assert usuarios["publicador"].email in enviados[0].to
    assert medida.titulo in enviados[0].subject + enviados[0].body


def test_publicar_avisa_a_quien_lo_escribio(medida, usuarios):
    medida.transicionar("revision", usuario=usuarios["editor"])
    _correos_encolados()
    mail.outbox.clear()

    medida.transicionar("publicado", usuario=usuarios["publicador"])
    enviados = _correos_encolados()

    assert len(enviados) == 1
    assert enviados[0].to == [usuarios["editor"].email]


def test_devolver_a_borrador_lleva_las_observaciones_en_el_correo(medida, usuarios):
    """Es el único sitio donde se le puede explicar al autor qué corregir.

    Si la nota no viajara en el correo, el autor vería su contenido de vuelta en borrador sin
    saber por qué, y tendría que entrar al admin a buscarla.
    """
    medida.transicionar("revision", usuario=usuarios["editor"])
    _correos_encolados()
    mail.outbox.clear()

    medida.nota_revision = "Falta citar la fuente de la cifra de familias."
    medida.transicionar("borrador", usuario=usuarios["publicador"])
    enviados = _correos_encolados()

    assert len(enviados) == 1
    assert enviados[0].to == [usuarios["editor"].email]
    assert "Falta citar la fuente" in enviados[0].body


def test_archivar_no_llena_la_bandeja_de_nadie(medida, usuarios):
    """Solo las tres transiciones que le importan a una persona generan correo.

    Un aviso que se ignora deja de ser un aviso.
    """
    medida.transicionar("revision", usuario=usuarios["editor"])
    medida.transicionar("publicado", usuario=usuarios["publicador"])
    _correos_encolados()
    mail.outbox.clear()

    medida.transicionar("archivado", usuario=usuarios["publicador"])

    assert _correos_encolados() == []


def test_sin_destinatarios_la_transicion_sigue_adelante(medida, usuarios):
    """Un buzón mal configurado no puede impedir publicar.

    Queda registrado en el log —es el síntoma de un grupo mal nombrado o de usuarios sin correo—
    pero la operación editorial no se bloquea por ello.
    """
    usuarios["publicador"].email = ""
    usuarios["publicador"].save()
    mail.outbox.clear()

    medida.transicionar("revision", usuario=usuarios["editor"])

    assert medida.estado == "revision"
    assert _correos_encolados() == []


# --- Publicación y visibilidad ---------------------------------------------


def test_el_manager_publicados_es_el_unico_filtro_de_visibilidad(medida, usuarios):
    from apps.medidas.models import Medida

    for estado in ("borrador", "revision", "archivado"):
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
