"""Tareas de contenidos: la redacción de una noticia desde su URL de origen (ADR-D7).

Corre en el worker (django-tasks, ADR-A3) y respeta la regla transversal del proyecto: **nada de
esto puede tumbar la operación que lo disparó**. El guardado en el admin ya terminó cuando esto
empieza; si la IA falla, la noticia sigue ahí y se redacta a mano.

Va en segundo plano y no en el propio `save_model` por un motivo medible: gunicorn corre con
`--timeout 120` y 3 workers, y la llamada puede tardar hasta ~120 s (60 s de timeout más un
reintento con backoff). Síncrono, gunicorn mataría al worker justo en el límite y el editor vería
un 502 con el guardado a medias, mientras tres redacciones a la vez dejarían el admin sin atender.
"""
import logging

from django.core.files.base import ContentFile
from django_tasks import task

from apps.core.models import EstadoIA, slug_unico

logger = logging.getLogger(__name__)

#: Los que la IA escribe. Se listan aquí porque son también los que **no** se pisan si un editor
#: los tocó mientras la tarea estaba en cola.
CAMPOS_REDACTADOS = ("titulo", "bajada", "cuerpo", "tipo", "autor", "fecha", "palabras_clave")


@task()
def redactar_noticia_desde_url(pk) -> None:
    """Rellena una noticia a partir de `url_origen`.

    Dos reglas que no son negociables, heredadas de `apps.core.tasks.generar_resumen_ia`:

    - **Nunca pisa una edición humana.** Entre el encolado y este momento pudo entrar un editor;
      pisarle lo escrito sería el peor resultado posible de una función que se llama «de ayuda».
    - **El candado solo se cierra si se llegó a escribir.** Un timeout o una URL caída dejan
      `ia_estado=error` con el detalle a la vista y permiten reintentar: un corte de red no debería
      inutilizar la noticia para siempre.
    """
    from apps.contenidos import redaccion
    from apps.contenidos.models import Noticia

    noticia = Noticia.objects.filter(pk=pk).first()
    if noticia is None or noticia.redactada_por_ia or not noticia.url_origen:
        return

    noticia.ia_estado = EstadoIA.PROCESANDO
    noticia.save(update_fields=["ia_estado"])

    try:
        propuesta = redaccion.redactar(noticia.url_origen)
    except Exception as exc:  # noqa: BLE001 — el detalle va al log que ve el editor
        noticia.ia_estado = EstadoIA.ERROR
        noticia.log_ia = (
            f"No se pudo redactar desde {noticia.url_origen}:\n{exc}\n\n"
            f"Puedes reintentar marcando de nuevo la casilla, o redactarla a mano; la publicación "
            f"no depende de esto."
        )
        noticia.save(update_fields=["ia_estado", "log_ia"])
        logger.warning("La redacción con IA falló para noticia %s: %s", pk, exc)
        return

    # Se recarga justo antes de escribir: es la ventana en la que un editor pudo adelantarse.
    noticia.refresh_from_db()
    respetados = []
    for campo in CAMPOS_REDACTADOS:
        if _lo_escribio_una_persona(noticia, campo):
            respetados.append(campo)
            continue
        setattr(noticia, campo, getattr(propuesta, campo))

    if not noticia.imagen_portada and propuesta.imagen:
        nombre, contenido = propuesta.imagen
        noticia.imagen_portada.save(nombre, ContentFile(contenido), save=False)
        if not noticia.imagen_titulo:
            noticia.imagen_titulo = propuesta.imagen_titulo

    noticia.slug = slug_unico(noticia)
    noticia.redactada_por_ia = True
    noticia.ia_estado = EstadoIA.OK
    noticia.log_ia = _bitacora(propuesta, respetados)
    noticia.save()


def _lo_escribio_una_persona(noticia, campo) -> bool:
    """¿Hay contenido humano en ese campo?

    El título y el slug provisionales que puso el admin **no cuentan**: los escribió la máquina
    para poder guardar, y confundirlos con una edición dejaría la noticia llamándose
    «(redactando) …» para siempre.
    """
    from apps.contenidos.models import Noticia

    valor = getattr(noticia, campo)
    if campo == "titulo":
        return bool(valor) and not str(valor).startswith(Noticia.PREFIJO_PROVISIONAL)
    if campo == "fecha":
        return False  # la provisional es la de hoy y es indistinguible de una escrita a mano
    if campo == "tipo":
        # `tipo` SIEMPRE tiene valor —su default es «noticia»—, así que «¿está lleno?» no
        # distingue una elección de un valor por defecto. Sin esta rama, la clasificación de la IA
        # no se aplicaba nunca y el registro decía «se conservó lo escrito a mano» sobre algo que
        # nadie había escrito. Se respeta solo un valor distinto del default, que sí es una
        # decisión deliberada del editor.
        return valor != Noticia.Tipo.NOTICIA
    return bool(valor)


def _bitacora(propuesta, respetados) -> str:
    lineas = [
        f"Redactada con {propuesta.modelo} desde la URL de origen.",
        "**Revísala y corrígela antes de publicar**, incluidos los derechos de la imagen: viene "
        "de un sitio ajeno.",
    ]
    if propuesta.costo is not None:
        lineas.append(f"Coste de la llamada: ${propuesta.costo:.6f}.")
    if respetados:
        lineas.append(
            "Se conservó lo que ya estaba escrito a mano en: " + ", ".join(respetados) + "."
        )
    lineas += propuesta.avisos
    return "\n".join(lineas)
