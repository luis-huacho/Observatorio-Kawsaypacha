"""Acciones y consultas del panel del admin que no cuelgan de un modelo.

Dos: reindexar la búsqueda —para que PREDES no dependa de que alguien entre al servidor a correr
`manage.py meili_rebuild`— y el estado de la redacción con IA de una noticia, que es lo que permite
a la ficha refrescarse sola cuando el worker termina.
"""
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_GET, require_POST


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


@staff_member_required
@require_GET
def estado_ia_noticia(request, pk):
    """Estado de la redacción con IA de una noticia, para el sondeo de la ficha.

    Existe porque la redacción corre en el worker: sin esto el editor guarda y no tiene forma de
    saber si ya terminó salvo recargar a ciegas. Devuelve lo justo —estado, si quedó bloqueada y el
    registro— y **nada del contenido**, que se ve al recargar.

    Va bajo `ADMIN_URL` y con `staff_member_required`: el `log_ia` puede llevar la URL de origen y
    el detalle de un error del servidor, y eso no es público.
    """
    from apps.contenidos.models import Noticia

    noticia = Noticia.objects.filter(pk=pk).values("ia_estado", "redactada_por_ia", "log_ia").first()
    if noticia is None:
        return JsonResponse({"error": "no existe"}, status=404)
    return JsonResponse(
        {
            "estado": noticia["ia_estado"],
            "redactada": noticia["redactada_por_ia"],
            "log": noticia["log_ia"],
        }
    )
