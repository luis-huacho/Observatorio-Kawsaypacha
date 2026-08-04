"""Responde dos preguntas del runbook: ¿está arriba la búsqueda, y está al día?

Termina con **código distinto de 0** si el servicio no responde o si algún índice está desfasado,
que es lo que lo hace usable desde un cron:

    0 4 * * * … manage.py meili_estado || mail -s "Buscador del Observatorio" alguien@predes.org.pe

Reindexar es otro comando (`meili_rebuild`) y también un botón en el panel del admin: comprobar y
arreglar se piden por separado a propósito, para que un cron de vigilancia no reconstruya índices
por su cuenta a las cuatro de la mañana.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.core.services import meili


class Command(BaseCommand):
    help = "Estado de Meilisearch: servicio y documentos indexados frente a la base de datos."

    def handle(self, *args, **opciones):
        estado = meili.estado_indices()

        if not estado["disponible"]:
            raise CommandError(
                f"Meilisearch no responde en {meili.cliente_url()}. El sitio sigue buscando con "
                f"el respaldo de DRF —sin facetas ni tolerancia a erratas— y avisa de ello en "
                f"pantalla."
            )

        self.stdout.write(f"  {self.style.SUCCESS('●')} Meilisearch responde")
        self.stdout.write(f"\n  {'índice':<12} {'en Meili':>9} {'en la base':>11}")
        for indice in estado["indices"]:
            en_meili = "—" if indice["en_meili"] is None else f"{indice['en_meili']:,}"
            marca = self.style.SUCCESS("✓") if indice["al_dia"] else self.style.ERROR("✗")
            self.stdout.write(
                f"  {indice['slug']:<12} {en_meili:>9} {indice['en_bd']:>11,}  {marca}"
            )

        if estado["pendientes"]:
            self.stdout.write(
                f"\n  {estado['pendientes']} tarea(s) en cola en Meilisearch: si algún conteo no "
                f"cuadra, puede ser que se esté indexando ahora mismo."
            )

        if not estado["al_dia"]:
            desfasados = [i["slug"] for i in estado["indices"] if not i["al_dia"]]
            raise CommandError(
                f"Índices desfasados: {', '.join(desfasados)}. Lo que no está indexado no se "
                f"encuentra en el buscador, aunque esté publicado. Se arregla con «manage.py "
                f"meili_rebuild {' '.join(desfasados)}» o con el botón del panel del admin."
            )

        self.stdout.write(self.style.SUCCESS("\n  Todos los índices al día."))
