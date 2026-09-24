@echo off
REM ============================================
REM  Script de compilación para Antivirus_EACoreServer
REM  Ejecutar como Administrador
REM ============================================

echo ============================================
echo  Antivirus EACoreServer - Build Script
echo ============================================
echo.

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no encontrado. Instale Python 3.12+
    pause
    exit /b 1
)

REM Verificar e instalar dependencias
echo [INFO] Verificando dependencias...
pip list 2>nul | findstr /i "PyInstaller" >nul
if errorlevel 1 (
    echo [INFO] Instalando PyInstaller...
    pip install pyinstaller>=6.0.0
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