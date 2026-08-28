import re
import time
import uuid
from pathlib import Path

from django.conf import settings
from django.contrib import admin, messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.html import format_html
from django_ckeditor_5.widgets import CKEditor5Widget
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action

from apps.core.admin_workflow import WorkflowAdmin

from . import importacion
from .forms import SubirFichasACCForm
from .models import Medida, MedidaFichaACC, MedidaImagen, extracto

#: Un temporal abandonado (el usuario cerró la pestaña en la pantalla de confirmación) se barre
#: en la siguiente subida. Seis horas es holgado para revisar una lista larga y volver.
VIDA_TEMPORAL_S = 6 * 3600

CLAVE_SESION = "fichas_acc_importacion"


def _fichas(n: int, singular: str, plural: str) -> str:
    return f"{singular} {n} ficha" if n == 1 else f"{plural} {n} fichas"


def _filas(n: int, singular: str, plural: str) -> str:
    return f"{singular} {n} fila" if n == 1 else f"{plural} {n} filas"


class MedidaImagenInline(TabularInline):
    """Galería. `pie` es obligatorio en el modelo, así que el inline no lo deja en blanco."""

    model = MedidaImagen
    extra = 1
    fields = ("imagen", "vista_previa", "pie", "orden")
    readonly_fields = ("vista_previa",)
    ordering = ("orden",)

    @admin.display(description="vista previa")
    def vista_previa(self, obj):
        if not obj.pk or not obj.imagen:
            return "—"
        return format_html(
            '<img src="{}" style="height:64px;border-radius:4px">', obj.imagen.url
        )


@admin.register(Medida)
class MedidaAdmin(WorkflowAdmin, ModelAdmin):
    campos_rich = ["contenido"]

    list_display = ("titulo", "tipo_peligro", "ambito", "resultado", "distrito", "destacada")
    list_filter = ("estado", "resultado", "ambito", "tipo_peligro", "destacada")
    search_fields = ("titulo", "comunidad", "resumen_corto", "slug")
    prepopulated_fields = {"slug": ("titulo",)}
    autocomplete_fields = ("tipo_peligro", "distrito")
    inlines = (MedidaImagenInline,)
    list_select_related = ("tipo_peligro", "distrito")

    fieldsets = (
        (None, {"fields": ("titulo", "slug", "resumen_corto", "destacada")}),
        ("Clasificación", {"fields": ("tipo_peligro", "ambito", "resultado")}),
        ("Ubicación", {"fields": ("distrito", "comunidad", "centro_poblado")}),
        ("Contenido", {"fields": ("contenido", "video_url", "enlaces", "palabras_clave")}),
        ("Portada", {
            "fields": ("imagen_portada", "imagen_titulo"),
            "description": "Si dejas la portada vacía se usa la ilustración institucional del "
                           "peligro de la medida. No es un dato faltante.",
        }),
        ("Ficha técnica", {
            "classes": ("collapse",),
            "fields": ("fecha_implementacion", "actores", "costo_referencial", "documentos"),
        }),
        ("Estado editorial", {
            "fields": ("estado_badge", "nota_revision", "publicado_en", "creado_por",
                       "revisado_por"),
        }),
    )

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name in self.campos_rich:
            kwargs["widget"] = CKEditor5Widget(config_name="default")
        return super().formfield_for_dbfield(db_field, request, **kwargs)


@admin.register(MedidaFichaACC)
class MedidaFichaACCAdmin(ModelAdmin):
    """Separado de Medida (no inline): la ficha tiene 17 preguntas y mezclarla en el
    formulario de Medida lo haría inmanejable. Tampoco cuelga de una Medida — ver el modelo."""

    actions_list = ["importar_excel", "descargar_plantilla"]

    list_display = ("columna_001", "columna_002", "columna_003", "columna_005", "creado_en")
    search_fields = ("value_001", "value_002", "value_003")

    @admin.display(description=MedidaFichaACC._meta.get_field("value_001").verbose_name)
    def columna_001(self, obj):
        return extracto(obj.value_001)

    @admin.display(description=MedidaFichaACC._meta.get_field("value_002").verbose_name)
    def columna_002(self, obj):
        return extracto(obj.value_002)

    @admin.display(description=MedidaFichaACC._meta.get_field("value_003").verbose_name)
    def columna_003(self, obj):
        return extracto(obj.value_003)

    @admin.display(description=MedidaFichaACC._meta.get_field("value_005").verbose_name)
    def columna_005(self, obj):
        return extracto(obj.value_005)

    # --- Importación desde Excel ------------------------------------------------------------
    #
    # Unfold rutea `actions_list` desde su propio `get_urls()`, así que no hace falta declarar
    # URLs ni sustituir el `change_list_template`.

    @action(description="Importar desde Excel", url_path="importar", icon="upload_file",
            permissions=["add"])
    def importar_excel(self, request):
        """Sube el Excel, muestra qué entra y qué se omite, y solo entonces escribe.

        Las tres etapas viven en una sola vista y una sola URL porque comparten estado: el
        formulario de subida, la pantalla de confirmación y el guardado son el mismo trámite.
        """
        if request.method == "POST" and request.POST.get("confirmar"):
            return self._confirmar_importacion(request)

        formulario = SubirFichasACCForm(request.POST or None, request.FILES or None)
        if request.method == "POST" and formulario.is_valid():
            return self._previsualizar(request, formulario.cleaned_data["archivo"])

        return render(request, "admin/medidas/medidafichaacc/importar.html",
                      self._contexto(request, {"formulario": formulario}))

    @action(description="Descargar plantilla", url_path="plantilla", icon="download",
            permissions=["add"])
    def descargar_plantilla(self, request):
        respuesta = HttpResponse(
            importacion.plantilla_xlsx(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        respuesta["Content-Disposition"] = 'attachment; filename="plantilla-fichas-acc.xlsx"'
        return respuesta

    def _previsualizar(self, request, archivo):
        try:
            analisis = importacion.analizar(archivo)
        except importacion.ExcelInvalido as exc:
            return render(request, "admin/medidas/medidafichaacc/importar.html",
                          self._contexto(request, {
                              "formulario": SubirFichasACCForm(),
                              "error": str(exc),
                          }))

        # El análisis se rehace al confirmar, así que lo que se guarda es el archivo, no las
        # filas ya clasificadas: entre pantalla y pantalla pueden haber entrado fichas nuevas.
        token = self._guardar_temporal(archivo)
        request.session[CLAVE_SESION] = token

        return render(request, "admin/medidas/medidafichaacc/confirmar.html",
                      self._contexto(request, {
                          "analisis": analisis,
                          "nombre_archivo": archivo.name,
                      }))

    def _confirmar_importacion(self, request):
        ruta = self._ruta_temporal(request.session.get(CLAVE_SESION))
        if ruta is None or not ruta.exists():
            self.message_user(
                request,
                "La importación caducó o ya se aplicó. Vuelve a subir el archivo.",
                messages.WARNING,
            )
            return redirect(self._url_listado())

        try:
            with ruta.open("rb") as fh:
                analisis = importacion.analizar(fh)
            creadas = importacion.importar(analisis)
        except importacion.ExcelInvalido as exc:
            self.message_user(request, str(exc), messages.ERROR)
            return redirect(self._url_listado())
        finally:
            ruta.unlink(missing_ok=True)
            request.session.pop(CLAVE_SESION, None)

        omitidas = len(analisis.omitidas)
        if omitidas:
            self.message_user(
                request,
                f"Se {_fichas(creadas, 'importó', 'importaron')} y se "
                f"{_filas(omitidas, 'omitió', 'omitieron')} "
                "(nombre repetido o campos obligatorios vacíos).",
                messages.WARNING,
            )
        else:
            self.message_user(
                request, f"Se {_fichas(creadas, 'importó', 'importaron')}.", messages.SUCCESS
            )
        return redirect(self._url_listado())

    # --- Auxiliares -------------------------------------------------------------------------

    def _contexto(self, request, extra):
        contexto = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Importar fichas ACC desde Excel",
            "url_listado": self._url_listado(),
            "url_plantilla": reverse("admin:medidas_medidafichaacc_descargar_plantilla"),
            "columnas": importacion.columnas_esperadas(),
        }
        contexto.update(extra)
        return contexto

    def _url_listado(self):
        return reverse("admin:medidas_medidafichaacc_changelist")

    def _dir_temporal(self) -> Path:
        """Se lee en cada llamada, no al importar el módulo: así `settings` se puede sustituir
        en las pruebas y la suite no escribe dentro del repositorio."""
        return Path(settings.IMPORTACIONES_TMP_DIR)

    def _guardar_temporal(self, archivo) -> str:
        self._dir_temporal().mkdir(parents=True, exist_ok=True)
        self._barrer_temporales()
        token = uuid.uuid4().hex
        destino = self._dir_temporal() / f"{token}.xlsx"
        archivo.seek(0)
        with destino.open("wb") as fh:
            for trozo in archivo.chunks():
                fh.write(trozo)
        return token

    def _ruta_temporal(self, token):
        """El token viene de la sesión, pero se valida igual: es lo que forma un nombre de
        archivo, y un token con `../` leería fuera del directorio."""
        if not token or not re.fullmatch(r"[0-9a-f]{32}", token):
            return None
        return self._dir_temporal() / f"{token}.xlsx"

    def _barrer_temporales(self):
        limite = time.time() - VIDA_TEMPORAL_S
        for viejo in self._dir_temporal().glob("*.xlsx"):
            if viejo.stat().st_mtime < limite:
                viejo.unlink(missing_ok=True)
