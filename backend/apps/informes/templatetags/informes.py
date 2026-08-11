"""Filtros de plantilla de los informes."""
from pathlib import Path

from django import template
from django.conf import settings

register = template.Library()


@register.filter
def plural_es(cantidad, formas: str) -> str:
    """`{{ n|plural_es:"centro poblado,centros poblados" }}`.

    Un documento formal no puede imprimir "1 centros poblados cuentan", y el `pluralize` de
    Django solo añade sufijos: no sirve para "cuenta/cuentan" ni para "no cuenta/no cuentan".
    """
    singular, _, plural = formas.partition(",")
    try:
        n = int(cantidad)
    except (TypeError, ValueError):
        n = 0
    return singular if n == 1 else (plural or singular)


@register.filter
def miles(valor) -> str:
    """Separador de miles con coma, como escribe Perú (10,978).

    No se usa `intcomma`: con `USE_L10N` el formato del locale tiene precedencia sobre
    `THOUSAND_SEPARATOR`, y el locale «es» de Django separa con espacio fino. El resultado era
    un PDF que decía «7 236» donde el sitio, que formatea con `Intl` es-PE, dice «7,236».
    """
    if valor is None or valor == "":
        return "—"
    try:
        return f"{int(valor):,}"
    except (TypeError, ValueError):
        return str(valor)


@register.filter
def soles(valor) -> str:
    """Importe con el formato del sitio: `S/ 54,591,255`, sin decimales.

    Sin decimales a propósito: son presupuestos públicos de millones de soles, y los céntimos
    solo alargan la columna. El separador es el mismo que `miles`, por lo mismo que aquel.
    """
    if valor is None or valor == "":
        return "—"
    try:
        return f"S/ {float(valor):,.0f}"
    except (TypeError, ValueError):
        return "—"


@register.filter
def pct(valor) -> str:
    """Fracción 0-1 como porcentaje. `None` es «—», nunca «0 %».

    La diferencia importa: una municipalidad con PIM cero no ha ejecutado el 0 % de lo que
    tenía, es que no tenía nada que ejecutar.
    """
    if valor is None or valor == "":
        return "—"
    try:
        return f"{float(valor) * 100:.1f} %"
    except (TypeError, ValueError):
        return "—"


@register.simple_tag
def logo_predes() -> str:
    """Ruta del logo para WeasyPrint.

    Se resuelve a un `file://` absoluto: WeasyPrint carga las imágenes él mismo y una ruta
    relativa al dominio público no existe desde el proceso del worker.
    """
    ruta = Path(settings.BASE_DIR) / "static" / "img" / "logo-predes-green.svg"
    return ruta.as_uri() if ruta.exists() else ""
