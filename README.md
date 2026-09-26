# Antivirus EACoreServer

Aplicación de escritorio en Python 3.12+ para **diagnosticar** la estructura USB `Kaspersky\\Usb Drive` y gestionar procesos llamados `EACoreServer.exe`. Interfaz gráfica en español y controles conservadores para evitar cambios accidentales.

---

## Tabla de Contenidos

1. [Descripción](#descripción)
2. [Requisitos del Sistema](#requisitos-del-sistema)
3. [Instalación de Dependencias](#instalación-de-dependencias)
4. [Ejecución de la Aplicación](#ejecución-de-la-aplicación)
5. [Empaquetado como Antivirus_EACoreServer.exe](#empaquetado-como-antivirus_eacoreserverexe)
6. [Instalador con Inno Setup (Opcional)](#instalador-con-inno-setup-opcional)
7. [Módulos del Proyecto](#módulos-del-proyecto)
8. [Firma USB atendida](#firma-usb-atendida)
9. [Manejo de Errores](#manejo-de-errores)
10. [Solución de Problemas](#solución-de-problemas)
11. [Pruebas](#pruebas)

---

## Descripción

**Antivirus EACoreServer** es una utilidad de diagnóstico y reparación conservadora diseñada para:

- **Consulta HTTPS de rutas**: obtiene rutas históricas candidatas de `EACoreServer.exe` desde `https://processchecker.com/file/EACoreServer.exe.html` y las combina con una lista local para funcionar sin conexión. Las rutas son datos de diagnóstico, **no indicadores de malware**.
- **Gestión protegida de procesos**: muestra procesos `EACoreServer.exe` y permite finalizarlos con confirmación. Las rutas típicas de EA/Origin y sus juegos se identifican como posibles componentes legítimos y quedan protegidas contra eliminación por nombre.
- **Monitoreo de unidades**: lista letras de unidad para diagnóstico. Solo memorias extraíbles y discos USB físicos se habilitan para reparación; discos internos y de red son de solo diagnóstico.
- **Reparación conservadora y manual**: solo repara después de encontrar la firma exacta `Kaspersky\Usb Drive\3.0` con `5.dat`, `6.dat`, `7.dat` y un fichero numérico sin extensión, y tras una confirmación explícita. Restaura archivos por copia verificada con SHA-256 antes de retirar el origen, resuelve colisiones sin sobrescribir y elimina únicamente esos ficheros de firma y carpetas vacías. No existe reparación automática al insertar una unidad.
- **Temas de interfaz**: selector **Claro / Oscuro / Sistema** (menú *Ver → Tema*). La preferencia se guarda en `%USERPROFILE%\Antivirus_EACoreServer_Logs\config.json`.

## Principios de seguridad

`EACoreServer.exe` fue distribuido por productos legítimos de EA/Origin. Por eso, un nombre de archivo, una ruta histórica o una carpeta llamada `Kaspersky` no demuestran por sí solos una infección. Antes de eliminar un archivo, valide su firma digital, origen y contexto. La herramienta no sustituye a Microsoft Defender ni a un antivirus con firmas actualizadas.



---

## Requisitos del Sistema

- **SO**: Windows 10/11 (64-bit recomendado), macOS 12+ y Linux con `tkinter`
- **Python**: 3.12 o superior
- **Permisos**: se recomienda Administrador en Windows, `root` en Linux y privilegios
  de administrador en macOS para la funcionalidad completa
- **Arquitectura**: x64 en Windows; x64 y arm64 en macOS y Linux

> **Compatibilidad multiplataforma.** El código Win32 (`pywin32`, `ctypes.windll`,
> IOCTLs y la ventana `WM_DEVICECHANGE`) está aislado en `usb_monitor_windows.py` y
> solo se importa en Windows. `usb_monitor.py` es una fachada portable que en macOS
> usa `diskutil` y en Linux `/proc/mounts` + `/sys/block`. La elevación de privilegios
> usa `ShellExecuteW` en Windows, `osascript` en macOS y `pkexec`/`sudo` en Linux.
>
> La **reparación real** sigue dirigida a unidades con la estructura del malware; en
> macOS y Linux la herramienta opera en modo de diagnóstico y prueba.

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
pip install -r requirements-dev.txt
```

> `requirements-dev.txt` incluye `requirements.txt` y añade PyInstaller.

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
| `scraper.py` | Consulta HTTPS y validación de rutas candidatas de processchecker.com |
| `process_manager.py` | Diagnóstico de procesos y protección de rutas típicas EA/Origin |
| `usb_monitor.py` | Fachada multiplataforma del monitor USB (Windows, macOS y Linux) |
| `usb_monitor_windows.py` | Backend exclusivo de Windows: `pywin32`, IOCTLs y `WM_DEVICECHANGE` |
| `repair_engine.py` | Detección por firma exacta y restauración verificada con SHA-256 |
| `logger.py` | Sistema de logging centralizado (consola + archivo) |
| `requirements.txt` | Dependencias Python (`pywin32` marcado solo para Windows) |
| `requirements-dev.txt` | Dependencias de empaquetado (PyInstaller) |
| `Antivirus_EACoreServer.spec` | Configuración de PyInstaller |
| `tests/test_repair_engine.py` | Pruebas de firma exacta, SHA-256, colisiones y preservación |
| `tests/test_scraper_rutas.py` | Pruebas de las 52 rutas únicas sin duplicados |
| `tests/test_multiplataforma.py` | Pruebas de importación y comportamiento en los 3 SO |

---

## Firma USB atendida

La reparación se habilita únicamente cuando se encuentra la siguiente firma completa en un **medio USB físico o extraíble**:

```
[Unidad]:\
└── Kaspersky\
    └── Usb Drive\
        ├── [archivos y carpetas originales del usuario]
        └── 3.0\
            ├── Fichero en forma de número sin extensión, número aleatorio empezando en 0
            ├── 5.dat
            ├── 6.dat
            └── 7.dat
            
```

La firma **exacta** exige los cuatro elementos a la vez:

| Elemento | Ubicación | Obligatorio |
|----------|-----------|-------------|
| `5.dat`, `6.dat`, `7.dat` | `Kaspersky\Usb Drive\3.0\` | Sí, los tres |
| Fichero numérico **sin extensión** (p. ej. `0`, `1337`, `20240517`) | `Kaspersky\Usb Drive\3.0\` | Al menos uno |

Una carpeta con el mismo nombre pero sin la firma completa queda marcada como
**requiere revisión** y no se modifica. Si están los tres `.dat` pero falta el
fichero numérico, el diagnóstico es **sospechoso**: los `.dat` sueltos no son
prueba suficiente. Un *directorio* llamado `1234` tampoco cuenta como firma,
solo archivos regulares cuyo nombre sea íntegramente numérico.

### Proceso de reparación seguro

1. Valida la firma exacta y solicita confirmación del usuario.
2. Quita atributos de oculto/sistema/solo lectura en la estructura validada
   (ACL de Win32 en Windows; permisos POSIX en macOS y Linux).
3. **Restaura por copia verificada, nunca con `shutil.move` a ciegas.** Cada
   archivo se calcula su SHA-256 en el origen, se copia al destino, se fuerza la
   escritura a disco con `fsync` y se vuelve a calcular el SHA-256 de la copia.
   **Solo si ambas sumas coinciden se retira el origen**; si difieren, la copia
   defectuosa se descarta y el archivo original permanece intacto.
4. Resuelve colisiones sin sobrescribir: crea un nombre con sufijo (`_1`, `_2`, …).
5. Elimina únicamente `5.dat`, `6.dat`, `7.dat` y los ficheros numéricos sin
   extensión dentro de `3.0\`.
6. Elimina `3.0\`, `Usb Drive\` y `Kaspersky\` **solo si están vacías**, usando
   `rmdir` y nunca `rmtree`. Si queda un elemento desconocido o bloqueado, lo
   conserva y registra el incidente.
7. No sigue enlaces simbólicos: un `symlink` dentro del USB no puede usarse para
   escribir fuera de él.
8. Guarda el estado de unidades completadas, las sumas SHA-256 verificadas y
   todas las acciones en el log.


---

## Manejo de Errores

La aplicación maneja los siguientes escenarios de error:

- **Sin firma completa**: No genera fallos ni cambios; se informa como unidad limpia o que requiere revisión.
- **Archivos o carpetas bloqueados/desconocidos**: Se conservan y se reportan; no se fuerza un borrado recursivo.
- **Permisos insuficientes**: Se notifica al usuario; la finalización de procesos puede intentar `taskkill /F`
- **Red inactiva**: Se usan rutas por defecto locales (fallback)
- **Unidades sin formato**: Se detectan como no accesibles y se saltan

---

## Solución de Problemas

### La aplicación no muestra todas las unidades
- Se listan letras de USB, discos fijos y red para diagnóstico; los CD-ROM vacíos se omiten. Solo medios USB/extraíbles se pueden reparar.
- Verifique que la unidad tiene letra asignada (Administración de discos)
- Ejecute como Administrador
- Pulse *Refrescar Unidades* en el menú *Herramientas*

### No se puede finalizar EACoreServer.exe
- Ejecute como Administrador
- Puede ser un componente legítimo de EA/Origin o de un juego. Revise el editor en Propiedades → Firmas digitales antes de intervenir.
- Verifique si es un servicio de Windows desde `services.msc`

### La reparación USB falla
- La unidad debe ser extraíble/USB físico y tener la firma exacta: `5.dat`, `6.dat`,
  `7.dat` y al menos un fichero numérico sin extensión dentro de `3.0\`.
- Asegúrese de que la unidad no está en uso y que tiene permisos de escritura.
- Si se informa contenido no reconocido, haga una copia y revíselo: la herramienta lo conserva deliberadamente.

### El scraping no funciona
- Se usa fallback automático con 52 rutas locales únicas
- Verifique conectividad a internet
- La URL `https://processchecker.com/file/EACoreServer.exe.html` puede estar caída

---

## Pruebas

Las pruebas no requieren una unidad USB física ni `pywin32`:

```bash
python -m py_compile main.py gui.py logger.py process_manager.py repair_engine.py scraper.py usb_monitor.py usb_monitor_windows.py
python -m unittest discover -s tests -v
```

**54 pruebas** cubren (el número de omitidas varía según el SO):

- ausencia de firma, firma incompleta y `.dat` completos sin fichero numérico;
- confirmación de la firma exacta con varios ficheros numéricos sin extensión;
- restauración con verificación SHA-256 y auditoría de las sumas;
- copia corrupta: el origen **no** se retira cuando el SHA-256 no coincide;
- resolución de colisiones y preservación de contenido no reconocido;
- enlaces simbólicos no seguidos;
- las 52 rutas únicas sin duplicados y su fusión con las rutas remotas;
- importación y comportamiento multiplataforma en Windows, macOS y Linux.

`py_compile` solo valida sintaxis y no importa los módulos, por eso
`usb_monitor_windows.py` puede compilarse también en Ubuntu y macOS.

### Integración continua

El flujo `.github/workflows/ci.yml` ejecuta la comprobación de sintaxis y las
pruebas unitarias en una matriz de **Ubuntu, macOS y Windows** con Python 3.12,
sin `fail-fast` para que los tres sistemas reporten su resultado.

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
*Versión: 1.1.0*
*Python 3.12+ | Windows 10/11 · macOS · Linux*
