"""Formulario del admin para Norma, con el bloque de redacción asistida (ADR-D8).

El mecanismo es el de `apps.core.forms.RedaccionIAFormMixin`, estrenado en noticias. Aquí solo
queda la lista de campos que el editor deja de escribir cuando la IA va a redactar.

Son más que en una noticia porque `Norma` tiene más obligatorios: `tipo`, `ambito` y `resumen` no
llevan `blank=True` y `Noticia` no tiene equivalentes. Ninguno de ellos tiene valor por defecto, lo
que más adelante simplifica la tarea (ver `apps/normativa/tasks.py`).
"""
from django import forms

from apps.core.forms import RedaccionIAFormMixin

from . import importacion
from .models import Norma

OPCIONALES_CON_IA = ("titulo", "slug", "tipo", "ambito", "fecha", "resumen")


class NormaForm(RedaccionIAFormMixin):
    opcionales_con_ia = OPCIONALES_CON_IA

    class Meta:
        model = Norma
        fields = "__all__"


class SubirNormasForm(forms.Form):
    """Un solo campo: el Excel con las siete columnas de normativa (ADR-D9).

    La comprobación de extensión es una cortesía, no una garantía —quien renombre un .doc a .xlsx
    pasa igual—; lo que de verdad protege es que `importacion.analizar` no importa nada si no
    logra abrir el archivo o si la cabecera no es la esperada.
    """

    archivo = forms.FileField(
        label="Archivo Excel",
        widget=forms.ClearableFileInput(attrs={
            "accept": ".xlsx",
            "class": "border border-base-200 dark:border-base-800 rounded-md px-3 py-2 "
                     "text-sm w-full bg-white dark:bg-base-900",
        }),
        help_text=f"Formato .xlsx. La primera hoja debe traer las {len(importacion.COLUMNAS)} "
                  "columnas en la fila 1 y una norma por fila a partir de la 2.",
    )

    def clean_archivo(self):
        archivo = self.cleaned_data["archivo"]
        if not archivo.name.lower().endswith(".xlsx"):
            raise forms.ValidationError(
                "El archivo debe ser un Excel .xlsx. Si lo tienes en .xls o en CSV, ábrelo y "
                "guárdalo como «Libro de Excel (.xlsx)»."
            )
        return archivo
