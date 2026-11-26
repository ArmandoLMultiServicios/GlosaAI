"""Generación del reporte PDF de hallazgos de glosa."""

from io import BytesIO

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)
from xml.sax.saxutils import escape

from . import control_riesgos as cr
from .criterios import RESULTADOS, TITULOS_VERIFICACION

SEVERIDADES = {
    'critica': ('Crítica', colors.HexColor('#991b1b')),
    'alta': ('Alta', colors.HexColor('#dc2626')),
    'media': ('Media', colors.HexColor('#d97706')),
    'baja': ('Baja', colors.HexColor('#2563eb')),
    'informativa': ('Informativa', colors.HexColor('#6b7280')),
}
ORDEN_SEVERIDAD = list(SEVERIDADES)

COLORES_RESULTADO = {
    'coincide': (RESULTADOS['coincide'], colors.HexColor('#15803d')),
    'discrepancia': (RESULTADOS['discrepancia'], colors.HexColor('#dc2626')),
    'no_verificable': (RESULTADOS['no_verificable'], colors.HexColor('#b45309')),
    'no_aplica': (RESULTADOS['no_aplica'], colors.HexColor('#6b7280')),
}

ETIQUETAS_PEDIMENTO = [
    ('numero_pedimento', 'Pedimento'), ('tipo_operacion', 'Tipo de operación'),
    ('clave_pedimento', 'Clave'), ('aduana', 'Aduana'), ('fecha_pago', 'Fecha de pago'),
    ('tipo_cambio', 'Tipo de cambio'), ('importador_exportador', 'Importador/Exportador'),
    ('proveedor_comprador', 'Proveedor/Comprador'), ('incoterm', 'INCOTERM'),
    ('moneda_factura', 'Moneda factura'), ('valor_dolares', 'Valor dólares'),
    ('valor_aduana', 'Valor aduana'), ('valor_comercial', 'Valor comercial'),
    ('peso_bruto', 'Peso bruto'), ('bultos', 'Bultos'), ('medio_transporte', 'Transporte'),
]

COLORES_RESPUESTA = {
    'si': colors.HexColor('#111827'),
    'no': colors.HexColor('#111827'),
    'no_verificable': colors.HexColor('#b45309'),
    'no_aplica': colors.HexColor('#6b7280'),
}
VERDE = colors.HexColor('#15803d')
ROJO = colors.HexColor('#dc2626')
NARANJA = colors.HexColor('#ff5500')
NARANJA_CLARO = colors.HexColor('#fff0e8')

AZUL = colors.HexColor('#1e3a5f')
GRIS_CLARO = colors.HexColor('#f3f4f6')


def _estilos():
    base = getSampleStyleSheet()
    return {
        'titulo': ParagraphStyle('titulo', parent=base['Title'], textColor=AZUL, fontSize=18),
        'subtitulo': ParagraphStyle('subtitulo', parent=base['Normal'], alignment=TA_CENTER,
                                    textColor=colors.HexColor('#4b5563')),
        'h2': ParagraphStyle('h2', parent=base['Heading2'], textColor=AZUL, spaceBefore=12),
        'normal': ParagraphStyle('normal', parent=base['Normal'], fontSize=9.5, leading=13),
        'celda': ParagraphStyle('celda', parent=base['Normal'], fontSize=8.5, leading=11),
        'celda_b': ParagraphStyle('celda_b', parent=base['Normal'], fontSize=8.5, leading=11,
                                  fontName='Helvetica-Bold'),
        'blanco': ParagraphStyle('blanco', parent=base['Normal'], fontSize=9,
                                 textColor=colors.white, fontName='Helvetica-Bold'),
    }


def _p(texto, estilo):
    return Paragraph(escape(str(texto or '—')).replace('\n', '<br/>'), estilo)


def _pie(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 7.5)
    canvas.setFillColor(colors.HexColor('#6b7280'))
    canvas.drawString(2 * cm, 1.2 * cm, 'Reporte generado automáticamente. Verifique los hallazgos antes de tomar decisiones.')
    canvas.drawRightString(letter[0] - 2 * cm, 1.2 * cm, f'Página {doc.page}')
    canvas.restoreState()


def generar_reporte(resultado):
    """Devuelve los bytes del PDF con los hallazgos del análisis."""
    r = resultado or {}
    pedimento = r.get('datos_pedimento', {}).get('numero_pedimento') or 'sin número'
    e = _estilos()
    ancho = letter[0] - 4 * cm
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=2 * cm,
                            title=f'Glosa pedimento {pedimento}')
    hallazgos = sorted(r.get('hallazgos', []),
                       key=lambda h: ORDEN_SEVERIDAD.index(h.get('severidad', 'informativa')))
    fecha = timezone.localtime().strftime('%d/%m/%Y %H:%M')

    story = [
        Paragraph('GlosaAI · Reporte de glosa', e['titulo']),
        Paragraph(f'Pedimento {escape(pedimento)} · Analizado el {fecha}'
                  + (f' · {escape(r["meta"]["modelo"])}' if r.get('meta', {}).get('modelo') else ''),
                  e['subtitulo']),
        Spacer(1, 12),
    ]

    # Conteo por severidad
    conteo = {s: 0 for s in SEVERIDADES}
    for h in hallazgos:
        conteo[h.get('severidad', 'informativa')] += 1
    celdas = [[_p(f'{n}', e['blanco']) for n in conteo.values()],
              [_p(SEVERIDADES[s][0], e['blanco']) for s in conteo]]
    t = Table(celdas, colWidths=[ancho / 5] * 5)
    t.setStyle(TableStyle(
        [('BACKGROUND', (i, 0), (i, 1), SEVERIDADES[s][1]) for i, s in enumerate(conteo)] +
        [('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('TOPPADDING', (0, 0), (-1, -1), 4)]))
    story += [t, Spacer(1, 8)]

    story += [Paragraph('Resumen', e['h2']), _p(r.get('resumen'), e['normal'])]

    # Datos del pedimento
    dp = r.get('datos_pedimento', {})
    filas = []
    pares = [(etq, dp.get(k)) for k, etq in ETIQUETAS_PEDIMENTO]
    for i in range(0, len(pares), 2):
        fila = []
        for etq, val in pares[i:i + 2]:
            fila += [_p(etq, e['celda_b']), _p(val, e['celda'])]
        filas.append(fila)
    t = Table(filas, colWidths=[ancho * 0.18, ancho * 0.32] * 2)
    t.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#d1d5db')),
                           ('BACKGROUND', (0, 0), (0, -1), GRIS_CLARO),
                           ('BACKGROUND', (2, 0), (2, -1), GRIS_CLARO),
                           ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    story += [Paragraph('Datos del pedimento', e['h2']), t]

    # Hallazgos
    story.append(Paragraph(f'Hallazgos ({len(hallazgos)})', e['h2']))
    if not hallazgos:
        story.append(_p('No se encontraron inconsistencias.', e['normal']))
    for n, h in enumerate(hallazgos, start=1):
        etq, color = SEVERIDADES.get(h.get('severidad'), SEVERIDADES['informativa'])
        filas = [
            [_p(f'#{n}  {etq.upper()} · {h.get("categoria")} · {h.get("campo")}', e['blanco']), ''],
            [_p('Punto de verificación', e['celda_b']),
             _p(TITULOS_VERIFICACION.get(h.get('punto'), h.get('punto')), e['celda'])],
            [_p('Documento', e['celda_b']), _p(h.get('documento'), e['celda'])],
            [_p('Valor en pedimento', e['celda_b']), _p(h.get('valor_pedimento'), e['celda'])],
            [_p('Valor en documento', e['celda_b']), _p(h.get('valor_documento'), e['celda'])],
        ]
        if h.get('calculo'):
            filas.append([_p('Cálculo', e['celda_b']), _p(h.get('calculo'), e['celda'])])
        filas += [
            [_p('Descripción', e['celda_b']), _p(h.get('descripcion'), e['celda'])],
            [_p('Recomendación', e['celda_b']), _p(h.get('recomendacion'), e['celda'])],
        ]
        t = Table(filas, colWidths=[ancho * 0.22, ancho * 0.78])
        t.setStyle(TableStyle([('SPAN', (0, 0), (1, 0)),
                               ('BACKGROUND', (0, 0), (1, 0), color),
                               ('BACKGROUND', (0, 1), (0, -1), GRIS_CLARO),
                               ('BOX', (0, 0), (-1, -1), 0.6, color),
                               ('INNERGRID', (0, 1), (-1, -1), 0.3, colors.HexColor('#d1d5db')),
                               ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
        story += [KeepTogether(t), Spacer(1, 8)]

    # Lista de verificación
    lista = r.get('lista_verificacion', [])
    if lista:
        filas = [[_p('#', e['blanco']), _p('Punto de verificación', e['blanco']),
                  _p('Resultado', e['blanco']), _p('Detalle', e['blanco'])]]
        for n, item in enumerate(lista, start=1):
            etq, color = COLORES_RESULTADO.get(item.get('resultado'), COLORES_RESULTADO['no_verificable'])
            filas.append([_p(n, e['celda']),
                          _p(TITULOS_VERIFICACION.get(item.get('punto'), item.get('punto')), e['celda_b']),
                          _p(etq, ParagraphStyle('resultado', parent=e['celda_b'], textColor=color)),
                          _p(item.get('detalle'), e['celda'])])
        t = Table(filas, colWidths=[ancho * 0.05, ancho * 0.25, ancho * 0.15, ancho * 0.55],
                  repeatRows=1)
        t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), AZUL),
                               ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#d1d5db')),
                               ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
        story += [Paragraph('Lista de verificación', e['h2']), t]

    # Documentos revisados
    docs = r.get('documentos', [])
    if docs:
        filas = [[_p('Archivo', e['blanco']), _p('Tipo', e['blanco']),
                  _p('Datos identificados', e['blanco']), _p('Legible', e['blanco'])]]
        filas += [[_p(d.get('archivo'), e['celda']), _p(d.get('tipo_documento'), e['celda']),
                   _p(d.get('descripcion'), e['celda']), _p('Sí' if d.get('legible') else 'No', e['celda'])]
                  for d in docs]
        t = Table(filas, colWidths=[ancho * 0.25, ancho * 0.17, ancho * 0.48, ancho * 0.10],
                  repeatRows=1)
        t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), AZUL),
                               ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#d1d5db')),
                               ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
        story += [Paragraph('Documentos revisados', e['h2']), t]

    story += [Paragraph('Conclusión', e['h2']), _p(r.get('conclusion'), e['normal'])]

    if r.get('control_riesgos'):
        story += [PageBreak()] + _hoja_control_riesgos(r['control_riesgos'], e, ancho, pedimento, fecha)

    doc.build(story, onFirstPage=_pie, onLaterPages=_pie)
    return buffer.getvalue()


# ─── Hoja de control de riesgos del embarque ───

def _pesos(valor):
    return f'$ {valor:,.2f}'


def _tabla_preguntas(items, e, ancho):
    filas = [[_p('Pregunta', e['blanco']), _p('Respuesta', e['blanco']), _p('Evidencia', e['blanco'])]]
    for item in items:
        clave = item.get('respuesta')
        estilo = ParagraphStyle('respuesta', parent=e['celda_b'],
                                textColor=COLORES_RESPUESTA.get(clave, COLORES_RESPUESTA['no_verificable']))
        filas.append([_p(cr.PREGUNTAS.get(item.get('pregunta'), item.get('pregunta')), e['celda']),
                      _p(cr.RESPUESTAS.get(clave, clave), estilo),
                      _p(item.get('detalle'), e['celda'])])
    t = Table(filas, colWidths=[ancho * 0.38, ancho * 0.14, ancho * 0.48], repeatRows=1)
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), AZUL),
                           ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#d1d5db')),
                           ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    return t


def _por_solicitar(items):
    return [x['solicitar'].strip() for x in items if (x.get('solicitar') or '').strip()]


def _caja_solicitar(pedir, e, ancho, titulo='Por favor solicitar'):
    if not pedir:
        return []
    estilo = ParagraphStyle('solicitar', parent=e['celda'], textColor=colors.HexColor('#8a3a10'))
    texto = f'<b>{titulo}:</b> ' + '; '.join(escape(x) for x in pedir)
    t = Table([[Paragraph(texto, estilo)]], colWidths=[ancho])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), NARANJA_CLARO),
                           ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#f6c9ad'))]))
    return [Spacer(1, 6), t]


def _veredicto_valor(rv, e, ancho):
    if not rv.get('evaluado'):
        texto, color = 'Riesgo de valor: NO VERIFICABLE · determínalo con la tabla', COLORES_RESPUESTA['no_verificable']
    elif rv['pasa']:
        texto, color = (f"Riesgo de valor: PASA · omisión estimada {_pesos(rv['omision'])} "
                        f"de un máximo de {_pesos(rv['importe_maximo'])}"), VERDE
    else:
        texto, color = (f"Riesgo de valor: NO PASA · omisión estimada {_pesos(rv['omision'])} rebasa "
                        f"el máximo de {_pesos(rv['importe_maximo'])} · NOTIFICAR AL GERENTE"), ROJO
    t = Table([[_p(texto, e['blanco'])]], colWidths=[ancho])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), color),
                           ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
    return t


def _riesgo_valor(rv, e, ancho):
    tabla = rv['tabla']
    tasas_pedimento = set(rv.get('tasas') or [])
    referencia = cr.parametros_valor()['tasa_referencia']
    derecha = ParagraphStyle('derecha', parent=e['celda'], alignment=2)
    filas = [
        [_p('Tasa', e['celda_b'])] + [_p(f"{f['tasa']:g}%", e['celda_b']) for f in tabla],
        [_p('IVA + DTA', e['celda'])] + [_p(f"{f['omitido'] - f['diferencia']:.2f}%", derecha) for f in tabla],
        [_p(f'Dif. para {referencia:g}%', e['celda'])] + [_p(f"{f['diferencia']:g}%", derecha) for f in tabla],
        [_p('Total omitido', e['celda'])] + [_p(f"{f['omitido']:.0f}%", derecha) for f in tabla],
        [_p('Valor máx. MXN', e['celda_b'])] + [_p(f"{f['valor_maximo']:,.2f}", derecha) for f in tabla],
    ]
    if tabla and tabla[0]['valor_maximo_usd'] is not None:
        filas.append([_p('Valor máx. USD', e['celda'])]
                     + [_p(f"{f['valor_maximo_usd']:,.2f}", derecha) for f in tabla])
    t = Table(filas, colWidths=[ancho * 0.16] + [ancho * 0.12] * len(tabla))
    estilo = [('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#d1d5db')),
              ('BACKGROUND', (0, 0), (0, -1), GRIS_CLARO), ('BACKGROUND', (0, 0), (-1, 0), GRIS_CLARO),
              ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
              ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3)]
    for i, f in enumerate(tabla, start=1):
        if f['tasa'] in tasas_pedimento:
            estilo += [('BACKGROUND', (i, 0), (i, -1), NARANJA_CLARO), ('BOX', (i, 0), (i, -1), 1.2, NARANJA)]
    t.setStyle(TableStyle(estilo))
    story = [t, Spacer(1, 4),
             _p(f'Cada columna es el valor de mercancía con el que, si debiera pagar {referencia:g}% de IGI, '
                'la omisión llegaría al importe máximo. En naranja, las tasas declaradas en el pedimento.',
                ParagraphStyle('nota', parent=e['celda'], textColor=colors.HexColor('#6b7280'))),
             Spacer(1, 8)]

    if rv.get('evaluado'):
        filas = [[_p(x, e['blanco']) for x in ('Partida', 'Fracción', 'Tasa IGI', 'Valor en aduana',
                                              'Omisión estimada')]]
        for d in rv['partidas']:
            filas.append([_p(d.get('partida'), e['celda']), _p(d.get('fraccion'), e['celda']),
                          _p(f"{d['tasa_igi']:g}%", derecha), _p(_pesos(d['valor_aduana']), derecha),
                          _p(_pesos(d['omision']), derecha)])
        negrita_derecha = ParagraphStyle('negrita_derecha', parent=e['celda_b'], alignment=2)
        filas.append([_p('Total', e['celda_b']), '', '', _p(_pesos(rv['valor_total']), negrita_derecha),
                      _p(_pesos(rv['omision']), negrita_derecha)])
        t = Table(filas, colWidths=[ancho * 0.12, ancho * 0.22, ancho * 0.14, ancho * 0.26, ancho * 0.26],
                  repeatRows=1)
        t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), AZUL),
                               ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#d1d5db')),
                               ('BACKGROUND', (0, -1), (-1, -1), GRIS_CLARO)]))
        story += [t, Spacer(1, 6)]
    story.append(_veredicto_valor(rv, e, ancho))
    return story


def _hoja_control_riesgos(c, e, ancho, pedimento, fecha):
    enc = c.get('encabezado') or {}
    rv = c.get('riesgo_valor') or cr.calcular_riesgo_valor([])
    respuestas = {x.get('pregunta'): x for x in c.get('respuestas') or []}

    story = [Paragraph('Revisión de control de riesgos del embarque', e['titulo']),
             Paragraph(f'Pedimento {escape(pedimento)} · {fecha}', e['subtitulo']), Spacer(1, 10)]

    if enc.get('contenedores'):
        embarque = f"Contenedores: {enc.get('cantidad_contenedores') or 'sí'}"
    else:
        embarque = 'Contenedores: no'
    embarque += ' · Carga suelta: ' + ('sí' if enc.get('carga_suelta') else 'no')
    pares = [('Referencia', enc.get('referencia')), ('Pedimento', pedimento),
             ('Importador', enc.get('importador')), ('Valor factura', enc.get('valor_factura')),
             ('Embarque', embarque), ('Fecha y hora', fecha)]
    filas = [[_p(a, e['celda_b']), _p(b, e['celda']), _p(x, e['celda_b']), _p(y, e['celda'])]
             for (a, b), (x, y) in zip(pares[::2], pares[1::2])]
    t = Table(filas, colWidths=[ancho * 0.15, ancho * 0.35] * 2)
    t.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#d1d5db')),
                           ('BACKGROUND', (0, 0), (0, -1), GRIS_CLARO),
                           ('BACKGROUND', (2, 0), (2, -1), GRIS_CLARO),
                           ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    story += [t, Spacer(1, 8), _veredicto_valor(rv, e, ancho)]
    story += _caja_solicitar(_por_solicitar(respuestas.values()), e, ancho,
                             'Por favor solicitar (todas las secciones)')

    for id_seccion, titulo, nota, preguntas in cr.SECCIONES:
        items = [respuestas.get(id_) or {'pregunta': id_, 'respuesta': 'no_verificable', 'detalle': ''}
                 for id_, _ in preguntas]
        story.append(Paragraph(escape(titulo) + (f' <font size="9" color="#6b7280">· {escape(nota)}</font>'
                                                 if nota else ''), e['h2']))
        story += [_tabla_preguntas(items, e, ancho)] + _caja_solicitar(_por_solicitar(items), e, ancho)
        if id_seccion == 'documentos_compra':
            story.append(Paragraph(
                '1. Riesgo del valor · art. 165 fracc. II inciso a) '
                f'<font size="9" color="#6b7280">· Importe máximo de omisión {_pesos(rv["importe_maximo"])}</font>',
                e['h2']))
            story += _riesgo_valor(rv, e, ancho)
    return story
