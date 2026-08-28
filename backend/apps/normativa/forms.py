"""Formulario del admin para Norma, con el bloque de redacción asistida (ADR-D8).

El mecanismo es el de `apps.core.forms.RedaccionIAFormMixin`, estrenado en noticias. Aquí solo
queda la lista de campos que el editor deja de escribir cuando la IA va a redactar.

Son más que en una noticia porque `Norma` tiene más obligatorios: `tipo`, `ambito` y `resumen` no
llevan `blank=True` y `Noticia` no tiene equivalentes. Ninguno de ellos tiene valor por defecto, lo
que más adelante simplifica la tarea (ver `apps/normativa/tasks.py`).
"""
from apps.core.forms import RedaccionIAFormMixin

from .models import Norma

OPCIONALES_CON_IA = ("titulo", "slug", "tipo", "ambito", "fecha", "resumen")


class NormaForm(RedaccionIAFormMixin):
    opcionales_con_ia = OPCIONALES_CON_IA

    class Meta:
        model = Norma
        fields = "__all__"
