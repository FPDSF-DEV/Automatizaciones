@echo off
title SIHO - Descarga de datos
cd /d "%~dp0"
echo Iniciando la aplicacion SIHO...
echo Se abrira el navegador en http://localhost:5000
echo (Deje esta ventana abierta mientras usa la aplicacion)
echo.
python app.py
pause
