"""Paso 3 de 3: se va el CharField y la clave foránea toma su nombre.

Va en una migración aparte de la de datos a propósito: si el borrado fuera en la misma, un fallo a
mitad dejaría el mapeo hecho y la columna vieja ya perdida, sin nada a lo que volver.

**El `AlterField` de la primera operación es lo que hace reversible toda la cadena**, y no es
cosmético. Al deshacer, `RemoveField` vuelve a crear la columna tal como estaba en el estado
anterior; el `tipo` original era `NOT NULL` y sin `default`, así que Postgres rechazaba añadirla
sobre una tabla con filas —«column "tipo" contains null values"»— y la reversión moría antes de
llegar al paso 2, que es justo el que sabe devolver los valores. Relajarla a `blank` con default
vacío deja la marcha atrás practicable, que es la única forma de que el reverso escrito en `0007`
sirva para algo.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("normativa", "0007_migrar_tipos_de_norma")]

    operations = [
        migrations.AlterField(
            model_name="norma",
            name="tipo",
            field=models.CharField(blank=True, default="", max_length=12),
        ),
        migrations.RemoveField(model_name="norma", name="tipo"),
        migrations.RenameField(model_name="norma", old_name="tipo_nuevo", new_name="tipo"),
    ]
