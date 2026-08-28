"""Formulario del admin para Noticia, con el bloque de redacción asistida (ADR-D7).

Todo el mecanismo vive en `apps.core.forms.RedaccionIAFormMixin`, compartido con normativa
(ADR-D8). Aquí solo queda lo que es de una noticia: qué campos deja de escribir el editor cuando
la IA va a redactar.
"""
from apps.core.forms import RedaccionIAFormMixin

from .models import Noticia

#: `cuerpo`, `autor` y `palabras_clave` ya son opcionales en el modelo, y `tipo` tiene default.
OPCIONALES_CON_IA = ("titulo", "slug", "bajada", "fecha")


class NoticiaForm(RedaccionIAFormMixin):
    opcionales_con_ia = OPCIONALES_CON_IA

    class Meta:
        model = Noticia
        fields = "__all__"
