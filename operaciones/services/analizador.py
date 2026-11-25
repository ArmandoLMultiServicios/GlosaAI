"""Análisis de glosa: compara el pedimento contra sus documentos soporte con un modelo de IA.

Las instrucciones, la lista de verificación y el formato de respuesta son los mismos para todos los
proveedores; el proveedor (Claude, Gemini u OpenAI) se elige en config/settings.py.
"""

import json
import mimetypes
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from .criterios import (CRITERIOS_SEVERIDAD, IDS_VERIFICACION, RESULTADOS, TOLERANCIAS,
                        texto_lista_verificacion, texto_reglas_documentos)
from .proveedores import Documento, ErrorAnalisis, Texto, obtener_proveedor

SYSTEM_PROMPT = f"""\
Eres un glosador aduanal experto en comercio exterior mexicano (Ley Aduanera, su Reglamento, \
Reglas Generales de Comercio Exterior, Anexo 22 y LIGIE). Realizas la "segunda glosa": revisas \
un pedimento ya pagado contra toda la documentación con la que se elaboró (factura comercial, \
conocimiento de embarque/BL, guía, COVE, certificados de origen, certificados NOM o de calidad, \
cartas, packing list, etc.) para detectar inconsistencias.

Método de trabajo:
1. Lee todos los documentos y extrae sus datos antes de comparar. Un mismo archivo puede traer \
varios documentos (incluso todo el expediente con el pedimento): sepáralos por página y trata \
cada uno como un documento distinto. Cita la página cuando ayude a ubicar un dato.
2. Recorre la LISTA DE VERIFICACIÓN completa, en orden, sin omitir ningún punto. Para cada punto \
compara el pedimento contra todos los documentos soporte que contengan ese dato, y también los \
documentos soporte entre sí. Registra cada punto en `lista_verificacion` con su resultado:
   - coincide: verificaste el dato y todos los documentos que lo contienen concuerdan.
   - discrepancia: encontraste al menos una diferencia (debe tener uno o más hallazgos).
   - no_verificable: el dato existe en el pedimento pero ningún documento proporcionado permite \
verificarlo, o el documento es ilegible.
   - no_aplica: el punto no aplica a esta operación.
   En `detalle` anota, de forma breve, qué comparaste y con qué valores.
3. Crea un hallazgo por cada discrepancia distinta, y uno informativo por cada punto \
no_verificable que sea relevante. No combines en un hallazgo discrepancias de datos distintos \
(por ejemplo, buque y viaje son hallazgos separados) ni repitas la misma discrepancia en varios \
hallazgos. Cada hallazgo indica el `punto` de la lista al que pertenece.
4. Asigna la severidad exclusivamente con los CRITERIOS DE SEVERIDAD.

El pedimento está en pesos mexicanos (MXN) y los documentos soporte normalmente en moneda \
extranjera. Para comparar importes usa SIEMPRE el tipo de cambio declarado en el pedimento (y el \
factor de moneda si la factura no está en USD). Muestra la conversión en el campo `calculo`.

LISTA DE VERIFICACIÓN:
{texto_lista_verificacion()}

CRITERIOS DE SEVERIDAD:
{CRITERIOS_SEVERIDAD}

TOLERANCIAS:
{TOLERANCIAS}

{texto_reglas_documentos()}

Sé preciso: cita el valor exacto del pedimento y el del documento, e identifica el archivo de \
origen. No supongas datos que no estén en los documentos. Responde todo en español.
"""

ESQUEMA_RESULTADO = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['resumen', 'datos_pedimento', 'documentos', 'lista_verificacion', 'hallazgos',
                 'conclusion'],
    'properties': {
        'resumen': {'type': 'string', 'description': 'Resumen ejecutivo de la revisión.'},
        'datos_pedimento': {
            'type': 'object',
            'additionalProperties': False,
            'required': ['numero_pedimento', 'tipo_operacion', 'clave_pedimento', 'aduana',
                         'fecha_pago', 'tipo_cambio', 'importador_exportador', 'proveedor_comprador',
                         'incoterm', 'moneda_factura', 'valor_dolares', 'valor_aduana',
                         'valor_comercial', 'peso_bruto', 'bultos', 'medio_transporte'],
            'properties': {k: {'type': 'string'} for k in [
                'numero_pedimento', 'tipo_operacion', 'clave_pedimento', 'aduana', 'fecha_pago',
                'tipo_cambio', 'importador_exportador', 'proveedor_comprador', 'incoterm',
                'moneda_factura', 'valor_dolares', 'valor_aduana', 'valor_comercial',
                'peso_bruto', 'bultos', 'medio_transporte',
            ]},
        },
        'documentos': {
            'type': 'array',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['archivo', 'tipo_documento', 'descripcion', 'legible'],
                'properties': {
                    'archivo': {'type': 'string'},
                    'tipo_documento': {'type': 'string', 'description': 'Factura, BL, COVE, certificado de origen, etc.'},
                    'descripcion': {'type': 'string', 'description': 'Datos clave identificados en el documento.'},
                    'legible': {'type': 'boolean'},
                },
            },
        },
        'lista_verificacion': {
            'type': 'array',
            'description': 'Exactamente un elemento por punto de la lista de verificación, en orden.',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['punto', 'resultado', 'detalle'],
                'properties': {
                    'punto': {'type': 'string', 'enum': IDS_VERIFICACION},
                    'resultado': {'type': 'string', 'enum': list(RESULTADOS)},
                    'detalle': {'type': 'string'},
                },
            },
        },
        'hallazgos': {
            'type': 'array',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['punto', 'severidad', 'categoria', 'campo', 'documento',
                             'valor_pedimento', 'valor_documento', 'calculo', 'descripcion',
                             'recomendacion'],
                'properties': {
                    'punto': {'type': 'string', 'enum': IDS_VERIFICACION},
                    'severidad': {'type': 'string', 'enum': ['critica', 'alta', 'media', 'baja', 'informativa']},
                    'categoria': {'type': 'string', 'description': 'Valor, Clasificación, Origen, Cantidades, Partes, Transporte, Contribuciones, Documental, etc.'},
                    'campo': {'type': 'string', 'description': 'Campo o dato que presenta la inconsistencia.'},
                    'documento': {'type': 'string', 'description': 'Archivo(s) contra el que se comparó.'},
                    'valor_pedimento': {'type': 'string'},
                    'valor_documento': {'type': 'string'},
                    'calculo': {'type': 'string', 'description': 'Conversión o cálculo realizado; vacío si no aplica.'},
                    'descripcion': {'type': 'string'},
                    'recomendacion': {'type': 'string'},
                },
            },
        },
        'conclusion': {'type': 'string'},
    },
}

TIPOS_IMAGEN = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
                '.gif': 'image/gif', '.webp': 'image/webp'}
TIPOS_TEXTO = {'.xml', '.txt', '.csv', '.json'}
EXTENSIONES_PERMITIDAS = {'.pdf', *TIPOS_IMAGEN, *TIPOS_TEXTO}

# Suma máxima de los archivos de un análisis (la solicitud a la API admite 32 MB en base64).
TAMANO_MAXIMO_MB = 22


@dataclass
class Archivo:
    nombre: str
    datos: bytes

    @property
    def extension(self):
        return Path(self.nombre).suffix.lower()


def _documento(archivo):
    """Convierte un archivo subido en un `Documento` con su tipo MIME."""
    ext = archivo.extension
    if ext == '.pdf':
        return Documento(archivo.nombre, archivo.datos, 'application/pdf')
    if ext in TIPOS_IMAGEN:
        return Documento(archivo.nombre, archivo.datos, TIPOS_IMAGEN[ext])
    if ext in TIPOS_TEXTO:
        return Documento(archivo.nombre, archivo.datos, 'text/plain')
    tipo = mimetypes.guess_type(archivo.nombre)[0] or ext
    raise ErrorAnalisis(f'Tipo de archivo no soportado: {archivo.nombre} ({tipo})')


def validar_tamano(archivos):
    """La API acepta solicitudes de hasta 32 MB; los archivos viajan en base64 (+33 %)."""
    total = sum(len(a.datos) for a in archivos)
    if total > TAMANO_MAXIMO_MB * 1024 * 1024:
        raise ErrorAnalisis(
            f'Los archivos suman {total / 1024 / 1024:.1f} MB y el máximo es {TAMANO_MAXIMO_MB} MB. '
            'Reduce la resolución de los escaneos o quita documentos que no sean necesarios.')


def detectar_pedimento(archivos):
    """Busca el pedimento entre los archivos por su texto (los pedimentos son PDF digitales).

    Revisa todas las páginas, porque en un expediente en un solo PDF el pedimento puede no ir
    al principio. Las páginas escaneadas no tienen texto y simplemente no coinciden.
    """
    for archivo in archivos:
        if archivo.extension != '.pdf':
            continue
        try:
            lector = PdfReader(BytesIO(archivo.datos))
            for pagina in lector.pages:
                texto = (pagina.extract_text() or '').upper()
                if 'PEDIMENTO' in texto and 'CUADRO DE LIQUIDACION' in texto:
                    return archivo
        except Exception:
            continue
    return None


def construir_contenido(archivos, pedimento=None):
    """Arma el mensaje para el modelo como una lista de `Texto` y `Documento`.

    Acepta un solo archivo con todo el expediente (pedimento y documentos soporte juntos), o
    varios archivos. Si no se indica el pedimento, se pide al modelo identificarlo.
    """
    if not archivos:
        raise ErrorAnalisis('Sube el pedimento y su documentación.')

    contenido = []
    instrucciones = ''
    if len(archivos) == 1:
        archivo = archivos[0]
        contenido += [Texto(f'EXPEDIENTE COMPLETO (archivo: {archivo.nombre})'),
                      _documento(archivo)]
        instrucciones = (
            'Este único archivo contiene el pedimento y toda su documentación soporte. Antes de '
            'comparar, identifica cada documento y sus páginas (p. ej. pedimento págs. 1-6, factura '
            'págs. 7-8). En `documentos` registra cada uno por separado, con las páginas en '
            '`archivo` (p. ej. "expediente.pdf, págs. 7-8").\n')
    else:
        soportes = [a for a in archivos if a is not pedimento]
        if pedimento is not None:
            contenido += [Texto(f'PEDIMENTO (archivo: {pedimento.nombre})'),
                          _documento(pedimento)]
        for i, archivo in enumerate(soportes, start=1):
            etiqueta = 'DOCUMENTO SOPORTE' if pedimento is not None else 'DOCUMENTO'
            contenido += [Texto(f'{etiqueta} {i} (archivo: {archivo.nombre})'),
                          _documento(archivo)]
        if pedimento is None:
            instrucciones = ('No se indicó cuál archivo es el pedimento: identifícalo entre los '
                             'documentos y usa el resto como documentación soporte.\n')
        instrucciones += (
            'Un archivo puede contener varios documentos (p. ej. el pedimento junto con la factura '
            'y el BL): identifícalos por página y regístralos por separado en `documentos`, con '
            'las páginas en `archivo`.\n')
    instrucciones += (
        'Busca inconsistencias entre la información contenida en el pedimento y el resto de la '
        'documentación. Toma en cuenta que el pedimento está en pesos mexicanos y el resto de la '
        'documentación en otra denominación extranjera; toma el tipo de cambio que se encuentra en '
        'el pedimento como referencia. Ordena los hallazgos de mayor a menor severidad.'
    )
    contenido.append(Texto(instrucciones))
    return contenido


def normalizar_lista(lista):
    """Deja exactamente un elemento por punto, en el orden de LISTA_VERIFICACION.

    El esquema no puede obligar al modelo a cubrir todos los puntos; los que falten se marcan
    como no verificables para que el reporte lo haga evidente.
    """
    por_punto = {}
    for item in lista:
        por_punto.setdefault(item.get('punto'), item)
    return [por_punto.get(id_) or {'punto': id_, 'resultado': 'no_verificable',
                                   'detalle': 'El análisis no evaluó este punto.'}
            for id_ in IDS_VERIFICACION]


def analizar(archivos, pedimento=None, proveedor=None):
    """Ejecuta el análisis y devuelve el resultado como dict (según ESQUEMA_RESULTADO).

    `proveedor` permite forzar uno distinto al configurado (útil en pruebas).
    """
    proveedor = proveedor or obtener_proveedor()
    respuesta = proveedor.generar_json(SYSTEM_PROMPT, construir_contenido(archivos, pedimento),
                                       ESQUEMA_RESULTADO)
    try:
        resultado = json.loads(respuesta.json)
    except json.JSONDecodeError as e:
        raise ErrorAnalisis('El modelo devolvió una respuesta con formato inválido; intenta de nuevo.') from e
    resultado['lista_verificacion'] = normalizar_lista(resultado.get('lista_verificacion', []))
    resultado.setdefault('hallazgos', [])
    resultado['meta'] = {
        'proveedor': proveedor.nombre,
        'modelo': respuesta.modelo,
        'tokens_entrada': respuesta.tokens_entrada,
        'tokens_salida': respuesta.tokens_salida,
    }
    return resultado
