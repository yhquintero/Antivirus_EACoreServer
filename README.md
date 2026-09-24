# Antivirus EACoreServer

Aplicación de escritorio en Python 3.12+ para la detección y eliminación de malware en unidades USB, discos fijos y de red, y la gestión de procesos `EACoreServer.exe`. Interfaz gráfica en español.

---

## Tabla de Contenidos

1. [Descripción](#descripción)
2. [Requisitos del Sistema](#requisitos-del-sistema)
3. [Instalación de Dependencias](#instalación-de-dependencias)
4. [Ejecución de la Aplicación](#ejecución-de-la-aplicación)
5. [Empaquetado como Antivirus_EACoreServer.exe](#empaquetado-como-antivirus_eacoreserverexe)
6. [Instalador con Inno Setup (Opcional)](#instalador-con-inno-setup-opcional)
7. [Módulos del Proyecto](#módulos-del-proyecto)
8. [Estructura del Malware que Combate](#estructura-del-malware-que-combate)
9. [Manejo de Errores](#manejo-de-errores)
10. [Solución de Problemas](#solución-de-problemas)

---

## Descripción

**Antivirus EACoreServer** es una utilidad de seguridad diseñada para:

- **Web Scraping**: Obtiene rutas candidatas de `EACoreServer.exe` desde `http://processchecker.com/file/EACoreServer.exe.html` y las fusiona con las 57 rutas por defecto (listado oficial de processchecker.com), garantizando cobertura total incluso sin conexión.
- **Gestión de Procesos**: Detecta y finaliza el proceso `EACoreServer.exe` en cualquiera de las rutas identificadas. Puede **detener el servicio y eliminar por completo** `EACoreServer.exe` + `EACore.dat` (el fichero que contiene la base del virus) de la carpeta seleccionada o del servicio de `C:\ProgramData\EACoreService`.
- **Monitoreo de Unidades**: Lista **todas las unidades con letra (A–Z)**: memorias USB y tarjetas (extraíbles), discos fijos (SSD/HDD internos o externos USB) y unidades de red. Cada unidad se muestra con etiqueta, sistema de archivos, tamaño y número de serie.
- **Reparación Automática**: Cuando se detecta una unidad infectada con el malware `Kaspersky\Usb Drive`, restaura los archivos originales, elimina las bases de datos del virus y limpia la estructura maliciosa. El estado de las unidades reparadas se **guarda en disco** (se recuerda entre sesiones).
- **Temas de interfaz**: Selector de tema **Claro / Oscuro / Sistema** (menú *Ver → Tema*). La preferencia se guarda en `%USERPROFILE%\Antivirus_EACoreServer_Logs\config.json` y se recuerda en cada inicio.

---

## Requisitos del Sistema

- **SO**: Windows 10/11 (64-bit recomendado)
- **Python**: 3.12 o superior
- **Permisos**: Se recomienda ejecutar como Administrador para funcionalidad completa
- **Arquitectura**: x64

---

## Instalación de Dependencias

### Paso 1: Crear entorno virtual (recomendado)

```powershell
python -m venv venv
.\venv\Scripts\activate
```

### Paso 2: Instalar dependencias

```powershell
pip install -r requirements.txt
```

### Paso 3: Verificar instalación

```powershell
python -c "import tkinter; import psutil; import requests; import win32api; print('Todas las dependencias OK')"
```

---

## Ejecución de la Aplicación

### Desde la línea de comandos:

```powershell
python main.py
```

O directamente:

```powershell
python gui.py
```

### Como administrador (recomendado):

```powershell
runas /user:Administrador python main.py
```

---

## Empaquetado como Antivirus_EACoreServer.exe

### Paso 1: Instalar PyInstaller

```powershell
pip install pyinstaller>=6.0.0
```

### Paso 2: Empaquetar (con consola visible para depuración)

```powershell
pyinstaller Antivirus_EACoreServer.spec --clean
```

### Paso 3: Empaquetar (sin consola, modo ventana only)

Edite el archivo `Antivirus_EACoreServer.spec` y cambie:
```python
console=True,   # → Cambiar a:
console=False,
```

Luego ejecute:
```powershell
pyinstaller Antivirus_EACoreServer.spec --clean
```

### Paso 4: El archivo .exe estará en:

```
dist\Antivirus_EACoreServer.exe
```

### Opciones adicionales de PyInstaller:

```powershell
# Empaquetado con icono personalizado
pyinstaller Antivirus_EACoreServer.spec --icon=icono.ico --clean

# Empaquetado con un solo archivo (one-file)
pyinstaller --onefile --windowed --name Antivirus_EACoreServer main.py

# Empaquetado con consola oculta y modo one-file
pyinstaller --onefile --noconsole --name Antivirus_EACoreServer main.py

# Para ver qué módulos están incluidos
pyinstaller --debug all Antivirus_EACoreServer.spec
```

### Solución de problemas comunes del empaquetado:

Si obtiene errores de módulos faltantes, agréguelos a `hiddenimports` en el `.spec`:

```python
hiddenimports=[
    ...
    'pystray',
    'PIL',
    'PIL.Image',
    'PIL.ImageTk',
    'pkg_resources',
    'setuptools',
],
```

---

## Instalador con Inno Setup (Opcional)

### Paso 1: Descargar e instalar Inno Setup

Descargue desde: https://jrsoftware.org/isdl.php

### Paso 2: Crear el script del instalador `installer.iss`

```iss
[Setup]
AppName=Antivirus EACoreServer
AppVersion=1.0
DefaultDirName={pf}\Antivirus EACoreServer
DefaultGroupName=Antivirus EACoreServer
OutputDir=dist
OutputBaseFilename=Antivirus_EACoreServer_Setup
Compression=lzma
SolidCompression=yes

[Files]
Source: "dist\Antivirus_EACoreServer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\Antivirus EACoreServer"; Filename: "{app}\Antivirus_EACoreServer.exe"
Name: "{group}\Desinstalar Antivirus EACoreServer"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\Antivirus_EACoreServer.exe"; Description: "Ejecutar Antivirus EACoreServer"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\Antivirus_EACoreServer.exe"; Parameters: "/quit"; Flags: runhidden

[Registry]
Root: HKLM; Subkey: "SOFTWARE\AntivirusEACoreServer"; ValueType: string; ValueName: "InstallDir"; ValueString: "{app}"
Root: HKLM; Subkey: "SOFTWARE\AntivirusEACoreServer"; ValueType: string; ValueName: "Version"; ValueString: "1.0"
```

### Paso 3: Compilar el instalador

```powershell
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

El instalador estará en la carpeta `dist`.

---

## Módulos del Proyecto

| Archivo | Descripción |
|---------|-------------|
| `main.py` | Punto de entrada principal. Verifica permisos y lanza la GUI |
| `gui.py` | Interfaz gráfica completa con tkinter (3 pestañas) |
| `scraper.py` | Web scraping de rutas EACoreServer.exe desde processchecker.com |
| `process_manager.py` | Detección y finalización de procesos EACoreServer.exe |
| `usb_monitor.py` | Monitor de inserción/remoción de unidades USB |
| `repair_engine.py` | Motor de reparación de unidades USB infectadas |
| `logger.py` | Sistema de logging centralizado (consola + archivo) |
| `requirements.txt` | Dependencias Python |
| `Antivirus_EACoreServer.spec` | Configuración de PyInstaller |

---

## Estructura del Malware que Combate

```
[Unidad]:\
├── Kaspersky\                    (atributos: -a -r -h -s)
│   └── Usb Drive\                (atributos: -a -r -h -s)
│       ├── [archivos y carpetas originales del usuario]
│       └── 3.0\
│           ├── 3.dat             ← Base de datos del virus
│           ├── 4.dat             ← Base de datos del virus
│           ├── 5.dat             ← Base de datos del virus
│           ├── 6.dat             ← Base de datos del virus
│           └── 7.dat             ← Base de datos del virus
└── [archivos originales]         ← Deberían estar aquí
```

### Proceso de reparación:

1. **Verificar** existencia de `Kaspersky\Usb Drive\`
2. **Quitar atributos** (`-h -s -r -a`) de `Kaspersky` y `Usb Drive`
3. **Mover** todo el contenido de `Usb Drive\` a la raíz de la unidad
4. **Eliminar** `3.dat`, `4.dat`, `5.dat`, `6.dat`, `7.dat`
5. **Eliminar** carpetas `3.0\`, `Usb Drive\`, `Kaspersky\` en ese orden
6. **Registrar** todas las acciones en el log

---

## Manejo de Errores

La aplicación maneja los siguientes escenarios de error:

- **Unidades sin carpeta Kaspersky**: No generan fallos, se registran como "sin infección"
- **Archivos bloqueados**: Se reportan sin detener el proceso completo
- **Permisos insuficientes**: Se notifica al usuario y se intenta con `taskkill /F`
- **Red inactiva**: Se usan rutas por defecto locales (fallback)
- **Unidades sin formato**: Se detectan como no accesibles y se saltan

---

## Solución de Problemas

### La aplicación no muestra todas las unidades
- Se listan todas las letras A–Z (USB extraíbles, discos fijos SSD/HDD y unidades de red); los CD-ROM vacíos se omiten
- Verifique que la unidad tiene letra asignada (Administración de discos)
- Ejecute como Administrador
- Pulse *Refrescar Unidades* en el menú *Herramientas*

### No se puede finalizar EACoreServer.exe
- Ejecute como Administrador
- El proceso puede estar protegido por EA AntiCheat
- Verifique si es un servicio de Windows y deténelo desde `services.msc`

### La reparación USB falla
- Asegúrese de que la unidad no está en uso por otro programa
- Verifique que tiene permisos de escritura en la unidad
- Revise el log para detalles del error

### El scraping no funciona
- Se usa fallback automático con 57 rutas locales
- Verifique conectividad a internet
- La URL `http://processchecker.com/file/EACoreServer.exe.html` puede estar caída

---

## Logging

Todos los registros se almacenan en:

```
C:\Users\[Usuario]\Antivirus_EACoreServer_Logs\antivirus_YYYYMMDD.log
```

Rotación automática: 5 MB por archivo, 7 archivos de respaldo.

---

## Licencia

Aplicación de utilidad personal. Uso bajo su propia responsabilidad.

---

## Soporte

Para problemas o preguntas, revise:
1. El archivo de log en `Antivirus_EACoreServer_Logs\`
2. La pestaña "Registro (Log)" de la interfaz gráfica
3. El mensaje de error detallado en la barra de estado

---

*Última actualización: Septiembre 2026*
*Versión: 1.0*
*Python 3.12+ | Windows 10/11*
