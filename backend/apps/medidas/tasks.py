"""Tareas de medidas: la redacción de una medida desde una ficha ACC (ADR-D10).

Corre en el worker (django-tasks, ADR-A3) y respeta la regla transversal del proyecto: **nada de
esto puede tumbar la operación que lo disparó**. El guardado en el admin ya terminó cuando esto
empieza; si la IA falla, la medida sigue ahí y se redacta a mano.

Va en segundo plano y no en el propio `save_model` por el mismo motivo medible que las noticias y
las normas: gunicorn corre con `--timeout 120` y 3 workers, y la llamada puede tardar hasta ~120 s
(60 s de timeout más un reintento con backoff).
"""
import logging

from django_tasks import task

from apps.core.models import EstadoIA, slug_unico

logger = logging.getLogger(__name__)

#: Los que la IA escribe. Se listan aquí porque son también los que **no** se pisan si un editor
#: los tocó mientras la tarea estaba en cola.
#:
#: Lo que NO está, y no es un olvido: `destacada` decide la vitrina de la portada y esa es una
#: elección editorial de PREDES; `imagen_portada`, `imagen_titulo`, `video_url`, `enlaces` y
#: `documentos` no tienen de dónde salir —una ficha no trae URL ni imágenes, e inventarlas es la
#: alucinación clásica—; `centro_poblado` exigiría casar una comunidad contra el padrón, que es
#: fabricar una georreferencia; y `ficha_acc` es la procedencia, la eligió el editor.
CAMPOS_REDACTADOS = (
    "titulo", "resumen_corto", "tipo_peligro", "ambito", "resultado", "distrito", "comunidad",
    "contenido", "palabras_clave", "actores", "fecha_implementacion", "costo_referencial",
)

#: Campos donde «vacío» y «cero» no son lo mismo. `Decimal("0.00")` y una fecha son *falsy* en
#: Python, y un aporte comunal sin costo monetario es un dato legítimo que la IA no puede pisar.
CAMPOS_QUE_ADMITEN_CERO = ("fecha_implementacion", "costo_referencial")

#: Los que se comprueban por su `_id`: preguntar por el objeto dispararía una consulta por campo.
CAMPOS_RELACION = ("tipo_peligro", "distrito")


@task()
def redactar_medida_desde_ficha(pk) -> None:
    """Rellena una medida a partir de las respuestas de su ficha ACC.

    Tres reglas que no son negociables, dos heredadas de `apps.normativa.tasks` y una propia:

    - **Nunca pisa una edición humana.** Entre el encolado y este momento pudo entrar un editor.
    - **El candado solo se cierra si se llegó a escribir.** Un timeout deja `ia_estado=error` con
      el detalle a la vista y permite reintentar, y la ficha vuelve a estar disponible.
    - **Una ficha se gasta una sola vez.** El formulario ya lo valida, pero entre validar y
      encolar caben dos peticiones: sin esta guarda, dos guardados simultáneos con la misma ficha
      son dos llamadas a OpenRouter y dos medidas de lo mismo.
    """
    from apps.medidas import redaccion
    from apps.medidas.models import Medida

    medida = Medida.objects.filter(pk=pk).select_related("ficha_acc").first()
    if medida is None or medida.redactada_por_ia or not medida.ficha_acc_id:
        return

    gastada = (
        Medida.objects.filter(ficha_acc_id=medida.ficha_acc_id, redactada_por_ia=True)
        .exclude(pk=medida.pk)
        .exists()
    )
    if gastada:
        medida.ia_estado = EstadoIA.ERROR
        medida.log_ia = (
            "Esta ficha ACC ya se usó para redactar otra medida y cada una solo puede usarse una "
            "vez. Elige otra ficha o redacta esta medida a mano."
        )
        medida.save(update_fields=["ia_estado", "log_ia"])
        return

    medida.ia_estado = EstadoIA.PROCESANDO
    medida.save(update_fields=["ia_estado"])

    try:
        propuesta = redaccion.redactar(medida.ficha_acc)
    except Exception as exc:  # noqa: BLE001 — el detalle va al log que ve el editor
        medida.ia_estado = EstadoIA.ERROR
        medida.log_ia = (
            f"No se pudo redactar desde la ficha ACC #{medida.ficha_acc_id}:\n{exc}\n\n"
            f"Puedes reintentar marcando de nuevo la casilla, o redactarla a mano; la publicación "
            f"no depende de esto."
        )
        medida.save(update_fields=["ia_estado", "log_ia"])
        logger.warning("La redacción con IA falló para medida %s: %s", pk, exc)
        return

    # Se recarga justo antes de escribir: es la ventana en la que un editor pudo adelantarse.
    medida.refresh_from_db()
    respetados = []
    for campo in CAMPOS_REDACTADOS:
        if _lo_escribio_una_persona(medida, campo):
            respetados.append(campo)
            continue
        setattr(medida, campo, getattr(propuesta, campo))

    # El contacto lo pega el servidor, no la IA: nunca salió de la base (ver `redaccion`). Solo
    # si el contenido lo escribió la máquina — si lo escribió una persona, no se toca nada.
    contacto = "" if "contenido" in respetados else medida.bloque_de_contacto()
    if contacto:
        medida.contenido = f"{medida.contenido}{contacto}"

    medida.slug = slug_unico(medida)
    medida.redactada_por_ia = True
    medida.ia_estado = EstadoIA.OK
    medida.log_ia = _bitacora(propuesta, respetados, con_contacto=bool(contacto))
    medida.save()


def _lo_escribio_una_persona(medida, campo) -> bool:
    """¿Hay contenido humano en ese campo?

    Tres diferencias con normativa, todas deliberadas:

    - Las relaciones se miran por su `_id`.
    - `fecha_implementacion` y `costo_referencial` con `is not None` y **no** con `bool()`:
      `Decimal("0.00")` es *falsy*, y un aporte comunal sin costo monetario es un dato legítimo.
    - No hay rama `return False` para la fecha. `Norma.fecha` la necesitaba porque el admin le
      ponía la de hoy y era indistinguible de una escrita a mano; aquí no se provisiona ninguna
      fecha, así que un valor **es** una decisión humana y se respeta.
    """
    if campo == "titulo":
        return bool(medida.titulo) and not str(medida.titulo).startswith(
            medida.PREFIJO_PROVISIONAL
        )
    if campo in CAMPOS_RELACION:
        return getattr(medida, f"{campo}_id") is not None
    if campo in CAMPOS_QUE_ADMITEN_CERO:
        return getattr(medida, campo) is not None
    return bool(getattr(medida, campo))


def _bitacora(propuesta, respetados, *, con_contacto: bool) -> str:
    lineas = [
        f"Redactada con {propuesta.modelo} desde la ficha ACC de origen.",
        "**Revísala y corrígela antes de publicar.** En particular el alcance y el resultado: una "
        "ficha ACC describe una buena práctica, así que casi siempre se clasificará como «éxito» "
        "y eso no siempre es lo que corresponde.",
    ]
    if propuesta.costo is not None:
        lineas.append(f"Coste de la llamada: ${propuesta.costo:.6f}.")
    if con_contacto:
        lineas.append(
            "Al final del contenido se añadió el bloque «Contacto de la experiencia» con los "
            "datos que trae la ficha. **No se le mandaron a la IA**, pero el contenido es "
            "público: bórralo antes de publicar si esa persona no autorizó difundirlos."
        )
    if respetados:
        lineas.append(
            "Se conservó lo que ya estaba escrito a mano en: " + ", ".join(respetados) + "."
        )
    lineas += propuesta.avisos
    return "\n".join(lineas)
