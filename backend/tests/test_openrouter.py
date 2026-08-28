"""Cliente de OpenRouter (ADR-A22).

Lo que protege: la **continuidad del razonamiento entre turnos**, que es lo único de esta
integración que puede romperse sin dar ningún error. OpenRouter exige que `reasoning_details` se
reenvíe idéntico y en el mismo orden; si se altera, la segunda llamada responde igual de bien y el
modelo, simplemente, ya no continúa desde donde se quedó. No hay excepción, ni aviso, ni diferencia
visible en la respuesta.

El cliente es falso y no hay red: lo que se fija aquí es **con qué se llama al SDK** y **qué se
hace con lo que devuelve**, no que OpenRouter sepa responder.
"""
from io import StringIO

import pytest

from apps.core.services import openrouter

RAZONAMIENTO = [
    {"type": "reasoning.text", "text": "Cuento las erres de fresa."},
    {"type": "reasoning.text", "text": "Son tres."},
]


class MensajeFalso:
    """El mensaje del asistente.

    `reasoning_details` **solo existe si se pasa**, igual que en el SDK real: sus modelos admiten
    campos extra, así que el atributo está ausente —no a `None`— cuando el proveedor no lo manda.
    Es lo que obliga a leerlo con `getattr` y lo que esta clase reproduce a propósito.
    """

    def __init__(self, content, reasoning_details=None):
        self.content = content
        if reasoning_details is not None:
            self.reasoning_details = reasoning_details


class UsoFalso:
    def __init__(self, cost=None):
        self.prompt_tokens = 11
        self.completion_tokens = 22
        self.total_tokens = 33
        if cost is not None:
            self.cost = cost


class ClienteFalso:
    """Registra cada llamada en `self.llamadas` y devuelve las respuestas que se le den.

    **No expone nada más que `chat.completions.create`.** Si el servicio empezara a usar otra parte
    del SDK, estas pruebas fallarían con `AttributeError`, que es lo que se busca: la superficie de
    esta integración tiene que seguir siendo una sola llamada.
    """

    def __init__(self, respuestas):
        self._respuestas = list(respuestas)
        self.llamadas = []
        cliente = self

        class Completions:
            def create(self, **kwargs):
                cliente.llamadas.append(kwargs)
                return cliente._respuestas.pop(0)

        class Chat:
            completions = Completions()

        self.chat = Chat()


def respuesta_falsa(texto, razonamiento=None, modelo="modelo/de-prueba", costo=None):
    class Respuesta:
        choices = [type("Opcion", (), {"message": MensajeFalso(texto, razonamiento)})()]
        usage = UsoFalso(costo)
        model = modelo

    return Respuesta()


@pytest.fixture
def openrouter_falso(monkeypatch, settings):
    """Instala un cliente falso con las respuestas que se le digan y devuelve el registro."""

    def instalar(*respuestas):
        settings.OPENROUTER_API_KEY = "llave-de-prueba"
        settings.OPENROUTER_MODELO = "modelo/por-defecto"
        falso = ClienteFalso(respuestas)
        monkeypatch.setattr(
            openrouter, "cliente", lambda timeout=None, reintentos=None: falso
        )
        return falso

    return instalar


def test_sin_llave_se_dice_que_falta_y_donde_ponerla(settings):
    """El mensaje nombra la variable y el archivo.

    Quien lo lee suele ser quien despliega, no quien programó: «falta la llave» sin decir cuál ni
    dónde obliga a leer el código para averiguarlo.
    """
    settings.OPENROUTER_API_KEY = ""

    with pytest.raises(RuntimeError) as error:
        openrouter.cliente()

    assert "OPENROUTER_API_KEY" in str(error.value)
    assert "backend/.env" in str(error.value)


def test_el_cliente_lleva_timeout_y_reintentos_y_el_modelo_sale_de_settings(settings):
    """La integración con Gemini no tiene ninguna de las tres cosas; ésta no debe repetirlo.

    Sin timeout, un proveedor que acepta la conexión y no contesta cuelga al worker con la tarea a
    medias. Y con el modelo escrito a fuego, cambiarlo exige tocar código y desplegar.
    """
    settings.OPENROUTER_API_KEY = "llave-de-prueba"

    real = openrouter.cliente()

    assert real.timeout == settings.OPENROUTER_TIMEOUT
    assert real.max_retries == settings.OPENROUTER_REINTENTOS
    assert str(real.base_url).startswith(settings.OPENROUTER_BASE_URL)
    assert settings.OPENROUTER_MODELO  # el default vive en settings, no en el servicio


def test_completar_devuelve_texto_uso_y_el_razonamiento_intacto(openrouter_falso):
    falso = openrouter_falso(
        respuesta_falsa("Hay tres.", RAZONAMIENTO, modelo="modelo/real", costo=0.00012)
    )

    respuesta = openrouter.completar(
        [{"role": "user", "content": "¿Cuántas erres tiene 'fresa'?"}], razonamiento=True
    )

    assert respuesta.texto == "Hay tres."
    # Idéntico, no equivalente: es el objeto que llegó, sin normalizar.
    assert respuesta.razonamiento == RAZONAMIENTO
    assert respuesta.modelo == "modelo/real"
    assert respuesta.tokens == {"entrada": 11, "salida": 22, "total": 33}
    assert respuesta.costo == 0.00012
    assert falso.llamadas[0]["model"] == "modelo/por-defecto"


def test_una_respuesta_sin_razonamiento_no_inventa_la_clave(openrouter_falso):
    """El modelo que no razona deja el atributo AUSENTE, no a `None`.

    Si el servicio lo leyera como atributo directo, esta llamada reventaría con `AttributeError`
    en vez de devolver una respuesta perfectamente válida.
    """
    openrouter_falso(respuesta_falsa("Sin pensar."))

    respuesta = openrouter.completar([{"role": "user", "content": "Hola"}])

    assert respuesta.razonamiento is None
    # Y el turno reenviable no lleva la clave: vacía no es lo mismo que ausente.
    assert respuesta.como_mensaje() == {"role": "assistant", "content": "Sin pensar."}


def test_el_segundo_turno_reenvia_los_bloques_sin_tocarlos(openrouter_falso):
    """La prueba que sostiene el módulo entero.

    Reordenar o reescribir los bloques rompe la continuidad **sin dar ningún error**: la segunda
    llamada responde igual de bien y el modelo ya no retoma su razonamiento anterior.
    """
    falso = openrouter_falso(
        respuesta_falsa("Hay tres.", RAZONAMIENTO),
        respuesta_falsa("Sí, tres.", RAZONAMIENTO),
    )

    primera = openrouter.completar(
        [{"role": "user", "content": "¿Cuántas erres tiene 'fresa'?"}], razonamiento=True
    )

    historial = [
        {"role": "user", "content": "¿Cuántas erres tiene 'fresa'?"},
        primera.como_mensaje(),
        {"role": "user", "content": "¿Seguro? Piénsalo con calma."},
    ]
    openrouter.completar(historial, razonamiento=True)

    turno_asistente = falso.llamadas[1]["messages"][1]
    assert turno_asistente["role"] == "assistant"
    assert turno_asistente["content"] == "Hay tres."
    assert turno_asistente["reasoning_details"] == RAZONAMIENTO
    assert turno_asistente["reasoning_details"] is primera.razonamiento


@pytest.mark.parametrize(
    ("razonamiento", "esperado"),
    [
        (None, None),
        (True, {"enabled": True}),
        (False, {"enabled": False}),
        ({"effort": "high", "exclude": True}, {"effort": "high", "exclude": True}),
    ],
)
def test_el_razonamiento_viaja_en_extra_body_sin_traducirse(
    openrouter_falso, razonamiento, esperado
):
    """`None` no manda nada y deja mandar al default del proveedor; un `dict` viaja tal cual.

    Traducir aquí `effort`/`max_tokens`/`exclude` a un vocabulario propio solo añadiría una capa
    que mantener sincronizada con OpenRouter.
    """
    falso = openrouter_falso(respuesta_falsa("Vale."))

    openrouter.completar(
        [{"role": "user", "content": "Hola"}], razonamiento=razonamiento
    )

    enviado = falso.llamadas[0].get("extra_body", {}).get("reasoning")
    assert enviado == esperado


def test_las_opciones_pasan_al_sdk_y_un_extra_body_propio_se_respeta(openrouter_falso):
    falso = openrouter_falso(respuesta_falsa("Vale."))

    openrouter.completar(
        [{"role": "user", "content": "Hola"}],
        modelo="otro/modelo",
        razonamiento=True,
        temperature=0.2,
        extra_body={"provider": {"sort": "throughput"}},
    )

    llamada = falso.llamadas[0]
    assert llamada["model"] == "otro/modelo"
    assert llamada["temperature"] == 0.2
    assert llamada["extra_body"] == {
        "provider": {"sort": "throughput"},
        "reasoning": {"enabled": True},
    }


@pytest.mark.parametrize(
    ("bandera", "esperado"),
    [([], {"enabled": True}), (["--sin-razonamiento"], {"enabled": False})],
)
def test_la_bandera_de_ia_probar_apaga_el_razonamiento_de_verdad(
    openrouter_falso, bandera, esperado
):
    """`--sin-razonamiento` tiene que mandar `enabled: False`, no dejar de mandar nada.

    Mapearla a `None` es lo que parece correcto y no lo es: `None` deja mandar al default del
    proveedor, y el modelo configurado razona por defecto. La bandera quedaba sin efecto y el
    comando seguía pagando los tokens de razonamiento sin que nada lo delatara.
    """
    from django.core.management import call_command

    falso = openrouter_falso(respuesta_falsa("LISTO"))

    call_command("ia_probar", *bandera, stdout=StringIO())

    assert falso.llamadas[0]["extra_body"]["reasoning"] == esperado


def test_una_conversacion_vacia_se_rechaza_antes_de_gastar(openrouter_falso):
    openrouter_falso(respuesta_falsa("No debería llegar aquí."))

    with pytest.raises(ValueError):
        openrouter.completar([])
