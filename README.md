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
- **Reparación conservadora y manual**: solo repara después de encontrar la firma completa `Kaspersky\Usb Drive\3.0` con `3.dat` a `7.dat`, y tras una confirmación explícita. Restaura archivos, resuelve colisiones sin sobrescribir y elimina únicamente esos archivos de firma y carpetas vacías. No existe reparación automática al insertar una unidad.
- **Temas de interfaz**: selector **Claro / Oscuro / Sistema** (menú *Ver → Tema*). La preferencia se guarda en `%USERPROFILE%\Antivirus_EACoreServer_Logs\config.json`.

## Principios de seguridad

`EACoreServer.exe` fue distribuido por productos legítimos de EA/Origin. Por eso, un nombre de archivo, una ruta histórica o una carpeta llamada `Kaspersky` no demuestran por sí solos una infección. Antes de eliminar un archivo, valide su firma digital, origen y contexto. La herramienta no sustituye a Microsoft Defender ni a un antivirus con firmas actualizadas.



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
| `scraper.py` | Consulta HTTPS y validación de rutas candidatas de processchecker.com |
| `process_manager.py` | Diagnóstico de procesos y protección de rutas típicas EA/Origin |
| `usb_monitor.py` | Monitor de inserción/remoción de unidades USB |
| `repair_engine.py` | Detección por firma completa y reparación no destructiva de USB |
| `logger.py` | Sistema de logging centralizado (consola + archivo) |
| `requirements.txt` | Dependencias Python |
| `Antivirus_EACoreServer.spec` | Configuración de PyInstaller |
| `tests/test_repair_engine.py` | Pruebas de firma, colisiones y preservación de contenido |

---

## Firma USB atendida

La reparación se habilita únicamente cuando se encuentra la siguiente firma completa en un **medio USB físico o extraíble**:

```
[Unidad]:\
└── Kaspersky\
    └── Usb Drive\
        ├── [archivos y carpetas originales del usuario]
        └── 3.0\
            ├── 3.dat
            ├── 4.dat
            ├── 5.dat
            ├── 6.dat
            └── 7.dat
```

Una carpeta con el mismo nombre pero sin los cinco archivos de firma queda marcada como **requiere revisión** y no se modifica.

### Proceso de reparación seguro

1. Valida la firma completa y solicita confirmación del usuario.
2. Quita atributos de oculto/sistema/solo lectura en la estructura validada.
3. Mueve el contenido de `Usb Drive\` a la raíz sin sobrescribir: ante colisiones crea un nombre con sufijo (`_1`, `_2`, …).
4. Elimina solo `3.dat` a `7.dat` dentro de `3.0\`.
5. Elimina `3.0\`, `Usb Drive\` y `Kaspersky\` **solo si están vacías**. Si queda un elemento desconocido o bloqueado, lo conserva y registra el incidente.
6. Guarda el estado de unidades completadas y todas las acciones en el log.


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
- La unidad debe ser extraíble/USB físico y tener los cinco archivos de firma.
- Asegúrese de que la unidad no está en uso y que tiene permisos de escritura.
- Si se informa contenido no reconocido, haga una copia y revíselo: la herramienta lo conserva deliberadamente.

### El scraping no funciona
- Se usa fallback automático con 57 rutas locales
- Verifique conectividad a internet
- La URL `https://processchecker.com/file/EACoreServer.exe.html` puede estar caída

---

## Pruebas

Las pruebas del motor no requieren una unidad USB física ni `pywin32`:

```powershell
python -m unittest discover -s tests -v
```

Cubren ausencia de firma, firma incompleta sin modificaciones, restauración con colisiones y preservación de contenido no reconocido.

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
*Python 3.12+ | Windows 10/11*
