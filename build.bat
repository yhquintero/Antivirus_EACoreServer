@echo off
REM ============================================
REM  Script de compilación para Antivirus_EACoreServer
REM  Ejecutar como Administrador
REM
REM  IMPORTANTE: Este script DEBE ejecutarse con Python 3.8 de 32 bits.
REM  Python 3.9+ genera un ejecutable que NO funciona en Windows 7/8 porque
REM  requiere api-ms-win-core-path-l1-1-0.dll (inexistente en esos sistemas).
REM ============================================

setlocal enabledelayedexpansion

echo ============================================
echo  Antivirus EACoreServer - Build Script
echo ============================================
echo.

REM -----------------------------------------------
REM  1. Verificar que Python está en el PATH
REM -----------------------------------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no encontrado en el PATH.
    echo.
    echo Este build requiere Python 3.8 de 32 bits instalado y accesible.
    echo Descargue Python 3.8 desde: https://www.python.org/downloads/release/python-3820/
    echo.
    echo Marque la opcion "Add Python to PATH" durante la instalacion.
    pause
    exit /b 1
)

REM -----------------------------------------------
REM  2. Verificar que la version es EXACTAMENTE 3.8
REM -----------------------------------------------
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYTHON_VERSION=%%v

echo [INFO] Python detectado: %PYTHON_VERSION%
echo.

REM Extraer mayor y menor de la version
for /f "tokens=1,2 delims=." %%a in ("%PYTHON_VERSION%") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)

if not "%PY_MAJOR%"=="3" (
    echo [ERROR] Se requiere Python 3.x, se encontro Python %PYTHON_VERSION%.
    echo.
    echo Python %PYTHON_VERSION% genera un ejecutable que requiere
    echo api-ms-win-core-path-l1-1-0.dll, inexistente en Windows 7 y 8.
    echo El usuario final vera este error al intentar abrir el programa:
    echo.
    echo   "El programa no puede iniciarse porque falta
    echo    api-ms-win-core-path-l1-1-0.dll en el equipo."
    echo.
    echo Solucion: use Python 3.8 de 32 bits para compilar.
    pause
    exit /b 1
)

if not "%PY_MINOR%"=="8" (
    echo [ERROR] Se requiere Python 3.8, se encontro Python %PYTHON_VERSION%.
    echo.
    echo Python 3.%PY_MINOR% no es compatible con Windows 7/8. El ejecutable
    echo generado fallara al arrancar en esos sistemas con el siguiente error:
    echo.
    echo   "El programa no puede iniciarse porque falta
    echo    api-ms-win-core-path-l1-1-0.dll en el equipo."
    echo.
    echo   "Failed to load Python DLL 'C:\Windows\TEMP\2\_MEI...\python3%PY_MINOR%.dll'.
    echo    LoadLibrary: No se puede encontrar el modulo especificado."
    echo.
    echo Solucion:
    echo   1. Desinstale Python %PYTHON_VERSION%.
    echo   2. Instale Python 3.8 de 32 bits desde:
    echo      https://www.python.org/downloads/release/python-3820/
    echo   3. Vuelva a ejecutar este script.
    pause
    exit /b 1
)

REM -----------------------------------------------
REM  3. Verificar arquitectura: debe ser 32 bits
REM -----------------------------------------------
python -c "import struct; exit(0 if struct.calcsize('P') == 4 else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Se requiere Python 3.8 de 32 BITS (x86), se detecto 64 bits.
    echo.
    echo Un ejecutable x86 funciona en Windows de 32 y 64 bits.
    echo Un ejecutable x64 SOLO funciona en Windows de 64 bits.
    echo.
    echo Para maximizar la compatibilidad, instale Python 3.8 de 32 bits:
    echo   https://www.python.org/downloads/release/python-3820/
    echo   (el instalador "Windows installer (32-bit)")
    pause
    exit /b 1
)

echo [OK] Python 3.8 de 32 bits confirmado.
echo.

REM -----------------------------------------------
REM  4. Verificar e instalar PyInstaller
REM -----------------------------------------------
echo [INFO] Verificando dependencias...

pip list 2>nul | findstr /i "PyInstaller" >nul
if errorlevel 1 (
    echo [INFO] Instalando PyInstaller...
    pip install "pyinstaller>=5.13.2,<7.0.0"
    if errorlevel 1 (
        echo [ERROR] No se pudo instalar PyInstaller.
        pause
        exit /b 1
    )
) else (
    echo [OK] PyInstaller ya instalado.
)

REM -----------------------------------------------
REM  5. Verificar e instalar dependencias
REM -----------------------------------------------
pip list 2>nul | findstr /i "requests" >nul
if errorlevel 1 (
    echo [INFO] Instalando dependencias...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] No se pudieron instalar las dependencias.
        pause
        exit /b 1
    )
) else (
    echo [OK] Dependencias ya instaladas.
)

echo.

REM -----------------------------------------------
REM  6. Limpiar directorios de build anteriores
REM -----------------------------------------------
if exist build rmdir /s /q build >nul 2>&1
if exist dist rmdir /s /q dist >nul 2>&1
echo [INFO] Directorios de build limpiados.
echo.

REM -----------------------------------------------
REM  7. Compilar con PyInstaller
REM -----------------------------------------------
echo [INFO] Empaquetando con PyInstaller (modo onefile, x86)...
echo.

pyinstaller Antivirus_EACoreServer.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo [ERROR] El empaquetado fallo. Revise los mensajes anteriores.
    echo.
    echo Causas comunes:
    echo   - Modulo faltante en hiddenimports del archivo .spec
    echo   - Error de sintaxis en algun modulo del proyecto
    echo   - PyInstaller incompatible con esta version de Python
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Empaquetado completado exitosamente.
echo  Archivo: dist\Antivirus_EACoreServer.exe
echo ============================================
echo.
echo NOTA: El ejecutable fue compilado con Python %PYTHON_VERSION% (32 bits).
echo       Deberia funcionar en Windows Vista, 7, 8, 8.1, 10 y 11.
echo.
echo Verificacion rapida:
echo   1. Ejecute dist\Antivirus_EACoreServer.exe
echo   2. Compruebe que la barra de estado muestra el sistema correctamente
echo   3. En Ayuda -> Comprobar compatibilidad, verifique el nivel de soporte
echo.
pause
