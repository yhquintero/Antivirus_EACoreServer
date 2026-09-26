# Antivirus EACoreServer

Aplicación de escritorio en Python 3.8+ para **diagnosticar** la estructura USB `Kaspersky\\Usb Drive` y gestionar procesos llamados `EACoreServer.exe`. Interfaz gráfica en español, cinco paletas de color personalizables, ayuda visual integrada y controles conservadores para evitar cambios accidentales.

Funciona en Windows Vista, 7, 8, 8.1, 10 y 11 (x86 y x64), macOS, Linux, FreeBSD, OpenBSD, NetBSD, DragonFly, Solaris/illumos y AIX.

---

## Tabla de Contenidos

1. [Descripción](#descripción)
2. [Compatibilidad por sistema operativo](#compatibilidad-por-sistema-operativo)
3. [Requisitos del Sistema](#requisitos-del-sistema)
4. [Instalación de Dependencias](#instalación-de-dependencias)
5. [Ejecución de la Aplicación](#ejecución-de-la-aplicación)
6. [Personalización de la interfaz](#personalización-de-la-interfaz)
7. [Ayuda visual para el usuario final](#ayuda-visual-para-el-usuario-final)
8. [Empaquetado como Antivirus_EACoreServer.exe](#empaquetado-como-antivirus_eacoreserverexe)
9. [Instalador con Inno Setup (Opcional)](#instalador-con-inno-setup-opcional)
10. [Módulos del Proyecto](#módulos-del-proyecto)
11. [Firma USB atendida](#firma-usb-atendida)
12. [Manejo de Errores](#manejo-de-errores)
13. [Solución de Problemas](#solución-de-problemas)
14. [Pruebas](#pruebas)

---

## Descripción

**Antivirus EACoreServer** es una utilidad de diagnóstico y reparación conservadora diseñada para:

- **Consulta HTTPS de rutas**: obtiene rutas históricas candidatas de `EACoreServer.exe` desde `https://processchecker.com/file/EACoreServer.exe.html` y las combina con una lista local para funcionar sin conexión. Las rutas son datos de diagnóstico, **no indicadores de malware**.
- **Gestión protegida de procesos**: muestra procesos `EACoreServer.exe` y permite finalizarlos con confirmación. Las rutas típicas de EA/Origin y sus juegos se identifican como posibles componentes legítimos y quedan protegidas contra eliminación por nombre.
- **Monitoreo de unidades**: lista letras de unidad para diagnóstico. Solo memorias extraíbles y discos USB físicos se habilitan para reparación; discos internos y de red son de solo diagnóstico.
- **Reparación conservadora y manual**: solo repara después de encontrar la firma exacta `Kaspersky\Usb Drive\3.0` con `5.dat`, `6.dat`, `7.dat` y un fichero numérico sin extensión, y tras una confirmación explícita. Restaura archivos por copia verificada con SHA-256 antes de retirar el origen, resuelve colisiones sin sobrescribir y elimina únicamente esos ficheros de firma y carpetas vacías. No existe reparación automática al insertar una unidad.
- **Compatibilidad amplia**: atiende Windows desde Vista hasta 11 (x86 y x64), además de macOS, Linux y los Unix con backend POSIX genérico (BSD, Solaris/illumos, AIX). En Windows XP/2000/Server 2003 explica por escrito por qué no puede ejecutarse, en vez de fallar con un error críptico.
- **Temas de interfaz**: cinco paletas profesionales (menú *Ver → Tema*), selector de **color de acento** con muestrario y color personalizado (*Ver → Color de acento*) y cuatro **tamaños de letra** (*Ver → Tamaño de letra*). Todas las combinaciones cumplen contraste WCAG AA y la preferencia se guarda en `%USERPROFILE%\Antivirus_EACoreServer_Logs\config.json`.
- **Ayuda visual**: pestaña **Ayuda** con guía paso a paso, leyenda de estados, diagrama de la firma del malware, notas de seguridad y preguntas frecuentes; ayuda emergente (*tooltip*) en cada control y asistente de bienvenida en el primer arranque. Se abre con **F1** o **Ctrl+H**.

## Principios de seguridad

`EACoreServer.exe` fue distribuido por productos legítimos de EA/Origin. Por eso, un nombre de archivo, una ruta histórica o una carpeta llamada `Kaspersky` no demuestran por sí solos una infección. Antes de eliminar un archivo, valide su firma digital, origen y contexto. La herramienta no sustituye a Microsoft Defender ni a un antivirus con firmas actualizadas.



---

## Compatibilidad por sistema operativo

El piso del proyecto es **Python 3.8** porque es el último intérprete con instalador
para Windows Vista, 7 y 8.0: desde Python 3.9 el ejecutable ni siquiera arranca en
esos sistemas.

| Sistema | Python utilizable | Estado |
|---------|-------------------|--------|
| Windows 2000 / XP / Server 2003 | 3.4 (último con instalador) | ❌ **No soportado**: las dependencias (`requests`, `Pillow`) exigen 3.8+ |
| Windows Vista | **solo 3.8** | ✅ Soporte completo |
| Windows 7 | **solo 3.8** + update `KB2533623` | ✅ Soporte completo |
| Windows 8.0 | **solo 3.8** | ✅ Soporte completo |
| Windows 8.1 | 3.8 a 3.12 | ✅ Soporte completo |
| Windows 10 / 11 | cualquier Python soportado | ✅ Soporte completo |
| macOS | 3.8+ | ✅ Soporte completo (modo diagnóstico) |
| Linux | 3.8+ | ✅ Soporte completo (modo diagnóstico) |
| FreeBSD / OpenBSD / NetBSD / DragonFly | 3.8+ | 🩺 Solo diagnóstico |
| Solaris / illumos | 3.8+ | 🩺 Solo diagnóstico |
| AIX | 3.8+ | 🩺 Solo diagnóstico |
| Otros Unix no reconocidos | 3.8+ | 🩺 Solo diagnóstico, con aviso |

> **Para el mayor alcance posible** (de Vista a 11, x86 y x64) construya el
> ejecutable con **Python 3.8 de 32 bits**: un binario de 32 bits también funciona
> en un Windows de 64 bits, pero no al revés.

La aplicación comprueba en este orden y **antes de abrir la ventana**: versión del
intérprete, sistema operativo y privilegios. Si el sistema no está soportado muestra
un diálogo con la explicación y la alternativa, y registra el motivo en el log.

## Requisitos del Sistema

- **SO**: Windows Vista o superior, macOS 12+, Linux, BSD, Solaris/illumos o AIX, con `tkinter`
- **Python**: 3.8 o superior (3.12 recomendado en Windows 10/11)
- **Permisos**: se recomienda Administrador en Windows, `root` en Linux y privilegios
  de administrador en macOS para la funcionalidad completa
- **Arquitectura**: x86 o x64 en Windows; x64 y arm64 en macOS y Linux

> **Compatibilidad multiplataforma.** El código Win32 (`pywin32`, `ctypes.windll`,
> IOCTLs y la ventana `WM_DEVICECHANGE`) está aislado en `usb_monitor_windows.py` y
> solo se importa en Windows. `usb_monitor.py` es una fachada portable que en macOS
> usa `diskutil`, en Linux `/proc/mounts` + `/sys/block` y en BSD/Solaris/AIX un
> backend POSIX genérico basado en `df -kP` y `mount`. La elevación de privilegios
> usa `ShellExecuteW` en Windows, `osascript` en macOS y `pkexec`/`sudo`/`doas` en
> Linux y BSD.
>
> La **reparación real** sigue dirigida a unidades con la estructura del malware; en
> macOS, Linux y el resto de Unix la herramienta opera en modo de diagnóstico y
> prueba. En los sistemas POSIX genéricos la detección de medios extraíbles es
> deliberadamente conservadora: ante la duda la unidad se marca como no reparable.

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

## Personalización de la interfaz

Todo se cambia en vivo desde el menú **Ver** y se guarda automáticamente en
`%USERPROFILE%\Antivirus_EACoreServer_Logs\config.json`
(`~/.config` no se usa; en Linux y macOS es `~/Antivirus_EACoreServer_Logs/config.json`).

### Tema

| Paleta | Carácter |
|--------|----------|
| **Grafito Oscuro** | Neutro y descansado para sesiones largas. Por defecto. |
| **Claro Neutro** | Fondo claro para entornos muy iluminados o impresión. |
| **Azul Corporativo** | Azul oscuro profesional, tono de herramienta de TI. |
| **Verde Esmeralda** | Verde profundo, acento distintivo. |
| **Alto Contraste** | Negro y blanco puros. Cumple **WCAG AAA** (contraste ≥ 7:1). |
| **Seguir al Sistema** | Detecta el modo claro u oscuro del sistema operativo. |

### Color de acento

Además del acento propio de cada paleta hay ocho colores sugeridos y un selector
libre (`Ver → Color de acento → Personalizado…`). Al elegir uno, la aplicación
**recalcula** los tonos derivados (acento claro, oscuro, selección) y elige el
color del texto sobre el acento **por contraste**, no a mano: con un amarillo
brillante el texto pasa a negro y con un violeta profundo a blanco.

Los colores semánticos se conservan a propósito: el rojo sigue significando error
aunque el acento también sea rojizo, para no perder el significado del estado.

### Tamaño de letra

Cuatro escalas —**Pequeño**, **Normal**, **Grande** y **Muy grande**— que afectan
a toda la interfaz, incluidas las tablas, el registro y la ayuda. Pensado para
pantallas de portátil y para usuarios que necesitan letra más grande.

`Ver → Restablecer apariencia` devuelve tema, acento y escala a sus valores por
defecto.

> **Accesibilidad verificada.** Las cinco paletas, los ocho acentos sugeridos y
> los tintes de fila de la tabla de unidades cumplen el criterio **AA de WCAG 2.1**
> (contraste ≥ 4,5:1 para texto normal). Está comprobado por
> `tests/test_temas.py` en cada ejecución del CI, no a ojo.

---

## Ayuda visual para el usuario final

La pestaña **Ayuda** (o **F1** / **Ctrl+H**) reúne lo que un usuario no técnico
necesita para usar la herramienta sin miedo:

- **Guía paso a paso** en cinco pasos, desde conectar la unidad hasta verificar
  el resultado.
- **Leyenda de estados** con el icono, el color y la explicación de cada uno de
  los ocho estados que puede mostrar la tabla de unidades.
- **Diagrama de la firma del malware**: la estructura `Kaspersky\Usb Drive\3.0`
  dibujada en ASCII, señalando dónde quedan ocultos los archivos originales del
  usuario y cuáles son los ficheros de firma que se eliminan.
- **Qué hace cada botón**, distinguiendo las acciones de solo diagnóstico de las
  que borran algo.
- **Notas de seguridad**, incluido el aviso de que `EACoreServer.exe` fue
  distribuido legítimamente por EA/Origin y de que conviene hacer copia de
  seguridad antes de reparar.
- **Preguntas frecuentes** y la **información del sistema** detectado, con su
  nivel de soporte.
- **Exportar la guía** a un archivo de texto para imprimirla o adjuntarla.

Además:

- **Tooltips** en cada botón, tabla, barra de progreso y registro: al dejar el
  ratón encima aparece una frase breve que explica la acción.
- **Asistente de bienvenida** la primera vez que se abre la aplicación, que
  resume las tres funciones y recuerda que nada se repara automáticamente. Solo
  se muestra una vez.
- **Barra de estado** con el sistema operativo, la arquitectura y el nivel de
  soporte detectados, siempre visible.
- `Ayuda → Comprobar compatibilidad del sistema` abre un diálogo con el detalle
  completo de la plataforma.

> La leyenda y la tabla de unidades **no pueden contradecirse**: el texto, el
> icono, el color y el tag de cada estado salen de un único catálogo en
> `ayuda.py` (`ESTADOS_UNIDAD`). `tests/test_ayuda.py` falla si alguien vuelve a
> escribir un estado a mano en `gui.py`.

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
| `main.py` | Punto de entrada principal. Verifica intérprete, sistema y permisos, y lanza la GUI |
| `gui.py` | Interfaz gráfica completa con tkinter (4 pestañas: procesos, unidades, log y ayuda) |
| `compat.py` | Detección de plataforma, matriz de soporte por versión de Windows y mensajes de no soporte |
| `temas.py` | Motor de temas sin tkinter: 5 paletas, acento personalizable, escalas de letra y validación WCAG |
| `ayuda.py` | Contenido de la ayuda visual, catálogo único de estados de unidad, traducción de estados de reparación y clase `ToolTip` |
| `scraper.py` | Consulta HTTPS y validación de rutas candidatas de processchecker.com |
| `process_manager.py` | Diagnóstico de procesos y protección de rutas típicas EA/Origin |
| `usb_monitor.py` | Fachada multiplataforma del monitor USB (Windows, macOS, Linux y POSIX genérico) |
| `usb_monitor_windows.py` | Backend exclusivo de Windows: `pywin32`, IOCTLs y `WM_DEVICECHANGE` |
| `repair_engine.py` | Detección por firma exacta y restauración verificada con SHA-256 |
| `logger.py` | Sistema de logging centralizado (consola + archivo) |
| `requirements.txt` | Dependencias Python (`pywin32` marcado solo para Windows) |
| `requirements-dev.txt` | Dependencias de empaquetado (PyInstaller) |
| `Antivirus_EACoreServer.spec` | Configuración de PyInstaller |
| `tests/test_repair_engine.py` | Pruebas de firma exacta, SHA-256, colisiones y preservación |
| `tests/test_scraper_rutas.py` | Pruebas de las 52 rutas únicas sin duplicados |
| `tests/test_multiplataforma.py` | Pruebas de importación y comportamiento en los 3 SO |
| `tests/test_compat.py` | Matriz de soporte por versión de Windows y familias Unix (33 pruebas) |
| `tests/test_temas.py` | Contraste WCAG, acentos personalizados, escalas y fuentes (66 pruebas) |
| `tests/test_ayuda.py` | Contenido de la ayuda, consistencia leyenda ↔ tabla y estados de reparación (67 pruebas) |
| `tests/test_piso_python38.py` | Garantiza que el código siga siendo válido en Python 3.8 (12 pruebas) |
| `tests/test_gui_headless.py` | Construye la ventana real y ejercita todos los temas (25 pruebas) |

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

### La aplicación no arranca en Windows 7, 8 o Vista

Python 3.9 y posteriores **no se instalan** en esos sistemas: el intérprete ni
siquiera arranca. Use **Python 3.8**, que es el último con instalador para
Vista, 7 y 8.0.

En **Windows 7** además hace falta el update
[`KB2533623`](https://support.microsoft.com/kb/2533623), porque Python 3.8 usa
APIs de carga de DLL que ese sistema no trae de serie. Sin él, la instalación
termina pero el intérprete falla al iniciar.

Para **Windows 8.1** puede usar de Python 3.8 a 3.12.

Si el ejecutable se construyó con PyInstaller, reconstrúyalo con Python 3.8 de
32 bits: ese binario funciona en todas las versiones anteriores y en los Windows
de 64 bits.

### En Windows XP aparece un aviso y la aplicación se cierra

Es el comportamiento previsto. El último Python con instalador para Windows XP
es **3.4.4** (2016), y las dependencias del proyecto (`requests`, `Pillow`)
exigen Python 3.8 o superior. No hay forma de hacerlo funcionar sin reescribir
la aplicación contra un intérprete de hace una década.

El aviso lo explica por escrito y sugiere la alternativa: atender esa unidad
desde un equipo con Windows 7 o superior. La unidad USB se puede conectar en
cualquier otro equipo compatible.

### En Linux, BSD o macOS la reparación aparece bloqueada

Es deliberado. La reparación está diseñada para unidades con la estructura del
malware en un medio extraíble, y la enumeración fiable de medios extraíbles
depende de las APIs de Windows. Fuera de Windows la herramienta opera en **modo
de diagnóstico**: lista las unidades, analiza la firma y explica qué encontró,
pero no modifica nada.

En BSD, Solaris y AIX la detección usa un backend POSIX genérico (`df -kP` y
`mount`) y es **conservadora a propósito**: ante la duda marca la unidad como no
reparable.

### El scraping no funciona
- Se usa fallback automático con 52 rutas locales únicas
- Verifique conectividad a internet
- La URL `https://processchecker.com/file/EACoreServer.exe.html` puede estar caída

---

## Pruebas

Las pruebas no requieren una unidad USB física ni `pywin32`:

```bash
python -m py_compile main.py gui.py logger.py process_manager.py repair_engine.py scraper.py usb_monitor.py usb_monitor_windows.py compat.py temas.py ayuda.py
python -m unittest discover -s tests -v
```

En Linux hace falta una pantalla para las pruebas de la interfaz; use Xvfb:

```bash
xvfb-run -a python -m unittest discover -s tests -v
```

**257 pruebas** cubren (el número de omitidas varía según el SO y la pantalla):

- ausencia de firma, firma incompleta y `.dat` completos sin fichero numérico;
- confirmación de la firma exacta con varios ficheros numéricos sin extensión;
- restauración con verificación SHA-256 y auditoría de las sumas;
- copia corrupta: el origen **no** se retira cuando el SHA-256 no coincide;
- resolución de colisiones y preservación de contenido no reconocido;
- enlaces simbólicos no seguidos;
- las 52 rutas únicas sin duplicados y su fusión con las rutas remotas;
- importación y comportamiento multiplataforma en Windows, macOS y Linux;
- la clasificación de cada edición de Windows (XP no soportado, Vista/7/8 con
  Python 3.8, 8.1 hasta 3.12) y de BSD, Solaris, AIX y sistemas desconocidos;
- contraste WCAG AA de las cinco paletas, de los ocho acentos sugeridos y de los
  tintes de fila, además de la legibilidad del texto sobre acentos extremos;
- que la leyenda de estados describa exactamente los textos que muestra la tabla;
- que todo estado del motor de reparación tenga traducción legible y que una
  reparación con errores no se muestre como si hubiera terminado bien;
- que el código siga siendo sintáctica y semánticamente válido en Python 3.8;
- la construcción real de la ventana y la aplicación de todas las combinaciones
  de tema, acento y tamaño de letra (se omite si no hay pantalla disponible).

`py_compile` solo valida sintaxis y no importa los módulos, por eso
`usb_monitor_windows.py` puede compilarse también en Ubuntu y macOS.

### Integración continua

El flujo `.github/workflows/ci.yml` ejecuta cinco combinaciones sin `fail-fast`,
para que cada una reporte su resultado aunque otra falle:

| Sistema | Python |
|---------|--------|
| Ubuntu (latest) | 3.12 |
| macOS (latest) | 3.12 |
| Windows (latest) | 3.12 |
| Windows (latest) | **3.8** ← piso de Vista/7/8 |
| Ubuntu 22.04 | **3.8** ← piso de Vista/7/8 |

Cada combinación comprueba la sintaxis de los once módulos, la compatibilidad con
Python 3.8, las pruebas unitarias, las 52 rutas únicas y el contraste WCAG de las
paletas. En Linux se instala **Xvfb** y hay un paso que **falla si las pruebas de
la interfaz se omiten**, para que un entorno roto no pase desapercibido.

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
*Versión: 1.2.0*
*Python 3.8+ | Windows Vista a 11 (x86 y x64) · macOS · Linux · BSD · Solaris/illumos · AIX*
