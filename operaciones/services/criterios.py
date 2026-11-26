
"""Lista de verificación fija y criterios de severidad de la segunda glosa.

Todo lo que el modelo debe revisar, y cómo calificar lo que encuentre, vive aquí para que el
análisis sea repetible entre corridas. Para agregar un punto basta con añadirlo a
LISTA_VERIFICACION: el prompt, el esquema de salida y el reporte PDF lo toman automáticamente.
"""

# (id, título, qué revisar). El orden es el orden de revisión y del reporte.
LISTA_VERIFICACION = [
    # Partes y factura
    ('importador', 'Importador / exportador',
     'RFC, nombre o razón social y domicilio del pedimento contra factura, BL/guía, COVE y '
     'certificados (origen, NOM).'),
    ('proveedor', 'Proveedor / comprador',
     'Nombre, ID fiscal y domicilio del proveedor contra factura y certificado de origen; '
     'vinculación declarada.'),
    ('factura', 'Factura comercial',
     'Número y fecha de cada factura, INCOTERM, moneda y factor de moneda, contra la factura, la '
     'relación de facturas o escrito de partidas, el COVE y las referencias en BL y certificados.'),

    # Valor
    ('valor_comercial', 'Valor en dólares y valor comercial',
     'Valor en dólares contra el total de la factura; valor comercial = valor en moneda de factura '
     '× factor × tipo de cambio del pedimento.'),
    ('incrementables', 'Incrementables y decrementables',
     'Fletes, seguros, embalajes y otros incrementables o decrementables, y su coherencia con el '
     'INCOTERM, el BL (prepaid/collect) y el lugar de entrega.'),
    ('valor_aduana', 'Valor en aduana por partida',
     'Conversión de cada renglón de factura al tipo de cambio del pedimento contra el valor en '
     'aduana y el valor comercial de cada partida; suma de partidas contra el total.'),
    ('vinculacion_valoracion', 'Vinculación y método de valoración',
     'Método de valoración declarado, vinculación y evidencia de que no afectó el precio; '
     'precios distintos para mercancía idéntica.'),

    # Mercancía
    ('descripcion', 'Descripción, números de parte y modelos',
     'Descripción, número de parte, marca y modelo de cada partida contra la factura y el escrito '
     'de partidas; que la descripción permita identificar la mercancía.'),
    ('cantidades', 'Cantidades y unidades de medida',
     'Cantidad UMC y UMT de cada partida contra factura, packing list, BL y certificados; '
     'claves de unidad de medida.'),
    ('precios_unitarios', 'Precios unitarios',
     'Precio unitario de cada partida = valor / cantidad, y su equivalencia con el precio de '
     'factura convertido.'),
    ('fraccion', 'Fracción arancelaria',
     'Fracción de cada partida contra la naturaleza de la mercancía según factura, fichas, '
     'certificados NOM (campo de aplicación) y HS del BL y del certificado de origen.'),
    ('nico', 'NICO',
     'NICO de cada partida contra la descripción y características de la mercancía; mismo NICO '
     'para mercancía de iguales características.'),
    ('origen', 'País de origen y vendedor',
     'País de origen y de vendedor de cada partida contra factura, BL y certificado de origen.'),
    ('preferencia', 'Preferencia arancelaria y certificado de origen',
     'Tasa aplicada e identificador de trato preferencial contra el certificado de origen: número, '
     'fecha, vigencia, exportador, productor, importador, factura, cantidad, HS y criterio.'),
    ('certificado_eur1', 'Certificado de circulación EUR.1 (TLCUEM)',
     'Si se aplica preferencia del TLC con la Unión Europea, Andorra o San Marino, revisa campo '
     'por campo el EUR.1 contra las REGLAS DEL CERTIFICADO EUR.1 y contra pedimento, factura y BL. '
     'Si la preferencia es de otro tratado o no hay EUR.1, marca no_aplica.'),
    ('regulaciones', 'Regulaciones no arancelarias (NOM, permisos)',
     'Identificadores NM/EN/permisos de cada partida contra los certificados proporcionados: '
     'que ampare el modelo y la medida, titular, y vigencia a la fecha de entrada.'),
    ('identificadores', 'Identificadores y e-documents',
     'COVE, e-documents (ED) y demás identificadores declarados contra los documentos '
     'proporcionados; documentos declarados que no se proporcionaron.'),

    # Transporte
    ('documento_transporte', 'Documento de transporte',
     'Número de BL master o guía master, transportista y su RFC contra el BL master, Delivery '
     'Order y factura. El BL house no se revisa (ver REGLAS DEL BL).'),
    ('medio_transporte', 'Medio de transporte',
     'Nombre del buque, número y dirección de viaje y bandera del pedimento contra BL, Delivery '
     'Order y factura. Si los documentos soporte mencionan buques distintos, repórtalo aunque el '
     'pedimento coincida con alguno.'),
    ('fechas', 'Fechas de entrada, pago y embarque',
     'Fecha de entrada contra la fecha de arribo de la Delivery Order, aviso de arribo o '
     'manifiesto; fecha de pago; fechas de embarque de BL y factura.'),
    ('peso_bultos', 'Peso y bultos',
     'Peso bruto, número de bultos y marcas contra BL, Delivery Order y packing list.'),
    ('contenedores', 'Contenedores y sellos',
     'Número y tipo de contenedor, y sellos, contra BL y Delivery Order.'),
    ('aduana_destino', 'Aduana, destino y recinto',
     'Aduana de entrada/despacho, destino de la mercancía y recinto fiscalizado contra puerto de '
     'descarga, lugar de entrega y terminal del BL y la Delivery Order.'),

    # Contribuciones
    ('tipo_cambio', 'Tipo de cambio',
     'Tipo de cambio aplicado contra el publicado en el DOF para la fecha que corresponda; si no '
     'se proporcionó la publicación, márcalo no verificable.'),
    ('contribuciones', 'Contribuciones por partida y a nivel pedimento',
     'Tasas y cálculo de IGI, DTA, IVA, PRV, IVA/PRV y otras contribuciones, base gravable de cada '
     'una, y que la tasa corresponda a la preferencia y régimen.'),
    ('totales', 'Cuadro de liquidación',
     'Suma de contribuciones contra los totales del cuadro de liquidación y formas de pago.'),

    # Expediente
    ('expediente', 'Integridad del expediente',
     'Documentos que faltan para sustentar lo declarado, documentos ilegibles y documentos del '
     'expediente que no corresponden a la operación o están vencidos.'),
]

IDS_VERIFICACION = [p[0] for p in LISTA_VERIFICACION]
TITULOS_VERIFICACION = {p[0]: p[1] for p in LISTA_VERIFICACION}

# Resultado de cada punto de la lista de verificación.
RESULTADOS = {
    'coincide': 'Coincide',
    'discrepancia': 'Discrepancia',
    'no_verificable': 'No verificable',
    'no_aplica': 'No aplica',
}

CRITERIOS_SEVERIDAD = """\
- critica: afecta el pago de contribuciones o el cumplimiento de regulaciones. Ejemplos: \
diferencia en valor en aduana, base gravable, tasa o contribuciones mayor a $100 MXN; preferencia \
arancelaria sin certificado de origen válido o que no ampara la mercancía; NOM o permiso faltante, \
vencido o que no ampara el modelo declarado; mercancía o cantidades no amparadas por la factura.
- alta: un dato declarado en el pedimento contradice directamente a un documento soporte y obliga \
a rectificar, aunque no cambie las contribuciones. Ejemplos: buque, viaje, BL, contenedor o fecha \
de entrada distintos a los del documento de transporte; número o fecha de factura, proveedor, ID \
fiscal o RFC distintos; peso o bultos distintos; fracción arancelaria contradicha por un documento \
soporte (p. ej. un certificado NOM o ficha que describe otra mercancía).
- media: riesgo que requiere análisis técnico o confirmación externa antes de decidir si se \
rectifica, o discrepancia entre documentos soporte que involucra un dato declarado en el pedimento. \
Ejemplos: clasificación o NICO dudosos sin evidencia concluyente; criterio de NICO inconsistente \
entre partidas; documentos soporte con buques o fechas distintos entre sí.
- baja: discrepancia entre documentos soporte que no afecta ningún dato declarado en el pedimento, \
o asunto de forma. Ejemplos: fecha de zarpe distinta entre factura y BL; INCOTERM mal redactado \
sin efecto en el valor; descripción genérica pero correcta.
- informativa: no hay discrepancia, pero falta información para verificar o hay una recomendación. \
Ejemplos: documento declarado que no se proporcionó; dato no verificable; documento sobrante o \
vencido no utilizado en el pedimento; oportunidad de decrementar o de recuperar un pago indebido \
que debe confirmarse.
Si dudas entre dos niveles, aplica la definición literal: no subas un hallazgo de nivel por \
precaución ni lo bajes por ser frecuente.\
"""

TOLERANCIAS = """\
- Importes en MXN: diferencias de hasta $1 por partida o por concepto se deben a redondeo y no son \
hallazgos.
- Importes en moneda extranjera: diferencias de hasta 0.01 por renglón no son hallazgos.
- Pesos: el peso bruto debe coincidir exactamente con el BL; diferencias solo por formato \
(separadores, unidades equivalentes) no son hallazgos.\
"""


# Requisitos de llenado de documentos específicos. Cada entrada se agrega al prompt como una
# sección "REGLAS DEL <nombre>". Para revisar otro documento (p. ej. certificado T-MEC) añade una
# entrada aquí y un punto en LISTA_VERIFICACION que haga referencia a ella.
REGLAS_DOCUMENTOS = {
    'CERTIFICADO EUR.1': """\
Notas al Certificado de circulación EUR.1 (Decisión 2/2000 del Consejo Conjunto CE-México, Anexo \
III). Para aplicar trato preferencial el certificado debe estar expedido por la autoridad \
aduanera de un Estado Miembro de la Comunidad, del Principado de Andorra o de la República de San \
Marino, y cumplir:
- Campo 1 (obligatorio): nombre completo o razón social, domicilio completo y país del exportador.
- Campo 2 (obligatorio): país, grupo de países o territorio de exportación y de importación. Para \
mercancías comunitarias se aceptan el Estado Miembro, "Comunidad Europea", "Unión Europea" o las \
siglas CE, UE, CM (Ceuta y Melilla), AD (Andorra), SM (San Marino).
- Campo 3 (opcional): si se llena, nombre o razón social, domicilio completo y país del \
destinatario; debe coincidir con el importador del pedimento.
- Campo 4 (obligatorio): país, grupo de países o territorio de origen de las mercancías, con las \
mismas denominaciones aceptadas en el campo 2. Debe ser congruente con el país de origen \
declarado en el pedimento.
- Campo 5 (obligatorio): país, grupo de países o territorio de destino (México).
- Campo 6 (opcional): medio de transporte, número de guía aérea o BL; si se llena, debe coincidir \
con el documento de transporte y el pedimento.
- Campo 7 (observaciones):
  * Textiles de las partidas 52.08 a 52.16, 54.07 a 54.08, 55.12 a 55.16, 58.01, 58.06 y 58.11 que \
usen la regla del cupo del Apéndice II deben llevar la leyenda "Cumple la norma de origen \
específica establecida en el Apéndice II" o "Meets the specific rule of origin as set out in \
Appendix II".
  * Calzado de las partidas 64.02 a 64.04 que use la regla del Apéndice II(a) debe llevar "Cumple \
la norma de origen específica establecida en la Nota 9 del Apéndice II(a)" o "Meets the specific \
rule of origin as set out in Appendix II(a), Note 9".
  * Un duplicado (art. 18) debe decir "Duplicado" (o su equivalente en un idioma oficial).
  * Un certificado expedido después de la exportación (art. 17) debe decir "Expedido a \
Posteriori" o "Issued Retrospectively".
- Campo 8 (obligatorio): número de orden de cada producto; marcas y numeración; número y \
naturaleza de los bultos (o "a granel"); designación comercial suficiente para relacionarla con la \
factura, y clasificación arancelaria al menos a partida (4 dígitos) del Sistema Armonizado, que \
debe ser congruente con la fracción del pedimento. No debe haber líneas ni espacios en blanco \
entre productos, y después del último debe haber una línea horizontal y una cruzada (o rayado) \
que impida añadir texto. Para grandes envíos o descripción genérica puede usarse el \
procedimiento de las Notas Explicativas.
- Campo 9 (obligatorio): masa bruta (kg) u otra medida de la cantidad amparada; compárala con \
pedimento, factura, packing list y BL.
- Campo 10 (opcional): número de las facturas. Es obligatorio si el campo 8 usa el procedimiento \
de las Notas Explicativas para grandes envíos o descripción genérica. Si se llena, debe coincidir \
con la factura del pedimento.
- Campo 11 (obligatorio): lugar y fecha de expedición, autoridad aduanera y país de expedición \
(pueden venir en el sello si son legibles); firmado, fechado y sellado por la autoridad aduanera \
del país de exportación. En un duplicado la fecha es la del certificado original. La importación \
debe efectuarse dentro de los 10 meses siguientes a la fecha de expedición: compara contra la \
fecha de entrada o de pago del pedimento.
- Campo 12 (obligatorio): llenado completo, firmado y fechado por el exportador o su representante.
- Campos 13 y 14: uso exclusivo de la autoridad; no son hallazgos si están vacíos.
Severidad: un EUR.1 vencido (más de 10 meses), sin firma o sello de la autoridad (campo 11) o del \
exportador (campo 12), con campos obligatorios vacíos, sin la leyenda requerida en el campo 7, o \
cuyas mercancías, partida o cantidad no corresponden a lo declarado invalida la preferencia: es \
critica. Defectos de forma que no impiden relacionar el certificado con la mercancía (p. ej. \
espacio en blanco sin cancelar, domicilio incompleto) son media.""",
    'BL': """Solo se revisa el BL master (master bill of lading / guía master: el que emite la naviera o aerolínea). El BL house (house bill of lading, guía house o hija: el que emite el agente de carga o NVOCC) se ignora por completo:
- Toda referencia a "BL" en la lista de verificación significa el BL master.
- No compares datos contra el BL house ni generes hallazgos a partir de él, aunque se haya proporcionado o aunque contradiga al pedimento o a otros documentos.
- No verifiques el número de guía house declarado en el pedimento, ni reportes que falta el BL house o que no se proporcionó.
- Si se proporcionó un BL house, regístralo en `documentos` indicando que es house y que se ignoró; no lo uses como fuente de ningún dato.
- Para distinguirlos: el master lo emite el transportista (naviera o aerolínea) y su embarcador suele ser el agente de carga; el house lo emite el agente de carga y su embarcador suele ser el proveedor. Busca las leyendas "MASTER", "HOUSE", "MBL", "HBL", "MAWB" o "HAWB".
- Si solo hay un BL y no se puede saber si es master o house, úsalo como BL master.""",
}


def texto_reglas_documentos():
    return '\n\n'.join(f'REGLAS DEL {nombre}:\n{texto}' for nombre, texto in REGLAS_DOCUMENTOS.items())


def texto_lista_verificacion():
    return '\n'.join(f'{i}. [{id_}] {titulo}: {que}'
                     for i, (id_, titulo, que) in enumerate(LISTA_VERIFICACION, start=1))
