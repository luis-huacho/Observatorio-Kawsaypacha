"""Regenera los PMTiles de las capas cartográficas (spec 05)."""
from django.core.management.base import BaseCommand, CommandError

from apps.mapas.models import CapaCartografica
from apps.mapas.pipeline import generar_capa


class Command(BaseCommand):
    help = "Genera los vector tiles de una o de todas las capas cartográficas."

    def add_arguments(self, parser):
        parser.add_argument("slugs", nargs="*", help="Capas a generar. Sin argumentos, todas.")
        parser.add_argument(
            "--rehacer",
            action="store_true",
            help="Regenera también las capas que ya están en estado «ok».",
        )

    def handle(self, *args, **opciones):
        capas = CapaCartografica.objects.exclude(archivo_geojson="")
        if opciones["slugs"]:
            capas = capas.filter(slug__in=opciones["slugs"])
            faltan = set(opciones["slugs"]) - set(capas.values_list("slug", flat=True))
            if faltan:
                raise CommandError(
                    f"Sin capa (o sin archivo adjunto): {', '.join(sorted(faltan))}."
                )
        if not opciones["rehacer"]:
            capas = capas.exclude(estado_tiles=CapaCartografica.EstadoTiles.OK)

        if not capas:
            self.stdout.write("  No hay capas pendientes. Usa --rehacer para forzarlas.")
            return

        for capa in capas:
            self.stdout.write(f"  → {capa.slug}…")
            resultado = generar_capa(capa.pk)
            estilo = self.style.SUCCESS("✓") if not resultado.startswith("error") \
                else self.style.ERROR("✗")
            self.stdout.write(f"  {estilo} {capa.slug}: {resultado}")
