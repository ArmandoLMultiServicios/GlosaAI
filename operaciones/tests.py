import json
from io import BytesIO
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from .services import analizador, control_riesgos, trabajos
from .services.analizador import (ESQUEMA_RESULTADO, SYSTEM_PROMPT, Archivo, construir_contenido,
                                  detectar_pedimento, normalizar_lista)
from .services.criterios import IDS_VERIFICACION, LISTA_VERIFICACION
from .services.proveedores import (Documento, ErrorAnalisis, Proveedor, Respuesta, Texto,
                                   obtener_proveedor)
from .services.reporte import generar_reporte

PDF_MINIMO = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF'

RESULTADO = {
    'resumen': 'Se detectó una diferencia en el peso bruto.',
    'datos_pedimento': {'numero_pedimento': '26 51 1698 6000855', 'tipo_cambio': '18.42500',
                        'valor_dolares': '51,743.00', 'incoterm': 'CIF'},
    'documentos': [{'archivo': 'FAC.pdf', 'tipo_documento': 'Factura',
                    'descripcion': 'Factura 10019171 por 51,743.00 USD', 'legible': True}],
    'hallazgos': [
        {'punto': 'fechas', 'severidad': 'baja', 'categoria': 'Documental', 'campo': 'Fecha', 'documento': 'BL.pdf',
         'valor_pedimento': '18/10/2026', 'valor_documento': '17/10/2026', 'calculo': '',
         'descripcion': 'Fecha distinta', 'recomendacion': 'Revisar'},
        {'punto': 'peso_bultos', 'severidad': 'alta', 'categoria': 'Cantidades', 'campo': 'Peso bruto', 'documento': 'BL.pdf',
         'valor_pedimento': '7,270.044 kg', 'valor_documento': '7,300.000 kg',
         'calculo': '7,300.000 - 7,270.044 = 29.956 kg', 'descripcion': 'Diferencia de peso <&>',
         'recomendacion': 'Rectificar el pedimento'},
    ],
    'lista_verificacion': normalizar_lista([
        {'punto': 'factura', 'resultado': 'coincide', 'detalle': 'Factura 10019171 en todos'},
        {'punto': 'peso_bultos', 'resultado': 'discrepancia', 'detalle': '7,270.044 vs 7,300'},
        {'punto': 'tipo_cambio', 'resultado': 'no_verificable', 'detalle': 'Sin DOF'},
    ]),
    'conclusion': 'Se recomienda rectificar.',
    'control_riesgos': control_riesgos.normalizar({
        'encabezado': {'referencia': 'MS-1234', 'contenedores': True, 'cantidad_contenedores': '2',
                       'carga_suelta': False, 'importador': 'IMPORTADORA SA DE CV',
                       'valor_factura': '51,743.00 USD'},
        'partidas': [{'partida': '1', 'fraccion': '6109.10.01', 'tasa_igi': 25, 'valor_aduana': 500000},
                     {'partida': '2', 'fraccion': '8471.30.01', 'tasa_igi': 0, 'valor_aduana': 450000}],
        'respuestas': [
            {'pregunta': 'nom_etiquetado', 'respuesta': 'si', 'detalle': 'NOM-004 en partida 1',
             'solicitar': '', 'opciones': ['NOM-004-SE-2021', 'NOM-050']},
            {'pregunta': 'mve_incrementables', 'respuesta': 'si', 'detalle': 'Factura desglosa flete',
             'solicitar': '', 'opciones': ['FLETE']},
            {'pregunta': 'csf_mes', 'respuesta': 'no_verificable', 'detalle': 'No se proporcionó',
             'solicitar': 'CSF del mes en curso'},
        ],
    }, '18.42500'),
}


def pdf_con_texto(*paginas):
    """PDF con una página por cada texto recibido."""
    buffer = BytesIO()
    c = canvas.Canvas(buffer)
    for texto in paginas:
        c.drawString(72, 720, texto)
        c.showPage()
    c.save()
    return buffer.getvalue()


class HiloInmediato:
    """Sustituye a threading.Thread en las pruebas: ejecuta el trabajo en el momento."""

    def __init__(self, target, args=(), daemon=None):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


@override_settings(CORREO_CONFIGURADO=True, CORREO_DOMINIO='multiservicios.mx')
class GlosaTests(TestCase):
    def setUp(self):
        hilo = mock.patch.object(trabajos.threading, 'Thread', HiloInmediato)
        hilo.start()
        self.addCleanup(hilo.stop)
        self.usuario = User.objects.create_user('armandol', password='clave-de-prueba-123')
        self.client.force_login(self.usuario)

    def _archivos(self):
        return [SimpleUploadedFile('1698-510-6000855-N.pdf', PDF_MINIMO, 'application/pdf'),
                SimpleUploadedFile('FAC.pdf', PDF_MINIMO, 'application/pdf'),
                SimpleUploadedFile('COVE.xml', b'<cove>1</cove>', 'text/xml')]

    def _enviar(self, **extra):
        datos = {'archivos': self._archivos(), 'usuario': 'armandol'}
        datos.update(extra)
        return self.client.post(reverse('operaciones:analizar'), datos)

    def test_pagina_inicio(self):
        resp = self.client.get(reverse('operaciones:inicio'))
        self.assertContains(resp, 'id="dropzone"')
        self.assertContains(resp, 'name="csrf-token"')
        self.assertContains(resp, 'id="usuario"')
        self.assertContains(resp, '@multiservicios.mx')
        self.assertContains(resp, 'value="armandol"')   # correo sugerido: el del usuario
        self.assertContains(resp, 'Cerrar sesión')
        self.assertNotContains(resp, 'Usuarios</a>')     # solo el personal administra usuarios

    def test_sin_sesion_redirige_al_login(self):
        self.client.logout()
        resp = self.client.get(reverse('operaciones:inicio'))
        self.assertRedirects(resp, f"{reverse('login')}?next=/")
        with mock.patch.object(trabajos, 'analizar') as analizar:
            resp = self._enviar()
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp['Location'].startswith(reverse('login')))
        analizar.assert_not_called()
        self.assertEqual(len(mail.outbox), 0)

    def test_inicio_y_cierre_de_sesion(self):
        self.client.logout()
        resp = self.client.get(reverse('login'))
        self.assertContains(resp, 'Iniciar sesión')
        resp = self.client.post(reverse('login'), {'username': 'armandol', 'password': 'mala'})
        self.assertContains(resp, 'Usuario o contraseña incorrectos')
        resp = self.client.post(reverse('login'), {'username': 'armandol', 'password': 'clave-de-prueba-123'})
        self.assertRedirects(resp, reverse('operaciones:inicio'))
        resp = self.client.post(reverse('logout'))
        self.assertRedirects(resp, reverse('login'))
        self.assertEqual(self.client.get(reverse('operaciones:inicio')).status_code, 302)

    def _como_admin(self):
        admin = User.objects.create_superuser('admin', password='clave-de-prueba-123')
        self.client.force_login(admin)
        return admin

    def test_usuarios_solo_para_administradores(self):
        self.assertEqual(self.client.get(reverse('operaciones:usuarios')).status_code, 403)
        self.assertEqual(self.client.get(reverse('operaciones:usuario_nuevo')).status_code, 403)
        self.assertEqual(self.client.post(reverse('operaciones:usuario_eliminar', args=[self.usuario.pk])).status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.usuario.pk).exists())
        self._como_admin()
        resp = self.client.get(reverse('operaciones:inicio'))
        self.assertContains(resp, 'Usuarios</a>')
        resp = self.client.get(reverse('operaciones:usuarios'))
        self.assertContains(resp, 'armandol')
        self.assertContains(self.client.get(reverse('operaciones:usuarios') + '?q=nadie'), 'Ningún usuario coincide')

    def test_alta_de_usuario(self):
        self._como_admin()
        resp = self.client.get(reverse('operaciones:usuario_nuevo'))
        self.assertContains(resp, 'name="first_name"')
        self.assertContains(resp, 'name="administrador"')
        datos = {'username': 'Juanp', 'first_name': 'Juan', 'last_name': 'Pérez', 'email': '',
                 'password1': 'Aduana-Segura-2026', 'password2': 'Aduana-Segura-2026'}
        resp = self.client.post(reverse('operaciones:usuario_nuevo'), datos)
        self.assertRedirects(resp, reverse('operaciones:usuarios'), fetch_redirect_response=False)
        nuevo = User.objects.get(username='Juanp')
        self.assertEqual(nuevo.email, 'juanp@multiservicios.mx')
        self.assertFalse(nuevo.is_staff or nuevo.is_superuser)
        self.assertTrue(nuevo.check_password('Aduana-Segura-2026'))
        self.assertContains(self.client.get(reverse('operaciones:usuarios')), 'Se creó el usuario Juanp')

        self.client.post(reverse('operaciones:usuario_nuevo'),
                         {**datos, 'username': 'jefa', 'email': 'jefa@otro.mx', 'administrador': 'on'})
        jefa = User.objects.get(username='jefa')
        self.assertTrue(jefa.is_staff and jefa.is_superuser)

        # Errores: usuario repetido y contraseñas distintas
        resp = self.client.post(reverse('operaciones:usuario_nuevo'), {**datos, 'password2': 'otra-cosa-2026'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'campo-error')
        self.assertEqual(User.objects.filter(username__iexact='juanp').count(), 1)

    def test_editar_usuario_y_cambiar_su_contrasena(self):
        self._como_admin()
        url = reverse('operaciones:usuario_editar', args=[self.usuario.pk])
        self.assertContains(self.client.get(url), 'Eliminar usuario')
        resp = self.client.post(url, {'first_name': 'Armando', 'last_name': 'L', 'email': '', 'is_active': 'on',
                                      'administrador': 'on', 'nueva_contrasena': 'Nueva-Clave-2026',
                                      'confirmar_contrasena': 'Nueva-Clave-2026'})
        self.assertRedirects(resp, reverse('operaciones:usuarios'))
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.get_full_name(), 'Armando L')
        self.assertEqual(self.usuario.email, 'armandol@multiservicios.mx')
        self.assertTrue(self.usuario.is_superuser and self.usuario.is_staff)
        self.assertTrue(self.usuario.check_password('Nueva-Clave-2026'))

        # Sin contraseña nueva no se toca; quitar Activo y Administrador
        self.client.post(url, {'first_name': 'Armando', 'last_name': 'L', 'email': 'armandol@multiservicios.mx'})
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.is_active or self.usuario.is_superuser or self.usuario.is_staff)
        self.assertTrue(self.usuario.check_password('Nueva-Clave-2026'))

        resp = self.client.post(url, {'first_name': '', 'last_name': '', 'email': '',
                                      'nueva_contrasena': 'abc', 'confirmar_contrasena': 'xyz'})
        self.assertContains(resp, 'Las contraseñas no coinciden')

    def test_administrador_no_puede_quitarse_el_acceso(self):
        admin = self._como_admin()
        url = reverse('operaciones:usuario_editar', args=[admin.pk])
        self.assertNotContains(self.client.get(url), 'Eliminar usuario')
        self.client.post(url, {'first_name': '', 'last_name': '', 'email': '',
                               'nueva_contrasena': 'Otra-Clave-2026', 'confirmar_contrasena': 'Otra-Clave-2026'})
        admin.refresh_from_db()
        self.assertTrue(admin.is_active and admin.is_superuser and admin.is_staff)
        # Cambió su propia contraseña sin que se le cierre la sesión
        self.assertEqual(self.client.get(reverse('operaciones:usuarios')).status_code, 200)
        self.client.post(reverse('operaciones:usuario_eliminar', args=[admin.pk]))
        self.assertTrue(User.objects.filter(pk=admin.pk).exists())
        # A otro sí lo puede eliminar
        self.client.post(reverse('operaciones:usuario_eliminar', args=[self.usuario.pk]))
        self.assertFalse(User.objects.filter(pk=self.usuario.pk).exists())

    def test_mi_contrasena(self):
        url = reverse('operaciones:mi_contrasena')
        self.assertContains(self.client.get(url), 'Cambiar mi contraseña')
        resp = self.client.post(url, {'old_password': 'mala', 'new_password1': 'Nueva-Clave-2026',
                                      'new_password2': 'Nueva-Clave-2026'})
        self.assertContains(resp, 'campo-error')
        resp = self.client.post(url, {'old_password': 'clave-de-prueba-123', 'new_password1': 'Nueva-Clave-2026',
                                      'new_password2': 'Nueva-Clave-2026'})
        self.assertRedirects(resp, reverse('operaciones:inicio'), fetch_redirect_response=False)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('Nueva-Clave-2026'))
        self.assertContains(self.client.get(reverse('operaciones:inicio')), 'Tu contraseña se cambió')

    def test_contrasena_temporal_obliga_a_cambiarla(self):
        admin = self._como_admin()
        self.client.post(reverse('operaciones:usuario_nuevo'), {
            'username': 'juanp', 'first_name': 'Juan', 'last_name': '', 'email': '',
            'password1': 'Temporal-2026', 'password2': 'Temporal-2026'})
        self.assertContains(self.client.get(reverse('operaciones:usuarios')), 'Contraseña temporal')

        # Primer ingreso: cualquier página lo lleva a elegir su contraseña
        self.client.logout()
        resp = self.client.post(reverse('login'), {'username': 'juanp', 'password': 'Temporal-2026'}, follow=True)
        self.assertRedirects(resp, reverse('operaciones:mi_contrasena'))
        self.assertContains(resp, 'Elige tu contraseña')
        self.assertNotContains(resp, 'Cancelar')
        for url in (reverse('operaciones:inicio'), reverse('operaciones:usuarios')):
            self.assertRedirects(self.client.get(url), reverse('operaciones:mi_contrasena'))
        with mock.patch.object(trabajos, 'analizar') as analizar:
            self.assertEqual(self._enviar().status_code, 302)
        analizar.assert_not_called()
        # Puede cerrar sesión sin cambiarla
        self.assertRedirects(self.client.post(reverse('logout')), reverse('login'))
        self.client.login(username='juanp', password='Temporal-2026')

        # No puede quedarse con la misma
        url = reverse('operaciones:mi_contrasena')
        resp = self.client.post(url, {'old_password': 'Temporal-2026', 'new_password1': 'Temporal-2026',
                                      'new_password2': 'Temporal-2026'})
        self.assertContains(resp, 'debe ser distinta')
        resp = self.client.post(url, {'old_password': 'Temporal-2026', 'new_password1': 'Mi-Propia-Clave-26',
                                      'new_password2': 'Mi-Propia-Clave-26'})
        self.assertRedirects(resp, reverse('operaciones:inicio'), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse('operaciones:inicio')).status_code, 200)

        # Si el administrador le pone otra contraseña, vuelve a ser temporal
        juan = User.objects.get(username='juanp')
        self.client.force_login(admin)
        self.assertNotContains(self.client.get(reverse('operaciones:usuarios')), 'Contraseña temporal')
        self.client.post(reverse('operaciones:usuario_editar', args=[juan.pk]), {
            'first_name': 'Juan', 'last_name': '', 'email': '', 'is_active': 'on',
            'nueva_contrasena': 'Otra-Temporal-26', 'confirmar_contrasena': 'Otra-Temporal-26'})
        juan.refresh_from_db()
        self.client.force_login(juan)
        self.assertRedirects(self.client.get(reverse('operaciones:inicio')), reverse('operaciones:mi_contrasena'))

        # La que el administrador se pone a sí mismo no es temporal
        self.client.force_login(admin)
        self.client.post(reverse('operaciones:usuario_editar', args=[admin.pk]), {
            'first_name': '', 'last_name': '', 'email': '',
            'nueva_contrasena': 'Admin-Nueva-2026', 'confirmar_contrasena': 'Admin-Nueva-2026'})
        self.assertEqual(self.client.get(reverse('operaciones:inicio')).status_code, 200)

    def test_contrasenas_cortas_y_simples(self):
        url = reverse('operaciones:mi_contrasena')
        resp = self.client.post(url, {'old_password': 'clave-de-prueba-123', 'new_password1': 'abc',
                                      'new_password2': 'abc'})
        self.assertContains(resp, 'campo-error')   # menos de 4 caracteres
        for nueva in ('juan', '1234', 'armandol'):
            resp = self.client.post(url, {'old_password': getattr(self, '_clave', 'clave-de-prueba-123'),
                                          'new_password1': nueva, 'new_password2': nueva})
            self.assertRedirects(resp, reverse('operaciones:inicio'), fetch_redirect_response=False)
            self._clave = nueva

    def test_flujo_completo_envia_el_reporte_por_correo(self):
        recibidos = {}

        def analizar_falso(archivos, pedimento):
            recibidos.update(n=len(archivos), pedimento=pedimento.nombre)
            return {**RESULTADO, 'meta': {'modelo': 'claude-opus-5-5'}}

        with mock.patch.object(trabajos, 'analizar', side_effect=analizar_falso) as analizar:
            resp = self._enviar(pedimento='0')
        self.assertEqual(resp.json(), {'correo': 'armandol@multiservicios.mx'})
        self.assertEqual(recibidos, {'n': 3, 'pedimento': '1698-510-6000855-N.pdf'})
        # Al terminar, los documentos subidos se liberan de la memoria.
        self.assertEqual(analizar.call_args.args[0], [])

        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertEqual(correo.to, ['armandol@multiservicios.mx'])
        self.assertIn('26 51 1698 6000855', correo.subject)
        self.assertIn('2 hallazgos', correo.subject)
        self.assertIn('1 alta, 1 baja', correo.body)
        self.assertIn('FAC.pdf', correo.body)
        self.assertIn('claude-opus-5-5', correo.body)
        self.assertIn('riesgo de valor (art. 165): pasa', correo.body)
        self.assertIn('• CSF del mes en curso', correo.body)
        nombre, contenido, tipo = correo.attachments[0]
        self.assertEqual((nombre, tipo), ('Glosa_265116986000855.pdf', 'application/pdf'))
        self.assertTrue(contenido.startswith(b'%PDF'))

    def test_si_falla_el_analisis_se_avisa_por_correo(self):
        with mock.patch.object(trabajos, 'analizar', side_effect=ErrorAnalisis('Uno de los PDF no se pudo leer')):
            resp = self._enviar()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('No se pudo generar', mail.outbox[0].subject)
        self.assertIn('Uno de los PDF no se pudo leer', mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].attachments, [])

    def test_error_inesperado_tambien_se_avisa(self):
        with mock.patch.object(trabajos, 'analizar', side_effect=RuntimeError('algo raro')):
            self._enviar()
        self.assertIn('Error inesperado: algo raro', mail.outbox[0].body)

    def test_usuario_obligatorio_y_solo_del_dominio(self):
        for usuario in ['', 'juan@gmail.com', 'con espacio', '@multiservicios.mx']:
            with self.subTest(usuario=usuario):
                resp = self._enviar(usuario=usuario)
                self.assertEqual(resp.status_code, 400)
        self.assertEqual(mail.outbox, [])

    def test_acepta_usuario_con_dominio_y_mayusculas(self):
        with mock.patch.object(trabajos, 'analizar', return_value=dict(RESULTADO)):
            resp = self._enviar(usuario='  ArmandoL@Multiservicios.MX ')
        self.assertEqual(resp.json()['correo'], 'armandol@multiservicios.mx')

    @override_settings(CORREO_CONFIGURADO=False)
    def test_sin_correo_configurado_no_acepta_analisis(self):
        with mock.patch.object(trabajos, 'analizar') as analizar:
            resp = self._enviar()
        self.assertEqual(resp.status_code, 503)
        self.assertIn('CORREO_SMTP_HOST', resp.json()['error'])
        analizar.assert_not_called()

    def test_rechaza_extension_no_permitida(self):
        resp = self._enviar(archivos=[SimpleUploadedFile('virus.exe', b'x'),
                                      SimpleUploadedFile('FAC.pdf', PDF_MINIMO)])
        self.assertEqual(resp.status_code, 400)
        self.assertIn('virus.exe', resp.json()['error'])

    def test_acepta_un_solo_archivo_con_todo_el_expediente(self):
        with mock.patch.object(trabajos, 'analizar', return_value=dict(RESULTADO)) as analizar:
            resp = self._enviar(archivos=[SimpleUploadedFile('expediente.pdf', PDF_MINIMO)])
        self.assertEqual(resp.status_code, 200)
        analizar.assert_called_once()
        self.assertEqual(len(mail.outbox), 1)

    def test_requiere_al_menos_un_archivo(self):
        resp = self.client.post(reverse('operaciones:analizar'), {'usuario': 'armandol'})
        self.assertEqual(resp.status_code, 400)

    def test_rechaza_archivos_demasiado_grandes(self):
        grande = b'%PDF' + b'0' * (analizador.TAMANO_MAXIMO_MB * 1024 * 1024)
        resp = self._enviar(archivos=[SimpleUploadedFile('grande.pdf', grande)])
        self.assertEqual(resp.status_code, 400)
        self.assertIn('MB', resp.json()['error'])

    def test_comando_probar_correo(self):
        from io import StringIO

        from django.core.management import call_command
        salida = StringIO()
        call_command('probar_correo', 'ArmandoL', stdout=salida)
        self.assertEqual(mail.outbox[-1].to, ['armandol@multiservicios.mx'])
        self.assertIn('Enviado', salida.getvalue())

    def test_error_real_de_api_llega_por_correo(self):
        with mock.patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}, clear=False):
            self._enviar()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('No se pudo generar', mail.outbox[0].subject)

    def test_detecta_pedimento_por_texto(self):
        archivos = [Archivo('fac.pdf', pdf_con_texto('COMMERCIAL INVOICE')),
                    Archivo('x.pdf', pdf_con_texto('PEDIMENTO  CUADRO DE LIQUIDACION'))]
        self.assertIs(detectar_pedimento(archivos), archivos[1])
        self.assertIsNone(detectar_pedimento(archivos[:1]))

    def test_detecta_pedimento_que_no_esta_en_la_primera_pagina(self):
        combinado = Archivo('expediente.pdf', pdf_con_texto('COMMERCIAL INVOICE',
                                                            'PEDIMENTO  CUADRO DE LIQUIDACION'))
        otro = Archivo('bl.pdf', pdf_con_texto('BILL OF LADING'))
        self.assertIs(detectar_pedimento([otro, combinado]), combinado)

    def test_contenido_con_un_solo_archivo(self):
        contenido = construir_contenido([Archivo('expediente.pdf', PDF_MINIMO)])
        self.assertEqual([type(b) for b in contenido], [Texto, Documento, Texto])
        self.assertIn('EXPEDIENTE COMPLETO', contenido[0].texto)
        self.assertIn('único archivo contiene el pedimento', contenido[-1].texto)

    def test_contenido_del_mensaje(self):
        ped = Archivo('ped.pdf', PDF_MINIMO)
        archivos = [Archivo('FAC.pdf', PDF_MINIMO), ped, Archivo('COVE.xml', b'<cove/>')]
        contenido = construir_contenido(archivos, ped)
        self.assertEqual([type(b) for b in contenido],
                         [Texto, Documento, Texto, Documento, Texto, Documento, Texto])
        self.assertIn('PEDIMENTO (archivo: ped.pdf)', contenido[0].texto)
        self.assertEqual([d.mime for d in contenido if isinstance(d, Documento)],
                         ['application/pdf', 'application/pdf', 'text/plain'])
        self.assertIn('tipo de cambio', contenido[-1].texto)

        sin_pedimento = construir_contenido(archivos)
        self.assertIn('identifícalo', sin_pedimento[-1].texto)

    def test_reporte_pdf(self):
        pdf = generar_reporte(RESULTADO)
        self.assertTrue(pdf.startswith(b'%PDF'))
        texto = '\n'.join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)
        self.assertIn('Lista de verificación', texto)
        self.assertIn('Discrepancia', texto)

    def test_riesgo_de_valor_coincide_con_la_tabla_del_formato(self):
        tabla = {f['tasa']: f for f in control_riesgos.tabla_valor()}
        # Valores del formato en papel (importe máximo $374,610, IVA+DTA 16.93 %, referencia 35 %).
        for tasa, valor in [(0, 721374.93), (5, 798231.41), (10, 893417.60), (15, 1014378.55),
                            (20, 1173222.67), (25, 1391050.87), (30, 1708207.93)]:
            self.assertAlmostEqual(tabla[tasa]['valor_maximo'], valor, delta=1)

    def test_riesgo_de_valor_por_partida(self):
        rv = RESULTADO['control_riesgos']['riesgo_valor']
        # 500,000 × (16.93 % + 10 %) + 450,000 × (16.93 % + 35 %) = 134,650 + 233,685
        self.assertAlmostEqual(rv['omision'], 368335, delta=0.01)
        self.assertTrue(rv['pasa'])
        self.assertEqual(rv['tasas'], [0, 25])
        no_pasa = control_riesgos.calcular_riesgo_valor(
            [{'partida': '1', 'fraccion': 'x', 'tasa_igi': 0, 'valor_aduana': 721400}])
        self.assertFalse(no_pasa['pasa'])
        sin_datos = control_riesgos.calcular_riesgo_valor([{'tasa_igi': None, 'valor_aduana': 'abc'}])
        self.assertFalse(sin_datos['evaluado'])
        self.assertIsNone(sin_datos['pasa'])

    @override_settings(RIESGO_IMPORTE_MAXIMO_OMISION=100000)
    def test_importe_maximo_configurable(self):
        rv = control_riesgos.calcular_riesgo_valor(
            [{'partida': '1', 'fraccion': 'x', 'tasa_igi': 0, 'valor_aduana': 200000}])
        self.assertFalse(rv['pasa'])
        self.assertEqual(rv['importe_maximo'], 100000)

    def test_control_de_riesgos_normaliza_las_respuestas(self):
        respuestas = RESULTADO['control_riesgos']['respuestas']
        self.assertEqual([r['pregunta'] for r in respuestas], control_riesgos.IDS_PREGUNTAS)
        por_id = {r['pregunta']: r for r in respuestas}
        self.assertEqual(por_id['nom_etiquetado']['respuesta'], 'si')
        self.assertEqual(por_id['contrato']['respuesta'], 'no_verificable')
        vacio = control_riesgos.normalizar(None)
        self.assertEqual(len(vacio['respuestas']), len(control_riesgos.IDS_PREGUNTAS))
        self.assertFalse(vacio['riesgo_valor']['evaluado'])

    def test_reporte_incluye_la_hoja_de_control_de_riesgos(self):
        lector = PdfReader(BytesIO(generar_reporte(RESULTADO)))
        ultima = '\n'.join(p.extract_text() for p in lector.pages[1:])
        self.assertIn('REVISION DE CONTROL DE RIESGOS DEL EMBARQUE', ultima)
        self.assertIn('SI Pasa', ultima)
        self.assertIn('NOM-004-SE-2021', ultima)
        self.assertIn('CSF del mes en curso', ultima)
        self.assertIn('721,374.93', ultima)
        sin_hoja = {k: v for k, v in RESULTADO.items() if k != 'control_riesgos'}
        texto = '\n'.join(p.extract_text() for p in PdfReader(BytesIO(generar_reporte(sin_hoja))).pages)
        self.assertNotIn('CONTROL DE RIESGOS', texto)

    def test_prompt_y_esquema_cubren_el_control_de_riesgos(self):
        for id_ in control_riesgos.IDS_PREGUNTAS:
            self.assertIn(f'[{id_}]', SYSTEM_PROMPT)
        props = ESQUEMA_RESULTADO['properties']['control_riesgos']['properties']
        self.assertEqual(props['respuestas']['items']['properties']['pregunta']['enum'],
                         control_riesgos.IDS_PREGUNTAS)
        self.assertIn('control_riesgos', ESQUEMA_RESULTADO['required'])
        self.assertIn('Fecha de hoy', construir_contenido([Archivo('e.pdf', PDF_MINIMO)])[-1].texto)

    def test_prompt_y_esquema_cubren_la_lista(self):
        for id_, titulo, _ in LISTA_VERIFICACION:
            self.assertIn(f'[{id_}] {titulo}', SYSTEM_PROMPT)
        props = ESQUEMA_RESULTADO['properties']
        self.assertEqual(props['lista_verificacion']['items']['properties']['punto']['enum'],
                         IDS_VERIFICACION)
        self.assertEqual(props['hallazgos']['items']['properties']['punto']['enum'],
                         IDS_VERIFICACION)
        self.assertIn('CRITERIOS DE SEVERIDAD', SYSTEM_PROMPT)

    def test_reintenta_si_la_api_se_satura_a_mitad_del_stream(self):
        import anthropic
        import httpx2

        from .services.proveedores import claude

        respuesta_http = httpx2.Response(200, request=httpx2.Request('POST', 'https://api.anthropic.com'))
        saturada = anthropic.APIStatusError(
            'Overloaded', response=respuesta_http,
            body={'type': 'error', 'error': {'type': 'overloaded_error', 'message': 'Overloaded'}})
        final = mock.Mock(name='mensaje')
        stream_ok = mock.MagicMock()
        stream_ok.__enter__.return_value.get_final_message.return_value = final
        stream_falla = mock.MagicMock()
        stream_falla.__enter__.return_value.get_final_message.side_effect = saturada
        client = mock.Mock()
        client.beta.messages.stream.side_effect = [stream_falla, stream_ok]

        proveedor = claude.Claude('claude-opus-5-5', 'high')
        with mock.patch.object(claude, 'ESPERAS_REINTENTO', [0]):
            self.assertIs(proveedor._solicitar(client, 'sistema', [], {}), final)
        self.assertEqual(client.beta.messages.stream.call_count, 2)

        client.beta.messages.stream.side_effect = [stream_falla, stream_falla]
        with mock.patch.object(claude, 'ESPERAS_REINTENTO', [0]):
            with self.assertRaises(anthropic.APIStatusError):
                proveedor._solicitar(client, 'sistema', [], {})

    def test_normalizar_lista(self):
        lista = normalizar_lista([
            {'punto': 'totales', 'resultado': 'coincide', 'detalle': 'a'},
            {'punto': 'importador', 'resultado': 'coincide', 'detalle': 'b'},
            {'punto': 'importador', 'resultado': 'discrepancia', 'detalle': 'duplicado'},
        ])
        self.assertEqual([i['punto'] for i in lista], IDS_VERIFICACION)
        self.assertEqual(lista[0]['detalle'], 'b')
        faltantes = [i for i in lista if i['punto'] not in ('totales', 'importador')]
        self.assertTrue(all(i['resultado'] == 'no_verificable' for i in faltantes))


class ProveedorFalso(Proveedor):
    nombre = 'falso'

    def __init__(self, json_respuesta):
        super().__init__('modelo-falso', 'high')
        self.json_respuesta = json_respuesta
        self.recibido = None

    def generar_json(self, system, partes, esquema):
        self.recibido = (system, partes, esquema)
        return Respuesta(self.json_respuesta, 'modelo-falso-v1', 10, 20)


class ProveedoresTests(TestCase):
    def test_analizar_usa_el_proveedor_y_registra_meta(self):
        proveedor = ProveedorFalso(json.dumps({**RESULTADO, 'lista_verificacion': []}))
        resultado = analizador.analizar([Archivo('expediente.pdf', PDF_MINIMO)], proveedor=proveedor)
        system, partes, esquema = proveedor.recibido
        self.assertIs(system, analizador.SYSTEM_PROMPT)
        self.assertIs(esquema, analizador.ESQUEMA_RESULTADO)
        self.assertIsInstance(partes[1], Documento)
        self.assertEqual(resultado['meta'], {'proveedor': 'falso', 'modelo': 'modelo-falso-v1',
                                             'tokens_entrada': 10, 'tokens_salida': 20})
        self.assertEqual(len(resultado['lista_verificacion']), len(IDS_VERIFICACION))

    def test_json_invalido_da_error_claro(self):
        with self.assertRaises(ErrorAnalisis):
            analizador.analizar([Archivo('a.pdf', PDF_MINIMO)], proveedor=ProveedorFalso('no es json'))

    @override_settings(IA_PROVEEDOR='anthropic', IA_MODELO='',
                       IA_MODELOS={'anthropic': 'claude-x', 'gemini': 'gemini-x', 'openai': 'gpt-x'})
    def test_seleccion_de_proveedor_y_modelo(self):
        p = obtener_proveedor()
        self.assertEqual((p.nombre, p.modelo), ('anthropic', 'claude-x'))
        self.assertEqual(obtener_proveedor('gemini').modelo, 'gemini-x')
        self.assertEqual(obtener_proveedor('openai', 'gpt-otro').modelo, 'gpt-otro')
        with self.settings(IA_PROVEEDOR='openai', IA_MODELO='gpt-desde-env'):
            p = obtener_proveedor()
            self.assertEqual((p.nombre, p.modelo), ('openai', 'gpt-desde-env'))
        with self.assertRaises(ErrorAnalisis):
            obtener_proveedor('desconocido')

    def test_reintenta_si_se_corta_la_conexion_a_mitad_del_stream(self):
        import httpx2

        from .services.proveedores import claude

        final = mock.Mock(name='mensaje')
        stream_ok = mock.MagicMock()
        stream_ok.__enter__.return_value.get_final_message.return_value = final
        stream_cortado = mock.MagicMock()
        stream_cortado.__enter__.return_value.get_final_message.side_effect = \
            httpx2.RemoteProtocolError('peer closed connection without sending complete message body')
        client = mock.Mock()
        client.beta.messages.stream.side_effect = [stream_cortado, stream_ok]
        with mock.patch.object(claude, 'ESPERAS_REINTENTO', [0]):
            self.assertIs(claude.Claude('claude-opus-5-5', 'high')._solicitar(client, 's', [], {}), final)

        # Si se agotan los reintentos, el usuario ve un mensaje claro, no "Error inesperado".
        with mock.patch.object(claude.anthropic, 'Anthropic') as Anthropic, \
                mock.patch.object(claude, 'ESPERAS_REINTENTO', []):
            Anthropic.return_value.beta.messages.stream.return_value = stream_cortado
            with self.assertRaisesRegex(ErrorAnalisis, 'conexión'):
                claude.Claude('claude-opus-5-5', 'high').generar_json('s', [Texto('x')], {})

    def test_opciones_de_claude_segun_el_modelo(self):
        from .services.proveedores.claude import Claude
        esquema = {'type': 'object'}

        opus55 = Claude('claude-opus-5-5', 'xhigh')._opciones_modelo(esquema)
        self.assertEqual(opus55['output_config']['effort'], 'xhigh')
        self.assertNotIn('thinking', opus55)

        sonnet46 = Claude('claude-sonnet-4-6', 'xhigh')._opciones_modelo(esquema)
        self.assertEqual(sonnet46['output_config']['effort'], 'high')
        self.assertEqual(sonnet46['thinking'], {'type': 'adaptive'})
        self.assertEqual(sonnet46['output_config']['format']['schema'], esquema)

        opus48 = Claude('claude-opus-4-8', 'xhigh')._opciones_modelo(esquema)
        self.assertEqual(opus48['output_config']['effort'], 'xhigh')
        self.assertEqual(opus48['thinking'], {'type': 'adaptive'})

        haiku45 = Claude('claude-haiku-4-5', 'high')._opciones_modelo(esquema)
        self.assertNotIn('effort', haiku45['output_config'])
        self.assertNotIn('thinking', haiku45)
        self.assertEqual(haiku45['max_tokens'], 64000)
        self.assertEqual(sonnet46['max_tokens'], 128000)

    def test_partes_de_gemini(self):
        from .services.proveedores import gemini
        pdf = gemini._parte(Documento('a.pdf', PDF_MINIMO, 'application/pdf'))
        self.assertEqual(pdf.inline_data.mime_type, 'application/pdf')
        xml = gemini._parte(Documento('cove.xml', b'<cove/>', 'text/plain'))
        self.assertIn('<cove/>', xml.text)
        self.assertEqual(gemini._parte(Texto('hola')).text, 'hola')

    def test_partes_de_openai(self):
        from .services.proveedores import openai_gpt
        pdf = openai_gpt._parte(Documento('a.pdf', PDF_MINIMO, 'application/pdf'))
        self.assertEqual(pdf['type'], 'input_file')
        self.assertTrue(pdf['file_data'].startswith('data:application/pdf;base64,'))
        img = openai_gpt._parte(Documento('a.png', b'png', 'image/png'))
        self.assertTrue(img['image_url'].startswith('data:image/png;base64,'))
        self.assertEqual(openai_gpt._parte(Texto('hola')), {'type': 'input_text', 'text': 'hola'})

    @override_settings(GEMINI_API_KEY='')
    def test_gemini_sin_llave(self):
        with self.assertRaisesRegex(ErrorAnalisis, 'GEMINI_API_KEY'):
            obtener_proveedor('gemini').generar_json('s', [Texto('x')], {})

    @override_settings(OPENAI_API_KEY='')
    def test_openai_sin_llave(self):
        with self.assertRaisesRegex(ErrorAnalisis, 'OPENAI_API_KEY'):
            obtener_proveedor('openai').generar_json('s', [Texto('x')], {})

    @override_settings(GEMINI_API_KEY='llave-de-prueba')
    def test_gemini_envia_esquema_y_lee_respuesta(self):
        from .services.proveedores import gemini
        respuesta = mock.Mock(text='{"ok": true}', model_version='gemini-x-001',
                              candidates=[mock.Mock(finish_reason=mock.Mock(name_='STOP'))])
        respuesta.candidates[0].finish_reason.name = 'STOP'
        respuesta.usage_metadata = mock.Mock(prompt_token_count=100, candidates_token_count=30,
                                             thoughts_token_count=20)
        with mock.patch.object(gemini.genai, 'Client') as Client:
            Client.return_value.models.generate_content.return_value = respuesta
            r = obtener_proveedor('gemini', 'gemini-x').generar_json('sistema', [Texto('hola')], {'type': 'object'})
        kwargs = Client.return_value.models.generate_content.call_args.kwargs
        self.assertEqual(kwargs['model'], 'gemini-x')
        self.assertEqual(kwargs['config'].response_json_schema, {'type': 'object'})
        self.assertEqual(kwargs['config'].system_instruction, 'sistema')
        self.assertEqual((r.json, r.modelo, r.tokens_entrada, r.tokens_salida),
                         ('{"ok": true}', 'gemini-x-001', 100, 50))

    @override_settings(OPENAI_API_KEY='llave-de-prueba', IA_ESFUERZO='medium')
    def test_openai_envia_esquema_y_lee_respuesta(self):
        from .services.proveedores import openai_gpt
        respuesta = mock.Mock(status='completed', output_text='{"ok": true}', model='gpt-x-2026',
                              output=[], usage=mock.Mock(input_tokens=100, output_tokens=40))
        with mock.patch.object(openai_gpt.openai, 'OpenAI') as OpenAI:
            OpenAI.return_value.responses.create.return_value = respuesta
            r = obtener_proveedor('openai', 'gpt-x').generar_json('sistema', [Texto('hola')], {'type': 'object'})
        kwargs = OpenAI.return_value.responses.create.call_args.kwargs
        self.assertEqual(kwargs['model'], 'gpt-x')
        self.assertEqual(kwargs['instructions'], 'sistema')
        self.assertEqual(kwargs['reasoning'], {'effort': 'medium'})
        self.assertEqual(kwargs['text']['format']['schema'], {'type': 'object'})
        self.assertTrue(kwargs['text']['format']['strict'])
        self.assertEqual((r.json, r.modelo, r.tokens_salida), ('{"ok": true}', 'gpt-x-2026', 40))
