"""Saca «Comparar distritos» de la navegación (ADR-P2).

Hace falta una migración de datos, y no basta con el YAML de semillas, porque `semilla.sembrar`
es *crear lo que falta y no tocar lo que ya existe* —a propósito: el seed corre en cada despliegue
y no debe pisar lo que PREDES edita desde el admin—. Sin esto, la base ya sembrada seguiría
sirviendo el enlace y el cambio solo se vería en instalaciones nuevas.

Es reversible: el reverso lo vuelve a mostrar. Y sigue siendo una decisión de PREDES, que puede
marcar la casilla «visible» en el admin sin necesidad de otra migración.
"""

from django.db import migrations

URL = "/comparar"


def ocultar(apps, schema_editor):
    EnlaceMenu = apps.get_model("sitio", "EnlaceMenu")
    EnlaceMenu.objects.filter(url=URL).update(visible=False)


def mostrar(apps, schema_editor):
    EnlaceMenu = apps.get_model("sitio", "EnlaceMenu")
    EnlaceMenu.objects.filter(url=URL).update(visible=True)


class Migration(migrations.Migration):
    dependencies = [("sitio", "0001_initial")]

    operations = [migrations.RunPython(ocultar, mostrar)]
