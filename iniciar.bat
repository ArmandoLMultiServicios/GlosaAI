@echo off
rem Inicia Segunda Glosa con waitress (servidor de produccion para Windows).
rem Doble clic para arrancar; cierra esta ventana para detenerlo.

rem 0.0.0.0 = accesible desde otras computadoras de la red; 127.0.0.1 = solo esta PC.
set HOST=0.0.0.0
set PUERTO=8020

cd /d "%~dp0"
echo Segunda Glosa en http://localhost:%PUERTO%/
echo (desde otra PC de la red: http://IP-DE-ESTA-PC:%PUERTO%/)
echo Cierra esta ventana para detener el servidor.
echo.
".venv\Scripts\python.exe" -m waitress --listen=%HOST%:%PUERTO% --threads=8 --channel-timeout=300 config.wsgi:application
pause
