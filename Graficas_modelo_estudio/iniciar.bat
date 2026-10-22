@echo off
rem Expansion retardada: dentro de un bloque if(...) cmd expande %VAR% al leer
rem el bloque, no al ejecutarlo, asi que las variables que se asignan y se usan
rem dentro del mismo bloque se escriben !VAR!.
setlocal enabledelayedexpansion

rem ---------------------------------------------------------------------------
rem  Generacion de graficas - arranque en un clic.
rem
rem  La primera vez crea el entorno virtual e instala las dependencias (tarda
rem  unos minutos). Las siguientes veces solo corre los modulos.
rem
rem  El entorno vive en .venv, dentro de esta misma carpeta, y no en la ruta de
rem  Python de la Microsoft Store: esa ruta es tan larga que Windows trunca los
rem  archivos de streamlit y la instalacion queda a medias sin avisar.
rem
rem  Los argumentos se reenvian a ejecutar.py, por ejemplo:
rem      iniciar.bat                    corre todos los modulos
rem      iniciar.bat ops productividad  solo esos modulos
rem      iniciar.bat app                abre la app web de contratacion OPS
rem ---------------------------------------------------------------------------

cd /d "%~dp0"
set "VENV=%~dp0.venv"
set "PY=%VENV%\Scripts\python.exe"

echo.
echo ===========================================
echo   Generacion de graficas
echo ===========================================
echo.

rem --- 1. Entorno virtual ----------------------------------------------------
if not exist "%PY%" (
    echo [1/3] Creando el entorno virtual...

    set "BASE="
    where py >nul 2>&1 && set "BASE=py -3"
    if not defined BASE (
        where python >nul 2>&1 && set "BASE=python"
    )
    if not defined BASE (
        echo.
        echo   ERROR: no se encontro Python en este equipo.
        echo   Instalalo desde https://www.python.org/downloads/ y marca
        echo   la casilla "Add Python to PATH" durante la instalacion.
        echo.
        pause
        exit /b 1
    )

    !BASE! -m venv "%VENV%"
    if not exist "%PY%" (
        echo.
        echo   ERROR: no se pudo crear el entorno virtual en:
        echo   %VENV%
        echo.
        pause
        exit /b 1
    )
) else (
    echo [1/3] Entorno virtual listo.
)

rem --- 2. Dependencias -------------------------------------------------------
"%PY%" -c "import pandas, matplotlib, openpyxl, streamlit" >nul 2>&1
if errorlevel 1 (
    echo [2/3] Instalando dependencias, esto tarda unos minutos...
    "%PY%" -m pip install --quiet --upgrade pip
    "%PY%" -m pip install --quiet -r "%~dp0requirements.txt"
    if errorlevel 1 (
        echo.
        echo   ERROR: fallo la instalacion de dependencias.
        echo   Revisa la conexion a internet y vuelve a ejecutar este archivo.
        echo.
        pause
        exit /b 1
    )
) else (
    echo [2/3] Dependencias instaladas.
)

rem --- 3. Modulos ------------------------------------------------------------
echo [3/3] Generando...
echo.

"%PY%" "%~dp0ejecutar.py" %*

echo.
pause
endlocal
