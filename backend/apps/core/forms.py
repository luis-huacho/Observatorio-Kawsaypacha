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
    """Cada formulario declara `opcionales_con_ia` con los suyos y hereda todo lo demás.

    **De dónde redacta la IA lo nombra `campo_origen`.** Empezó estando clavado en `url_origen`,
    que es lo que usan noticias y normas; desde ADR-D10 hay un tercer caso cuya procedencia es una
    ficha ACC ya cargada en la base, y un `URLField` y una clave foránea no tienen nada que
    abstraer salvo el papel que cumplen. Los valores por defecto son los de siempre, así que los
    dos formularios que ya existían no cambian.
    """

    #: Los que deja de escribir el editor cuando la IA va a redactar.
    opcionales_con_ia: tuple[str, ...] = ()
    #: El campo que declara la procedencia. Sin él, la casilla no tiene de dónde redactar.
    campo_origen: str = "url_origen"
    #: `{nombre}` se sustituye por el `verbose_name` del modelo.
    mensaje_sin_origen: str = (
        "Hace falta la URL de origen para que la IA pueda redactar la {nombre}."
    )
    ayuda_procesar_con_ia: str = (
        "Al guardar, se leerá la URL de origen y se redactará la ficha en segundo plano. "
        "Puedes dejar el resto en blanco. Revisa y corrige antes de publicar."
    )

    procesar_con_ia = forms.BooleanField(label="Procesar con IA", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["procesar_con_ia"].help_text = self.ayuda_procesar_con_ia
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

        if not datos.get(self.campo_origen):
            self.add_error(self.campo_origen, self.mensaje_sin_origen.format(nombre=nombre))
        if self.instance.pk and self.instance.ia_estado == EstadoIA.PROCESANDO:
            self.add_error(
                "procesar_con_ia",
                f"Ya se está redactando esta {nombre}. Espera a que termine antes de reintentar.",
            )
        return datos
