"""Crea los índices, aplica sus ajustes y genera la llave search-only.

Idempotente: corre en el arranque del backend (ver spec 07). Imprime la llave para copiarla a
`frontend/.env` como `VITE_MEILI_SEARCH_KEY`.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.core.services import meili


class Command(BaseCommand):
    help = "Prepara los índices de Meilisearch y muestra la llave de solo búsqueda."

    def add_arguments(self, parser):
        parser.add_argument(
            "--tolerante",
            action="store_true",
            help="Si Meilisearch no responde, avisa y termina bien. Se usa en el arranque del "
                 "contenedor: la búsqueda es una función del sitio, no un requisito para "
                 "servirlo.",
        )

    def handle(self, *args, **opciones):
        if not meili.disponible():
            mensaje = (
                f"Meilisearch no responde en {meili.cliente_url()}. La búsqueda quedará "
                f"degradada a los endpoints DRF hasta que vuelva."
            )
            if opciones["tolerante"]:
                self.stdout.write(self.style.WARNING(f"  ! {mensaje}"))
                return
            raise CommandError(mensaje)

        for slug, indice in meili.INDICES.items():
            meili.preparar(slug)
            self.stdout.write(
                f"  {self.style.SUCCESS('✓')} índice «{slug}» listo "
                f"({len(indice.searchable)} campos buscables, "
                f"{len(indice.filterable)} facetas)"
            )

        llave = meili.llave_busqueda()
        self.stdout.write(self.style.MIGRATE_HEADING("\nLlave de solo búsqueda"))
        self.stdout.write(f"  VITE_MEILI_SEARCH_KEY={llave}")
        self.stdout.write(
            "\n  Va en LOS DOS .env: `frontend/.env` para `npm run dev`, y el `.env` de la raíz "
            "para el bundle compilado, que es el que sirve nginx. Vite hornea las VITE_* en el "
            "build, así que cambiarla exige reconstruir el frontend, no reiniciarlo."
        )
        self.stdout.write(
            "\n  No cambia: se deriva del uid fijo y de MEILI_MASTER_KEY, así que recrear el "
            "volumen de Meilisearch o restaurar un respaldo la deja igual."
        )
        self.stdout.write(
            "\n  Es segura por diseño: solo permite buscar, y solo en los índices públicos. "
            "La master key nunca sale del backend."
        )
