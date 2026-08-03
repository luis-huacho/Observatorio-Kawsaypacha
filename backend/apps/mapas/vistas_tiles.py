"""Servido de `.pmtiles` **solo para desarrollo**, con soporte de HTTP Range.

En producción esto lo hace nginx (ADR-A14) y este módulo no se usa.

Existe porque el protocolo `pmtiles://` **lee el archivo por rangos**: pide la cabecera, luego
el directorio y luego cada tesela suelta. Ni `django.views.static.serve` ni `FileResponse`
implementan `Range` en Django 5.2, así que devuelven los 3 MB completos con un `200` en cada
petición. El visor acaba funcionando por accidente —descargando el archivo entero una y otra
vez— y el primer indicio del problema es que el mapa tarda una eternidad en local mientras en
producción va fino. Mejor que el entorno de desarrollo se comporte como el de producción.
"""
import mimetypes
import re
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse, HttpResponseNotModified
from django.utils.http import http_date
from django.views.decorators.http import require_safe

RANGO = re.compile(r"bytes=(\d*)-(\d*)")


@require_safe
def servir_tile(request, ruta: str):
    archivo = (Path(settings.MEDIA_ROOT) / "tiles" / ruta).resolve()
    raiz = (Path(settings.MEDIA_ROOT) / "tiles").resolve()
    # Sin esta comprobación, `../../` en la ruta serviría cualquier archivo del disco.
    if raiz not in archivo.parents or not archivo.is_file():
        raise Http404(f"No existe el tile «{ruta}».")

    tamano = archivo.stat().st_size
    mtime = archivo.stat().st_mtime
    tipo = mimetypes.guess_type(str(archivo))[0] or "application/octet-stream"

    cabecera_rango = request.META.get("HTTP_RANGE", "")
    coincidencia = RANGO.match(cabecera_rango) if cabecera_rango else None

    if coincidencia is None:
        respuesta = FileResponse(archivo.open("rb"), content_type=tipo)
        respuesta["Content-Length"] = str(tamano)
    else:
        inicio_txt, fin_txt = coincidencia.groups()
        if inicio_txt:
            inicio = int(inicio_txt)
            fin = int(fin_txt) if fin_txt else tamano - 1
        else:
            # `bytes=-500` significa los últimos 500 bytes, no "desde 0 hasta 500".
            inicio = max(tamano - int(fin_txt), 0)
            fin = tamano - 1
        fin = min(fin, tamano - 1)
        if inicio > fin:
            respuesta = HttpResponse(status=416)
            respuesta["Content-Range"] = f"bytes */{tamano}"
            return respuesta

        with archivo.open("rb") as fh:
            fh.seek(inicio)
            cuerpo = fh.read(fin - inicio + 1)
        respuesta = HttpResponse(cuerpo, status=206, content_type=tipo)
        respuesta["Content-Range"] = f"bytes {inicio}-{fin}/{tamano}"
        respuesta["Content-Length"] = str(len(cuerpo))

    respuesta["Accept-Ranges"] = "bytes"
    respuesta["Last-Modified"] = http_date(mtime)
    respuesta["Cache-Control"] = "public, max-age=3600"
    # Mismas cabeceras CORS que pondrá nginx: así el visor en dev se comporta igual que en
    # producción, incluida la lectura de respuestas parciales cross-origin.
    respuesta["Access-Control-Allow-Origin"] = "*"
    respuesta["Access-Control-Expose-Headers"] = "Content-Length,Content-Range"

    if request.META.get("HTTP_IF_MODIFIED_SINCE") and coincidencia is None:
        from django.utils.http import parse_http_date_safe

        desde = parse_http_date_safe(request.META["HTTP_IF_MODIFIED_SINCE"])
        if desde is not None and int(mtime) <= desde:
            return HttpResponseNotModified()

    return respuesta
