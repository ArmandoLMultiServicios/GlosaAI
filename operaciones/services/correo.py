"""Correos que recibe el usuario: el reporte terminado o el aviso de que no se pudo generar."""

import re

from django.conf import settings
from django.core.mail import EmailMessage

from .reporte import ORDEN_SEVERIDAD, SEVERIDADES

USUARIO_VALIDO = re.compile(r'^[a-z0-9][a-z0-9._-]*$')


class CorreoInvalido(ValueError):
    pass


def correo_de_usuario(usuario):
    """Convierte lo que escribió el usuario en una dirección del dominio de la empresa.

    Acepta "armandol" o "armandol@multiservicios.mx"; rechaza cualquier otro dominio.
    """
    usuario = (usuario or '').strip().lower()
    dominio = settings.CORREO_DOMINIO.lower()
    if usuario.endswith('@' + dominio):
        usuario = usuario[:-len(dominio) - 1]
    if '@' in usuario:
        raise CorreoInvalido(f'Solo se pueden enviar reportes a cuentas @{dominio}.')
    if not USUARIO_VALIDO.match(usuario):
        raise CorreoInvalido('Escribe tu usuario de correo (por ejemplo: armandol).')
    return f'{usuario}@{dominio}'


def _lista_archivos(nombres):
    return '\n'.join(f'  • {n}' for n in nombres)


def enviar_reporte(destinatario, resultado, pdf, nombre_pdf, nombres_archivos):
    pedimento = resultado.get('datos_pedimento', {}).get('numero_pedimento') or 'sin número'
    conteo = {s: 0 for s in ORDEN_SEVERIDAD}
    for h in resultado.get('hallazgos', []):
        conteo[h.get('severidad', 'informativa')] += 1
    total = sum(conteo.values())
    resumen_conteo = ', '.join(f'{n} {SEVERIDADES[s][0].lower()}' for s, n in conteo.items() if n)

    asunto = f'GlosaAI · Pedimento {pedimento} · {total} hallazgo{"" if total == 1 else "s"}'
    cuerpo = (
        f'Se terminó la revisión del pedimento {pedimento}.\n\n'
        f'Hallazgos: {resumen_conteo or "ninguno"}.\n\n'
        f'Resumen:\n{resultado.get("resumen", "")}\n\n'
        f'El reporte completo va adjunto ({nombre_pdf}).\n\n'
        f'Documentos analizados:\n{_lista_archivos(nombres_archivos)}\n\n'
        f'Modelo: {resultado.get("meta", {}).get("modelo", "")}\n'
        '—\nReporte generado automáticamente. Verifique los hallazgos antes de tomar decisiones.'
    )
    mensaje = EmailMessage(subject=asunto, body=cuerpo, to=[destinatario])
    mensaje.attach(nombre_pdf, pdf, 'application/pdf')
    mensaje.send()


def enviar_error(destinatario, error, nombres_archivos):
    cuerpo = (
        'No se pudo generar el reporte de segunda glosa.\n\n'
        f'Motivo: {error}\n\n'
        f'Documentos que se enviaron:\n{_lista_archivos(nombres_archivos)}\n\n'
        'Puedes volver a intentarlo desde la página de GlosaAI.'
    )
    EmailMessage(subject='GlosaAI · No se pudo generar el reporte', body=cuerpo,
                 to=[destinatario]).send()
