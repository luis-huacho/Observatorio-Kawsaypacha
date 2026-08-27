"""Los textos del hero al día, y «Medidas» pasa a llamarse «Buenas prácticas».

Dos cambios sin relación técnica entre sí, juntos porque llegaron en el mismo encargo y los dos
son *datos que la base sembrada dejó atrás*:

1. **El hero.** El commit `b635d54` cambió el título y el subtítulo en la semilla y en los
   respaldos de `Home.tsx`, pero la base ya sembrada se quedó con los del prototipo y es la que
   manda: `semilla.sembrar` crea lo que falta y no pisa lo que existe.
2. **La etiqueta del menú.** Renombrar solo en el YAML no vale, y además es peligroso: el seed casa
   las filas por `(zona, url, texto)`, así que un texto distinto no actualiza la fila, crea una
   segunda y el menú acaba mostrando «Medidas» *y* «Buenas prácticas». Por eso se opera por
   `(zona, url)` y se desduplica antes, igual que en la `0004`.

Los bloques del hero se tocan **solo si siguen teniendo el texto viejo exacto**. No es un adorno:
son contenido que PREDES edita desde el admin, y el contrato de todo esto es no pisar lo editado.
Si alguien ya los cambió, esta migración pasa de largo.
"""

from django.db import migrations

TITULO_ANTES = "<p>Observatorio del riesgo y la adaptación climática en Cusco.</p>"
TITULO_DESPUES = (
    "<p>Observatorio para la Gestión del riesgo de desastres y la adaptación al cambio "
    "climático.</p>"
)

SUBTITULO_ANTES = (
    "<p>Monitoreamos peligros, prácticas que funcionan, inversión pública y prioridades de los "
    "gobiernos locales y regionales para reducir el riesgo de desastres.</p>"
)
SUBTITULO_DESPUES = (
    "<p>Monitoreamos y facilitamos información sobre los peligros, inversión, normativa, medidas "
    "y buenas prácticas para la gestión del riesgo y la adaptación climática.</p>"
)

BLOQUES = [
    ("home.hero.titulo", TITULO_ANTES, TITULO_DESPUES),
    ("home.hero.subtitulo", SUBTITULO_ANTES, SUBTITULO_DESPUES),
]

# (zona, url): la sección se sigue sirviendo en /medidas; lo que cambia es cómo se llama.
MENU = [("header", "/medidas"), ("footer", "/medidas")]
MENU_ANTES = "Medidas"
MENU_DESPUES = "Buenas prácticas"


def _mover_bloques(apps, de, a):
    """Reescribe los bloques del hero, respetando lo que se haya editado en el admin."""
    BloqueTexto = apps.get_model("sitio", "BloqueTexto")
    for clave, antes, despues in BLOQUES:
        origen, destino = (antes, despues) if de == "antes" else (despues, antes)
        BloqueTexto.objects.filter(clave=clave, cuerpo=origen).update(cuerpo=destino)


def _renombrar_menu(apps, texto):
    EnlaceMenu = apps.get_model("sitio", "EnlaceMenu")
    for zona, url in MENU:
        # Una fila por `(zona, url)`: si un entorno sembró con el YAML nuevo antes de migrar,
        # tendría dos y el `update` las dejaría idénticas, duplicando la entrada del menú.
        ids = list(
            EnlaceMenu.objects.filter(zona=zona, url=url)
            .order_by("id")
            .values_list("id", flat=True)
        )
        if len(ids) > 1:
            EnlaceMenu.objects.filter(id__in=ids[1:]).delete()
        EnlaceMenu.objects.filter(zona=zona, url=url).update(texto=texto)


def aplicar(apps, schema_editor):
    _mover_bloques(apps, "antes", "despues")
    _renombrar_menu(apps, MENU_DESPUES)


def revertir(apps, schema_editor):
    _mover_bloques(apps, "despues", "antes")
    _renombrar_menu(apps, MENU_ANTES)


class Migration(migrations.Migration):
    dependencies = [("sitio", "0004_renombrar_y_reordenar_el_menu")]

    operations = [migrations.RunPython(aplicar, revertir)]
