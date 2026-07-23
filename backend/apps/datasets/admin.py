from django.contrib import admin, messages
from unfold.admin import ModelAdmin

from .models import DatasetUpload
from .tasks import procesar_dataset


@admin.register(DatasetUpload)
class DatasetUploadAdmin(ModelAdmin):
    list_display = [
        "tipo_dataset",
        "estado",
        "activo",
        "filas_importadas",
        "subido_por",
        "creado_en",
    ]
    list_filter = ["tipo_dataset", "estado", "activo"]
    readonly_fields = [
        "estado",
        "log",
        "filas_leidas",
        "filas_importadas",
        "activo",
        "activado_en",
        "subido_por",
    ]
    actions = ["validar_e_importar"]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.subido_por = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="Validar e importar (reemplaza los datos activos)")
    def validar_e_importar(self, request, queryset):
        for upload in queryset:
            upload.estado = DatasetUpload.Estado.VALIDANDO
            upload.save(update_fields=["estado"])
            procesar_dataset.enqueue(upload.pk)
        self.message_user(
            request,
            f"{queryset.count()} carga(s) encoladas; el resultado aparecerá en el log.",
            level=messages.SUCCESS,
        )
