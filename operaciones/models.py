from django.conf import settings
from django.db import models


class Perfil(models.Model):
    """Datos extra de cada usuario. Los documentos y reportes no se guardan (ver README)."""

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='perfil')
    # La contraseña la puso un administrador: al entrar se le pide que elija la suya.
    contrasena_temporal = models.BooleanField(default=False)

    def __str__(self):
        return self.usuario.get_username()


def tiene_contrasena_temporal(usuario):
    return Perfil.objects.filter(usuario=usuario, contrasena_temporal=True).exists()


def marcar_contrasena_temporal(usuario, temporal=True):
    Perfil.objects.update_or_create(usuario=usuario, defaults={'contrasena_temporal': temporal})
