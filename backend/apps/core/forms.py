"""El bloque «Procesar con IA» del formulario del admin (ADR-D7, ADR-D8).

La casilla **no es un campo del modelo** —no tiene sentido persistir una intención de una sola
vez— y sin embargo cambia qué campos son obligatorios. El truco, que es el idioma estándar de
Django y el único que funciona aquí: los obligatorios se relajan **siempre** en `__init__`, y
`clean()` los vuelve a exigir cuando la casilla no viene marcada. Al construir el formulario
todavía no se sabe qué llegará por POST, así que decidirlo en `__init__` a partir de la casilla es
imposible.

Relajarlos en el formulario **no basta por sí solo**: hay campos `NOT NULL` y alguno `unique`. Los
valores provisionales los pone `RedaccionIAAdminMixin.provisionales_ia()`; aquí solo se levanta la
exigencia de que los escriba una persona.
"""
from django import forms

from apps.core.models import EstadoIA


class RedaccionIAFormMixin(forms.ModelForm):
    """Cada formulario declara `opcionales_con_ia` con los suyos y hereda todo lo demás."""

    #: Los que deja de escribir el editor cuando la IA va a redactar.
    opcionales_con_ia: tuple[str, ...] = ()

    procesar_con_ia = forms.BooleanField(
        label="Procesar con IA",
        required=False,
        help_text=(
            "Al guardar, se leerá la URL de origen y se redactará la ficha en segundo plano. "
            "Puedes dejar el resto en blanco. Revisa y corrige antes de publicar."
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre in self.opcionales_con_ia:
            if nombre in self.fields:
                self.fields[nombre].required = False

        if self.instance.pk and self.instance.redactada_por_ia:
            # `disabled` y no `readonly_fields`: el admin resuelve `readonly_fields` contra el
            # modelo, y este campo no existe en él. Además Django ignora lo que llegue por POST en
            # un campo deshabilitado, así que el candado no se salta manipulando el formulario.
            campo = self.fields["procesar_con_ia"]
            campo.disabled = True
            campo.help_text = (
                f"Esta {self._meta.model._meta.verbose_name} ya se redactó con IA. Cada registro "
                f"solo puede usarla una vez; a partir de aquí se edita a mano."
            )

    def clean(self):
        datos = super().clean()
        con_ia = datos.get("procesar_con_ia") and not self.instance.redactada_por_ia
        nombre = self._meta.model._meta.verbose_name

        if not con_ia:
            for campo in self.opcionales_con_ia:
                if campo in self.fields and not datos.get(campo):
                    self.add_error(campo, self.fields[campo].error_messages["required"])
            return datos

        if not datos.get("url_origen"):
            self.add_error(
                "url_origen",
                f"Hace falta la URL de origen para que la IA pueda redactar la {nombre}.",
            )
        if self.instance.pk and self.instance.ia_estado == EstadoIA.PROCESANDO:
            self.add_error(
                "procesar_con_ia",
                f"Ya se está redactando esta {nombre}. Espera a que termine antes de reintentar.",
            )
        return datos
