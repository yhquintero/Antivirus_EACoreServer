@echo off
REM ============================================
REM  Script de compilación para Antivirus_EACoreServer
REM  Ejecutar como Administrador
REM ============================================

echo ============================================
echo  Antivirus EACoreServer - Build Script
echo ============================================
echo.

REM Verificar Python. El binario universal se construye con Python 3.8 x86.
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no encontrado. Use Python 3.8 de 32 bits.
    echo [INFO] En Windows 7 instale tambien KB2533623: sin esa actualizacion
    echo [INFO] Python no puede cargar api-ms-win-core-path-l1-1-0.dll.
    pause
    exit /b 1
)
python -c "import sys,struct; assert sys.version_info[:2] == (3,8) and struct.calcsize('P') == 4" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Este build requiere Python 3.8 de 32 bits para Vista-11 x86/x64.
    echo [INFO] Un ejecutable x86 funciona tambien en Windows x64.
    pause
    exit /b 1
)

REM Verificar e instalar dependencias
echo [INFO] Verificando dependencias...
pip list 2>nul | findstr /i "PyInstaller" >nul
if errorlevel 1 (
    echo [INFO] Instalando PyInstaller...
    pip install "pyinstaller==5.13.2"
)

pip list 2>nul | findstr /i "requests" >nul
if errorlevel 1 (
    echo [INFO] Instalando dependencias...
    pip install -r requirements.txt
)

echo.
echo [INFO] Empaquetando con PyInstaller...
echo.

REM Opcion 1: Con consola visible (modo depuracion)
pyinstaller Antivirus_EACoreServer.spec --clean --noconfirm

echo.
echo ============================================
echo  Empaquetado completado.
echo  Archivo: dist\Antivirus_EACoreServer.exe
echo ============================================
echo.
pause