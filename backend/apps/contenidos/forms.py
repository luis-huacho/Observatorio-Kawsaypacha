"""Formulario del admin para Noticia, con el bloque de redacción asistida (ADR-D7).

Es el primer `ModelForm` propio del proyecto. Existe por una razón concreta: la casilla «Procesar
con IA» **no es un campo del modelo** —no tiene sentido persistir una intención de una sola vez— y
sin embargo cambia qué campos son obligatorios.

El truco, que es el idioma estándar de Django y el único que funciona aquí: los obligatorios se
relajan **siempre** en `__init__`, y `clean()` los vuelve a exigir cuando la casilla no viene
marcada. Al construir el formulario todavía no se sabe qué llegará por POST, así que decidirlo en
`__init__` a partir de la casilla es imposible.

Relajarlos en el formulario **no basta por sí solo**: `fecha` y `slug` son `NOT NULL` en la base y
`slug` además `unique`. Los valores provisionales los pone `NoticiaAdmin.save_model()`; aquí solo se
levanta la exigencia de que los escriba una persona.
"""
from django import forms

from apps.core.models import EstadoIA

from .models import Noticia

#: Los que deja de escribir el editor cuando la IA va a redactar. `cuerpo`, `autor` y
#: `palabras_clave` ya son opcionales en el modelo, y `tipo` tiene default.
OPCIONALES_CON_IA = ("titulo", "slug", "bajada", "fecha")


class NoticiaForm(forms.ModelForm):
    procesar_con_ia = forms.BooleanField(
        label="Procesar con IA",
        required=False,
        help_text=(
            "Al guardar, se leerá la URL de origen y se redactará la ficha en segundo plano. "
            "Puedes dejar el resto en blanco. Revisa y corrige antes de publicar."
        ),
    )

    class Meta:
        model = Noticia
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre in OPCIONALES_CON_IA:
            if nombre in self.fields:
                self.fields[nombre].required = False

        if self.instance.pk and self.instance.redactada_por_ia:
            # `disabled` y no `readonly_fields`: el admin resuelve `readonly_fields` contra el
            # modelo, y este campo no existe en él. Además Django ignora lo que llegue por POST en
            # un campo deshabilitado, así que el candado no se salta manipulando el formulario.
            campo = self.fields["procesar_con_ia"]
            campo.disabled = True
            campo.help_text = (
                "Esta noticia ya se redactó con IA. Cada registro solo puede usarla una vez; "
                "a partir de aquí se edita a mano."
            )

    def clean(self):
        datos = super().clean()
        con_ia = datos.get("procesar_con_ia") and not self.instance.redactada_por_ia

        if not con_ia:
            for nombre in OPCIONALES_CON_IA:
                if nombre in self.fields and not datos.get(nombre):
                    self.add_error(nombre, self.fields[nombre].error_messages["required"])
            return datos

        if not datos.get("url_origen"):
            self.add_error(
                "url_origen", "Hace falta la URL de origen para que la IA pueda redactar la noticia."
            )
        if self.instance.pk and self.instance.ia_estado == EstadoIA.PROCESANDO:
            self.add_error(
                "procesar_con_ia",
                "Ya se está redactando esta noticia. Espera a que termine antes de reintentar.",
            )
        return datos
