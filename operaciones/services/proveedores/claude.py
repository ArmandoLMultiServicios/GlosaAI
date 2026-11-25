"""Proveedor Anthropic (Claude). Credenciales: ANTHROPIC_API_KEY y, si aplica, ANTHROPIC_WORKSPACE_ID."""

import base64
import logging
import time

import anthropic
import httpx2   # transporte HTTP del SDK de Anthropic 1.x
from django.conf import settings

from .base import Documento, ErrorAnalisis, Proveedor, Respuesta

logger = logging.getLogger(__name__)

# Segundos de espera antes de cada reintento cuando la API se satura a mitad de la respuesta.
ESPERAS_REINTENTO = [15, 45]

# Diferencias entre generaciones de Claude que afectan la solicitud:
# - En los modelos 4.x, si no se pide `thinking`, el modelo no razona antes de responder
#   (en los 5.x razona por defecto). Para la glosa siempre queremos que razone.
PIDEN_THINKING_EXPLICITO = ('claude-opus-4-', 'claude-sonnet-4-')
# - Opus 4.6 y Sonnet 4.6 no aceptan el esfuerzo 'xhigh' (sí low, medium, high y max).
SIN_ESFUERZO_XHIGH = ('claude-opus-4-6', 'claude-sonnet-4-6')
# - Haiku 4.5 no acepta `effort` ni el modo adaptativo de razonamiento.
SIN_ESFUERZO = ('claude-haiku-4-5',)
# - Tokens máximos de respuesta (incluye el razonamiento). Los modelos actuales y los 4.6 admiten
#   128 000; Haiku 4.5, 64 000. Los modelos 4.x razonan más extenso y necesitan el margen.
MAX_TOKENS = 128000
MAX_TOKENS_POR_MODELO = {'claude-haiku-4-5': 64000}


def _bloque(parte):
    if not isinstance(parte, Documento):
        return {'type': 'text', 'text': parte.texto}
    if parte.mime == 'application/pdf':
        return {'type': 'document', 'title': parte.nombre,
                'source': {'type': 'base64', 'media_type': parte.mime,
                           'data': base64.standard_b64encode(parte.datos).decode()}}
    if parte.mime.startswith('image/'):
        return {'type': 'image',
                'source': {'type': 'base64', 'media_type': parte.mime,
                           'data': base64.standard_b64encode(parte.datos).decode()}}
    return {'type': 'document', 'title': parte.nombre,
            'source': {'type': 'text', 'media_type': 'text/plain',
                       'data': parte.datos.decode('utf-8', errors='replace')}}


def _es_saturacion(error):
    """Errores temporales que llegan a mitad del stream (el SDK no los reintenta): saturación del
    servidor o conexión cortada mientras llegaba la respuesta."""
    if isinstance(error, (anthropic.APIConnectionError, httpx2.TransportError)):
        return True
    cuerpo = error.body if isinstance(error.body, dict) else {}
    tipo = cuerpo.get('error', {}).get('type') if isinstance(cuerpo.get('error'), dict) else None
    return tipo in ('overloaded_error', 'api_error') or error.status_code >= 500


class Claude(Proveedor):
    nombre = 'anthropic'

    def _opciones_modelo(self, esquema):
        """Parámetros que dependen del modelo elegido (ver las tablas al inicio del archivo)."""
        output_config = {'format': {'type': 'json_schema', 'schema': esquema}}
        opciones = {'max_tokens': next((v for k, v in MAX_TOKENS_POR_MODELO.items()
                                        if self.modelo.startswith(k)), MAX_TOKENS)}
        if not self.modelo.startswith(SIN_ESFUERZO):
            esfuerzo = self.esfuerzo
            if esfuerzo == 'xhigh' and self.modelo.startswith(SIN_ESFUERZO_XHIGH):
                esfuerzo = 'high'
            output_config['effort'] = esfuerzo
            if self.modelo.startswith(PIDEN_THINKING_EXPLICITO):
                opciones['thinking'] = {'type': 'adaptive'}
        opciones['output_config'] = output_config
        return opciones

    def _solicitar(self, client, system, contenido, esquema):
        """Hace la solicitud en streaming; reintenta si el servidor se satura a mitad de la respuesta."""
        for intento, espera in enumerate([*ESPERAS_REINTENTO, None], start=1):
            try:
                with client.beta.messages.stream(
                    model=self.modelo,
                    betas=['server-side-fallback-2026-07-01'],
                    fallbacks='default',
                    system=system,
                    messages=[{'role': 'user', 'content': contenido}],
                    **self._opciones_modelo(esquema),
                ) as stream:
                    return stream.get_final_message()
            except (anthropic.APIStatusError, anthropic.APIConnectionError, httpx2.TransportError) as e:
                if espera is None or isinstance(e, anthropic.RateLimitError) or not _es_saturacion(e):
                    raise
                logger.warning('Falla temporal de la API (intento %s: %s); reintentando en %ss',
                               intento, type(e).__name__, espera)
                time.sleep(espera)

    def generar_json(self, system, partes, esquema):
        headers = {}
        if settings.ANTHROPIC_WORKSPACE_ID:
            headers['anthropic-workspace-id'] = settings.ANTHROPIC_WORKSPACE_ID
        client = anthropic.Anthropic(default_headers=headers)
        try:
            respuesta = self._solicitar(client, system, [_bloque(p) for p in partes], esquema)
        except TypeError as e:
            # El SDK lanza TypeError cuando no encuentra ninguna credencial configurada.
            if 'authentication' not in str(e):
                raise
            raise ErrorAnalisis('Falta configurar ANTHROPIC_API_KEY en el archivo .env.') from e
        except anthropic.AuthenticationError as e:
            raise ErrorAnalisis('Llave de API de Anthropic inválida o ausente (ANTHROPIC_API_KEY).') from e
        except anthropic.BadRequestError as e:
            cuerpo = e.body if isinstance(e.body, dict) else {}
            mensaje = cuerpo.get('error', {}).get('message', e.message)
            if 'PDF specified was not valid' in mensaje:
                raise ErrorAnalisis('Uno de los PDF no se pudo leer: puede estar dañado o protegido '
                                    'con contraseña.') from e
            raise ErrorAnalisis(f'Solicitud rechazada por la API: {mensaje}') from e
        except anthropic.RateLimitError as e:
            raise ErrorAnalisis('Límite de uso de la API alcanzado; intenta de nuevo en unos minutos.') from e
        except anthropic.APIStatusError as e:
            if _es_saturacion(e):
                raise ErrorAnalisis('El servicio de análisis está saturado en este momento; intenta '
                                    'de nuevo en unos minutos.') from e
            raise ErrorAnalisis(f'Error de la API ({e.status_code}): {e.message}') from e
        except (anthropic.APIConnectionError, httpx2.TransportError) as e:
            raise ErrorAnalisis('Se perdió la conexión con la API de Anthropic; intenta de nuevo.') from e

        if respuesta.stop_reason == 'refusal':
            raise ErrorAnalisis('El modelo declinó analizar los documentos.')
        if respuesta.stop_reason == 'max_tokens':
            raise ErrorAnalisis('La respuesta excedió el límite de tokens; intenta con menos documentos.')
        texto = next((b.text for b in respuesta.content if b.type == 'text'), None)
        if not texto:
            raise ErrorAnalisis('La API no devolvió resultado.')
        return Respuesta(texto, respuesta.model, respuesta.usage.input_tokens,
                         respuesta.usage.output_tokens)
