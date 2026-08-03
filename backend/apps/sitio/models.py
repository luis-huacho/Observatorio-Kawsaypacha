from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimeStampedMixin, WorkflowMixin, permiso_publicar


class ConfiguracionSitio(TimeStampedMixin):
    """Singleton con la marca y los datos de contacto. Se edita, no se crea."""

    nombre_sitio = models.CharField(max_length=150, default="Observatorio Kallpachakuy")
    descripcion_footer = models.TextField(blank=True)
    email_contacto = models.EmailField(blank=True)
    telefono = models.CharField(max_length=60, blank=True)
    direccion = models.CharField(max_length=250, blank=True)
    redes = models.JSONField(
        default=dict, blank=True, help_text='P. ej. {"facebook": "https://…"}.'
    )
    # [+] futuro
    mensaje_banner = models.CharField(max_length=300, blank=True)
    logo = models.ImageField(upload_to="sitio/", null=True, blank=True)
    logo_footer = models.ImageField(upload_to="sitio/", null=True, blank=True)

    class Meta:
        verbose_name = "configuración del sitio"
        verbose_name_plural = "configuración del sitio"

    def __str__(self) -> str:
        return self.nombre_sitio

    def clean(self):
        if not self.pk and ConfiguracionSitio.objects.exists():
            raise ValidationError("Ya existe la configuración del sitio: edita la que hay.")

    @classmethod
    def get_solo(cls) -> "ConfiguracionSitio":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class BloqueTexto(TimeStampedMixin):
    """Texto estático administrable, identificado por clave (`home.hero.titulo`, `sobre.mision`).

    Un modelo por página multiplicaría tablas y admins para lo mismo; la clave con prefijo
    permite agrupar en el admin y que el frontend pida un solo payload.
    """

    class Pagina(models.TextChoices):
        HOME = "home", "Portada"
        SOBRE = "sobre", "Sobre el observatorio"
        PELIGROS = "peligros", "Exposición a peligros"
        MEDIDAS = "medidas", "Medidas"
        NORMATIVA = "normativa", "Normativa"
        RECURSOS = "recursos", "Recursos"
        FOOTER = "footer", "Pie de página"
        GENERAL = "general", "General"

    clave = models.SlugField(max_length=80, unique=True, help_text="P. ej. home.hero.titulo")
    titulo = models.CharField(max_length=200, blank=True)
    cuerpo = models.TextField(
        blank=True, help_text="HTML de CKEditor 5. Se sanea al guardar (ADR-D2)."
    )
    pagina = models.CharField(max_length=12, choices=Pagina.choices, default=Pagina.GENERAL)

    class Meta:
        ordering = ["pagina", "clave"]
        verbose_name = "bloque de texto"
        verbose_name_plural = "bloques de texto"

    def __str__(self) -> str:
        return self.clave


class HeroSlide(TimeStampedMixin, WorkflowMixin):
    titulo = models.CharField(max_length=200)
    subtitulo = models.CharField(max_length=300, blank=True)
    imagen = models.ImageField(upload_to="hero/", null=True, blank=True)
    cta_texto = models.CharField("texto del botón", max_length=80, blank=True)
    cta_url = models.CharField("destino del botón", max_length=200, blank=True)
    orden = models.PositiveSmallIntegerField(default=0)
    # [+] futuro
    vigente_desde = models.DateField(null=True, blank=True)
    vigente_hasta = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["orden"]
        verbose_name = "slide del hero"
        verbose_name_plural = "hero de portada"
        permissions = permiso_publicar("slides del hero")

    def __str__(self) -> str:
        return self.titulo


class EnlaceMenu(TimeStampedMixin):
    """Navegación controlada por datos: PREDES reordena y oculta sin tocar código.

    Prioridades vive aquí con `visible=False` (ADR-P1): no se borra, se oculta.
    """

    class Zona(models.TextChoices):
        HEADER = "header", "Menú principal"
        FOOTER = "footer", "Pie de página"

    zona = models.CharField(max_length=8, choices=Zona.choices)
    texto = models.CharField(max_length=80)
    url = models.CharField(max_length=200)
    grupo = models.CharField(
        max_length=60,
        blank=True,
        help_text="Columna del pie en la que se agrupa (p. ej. «Más»). Vacío en el header.",
    )
    orden = models.PositiveSmallIntegerField(default=0)
    visible = models.BooleanField(default=True)

    class Meta:
        ordering = ["zona", "orden"]
        verbose_name = "enlace del menú"
        verbose_name_plural = "menú"

    def __str__(self) -> str:
        return f"{self.get_zona_display()}: {self.texto}"
