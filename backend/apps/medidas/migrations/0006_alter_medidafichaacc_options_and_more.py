from django.db import migrations


class Migration(migrations.Migration):
    """La ficha ACC deja de colgar de una Medida.

    **Es irreversible**: al soltar la columna se pierde qué ficha pertenecía a qué medida en los
    registros ya cargados. Se aceptó porque nadie leía esa relación —no hay serializer, API,
    frontend ni semilla que la use— y porque el formulario que PREDES reparte es autónomo: exigir
    una medida ya publicada a la cual colgarla bloqueaba la carga en lote sin aportar nada.

    El `ordering` no es cosmético. Las fichas de una misma importación entran todas en el mismo
    `bulk_create` y empatan en `creado_en`; un orden parcial paginado repite filas y se salta
    otras en silencio, que es lo que ya costó una corrección en /api/ccpp/.
    """

    dependencies = [
        ('medidas', '0005_alter_medida_estado'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='medidafichaacc',
            options={
                'ordering': ['-creado_en', 'id'],
                'verbose_name': 'Ficha de Adaptación al Cambio Climático',
                'verbose_name_plural': 'fichas de Adaptación al Cambio Climático',
            },
        ),
        migrations.RemoveField(
            model_name='medidafichaacc',
            name='medida',
        ),
    ]
