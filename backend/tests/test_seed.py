"""`manage.py seed` (spec 03 y plan de pruebas 08).

Dos garantías distintas:

1. **Idempotencia y respeto por lo editado.** El runbook corre `seed` en cada despliegue: si
   pisara los textos que PREDES haya cambiado, cada actualización se los devolvería al valor de
   fábrica sin avisar.
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
    """La prueba que protege el runbook: `seed` corre en cada despliegue.

    Si devolviera los textos al valor de fábrica, PREDES perdería su trabajo en cada
    actualización y no habría forma de saber que fue el despliegue.
    """
    from apps.sitio.models import BloqueTexto

    _seed("--solo-catalogos")
    bloque = BloqueTexto.objects.first()
    bloque.cuerpo = "<p>Texto que escribió PREDES y no se toca.</p>"
    bloque.save()

    _seed("--solo-catalogos")
    bloque.refresh_from_db()

    assert "no se toca" in bloque.cuerpo


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

    assert "puede_publicar" not in codigos_editor
    assert "puede_publicar" in codigos_publicador


def test_prioridades_queda_oculta_y_no_borrada(db):
    """ADR-P1: la sección se retira con `visible=False` para poder recuperarla sin migrar."""
    from apps.sitio.models import EnlaceMenu

    _seed("--solo-catalogos")
    prioridades = EnlaceMenu.objects.filter(url="/prioridades")

    assert prioridades.exists()
    assert not prioridades.filter(visible=True).exists()


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
