"""Reoptimiza las imágenes que ya estaban subidas antes de que el mixin existiera.

`ImagenOptimizadaMixin` cubre lo que se sube de ahora en adelante. Este comando es para el resto:
las portadas y las fotos de galería que llevan meses publicadas a tamaño original.

    manage.py optimizar_imagenes --simular     # dice qué haría, no toca nada
    manage.py optimizar_imagenes

**No cambia el formato, solo el tamaño.** El mixin sí convierte a JPEG o WebP, pero eso cambia la
extensión y por tanto la URL; hacerlo aquí dejaría rotos los enlaces ya publicados y un rastro de
archivos huérfanos en `media/`. Reescalar en el mismo formato conserva la ruta y ya se lleva la
mayor parte del ahorro: el peso de una foto va con los píxeles mucho más que con el códec.

**Reescribe con `os.replace`**, que es atómico: si el proceso muere a mitad, el archivo original
sigue entero. Un comando de mantenimiento que puede dejar medio JPEG escrito no es un comando de
mantenimiento.
"""
import os
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.core import imagenes


def _modelos_con_imagen():
    """Los modelos que declaran `campos_imagen`, en el orden en que Django los conoce."""
    for modelo in apps.get_models():
        campos = getattr(modelo, "campos_imagen", ())
        if campos:
            yield modelo, campos


def _kb(n: int) -> str:
    return f"{n / 1024:,.0f} KB".replace(",", " ")


class Command(BaseCommand):
    help = "Reescala las imágenes ya subidas al ancho máximo, sin cambiarles el formato."

    def add_arguments(self, parser):
        parser.add_argument(
            "--simular",
            action="store_true",
            help="Muestra qué se optimizaría y cuánto se ahorraría, sin escribir nada.",
        )

    def handle(self, *args, **opciones):
        simular = opciones["simular"]
        ancho = settings.CONTENIDO_ANCHO_MAXIMO_PX
        if simular:
            self.stdout.write(self.style.WARNING("  Simulación: no se escribe nada.\n"))

        total_antes = total_despues = tocadas = revisadas = 0

        for modelo, campos in _modelos_con_imagen():
            etiqueta = f"{modelo._meta.app_label}.{modelo.__name__}"
            for instancia in modelo.objects.all().iterator():
                for nombre in campos:
                    campo = getattr(instancia, nombre, None)
                    if not campo:
                        continue
                    revisadas += 1
                    resultado = self._optimizar_una(campo, ancho, simular)
                    if resultado is None:
                        continue
                    antes, despues = resultado
                    total_antes += antes
                    total_despues += despues
                    tocadas += 1
                    self.stdout.write(
                        f"  {etiqueta} #{instancia.pk} {campo.name}\n"
                        f"      {_kb(antes)} → {_kb(despues)}  "
                        f"({100 - despues * 100 // max(antes, 1)}% menos)"
                    )

        self.stdout.write("")
        self.stdout.write(f"  revisadas : {revisadas}")
        self.stdout.write(f"  {'optimizables' if simular else 'optimizadas'}: {tocadas}")
        if tocadas:
            ahorro = total_antes - total_despues
            self.stdout.write(
                self.style.SUCCESS(
                    f"  ahorro    : {_kb(ahorro)} de {_kb(total_antes)} "
                    f"({ahorro * 100 // max(total_antes, 1)}%)"
                )
            )
        else:
            self.stdout.write("  No hay nada que optimizar.")

    def _optimizar_una(self, campo, ancho: int, simular: bool):
        """`(bytes antes, bytes después)` si hay algo que hacer, o `None`.

        Devuelve `None` también cuando el archivo no existe en disco: en `media/` sobreviven
        referencias a archivos borrados a mano, y reventar por una de ellas dejaría el comando sin
        terminar el resto.
        """
        almacenamiento = campo.storage
        if not hasattr(almacenamiento, "path"):
            return None
        try:
            ruta = Path(almacenamiento.path(campo.name))
            if not ruta.is_file():
                return None
            antes = ruta.stat().st_size
            with almacenamiento.open(campo.name, "rb") as archivo:
                # `None` en el formato: se conserva el de origen. Ver el encabezado del módulo.
                reducida = imagenes.optimizar(archivo, ancho, None)
                if reducida is archivo:
                    return None
                datos = reducida.read()
        except Exception as exc:  # noqa: BLE001 — una imagen rara no puede parar el comando entero
            self.stderr.write(self.style.WARNING(f"  omitida {campo.name}: {exc}"))
            return None

        if len(datos) >= antes:
            # Reescalar y que salga más grande pasa con imágenes ya muy comprimidas. Se deja la que
            # está: el objetivo es que pese menos, no que esté reescrita.
            return None

        if not simular:
            temporal = ruta.with_suffix(ruta.suffix + ".tmp")
            temporal.write_bytes(datos)
            os.replace(temporal, ruta)

        return antes, len(datos)
