# -*- mode: python ; coding: utf-8 -*-
#
# Especificación de PyInstaller para Antivirus_EACoreServer.
#
# Requisitos de plataforma objetivo:
#   · Windows Vista, 7, 8, 8.1, 10 y 11 (x86 y x64).
#   · macOS y Linux (sin cambios relevantes).
#
# Para Windows 7 el ejecutable DEBE construirse con Python 3.8 de 32 bits:
#   - Python 3.9+ requiere api-ms-win-core-path-l1-1-0.dll, inexistente en Win7.
#   - Un binario x86 corre también en Windows de 64 bits (WOW64).
#   - Consulte el script build.bat para los controles previos al empaquetado.

import os

# ---------------------------------------------------------------------------
# Directorio temporal en ejecución.
# ---------------------------------------------------------------------------
# PyInstaller en modo onefile extrae el ejecutable a un directorio _MEI bajo
# la variable de entorno TEMP. En Windows, cuando TEMP apunta a
# C:\Windows\TEMP o a una ruta con permisos restringidos, python3x.dll no
# puede cargarse y la aplicación falla con "Failed to load Python DLL".
#
# Solución: forzar un directorio temporal controlado por el usuario cuando el
# entorno TEMP del sistema no sea escribible.
#
# Se evalúa en tiempo de empaquetado para que el valor quede embebido en el
# ejecutable; al arrancar, PyInstaller lo usa como base de _MEI.
def _runtime_tmpdir_sugerido():
    """Devuelve una ruta temporal escribible o None para usar la del sistema."""
    # En el contexto del empaquetado, sys._MEIPASS aún no existe.
    # Usamos la carpeta local del usuario como alternativa segura.
    try:
        import tempfile
        # tempfile.gettempdir() respeta TMP/TEMP del usuario antes que la del sistema.
        tmp = tempfile.gettempdir()
        if os.path.isdir(tmp) and os.access(tmp, os.W_OK):
            # Dentro de la carpeta temporal, usar un subdirectorio propio para
            # aislar la aplicación y evitar colisiones con otros _MEI*.
            ruta = os.path.join(tmp, "AntivirusEACoreServer_Temp")
            return ruta
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Análisis
# ---------------------------------------------------------------------------
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        # Módulos importados dinámicamente que PyInstaller no detecta por sí solo.
        'usb_monitor_windows',
        'tkinter',
        'tkinter.ttk',
        'tkinter.scrolledtext',
        'tkinter.messagebox',
        'tkinter.filedialog',
        'tkinter.simpledialog',
        'tkinter.colorchooser',
        'tkinter.font',
        # Dependencias de terceros: asegurar que se empaqueten.
        'requests',
        'bs4',
        'psutil',
        'pystray',
        'PIL',
        'PIL.Image',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Módulos pesados innecesarios que aumentan el tamaño del ejecutable.
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# ---------------------------------------------------------------------------
# Manifiesto de Windows
# ---------------------------------------------------------------------------
# Incluye un manifiesto con compatibilidad para Windows 10/11 pero también para
# versiones anteriores (Vista, 7, 8). Esto evita que Windows aplique capas de
# compatibilidad que rompan la detección de la versión real del SO.
_manifest_text = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <assemblyIdentity
      type="win32"
      name="Antivirus_EACoreServer"
      version="1.2.0.0"
      processorArchitecture="x86"/>
  <description>Antivirus EACoreServer - Protección USB y gestión de procesos</description>
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
    <security>
      <requestedPrivileges>
        <requestedExecutionLevel level="requireAdministrator" uiAccess="false"/>
      </requestedPrivileges>
    </security>
  </trustInfo>
  <compatibility xmlns="urn:schemas-microsoft-com:compatibility.v1">
    <application>
      <!-- Windows Vista -->
      <supportedOS Id="{e2011457-1546-43c5-a5fe-008deee3d3f0}"/>
      <!-- Windows 7 -->
      <supportedOS Id="{35138b9a-5d96-4fbd-8e2d-a2440225f93a}"/>
      <!-- Windows 8 -->
      <supportedOS Id="{4a2f28e3-53b9-4441-ba9c-d69d4a4a6e38}"/>
      <!-- Windows 8.1 -->
      <supportedOS Id="{1f676c76-80e1-4239-95bb-83d0f6d0da78}"/>
      <!-- Windows 10 -->
      <supportedOS Id="{8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a}"/>
      <!-- Windows 11 -->
      <supportedOS Id="{35138b9a-5d96-4fbd-8e2d-a2440225f93a}"/>
    </application>
  </compatibility>
  <application xmlns="urn:schemas-microsoft-com:asm.v3">
    <windowsSettings>
      <dpiAware xmlns="http://schemas.microsoft.com/SMI/2005/WindowsSettings">true</dpiAware>
      <dpiAwareness xmlns="http://schemas.microsoft.com/SMI/2016/WindowsSettings">PerMonitorV2</dpiAwareness>
    </windowsSettings>
  </application>
</assembly>
"""

# Escribir el manifiesto en el directorio de build.
_manifest_path = os.path.join('build', 'Antivirus_EACoreServer.manifest')
os.makedirs('build', exist_ok=True)
with open(_manifest_path, 'w', encoding='utf-8') as _f:
    _f.write(_manifest_text)

# ---------------------------------------------------------------------------
# Ejecutable
# ---------------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],  # archivos de nombres (no usados)
    name='Antivirus_EACoreServer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX desactivado: comprimir el ejecutable con UPX puede impedir la carga
    # de python3x.dll en Windows 7 y genera falsos positivos en antivirus.
    upx=False,
    upx_exclude=[],
    # Directorio temporal donde PyInstaller extrae los archivos en modo onefile.
    # Se apunta a una carpeta de usuario en vez de C:\Windows\TEMP para evitar
    # problemas de permisos que impiden la carga de python3x.dll.
    runtime_tmpdir=_runtime_tmpdir_sugerido(),
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='x86',
    codesign_identity=None,
    entitlements_file=None,
    # Manifiesto para compatibilidad con versiones antiguas de Windows y
    # para solicitar privilegios de administrador de forma nativa.
    manifest=_manifest_path,
)
