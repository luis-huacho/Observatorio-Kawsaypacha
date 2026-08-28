"""Acciones y consultas del panel del admin que no cuelgan de un modelo.

Dos: reindexar la búsqueda —para que PREDES no dependa de que alguien entre al servidor a
correr `manage.py meili_rebuild`— y el estado de la redacción con IA de una ficha, que es lo
que permite que se refresque sola cuando el worker termina.
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


#: Qué modelos puede consultar el sondeo. Sin lista blanca, la ruta serviría para leer el estado
#: —y el `log_ia`— de cualquier modelo del proyecto que casara con el patrón. Los dos que hay son
#: los que heredan `core.RedaccionIAMixin`.
MODELOS_CON_IA = {"contenidos.noticia", "normativa.norma"}


@staff_member_required
@require_GET
def estado_ia(request, app_label, modelo, pk):
    """Estado de la redacción con IA de una ficha, para el sondeo que la refresca sola.

    Existe porque la redacción corre en el worker: sin esto el editor guarda y no tiene forma de
    saber si ya terminó salvo recargar a ciegas. Devuelve lo justo —estado, si quedó bloqueada y el
    registro— y **nada del contenido**, que se ve al recargar.

    Va bajo `ADMIN_URL` y con `staff_member_required`: el `log_ia` puede llevar la URL de origen y
    el detalle de un error del servidor, y eso no es público.

    Es **uno solo para noticias y normas** (ADR-D8). Por eso los cuatro campos viven en un mixin
    compartido: si cada app hubiera bautizado a su manera el estado o el candado, esta vista
    tendría que saber de las dos.
    """
    from django.apps import apps

    clave = f"{app_label}.{modelo}".lower()
    if clave not in MODELOS_CON_IA:
        return JsonResponse({"error": "no existe"}, status=404)

    Modelo = apps.get_model(app_label, modelo)
    ficha = Modelo.objects.filter(pk=pk).values("ia_estado", "redactada_por_ia", "log_ia").first()
    if ficha is None:
        return JsonResponse({"error": "no existe"}, status=404)
    return JsonResponse(
        {
            "estado": ficha["ia_estado"],
            "redactada": ficha["redactada_por_ia"],
            "log": ficha["log_ia"],
        }
    )
