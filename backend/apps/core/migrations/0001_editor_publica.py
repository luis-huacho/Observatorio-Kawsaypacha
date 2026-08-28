"""El grupo Editor recibe `puede_publicar` (ADR-P3).

Hace falta una migración de datos, y no basta con cambiar `seed.py`, porque **el seed no corre en
el despliegue**: `docker-entrypoint.sh` solo hace `migrate` y `meili_setup`. Sin esto, el permiso
solo aparecería en instalaciones nuevas y en la base de PREDES el Editor se quedaría sin poder
hacer nada — al retirarse el paso de revisión, «Enviar a revisión» era su única acción.

Es el mismo patrón y el mismo razonamiento que `sitio/0002_ocultar_comparar_del_menu.py`.

Vive en `core` y no en una app editorial porque el permiso cruza las cinco: los grupos los
definen `core/grupos.py` y `core/management/commands/seed.py`.

Reversible: el reverso se lo quita.
"""

from django.db import migrations

GRUPO = "Editor"
PERMISO = "puede_publicar"


def conceder(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    grupo = Group.objects.filter(name=GRUPO).first()
    if grupo is None:
        # Base sin sembrar: el seed lo creará ya con el permiso.
        return
    grupo.permissions.add(*Permission.objects.filter(codename=PERMISO))


def retirar(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    grupo = Group.objects.filter(name=GRUPO).first()
    if grupo is None:
        return
    grupo.permissions.remove(*Permission.objects.filter(codename=PERMISO))


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        # Los `puede_publicar` nacen con el `Meta.permissions` de cada modelo, así que las tablas
        # y sus permisos tienen que existir antes de que esto los busque.
        ("contenidos", "0004_alter_evento_estado_alter_noticia_estado_and_more"),
        ("medidas", "0005_alter_medida_estado"),
        ("normativa", "0002_alter_norma_estado"),
        ("biblioteca", "0002_alter_documento_estado"),
        ("sitio", "0006_alter_heroslide_estado"),
    ]

    operations = [migrations.RunPython(conceder, retirar)]
