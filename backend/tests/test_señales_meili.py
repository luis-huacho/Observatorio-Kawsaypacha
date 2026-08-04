"""Las señales que sincronizan la búsqueda tienen que seguir conectadas (spec 04).

Lo que protege: que guardar contenido en el admin **encole** su reindexado. Es la mitad del doble
mecanismo de `apps/core/signals.py` —las señales cubren el día a día, `meili_rebuild` la
recuperación—, y es la mitad que no se nota cuando falta: lo publicado se ve en su página y
simplemente no aparece al buscarlo.

Existe porque esa mitad estuvo rota desde el principio y se descubrió el 04/08/2026, al desplegar
por primera vez contra un servidor real: `manage.py meili_estado` daba los tres índices
editoriales a cero después de sembrar. La causa era que `@receiver` conecta con **referencia
débil** por defecto, y los manejadores eran funciones locales dentro de `_registrar`: el
recolector de basura se los llevaba en cuanto la función retornaba, así que `post_save` se quedaba
sin un solo receptor.

Por eso la prueba mira los receptores vivos **después de un `gc.collect()`**: sin esa llamada
pasaría igual con el error puesto.
"""
import gc
import weakref

from django.db.models.signals import post_delete, post_save

import pytest

from apps.contenidos.models import Noticia
from apps.medidas.models import Medida
from apps.normativa.models import Norma
from apps.peligros.models import TipoPeligro

pytestmark = pytest.mark.django_db

MODELOS_INDEXADOS = [Medida, Norma, Noticia]


def test_los_receptores_se_guardan_con_referencia_fuerte():
    """La prueba que de verdad ataja el error: nada de referencias débiles.

    Es la comprobación estructural y no la de comportamiento porque **el fallo no se reproduce
    bajo pytest**: aquí los manejadores siguen vivos y las señales disparan. Solo aparece en un
    proceso de verdad —gunicorn, el worker, `manage.py shell`—, donde el recolector sí pasa por
    ellos. Medido en el servidor el 04/08/2026: `post_save.receivers` tenía **una sola entrada**,
    con su referencia débil ya muerta, y `Medida.save()` no encolaba nada.

    Así que lo que se fija es la causa, que sí es observable desde aquí: si estas entradas se
    guardan como `weakref`, el error ha vuelto.
    """
    debiles = [
        uid
        for (uid, _), receptor in ((e[0], e[1]) for e in post_save.receivers)
        if isinstance(uid, str)
        and uid.startswith("meili_")
        and isinstance(receptor, weakref.ReferenceType)
    ]

    assert not debiles, (
        f"Estos receptores se conectaron con referencia débil: {debiles}. Son funciones locales "
        f"de `_registrar`, así que el recolector se las lleva en cuanto la función retorna y la "
        f"búsqueda deja de sincronizarse en silencio. Hace falta `weak=False`."
    )


@pytest.mark.parametrize("modelo", MODELOS_INDEXADOS)
def test_las_señales_sobreviven_al_recolector(modelo):
    """Y el efecto: los receptores siguen ahí después de que el GC pase."""
    gc.collect()

    receptores_guardar, _ = post_save._live_receivers(modelo)
    receptores_borrar, _ = post_delete._live_receivers(modelo)

    assert receptores_guardar, (
        f"{modelo.__name__} no tiene receptor de post_save: guardar en el admin no encolará "
        f"su reindexado y el buscador se quedará atrás sin ningún síntoma."
    )
    assert receptores_borrar, f"{modelo.__name__} no tiene receptor de post_delete."


def test_guardar_encola_la_sincronizacion(monkeypatch):
    """Y el receptor hace lo que dice: encolar la tarea con su índice y su pk."""
    encoladas = []
    monkeypatch.setattr(
        "apps.core.signals._encolar",
        lambda slug, pk: encoladas.append((slug, str(pk))),
    )

    peligro = TipoPeligro.objects.create(
        slug="prueba_senales", nombre="Peligro de prueba", hoja_excel="X", orden=99
    )
    medida = Medida.objects.create(
        slug="prueba-senales", titulo="Prueba de señales", tipo_peligro=peligro
    )

    assert ("medidas", str(medida.pk)) in encoladas
