"""Piezas comunes a todos los proveedores de IA.

El análisis arma su mensaje con `Texto` y `Documento`, que no dependen de ningún proveedor; cada
proveedor los traduce al formato de su API y devuelve una `Respuesta` con el JSON generado.
"""

from dataclasses import dataclass


class ErrorAnalisis(Exception):
    """Error con un mensaje listo para mostrarse al usuario."""


@dataclass
class Texto:
    texto: str


@dataclass
class Documento:
    nombre: str
    datos: bytes
    mime: str   # application/pdf, image/png, image/jpeg, ..., o text/plain


@dataclass
class Respuesta:
    json: str
    modelo: str
    tokens_entrada: int
    tokens_salida: int


class Proveedor:
    """Interfaz de un proveedor. Para agregar uno nuevo, implementa `generar_json` y regístralo
    en `PROVEEDORES` (proveedores/__init__.py)."""

    nombre = ''

    def __init__(self, modelo, esfuerzo):
        self.modelo = modelo
        self.esfuerzo = esfuerzo

    def generar_json(self, system, partes, esquema):
        """Envía `system` + `partes` y devuelve una `Respuesta` cuyo JSON cumple `esquema`.

        Debe lanzar `ErrorAnalisis` con un mensaje claro ante errores de credenciales, de
        solicitud, de saturación o de respuesta incompleta.
        """
        raise NotImplementedError
