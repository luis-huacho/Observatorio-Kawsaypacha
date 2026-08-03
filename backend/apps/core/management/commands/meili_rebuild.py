"""Reconstruye uno o todos los índices de búsqueda.

Se corre al desplegar, tras un DatasetUpload de peligros (índice `ccpp`) y ante cualquier
sospecha de que el índice y la base no coinciden.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.core.services import meili


class Command(BaseCommand):
    help = "Reconstruye los índices de Meilisearch desde la base de datos."

    def add_arguments(self, parser):
        parser.add_argument(
            "indices",
            nargs="*",
            help=f"Índices a reconstruir. Sin argumentos, todos. Válidos: "
                 f"{', '.join(meili.INDICES)}.",
        )

    def handle(self, *args, **opciones):
        pedidos = opciones["indices"] or list(meili.INDICES)
        if desconocidos := [i for i in pedidos if i not in meili.INDICES]:
            raise CommandError(
                f"Índice desconocido: {', '.join(desconocidos)}. "
                f"Válidos: {', '.join(meili.INDICES)}."
            )
        if not meili.disponible():
            raise CommandError("Meilisearch no responde; no hay nada que reconstruir.")

        for slug in pedidos:
            total = meili.reconstruir(slug)
            self.stdout.write(
                f"  {self.style.SUCCESS('✓')} «{slug}»: {total:,} documento(s) indexado(s)"
            )
