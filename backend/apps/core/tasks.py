"""Tareas comunes: avisos del flujo editorial, resúmenes con IA y agregación de métricas.

Todas corren en el worker (django-tasks, ADR-A3). La regla transversal: **nada de esto puede
tumbar la operación que lo disparó**. Un SMTP caído no debe impedir publicar, y un fallo de
Gemini no debe dejar un documento sin guardar.
"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django_tasks import task

from apps.core.grupos import GRUPOS_REVISORES

logger = logging.getLogger(__name__)

# Transición → (plantilla, a quién se avisa)
PLANTILLAS = {
    ("borrador", "revision"): ("a_revision", "revisores"),
    ("revision", "publicado"): ("publicado", "autor"),
    ("revision", "borrador"): ("devuelto", "autor"),
}


@task()
def notificar_transicion_editorial(
    modelo: str,
    pk,
    titulo: str,
    de_estado: str,
    a_estado: str,
    usuario_id=None,
) -> None:
    """Aviso por correo del flujo editorial (requisito 2 del TDR).

    Solo las tres transiciones que le importan a una persona generan correo. Publicar y
    archivar en cadena, o mover algo entre borradores, no llena la bandeja de nadie: un aviso
    que se ignora deja de ser un aviso.
    """
    plantilla_destino = PLANTILLAS.get((de_estado, a_estado))
    if plantilla_destino is None:
        return
    plantilla, destino = plantilla_destino

    from django.apps import apps as django_apps

    objeto = django_apps.get_model(modelo).objects.filter(pk=pk).first()
    if objeto is None:
        return

    Usuario = get_user_model()
    if destino == "revisores":
        destinatarios = list(
            Usuario.objects.filter(groups__name__in=GRUPOS_REVISORES, is_active=True)
            .exclude(email="")
            .values_list("email", flat=True)
            .distinct()
        )
    else:
        autor = getattr(objeto, "creado_por", None)
        destinatarios = [autor.email] if autor and autor.email else []

    if not destinatarios:
        # Sin destinatarios no hay nada que enviar, pero conviene dejar rastro: es el síntoma
        # de un grupo mal nombrado o de usuarios sin correo, y si no se registra es invisible.
        logger.info(
            "Transición %s → %s de «%s» sin destinatarios (%s).",
            de_estado, a_estado, titulo, destino,
        )
        return

    quien = Usuario.objects.filter(pk=usuario_id).first() if usuario_id else None
    contexto = {
        "titulo": titulo,
        "tipo": objeto._meta.verbose_name,
        "de_estado": de_estado,
        "a_estado": a_estado,
        "usuario": quien,
        "nota_revision": getattr(objeto, "nota_revision", "") or "",
        "url_admin": _url_admin(objeto),
        "url_sitio": settings.SITE_URL,
        "nombre_sitio": "Observatorio Kallpachakuy",
    }

    asuntos = {
        "a_revision": f"«{titulo}» espera revisión",
        "publicado": f"«{titulo}» ya está publicado",
        "devuelto": f"«{titulo}» fue devuelto a borrador",
    }
    cuerpo_html = render_to_string(f"emails/{plantilla}.html", contexto)
    cuerpo_texto = render_to_string(f"emails/{plantilla}.txt", contexto)

    correo = EmailMultiAlternatives(
        subject=f"[Observatorio] {asuntos[plantilla]}",
        body=cuerpo_texto,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=destinatarios,
    )
    correo.attach_alternative(cuerpo_html, "text/html")
    # `fail_silently=False`: si el SMTP falla queremos verlo en el log del worker. La
    # transición ya está guardada, así que el contenido no se pierde por esto.
    correo.send(fail_silently=False)


def _url_admin(objeto) -> str:
    meta = objeto._meta
    try:
        ruta = reverse(f"admin:{meta.app_label}_{meta.model_name}_change", args=[objeto.pk])
    except Exception:  # noqa: BLE001 — un enlace roto no justifica perder el aviso
        return settings.BACKEND_URL
    return f"{settings.BACKEND_URL.rstrip('/')}{ruta}"


@task()
def generar_resumen_ia(modelo: str, pk) -> None:
    """Resumen del PDF con Gemini (ADR-A10).

    Reglas que no son negociables:
    - **Nunca pisa una edición humana**: solo escribe si `resumen` sigue vacío.
    - **La publicación no depende de esto**: cualquier fallo queda en `log_ia` y el documento
      se puede publicar igual, con el resumen escrito a mano.
    """
    from django.apps import apps as django_apps

    from apps.core.services import gemini

    Modelo = django_apps.get_model(modelo)
    objeto = Modelo.objects.filter(pk=pk).first()
    if objeto is None:
        return

    if objeto.resumen and objeto.resumen.strip():
        objeto.ia_estado = "ok"
        objeto.log_ia = "Ya tenía resumen: no se sobreescribe lo redactado a mano."
        objeto.save(update_fields=["ia_estado", "log_ia"])
        return

    objeto.ia_estado = "procesando"
    objeto.save(update_fields=["ia_estado"])
    try:
        contenido = objeto.archivo.read() if objeto.archivo else None
        texto = gemini.generar_resumen(archivo_pdf=contenido, url_pdf=objeto.url_externa)
    except Exception as exc:  # noqa: BLE001 — el detalle va al log que ve el editor
        objeto.ia_estado = "error"
        objeto.log_ia = (
            f"No se pudo generar el resumen: {exc}\n\n"
            f"Redáctalo manualmente; la publicación no depende de esto."
        )
        objeto.save(update_fields=["ia_estado", "log_ia"])
        logger.warning("Gemini falló para %s %s: %s", modelo, pk, exc)
        return

    # Se recarga antes de escribir: entre el encolado y ahora, un editor pudo haber escrito el
    # resumen a mano, y pisárselo sería el peor resultado posible de una función "de ayuda".
    objeto.refresh_from_db()
    if objeto.resumen and objeto.resumen.strip():
        objeto.ia_estado = "ok"
        objeto.log_ia = "Un editor escribió el resumen mientras se generaba: se conserva el suyo."
        objeto.save(update_fields=["ia_estado", "log_ia"])
        return

    objeto.resumen = texto
    objeto.resumen_generado_por_ia = True
    objeto.ia_estado = "ok"
    objeto.log_ia = (
        f"Resumen generado con {settings.GEMINI_MODELO}. Revísalo y corrígelo antes de publicar."
    )
    objeto.save(
        update_fields=["resumen", "resumen_generado_por_ia", "ia_estado", "log_ia"]
    )


@task()
def reindexar_meili(indice: str = "") -> None:
    """Reconstruye uno o todos los índices de búsqueda (spec 04)."""
    from apps.core.services import meili

    if not meili.disponible():
        logger.warning("Meilisearch no responde: se omite la reindexación de «%s».", indice or "todos")
        return
    for slug in ([indice] if indice else list(meili.INDICES)):
        total = meili.reconstruir(slug)
        logger.info("Índice «%s» reconstruido con %s documentos.", slug, total)


@task()
def sincronizar_meili(indice: str, pk: str) -> None:
    """Indexa o borra un documento tras un guardado o un borrado.

    Un Meilisearch caído no puede hacer fallar la tarea de forma ruidosa: el contenido ya está
    guardado, la búsqueda es una función degradable, y `meili_rebuild` recupera el índice.
    """
    from apps.core.services import meili

    if not meili.disponible():
        logger.info("Meilisearch no responde: «%s» %s se sincronizará en el próximo rebuild.",
                    indice, pk)
        return
    try:
        resultado = meili.sincronizar(indice, pk)
        logger.debug("Meili «%s» %s: %s", indice, pk, resultado)
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo sincronizar «%s» %s: %s", indice, pk, exc)


@task()
def agregar_metricas(dias_retencion: int = 90) -> None:
    """Tarea nocturna: agrega `EventoUso` a `ResumenDiario` y purga lo viejo (ADR-A11).

    El agregado es lo que sobrevive: los eventos crudos se borran a los 90 días, así que las
    cifras del dashboard tienen que estar consolidadas antes de la purga o se pierden.
    """
    from datetime import timedelta

    from django.db.models import Count
    from django.db.models.functions import TruncDate
    from django.utils import timezone

    from apps.metricas.models import EventoUso, ResumenDiario

    hoy = timezone.localdate()
    # Se reagrega el día anterior completo y el actual: el actual todavía crece, así que su
    # resumen se sobreescribe en cada corrida en vez de acumularse dos veces.
    desde = hoy - timedelta(days=1)
    filas = (
        EventoUso.objects.filter(fecha__date__gte=desde)
        .annotate(dia=TruncDate("fecha"))
        .values("dia", "tipo", "ruta", "detalle")
        .annotate(n=Count("id"))
    )
    for fila in filas:
        ResumenDiario.objects.update_or_create(
            fecha=fila["dia"],
            tipo=fila["tipo"],
            ruta=fila["ruta"],
            detalle=fila["detalle"] or "",
            defaults={"conteo": fila["n"]},
        )

    limite = timezone.now() - timedelta(days=dias_retencion)
    borrados, _ = EventoUso.objects.filter(fecha__lt=limite).delete()
    logger.info("Métricas agregadas; %s eventos purgados (>%s días).", borrados, dias_retencion)
