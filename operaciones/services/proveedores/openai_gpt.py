"""Proveedor OpenAI (GPT), con la Responses API. Credencial: OPENAI_API_KEY."""

import base64

import openai
from django.conf import settings

from .base import Documento, ErrorAnalisis, Proveedor, Respuesta


def _parte(parte):
    if not isinstance(parte, Documento):
        return {'type': 'input_text', 'text': parte.texto}
    if parte.mime == 'text/plain':
        return {'type': 'input_text',
                'text': f'--- {parte.nombre} ---\n{parte.datos.decode("utf-8", errors="replace")}'}
    datos = base64.b64encode(parte.datos).decode()
    if parte.mime.startswith('image/'):
        return {'type': 'input_image', 'image_url': f'data:{parte.mime};base64,{datos}'}
    return {'type': 'input_file', 'filename': parte.nombre,
            'file_data': f'data:{parte.mime};base64,{datos}'}


class OpenAIGPT(Proveedor):
    nombre = 'openai'

    def generar_json(self, system, partes, esquema):
        if not settings.OPENAI_API_KEY:
            raise ErrorAnalisis('Falta configurar OPENAI_API_KEY en el archivo .env.')
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY, timeout=15 * 60, max_retries=2)
        try:
            respuesta = client.responses.create(
                model=self.modelo,
                instructions=system,
                input=[{'role': 'user', 'content': [_parte(p) for p in partes]}],
                reasoning={'effort': self.esfuerzo},
                max_output_tokens=64000,
                text={'format': {'type': 'json_schema', 'name': 'glosa_ai',
                                 'schema': esquema, 'strict': True}},
            )
        except openai.AuthenticationError as e:
            raise ErrorAnalisis('Llave de API de OpenAI inválida (OPENAI_API_KEY).') from e
        except openai.RateLimitError as e:
            raise ErrorAnalisis('Límite de uso de OpenAI alcanzado; intenta de nuevo en unos minutos.') from e
        except openai.BadRequestError as e:
            raise ErrorAnalisis(f'Solicitud rechazada por OpenAI: {e.message}') from e
        except openai.APIStatusError as e:
            raise ErrorAnalisis(f'Error de OpenAI ({e.status_code}); intenta de nuevo en unos minutos.') from e
        except openai.APIConnectionError as e:
            raise ErrorAnalisis('No se pudo conectar con la API de OpenAI.') from e

        if respuesta.status == 'incomplete':
            motivo = getattr(respuesta.incomplete_details, 'reason', '')
            if motivo == 'max_output_tokens':
                raise ErrorAnalisis('La respuesta excedió el límite de tokens; intenta con menos documentos.')
            raise ErrorAnalisis(f'OpenAI no completó la respuesta (motivo: {motivo or "desconocido"}).')
        for item in respuesta.output:
            for contenido in getattr(item, 'content', None) or []:
                if contenido.type == 'refusal':
                    raise ErrorAnalisis('El modelo declinó analizar los documentos.')
        if not respuesta.output_text:
            raise ErrorAnalisis('OpenAI no devolvió resultado.')
        return Respuesta(respuesta.output_text, respuesta.model, respuesta.usage.input_tokens,
                         respuesta.usage.output_tokens)
