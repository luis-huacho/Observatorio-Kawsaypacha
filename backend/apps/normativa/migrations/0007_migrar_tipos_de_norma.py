"""Paso 2 de 3: siembra los cinco tipos y traslada el valor de cada norma a la clave foránea.

**Es el paso que puede perder datos en silencio.** Si el mapeo fallara, las normas quedarían sin
tipo y en pantalla se verían exactamente igual que si nunca lo hubieran tenido: sin error, sin
aviso y sin forma de saber cuál era. Por eso el reverso vuelve a escribir la cadena y por eso hay
una prueba que recorre los cinco valores.

La lista va escrita aquí y no leída de `tipos.yaml` por el mismo motivo que en
`0005_entidades_emisoras.py`: una migración es historia y tiene que dar el mismo resultado dentro
de un año; si leyera el YAML, editar el archivo reescribiría el pasado.

`sinonimos` se siembra con las quince variantes que la tabla fija de `importacion.py` reconocía
antes de que el catálogo existiera. Trasladarlas es lo que hace que el importador siga
reconociendo «D.S.» u «Ordenanza Regional» exactamente igual que ayer.
"""

from django.db import migrations

#: (slug, nombre, abreviatura, orden, sinónimos, valor crudo que tenía el CharField)
TIPOS = [
    ("ley", "Ley", "", 1, [], "Ley"),
    ("ds", "Decreto Supremo", "DS", 2, ["D.S."], "DS"),
    ("rm", "Resolución Ministerial", "RM", 3, ["R.M."], "RM"),
    ("rj", "Resolución Jefatural", "RJ", 4, ["R.J."], "RJ"),
    ("ordenanza", "Ordenanza", "", 5,
     ["Ordenanza Regional", "Ordenanza Municipal", "Ordenanza Provincial", "Ordenanza Distrital"],
     "Ordenanza"),
]


def aplicar(apps, schema_editor):
    TipoNorma = apps.get_model("normativa", "TipoNorma")
    Norma = apps.get_model("normativa", "Norma")

    por_crudo = {}
    for slug, nombre, abreviatura, orden, sinonimos, crudo in TIPOS:
        # `get_or_create` por slug: en desarrollo el seed pudo crearlos ya, y `nombre` es editable
        # desde el admin, así que casar por él crearía una segunda fila en vez de reconocer la que
        # está.
        tipo, _ = TipoNorma.objects.get_or_create(
            slug=slug,
            defaults={"nombre": nombre, "abreviatura": abreviatura, "orden": orden,
                      "sinonimos": sinonimos},
        )
        por_crudo[crudo] = tipo

    for crudo, tipo in por_crudo.items():
        Norma.objects.filter(tipo=crudo).update(tipo_nuevo=tipo)

    # Las que traían `""` —normas que la IA dejó a medio redactar— se quedan en NULL, que es lo
    # que esa cadena vacía siempre quiso decir.


def revertir(apps, schema_editor):
    Norma = apps.get_model("normativa", "Norma")

    for slug, _nombre, _abrev, _orden, _sinonimos, crudo in TIPOS:
        Norma.objects.filter(tipo_nuevo__slug=slug).update(tipo=crudo)
    Norma.objects.filter(tipo_nuevo__isnull=True).update(tipo="")


class Migration(migrations.Migration):
    dependencies = [("normativa", "0006_tiponorma")]

    operations = [migrations.RunPython(aplicar, revertir)]
