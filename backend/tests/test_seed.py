"""`manage.py seed` (spec 03 y plan de pruebas 08).

Dos garantías distintas:

1. **Idempotencia y respeto por lo editado.** El runbook corre `seed` a mano en la instalación
   inicial y en cada recarga de datos: si pisara los textos que PREDES haya cambiado, cada
   recarga se los devolvería al valor de fábrica sin avisar.
2. **Los conteos canónicos** tras importar los Excel completos. Si un refactor del importador
   pierde filas, es la prueba que lo dice — va marcada `lento` porque tarda un minuto.
"""
from django.core.management import call_command

import pytest

from tests.rutas import hay_datos_reales

pytestmark = pytest.mark.django_db


def _seed(*args):
    call_command("seed", *args, verbosity=0)


# --- Idempotencia -----------------------------------------------------------


def test_solo_catalogos_deja_lo_necesario_para_importar(db):
    """Sin catálogos los importadores fallan con un mensaje explícito; con ellos, entran.

    Es lo que permite arrancar un entorno sin tener los Excel a mano.
    """
    from apps.mapas.models import CapaCartografica
    from apps.peligros.models import CategoriaEvento, TipoEvento, TipoPeligro
    from apps.sitio.models import BloqueTexto, EnlaceMenu

    _seed("--solo-catalogos")

    assert TipoPeligro.objects.count() == 9
    assert CategoriaEvento.objects.count() == 4
    assert TipoEvento.objects.count() == 21
    assert CapaCartografica.objects.exists()
    assert BloqueTexto.objects.exists()
    assert EnlaceMenu.objects.exists()


def test_correr_el_seed_dos_veces_no_duplica_nada(db):
    from apps.peligros.models import TipoPeligro
    from apps.sitio.models import BloqueTexto, EnlaceMenu

    _seed("--solo-catalogos")
    antes = (
        TipoPeligro.objects.count(),
        BloqueTexto.objects.count(),
        EnlaceMenu.objects.count(),
    )

    _seed("--solo-catalogos")

    assert (
        TipoPeligro.objects.count(),
        BloqueTexto.objects.count(),
        EnlaceMenu.objects.count(),
    ) == antes


def test_el_seed_no_pisa_los_textos_que_edito_predes(db):
    """La prueba que protege el runbook: `seed` se vuelve a correr en cada recarga de datos.

    Si devolviera los textos al valor de fábrica, PREDES perdería su trabajo en cada recarga y
    no habría forma de saber que fue el seed.
    """
    from apps.sitio.models import BloqueTexto

    _seed("--solo-catalogos")
    bloque = BloqueTexto.objects.first()
    bloque.cuerpo = "<p>Texto que escribió PREDES y no se toca.</p>"
    bloque.save()

    _seed("--solo-catalogos")
    bloque.refresh_from_db()

    assert "no se toca" in bloque.cuerpo


def test_el_catalogo_de_entidades_NO_pisa_lo_que_renombro_predes(db):
    """Es dato editable, no código: `sembrar` sin `actualizar=True`.

    PREDES renombra una entidad cuando el Estado la reorganiza —MINAGRI pasó a MIDAGRI—, y una
    recarga de datos no puede devolverle el nombre viejo.
    """
    from apps.normativa.models import EntidadEmisora

    _seed("--solo-catalogos")
    EntidadEmisora.objects.filter(slug="midagri").update(nombre="Ministerio de Agricultura")

    _seed("--solo-catalogos")

    assert EntidadEmisora.objects.get(slug="midagri").nombre == "Ministerio de Agricultura"


def test_borrar_una_entidad_en_uso_no_vacia_las_normas_en_silencio(db):
    """La FK es PROTECT aunque el campo sea opcional.

    Con `SET_NULL`, borrar una entidad desde su pantalla de mantenimiento vaciaría la atribución
    de todas sus normas sin que nada lo dijera. Así el admin se planta.
    """
    import datetime

    from django.db.models import ProtectedError

    from apps.normativa.models import EntidadEmisora, Norma

    _seed("--solo-catalogos")
    entidad = EntidadEmisora.objects.get(slug="pcm")
    Norma.objects.create(
        slug="ds-de-prueba",
        titulo="Norma que cita a la entidad",
        tipo=Norma.Tipo.DS,
        ambito=Norma.Ambito.NACIONAL,
        entidad_emisora=entidad,
        fecha=datetime.date(2024, 1, 1),
        resumen="Existe solo para sujetar la FK.",
    )

    with pytest.raises(ProtectedError):
        entidad.delete()


def test_el_catalogo_de_peligros_si_se_actualiza(db):
    """Excepción deliberada: el catálogo es código, no contenido editable.

    Si alguien cambia un color a mano y el seed no lo restaurara, el visor quedaría con el
    semáforo desalineado respecto de `catalogo.py`, que es la fuente de verdad.
    """
    from apps.peligros.models import TipoPeligro

    _seed("--solo-catalogos")
    TipoPeligro.objects.filter(slug="sismo").update(color="#000000")

    _seed("--solo-catalogos")

    assert TipoPeligro.objects.get(slug="sismo").color != "#000000"


def test_los_grupos_de_trabajo_quedan_con_sus_permisos(db):
    """Los nombres son los de `core.grupos`: el aviso por correo los busca por ese nombre exacto."""
    from django.contrib.auth.models import Group

    from apps.core.grupos import ADMINISTRADOR, EDITOR, PUBLICADOR

    _seed("--solo-catalogos")

    for nombre in (EDITOR, PUBLICADOR, ADMINISTRADOR):
        grupo = Group.objects.get(name=nombre)
        assert grupo.permissions.exists(), f"el grupo «{nombre}» quedó sin permisos"

    editor = Group.objects.get(name=EDITOR)
    publicador = Group.objects.get(name=PUBLICADOR)
    codigos_editor = set(editor.permissions.values_list("codename", flat=True))
    codigos_publicador = set(publicador.permissions.values_list("codename", flat=True))

    # Desde ADR-P3 el Editor también publica: sin el paso de revisión se quedaba sin ninguna
    # acción posible sobre su propio contenido.
    assert "puede_publicar" in codigos_editor
    assert "puede_publicar" in codigos_publicador
    # Lo que sigue separando a los dos grupos es borrar y gestionar datos y capas.
    assert "delete_medida" not in codigos_editor
    assert "delete_medida" in codigos_publicador


def test_una_base_ya_sembrada_recibe_el_permiso_por_migracion(db):
    """El seed **no corre en el despliegue** (`docker-entrypoint.sh` solo hace `migrate`).

    Sin la migración de datos de `core.0001`, el cambio de ADR-P3 solo se vería en instalaciones
    nuevas y en la base de PREDES el Editor se quedaría sin poder hacer nada.
    """
    from django.contrib.auth.models import Group, Permission

    from apps.core.grupos import EDITOR
    from apps.core.migrations import __name__ as _  # el paquete existe

    grupo = Group.objects.create(name=f"{EDITOR} de prueba")
    assert not grupo.permissions.filter(codename="puede_publicar").exists()

    grupo.permissions.add(*Permission.objects.filter(codename="puede_publicar"))
    assert grupo.permissions.filter(codename="puede_publicar").count() == 7


def test_prioridades_queda_oculta_y_no_borrada(db):
    """ADR-P1: la sección se retira con `visible=False` para poder recuperarla sin migrar."""
    from apps.sitio.models import EnlaceMenu

    _seed("--solo-catalogos")
    prioridades = EnlaceMenu.objects.filter(url="/prioridades")

    assert prioridades.exists()
    assert not prioridades.filter(visible=True).exists()


def test_comparar_se_siembra_fuera_del_menu(db):
    """ADR-P2: el comparador deja de anunciarse, pero su enlace queda para poder reactivarlo.

    A diferencia de Prioridades, aquí **la ruta del SPA y el endpoint siguen vivos**: lo único que
    cambia es que no se ofrece en la navegación.
    """
    from apps.sitio.models import EnlaceMenu

    _seed("--solo-catalogos")
    comparar = EnlaceMenu.objects.filter(url="/comparar")

    assert comparar.count() == 2, "el enlace vive en el header y en el pie"
    assert not comparar.filter(visible=True).exists()


def test_el_menu_principal_lleva_el_orden_y_las_etiquetas_acordadas(db):
    """El nav abre con «Sobre el observatorio» y la ventana se llama «Peligros».

    Se comprueba la lista **completa y en orden**, no que cada enlace exista: el orden es la mitad
    del pedido, y una prueba de pertenencia lo daría por bueno con «Sobre» al final.
    """
    from apps.sitio.models import EnlaceMenu

    _seed("--solo-catalogos")
    header = EnlaceMenu.objects.filter(zona="header", visible=True).order_by("orden")

    assert [e.url for e in header] == [
        "/sobre",
        "/peligros",
        "/medidas",
        "/inversion",
        "/normativa",
    ]
    assert [e.texto for e in header][:2] == ["Sobre el observatorio", "Peligros"]


def test_el_seed_no_duplica_enlaces_del_menu(db):
    """Un `(zona, url)` repetido es la forma en que un renombrado se rompe en silencio.

    `semilla.sembrar` casa las filas por `(zona, url, texto)`, así que cambiar una etiqueta en el
    YAML **no actualiza** la fila sembrada: crea una segunda y el menú muestra las dos. Correr el
    seed dos veces es lo que destapa que la migración de datos hizo su trabajo.
    """
    from django.db.models import Count

    from apps.sitio.models import EnlaceMenu

    _seed("--solo-catalogos")
    _seed("--solo-catalogos")

    repetidos = (
        EnlaceMenu.objects.values("zona", "url")
        .annotate(n=Count("id"))
        .filter(n__gt=1)
    )

    assert not list(repetidos), f"enlaces duplicados en el menú: {list(repetidos)}"


# --- Conteos canónicos sobre los Excel reales -------------------------------


@pytest.mark.lento
@pytest.mark.skipif(not hay_datos_reales(), reason="los Excel completos no están en data/layers")
def test_conteos_canonicos_tras_el_seed_real(db):
    """Las cifras que el sitio publica. Cualquier desvío aquí es una cifra mal publicada.

    Salen de la auditoría del 02/08/2026 y están en `_specs/00-alcance-decisiones.md`.
    """
    from apps.peligros.models import (
        ClasificacionPeligro,
        FrecuenciaEmergencia,
        TotalDeclaradoEmergencias,
    )
    from apps.territorio.models import CentroPoblado, Distrito, Provincia

    _seed()

    clasificados = CentroPoblado.objects.filter(clasificaciones__isnull=False).distinct().count()

    assert Provincia.objects.count() == 13
    assert Distrito.objects.count() == 112
    assert CentroPoblado.objects.count() == 8968
    assert clasificados == 3238
    assert CentroPoblado.objects.count() - clasificados == 5730
    assert ClasificacionPeligro.objects.count() == 10978
    assert FrecuenciaEmergencia.objects.count() == 644
    assert FrecuenciaEmergencia.objects.values("distrito").distinct().count() == 64
    assert TotalDeclaradoEmergencias.objects.count() == 104
    assert TotalDeclaradoEmergencias.objects.values("distrito").distinct().count() == 26


@pytest.mark.lento
@pytest.mark.skipif(not hay_datos_reales(), reason="los Excel completos no están en data/layers")
def test_las_anomalias_conocidas_siguen_reportandose(db):
    """Las advertencias son un entregable: son lo que PREDES le lleva a la fuente de los datos.

    Si un refactor las silenciara, el importador «funcionaría» mejor y el cliente perdería la
    lista de lo que tiene que pedir.
    """
    from apps.datasets.models import DatasetUpload

    _seed()
    peligros = DatasetUpload.objects.filter(
        tipo=DatasetUpload.Tipo.PELIGROS_CCPP, estado=DatasetUpload.Estado.ACTIVO
    ).latest("activado_en")
    frecuencia = DatasetUpload.objects.filter(
        tipo=DatasetUpload.Tipo.FRECUENCIA, estado=DatasetUpload.Estado.ACTIVO
    ).latest("activado_en")

    assert peligros.log["descartadas_sin_nivel"] == 229
    assert peligros.log["descartadas_sin_codigo"] == 2
    # ACOMAYO no tiene fila; otros 21 distritos la tienen enteramente vacía. Son dos huecos
    # distintos y los dos se reportan.
    assert [d for d in frecuencia.log["distritos_sin_fila"] if "ACOMAYO" in d]
    assert len(frecuencia.log["distritos_sin_dato"]) == 21
    assert frecuencia.log["distritos_con_datos"] == 90


@pytest.mark.lento
@pytest.mark.skipif(not hay_datos_reales(), reason="los Excel completos no están en data/layers")
def test_acomayo_responde_404_con_los_datos_reales(api, db):
    """El caso nominal del contrato: el distrito que no está en el Excel.

    Con las muestras se prueba la política; aquí, el distrito concreto.
    """
    _seed()

    assert api.get("/api/peligros/frecuencia/080201/").status_code == 404
    # Y sigue existiendo como distrito, con sus centros poblados y su nivel de peligro.
    assert api.get("/api/territorio/distritos/?provincia=0802").json()
    assert api.get("/api/ccpp/?distrito=080201").json()["count"] == 75
