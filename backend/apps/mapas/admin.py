from django.contrib import admin, messages
from unfold.admin import ModelAdmin

from apps.core.admin_workflow import badge

from .models import CapaCartografica


@admin.register(CapaCartografica)
class CapaCartograficaAdmin(ModelAdmin):
    """Reemplazo de capas sin asistencia técnica (requisito 1 del TDR).

    El flujo que hará PREDES: subir el GeoJSON nuevo → «(Re)generar tiles» → ver el resultado
    en el visor. El swap de los `.pmtiles` es atómico, así que el mapa público nunca ve un
    tile a medio escribir.
    """

    list_display = ("nombre", "slug", "tipo_geometria", "estado_badge", "features_generados",
                    "visible_por_defecto", "orden")
    list_filter = ("estado_tiles", "tipo_geometria", "visible_por_defecto")
    list_editable = ("orden", "visible_por_defecto")
    search_fields = ("nombre", "slug")
    prepopulated_fields = {"slug": ("nombre",)}
    actions = ("regenerar_tiles",)
    readonly_fields = ("estado_badge", "estado_tiles", "tipo_geometria", "pmtiles",
                       "crs_origen", "features_generados", "log_error")

    fieldsets = (
        (None, {"fields": ("nombre", "slug", "descripcion", "archivo_geojson")}),
        ("Recorte a Cusco", {
            "fields": ("filtro_atributo", "simplificacion"),
            "description": "Las capas nacionales se recortan a la región. Por atributo: "
                           "<code>DN99=CUSCO</code>, o <code>DPTO ILIKE cusco</code> cuando la "
                           "fuente mezcla mayúsculas. Vacío = recorte espacial con el polígono "
                           "regional.",
        }),
        ("Apariencia en el mapa", {
            "fields": ("estilo", "min_zoom", "max_zoom", "visible_por_defecto", "orden"),
            "description": "El estilo es el «paint» de MapLibre: cambiar color o grosor no "
                           "requiere tocar código.",
        }),
        ("Atribución", {"fields": ("fuente", "atribucion")}),
        ("Estado de los tiles", {
            "fields": ("estado_badge", "crs_origen", "features_generados", "pmtiles",
                       "log_error"),
        }),
    )

    @admin.display(description="tiles")
    def estado_badge(self, obj):
        estilos = {
            "pendiente": ("#6B7280", "#F3F4F6"),
            "generando": ("#1D4ED8", "#EFF6FF"),
            "ok": ("#0B3B26", "#E7F0EA"),
            "error": ("#7C2D12", "#FEF2F2"),
        }
        color, fondo = estilos.get(obj.estado_tiles, ("#1F2937", "#F3F4F6"))
        return badge(obj.get_estado_tiles_display(), color, fondo)

    @admin.action(description="(Re)generar tiles")
    def regenerar_tiles(self, request, queryset):
        from apps.mapas.tasks import generar_tiles_capa

        encoladas = 0
        for capa in queryset:
            if not capa.archivo_geojson:
                self.message_user(
                    request, f"«{capa}» no tiene archivo GeoJSON que procesar.", messages.WARNING
                )
                continue
            capa.estado_tiles = CapaCartografica.EstadoTiles.GENERANDO
            capa.save(update_fields=["estado_tiles"])
            generar_tiles_capa.enqueue(capa.pk)
            encoladas += 1
        if encoladas:
            self.message_user(
                request,
                f"{encoladas} capa(s) en cola. Las capas de escala nacional tardan unos "
                f"minutos; el estado y el log se actualizan en esta misma lista.",
                messages.SUCCESS,
            )

    def save_model(self, request, obj, form, change):
        archivo_nuevo = "archivo_geojson" in (form.changed_data or [])
        super().save_model(request, obj, form, change)
        if archivo_nuevo and obj.archivo_geojson:
            from apps.mapas.tasks import generar_tiles_capa

            CapaCartografica.objects.filter(pk=obj.pk).update(
                estado_tiles=CapaCartografica.EstadoTiles.GENERANDO
            )
            generar_tiles_capa.enqueue(obj.pk)
            self.message_user(
                request,
                "Archivo nuevo: los tiles se están regenerando en segundo plano. El mapa "
                "público seguirá mostrando la versión anterior hasta que terminen.",
                messages.INFO,
            )
