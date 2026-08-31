"""Paso 1 de 3: el catálogo y la FK nueva, todavía en paralelo con el CharField.

La conversión va en tres migraciones porque `tipo` es `NOT NULL` y no se puede cambiar de tipo de
columna sin perder el dato por el camino. Aquí solo se crea sitio; el mapeo va en la siguiente y el
borrado del campo viejo en la tercera.
"""
from django.db import migrations, models
import django.contrib.postgres.fields
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("normativa", "0005_entidades_emisoras")]

    operations = [
        migrations.CreateModel(
            name="TipoNorma",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("nombre", models.CharField(max_length=120, unique=True)),
                ("abreviatura", models.CharField(blank=True, help_text='Sigla con la que se cita, p. ej. "DS". Es lo que se muestra en las tarjetas del listado, donde no cabe el nombre completo. Vacía en «Ley» u «Ordenanza», que ya son cortas.', max_length=20)),
                ("slug", models.SlugField(max_length=60, unique=True)),
                ("sinonimos", django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=80), blank=True, default=list, help_text="Otras formas en que llega escrito en los Excel que se importan, separadas por comas («D.S.», «Ordenanza Regional»). No hace falta cuidar tildes ni mayúsculas: se comparan normalizados.", size=None, verbose_name="sinónimos")),
                ("orden", models.PositiveSmallIntegerField(default=0, help_text="Los de menor número salen primero en el desplegable.")),
            ],
            options={
                "verbose_name": "tipo de norma",
                "verbose_name_plural": "tipos de norma",
                "ordering": ["orden", "nombre"],
            },
        ),
        migrations.AddField(
            model_name="norma",
            name="tipo_nuevo",
            field=models.ForeignKey(blank=True, help_text="Vacío si no consta; hace falta para publicar.", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="normas", to="normativa.tiponorma"),
        ),
    ]
