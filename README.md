# Segunda Glosa

Aplicación Django para la segunda glosa de pedimentos. Sueltas el pedimento y la documentación con
la que se elaboró (factura, BL, COVE, certificados de origen, etc.). Un modelo de IA (Claude,
Gemini u OpenAI, a elegir) busca inconsistencias y el reporte PDF con los hallazgos llega por correo.

## Cómo funciona

0. Inicias sesión con tu usuario y contraseña. Las cuentas las crea un administrador en
   la sección **Usuarios** (ver "Usuarios" en INSTALACION.md). Cada quien puede cambiar su
   contraseña haciendo clic en su nombre, arriba a la derecha. La sesión dura 10 horas y se cierra al cerrar el
   navegador.
1. En la página principal arrastras los documentos a la zona de carga, o haces clic para elegirlos.
   Se aceptan PDF (incluso escaneados), imágenes JPG/PNG y XML/TXT, hasta 22 MB en total.
   También puedes subir **un solo PDF con todo el expediente** (pedimento y documentos juntos):
   el modelo separa cada documento por páginas.
2. Marcas cuál archivo es el pedimento. Si el nombre tiene la forma patente-aduana-número
   (p. ej. `1698-510-6000855-N.pdf`) o contiene la palabra "pedimento", se marca solo.
   Si no marcas ninguno, el servidor lo busca por su texto y, como último recurso, el modelo lo
   identifica.
3. El reporte se envía a tu correo: el campo viene lleno con el correo de tu cuenta (o con tu
   usuario, si coincide con el de tu correo, p. ej. `armandol` → `armandol@multiservicios.mx`).
   Puedes cambiarlo para enviarlo a otra persona, pero solo a cuentas del dominio de la empresa.
4. **Analizar y Enviar por Correo**. La página confirma de inmediato y ya la puedes cerrar o
   subir otra operación. El análisis corre en segundo plano en el servidor: los archivos se envían
   al proveedor configurado como documentos nativos (el modelo lee el texto y la imagen de cada
   página, así que no hace falta OCR).
5. Al terminar (suele tardar de 3 a 5 minutos) te llega un correo con el resumen y el PDF adjunto.
   Si algo falla, te llega un correo con el motivo.

No se guarda nada en disco: los documentos y el PDF solo existen en memoria mientras dura el
análisis y el envío. Si reinicias el servidor a mitad de un análisis, ese análisis se pierde y no
llega ningún correo.

## Instalación

```bash
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env      # coloca tu ANTHROPIC_API_KEY y DJANGO_DEBUG=1
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py createsuperuser   # primer administrador
.venv\Scripts\python manage.py runserver
```

Abre http://127.0.0.1:8000/

## Cambiar de proveedor o de modelo

Todo está en un bloque de `config/settings.py` (sección "PROVEEDOR Y MODELO DE IA"):

```python
IA_PROVEEDOR = os.environ.get('IA_PROVEEDOR', 'anthropic')   # anthropic | gemini | openai

IA_MODELOS = {
    'anthropic': 'claude-opus-5-5',
    'gemini': 'gemini-4-argon',
    'openai': 'gpt-6-astra',
}
```

- **Cambiar de proveedor:** cambia `'anthropic'` por `'gemini'` u `'openai'` y agrega su llave en
  `.env` (`GEMINI_API_KEY` u `OPENAI_API_KEY`).
- **Cambiar de modelo:** edita la línea de ese proveedor en `IA_MODELOS`.
- **Sin tocar el código:** en `.env` pon `IA_PROVEEDOR=gemini` y, si quieres, `IA_MODELO=...`.

Reinicia `iniciar.bat` después de cualquier cambio. El PDF indica con qué modelo se hizo el
análisis. Las instrucciones, la lista de verificación y el formato del reporte son los mismos para
todos los proveedores, pero la calidad de los hallazgos puede variar entre modelos.

Para agregar otro proveedor: crea un archivo en `operaciones/services/proveedores/` con una clase
que herede de `Proveedor` e implemente `generar_json`, y regístralo en `PROVEEDORES`
(`proveedores/__init__.py`).

## Estructura

| Archivo | Qué hace |
|---|---|
| `operaciones/services/analizador.py` | Prompt de glosa, esquema JSON de salida, detección del pedimento y armado del mensaje |
| `operaciones/services/criterios.py` | Lista de verificación, criterios de severidad y tolerancias |
| `operaciones/services/proveedores/` | Un archivo por proveedor de IA (`claude.py`, `gemini.py`, `openai_gpt.py`) |
| `operaciones/services/reporte.py` | Generación del PDF de hallazgos |
| `operaciones/services/trabajos.py` | Ejecuta el análisis en segundo plano y envía el resultado por correo |
| `operaciones/services/correo.py` | Valida el usuario y arma los correos (reporte o aviso de error) |
| `operaciones/usuarios.py`, `operaciones/forms.py` | Administración de usuarios y cambio de la propia contraseña |
| `operaciones/templates/operaciones/base.html` | Encabezado y estilos comunes a todas las páginas |
| `operaciones/views.py` | Página de carga y recepción de los documentos |
| `operaciones/templates/operaciones/inicio.html` | Interfaz drag & drop |

## Configuración (`.env`)

- `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY` — solo la del proveedor que uses.
- `ANTHROPIC_WORKSPACE_ID` — solo si la llave de Anthropic no está ligada a un workspace.
- `IA_PROVEEDOR`, `IA_MODELO` — opcionales; sobreescriben lo de `config/settings.py`.
- `IA_ESFUERZO` — `low` | `medium` | `high` (defecto) | `xhigh` | `max` (Claude y OpenAI). Más alto =
  revisión más exhaustiva, más lenta y más costosa.
- `CORREO_SMTP_HOST`, `CORREO_SMTP_PUERTO`, `CORREO_SMTP_SEGURIDAD`, `CORREO_SMTP_USUARIO`,
  `CORREO_SMTP_CONTRASENA`, `CORREO_REMITENTE`, `CORREO_DOMINIO` — servidor de correo saliente.
  Sin `CORREO_SMTP_HOST` la página no acepta análisis. Con `CORREO_SMTP_HOST=consola` los correos
  se imprimen en la ventana del servidor (solo para pruebas).

## Pruebas

```bash
.venv\Scripts\python manage.py test operaciones
```

## Notas para producción

Los pasos para instalarlo y dejarlo corriendo en una PC con Windows están en
[INSTALACION.md](INSTALACION.md). Se arranca con `iniciar.bat` (waitress, puerto 8020).

- Los análisis se guardan en la memoria de un solo proceso (waitress con varios hilos). Para
  varios servidores habría que pasar a Redis o a una base de datos.
- `DJANGO_DEBUG`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` y
  `DJANGO_HTTPS` se configuran en `.env` (ver `.env.example`).
- Agregar autenticación: hoy cualquiera con acceso a la página puede generar análisis.
