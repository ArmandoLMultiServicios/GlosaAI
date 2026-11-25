"""Administración de usuarios (solo administradores) y cambio de la propia contraseña."""

from functools import wraps

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import FormularioCambioContrasena, FormularioEditarUsuario, FormularioNuevoUsuario
from .models import marcar_contrasena_temporal, tiene_contrasena_temporal


def solo_administradores(vista):
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        return vista(request, *args, **kwargs)
    return envoltura


@solo_administradores
def lista(request):
    busqueda = request.GET.get('q', '').strip()
    usuarios = User.objects.select_related('perfil').order_by('-is_active', 'username')
    if busqueda:
        usuarios = usuarios.filter(Q(username__icontains=busqueda) | Q(first_name__icontains=busqueda) |
                                   Q(last_name__icontains=busqueda) | Q(email__icontains=busqueda))
    return render(request, 'operaciones/usuarios/lista.html', {'usuarios': usuarios, 'busqueda': busqueda})


@solo_administradores
def nuevo(request):
    form = FormularioNuevoUsuario(request.POST or None)
    if form.is_valid():
        usuario = form.save()
        marcar_contrasena_temporal(usuario)
        messages.success(request, f'Se creó el usuario {usuario.username}. Al entrar se le pedirá cambiar '
                                  'la contraseña temporal.')
        return redirect('operaciones:usuarios')
    return render(request, 'operaciones/usuarios/formulario.html', {'form': form, 'nuevo': True})


@solo_administradores
def editar(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    form = FormularioEditarUsuario(request.POST or None, instance=usuario, editor=request.user)
    if form.is_valid():
        form.save()
        if form.cleaned_data.get('nueva_contrasena'):
            # La que pone un administrador es temporal; la que uno se pone a sí mismo, no.
            marcar_contrasena_temporal(usuario, temporal=usuario.pk != request.user.pk)
        if usuario.pk == request.user.pk:
            update_session_auth_hash(request, usuario)   # no cerrar la sesión si cambió su contraseña
        messages.success(request, f'Se guardaron los cambios de {usuario.username}.')
        return redirect('operaciones:usuarios')
    return render(request, 'operaciones/usuarios/formulario.html',
                  {'form': form, 'nuevo': False, 'usuario': usuario})


@require_POST
@solo_administradores
def eliminar(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    if usuario.pk == request.user.pk:
        messages.error(request, 'No puedes eliminar tu propia cuenta.')
    else:
        usuario.delete()
        messages.success(request, f'Se eliminó el usuario {usuario.username}.')
    return redirect('operaciones:usuarios')


def mi_contrasena(request):
    obligatorio = tiene_contrasena_temporal(request.user)
    form = FormularioCambioContrasena(request.user, request.POST or None)
    if form.is_valid():
        form.save()
        update_session_auth_hash(request, form.user)
        marcar_contrasena_temporal(request.user, temporal=False)
        messages.success(request, 'Tu contraseña se cambió.')
        return redirect('operaciones:inicio')
    return render(request, 'operaciones/usuarios/mi_contrasena.html', {'form': form, 'obligatorio': obligatorio})
