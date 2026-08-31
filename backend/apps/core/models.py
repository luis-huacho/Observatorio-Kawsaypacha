from django.conf import settings
from django.db import models
from django.utils import timezone

# Permiso custom que habilita las transiciones de publicación (spec 03). Se declara en el
# Meta.permissions de cada modelo Workflow porque Django no hereda `permissions` de un abstracto.
PERMISO_PUBLICAR = "puede_publicar"


def permiso_publicar(entidad: str) -> list[tuple[str, str]]:
    """Fila lista para el `Meta.permissions` de un modelo Workflow."""
    return [(PERMISO_PUBLICAR, f"Puede publicar y archivar {entidad}")]


class TimeStampedMixin(models.Model):
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class HtmlRicoMixin(models.Model):
    """Sanea los campos de `campos_html` **en `save()`** (ADR-D2).

    Vivía solo en `WorkflowAdmin.save_model`, y eso dejaba la garantía a medias: cualquier
    escritura que no pasara por el formulario del admin —un `loaddata`, un script, un futuro
    importador— metía el HTML tal cual en la base. El `help_text` de esos campos ya prometía que
    se saneaba al guardar, así que la promesa estaba escrita en el sitio equivocado.

    Aquí abajo la garantía es del modelo, y el resto del sistema la hereda: el frontend inyecta
    con `dangerouslySetInnerHTML`, el PDF y el índice de Meilisearch leen de la base.
    """

    #: Campos con HTML de CKEditor que hay que sanear.
    campos_html: tuple[str, ...] = ()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        from apps.core.sanitizar import sanear

        for campo in self.campos_html:
            setattr(self, campo, sanear(getattr(self, campo, "")))
        super().save(*args, **kwargs)


class ImagenOptimizadaMixin(models.Model):
    """Reduce y optimiza los campos de `campos_imagen` **en `save()`**.

    Es el espejo de `HtmlRicoMixin`, y por la misma razón: la garantía tiene que ser del modelo,
    no del formulario. Un `loaddata`, un importador o la portada que baja la IA desde una URL
    escriben sin pasar por el admin, y el visitante se traga la foto entera igual.

    **Por qué en `save()` y no con `storage=` en el campo**, que sería lo primero que uno prueba:
    el `storage` forma parte de `FileField.deconstruct()`, así que ponerlo emitiría una migración
    por cada campo tocado —seis migraciones que no cambian ni una columna—. Declararlo aquí no
    emite ninguna, y hay una prueba de `makemigrations --check` que lo fija.

    El trabajo lo hace `apps.core.imagenes.optimizar`, compartido con el editor de texto rico, y de
    ahí sale gratis lo importante: **es idempotente y a prueba de fallos**. Una imagen ya reducida
    se devuelve intacta —correr esto en cada `save()` no la degrada—, y si Pillow no sabe abrirla
    (un SVG de logotipo, un archivo corrupto) se guarda tal cual antes que perderla.
    """

    #: Campos de imagen que hay que optimizar al guardar.
    campos_imagen: tuple[str, ...] = ()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        from pathlib import PurePosixPath

        from django.conf import settings

        from apps.core import imagenes

        for nombre in self.campos_imagen:
            campo = getattr(self, nombre, None)
            # **`_committed` es la pregunta correcta**, no si hay archivo: dice si este `FieldFile`
            # trae contenido nuevo sin escribir todavía. Un registro que se vuelve a guardar sin
            # tocar la imagen la tiene ya escrita, y releerla de disco para reoptimizarla en cada
            # `save()` sería trabajo inútil en el mejor caso y recompresión repetida en el peor.
            if not campo or campo._committed:
                continue
            optimizada = imagenes.optimizar(
                campo.file, settings.CONTENIDO_ANCHO_MAXIMO_PX, imagenes.FORMATO_PUBLICACION
            )
            if optimizada is campo.file:
                continue
            # **Solo el basename.** `FieldFile.save` vuelve a pasar el nombre por `upload_to`, así
            # que darle una ruta ya resuelta produciría `noticias/2026/08/noticias/2026/08/foo.webp`.
            base = PurePosixPath(str(campo.name or "imagen")).name
            campo.save(imagenes.renombrar(base, imagenes.FORMATO_PUBLICACION),
                       optimizada, save=False)
        super().save(*args, **kwargs)


class EstadoIA(models.TextChoices):
    """Estado de un campo que la IA puede rellenar.

    Vive aquí y no en una app concreta porque ya lo usan dos —`biblioteca.Documento` para el
    resumen de un PDF, y `contenidos.Noticia` y `normativa.Norma` para la redacción desde una
    URL— y el vocabulario tiene que ser el mismo: la insignia del admin y el texto que lee el
    editor se derivan de él. `Documento` conserva su copia idéntica para no arrastrar una
    migración que no cambia nada.
    """

    PENDIENTE = "pendiente", "Pendiente"
    PROCESANDO = "procesando", "Procesando"
    OK = "ok", "Generado"
    ERROR = "error", "Error"


class EstadoIAMixin(models.Model):
    """Un registro que la IA puede redactar. **La procedencia la declara cada modelo.**

    Los tres campos del estado son idénticos en todos ellos, así que viven aquí: si el candado o
    el vocabulario del estado divergieran entre apps, el mixin de admin y el sondeo que refresca
    la ficha —que son uno solo para todas— dejarían de valer para una de ellas. De hecho la lista
    blanca del sondeo se comprueba contra esta clase: lo que herede de aquí tiene que estar en
    `MODELOS_CON_IA`.

    **`redactada_por_ia` es el candado, y solo se cierra cuando la IA llegó a escribir.** Un
    timeout o una URL caída dejan `ia_estado=error` con el motivo a la vista y permiten reintentar:
    un corte de red no debería inutilizar un registro para siempre.

    De dónde redacta la IA **no** está aquí, y no es un olvido: en noticias y normas es una URL
    (`RedaccionIAMixin`, abajo) y en medidas es una ficha ACC ya cargada en la base (ADR-D10). No
    hay un campo común que abstraer entre un `URLField` y una clave foránea, solo un papel; quien
    lo nombra es `campo_origen` en el formulario.
    """

    #: Con lo que el admin rellena el título mientras la IA trabaja. Vive aquí porque lo escriben
    #: el admin y lo leen las tareas: es la marca por la que «¿lo escribió una persona?» sabe que
    #: ese título lo puso la máquina y puede sustituirlo.
    PREFIJO_PROVISIONAL = "(redactando)"

    ia_estado = models.CharField(
        "estado de la IA", max_length=12, choices=EstadoIA.choices, default=EstadoIA.PENDIENTE
    )
    log_ia = models.TextField("registro de la IA", blank=True)
    redactada_por_ia = models.BooleanField("redactada por IA", default=False)

    class Meta:
        abstract = True


class RedaccionIAMixin(EstadoIAMixin):
    """`EstadoIAMixin` + la procedencia es una URL (ADR-D7 para noticias, D8 para normas)."""

    url_origen = models.URLField(
        "URL de origen",
        max_length=500,
        blank=True,
        help_text="Página de la que se redactó la ficha. Queda como procedencia.",
    )

    class Meta:
        abstract = True


def slug_unico(obj) -> str:
    """Slug definitivo desde el título del registro, sin chocar con los que ya existen.

    Hace falta porque el provisional que puso el admin lleva un sufijo aleatorio —necesario para
    que dos fichas creadas seguidas no colisionen— que no tiene por qué quedarse en la URL pública.
    Vale para cualquier modelo con `titulo` y `slug`, que son los dos que redacta la IA.
    """
    from django.utils.text import slugify

    tope = obj._meta.get_field("slug").max_length
    base = slugify(obj.titulo)[: tope - 10] or obj.slug
    candidato, sufijo = base, 2
    hermanos = type(obj)._default_manager.exclude(pk=obj.pk)
    while hermanos.filter(slug=candidato).exists():
        candidato = f"{base}-{sufijo}"
        sufijo += 1
    return candidato


class PublicadosManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(estado=WorkflowMixin.Estado.PUBLICADO)


class WorkflowMixin(models.Model):
    """Flujo editorial: borrador → publicado, con avisos por correo (ADR-P3).

    El paso intermedio de «revisión» **se retiró por decisión del dueño del proyecto**. El TDR lo
    pedía (requisito 2), así que la decisión y su riesgo están escritos en el ADR: desde aquí,
    quien redacta también publica y nadie mira el contenido antes de que salga.

    `archivado` se conserva: retirar algo publicado y dejarlo en borrador no son lo mismo.
    """

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        PUBLICADO = "publicado", "Publicado"
        ARCHIVADO = "archivado", "Archivado"

    TRANSICIONES = {
        Estado.BORRADOR: {Estado.PUBLICADO, Estado.ARCHIVADO},
        Estado.PUBLICADO: {Estado.BORRADOR, Estado.ARCHIVADO},
        Estado.ARCHIVADO: {Estado.BORRADOR},
    }

    # Transiciones que exigen el permiso `puede_publicar`. Desde ADR-P3 los tres grupos lo tienen,
    # así que esto ya no separa a un editor de un publicador; se conserva porque sigue siendo la
    # única defensa frente a un usuario de staff sin grupo, que si no publicaría al sitio.
    TRANSICIONES_RESERVADAS = {
        (Estado.BORRADOR, Estado.PUBLICADO),
        (Estado.PUBLICADO, Estado.ARCHIVADO),
        (Estado.PUBLICADO, Estado.BORRADOR),
        (Estado.BORRADOR, Estado.ARCHIVADO),
    }

    estado = models.CharField(
        max_length=12, choices=Estado.choices, default=Estado.BORRADOR, db_index=True
    )
    publicado_en = models.DateTimeField(null=True, blank=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    nota_revision = models.TextField(
        "nota de revisión",
        blank=True,
        help_text="Comentario del revisor al devolver el contenido a borrador.",
    )

    objects = models.Manager()
    publicados = PublicadosManager()

    class Meta:
        abstract = True

    # -- Flujo editorial ---------------------------------------------------
    #: Sin estos campos no se publica. Lo declara cada modelo; vacío = sin condiciones.
    CAMPOS_PARA_PUBLICAR: tuple[str, ...] = ()

    def faltantes_para_publicar(self) -> list[str]:
        """Qué **impide** publicar este registro. Vacío = nada.

        Los declara el modelo en `CAMPOS_PARA_PUBLICAR`. Existe porque `estado` está excluido del
        formulario (`WorkflowAdmin.get_exclude`), así que publicar no pasa por ningún `clean()`:
        la única puerta es `transicionar()`, y ahí es donde tiene que estar la guarda.

        El bucle vivía en `Medida` y subió aquí cuando `Norma` necesitó lo mismo (ADR-D11): la
        alternativa era copiarlo, y una guarda duplicada es una guarda que se queda a medias en
        una de las dos copias. Resuelve solo las claves foráneas —comprobar `campo` en vez de
        `campo_id` dispara una consulta por campo— y trata el **título provisional como
        faltante**, porque publicar «(redactando) …» se ve idéntico a un acierto.
        """
        faltan = []
        provisional_prefijo = getattr(self, "PREFIJO_PROVISIONAL", None)
        for nombre in self.CAMPOS_PARA_PUBLICAR:
            campo = self._meta.get_field(nombre)
            valor = getattr(self, f"{nombre}_id" if campo.is_relation else nombre)
            provisional = (
                nombre == "titulo"
                and provisional_prefijo is not None
                and str(valor or "").startswith(provisional_prefijo)
            )
            if not valor or provisional:
                faltan.append(str(campo.verbose_name))
        return faltan

    def avisos_al_publicar(self) -> list[str]:
        """Lo que **no** impide publicar pero hay que mirar una vez.

        Separado de `faltantes_para_publicar` a propósito: convertir un aviso en un bloqueo deja
        al editor sin salida cuando el dato es correcto, y convertir un bloqueo en aviso publica
        lo que no debía. Los muestra `WorkflowAdmin._transicionar` como advertencia, igual que ya
        hace con las devoluciones sin nota de revisión.
        """
        return []

    def usuario_puede_publicar(self, usuario) -> bool:
        codigo = f"{self._meta.app_label}.{PERMISO_PUBLICAR}"
        return bool(usuario and (usuario.is_superuser or usuario.has_perm(codigo)))

    def transiciones_posibles(self, usuario=None) -> set[str]:
        """Estados alcanzables desde el actual, ya filtrados por el permiso del usuario.

        El admin usa esto para no ofrecer botones que luego van a fallar (spec 03).
        """
        actual = self.Estado(self.estado)
        posibles = set(self.TRANSICIONES[actual])
        if usuario is not None and not self.usuario_puede_publicar(usuario):
            posibles -= {d for d in posibles if (actual, d) in self.TRANSICIONES_RESERVADAS}
        return {e.value for e in posibles}

    def transicionar(self, nuevo_estado: str, usuario=None) -> None:
        actual = self.Estado(self.estado)
        nuevo = self.Estado(nuevo_estado)
        if nuevo not in self.TRANSICIONES[actual]:
            raise ValueError(f"Transición inválida: {actual.label} → {nuevo.label}")
        if (
            usuario is not None
            and (actual, nuevo) in self.TRANSICIONES_RESERVADAS
            and not self.usuario_puede_publicar(usuario)
        ):
            raise PermissionError(
                f"«{usuario}» no tiene permiso para pasar de {actual.label} a {nuevo.label}."
            )
        # Antes de tocar nada: un rechazo no puede dejar el estado escrito ni el correo encolado.
        if nuevo == self.Estado.PUBLICADO and (faltan := self.faltantes_para_publicar()):
            raise ValueError("Falta completar antes de publicar: " + ", ".join(faltan) + ".")

        self.estado = nuevo
        if nuevo == self.Estado.PUBLICADO:
            self.publicado_en = timezone.now()
        if nuevo in {self.Estado.PUBLICADO, self.Estado.BORRADOR} and usuario is not None:
            self.revisado_por = usuario
        self.save()

        # El correo se encola: un SMTP lento o caído no puede bloquear el admin.
        from apps.core.tasks import notificar_transicion_editorial

        notificar_transicion_editorial.enqueue(
            modelo=self._meta.label,
            pk=self.pk,
            titulo=str(self),
            de_estado=actual.value,
            a_estado=nuevo.value,
            usuario_id=getattr(usuario, "pk", None),
        )
