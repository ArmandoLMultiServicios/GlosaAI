"""Revisión de control de riesgos del embarque (formato interno de la agencia).

La IA contesta cada pregunta del formato con los documentos del expediente; el riesgo de valor
(art. 165, fracción II, inciso a) de la Ley Aduanera) se calcula aquí, con los valores y tasas
que la IA extrae del pedimento, para que la cuenta no dependa del modelo.

Para agregar o cambiar preguntas edita SECCIONES: el prompt, el esquema y el reporte se
actualizan solos.
"""

from django.conf import settings

# (id, título de la sección, nota, [(id_pregunta, pregunta)])
SECCIONES = [
    ('documentos_compra', 'DATOS GENERALES Y DOCUMENTOS DE LA COMPRA', '', [
        ('comprobante_pago', 'Anexa el comprobante de pago al proveedor (indica el importe)'),
        ('orden_compra', 'La orden de compra del proveedor cuadra con el valor y el precio unitario'),
        ('contrato', 'Presentó contrato de compra-venta del proveedor y coinciden nombres y datos'),
    ]),
    ('etiquetado', '2.- REVISION DE RIESGO DEL ART. 165 FRACCION II INCISO b)', 'Sobre el ETIQUETADO', [
        ('nom_etiquetado', 'Lleva NOMs de etiquetado (NOM-050, NOM-024, NOM-051 u otras; indica cuáles)'),
        ('telas_carta', 'Son telas y presenta la carta, y coincide con la factura'),
        ('listado_no_previo', 'Está en el listado de no previo'),
        ('previo_origen', 'Presentaron previo de origen legible'),
        ('uvnom', 'Se debe solicitar al cliente la UVNOM o hacer previo en puerto'),
    ]),
    ('seguridad', '3.- REVISION DE RIESGO DEL ART. 165 FRACCION II INCISO b)', 'Sobre NOMS de seguridad', [
        ('nom_seguridad', 'Lleva NOMs de seguridad (NOM-001, NOM-003, NOM-084 u otras; indica cuáles) '
                          'y se presentó el certificado o documento que las ampara'),
    ]),
    ('permisos', '4.- REVISION DE RIESGO DEL ART. 165 FRACCION II INCISO b)', 'Sobre PERMISOS C1', [
        ('son_telas', 'Son telas'),
        ('textiles_varios', 'Son productos textiles varios'),
        ('permisos_c1', 'Presentó los permisos C1 (si no, deberán solicitarlos)'),
    ]),
    ('importador', '5.- REVISION DE RIESGO DEL IMPORTADOR', 'Se revisa con Area Legal', [
        ('csf_mes', 'Se tiene la Constancia de Situación Fiscal (CSF) del mes en curso'),
        ('csf_giro', 'La CSF coincide con el giro declarado (es congruente con la mercancía)'),
        ('opinion_cumplimiento', 'Se tiene la Opinión de Cumplimiento del mes en curso y es positiva'),
        ('datos_importador', 'Los datos del importador (RFC, razón social, domicilio) son exactos '
                             'entre pedimento, factura, CSF y demás documentos'),
    ]),
    ('vinculacion', '6.- REVISION DEL TEMA DE VINCULACION DEL IMPORTADOR', '', [
        ('vinculacion_declarada', 'Se declara vinculación'),
        ('vinculacion_documento', 'Hay un documento que compruebe la vinculación (indica cuál)'),
    ]),
    ('preferencia', '7.- REVISION DEL TEMA DE PREFERENCIA ARANCELARIA Y CUOTA COMPENSATORIA', '', [
        ('preferencia_declarada', 'Se declara alguna preferencia arancelaria'),
        ('preferencia_certificado', 'Anexa el certificado de origen'),
        ('cuota_declarada', 'Se declara cuota compensatoria'),
        ('cuota_certificado', 'Anexa el certificado del Anexo VIII'),
    ]),
    ('mve', '8.- PARA LA MANIFESTACION DE VALOR ELECTRONICA DE ADUANA', '', [
        ('mve_incrementables', 'La factura desglosa los gastos incrementables (flete, seguro, otros gastos; '
                               'indica cuáles) para digitalizarla en la Manifestación de Valor'),
        ('mve_comprobante', 'Hay comprobante de la fecha de pago de los gastos incrementables'),
    ]),
]

PREGUNTAS = {id_: texto for _, _, _, preguntas in SECCIONES for id_, texto in preguntas}
IDS_PREGUNTAS = list(PREGUNTAS)

# Preguntas con casillas de opciones en el formato. La IA marca en `opciones` las que apliquen.
OPCIONES = {
    'nom_etiquetado': ['NOM-050', 'NOM-024', 'NOM-051'],
    'nom_seguridad': ['NOM-001', 'NOM-003', 'NOM-084'],
    'mve_incrementables': ['FLETE', 'SEGURO', 'OTROS GASTOS'],
}

RESPUESTAS = {
    'si': 'Sí',
    'no': 'No',
    'no_verificable': 'No verificable',
    'no_aplica': 'No aplica',
}

# Columnas de la tabla del riesgo de valor (tasa de IGI en %).
TASAS_TABLA = [0, 5, 10, 15, 20, 25, 30]


def parametros_valor():
    return {
        'importe_maximo': float(settings.RIESGO_IMPORTE_MAXIMO_OMISION),
        'tasa_referencia': float(settings.RIESGO_TASA_REFERENCIA),
        'iva_dta': float(settings.RIESGO_IVA_DTA),
    }


def porcentaje_omitido(tasa, p=None):
    """Porción del valor que se omitiría si la mercancía debiera pagar la tasa de referencia.

    Es IVA + DTA (todo) más la diferencia entre la tasa de referencia y la tasa declarada,
    igual que la tabla del formato en papel.
    """
    p = p or parametros_valor()
    return (p['iva_dta'] + max(0.0, p['tasa_referencia'] - tasa)) / 100


def tabla_valor(tipo_cambio=None):
    """Filas de la tabla del formato: por cada tasa, el valor máximo de mercancía que no rebasa
    el importe máximo de omisión."""
    p = parametros_valor()
    filas = []
    for tasa in TASAS_TABLA:
        omitido = porcentaje_omitido(tasa, p)
        valor = p['importe_maximo'] / omitido
        filas.append({'tasa': tasa, 'diferencia': max(0.0, p['tasa_referencia'] - tasa),
                      'omitido': omitido * 100, 'valor_maximo': valor,
                      'valor_maximo_usd': valor / tipo_cambio if tipo_cambio else None})
    return filas


def _numero(valor):
    try:
        return float(str(valor).replace(',', '').replace('$', '').strip())
    except (TypeError, ValueError):
        return None


def calcular_riesgo_valor(partidas, tipo_cambio=None):
    """Omisión estimada del pedimento en el peor caso y si pasa contra el importe máximo."""
    p = parametros_valor()
    detalle = []
    for partida in partidas or []:
        valor = _numero(partida.get('valor_aduana'))
        tasa = _numero(partida.get('tasa_igi'))
        if valor is None or tasa is None:
            continue
        detalle.append({**partida, 'valor_aduana': valor, 'tasa_igi': tasa,
                        'omision': valor * porcentaje_omitido(tasa, p)})
    if not detalle:
        return {'evaluado': False, 'partidas': [], 'valor_total': 0.0, 'omision': 0.0,
                'importe_maximo': p['importe_maximo'], 'pasa': None,
                'tabla': tabla_valor(_numero(tipo_cambio))}
    omision = sum(d['omision'] for d in detalle)
    return {
        'evaluado': True,
        'partidas': detalle,
        'valor_total': sum(d['valor_aduana'] for d in detalle),
        'omision': omision,
        'importe_maximo': p['importe_maximo'],
        'pasa': omision <= p['importe_maximo'],
        'tasas': sorted({d['tasa_igi'] for d in detalle}),
        'tabla': tabla_valor(_numero(tipo_cambio)),
    }


def texto_instrucciones():
    preguntas = '\n'.join(
        f'{titulo}:\n' + '\n'.join(f'  - [{id_}] {texto}' for id_, texto in lista)
        for _, titulo, _, lista in SECCIONES)
    return f"""\
Además de la glosa, llena la REVISIÓN DE CONTROL DE RIESGOS DEL EMBARQUE en `control_riesgos`:
- `encabezado`: referencia de la operación (si aparece), si viene en contenedores y cuántos, si es \
carga suelta, nombre del importador y valor de la factura con su moneda.
- `partidas`: por cada partida del pedimento, su número, fracción arancelaria, tasa de IGI ad \
valorem declarada en % (0 si está exenta o tiene preferencia al 0) y valor en aduana en MXN. El \
sistema calcula con eso el riesgo de valor del art. 165 fracc. II inciso a); no hagas tú la cuenta.
- `respuestas`: exactamente una por cada pregunta siguiente, en orden:
{preguntas}
  Responde si / no según los documentos del expediente; no_verificable si depende de algo que no \
está en los documentos (p. ej. el listado de no previo o un documento que no se proporcionó y no se \
puede saber si existe); no_aplica si la pregunta no corresponde a la operación (p. ej. el \
certificado de origen cuando no hay preferencia). En `detalle` anota la evidencia (documento, \
página, NOM, importe). En `solicitar` anota qué documento hay que pedir al cliente; vacío si nada.
  En `opciones` anota: para nom_etiquetado y nom_seguridad, cada NOM que lleva la mercancía con su clave corta (p. ej. "NOM-050", "NOM-004"); para mve_incrementables, cuáles de "FLETE", "SEGURO" y "OTROS GASTOS" vienen desglosados en la factura. Para las demás preguntas deja la lista vacía.
- "Mes en curso" es el mes de la fecha de hoy que se indica en el mensaje.\
"""


ESQUEMA = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['encabezado', 'partidas', 'respuestas'],
    'properties': {
        'encabezado': {
            'type': 'object',
            'additionalProperties': False,
            'required': ['referencia', 'contenedores', 'cantidad_contenedores', 'carga_suelta',
                         'importador', 'valor_factura'],
            'properties': {
                'referencia': {'type': 'string'},
                'contenedores': {'type': 'boolean'},
                'cantidad_contenedores': {'type': 'string'},
                'carga_suelta': {'type': 'boolean'},
                'importador': {'type': 'string'},
                'valor_factura': {'type': 'string'},
            },
        },
        'partidas': {
            'type': 'array',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['partida', 'fraccion', 'tasa_igi', 'valor_aduana'],
                'properties': {
                    'partida': {'type': 'string'},
                    'fraccion': {'type': 'string'},
                    'tasa_igi': {'type': 'number', 'description': 'Tasa de IGI ad valorem en %, p. ej. 15.'},
                    'valor_aduana': {'type': 'number', 'description': 'Valor en aduana de la partida en MXN.'},
                },
            },
        },
        'respuestas': {
            'type': 'array',
            'description': 'Exactamente una por pregunta del control de riesgos, en orden.',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['pregunta', 'respuesta', 'detalle', 'solicitar', 'opciones'],
                'properties': {
                    'pregunta': {'type': 'string', 'enum': IDS_PREGUNTAS},
                    'respuesta': {'type': 'string', 'enum': list(RESPUESTAS)},
                    'detalle': {'type': 'string'},
                    'solicitar': {'type': 'string', 'description': 'Documento a pedir al cliente; vacío si nada.'},
                    'opciones': {'type': 'array', 'items': {'type': 'string'},
                                 'description': 'NOMs o incrementables marcados; vacío si no aplica.'},
                },
            },
        },
    },
}


def normalizar(control, tipo_cambio=None):
    """Deja una respuesta por pregunta, en orden, y agrega el cálculo del riesgo de valor."""
    control = dict(control or {})
    por_id = {}
    for r in control.get('respuestas') or []:
        por_id.setdefault(r.get('pregunta'), r)
    control['respuestas'] = [
        por_id.get(id_) or {'pregunta': id_, 'respuesta': 'no_verificable',
                            'detalle': 'El análisis no evaluó esta pregunta.', 'solicitar': '',
                            'opciones': []}
        for id_ in IDS_PREGUNTAS]
    control.setdefault('encabezado', {})
    control['riesgo_valor'] = calcular_riesgo_valor(control.get('partidas'), tipo_cambio)
    return control
