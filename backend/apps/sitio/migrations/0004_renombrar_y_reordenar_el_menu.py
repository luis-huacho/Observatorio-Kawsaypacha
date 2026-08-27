"""Renombra y reordena el menú principal: «Sobre el observatorio» al frente y «Peligros» corto.

El menú vive en tres sitios y hay que tocar los tres: la semilla, **la base ya sembrada** —esto— y
el respaldo del frontend. Hace falta una migración de datos porque `semilla.sembrar` es *crear lo
que falta y no tocar lo que ya existe*: el seed corre en cada despliegue y no debe pisar lo que
PREDES edita desde el admin.

Y hay un agravante propio de este cambio. El seed casa las filas por `(zona, url, texto)`, así que
un `texto` distinto en el YAML **no actualiza** la fila vieja: crearía una segunda y el menú
mostraría «Exposición a peligros» *y* «Peligros». Por eso aquí se opera por `(zona, url)`, que es
lo estable, y se desduplica antes de renombrar por si algún entorno ya sembró con el YAML nuevo.

Es reversible: el reverso devuelve las etiquetas y el orden anteriores.
"""

from django.db import migrations

# (zona, url) -> (texto antes, texto después, orden antes, orden después).
# `None` en un orden significa «no lo toques»: el pie se ordena por su propia columna.
CAMBIOS = [
    ("header", "/sobre", "Sobre", "Sobre el observatorio", 6, 1),
    ("header", "/peligros", "Exposición a peligros", "Peligros", 1, 2),
    ("header", "/medidas", "Medidas", "Medidas", 2, 3),
    ("header", "/inversion", "Inversión", "Inversión", 3, 4),
    ("header", "/normativa", "Normativa", "Normativa", 4, 5),
    ("header", "/comparar", "Comparar distritos", "Comparar distritos", 5, 6),
    ("footer", "/peligros", "Exposición a peligros", "Peligros", None, None),
]

# «Sobre el observatorio» pasó a abrir el menú principal, así que deja de anunciarse también en la
# barra superior: repetirlo en las dos barras se lee como descuido. Sigue en el pie.
TOP_RETIRADO = ("top", "/sobre", "Sobre el observatorio", 2)


def _desduplicar(EnlaceMenu, zona, url):
    """Deja una sola fila por `(zona, url)`, la más antigua.

    Un entorno que haya corrido `seed` después del renombrado en el YAML tiene dos filas para el
    mismo enlace. Sin esto, el `update` de abajo les pondría el mismo texto a las dos y el menú
    saldría con la entrada repetida sin que nada falle.
    """
    ids = list(
        EnlaceMenu.objects.filter(zona=zona, url=url).order_by("id").values_list("id", flat=True)
    )
    if len(ids) > 1:
        EnlaceMenu.objects.filter(id__in=ids[1:]).delete()


def aplicar(apps, schema_editor):
    EnlaceMenu = apps.get_model("sitio", "EnlaceMenu")

    for zona, url, _antes, despues, _orden_antes, orden in CAMBIOS:
        _desduplicar(EnlaceMenu, zona, url)
        campos = {"texto": despues}
        if orden is not None:
            campos["orden"] = orden
        EnlaceMenu.objects.filter(zona=zona, url=url).update(**campos)

    zona, url, _texto, _orden = TOP_RETIRADO
    EnlaceMenu.objects.filter(zona=zona, url=url).delete()


def revertir(apps, schema_editor):
    EnlaceMenu = apps.get_model("sitio", "EnlaceMenu")

    for zona, url, antes, _despues, orden, _orden_despues in CAMBIOS:
        campos = {"texto": antes}
        if orden is not None:
            campos["orden"] = orden
        EnlaceMenu.objects.filter(zona=zona, url=url).update(**campos)

    zona, url, texto, orden = TOP_RETIRADO
    if not EnlaceMenu.objects.filter(zona=zona, url=url).exists():
        EnlaceMenu.objects.create(zona=zona, url=url, texto=texto, orden=orden, visible=True)


class Migration(migrations.Migration):
    dependencies = [("sitio", "0003_alter_enlacemenu_grupo_alter_enlacemenu_zona")]

    operations = [migrations.RunPython(aplicar, revertir)]
