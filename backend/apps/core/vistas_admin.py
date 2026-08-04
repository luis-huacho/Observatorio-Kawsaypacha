"""Acciones del panel del admin que no cuelgan de un modelo.

Por ahora una: reindexar la búsqueda. Existe para que PREDES no dependa de que alguien entre al
servidor a correr `manage.py meili_rebuild` cuando el buscador no encuentre algo publicado.
"""
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect
from django.views.decorators.http import require_POST


@staff_member_required
@require_POST
def reindexar_busqueda(request):
    """Encola la reconstrucción de todos los índices y vuelve al panel.

    **Se encola, no se ejecuta aquí**: reconstruir el índice de centros poblados son ~16 s y 8.968
    documentos, y una petición HTTP no es el sitio para eso. La tarea es la misma que ya usa la
    importación de peligros (`core.tasks.reindexar_meili`).

    Es segura de repetir: `meili.reconstruir` llena un índice temporal y lo intercambia, así que el
    buscador nunca se queda vacío mientras se reconstruye.
    """
    from apps.core.tasks import reindexar_meili

    reindexar_meili.enqueue()
    messages.success(
        request,
        "Se está reconstruyendo la búsqueda. Tarda unos segundos y el buscador sigue funcionando "
        "mientras: recarga esta página para ver los conteos actualizados.",
    )
    return redirect("admin:index")
