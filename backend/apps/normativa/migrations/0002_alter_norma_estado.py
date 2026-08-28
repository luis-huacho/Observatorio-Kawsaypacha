"""Retira «revisión» del flujo editorial (ADR-P3).

Además del cambio de `choices`, un `RunPython` **defensivo**: la columna no tiene `CHECK` en
PostgreSQL, así que una fila que quedara en `revision` no daría ningún error — simplemente se
mostraría en crudo, con un valor que ya no está en las opciones y sin ninguna transición que la
saque de ahí. En desarrollo no hay ninguna; en la base de PREDES puede haberla.

El reverso no las devuelve a `revision`: no hay forma de saber cuáles estaban ahí, e inventarlo
sería peor que dejarlas en borrador, que es donde el flujo nuevo las pondría igualmente.
"""

from django.db import migrations, models



def a_borrador(apps, schema_editor):
    """Lo que quedara en «revisión» pasa a borrador: el estado ya no existe."""
    apps.get_model("normativa", "Norma").objects.filter(estado="revision").update(estado="borrador")


def sin_reverso(apps, schema_editor):
    """No hay a qué volver: no queda registro de cuáles estaban en revisión."""


class Migration(migrations.Migration):

    dependencies = [
        ('normativa', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(a_borrador, sin_reverso),
        migrations.AlterField(
            model_name='norma',
            name='estado',
            field=models.CharField(choices=[('borrador', 'Borrador'), ('publicado', 'Publicado'), ('archivado', 'Archivado')], db_index=True, default='borrador', max_length=12),
        ),
    ]
