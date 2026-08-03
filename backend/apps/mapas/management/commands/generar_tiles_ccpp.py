"""Regenera `media/tiles/ccpp.pmtiles` desde la base de datos (spec 05)."""
from django.core.management.base import BaseCommand, CommandError

from apps.mapas.pipeline import ErrorPipeline, generar_ccpp


class Command(BaseCommand):
    help = "Genera los vector tiles de centros poblados desde la base de datos."

    def handle(self, *args, **opciones):
        try:
            resultado = generar_ccpp()
        except ErrorPipeline as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"  {self.style.SUCCESS('✓')} ccpp.pmtiles: {resultado}")
