"""Siembra la plataforma desde los datos reales.

Idempotente: se puede correr tantas veces como haga falta, y **no pisa lo que el cliente haya
editado** (ver `apps.core.semilla`). Es la puerta de entrada tanto de un entorno nuevo como del
despliegue en el VPS, y a propósito usa **los mismos importadores que el admin**: si el seed
funciona, el camino que recorrerá PREDES al subir su Excel también.

    manage.py seed                     catálogos + territorio + peligros + frecuencia
    manage.py seed --demo              además, el contenido de demostración del prototipo
    manage.py seed --capas             adjunta los GeoJSON fuente a las capas
    manage.py seed --tiles             además, genera los PMTiles (necesita tippecanoe)
    manage.py seed --solo-catalogos    solo catálogos, grupos y textos; sin importar Excel
"""
import os
import shutil
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.core import semilla
from apps.peligros.catalogo import CATEGORIAS_EVENTO, FUENTES, PELIGROS

APPS = Path(__file__).resolve().parents[3]

# Archivo dentro de DATOS_FUENTE_DIR → tipo de DatasetUpload
ARCHIVOS_DATASET = {
    "data/Base_Nivel Peligro_CCPP_Cusco.xlsx": "peligros_ccpp",
    "data/Base_Frecuencia_Peligro_Cusco.xlsx": "frecuencia_emergencias",
}
ARCHIVOS_CAPA = {
    "rios": "rios.geojson",
    "lagunas": "lagos-y-lagunas.geojson",
    "glaciares": "glaciares.geojson",
    "limites-provinciales": "limites-provinciales.geojson",
    "limites-distritales": "limites-distritales.geojson",
}

# Permisos por grupo (spec 03). El editor trabaja su contenido; el publicador además publica y
# gestiona datos y capas; el administrador toca usuarios y configuración del sitio.
APPS_EDITORIALES = ["medidas", "normativa", "biblioteca", "contenidos"]
GRUPOS = {
    # El Editor publica desde ADR-P3: al retirarse el paso de revisión, sin este permiso se
    # quedaba sin ninguna acción posible sobre su propio contenido.
    "Editor": {
        "apps": APPS_EDITORIALES,
        "acciones": {"add", "change", "view"},
        "publicar": True,
    },
    "Publicador": {
        "apps": APPS_EDITORIALES + ["datasets", "mapas", "peligros", "sitio"],
        "acciones": {"add", "change", "view", "delete"},
        "publicar": True,
    },
    "Administrador": {
        "apps": APPS_EDITORIALES
        + ["datasets", "mapas", "peligros", "sitio", "metricas", "territorio", "auth"],
        "acciones": {"add", "change", "view", "delete"},
        "publicar": True,
    },
}


class Command(BaseCommand):
    help = "Siembra catálogos, datos reales y (opcionalmente) contenido de demostración."

    def add_arguments(self, parser):
        parser.add_argument("--demo", action="store_true",
                            help="Carga el contenido de demostración del prototipo.")
        parser.add_argument("--tiles", action="store_true",
                            help="Genera los PMTiles de capas y centros poblados.")
        parser.add_argument("--capas", action="store_true",
                            help="Adjunta los GeoJSON fuente a las capas cartográficas.")
        parser.add_argument("--solo-catalogos", action="store_true",
                            help="Solo catálogos, grupos y textos; sin importar Excel.")
        parser.add_argument("--datos", default=None,
                            help="Carpeta con los Excel y GeoJSON (por defecto DATOS_FUENTE_DIR).")

    def handle(self, *args, **opciones):
        self.datos = Path(opciones["datos"] or settings.DATOS_FUENTE_DIR)

        self._titulo("Catálogos")
        self._catalogo_peligros()
        self._catalogo_eventos()
        self._fuentes()
        self._catalogo_procesos_grd()

        self._titulo("Sitio, capas y biblioteca")
        self._sitio()
        self._capas()
        self._categorias_documento()
        self._entidades_emisoras()

        self._titulo("Grupos y superusuario")
        self._grupos()
        self._superusuario()

        if opciones["solo_catalogos"]:
            self._nota("--solo-catalogos: no se importa ningún Excel.")
            return

        self._titulo("Datos reales (mismos importadores que usa el admin)")
        self._importar_datasets()

        if opciones["capas"] or opciones["tiles"]:
            self._titulo("Archivos de las capas")
            self._adjuntar_capas()

        if opciones["demo"]:
            self._titulo("Contenido de demostración")
            self._demo()

        if opciones["tiles"]:
            self._titulo("Tiles")
            self._generar_tiles()

        self._titulo("Resumen")
        self._resumen()

    # -- Catálogos ---------------------------------------------------------
    def _catalogo_peligros(self):
        """Los 9 peligros salen de `apps.peligros.catalogo`, no de un YAML.

        El importador necesita el mapeo hoja → peligro antes de tocar la base, así que el
        catálogo tiene que ser código. Duplicarlo en un YAML solo garantizaría que las dos
        copias se desincronicen. Por eso este sí se actualiza en cada corrida.
        """
        from apps.peligros.models import TipoPeligro

        registros = [
            {
                "slug": p["slug"],
                "nombre": p["nombre"],
                "hoja_excel": p["hoja"],
                "categoria_geo": p["categoria_geo"],
                "orden": p["orden"],
                "color": p["color"],
                "icono": p["icono"],
            }
            for p in PELIGROS
        ]
        creados, _ = semilla.sembrar(TipoPeligro, registros, "slug", actualizar=True)
        self._ok(f"{len(PELIGROS)} tipos de peligro ({creados} nuevos)")

    def _catalogo_eventos(self):
        from apps.peligros.models import CategoriaEvento, TipoEvento

        n_tipos = 0
        for cat in CATEGORIAS_EVENTO:
            semilla.sembrar(
                CategoriaEvento,
                [{
                    "slug": cat["slug"],
                    "nombre": cat["nombre"],
                    "orden": cat["orden"],
                    "columna_total": cat["columna_total"],
                }],
                "slug",
                actualizar=True,
            )
            categoria = CategoriaEvento.objects.get(slug=cat["slug"])
            semilla.sembrar(
                TipoEvento,
                [
                    {
                        "slug": slug,
                        "nombre": nombre,
                        "categoria": categoria,
                        "orden": orden,
                        "columna_excel": columna,
                    }
                    for orden, (nombre, slug, columna) in enumerate(cat["eventos"], start=1)
                ],
                "slug",
                actualizar=True,
            )
            n_tipos += len(cat["eventos"])
        self._ok(f"{len(CATEGORIAS_EVENTO)} categorías y {n_tipos} tipos de evento")

    def _fuentes(self):
        from apps.peligros.models import Fuente

        semilla.sembrar(Fuente, FUENTES, "nombre", actualizar=True)
        self._ok(f"{len(FUENTES)} fuentes")

    def _catalogo_procesos_grd(self):
        """Procesos de la GRD y el mapeo de actividades del PP 0068.

        Los procesos se actualizan en cada corrida: son código. **Las clasificaciones no**: son
        una propuesta que PREDES corrige en el admin, y volver a sembrarlas con `actualizar`
        deshacía su trabajo en el siguiente despliegue. Solo se crean las que falten.
        """
        from apps.inversion.catalogo import ACTIVIDAD_A_PROCESO, PROCESOS_GRD
        from apps.inversion.models import ClasificacionActividad, ProcesoGRD

        semilla.sembrar(ProcesoGRD, PROCESOS_GRD, "slug", actualizar=True)
        procesos = {p.slug: p for p in ProcesoGRD.objects.all()}

        # El nombre real de cada actividad llega con la importación; hasta entonces vale el
        # código, que es lo que identifica la fila.
        registros = [
            {
                "codigo": codigo,
                "nombre": codigo,
                "origen": ClasificacionActividad.Origen.ACTIVIDAD,
                "proceso": procesos[slug],
                "automatico": True,
            }
            for codigo, slug in ACTIVIDAD_A_PROCESO.items()
        ]
        creadas, _ = semilla.sembrar(ClasificacionActividad, registros, "codigo")
        self._ok(
            f"{len(PROCESOS_GRD)} procesos de la GRD y {len(registros)} actividades "
            f"clasificadas ({creadas} nuevas)"
        )

    # -- Sitio -------------------------------------------------------------
    def _sitio(self):
        from apps.sitio.models import BloqueTexto, ConfiguracionSitio, EnlaceMenu

        datos = semilla.leer(APPS / "sitio/semillas/sitio.yaml")
        if semilla.sembrar_singleton(ConfiguracionSitio, datos["configuracion"]):
            self._ok("configuración del sitio")
        else:
            self._ok("configuración del sitio (ya existía, no se toca)")
        creados, existentes = semilla.sembrar(EnlaceMenu, datos["menu"], ["zona", "url", "texto"])
        self._ok(f"menú: {creados} enlaces nuevos, {existentes} ya existían")
        creados, existentes = semilla.sembrar(BloqueTexto, datos["bloques"], "clave")
        self._ok(f"textos: {creados} bloques nuevos, {existentes} ya existían")

    def _capas(self):
        from apps.mapas.models import CapaCartografica

        datos = semilla.leer(APPS / "mapas/semillas/capas.yaml")
        creados, existentes = semilla.sembrar(CapaCartografica, datos["capas"], "slug")
        self._ok(f"capas: {creados} nuevas, {existentes} ya existían")

    def _entidades_emisoras(self):
        from apps.normativa.models import EntidadEmisora

        datos = semilla.leer(APPS / "normativa/semillas/entidades.yaml")
        creadas, existentes = semilla.sembrar(EntidadEmisora, datos["entidades"], "slug")
        self._ok(f"entidades emisoras: {creadas} nuevas, {existentes} ya existían")

    def _categorias_documento(self):
        from apps.biblioteca.models import CategoriaDocumento

        datos = semilla.leer(APPS / "biblioteca/semillas/categorias.yaml")
        creados, existentes = semilla.sembrar(CategoriaDocumento, datos["categorias"], "slug")
        self._ok(f"categorías de documento: {creados} nuevas, {existentes} ya existían")

    # -- Usuarios ----------------------------------------------------------
    def _grupos(self):
        for nombre, conf in GRUPOS.items():
            grupo, _ = Group.objects.get_or_create(name=nombre)
            candidatos = Permission.objects.filter(content_type__app_label__in=conf["apps"])
            permisos = [
                p
                for p in candidatos
                if p.codename.startswith(tuple(f"{a}_" for a in conf["acciones"]))
            ]
            if conf["publicar"]:
                permisos += list(Permission.objects.filter(codename="puede_publicar"))
            grupo.permissions.set(permisos)
            self._ok(f"grupo {nombre}: {len(permisos)} permisos")

    def _superusuario(self):
        Usuario = get_user_model()
        usuario = os.environ.get("DJANGO_SUPERUSER_USERNAME", "")
        clave = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        correo = os.environ.get("DJANGO_SUPERUSER_EMAIL", "")
        if not usuario or not clave:
            self._nota(
                "DJANGO_SUPERUSER_USERNAME/PASSWORD no están en el entorno: no se crea "
                "superusuario. Créalo con `manage.py createsuperuser`."
            )
            return
        if Usuario.objects.filter(username=usuario).exists():
            self._ok(f"superusuario «{usuario}» ya existe; no se toca su contraseña")
            return
        Usuario.objects.create_superuser(username=usuario, email=correo, password=clave)
        self._ok(f"superusuario «{usuario}» creado")

    # -- Datos reales ------------------------------------------------------
    def _importar_datasets(self):
        from apps.datasets.models import DatasetUpload
        from apps.datasets.tasks import procesar_dataset

        for relativo, tipo in ARCHIVOS_DATASET.items():
            origen = self.datos / relativo
            if not origen.exists():
                raise CommandError(
                    f"No se encontró «{origen}».\n"
                    f"Los Excel canónicos no se versionan (5.4 MB): apunta --datos o "
                    f"DATOS_FUENTE_DIR a la carpeta que los contiene (ver _docs/desarrollo.md)."
                )
            upload = DatasetUpload.objects.create(tipo=tipo)
            with origen.open("rb") as fh:
                upload.archivo.save(origen.name, File(fh), save=True)

            # Se invoca la función, no `.enqueue()`: el seed tiene que ser síncrono para poder
            # informar del resultado y fallar si el dato no entró.
            procesar_dataset.func(upload.pk, encadenar=False)
            upload.refresh_from_db()
            if upload.estado != DatasetUpload.Estado.ACTIVO:
                raise CommandError(
                    f"La importación de «{origen.name}» falló: "
                    f"{(upload.log or {}).get('error', 'ver el log en el admin')}"
                )
            self._ok(
                f"{origen.name}: {upload.filas_importadas:,} registros importados de "
                f"{upload.filas_leidas:,} filas leídas"
            )
            avisos = (upload.log or {}).get("advertencias", [])
            for aviso in avisos[:5]:
                self._nota(aviso)
            if len(avisos) > 5:
                self._nota(f"… y {len(avisos) - 5} advertencia(s) más en el log del admin.")

    def _adjuntar_capas(self):
        from apps.mapas.models import CapaCartografica

        for slug, archivo in ARCHIVOS_CAPA.items():
            capa = CapaCartografica.objects.filter(slug=slug).first()
            if capa is None:
                self._nota(f"No existe la capa «{slug}»; se omite.")
                continue
            if capa.archivo_geojson:
                self._ok(f"{slug}: ya tiene archivo adjunto")
                continue
            origen = self.datos / archivo
            if not origen.exists():
                self._nota(f"No se encontró «{origen}»; la capa «{slug}» queda sin archivo.")
                continue
            with origen.open("rb") as fh:
                capa.archivo_geojson.save(origen.name, File(fh), save=True)
            self._ok(f"{slug}: adjuntado {archivo} ({origen.stat().st_size / 1e6:.0f} MB)")

    # -- Demo --------------------------------------------------------------
    def _demo(self):
        from apps.contenidos.models import Noticia
        from apps.medidas.models import Medida
        from apps.normativa.models import EntidadEmisora, Norma
        from apps.peligros.models import TipoPeligro
        from apps.territorio.models import Distrito

        ahora = timezone.now()

        datos = semilla.leer(APPS / "medidas/semillas/demo.yaml")
        registros = []
        for m in datos["medidas"]:
            fila = dict(m)
            fila["tipo_peligro"] = TipoPeligro.objects.get(slug=fila.pop("peligro"))
            ubigeo = fila.pop("distrito", None)
            fila["distrito"] = Distrito.objects.filter(ubigeo=ubigeo).first() if ubigeo else None
            if ubigeo and fila["distrito"] is None:
                self._nota(f"medida {fila['slug']}: no existe el distrito {ubigeo}.")
            fila["estado"] = Medida.Estado.PUBLICADO
            fila["publicado_en"] = ahora
            registros.append(fila)
        creados, existentes = semilla.sembrar(Medida, registros, "slug")
        self._ok(f"medidas: {creados} nuevas, {existentes} ya existían")

        datos = semilla.leer(APPS / "normativa/semillas/demo.yaml")
        entidades = {e.slug: e for e in EntidadEmisora.objects.all()}
        registros = []
        for n in datos["normas"]:
            fila = dict(n)
            # Una de las cinco va sin entidad a propósito: su municipalidad distrital no está en
            # el catálogo de arranque, y así en desarrollo se ve también la ficha sin ella.
            fila["entidad_emisora"] = entidades.get(fila.pop("entidad", None))
            fila["estado"] = Norma.Estado.PUBLICADO
            fila["publicado_en"] = ahora
            registros.append(fila)
        creados, existentes = semilla.sembrar(Norma, registros, "slug")
        self._ok(f"normas: {creados} nuevas, {existentes} ya existían")

        datos = semilla.leer(APPS / "contenidos/semillas/demo.yaml")
        registros = [
            {**n, "estado": Noticia.Estado.PUBLICADO, "publicado_en": ahora}
            for n in datos["noticias"]
        ]
        creados, existentes = semilla.sembrar(Noticia, registros, "slug")
        self._ok(f"noticias: {creados} nuevas, {existentes} ya existían")

    # -- Tiles -------------------------------------------------------------
    def _generar_tiles(self):
        if not shutil.which(settings.TIPPECANOE_BIN):
            self._nota(
                f"No se encontró «{settings.TIPPECANOE_BIN}» en el PATH: los tiles no se "
                f"generan. Dentro del contenedor del backend sí está disponible."
            )
            return
        from apps.mapas.models import CapaCartografica
        from apps.mapas.tasks import generar_tiles_capa, generar_tiles_ccpp

        self._ok(f"tiles de centros poblados: {generar_tiles_ccpp.func()}")
        for capa in CapaCartografica.objects.exclude(archivo_geojson=""):
            generar_tiles_capa.func(capa.pk)
            capa.refresh_from_db()
            if capa.estado_tiles == CapaCartografica.EstadoTiles.OK:
                self._ok(f"tiles de {capa.slug}: {capa.features_generados:,} features")
            else:
                self._nota(f"tiles de {capa.slug}: ERROR — {capa.log_error[:200]}")

    # -- Salida ------------------------------------------------------------
    def _resumen(self):
        from apps.medidas.models import Medida
        from apps.peligros.models import (
            ClasificacionPeligro,
            FrecuenciaEmergencia,
            TotalDeclaradoEmergencias,
        )
        from apps.territorio.models import CentroPoblado, Distrito, Provincia

        total_ccpp = CentroPoblado.objects.count()
        clasificados = ClasificacionPeligro.objects.values("centro_poblado").distinct().count()
        filas = [
            ("Provincias", Provincia.objects.count()),
            ("Distritos", Distrito.objects.count()),
            ("Centros poblados", total_ccpp),
            ("  con alguna clasificación", clasificados),
            ("  sin dato clasificado", total_ccpp - clasificados),
            ("Clasificaciones de peligro", ClasificacionPeligro.objects.count()),
            ("Frecuencias de emergencia", FrecuenciaEmergencia.objects.count()),
            ("  distritos con desglose",
             FrecuenciaEmergencia.objects.values("distrito").distinct().count()),
            ("Totales declarados (ADR-D1)", TotalDeclaradoEmergencias.objects.count()),
            ("Medidas publicadas", Medida.publicados.count()),
        ]
        ancho = max(len(n) for n, _ in filas)
        for nombre, valor in filas:
            self.stdout.write(f"  {nombre.ljust(ancho)}  {valor:>7,}")

    def _titulo(self, texto):
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n{texto}"))

    def _ok(self, texto):
        self.stdout.write(f"  {self.style.SUCCESS('✓')} {texto}")

    def _nota(self, texto):
        self.stdout.write(f"  {self.style.WARNING('!')} {texto}")
