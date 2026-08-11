"""Calcula el centroide de cada distrito desde la capa de límites distritales.

El visor necesita un punto por distrito para colgar lo que se mide por distrito —hoy el ícono de
emergencias—. Hasta que hubo geometría se usaba la mediana de los centros poblados, que nunca
sacaba el punto de su distrito pero se desviaba **3.4 km de mediana y hasta 27 km** en los
distritos grandes de selva (Echarate, Checacupe). Este comando lo sustituye por el centroide
real; la mediana se conserva como repliegue en `consultas.centroides_distritales`.

Lee el GeoJSON de la capa `limites-distritales` ya adjunta en el admin, así que no descarga nada
ni depende del repositorio de origen: la capa se sube una vez y esto trabaja sobre ella.
"""
import json

from django.core.management.base import BaseCommand, CommandError

SLUG_CAPA = "limites-distritales"


class Command(BaseCommand):
    help = "Calcula y guarda el centroide de cada distrito desde la capa de límites."

    def add_arguments(self, parser):
        parser.add_argument(
            "--capa",
            default=SLUG_CAPA,
            help=f"Slug de la capa de límites distritales (por defecto «{SLUG_CAPA}»).",
        )

    def handle(self, *args, **opciones):
        from apps.mapas.models import CapaCartografica
        from apps.territorio.models import Distrito

        capa = CapaCartografica.objects.filter(slug=opciones["capa"]).first()
        if capa is None or not capa.archivo_geojson:
            raise CommandError(
                f"La capa «{opciones['capa']}» no existe o no tiene archivo adjunto. "
                f"Corre `manage.py seed --capas` antes."
            )

        with capa.archivo_geojson.open("r") as fh:
            datos = json.load(fh)

        por_ubigeo = {d.ubigeo: d for d in Distrito.objects.all()}
        actualizados, fuera, sin_padron = [], [], []

        for feature in datos.get("features", []):
            props = feature.get("properties") or {}
            ubigeo = str(props.get("UBIGEO") or props.get("CODIGO") or "").strip()
            distrito = por_ubigeo.get(ubigeo)
            if distrito is None:
                # Solo interesan los de Cusco: el archivo trae el país entero.
                if ubigeo.startswith("08"):
                    sin_padron.append(ubigeo)
                continue

            anillo = _anillo_mayor(feature["geometry"])
            if not anillo:
                continue
            punto = _centroide(anillo)
            if punto is None:
                continue
            if not _dentro(punto, anillo):
                # Distritos cóncavos o en herradura: el centroide de área cae fuera. Se deja el
                # campo vacío y el repliegue hace su trabajo — guardar un punto fuera del
                # distrito sería peor que la aproximación que ya teníamos.
                fuera.append(f"{distrito.nombre} ({ubigeo})")
                continue

            distrito.lon, distrito.lat = punto
            actualizados.append(distrito)

        Distrito.objects.bulk_update(actualizados, ["lat", "lon"], batch_size=200)

        self.stdout.write(self.style.SUCCESS(f"  ✓ {len(actualizados)} distritos con centroide"))
        if fuera:
            self.stdout.write(
                self.style.WARNING(
                    f"  ! {len(fuera)} con el centroide fuera de su polígono, se dejan sin punto "
                    f"y caen en la mediana de sus centros poblados: {', '.join(fuera)}"
                )
            )
        if sin_padron:
            self.stdout.write(
                self.style.WARNING(
                    f"  ! {len(sin_padron)} ubigeos de Cusco en la capa que no están en el "
                    f"padrón: {', '.join(sorted(sin_padron))}"
                )
            )
        sin_centroide = Distrito.objects.filter(lat=None).count()
        if sin_centroide:
            self.stdout.write(f"  · {sin_centroide} distritos siguen sin centroide")


def _anillo_mayor(geometria) -> list | None:
    """El anillo exterior con más vértices.

    Un distrito puede ser un `MultiPolygon` por sus islas o exclaves; el centroide se calcula
    sobre la parte principal, que es donde tiene sentido colgar un ícono.
    """
    if geometria["type"] == "Polygon":
        anillos = [geometria["coordinates"][0]]
    elif geometria["type"] == "MultiPolygon":
        anillos = [p[0] for p in geometria["coordinates"]]
    else:
        return None
    return max(anillos, key=len) if anillos else None


def _centroide(anillo) -> tuple[float, float] | None:
    """Centroide **de área**, no promedio de vértices.

    El promedio se desplaza hacia el lado donde el contorno tiene más detalle, que en estos
    archivos es la frontera con más recortes: en un distrito alargado eso mueve el punto varios
    kilómetros sin ninguna razón geográfica.
    """
    area = cx = cy = 0.0
    for i in range(len(anillo) - 1):
        x0, y0 = anillo[i][0], anillo[i][1]
        x1, y1 = anillo[i + 1][0], anillo[i + 1][1]
        cruz = x0 * y1 - x1 * y0
        area += cruz
        cx += (x0 + x1) * cruz
        cy += (y0 + y1) * cruz
    if area == 0:
        return None
    area *= 0.5
    return (cx / (6 * area), cy / (6 * area))


def _dentro(punto, anillo) -> bool:
    """Point-in-polygon por conteo de cruces."""
    x, y = punto
    dentro = False
    for i in range(len(anillo) - 1):
        x0, y0 = anillo[i][0], anillo[i][1]
        x1, y1 = anillo[i + 1][0], anillo[i + 1][1]
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            dentro = not dentro
    return dentro
