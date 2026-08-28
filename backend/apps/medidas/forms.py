from django import forms

from apps.core.forms import RedaccionIAFormMixin

from .models import Medida, MedidaFichaACC

#: Los que el editor deja de escribir cuando la IA va a redactar. Son más que en una norma porque
#: `Medida` tiene más obligatorios; `tipo_peligro` está entre ellos y por eso la migración 0007 lo
#: hizo nullable (ADR-D10): es el único que no puede guardarse como cadena vacía.
OPCIONALES_CON_IA = ("titulo", "slug", "tipo_peligro", "ambito", "resultado", "resumen_corto")


class MedidaForm(RedaccionIAFormMixin):
    """Formulario del admin para Medida, con el bloque de redacción asistida (ADR-D10).

    Dos cosas propias de este caso, y las dos importan:

    - **La procedencia es una ficha, no una URL** (`campo_origen`). El mecanismo de `core` ya lo
      admite; aquí solo se le dice cuál es.
    - **El select solo es obligatorio en el alta.** Exigirlo siempre dejaría sin poder guardar a
      todas las medidas que ya existen —las de la semilla, las escritas a mano— por un campo que
      nació después que ellas.
    """

    opcionales_con_ia = OPCIONALES_CON_IA
    campo_origen = "ficha_acc"
    mensaje_sin_origen = "Elige la ficha ACC de la que la IA va a redactar la {nombre}."
    ayuda_procesar_con_ia = (
        "Al guardar, se leerán las respuestas de la ficha y se redactará la medida en segundo "
        "plano. Puedes dejar el resto en blanco. Revisa y corrige antes de publicar."
    )

    class Meta:
        model = Medida
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        campo = self.fields.get("ficha_acc")
        if campo is None:
            return
        # `incluyendo` es lo que permite volver a guardar una medida ya redactada: su propia ficha
        # ya está gastada y sin esto el campo respondería «Escoja una opción válida».
        campo.queryset = MedidaFichaACC.objects.disponibles_para_ia(
            incluyendo=self.instance.ficha_acc_id
        )
        campo.required = self.instance.pk is None


class SubirFichasACCForm(forms.Form):
    """Un solo campo: el Excel con las 17 columnas de la ficha.

    La comprobación de extensión es una cortesía, no una garantía —quien renombre un .doc a
    .xlsx pasa igual—; lo que de verdad protege es que `importacion.analizar` no importa nada si
    no logra abrir el archivo o si la cabecera no es la esperada.
    """

    archivo = forms.FileField(
        label="Archivo Excel",
        widget=forms.ClearableFileInput(attrs={
            "accept": ".xlsx",
            "class": "border border-base-200 dark:border-base-800 rounded-md px-3 py-2 "
                     "text-sm w-full bg-white dark:bg-base-900",
        }),
        help_text="Formato .xlsx. La primera hoja debe traer las 17 columnas de la ficha en la "
                  "fila 1 y una ficha por fila a partir de la 2.",
    )

    def clean_archivo(self):
        archivo = self.cleaned_data["archivo"]
        if not archivo.name.lower().endswith(".xlsx"):
            raise forms.ValidationError(
                "El archivo debe ser un Excel .xlsx. Si lo tienes en .xls o en CSV, ábrelo y "
                "guárdalo como «Libro de Excel (.xlsx)»."
            )
        return archivo
