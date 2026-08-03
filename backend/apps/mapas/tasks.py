"""Generación de tiles. La implementación completa del pipeline llega en la fase de mapas.

Estos envoltorios existen ya porque el admin y el seed los referencian: sin ellos, la acción
«(Re)generar tiles» fallaría con un ImportError en el worker en vez de con un mensaje legible.
"""
from django_tasks import task


@task()
def generar_tiles_capa(capa_id: int) -> str:
    from apps.mapas.pipeline import generar_capa

    return generar_capa(capa_id)


@task()
def generar_tiles_ccpp() -> str:
    from apps.mapas.pipeline import generar_ccpp

    return generar_ccpp()
