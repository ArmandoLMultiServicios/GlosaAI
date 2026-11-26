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


def _pesos(valor):
    return f'$ {valor:,.2f}'


# ─── Hoja de control de riesgos del embarque ───
# Sigue el diseño del formato en papel de la agencia: renglones con casillas ( X ) SI ( ) NO y
# datos sobre línea. Lo que llena el sistema va en azul (como escrito a mano) y la evidencia en
# letra chica debajo de cada renglón.

TINTA = '#1e3a5f'

ETIQUETAS_FORMATO = {
    'comprobante_pago': 'ANEXA IMPORTE DEL COMPROBANTE DE PAGO AL PROVEEDOR',
    'orden_compra': 'ORDEN DE COMPRA DEL PROVEEDOR CUADRA CON VALOR Y PRECIO UNITARIO',
    'contrato': 'PRESENTO CONTRATO DE COMPRA-VENTA DEL PROVEEDOR, COINCIDEN NOMBRES Y DATOS',
    'nom_etiquetado': 'LLEVA NOMS DE ETIQUETADO',
    'telas_carta': 'SON TELAS Y PRESENTA LA CARTA Y COINCIDE CON LA FACTURA',
    'listado_no_previo': 'ESTA EN EL LISTADO DE NO PREVIO',
    'previo_origen': 'PRESENTARON YA PREVIO DE ORIGEN LEGIBLE',
    'uvnom': 'SOLICITAR AL CLIENTE LA UVNOM / SE HACE PREVIO EN PUERTO',
    'nom_seguridad': 'LLEVA NOMS DE SEGURIDAD',
    'son_telas': 'SON TELAS',
    'textiles_varios': 'SON PRODUCTOS TEXTILES VARIOS',
    'permisos_c1': 'PRESENTO PERMISOS C1 (SI NO, DEBERAN SOLICITARLOS)',
    'csf_mes': 'TENEMOS LA CSF DEL MES EN CURSO',
    'csf_giro': 'LA CSF COINCIDE CON EL GIRO DECLARADO',
    'opinion_cumplimiento': 'OPINION DE CUMPLIMIENTO DEL MES EN CURSO',
    'datos_importador': 'REVISE DATOS EXACTOS DEL IMPORTADOR',
    'vinculacion_declarada': 'SE DECLARA VINCULACION',
    'vinculacion_documento': 'DOCUMENTO QUE LO COMPRUEBA',
    'preferencia_declarada': 'SE DECLARA ALGUNA PREFERENCIA ARANCELARIA',
    'preferencia_certificado': 'ANEXA CERTIFICADO',
    'cuota_declarada': 'SE DECLARA CUOTA COMPENSATORIA',
    'cuota_certificado': 'ANEXA CERTIFICADO ANEXO VIII',
    'mve_incrementables': '1.- FACTURA CON DESGLOSE DE LOS GASTOS INCREMENTABLES '
                          '(SE DIGITALIZA EN LA MANIFESTACION DE VALOR)',
    'mve_comprobante': '2.- COMPROBANTE DE FECHA DE PAGO DE LOS GASTOS INCREMENTABLES',
}


def _estilos_formato():
    base = getSampleStyleSheet()['Normal']

    def estilo(nombre, **kw):
        return ParagraphStyle(nombre, parent=base, **{'fontName': 'Helvetica', 'fontSize': 8.5,
                                                      'leading': 11, **kw})

    return {
        'titulo': estilo('f_titulo', fontName='Helvetica-Bold', fontSize=14, leading=18),
        'seccion': estilo('f_seccion', fontName='Helvetica-Bold', fontSize=9),
        'nota': estilo('f_nota', fontName='Helvetica-Bold', fontSize=9, alignment=2),
        'texto': estilo('f_texto'),
        'negrita': estilo('f_negrita', fontName='Helvetica-Bold'),
        'tinta': estilo('f_tinta', fontName='Helvetica-Bold', textColor=colors.HexColor(TINTA)),
        'evidencia': estilo('f_evidencia', fontName='Helvetica-Oblique', fontSize=7, leading=9,
                            textColor=colors.HexColor('#6b7280'), leftIndent=12),
        'tabla': estilo('f_tabla', fontSize=7.5, leading=9, alignment=2),
        'tabla_izq': estilo('f_tabla_izq', fontSize=7.5, leading=9),
        'tabla_b': estilo('f_tabla_b', fontName='Helvetica-Bold', fontSize=7.5, leading=9, alignment=2),
    }


def _tinta(texto):
    return f'<font color="{TINTA}"><b>{escape(str(texto))}</b></font>'


def _casilla(marcada):
    return f'( {_tinta("X")} )' if marcada else '(&nbsp;&nbsp;&nbsp;)'


def _aviso(respuesta):
    if respuesta == 'no_verificable':
        return ' &nbsp;<font size="7" color="#b45309"><b>NO VERIFICABLE</b></font>'
    if respuesta == 'no_aplica':
        return ' &nbsp;<font size="7" color="#6b7280"><b>NO APLICA</b></font>'
    return ''


def _renglon(celdas, anchos, subrayar=(), arriba=3):
    """Un renglón del formato; las columnas en `subrayar` llevan la línea donde va el dato."""
    t = Table([celdas], colWidths=anchos)
    estilo = [('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
              ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 4),
              ('TOPPADDING', (0, 0), (-1, -1), arriba), ('BOTTOMPADDING', (0, 0), (-1, -1), 1)]
    estilo += [('LINEBELOW', (i, 0), (i, 0), 0.5, colors.black) for i in subrayar]
    t.setStyle(TableStyle(estilo))
    return t


def _marcas_opciones(id_, item):
    marcadas = [str(o).upper().strip() for o in item.get('opciones') or []]
    partes, usadas = [], set()
    for opcion in cr.OPCIONES[id_]:
        clave = opcion.split()[0]   # 'OTROS GASTOS' → 'OTROS'
        encontrada = [m for m in marcadas if m.startswith(opcion) or clave in m]
        usadas.update(encontrada)
        partes.append(f'{opcion} {_casilla(bool(encontrada))}')
    if id_ != 'mve_incrementables':
        otras = [m for m in marcadas if m not in usadas]
        partes.append('OTRAS ' + (_tinta(', '.join(otras)) if otras else '________'))
    return '&nbsp;&nbsp;'.join(partes)


def _pregunta(id_, item, f, ancho):
    """Renglón de una pregunta: etiqueta, casillas y, debajo, la evidencia."""
    respuesta = item.get('respuesta')
    etiqueta = escape(ETIQUETAS_FORMATO.get(id_, cr.PREGUNTAS.get(id_, id_)))
    if id_ in cr.OPCIONES:
        texto = f'{etiqueta}: {_marcas_opciones(id_, item)}{_aviso(respuesta)}'
        filas = [_renglon([Paragraph(texto, f['texto'])], [ancho])]
    else:
        marcas = (f'{_casilla(respuesta == "si")} SI &nbsp;&nbsp;{_casilla(respuesta == "no")} NO'
                  f'{_aviso(respuesta)}')
        filas = [_renglon([Paragraph(f'{etiqueta}:', f['texto']), Paragraph(marcas, f['texto'])],
                          [ancho * 0.66, ancho * 0.34])]
    if item.get('detalle'):
        filas.append(Paragraph(escape(item['detalle']), f['evidencia']))
    return [KeepTogether(filas)]


def _por_favor_solicitar(items, f, ancho):
    pedir = '; '.join(x['solicitar'].strip() for x in items if (x.get('solicitar') or '').strip())
    return _renglon([Paragraph('Por favor solicitar:', f['texto']),
                     Paragraph(_tinta(pedir) if pedir else '', f['texto']), ''],
                    [ancho * 0.18, ancho * 0.62, ancho * 0.20], subrayar=(1,), arriba=6)


def _encabezado_seccion(titulo, nota, f, ancho):
    if not nota:
        return [Spacer(1, 10), _renglon([Paragraph(escape(titulo), f['seccion'])], [ancho])]
    return [Spacer(1, 10), _renglon([Paragraph(escape(titulo), f['seccion']),
                                     Paragraph(escape(nota), f['nota'])],
                                    [ancho * 0.68, ancho * 0.32])]


def _seccion_valor(rv, f, ancho):
    p = cr.parametros_valor()
    story = [Spacer(1, 10), _renglon(
        [Paragraph('1.- REVISION DE RIESGO DEL VALOR TABLA ART. 165 FRACCION II INCISO a)',
                   ParagraphStyle('f_seccion1', parent=f['seccion'], fontSize=8.5)),
         Paragraph(f'IMPORTE MAXIMO DE OMISION: {_pesos(rv["importe_maximo"])} pesos', f['nota'])],
        [ancho * 0.60, ancho * 0.40]), Spacer(1, 6)]

    tabla = rv['tabla']
    tasas = set(rv.get('tasas') or [])
    num = lambda v: Paragraph(v, f['tabla'])
    filas = [
        [Paragraph('<b>Tasa</b>', f['tabla_izq'])] + [Paragraph(f"<b>{t['tasa']:g}%</b>", f['tabla']) for t in tabla],
        [Paragraph('Tasa + IVA y dta', f['tabla_izq'])] + [num(f"{t['omitido'] - t['diferencia']:.4f}%") for t in tabla],
        [Paragraph(f"dif para {p['tasa_referencia']:g}%", f['tabla_izq'])] + [num(f"{t['diferencia']:g}%") for t in tabla],
        [Paragraph('total omitido', f['tabla_izq'])] + [num(f"{t['omitido']:.0f}%") for t in tabla],
        [Paragraph('Valor merc', f['tabla_izq'])] + [num(_pesos(t['valor_maximo'])) for t in tabla],
    ]
    if tabla and tabla[0]['valor_maximo_usd'] is not None:
        filas.append([Paragraph('usd x tipo de cambio', f['tabla_izq'])]
                     + [num(_pesos(t['valor_maximo_usd'])) for t in tabla])
    t = Table(filas, colWidths=[ancho * 0.16] + [ancho * 0.12] * len(tabla))
    estilo = [('GRID', (0, 0), (-1, -1), 0.4, colors.black),
              ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
              ('LEFTPADDING', (0, 0), (-1, -1), 2), ('RIGHTPADDING', (0, 0), (-1, -1), 2),
              ('TOPPADDING', (0, 0), (-1, -1), 1.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5)]
    for i, fila in enumerate(tabla, start=1):
        if fila['tasa'] in tasas:
            estilo += [('BACKGROUND', (i, 0), (i, -1), colors.HexColor('#e8eef6')),
                       ('BOX', (i, 0), (i, -1), 1.4, colors.HexColor(TINTA))]
    t.setStyle(TableStyle(estilo))
    story += [t, Spacer(1, 6)]

    if rv.get('evaluado'):
        tasas_txt = ', '.join(f'{x:g}%' for x in sorted(tasas))
        determina = (f'Tasa(s) {tasas_txt} · valor en aduana {_pesos(rv["valor_total"])} · '
                     f'omisión estimada {_pesos(rv["omision"])}')
    else:
        determina = 'No se pudieron leer las tasas y valores del pedimento: determinarlo con la tabla'
    story.append(_renglon([Paragraph('Señalar en cual se determina:', f['texto']),
                           Paragraph(_tinta(determina), f['texto'])],
                          [ancho * 0.27, ancho * 0.73], subrayar=(1,)))

    if rv.get('evaluado') and len(rv['partidas']) > 1:
        filas = [[Paragraph(f'<b>{x}</b>', f['tabla_izq']) for x in
                  ('Partida', 'Fracción', 'Tasa', 'Valor en aduana', 'Omisión estimada')]]
        for d in rv['partidas']:
            filas.append([Paragraph(escape(str(d.get('partida', ''))), f['tabla_izq']),
                          Paragraph(escape(str(d.get('fraccion', ''))), f['tabla_izq']),
                          num(f"{d['tasa_igi']:g}%"), num(_pesos(d['valor_aduana'])), num(_pesos(d['omision']))])
        t = Table(filas, colWidths=[ancho * 0.12, ancho * 0.22, ancho * 0.12, ancho * 0.22, ancho * 0.22],
                  hAlign='LEFT', repeatRows=1)
        t.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.black),
                               ('TOPPADDING', (0, 0), (-1, -1), 1), ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
                               ('LEFTPADDING', (0, 0), (-1, -1), 2)]))
        story += [Spacer(1, 4), t]

    pasa = rv.get('pasa')
    marca = lambda si: Paragraph(_tinta('X') if si else '', f['texto'])
    story.append(_renglon(
        [Paragraph('Señalar', f['texto']), Paragraph('SI Pasa:', f['texto']), marca(pasa is True),
         Paragraph('No Pasa:', f['texto']), marca(pasa is False),
         Paragraph('Notificar al Gerente:', f['texto']), marca(pasa is False),
         Paragraph('' if rv.get('evaluado') else '<font size="7" color="#b45309"><b>NO VERIFICABLE</b></font>',
                   f['texto'])],
        [ancho * 0.10, ancho * 0.09, ancho * 0.12, ancho * 0.09, ancho * 0.12, ancho * 0.19, ancho * 0.12,
         ancho * 0.17],
        subrayar=(2, 4, 6), arriba=8))
    return story


def _hoja_control_riesgos(c, e, ancho, pedimento, fecha):
    f = _estilos_formato()
    enc = c.get('encabezado') or {}
    rv = c.get('riesgo_valor') or cr.calcular_riesgo_valor([])
    respuestas = {x.get('pregunta'): x for x in c.get('respuestas') or []}
    item = lambda id_: respuestas.get(id_) or {'pregunta': id_, 'respuesta': 'no_verificable', 'detalle': ''}
    dato = lambda v: Paragraph(_tinta(v) if v else '', f['texto'])
    etq = lambda t: Paragraph(t, f['negrita'])

    story = [Paragraph('REVISION DE CONTROL DE RIESGOS DEL EMBARQUE', f['titulo']), Spacer(1, 8),
             _renglon([etq('REFERENCIA'), dato(enc.get('referencia')), '', etq('FECHA Y HORA:'), dato(fecha)],
                      [ancho * 0.15, ancho * 0.33, ancho * 0.07, ancho * 0.17, ancho * 0.28], subrayar=(1, 4)),
             _renglon([etq('PEDIMENTO'), dato(pedimento), ''], [ancho * 0.15, ancho * 0.33, ancho * 0.52],
                      subrayar=(1,)),
             _renglon([Paragraph(
                 f'CONTENEDORES {_casilla(enc.get("contenedores"))} CANTIDAD '
                 f'<u>&nbsp;{_tinta(enc.get("cantidad_contenedores") or "") if enc.get("contenedores") else "&nbsp;&nbsp;&nbsp;"}&nbsp;</u>'
                 f' &nbsp;CARGA SUELTA {_casilla(enc.get("carga_suelta"))}', f['texto'])], [ancho], arriba=6),
             _renglon([Paragraph('NOMBRE DEL IMPORTADOR:', f['texto']), dato(enc.get('importador')), ''],
                      [ancho * 0.27, ancho * 0.48, ancho * 0.25], subrayar=(1,), arriba=6),
             _renglon([Paragraph('VALOR FACTURA:', f['texto']), dato(enc.get('valor_factura')), ''],
                      [ancho * 0.18, ancho * 0.52, ancho * 0.30], subrayar=(1,), arriba=6)]

    pago = item('comprobante_pago')
    pago_txt = pago.get('detalle') if pago.get('respuesta') == 'si' else ''
    story += [_renglon([Paragraph('ANEXA IMPORTE DEL COMPROBANTE DE PAGO AL PROVEEDOR:', f['texto']),
                        dato(pago_txt), Paragraph('SOLICITARLO:', f['texto']),
                        dato(pago.get('solicitar') or '')],
                       [ancho * 0.53, ancho * 0.15, ancho * 0.14, ancho * 0.18], subrayar=(1, 3), arriba=6)]
    if pago.get('respuesta') != 'si' and pago.get('detalle'):
        story.append(Paragraph(escape(pago['detalle']), f['evidencia']))
    story += _pregunta('orden_compra', item('orden_compra'), f, ancho)
    notas = '; '.join(x['solicitar'].strip() for x in (item('orden_compra'), item('contrato'))
                      if (x.get('solicitar') or '').strip())
    story.append(_renglon([Paragraph('NOTAS:', f['texto']), dato(notas)], [ancho * 0.09, ancho * 0.91],
                          subrayar=(1,), arriba=6))
    story += [Spacer(1, 6)] + _pregunta('contrato', item('contrato'), f, ancho)

    story += _seccion_valor(rv, f, ancho)

    for id_seccion, titulo, nota, preguntas in cr.SECCIONES:
        if id_seccion == 'documentos_compra':
            continue
        items = [item(id_) for id_, _ in preguntas]
        story += _encabezado_seccion(titulo, nota, f, ancho)
        for id_, _ in preguntas:
            story += _pregunta(id_, item(id_), f, ancho)
        story.append(_por_favor_solicitar(items, f, ancho))
    return story
