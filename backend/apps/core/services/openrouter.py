"""Cliente de OpenRouter para los usos de IA del observatorio (ADR-A22).

Es la capa compartida: la usan las tareas del worker, las acciones del admin y los comandos de
`manage.py`. No sabe nada de modelos de Django ni de la cola — recibe mensajes y devuelve una
`Respuesta`.

Por qué OpenRouter y no un SDK por proveedor: un solo secreto y un solo cliente para cualquier
modelo, elegido con `OPENROUTER_MODELO`. Y por qué la librería `openai`: OpenRouter expone la API
de OpenAI, así que su cliente **es** ese SDK apuntado a otra `base_url`. Gemini sigue aparte
(ADR-A10) porque lee el PDF de forma nativa, que es lo que necesita el resumen de la biblioteca.

Cuatro cosas que este módulo resuelve una vez para que nadie tenga que redescubrirlas:

1. **El razonamiento se conserva entre turnos.** OpenRouter devuelve `reasoning_details` en el
   mensaje del asistente y exige que se reenvíe **sin modificar ni reordenar**; si se altera la
   secuencia, el modelo no puede continuar desde donde se quedó. Eso lo hace `Respuesta.como_mensaje()`.
2. **`reasoning_details` es un campo extra del SDK, no uno declarado.** Los modelos de `openai`
   admiten campos adicionales (`extra="allow"`), así que el atributo existe cuando el proveedor lo
   manda y **no existe** cuando no. Se lee con `getattr(..., None)`: escribirlo como atributo
   directo funciona hasta el primer modelo que no razona, y ahí revienta en vez de degradarse.
3. **Timeout y reintentos van en el cliente**, no en un bucle propio: el SDK ya reintenta con
   backoff ante 429 y 5xx. Es lo que pide `_specs/03-admin-editorial.md` y lo que la integración
   con Gemini nunca llegó a tener.
4. **El modelo sale de `settings`**, nunca escrito a fuego — el desajuste que hoy tiene
   `services/gemini.py`, que ignora su propia variable.

El servicio **lanza**; no registra ni traga errores. El log y el estado visible para el editor los
pone quien llama (ver `apps/core/tasks.py`), que es la frontera que permite que un fallo de IA no
tumbe nunca la operación que lo disparó.
"""
from dataclasses import dataclass
from typing import Any

from django.conf import settings

Mensaje = dict[str, Any]


def cliente(timeout: float | None = None, reintentos: int | None = None):
    """El cliente de `openai` apuntado a OpenRouter."""
    if not settings.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY no configurada en backend/.env")

    from openai import OpenAI

    return OpenAI(
        base_url=settings.OPENROUTER_BASE_URL,
        api_key=settings.OPENROUTER_API_KEY,
        timeout=settings.OPENROUTER_TIMEOUT if timeout is None else timeout,
        max_retries=settings.OPENROUTER_REINTENTOS if reintentos is None else reintentos,
        # Atribución de OpenRouter: son opcionales y gratis, y sin ellas el consumo aparece
        # anónimo en su panel, que es donde se revisa el gasto.
        default_headers={
            "HTTP-Referer": settings.SITE_URL,
            "X-Title": "Observatorio Kallpachakuy",
        },
    )


@dataclass(frozen=True)
class Respuesta:
    """Lo que hace falta de una respuesta: el texto, con qué se pagó y cómo continuarla."""

    texto: str
    #: `reasoning_details` **tal cual llegó**. No se normaliza ni se reordena a propósito.
    razonamiento: list | None
    modelo: str
    tokens: dict
    #: OpenRouter lo devuelve en `usage.cost`, en créditos. `None` si el proveedor no lo informa.
    costo: float | None

    def como_mensaje(self) -> Mensaje:
        """El turno del asistente, listo para reenviarse en la llamada siguiente.

        La clave `reasoning_details` **se omite** cuando no hubo razonamiento, en vez de mandarse
        a `null`: un turno con la clave vacía no es lo mismo que un turno sin ella.
        """
        mensaje: Mensaje = {"role": "assistant", "content": self.texto}
        if self.razonamiento is not None:
            mensaje["reasoning_details"] = self.razonamiento
        return mensaje


def completar(
    mensajes: list[Mensaje],
    *,
    modelo: str | None = None,
    razonamiento: bool | dict | None = None,
    timeout: float | None = None,
    **opciones: Any,
) -> Respuesta:
    """Una llamada a `chat.completions`.

    `razonamiento` acepta tres formas y ninguna se traduce a otra: `None` no manda nada y deja
    mandar al default del proveedor; `True`/`False` habilitan o deshabilitan; un `dict` viaja tal
    cual, que es como se piden `effort`, `max_tokens` o `exclude`. Inventar aquí un vocabulario
    propio solo añadiría una capa que traducir mal.

    **`None` no significa «sin razonamiento»**, y la diferencia se paga: hay modelos que razonan
    por defecto —el `deepseek-v4-flash` que viene configurado, sin ir más lejos—, así que para no
    pagar esos tokens hay que pasar `False`. `{"exclude": True}` es otra cosa: el modelo razona
    igual y **se cobra igual**, solo que no devuelve los bloques.

    `**opciones` pasa directo al SDK (`temperature`, `max_tokens`, `response_format`…).
    """
    if not mensajes:
        raise ValueError("Se requiere al menos un mensaje")

    extra_body = dict(opciones.pop("extra_body", None) or {})
    if razonamiento is not None:
        extra_body["reasoning"] = (
            razonamiento if isinstance(razonamiento, dict) else {"enabled": razonamiento}
        )

    respuesta = cliente(timeout=timeout).chat.completions.create(
        model=modelo or settings.OPENROUTER_MODELO,
        messages=mensajes,
        **({"extra_body": extra_body} if extra_body else {}),
        **opciones,
    )

    elegida = respuesta.choices[0].message
    uso = respuesta.usage
    return Respuesta(
        texto=(elegida.content or "").strip(),
        razonamiento=getattr(elegida, "reasoning_details", None),
        modelo=getattr(respuesta, "model", "") or "",
        tokens={
            "entrada": getattr(uso, "prompt_tokens", None) if uso else None,
            "salida": getattr(uso, "completion_tokens", None) if uso else None,
            "total": getattr(uso, "total_tokens", None) if uso else None,
        },
        costo=getattr(uso, "cost", None) if uso else None,
    )
