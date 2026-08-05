"""¿Sigue avanzando el worker? Responde la pregunta que el sitio no deja ver.

Termina con **código distinto de 0** si la cola está atascada, que es lo que lo hace usable desde
un cron, igual que `meili_estado`:

    35 4 * * * … manage.py cola_estado || mail -s "Cola del Observatorio" alguien@predes.org.pe

**Avisa y no arregla, a propósito.** Reiniciar el worker por su cuenta es justo lo que no se
quiere: si se atascó a mitad de una importación de 10,978 filas, matarlo puede dejar el dato peor
que parado. Por eso `deploy/vigilar-contenedores.sh` reinicia backend y nginx pero deja el worker
fuera, y lo que hay aquí es un aviso para que lo mire una persona.

Un worker atascado no se nota: el sitio sigue sirviendo y el admin sigue guardando. Lo que falla
es lo que nadie está mirando —un Excel que no entra, un correo que no sale, el índice de búsqueda
que se queda atrás—.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.core.services import tareas


class Command(BaseCommand):
    help = "Estado de la cola de tareas: qué hay pendiente y si el worker sigue avanzando."

    def handle(self, *args, **opciones):
        estado = tareas.estado_cola()

        if not estado["disponible"]:
            raise CommandError(
                "No se pudo leer la cola de tareas. Si la base no responde, eso es lo primero "
                "que hay que mirar: «docker compose ps db» y «docker compose logs db»."
            )

        conteos = estado["conteos"]
        self.stdout.write(f"\n  {'estado':<12} {'tareas':>7}")
        for clave, etiqueta in (
            ("READY", "en espera"),
            ("RUNNING", "en curso"),
            ("FAILED", "fallidas"),
            ("SUCCESSFUL", "hechas"),
        ):
            self.stdout.write(f"  {etiqueta:<12} {conteos.get(clave, 0):>7,}")

        if estado["esperando"]:
            self.stdout.write(
                f"\n  La más antigua en espera lleva {tareas._humano(estado['esperando'])}."
            )

        # Las fallidas no atascan la cola, pero son fallos silenciosos y merecen decirse.
        if estado["fallidas"]:
            self.stdout.write(self.style.WARNING(
                f"\n  {estado['fallidas']} tarea(s) fallida(s). No atascan la cola, pero algo no "
                f"se hizo: revisar en «docker compose logs worker»."
            ))

        if estado["atascada"]:
            raise CommandError(
                "La cola no avanza: "
                + "; ".join(estado["motivos"])
                + ". Revisar «docker compose logs worker»; si el worker está colgado, "
                "«docker compose restart worker» —pero comprobando antes qué tarea quedó a "
                "medias, porque una importación interrumpida hay que repetirla."
            )

        self.stdout.write(self.style.SUCCESS("\n  La cola avanza con normalidad."))
