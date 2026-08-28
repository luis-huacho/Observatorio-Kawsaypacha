"""Devuelve a la barra superior el enlace al sitio institucional, `predes.org.pe`.

El enlace se añadió el 19/08/2026 a **dos** de los tres sitios donde vive el menú —la semilla
`sitio.yaml` y el respaldo de `frontend/src/lib/sitio.tsx`— y faltó el tercero, que es la base ya
sembrada. En desarrollo no se notó porque ahí alguien corrió `seed` después; en el servidor la
barra superior lleva desde entonces mostrando solo «Contacto».

Lo que lo volvió invisible es que **`seed` no corre en el despliegue**: `docker-entrypoint.sh`
ejecuta `migrate` y `meili_setup`, nada más, y el seed es un paso manual del runbook para la
instalación inicial y las recargas. Así que un cambio de menú que solo toque el YAML se queda en
la máquina de quien lo escribió y en ningún servidor, sin que nada avise.

Se opera por `(zona, url)` y no por el texto, igual que en `0004`: el texto es editable desde el
admin y casar por él crearía una segunda fila en vez de reconocer la que ya está.
"""

from django.db import migrations

ZONA = "top"
URL = "https://predes.org.pe/"
TEXTO = "predes.org.pe"
ORDEN = 1


def aplicar(apps, schema_editor):
    EnlaceMenu = apps.get_model("sitio", "EnlaceMenu")

    # `get_or_create` y no `create`: en desarrollo la fila ya existe (la sembró el seed) y
    # duplicarla pintaría el enlace dos veces sin que nada fallara.
    EnlaceMenu.objects.get_or_create(
        zona=ZONA,
        url=URL,
        defaults={"texto": TEXTO, "orden": ORDEN, "visible": True},
    )


def revertir(apps, schema_editor):
    EnlaceMenu = apps.get_model("sitio", "EnlaceMenu")

    EnlaceMenu.objects.filter(zona=ZONA, url=URL).delete()


class Migration(migrations.Migration):
    dependencies = [("sitio", "0006_alter_heroslide_estado")]

    operations = [migrations.RunPython(aplicar, revertir)]
