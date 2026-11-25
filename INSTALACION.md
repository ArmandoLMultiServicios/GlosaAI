# Instalación local en Windows

La app corre en una PC con Windows usando **waitress**, un servidor de producción que funciona en
Windows. Se puede usar solo en esa PC o desde otras computadoras de la misma red.

Requisito: **Python 3.12 o superior** (https://www.python.org/downloads/). Durante la instalación
marca "Add python.exe to PATH".

---

## 1. Copiar el proyecto a la PC

Copia la carpeta `Segunda Glosa` a la PC donde va a correr (USB, carpeta compartida, etc.).
**No copies** la carpeta `.venv` ni `db.sqlite3`; se crean en el paso siguiente. Si es la misma
PC donde ya lo tienes, salta al paso 3.

Para empaquetarla sin esas carpetas, desde PowerShell en la PC de origen:

```powershell
cd "C:\Users\ArmandoL\Documents\GitHub\Segunda Glosa"
tar -czf segunda-glosa.tgz --exclude=.venv --exclude=__pycache__ --exclude=media --exclude=staticfiles --exclude=db.sqlite3 --exclude=.env --exclude=*.pdf --exclude=.claude .
```

Y en la PC destino, dentro de la carpeta donde quieras el proyecto (p. ej. `C:\SegundaGlosa`):

```powershell
tar -xzf segunda-glosa.tgz
```

## 2. Crear el entorno e instalar dependencias (PowerShell, en la carpeta del proyecto)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## 3. Configurar `.env`

```powershell
copy .env.example .env
.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(50))"
notepad .env
```

Llena:

```
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_WORKSPACE_ID=wrkspc_...
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<lo que imprimió el segundo comando>
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
```

Si vas a usar Gemini u OpenAI en lugar de Claude, pon `GEMINI_API_KEY=...` u `OPENAI_API_KEY=...`
y `IA_PROVEEDOR=gemini` u `IA_PROVEEDOR=openai` (ver "Cambiar de proveedor o de modelo" en el
README).

### Correo saliente

El reporte se envía por correo, así que hace falta una cuenta que pueda enviar por SMTP (por
ejemplo `glosa@multiservicios.mx`). Agrega en `.env`:

```
CORREO_SMTP_HOST=smtp.office365.com
CORREO_SMTP_PUERTO=587
CORREO_SMTP_SEGURIDAD=tls
CORREO_SMTP_USUARIO=glosa@multiservicios.mx
CORREO_SMTP_CONTRASENA=<contraseña de la cuenta o de aplicación>
CORREO_REMITENTE=Segunda Glosa <glosa@multiservicios.mx>
```

| Si el correo de la empresa es… | `CORREO_SMTP_HOST` | Puerto | Notas |
|---|---|---|---|
| Microsoft 365 / Outlook | `smtp.office365.com` | 587 | La cuenta debe tener habilitado "SMTP autenticado" (lo activa el administrador de Microsoft 365) |
| Google Workspace / Gmail | `smtp.gmail.com` | 587 | Usa una "contraseña de aplicación", no la contraseña normal |
| Servidor propio / hosting | el que indique tu proveedor | 587 o 465 | Con 465 pon `CORREO_SMTP_SEGURIDAD=ssl` |

Para comprobar que la configuración funciona, sin hacer un análisis:

```powershell
.venv\Scripts\python manage.py probar_correo armandol
```

Envía un correo de prueba a `armandol@multiservicios.mx` o muestra el error exacto del servidor.

Para probar sin enviar correos reales: `CORREO_SMTP_HOST=consola`. Los correos aparecen en la
ventana de `iniciar.bat`.

## 4. Preparar Django

```powershell
.venv\Scripts\python manage.py check
.venv\Scripts\python manage.py migrate
```

## 5. Crear el primer administrador

```powershell
.venv\Scripts\python manage.py createsuperuser
```

Pide usuario, correo (opcional) y contraseña. Con esa cuenta entras a la app y a la sección
**Usuarios**, donde das de alta a los demás (ver "Usuarios" más abajo).

## 6. Arrancar

Doble clic en **`iniciar.bat`**, o desde PowerShell:

```powershell
.\iniciar.bat
```

Abre http://localhost:8020/. Para detenerlo, cierra la ventana negra.

---

## Usuarios

Toda la app pide iniciar sesión. Los administradores ven el enlace **Usuarios** en el
encabezado (http://localhost:8020/usuarios/):

- **Dar de alta a alguien:** *Agregar usuario* → usuario, nombre, apellido, correo, una
  **contraseña temporal** y el interruptor *Administrador* → *Crear usuario*. Pásale el usuario y
  la contraseña temporal; la primera vez que entre, la app le pide elegir su propia contraseña y
  no le deja usar nada más hasta hacerlo. Mientras no lo haga, en la lista aparece como
  "Contraseña temporal".
  Conviene que el usuario sea el mismo que su correo (`armandol` para
  `armandol@multiservicios.mx`). Si dejas el correo vacío, se llena solo con
  `usuario@multiservicios.mx`, y el reporte le llega sin escribir nada.
- **Modificar a alguien:** clic en su renglón. Ahí cambias sus datos, lo haces administrador o le
  quitas el acceso. Si olvidó su contraseña, ponle una nueva: también es temporal, y al entrar se
  le pide cambiarla.
- **Quitar el acceso sin borrar la cuenta:** apaga *Activo*. En la lista aparece como
  "Sin acceso" y puedes reactivarlo cuando quieras.
- **Eliminar:** botón *Eliminar usuario* en su ficha (pide confirmación; no se puede deshacer).
- Nadie puede quitarse a sí mismo el acceso o el rol de administrador, ni eliminar su propia
  cuenta, para que la app no se quede sin administradores por accidente.

Cada usuario puede cambiar su propia contraseña haciendo clic en su nombre, arriba a la derecha.

Si se pierde la contraseña del único administrador:

```powershell
.venv\Scripts\python manage.py changepassword <usuario>
```

Los usuarios viven en `db.sqlite3`. **No lo borres ni lo reemplaces al actualizar**: ahí están
todas las cuentas. Respáldalo de vez en cuando.

## Usarlo desde otras computadoras de la red (opcional)

1. Averigua la IP de la PC que corre la app:
   ```powershell
   ipconfig
   ```
   Busca "Dirección IPv4", por ejemplo `192.168.1.50`.
2. Agrégala en `.env`:
   ```
   DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.50
   ```
3. Permite el puerto 8020 en el firewall de Windows (PowerShell **como administrador**):
   ```powershell
   New-NetFirewallRule -DisplayName "Segunda Glosa" -Direction Inbound -Protocol TCP -LocalPort 8020 -Action Allow -Profile Private
   ```
4. Reinicia `iniciar.bat`. Desde las otras PCs abre `http://192.168.1.50:8020/`.

Conviene que esa PC tenga IP fija (pídelo a quien administra la red); si la IP cambia, hay que
actualizar `DJANGO_ALLOWED_HOSTS`.

## Que arranque solo al encender la PC (opcional)

PowerShell **como administrador**, en la carpeta del proyecto:

```powershell
schtasks /Create /TN "Segunda Glosa" /TR "\"$PWD\iniciar.bat\"" /SC ONLOGON /RL LIMITED
```

Arranca cuando inicias sesión. Para quitarlo:

```powershell
schtasks /Delete /TN "Segunda Glosa" /F
```

---

## Cambiar el puerto o el acceso

En `iniciar.bat`:

- `PUERTO=8020`: cámbialo si ese puerto está ocupado.
- `HOST=0.0.0.0`: acepta conexiones de la red. Usa `127.0.0.1` para que solo funcione en esa PC.

## Actualizar a una versión nueva

El código vive en un repositorio privado de GitHub. En el servidor se actualiza con un comando.

### En la PC de desarrollo, cada vez que haya cambios

```powershell
git add -A
git commit -m "Describe el cambio"
git push
```

### En el servidor

Doble clic en **`actualizar.bat`** (o `.ctualizar.bat` en PowerShell, en la carpeta del
proyecto). Descarga la versión nueva, instala dependencias y actualiza la base de datos. Luego
cierra la ventana del servidor y vuelve a abrirla.

`.env`, `db.sqlite3` (los usuarios) y `.venv` no se tocan: no están en GitHub.

### Preparar el servidor la primera vez

Requiere Git para Windows (https://git-scm.com/download/win). En PowerShell, dentro de la carpeta
del proyecto que ya está instalado:

```powershell
git init -b main
git remote add origin https://github.com/<cuenta>/segunda-glosa.git
git fetch origin
git reset --hard origin/main
git branch --set-upstream-to=origin/main main
```

`git reset --hard` reemplaza el código por el de GitHub. Los archivos que no están en GitHub
(`.env`, `db.sqlite3`, `.venv`, tu `.bat` de arranque) se quedan como están. La primera vez que
se conecte, Git pide iniciar sesión en GitHub en una ventana del navegador.

No edites el código directamente en el servidor: el siguiente `actualizar.bat` fallaría. Si algo
se debe configurar solo en el servidor (IP, llaves, correo), va en su `.env`.

## Problemas comunes

| Síntoma | Causa probable |
|---|---|
| La página manda siempre al login aunque la contraseña es correcta | La cuenta está inactiva, o se abrió con otra IP/nombre y el navegador bloquea la cookie: entra siempre con la misma dirección |
| "no such table: auth_user" al iniciar sesión | Falta `.venv\Scripts\python manage.py migrate` |
| `Bad Request (400)` | La IP o nombre con que abres la página no está en `DJANGO_ALLOWED_HOSTS` |
| La ventana se cierra con `Define DJANGO_SECRET_KEY` | Falta la clave secreta en `.env` |
| Otras PCs no abren la página | Firewall (paso 3 de la red) o `HOST=127.0.0.1` en `iniciar.bat` |
| `error while attempting to bind` | El puerto ya está ocupado: cambia `PUERTO` en `iniciar.bat` |
| "Se perdió el análisis" | Se cerró o reinició `iniciar.bat` a mitad de un análisis |
| "Falta configurar ANTHROPIC_API_KEY" o error 400 de workspace | Revisa la llave y `ANTHROPIC_WORKSPACE_ID` en `.env` |
| "El envío de correo no está configurado" | Falta `CORREO_SMTP_HOST` en `.env` |
| La página dice "Recibido" pero no llega el correo | Revisa la ventana de `iniciar.bat`: ahí aparece el error de SMTP (contraseña, SMTP autenticado deshabilitado, puerto bloqueado). Revisa también la carpeta de spam |
