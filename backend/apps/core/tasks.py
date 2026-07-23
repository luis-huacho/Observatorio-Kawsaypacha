from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django_tasks import task


@task()
def notificar_transicion_editorial(
    modelo: str,
    pk,
    titulo: str,
    de_estado: str,
    a_estado: str,
    usuario_id=None,
) -> None:
    """Aviso por correo del flujo editorial (requisito TDR).

    - A revisión: se avisa al grupo "Publicadores".
    - Publicado o devuelto a borrador: se avisa al autor del contenido.
    """
    User = get_user_model()
    destinatarios: list[str] = []

    if a_estado == "revision":
        destinatarios = list(
            User.objects.filter(groups__name="Publicadores", is_active=True)
            .exclude(email="")
            .values_list("email", flat=True)
        )
    else:
        from django.apps import apps as django_apps

        obj = django_apps.get_model(modelo).objects.filter(pk=pk).first()
        autor = getattr(obj, "creado_por", None)
        if autor and autor.email:
            destinatarios = [autor.email]

    if not destinatarios:
        return

    asunto = f"[Observatorio] {titulo}: {de_estado} → {a_estado}"
    cuerpo = (
        f"El contenido «{titulo}» ({modelo}) cambió de estado: {de_estado} → {a_estado}.\n\n"
        f"Revísalo en el panel de administración: {settings.SITE_URL}"
    )
    send_mail(asunto, cuerpo, settings.DEFAULT_FROM_EMAIL, destinatarios, fail_silently=True)
