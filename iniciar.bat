@echo off
rem Inicia GlosaAI con waitress (servidor de produccion para Windows).
rem Doble clic para arrancar; cierra esta ventana para detenerlo.

rem 0.0.0.0 = accesible desde otras computadoras de la red (por cualquier IP de esta PC,
rem p. ej. http://10.99.0.5:8020/); 127.0.0.1 = solo esta PC.
set HOST=0.0.0.0
set PUERTO=8020

cd /d "%~dp0"

rem Para cambiar la IP o el puerto no edites este archivo (se reemplaza al actualizar):
rem pon SERVIDOR_HOST=... y/o SERVIDOR_PUERTO=... en el .env
if exist ".env" (
    for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do (
        if /i "%%a"=="SERVIDOR_HOST" set HOST=%%b
        if /i "%%a"=="SERVIDOR_PUERTO" set PUERTO=%%b
    )
)

rem El entorno virtual puede llamarse .venv o venv.
set PYTHON=
if exist ".venv\Scripts\python.exe" set PYTHON=.venv\Scripts\python.exe
if not defined PYTHON if exist "venv\Scripts\python.exe" set PYTHON=venv\Scripts\python.exe
if not defined PYTHON (
    echo No se encontro el entorno virtual ^(.venv o venv^) en %CD%
    echo Crealo con:  python -m venv .venv
    echo y luego:     .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

echo GlosaAI en http://localhost:%PUERTO%/
echo (desde otra PC de la red: http://IP-DE-ESTA-PC:%PUERTO%/)
echo Cierra esta ventana para detener el servidor.
echo.
"%PYTHON%" -m waitress --listen=%HOST%:%PUERTO% --threads=8 --channel-timeout=300 config.wsgi:application
pause
