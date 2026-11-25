"""Registro de proveedores de IA.

El proveedor y el modelo se eligen en config/settings.py (IA_PROVEEDOR / IA_MODELOS) o en .env
(IA_PROVEEDOR / IA_MODELO). Cada proveedor se importa solo cuando se usa, así que no hace falta
instalar ni configurar los que no uses.
"""

from importlib import import_module

from django.conf import settings

from .base import Documento, ErrorAnalisis, Proveedor, Respuesta, Texto

# nombre en la configuración -> (módulo, clase)
PROVEEDORES = {
    'anthropic': ('claude', 'Claude'),
    'gemini': ('gemini', 'Gemini'),
    'openai': ('openai_gpt', 'OpenAIGPT'),
}


def obtener_proveedor(nombre=None, modelo=None):
    """Instancia el proveedor configurado (o el indicado)."""
    nombre = nombre or settings.IA_PROVEEDOR
    if nombre not in PROVEEDORES:
        raise ErrorAnalisis(f'Proveedor de IA desconocido: "{nombre}". '
                            f'Opciones: {", ".join(PROVEEDORES)}.')
    modulo, clase = PROVEEDORES[nombre]
    try:
        cls = getattr(import_module(f'.{modulo}', __name__), clase)
    except ImportError as e:
        raise ErrorAnalisis(f'Falta instalar el paquete del proveedor "{nombre}": {e.name}. '
                            'Corre: .venv\\Scripts\\python -m pip install -r requirements.txt') from e
    modelo = modelo or (settings.IA_MODELO if nombre == settings.IA_PROVEEDOR else '') \
        or settings.IA_MODELOS[nombre]
    return cls(modelo=modelo, esfuerzo=settings.IA_ESFUERZO)


__all__ = ['Documento', 'ErrorAnalisis', 'Proveedor', 'Respuesta', 'Texto', 'PROVEEDORES',
           'obtener_proveedor']
