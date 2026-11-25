@echo off
rem Descarga la version mas reciente desde GitHub, instala dependencias y actualiza la base de datos.
rem No toca .env, db.sqlite3 ni el entorno virtual. Uso: doble clic, o "actualizar.bat" en la consola.

cd /d "%~dp0"

set PY=.venv\Scripts\python.exe
if not exist "%PY%" set PY=venv\Scripts\python.exe
if not exist "%PY%" (
    echo No encuentro el entorno virtual ^(.venv o venv^) en "%CD%".
    pause
    exit /b 1
)

echo.
echo === 1/3 Descargando la version nueva ===
git pull --ff-only
if errorlevel 1 (
    echo.
    echo No se pudo descargar. Si dice que hay cambios locales, alguien edito archivos en el
    echo servidor: avisa a quien mantiene el proyecto antes de continuar.
    pause
    exit /b 1
)

echo.
echo === 2/3 Instalando dependencias ===
"%PY%" -m pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 (
    echo.
    echo Fallo la instalacion de dependencias. Revisa el mensaje de arriba.
    pause
    exit /b 1
)

echo.
echo === 3/3 Actualizando la base de datos ===
"%PY%" manage.py migrate
if errorlevel 1 (
    echo.
    echo Fallo la migracion. Revisa el mensaje de arriba.
    pause
    exit /b 1
)

echo.
echo Listo. Cierra la ventana del servidor y vuelve a abrirlo para usar la version nueva.
pause
