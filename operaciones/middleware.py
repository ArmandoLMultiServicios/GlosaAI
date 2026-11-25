from django.shortcuts import redirect
from django.urls import reverse

from .models import tiene_contrasena_temporal


class ContrasenaTemporalMiddleware:
    """Mientras el usuario tenga la contraseña temporal que le dio un administrador, cualquier
    página lo lleva a "Mi contraseña" hasta que elija la suya."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            permitidas = (reverse('operaciones:mi_contrasena'), reverse('logout'))
            if request.path not in permitidas and tiene_contrasena_temporal(request.user):
                return redirect('operaciones:mi_contrasena')
        return self.get_response(request)
