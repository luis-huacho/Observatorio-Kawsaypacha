"""La fontanería común de los importadores de Excel del admin (ADR-D9).

Las tres etapas —subir, revisar, confirmar— viven en **una sola vista y una sola URL** porque son
el mismo trámite, y entre la pantalla de revisión y el «Importar» hay que guardar el archivo en
algún sitio. Eso, con su token, su barrido y su caducidad, es idéntico para cualquier importador;
lo único que cambia por app es el módulo de importación, las plantillas y los textos.

**Se generalizó en vez de copiarse, y por un motivo concreto:** copiar habría copiado también la
guarda de `_ruta_temporal()`, que valida el token contra `[0-9a-f]{32}` porque un token con `../`
leería fuera del directorio. Es el mismo argumento con el que ADR-D8 generalizó `RedaccionIAMixin`
—«duplicar habría duplicado la guarda anti-SSRF»—: una comprobación de seguridad duplicada es una
comprobación que un día se arregla en un sitio y no en el otro.

Cómo se usa: heredar de `ImportadorExcelAdminMixin` **antes** que del `ModelAdmin`, declarar los
cinco atributos de configuración y exponer las dos acciones de Unfold:

    class MiAdmin(ImportadorExcelAdminMixin, ModelAdmin):
        importacion_modulo = importacion
        importacion_form = SubirLoQueSeaForm
        importacion_clave_sesion = "lo_que_sea"
        importacion_plantillas = "admin/app/modelo"
        importacion_titulo = "Importar lo que sea desde Excel"
        importacion_archivo_plantilla = "plantilla-lo-que-sea.xlsx"

        @action(description="Importar desde Excel", url_path="importar", icon="upload_file",
                permissions=["add"])
        def importar_excel(self, request):
            return self.vista_importar(request)

Las acciones se declaran en cada admin y no aquí porque Unfold arma el nombre de la URL con el
`app_label` y el modelo, y el decorador tiene que verlas en la clase concreta.
"""
from __future__ import annotations

import re
import time
import uuid
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

#: Un temporal abandonado —alguien cerró la pestaña en la pantalla de confirmación— se barre en la
#: siguiente subida. Seis horas es holgado para revisar una lista larga y volver.
VIDA_TEMPORAL_S = 6 * 3600

TIPO_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def cuenta(n: int, singular: str, plural: str, sustantivo: str, sustantivo_plural: str) -> str:
    """«importó 1 norma» / «importaron 3 normas». La concordancia, en un solo sitio."""
    return f"{singular} {n} {sustantivo}" if n == 1 else f"{plural} {n} {sustantivo_plural}"


class ImportadorExcelAdminMixin:
    """Subir → revisar → confirmar, con el archivo a medio importar fuera de `MEDIA_ROOT`."""

    #: Módulo con `analizar()`, `importar()`, `plantilla_xlsx()` y `ExcelInvalido`.
    importacion_modulo = None
    #: Formulario con un único campo `archivo`.
    importacion_form = None
    #: Dónde se guarda el token en la sesión. Distinta por app, o dos importaciones a medias se
    #: pisarían entre sí.
    importacion_clave_sesion = ""
    #: Prefijo de las dos plantillas: `<prefijo>/importar.html` y `<prefijo>/confirmar.html`.
    importacion_plantillas = ""
    importacion_titulo = "Importar desde Excel"
    importacion_archivo_plantilla = "plantilla.xlsx"
    #: Para los mensajes finales: («norma», «normas»).
    importacion_sustantivo = ("registro", "registros")

    # --- Las dos vistas ---------------------------------------------------------------------

    def vista_importar(self, request):
        """Las tres etapas, en una sola URL: comparten estado y son el mismo trámite."""
        if request.method == "POST" and request.POST.get("confirmar"):
            return self._confirmar_importacion(request)

        formulario = self.importacion_form(request.POST or None, request.FILES or None)
        if request.method == "POST" and formulario.is_valid():
            return self._previsualizar(request, formulario.cleaned_data["archivo"])

        return self._render_subida(request, {"formulario": formulario})

    def vista_plantilla(self, request):
        respuesta = HttpResponse(
            self.importacion_modulo.plantilla_xlsx(), content_type=TIPO_XLSX
        )
        respuesta["Content-Disposition"] = (
            f'attachment; filename="{self.importacion_archivo_plantilla}"'
        )
        return respuesta

    # --- Etapas -----------------------------------------------------------------------------

    def _previsualizar(self, request, archivo):
        try:
            analisis = self.importacion_modulo.analizar(archivo)
        except self.importacion_modulo.ExcelInvalido as exc:
            return self._render_subida(
                request, {"formulario": self.importacion_form(), "error": str(exc)}
            )

        # Se guarda el ARCHIVO, no las filas ya clasificadas: el análisis se rehace al confirmar,
        # porque entre pantalla y pantalla pueden haber entrado registros nuevos.
        request.session[self.importacion_clave_sesion] = self._guardar_temporal(archivo)

        return render(
            request,
            f"{self.importacion_plantillas}/confirmar.html",
            self.contexto_importacion(
                request, {"analisis": analisis, "nombre_archivo": archivo.name}
            ),
        )

    def _confirmar_importacion(self, request):
        ruta = self._ruta_temporal(request.session.get(self.importacion_clave_sesion))
        if ruta is None or not ruta.exists():
            self.message_user(
                request,
                "La importación caducó o ya se aplicó. Vuelve a subir el archivo.",
                messages.WARNING,
            )
            return redirect(self._url_listado())

        try:
            with ruta.open("rb") as fh:
                analisis = self.importacion_modulo.analizar(fh)
            creados = self.importacion_modulo.importar(analisis)
        except self.importacion_modulo.ExcelInvalido as exc:
            self.message_user(request, str(exc), messages.ERROR)
            return redirect(self._url_listado())
        finally:
            # El temporal se consume una sola vez: sin esto, recargar la página de confirmación
            # importaría el archivo otra vez.
            ruta.unlink(missing_ok=True)
            request.session.pop(self.importacion_clave_sesion, None)

        self.message_user(request, *self.mensaje_importacion(creados, analisis))
        return redirect(self._url_listado())

    # --- Puntos de extensión ----------------------------------------------------------------

    def mensaje_importacion(self, creados: int, analisis) -> tuple[str, int]:
        singular, plural = self.importacion_sustantivo
        hecho = cuenta(creados, "importó", "importaron", singular, plural)
        omitidas = len(analisis.omitidas)
        if not omitidas:
            return f"Se {hecho}.", messages.SUCCESS
        return (
            f"Se {hecho} y se {cuenta(omitidas, 'omitió', 'omitieron', 'fila', 'filas')}. "
            "El motivo de cada omisión estaba en la pantalla anterior.",
            messages.WARNING,
        )

    def contexto_importacion(self, request, extra):
        contexto = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": self.importacion_titulo,
            "url_listado": self._url_listado(),
            "url_plantilla": self._url_admin("descargar_plantilla"),
        }
        contexto.update(extra)
        return contexto

    # --- Auxiliares -------------------------------------------------------------------------

    def _render_subida(self, request, extra):
        return render(
            request,
            f"{self.importacion_plantillas}/importar.html",
            self.contexto_importacion(request, extra),
        )

    def _url_admin(self, vista: str) -> str:
        opts = self.model._meta
        return reverse(f"admin:{opts.app_label}_{opts.model_name}_{vista}")

    def _url_listado(self) -> str:
        return self._url_admin("changelist")

    def _dir_temporal(self) -> Path:
        """Se lee en cada llamada, no al importar el módulo: así `settings` se puede sustituir en
        las pruebas y la suite no escribe dentro del repositorio."""
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
