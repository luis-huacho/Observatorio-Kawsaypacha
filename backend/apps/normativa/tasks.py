"""Tareas de normativa: la redacción de una norma desde el enlace a su publicación (ADR-D8).

Corre en el worker (django-tasks, ADR-A3) y respeta la regla transversal del proyecto: **nada de
esto puede tumbar la operación que lo disparó**. El guardado en el admin ya terminó cuando esto
empieza; si la IA falla, la norma sigue ahí y se redacta a mano.

Va en segundo plano y no en el propio `save_model` por el mismo motivo medible que las noticias:
gunicorn corre con `--timeout 120` y 3 workers, y la llamada puede tardar hasta ~120 s (60 s de
timeout más un reintento con backoff). Con un PDF el margen es aún menor, porque OpenRouter tiene
que parsearlo antes de responder.
"""
import logging

from django.core.files.base import ContentFile
from django_tasks import task

from apps.core.models import EstadoIA, slug_unico

logger = logging.getLogger(__name__)

#: Los que la IA escribe. Se listan aquí porque son también los que **no** se pisan si un editor
#: los tocó mientras la tarea estaba en cola.
#:
#: `analisis_predes` NO está, y no es un olvido: es la voz institucional de PREDES, la nota que
#: firma la organización en el listado. Tampoco `url_oficial`, que presenta un enlace como
#: publicación oficial y no puede acabar apuntando a un blog que el editor pegó a mano.
#: Los que son clave foránea, y por eso se leen por `_id`.
FORANEOS = ("tipo", "entidad_emisora")

CAMPOS_REDACTADOS = (
    "titulo", "numero", "tipo", "ambito", "entidad_emisora", "fecha", "resumen",
    "contenido", "palabras_clave", "estado_vigencia",
)


@task()
def redactar_norma_desde_url(pk) -> None:
    """Rellena una norma a partir de `url_origen`, sea una página web o un PDF.

    Dos reglas que no son negociables, heredadas de `apps.contenidos.tasks`:

    - **Nunca pisa una edición humana.** Entre el encolado y este momento pudo entrar un editor;
      pisarle lo escrito sería el peor resultado posible de una función que se llama «de ayuda».
    - **El candado solo se cierra si se llegó a escribir.** Un timeout, una URL caída o un PDF
      escaneado dejan `ia_estado=error` con el detalle a la vista y permiten reintentar.
    """
    from apps.normativa import redaccion
    from apps.normativa.models import Norma

    norma = Norma.objects.filter(pk=pk).first()
    if norma is None or norma.redactada_por_ia or not norma.url_origen:
        return

    norma.ia_estado = EstadoIA.PROCESANDO
    norma.save(update_fields=["ia_estado"])

    try:
        propuesta = redaccion.redactar(norma.url_origen)
    except Exception as exc:  # noqa: BLE001 — el detalle va al log que ve el editor
        norma.ia_estado = EstadoIA.ERROR
        norma.log_ia = (
            f"No se pudo redactar desde {norma.url_origen}:\n{exc}\n\n"
            f"Puedes reintentar marcando de nuevo la casilla, o redactarla a mano; la publicación "
            f"no depende de esto."
        )
        norma.save(update_fields=["ia_estado", "log_ia"])
        logger.warning("La redacción con IA falló para norma %s: %s", pk, exc)
        return

    # Se recarga justo antes de escribir: es la ventana en la que un editor pudo adelantarse.
    norma.refresh_from_db()
    respetados = []
    for campo in CAMPOS_REDACTADOS:
        if _lo_escribio_una_persona(norma, campo):
            respetados.append(campo)
            continue
        setattr(norma, campo, getattr(propuesta, campo))

    if not norma.imagen_portada and propuesta.imagen:
        nombre, contenido = propuesta.imagen
        norma.imagen_portada.save(nombre, ContentFile(contenido), save=False)
        if not norma.imagen_titulo:
            norma.imagen_titulo = propuesta.imagen_titulo

    norma.slug = slug_unico(norma)
    norma.redactada_por_ia = True
    norma.ia_estado = EstadoIA.OK
    norma.log_ia = _bitacora(propuesta, respetados)
    norma.save()


def _lo_escribio_una_persona(norma, campo) -> bool:
    """¿Hay contenido humano en ese campo?

    Aquí es más simple que en noticias, y conviene saber por qué: **ningún campo de `Norma` tiene
    valor por defecto**. `tipo` y `ambito` nacen vacíos, así que «¿está lleno?» sí distingue una
    elección de un relleno automático, y no hace falta la rama especial que ADR-D7 necesitó para
    `Noticia.tipo` —cuyo default «noticia» hacía que la clasificación de la IA no se aplicara nunca—.

    Quedan las dos excepciones de siempre, que son las que puso el admin para poder guardar.
    """
    # Por `_id` en las claves foráneas: `norma.entidad_emisora` dispararía una consulta solo
    # para saber si está vacía.
    valor = getattr(norma, f"{campo}_id" if campo in FORANEOS else campo)
    if campo == "titulo":
        return bool(valor) and not str(valor).startswith(norma.PREFIJO_PROVISIONAL)
    if campo == "fecha":
        return False  # la provisional es la de hoy y es indistinguible de una escrita a mano
    return bool(valor)


def _bitacora(propuesta, respetados) -> str:
    lineas = [
        f"Redactada con {propuesta.modelo} desde la URL de origen.",
        "**Revísala y corrígela antes de publicar.** En particular: el análisis de PREDES lo "
        "escribe una persona, la IA no lo toca; y si la URL de origen es la publicación oficial, "
        "cópiala también en «URL oficial», que es la que ve el público.",
    ]
    if propuesta.costo is not None:
        lineas.append(f"Coste de la llamada: ${propuesta.costo:.6f}.")
    if propuesta.imagen is not None:
        lineas.append(
            "La portada viene de un sitio ajeno: comprueba sus derechos antes de publicar."
        )
    if respetados:
        lineas.append(
            "Se conservó lo que ya estaba escrito a mano en: " + ", ".join(respetados) + "."
        )
    lineas += propuesta.avisos
    return "\n".join(lineas)
