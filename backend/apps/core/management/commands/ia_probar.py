"""Comprueba de extremo a extremo que la integración con OpenRouter funciona (ADR-A22).

Hace **una** llamada real y muestra qué modelo respondió, qué contestó, cuántos tokens costó y
cuánto se pagó. Existe porque lo demás de esta integración se prueba con un cliente falso: sin este
comando, la única forma de saber si la llave y el modelo son correctos sería conectarla antes a una
pantalla y descubrirlo ahí.

Gasta dinero, poco pero real, así que no es un `estado` que se pueda poner en un cron de vigilancia
—ésa es la diferencia con `meili_estado`—. Termina con código distinto de 0 si algo falla:

    manage.py ia_probar
    manage.py ia_probar --modelo openai/gpt-5 --sin-razonamiento
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core.services import openrouter

PREGUNTA = "Responde solo con la palabra LISTO."


class Command(BaseCommand):
    help = "Hace una llamada real a OpenRouter y muestra el resultado, los tokens y el coste."

    def add_arguments(self, parser):
        parser.add_argument("--modelo", help="Sobrescribe OPENROUTER_MODELO para esta llamada.")
        parser.add_argument("--pregunta", default=PREGUNTA, help="Qué preguntar.")
        parser.add_argument(
            "--sin-razonamiento",
            action="store_true",
            help="Desactiva el razonamiento. Útil con modelos que no lo soportan.",
        )

    def handle(self, *args, **opciones):
        if not settings.OPENROUTER_API_KEY:
            raise CommandError(
                "OPENROUTER_API_KEY no configurada en backend/.env. Consíguela en "
                "https://openrouter.ai/keys; mientras no esté, todo lo que dependa de IA queda "
                "deshabilitado y nada más se ve afectado."
            )

        modelo = opciones["modelo"] or settings.OPENROUTER_MODELO
        self.stdout.write(f"  Preguntando a {modelo}…")

        try:
            respuesta = openrouter.completar(
                [{"role": "user", "content": opciones["pregunta"]}],
                modelo=opciones["modelo"],
                # `False`, no `None`: `None` deja mandar al default del proveedor, y hay modelos
                # —el de por defecto, sin ir más lejos— que razonan salvo que se les diga que no.
                razonamiento=not opciones["sin_razonamiento"],
            )
        except Exception as exc:  # noqa: BLE001 — el detalle es justo lo que se viene a ver
            raise CommandError(f"La llamada falló: {exc}") from exc

        self.stdout.write(f"  {self.style.SUCCESS('●')} respondió {respuesta.modelo}\n")
        self.stdout.write(f"  {respuesta.texto}\n")

        tokens = respuesta.tokens
        self.stdout.write(
            f"  tokens: {tokens['entrada']} de entrada, {tokens['salida']} de salida "
            f"({tokens['total']} en total)"
        )
        if respuesta.costo is not None:
            self.stdout.write(f"  coste:  ${respuesta.costo:.6f}")
        if respuesta.razonamiento:
            self.stdout.write(
                f"  razonamiento: {len(respuesta.razonamiento)} bloque(s), que se reenviarían "
                f"tal cual en el turno siguiente."
            )
        elif not opciones["sin_razonamiento"]:
            self.stdout.write(
                "  razonamiento: no devuelto. Hay modelos que lo usan y no lo publican; no es "
                "un fallo de la integración."
            )
