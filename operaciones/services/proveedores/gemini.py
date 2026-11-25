"""Proveedor Google Gemini. Credencial: GEMINI_API_KEY."""

from django.conf import settings
from google import genai
from google.genai import errors, types

from .base import Documento, ErrorAnalisis, Proveedor, Respuesta

FINALES_BLOQUEO = {'SAFETY', 'BLOCKLIST', 'PROHIBITED_CONTENT', 'SPII', 'RECITATION', 'OTHER'}


def _parte(parte):
    if not isinstance(parte, Documento):
        return types.Part.from_text(text=parte.texto)
    if parte.mime == 'text/plain':
        return types.Part.from_text(
            text=f'--- {parte.nombre} ---\n{parte.datos.decode("utf-8", errors="replace")}')
    return types.Part.from_bytes(data=parte.datos, mime_type=parte.mime)


class Gemini(Proveedor):
    nombre = 'gemini'

    def generar_json(self, system, partes, esquema):
        if not settings.GEMINI_API_KEY:
            raise ErrorAnalisis('Falta configurar GEMINI_API_KEY en el archivo .env.')
        client = genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options=types.HttpOptions(
                timeout=15 * 60 * 1000,   # milisegundos
                retry_options=types.HttpRetryOptions(attempts=3, http_status_codes=[429, 500, 503]),
            ),
        )
        try:
            respuesta = client.models.generate_content(
                model=self.modelo,
                contents=[types.Content(role='user', parts=[_parte(p) for p in partes])],
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type='application/json',
                    response_json_schema=esquema,
                    max_output_tokens=65536,
                ),
            )
        except errors.ClientError as e:
            if e.code in (401, 403):
                raise ErrorAnalisis('Llave de API de Gemini inválida (GEMINI_API_KEY).') from e
            if e.code == 429:
                raise ErrorAnalisis('Límite de uso de Gemini alcanzado; intenta de nuevo en unos minutos.') from e
            raise ErrorAnalisis(f'Solicitud rechazada por Gemini: {e.message}') from e
        except errors.ServerError as e:
            raise ErrorAnalisis('Gemini está saturado en este momento; intenta de nuevo en unos minutos.') from e

        candidato = (respuesta.candidates or [None])[0]
        final = getattr(getattr(candidato, 'finish_reason', None), 'name', '')
        if final == 'MAX_TOKENS':
            raise ErrorAnalisis('La respuesta excedió el límite de tokens; intenta con menos documentos.')
        if final in FINALES_BLOQUEO or not respuesta.text:
            raise ErrorAnalisis(f'Gemini no devolvió resultado (motivo: {final or "desconocido"}).')
        uso = respuesta.usage_metadata
        salida = (uso.candidates_token_count or 0) + (uso.thoughts_token_count or 0)
        return Respuesta(respuesta.text, respuesta.model_version or self.modelo,
                         uso.prompt_token_count or 0, salida)
