"""Sincronización de la búsqueda por señales (spec 04).

Doble mecanismo a propósito: las señales cubren el día a día y `meili_rebuild` la recuperación.
Solo con señales, cualquier escritura fuera del ORM —un import masivo, un `update()` de
queryset— dejaría el índice desincronizado sin manera de notarlo.

La tarea se **encola**: indexar dentro del `save()` haría que un Meilisearch lento o caído
bloqueara el admin, y peor, que un fallo de búsqueda impidiera guardar contenido.
"""
import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _registrar(slug: str, etiqueta_modelo: str):
    from django.apps import apps as django_apps

    modelo = django_apps.get_model(etiqueta_modelo)

    # `weak=False` no es opcional, y es el error que este archivo tuvo desde el principio.
    #
    # `@receiver` conecta con referencia DÉBIL por defecto, y estos dos manejadores son funciones
    # locales: en cuanto `_registrar` retorna nadie más los referencia, el recolector se los lleva
    # y la señal se queda con una referencia muerta. El efecto es exactamente el que este archivo
    # dice evitar —el índice deja de sincronizarse— y además es invisible: lo publicado se ve en
    # su página y simplemente no aparece al buscarlo. Medido en el servidor el 04/08/2026, antes
    # del arreglo: `post_save.receivers` tenía UNA entrada, muerta, y `save()` no encolaba nada.
    #
    # Con `dispatch_uid` es peor de lo que parece, porque la entrada muerta se queda en el
    # registro con su clave: un segundo `conectar()` la ve ocupada y **no vuelve a conectar**.
    @receiver(post_save, sender=modelo, dispatch_uid=f"meili_save_{slug}", weak=False)
    def _al_guardar(sender, instance, **kwargs):
        _encolar(slug, instance.pk)

    @receiver(post_delete, sender=modelo, dispatch_uid=f"meili_delete_{slug}", weak=False)
    def _al_borrar(sender, instance, **kwargs):
        _encolar(slug, instance.pk)


def _encolar(slug: str, pk) -> None:
    from apps.core.tasks import sincronizar_meili

    try:
        sincronizar_meili.enqueue(indice=slug, pk=str(pk))
    except Exception as exc:  # noqa: BLE001
        # Si ni siquiera se puede encolar (base de tareas caída), se registra y se sigue: el
        # contenido ya está guardado y `meili_rebuild` recupera el índice.
        logger.warning("No se pudo encolar la sincronización de %s %s: %s", slug, pk, exc)


def conectar() -> None:
    """Conecta las señales de los índices editoriales.

    El índice `ccpp` queda fuera: se reconstruye completo tras cada importación de peligros, y
    conectar señales a 8,968 filas convertiría un import en 8,968 tareas encoladas.
    """
    from apps.core.services.meili import INDICES

    for slug, indice in INDICES.items():
        if slug == "ccpp":
            continue
        _registrar(slug, indice.modelo)
