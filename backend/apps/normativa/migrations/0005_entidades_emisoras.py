"""Siembra el catálogo de entidades emisoras en toda base ya creada.

Sin esto el catálogo existiría solo donde alguien corriera `seed`, porque **`seed` no corre en el
despliegue**: `docker-entrypoint.sh` ejecuta `migrate` y `meili_setup`, y el seed es un paso manual
del runbook. Un catálogo vacío no da error: deja el desplegable de `/normativa` sin una sola opción
y el «+» del admin como única vía, sin que nada avise. Es exactamente lo que le pasó al menú
superior en `sitio.0007`.

La lista va escrita aquí y no leída de `entidades.yaml` a propósito. Una migración es historia y
tiene que dar el mismo resultado dentro de un año; si leyera el YAML, editar el archivo reescribiría
el pasado. La copia se paga una vez: a partir de aquí el catálogo lo mantiene PREDES desde el admin
y ninguno de los dos archivos vuelve a tocarlo.
"""

from django.db import migrations

ENTIDADES = [
    ("congreso", "Congreso de la República", "Congreso", 1),
    ("pcm", "Presidencia del Consejo de Ministros", "PCM", 2),
    ("cenepred",
     "Centro Nacional de Estimación, Prevención y Reducción del Riesgo de Desastres",
     "CENEPRED", 3),
    ("indeci", "Instituto Nacional de Defensa Civil", "INDECI", 4),
    ("minam", "Ministerio del Ambiente", "MINAM", 5),
    ("mef", "Ministerio de Economía y Finanzas", "MEF", 6),
    ("midagri", "Ministerio de Desarrollo Agrario y Riego", "MIDAGRI", 7),
    ("mvcs", "Ministerio de Vivienda, Construcción y Saneamiento", "MVCS", 8),
    ("senamhi", "Servicio Nacional de Meteorología e Hidrología del Perú", "SENAMHI", 9),
    ("ana", "Autoridad Nacional del Agua", "ANA", 10),
    ("gore-cusco", "Gobierno Regional de Cusco", "GORE Cusco", 11),
    ("mpc", "Municipalidad Provincial del Cusco", "MPC", 12),
]


def aplicar(apps, schema_editor):
    EntidadEmisora = apps.get_model("normativa", "EntidadEmisora")

    for slug, nombre, sigla, orden in ENTIDADES:
        # Por `slug` y con `get_or_create`: en desarrollo el seed ya las creó, y `nombre` es
        # editable desde el admin, así que casar por él crearía una segunda fila en vez de
        # reconocer la que está.
        EntidadEmisora.objects.get_or_create(
            slug=slug, defaults={"nombre": nombre, "sigla": sigla, "orden": orden}
        )


def revertir(apps, schema_editor):
    EntidadEmisora = apps.get_model("normativa", "EntidadEmisora")

    # Solo las que no usa ninguna norma: la FK es PROTECT y borrar una en uso lanzaría
    # `ProtectedError` a mitad de la reversión.
    EntidadEmisora.objects.filter(
        slug__in=[slug for slug, *_ in ENTIDADES], normas__isnull=True
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("normativa", "0004_entidademisora_norma_entidad_emisora")]

    operations = [migrations.RunPython(aplicar, revertir)]
