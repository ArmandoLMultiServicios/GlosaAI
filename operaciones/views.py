from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .services import trabajos
from .services.analizador import EXTENSIONES_PERMITIDAS, Archivo, ErrorAnalisis, validar_tamano
from .services.correo import CorreoInvalido, correo_de_usuario


def _usuario_correo(user):
    """Usuario de correo sugerido para el usuario que inició sesión ('' si no se puede deducir)."""
    for candidato in (user.email, user.username):
        try:
            return correo_de_usuario(candidato).split('@')[0]
        except CorreoInvalido:
            pass
    return ''


def inicio(request):
    return render(request, 'operaciones/inicio.html', {
        'extensiones': ','.join(sorted(EXTENSIONES_PERMITIDAS)),
        'dominio': settings.CORREO_DOMINIO,
        'usuario_correo': _usuario_correo(request.user),
    })


@require_POST
def analizar(request):
    if not settings.CORREO_CONFIGURADO:
        return JsonResponse({'error': 'El envío de correo no está configurado en el servidor '
                                      '(CORREO_SMTP_HOST en .env).'}, status=503)
    try:
        destinatario = correo_de_usuario(request.POST.get('usuario'))
    except CorreoInvalido as e:
        return JsonResponse({'error': str(e)}, status=400)

    subidos = request.FILES.getlist('archivos')
    archivos = [Archivo(nombre=f.name, datos=f.read()) for f in subidos]
    invalidos = [a.nombre for a in archivos if a.extension not in EXTENSIONES_PERMITIDAS]
    if invalidos:
        return JsonResponse({'error': f'Tipo de archivo no permitido: {", ".join(invalidos)}'}, status=400)
    if not archivos:
        return JsonResponse({'error': 'Sube el pedimento y su documentación.'}, status=400)
    try:
        validar_tamano(archivos)
    except ErrorAnalisis as e:
        return JsonResponse({'error': str(e)}, status=400)

    pedimento = None
    indice = request.POST.get('pedimento', '')
    if indice.isdigit() and int(indice) < len(archivos):
        pedimento = archivos[int(indice)]

    trabajos.lanzar(archivos, pedimento, destinatario)
    return JsonResponse({'correo': destinatario})
