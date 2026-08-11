"""Vacía `CentroPoblado.poblacion`: el dato no tiene fuente respaldada (ADR-A19).

El Excel de exposición trae la columna y hasta ahora se importaba, así que las bases ya
sembradas conservan 8,968 valores que el sitio ha dejado de publicar. Dejarlos ahí sería una
trampa para quien consulte la base directamente o escriba una consulta nueva: el dato parecería
disponible y respaldado.

**Es reversible en el sentido que importa**: el campo sigue existiendo y el día que PREDES
entregue un padrón oficial se vuelve a importar. Lo que no se puede es recuperar estos valores
concretos desde la base — pero sí desde el Excel de origen, que es de donde salieron.
"""
from django.db import migrations


def vaciar(apps, schema_editor):
    CentroPoblado = apps.get_model("territorio", "CentroPoblado")
    CentroPoblado.objects.exclude(poblacion=None).update(poblacion=None)


def sin_vuelta(apps, schema_editor):
    """La marcha atrás no repuebla: el dato se recupera reimportando el Excel, no aquí."""


class Migration(migrations.Migration):
    dependencies = [("territorio", "0001_initial")]

    operations = [migrations.RunPython(vaciar, sin_vuelta)]
