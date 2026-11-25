"""Generación del reporte PDF de hallazgos de glosa."""

from io import BytesIO

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)
from xml.sax.saxutils import escape

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
        Paragraph('Reporte de Segunda Glosa', e['titulo']),
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

    doc.build(story, onFirstPage=_pie, onLaterPages=_pie)
    return buffer.getvalue()
