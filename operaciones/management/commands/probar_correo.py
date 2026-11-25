"""Envía un correo de prueba para verificar la configuración SMTP sin hacer un análisis.

Uso:  .venv\\Scripts\\python manage.py probar_correo armandol
"""

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand, CommandError

from operaciones.services.correo import CorreoInvalido, correo_de_usuario


class Command(BaseCommand):
    help = 'Envía un correo de prueba a <usuario>@CORREO_DOMINIO para verificar el SMTP.'

    def add_arguments(self, parser):
        parser.add_argument('usuario', help='Usuario de correo, p. ej. armandol')

    def handle(self, *args, usuario, **options):
        if not settings.CORREO_CONFIGURADO:
            raise CommandError('Falta CORREO_SMTP_HOST en el archivo .env.')
        try:
            destinatario = correo_de_usuario(usuario)
        except CorreoInvalido as e:
            raise CommandError(str(e))

        opciones = settings.MAILERS['default'].get('OPTIONS', {})
        self.stdout.write(f"Servidor: {opciones.get('host', 'consola')}:{opciones.get('port', '')} | "
                          f"cuenta: {opciones.get('username', '')} | remitente: {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f'Enviando correo de prueba a {destinatario}...')
        try:
            EmailMessage(
                subject='Segunda glosa · Correo de prueba',
                body='Si recibes este correo, el envío de reportes de Segunda Glosa está bien configurado.',
                to=[destinatario],
            ).send()
        except Exception as e:
            raise CommandError(f'No se pudo enviar: {type(e).__name__}: {e}')
        self.stdout.write(self.style.SUCCESS('Enviado. Revisa la bandeja de entrada (y la de spam).'))
