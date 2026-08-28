from django import forms


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
