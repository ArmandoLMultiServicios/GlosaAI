"""Análisis en segundo plano: al terminar, el reporte se envía por correo.

No se guarda nada en disco ni en base de datos: los documentos y el PDF viven en memoria solo
mientras dura el análisis y el envío. Si el servidor se reinicia a mitad de un análisis, ese
análisis se pierde (el usuario no recibe correo).
"""

import logging
import threading

from .analizador import ErrorAnalisis, analizar, detectar_pedimento
from .correo import enviar_error, enviar_reporte
from .reporte import generar_reporte

logger = logging.getLogger(__name__)


def _ejecutar(archivos, pedimento, destinatario):
    nombres = [a.nombre for a in archivos]
    try:
        if pedimento is None:
            pedimento = detectar_pedimento(archivos)
        resultado = analizar(archivos, pedimento)
        archivos.clear()   # los documentos ya no se necesitan
        numero = resultado.get('datos_pedimento', {}).get('numero_pedimento', '')
        nombre_pdf = f"Glosa_{numero.replace(' ', '') or 'reporte'}.pdf"
        enviar_reporte(destinatario, resultado, generar_reporte(resultado), nombre_pdf, nombres)
        logger.info('Reporte %s enviado a %s', nombre_pdf, destinatario)
        return
    except ErrorAnalisis as e:
        error = str(e)
    except Exception as e:
        logger.exception('Error en el análisis para %s', destinatario)
        error = f'Error inesperado: {e}'
    finally:
        archivos.clear()
    try:
        enviar_error(destinatario, error, nombres)
    except Exception:
        logger.exception('No se pudo enviar el aviso de error a %s', destinatario)


def lanzar(archivos, pedimento, destinatario):
    """Inicia el análisis en segundo plano; el resultado llegará por correo a `destinatario`."""
    threading.Thread(target=_ejecutar, args=[archivos, pedimento, destinatario], daemon=True).start()
