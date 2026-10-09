# Antivirus EACoreServer

Aplicación de escritorio en Python 3.8+ para **diagnosticar** la estructura USB `Kaspersky\Usb Drive` y gestionar procesos llamados `EACoreServer.exe`. Interfaz gráfica profesional en español con componentes modernos (botones con efecto *hover*, tarjetas agrupadoras, menús contextuales en tablas, notificaciones *toast*, barra de búsqueda en el registro e indicadores de estado en tiempo real), cinco paletas de color personalizables, ayuda visual integrada y controles conservadores para evitar cambios accidentales.

Funciona en Windows Vista, 7, 8, 8.1, 10 y 11 (x86 y x64), macOS, Linux, FreeBSD, OpenBSD, NetBSD, DragonFly, Solaris/illumos y AIX.

---

## Tabla de Contenidos

1. [¿Qué hace esta aplicación?](#1-qué-hace-esta-aplicación)
2. [Compatibilidad por sistema operativo](#2-compatibilidad-por-sistema-operativo)
3. [PARTE I — Usuario final: instalar y usar](#parte-i--usuario-final-instalar-y-usar)
   - [Opción A: Usar el ejecutable ya compilado](#opción-a-usar-el-ejecutable-ya-compilado)
   - [Opción B: Instalar desde el instalador Inno Setup](#opción-b-instalar-desde-el-instalador-inno-setup)
4. [PARTE II — Desarrollador: ejecutar desde el código fuente](#parte-ii--desarrollador-ejecutar-desde-el-código-fuente)
   - [Paso 1: Clonar el repositorio](#paso-1-clonar-el-repositorio)
   - [Paso 2: Instalar Python 3.8+](#paso-2-instalar-python-38)
   - [Paso 3: Crear entorno virtual](#paso-3-crear-entorno-virtual)
   - [Paso 4: Instalar dependencias](#paso-4-instalar-dependencias)
   - [Paso 5: Verificar la instalación](#paso-5-verificar-la-instalación)
   - [Paso 6: Ejecutar la aplicación](#paso-6-ejecutar-la-aplicación)
   - [Paso 7: Ejecutar con permisos de administrador](#paso-7-ejecutar-con-permisos-de-administrador)
5. [PARTE III — Compilar el ejecutable (.exe)](#parte-iii--compilar-el-ejecutable-exe)
   - [Requisito crítico: Python 3.8 de 32 bits](#requisito-crítico-python-38-de-32-bits)
   - [Paso 1: Instalar Python 3.8 de 32 bits](#paso-1-instalar-python-38-de-32-bits)
   - [Paso 2: Clonar el repositorio](#paso-2-clonar-el-repositorio)
   - [Paso 3: Crear entorno virtual con Python 3.8](#paso-3-crear-entorno-virtual-con-python-38)
   - [Paso 4: Instalar dependencias de desarrollo](#paso-4-instalar-dependencias-de-desarrollo)
   - [Paso 5: Verificar que Python es 3.8 x86](#paso-5-verificar-que-python-es-38-x86)
   - [Paso 6: Compilar con build.bat (recomendado)](#paso-6-compilar-con-buildbat-recomendado)
   - [Paso 7: Compilar manualmente con PyInstaller (alternativo)](#paso-7-compilar-manualmente-con-pyinstaller-alternativo)
   - [Paso 8: Verificar el ejecutable generado](#paso-8-verificar-el-ejecutable-generado)
6. [PARTE IV — Crear el instalador con Inno Setup](#parte-iv--crear-el-instalador-con-inno-setup)
   - [Paso 1: Compilar el ejecutable](#paso-1-compilar-el-ejecutable)
   - [Paso 2: Descargar e instalar Inno Setup](#paso-2-descargar-e-instalar-inno-setup)
   - [Paso 3: Preparar el icono](#paso-3-preparar-el-icono)
   - [Paso 4: Compilar el instalador](#paso-4-compilar-el-instalador)
   - [Paso 5: Probar el instalador](#paso-5-probar-el-instalador)
7. [Personalización de la interfaz](#personalización-de-la-interfaz)
8. [Ayuda visual para el usuario final](#ayuda-visual-para-el-usuario-final)
9. [Atajos de teclado](#atajos-de-teclado)
10. [Módulos del proyecto](#módulos-del-proyecto)
11. [Firma USB atendida](#firma-usb-atendida)
12. [Principios de seguridad](#principios-de-seguridad)
13. [Manejo de errores](#manejo-de-errores)
14. [Solución de problemas completa](#solución-de-problemas-completa)
15. [Pruebas automatizadas](#pruebas-automatizadas)
16. [Logging](#logging)
17. [Integración continua](#integración-continua)
18. [Licencia](#licencia)
19. [Soporte](#soporte)

---

## 1. ¿Qué hace esta aplicación?

**Antivirus EACoreServer** es una utilidad de diagnóstico y reparación conservadora diseñada para:

- **Consulta HTTPS de rutas**: obtiene rutas históricas candidatas de `EACoreServer.exe` desde `https://processchecker.com/file/EACoreServer.exe.html` y las combina con una lista local de 52 rutas para funcionar sin conexión. Las rutas son datos de diagnóstico, **no indicadores de malware**.
- **Gestión protegida de procesos**: muestra procesos `EACoreServer.exe` y permite finalizarlos con confirmación. Las rutas típicas de EA/Origin y sus juegos se identifican como posibles componentes legítimos y quedan protegidas contra eliminación por nombre.
- **Monitoreo de unidades USB**: detecta automáticamente unidades conectadas. Solo memorias extraíbles y discos USB físicos se habilitan para reparación; discos internos y de red son de solo diagnóstico.
- **Reparación conservadora y manual**: solo repara después de encontrar la firma exacta `Kaspersky\Usb Drive\3.0` con `5.dat`, `6.dat`, `7.dat` y un fichero numérico sin extensión, y tras una confirmación explícita del usuario. Restaura archivos por copia verificada con SHA-256 antes de retirar el origen, resuelve colisiones sin sobrescribir y elimina únicamente esos ficheros de firma y carpetas vacías. **No existe reparación automática al insertar una unidad.**
- **Compatibilidad amplia**: atiende Windows desde Vista hasta 11 (x86 y x64), además de macOS, Linux y los Unix con backend POSIX genérico (BSD, Solaris/illumos, AIX).
- **Interfaz profesional**: botones con efecto *hover*, tarjetas agrupadoras, menús contextuales en tablas (clic derecho), notificaciones *toast* no bloqueantes, barra de búsqueda en el registro, indicadores de estado en tiempo real y barra de progreso con porcentaje.
- **Temas de interfaz**: cinco paletas profesionales (menú *Ver → Tema*), selector de **color de acento** con muestrario y color personalizado (*Ver → Color de acento*) y cuatro **tamaños de letra** (*Ver → Tamaño de letra*). Todas las combinaciones cumplen contraste WCAG AA.
- **Ayuda visual integrada**: pestaña **Ayuda** con guía paso a paso, leyenda de estados, diagrama de la firma del malware, notas de seguridad y preguntas frecuentes; ayuda emergente (*tooltip*) en cada control y asistente de bienvenida en el primer arranque. Se abre con **F1** o **Ctrl+H**.
- **Diagnóstico preventivo**: detecta DLLs del sistema faltantes (`api-ms-win-core-path-l1-1-0.dll`) y carpetas temporales problemáticas **antes** de que la aplicación falle, mostrando mensajes claros en español.

---

## 2. Compatibilidad por sistema operativo

El piso del proyecto es **Python 3.8** porque es el último intérprete con instalador para Windows Vista, 7 y 8.0: desde Python 3.9 el ejecutable ni siquiera arranca en esos sistemas.

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
| FreeBSD / OpenBSD / NetBSD / DragonFly | 3.8+ |  Solo diagnóstico |
| Solaris / illumos | 3.8+ | 🩺 Solo diagnóstico |
| AIX | 3.8+ | 🩺 Solo diagnóstico |
| Otros Unix no reconocidos | 3.8+ |  Solo diagnóstico, con aviso |

> **Para el mayor alcance posible** (de Vista a 11, x86 y x64) construya el ejecutable con **Python 3.8 de 32 bits**: un binario de 32 bits también funciona en un Windows de 64 bits, pero no al revés.

La aplicación comprueba en este orden y **antes de abrir la ventana**: DLLs del sistema, versión del intérprete, sistema operativo y privilegios. Si algo no está soportado muestra un diálogo con la explicación y la alternativa, y registra el motivo en el log.

---

## PARTE I — Usuario final: instalar y usar

Si no quiere compilar nada y solo desea usar la aplicación, tiene dos opciones:

### Opción A: Usar el ejecutable ya compilado

**Requisito previo:** El ejecutable debe haber sido compilado con Python 3.8 de 32 bits (el desarrollador se encarga de esto). Si no fue así, aparecerá el error *"Falta api-ms-win-core-path-l1-1-0.dll"* en Windows 7/8.

1. **Descargue** el archivo `Antivirus_EACoreServer.exe` desde la sección *Releases* del repositorio o recíbelo de su administrador de TI.
2. **Haga doble clic** en el archivo `.exe`.
3. Si Windows muestra el aviso de **SmartScreen** o *"¿Desea permitir que esta aplicación haga cambios?"*, pulse **Sí** (la aplicación necesita permisos de administrador para gestionar procesos y unidades USB).
4. La aplicación se abrirá mostrando la ventana principal con tres pestañas: **Gestión de procesos**, **Reparación de unidades** y **Registro**.
5. Conecte una unidad USB si desea diagnosticarla; la aplicación la detectará automáticamente en un segundo.
6. Use **F1** en cualquier momento para abrir la guía completa de uso.

**Si aparece un error al abrir el .exe**, consulte la sección [Solución de problemas completa](#14-solución-de-problemas-completa).

### Opción B: Instalar desde el instalador Inno Setup

1. **Descargue** el archivo `Antivirus_EACoreServer_Setup.exe`.
2. **Haga doble clic** en el instalador.
3. Siga el asistente: acepte la licencia, elija la carpeta de instalación (por defecto `C:\Program Files\Antivirus EACoreServer`) y marque *"Crear acceso directo en el escritorio"* si lo desea.
4. Al finalizar, marque *"Ejecutar Antivirus EACoreServer"* y pulse *Finalizar*.
5. La aplicación se abrirá automáticamente. Encontrará un acceso directo en el menú Inicio → *Antivirus EACoreServer*.

**Para desinstalar:** Menú Inicio → *Antivirus EACoreServer* → *Desinstalar Antivirus EACoreServer*, o desde *Panel de control → Programas y características*.

---

## PARTE II — Desarrollador: ejecutar desde el código fuente

Siga estos pasos en orden para ejecutar la aplicación directamente desde el código fuente.

### Paso 1: Clonar el repositorio

Abra una terminal o símbolo del sistema y ejecute:

```bash
git clone https://github.com/yhquintero/Antivirus_EACoreServer.git
cd Antivirus_EACoreServer
```

Si no tiene `git`, descargue el ZIP desde GitHub y extráigalo en una carpeta de su elección.

### Paso 2: Instalar Python 3.8+

La aplicación requiere **Python 3.8 o superior**. La versión recomendada depende de su sistema:

| Sistema | Versión recomendada | Enlace de descarga |
|---------|--------------------|--------------------|
| Windows 10/11 | Python 3.12 (última estable) | https://www.python.org/downloads/ |
| Windows 8.1 | Python 3.12 | https://www.python.org/downloads/release/python-3127/ |
| Windows 7 / Vista / 8.0 | **Python 3.8.20** (última compatible) | https://www.python.org/downloads/release/python-3820/ |
| macOS 12+ | Python 3.12 | https://www.python.org/downloads/ |
| Linux (Ubuntu/Debian) | Python 3.8+ del repositorio | `sudo apt install python3 python3-venv python3-tk` |

**Al instalar Python en Windows:**
- ✅ Marque la casilla **"Add Python to PATH"** (imprescindible).
- ✅ Marque **"Install launcher for all users"** (recomendado).
- ✅ Pulse **"Install Now"**.

**Verificar la instalación:**

```bash
python --version
```

Debe mostrar `Python 3.8.X` o superior. Si muestra un error, Python no está en el PATH.

### Paso 3: Crear entorno virtual

Se recomienda trabajar en un entorno virtual para no contaminar el Python del sistema:

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\activate
```

**Windows (CMD):**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

El prompt cambiará mostrando `(venv)` al inicio, indicando que el entorno virtual está activo.

**Para salir del entorno virtual** en cualquier momento:
```bash
deactivate
```

### Paso 4: Instalar dependencias

Con el entorno virtual activado, instale las dependencias principales:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Esto instalará:
- `requests` — Consultas HTTPS a processchecker.com
- `beautifulsoup4` — Parseo de HTML
- `psutil` — Información de procesos del sistema
- `pystray` — Icono en la bandeja del sistema
- `Pillow` — Procesamiento de imágenes (para pystray)
- `pywin32` — API de Windows (solo en Windows, ignorado en macOS/Linux)

### Paso 5: Verificar la instalación

Compruebe que todas las dependencias se instalaron correctamente:

```bash
python -c "import tkinter; import psutil; import requests; print('Todas las dependencias OK')"
```

En Windows, además verifique `pywin32`:
```bash
python -c "import win32api; print('pywin32 OK')"
```

Si alguna importación falla, vuelva al Paso 4 y revise los mensajes de error de `pip`.

### Paso 6: Ejecutar la aplicación

Desde la carpeta del proyecto, con el entorno virtual activado:

```bash
python main.py
```

O alternativamente:
```bash
python gui.py
```

La ventana principal se abrirá mostrando las pestañas de Gestión de procesos, Reparación de unidades y Registro.

### Paso 7: Ejecutar con permisos de administrador

Para funcionalidad completa (finalizar procesos, detener servicios, reparar unidades) se recomiendan permisos elevados:

**Windows (PowerShell como administrador):**
```powershell
python main.py
```

**Windows (desde CMD normal, la app solicitará elevación):**
```cmd
python main.py
```
La aplicación mostrará un diálogo pidiendo confirmación para re-ejecutarse como administrador.

**Windows (ejecución explícita como admin):**
```cmd
runas /user:Administrador python main.py
```

**Linux:**
```bash
sudo python3 main.py
```

**macOS:**
```bash
sudo python3 main.py
```

---

## PARTE III — Compilar el ejecutable (.exe)

️ **Esta sección es para desarrolladores que quieren generar un ejecutable distribuible.**

### Requisito crítico: Python 3.8 de 32 bits

> **Regla de oro:** El ejecutable **debe** compilarse siempre con **Python 3.8 de 32 bits (x86)** para garantizar compatibilidad con Windows 7, 8, 8.1, 10 y 11.
>
> - Python 3.9+ **no funciona en Windows 7/8/Vista** (requiere `api-ms-win-core-path-l1-1-0.dll` inexistente en esos sistemas).
> - Un binario de 32 bits **funciona tanto en Windows de 32 como de 64 bits** (vía WOW64).
> - Un binario de 64 bits **solo funciona en Windows de 64 bits**.
> - PyInstaller ≥ 6.1.0 eliminó soporte para Python 3.8; se usa `pyinstaller>=5.13.2,<6.1.0`.

### Paso 1: Instalar Python 3.8 de 32 bits

1. **Desinstale** cualquier otra versión de Python que tenga (opcional pero recomendado para evitar conflictos de PATH).
2. **Descargue** Python 3.8.20 de 32 bits desde: https://www.python.org/downloads/release/python-3820/
   - Elija el instalador **"Windows installer (32-bit)"** (NO el de 64 bits).
3. **Ejecute** el instalador `python-3.8.20.exe`.
4. **Marque** las casillas:
   - ✅ "Add Python 3.8 to PATH"
   - ✅ "Install launcher for all users"
5. Pulse **"Install Now"**.
6. **Verifique** la instalación abriendo una nueva terminal:

```bash
python --version
```
Debe mostrar `Python 3.8.20`.

```bash
python -c "import struct; print(f'{struct.calcsize(\"P\") * 8} bits')"
```
Debe mostrar `32 bits`. Si muestra `64 bits`, instaló la versión incorrecta.

### Paso 2: Clonar el repositorio

```bash
git clone https://github.com/yhquintero/Antivirus_EACoreServer.git
cd Antivirus_EACoreServer
```

### Paso 3: Crear entorno virtual con Python 3.8

```bash
python -m venv venv
```

**Windows (PowerShell):**
```powershell
.\venv\Scripts\activate
```

**Windows (CMD):**
```cmd
venv\Scripts\activate.bat
```

**macOS / Linux:**
```bash
source venv/bin/activate
```

### Paso 4: Instalar dependencias de desarrollo

```bash
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

`requirements-dev.txt` incluye `requirements.txt` (dependencias de ejecución) más `pyinstaller>=5.13.2,<6.1.0`.

### Paso 5: Verificar que Python es 3.8 x86

Antes de compilar, confirme que está usando la versión correcta:

```bash
python -c "import sys, struct; print(f'Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} ({struct.calcsize(\"P\") * 8} bits)')"
```

Salida esperada: `Python 3.8.20 (32 bits)`

Si no coincide, vuelva al Paso 1.

### Paso 6: Compilar con build.bat (recomendado)

El script `build.bat` automatiza todo el proceso de compilación con verificaciones integradas:

```cmd
build.bat
```

**Qué hace `build.bat` automáticamente:**
1. Verifica que Python está en el PATH.
2. Comprueba que la versión es **exactamente 3.8** (rechaza 3.9, 3.10, 3.11, 3.12…).
3. Verifica que la arquitectura es **32 bits** (rechaza 64 bits).
4. Instala PyInstaller si no está presente.
5. Instala las dependencias si faltan.
6. Limpia los directorios `build/` y `dist/` anteriores.
7. Ejecuta PyInstaller con la configuración del archivo `.spec`.

Si alguna verificación falla, `build.bat` muestra un mensaje detallado explicando la causa y la solución, y se detiene sin compilar.

Al finalizar exitosamente, el ejecutable estará en:
```
dist\Antivirus_EACoreServer.exe
```

### Paso 7: Compilar manualmente con PyInstaller (alternativo)

Si prefiere compilar sin `build.bat`:

```bash
pyinstaller Antivirus_EACoreServer.spec --clean --noconfirm
```

El archivo `.spec` ya tiene configuradas las opciones óptimas para Windows 7+:
- `upx=False` — Evita problemas de carga de DLLs y falsos positivos en antivirus.
- `runtime_tmpdir` — Directorio temporal en carpeta de usuario (evita `C:\Windows\TEMP`).
- `target_arch='x86'` — Binario de 32 bits.
- Manifiesto con compatibilidad explícita para Windows Vista a 11.
- `hiddenimports` completos para todos los módulos.

**Opciones adicionales de PyInstaller:**

```bash
# Ver los módulos incluidos (modo depuración)
pyinstaller --debug all Antivirus_EACoreServer.spec

# Cambiar a modo consola (útil para depurar)
# Edite el .spec: console=True, luego:
pyinstaller Antivirus_EACoreServer.spec --clean --noconfirm

# Volver a modo ventana (producción)
# Edite el .spec: console=False, luego:
pyinstaller Antivirus_EACoreServer.spec --clean --noconfirm
```

**Si obtiene errores de módulos faltantes**, agréguelos a `hiddenimports` en el `.spec`:

```python
hiddenimports=[
    'usb_monitor_windows',
    'tkinter', 'tkinter.ttk', 'tkinter.scrolledtext',
    'tkinter.messagebox', 'tkinter.filedialog',
    'requests', 'bs4', 'psutil', 'pystray', 'PIL', 'PIL.Image',
],
```

### Paso 8: Verificar el ejecutable generado

1. **Ubique** el ejecutable en `dist\Antivirus_EACoreServer.exe`.
2. **Ejecútelo** con doble clic.
3. **Compruebe** que:
   - La ventana se abre sin errores.
   - La barra de estado muestra el sistema operativo detectado correctamente.
   - En *Ayuda → Comprobar compatibilidad del sistema*, el nivel de soporte es "completo".
   - Las pestañas funcionan y los botones responden.
4. **Pruebe en Windows 7** (máquina virtual o equipo real) si ese es su objetivo.

---

## PARTE IV — Crear el instalador con Inno Setup

Para distribuir la aplicación con un instalador profesional en Windows.

### Paso 1: Compilar el ejecutable

Complete primero la [PARTE III](#parte-iii--compilar-el-ejecutable-exe) para generar `dist\Antivirus_EACoreServer.exe`.

### Paso 2: Descargar e instalar Inno Setup

1. Descargue Inno Setup desde: https://jrsoftware.org/isdl.php
2. Elija la versión **"Inno Setup 6.x.x"** (la más reciente).
3. Ejecute el instalador y acepte las opciones por defecto.
4. Inno Setup se instalará en `C:\Program Files (x86)\Inno Setup 6\`.

### Paso 3: Preparar el icono

El instalador busca un archivo `icono.ico` en la carpeta del proyecto:

1. Consiga o cree un icono `.ico` de 256×256 píxeles (puede convertir un PNG con herramientas online).
2. Colóquelo en la raíz del proyecto como `icono.ico`.
3. Si no tiene icono, el instalador usará el icono por defecto de Inno Setup.

### Paso 4: Compilar el instalador

**Desde la línea de comandos** (PowerShell o CMD):

```powershell
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

**O desde el IDE de Inno Setup:**
1. Abra Inno Setup.
2. File → Open → seleccione `installer.iss`.
3. Build → Compile (o pulse F9).

El instalador se generará en:
```
dist\Antivirus_EACoreServer_Setup.exe
```

### Paso 5: Probar el instalador

1. **Ejecute** `dist\Antivirus_EACoreServer_Setup.exe` en una máquina limpia (o máquina virtual).
2. Siga el asistente de instalación.
3. Verifique que:
   - La aplicación se instala en `C:\Program Files\Antivirus EACoreServer\`.
   - El acceso directo del menú Inicio funciona.
   - El acceso directo de escritorio (si se marcó) funciona.
   - La aplicación se ejecuta correctamente.
4. **Pruebe la desinstalación** desde *Panel de control → Programas y características*.

---

## Personalización de la interfaz

Todo se cambia en vivo desde el menú **Ver** y se guarda automáticamente en `%USERPROFILE%\Antivirus_EACoreServer_Logs\config.json` (en Linux y macOS es `~/Antivirus_EACoreServer_Logs/config.json`).

### Tema

Acceda con **Ver → Tema**:

| Paleta | Carácter | Uso recomendado |
|--------|----------|-----------------|
| **Grafito Oscuro** | Neutro y descansado | Sesiones largas, uso nocturno. **Predeterminado.** |
| **Claro Neutro** | Fondo claro | Entornos muy iluminados, impresión en pantalla |
| **Azul Corporativo** | Azul oscuro profesional | Entornos de TI, aspecto institucional |
| **Verde Esmeralda** | Verde profundo | Distinguir estados con claridad |
| **Alto Contraste** | Negro y blanco puros | Accesibilidad. Cumple **WCAG AAA** (contraste ≥ 7:1) |
| **Seguir al Sistema** | Detecta claro/oscuro del SO | Para respetar la preferencia del sistema |

### Color de acento

Acceda con **Ver → Color de acento**:

- **El de la paleta (recomendado)**: usa el acento predefinido del tema.
- **Ocho colores sugeridos**: Azul vivo, Azul institucional, Esmeralda, Violeta, Magenta, Naranja, Rojo, Cian profundo.
- **Color personalizado…**: abre el selector nativo de color del sistema para elegir cualquier color hexadecimal.

Al elegir un acento, la aplicación **recalcula automáticamente**:
- Tono claro del acento (para hover)
- Tono oscuro del acento (para pulsado)
- Color de selección
- Color del texto sobre el acento (negro sobre amarillo, blanco sobre azul, etc.)

Los colores semánticos (rojo=error, verde=éxito, naranja=advertencia) se conservan siempre, aunque el acento sea similar, para no perder el significado de los estados.

### Tamaño de letra

Acceda con **Ver → Tamaño de letra**:

| Escala | Factor | Uso |
|--------|--------|-----|
| **Pequeño** | 0.90× | Pantallas grandes, mucha información |
| **Normal** | 1.00× | **Predeterminado.** Uso general. |
| **Grande** | 1.15× | Pantallas de portátil, visión reducida |
| **Muy grande** | 1.30× | Accesibilidad, presentaciones |

**Restablecer apariencia** (Ver → Restablecer apariencia) devuelve tema, acento y escala a los valores por defecto.

> **Accesibilidad verificada.** Las cinco paletas, los ocho acentos sugeridos y los tintes de fila de la tabla de unidades cumplen el criterio **AA de WCAG 2.1** (contraste ≥ 4,5:1 para texto normal). Está comprobado por `tests/test_temas.py` en cada ejecución del CI, no a ojo.

---

## Ayuda visual para el usuario final

La pestaña **Ayuda** (o **F1** / **Ctrl+H**) reúne todo lo que un usuario no técnico necesita:

- **Guía paso a paso** en 5 pasos, desde conectar la unidad hasta verificar el resultado.
- **Leyenda de estados** con icono, color y explicación de cada uno de los 8 estados posibles.
- **Diagrama de la firma del malware** en ASCII, señalando dónde quedan ocultos los archivos originales.
- **Qué hace cada botón**, distinguiendo acciones de solo diagnóstico de las que modifican algo.
- **Notas de seguridad**, incluido el aviso de que `EACoreServer.exe` fue distribuido legítimamente por EA/Origin.
- **Preguntas frecuentes** y la **información del sistema** detectado con su nivel de soporte.
- **Exportar la guía** a un archivo de texto para imprimirla o adjuntarla a una consulta.

Además:
- **Tooltips** en cada botón, tabla, barra de progreso y registro: al dejar el ratón encima aparece una explicación breve.
- **Asistente de bienvenida** la primera vez que se abre la aplicación. Solo se muestra una vez.
- **Barra de estado** con el sistema operativo, la arquitectura y el nivel de soporte, siempre visible.
- **Notificaciones toast** no bloqueantes para confirmar acciones (unidad detectada, reparación completada, etc.).
- `Ayuda → Comprobar compatibilidad del sistema` abre un diálogo con el detalle completo de la plataforma.

> La leyenda y la tabla de unidades **no pueden contradecirse**: el texto, el icono, el color y el tag de cada estado salen de un único catálogo en `ayuda.py`. `tests/test_ayuda.py` falla si alguien escribe un estado a mano en `gui.py`.

---

## Atajos de teclado

| Atajo | Acción |
|-------|--------|
| **F1** / **Ctrl+H** | Abrir guía de uso |
| **F5** | Refrescar unidades USB |
| **Ctrl+R** | Escanear rutas EACoreServer |
| **Ctrl+L** | Limpiar el registro |
| **Ctrl+E** | Exportar el registro |
| **Ctrl+Q** | Salir de la aplicación |
| **Supr** (en tabla de procesos) | Finalizar proceso seleccionado |
| **Enter** (en tabla de unidades) | Reparar unidad seleccionada |
| **Clic derecho** (en tablas) | Menú contextual con acciones rápidas |

También disponibles en **Ayuda → Atajos de teclado**.

---

## Módulos del proyecto

| Archivo | Descripción |
|---------|-------------|
| `main.py` | Punto de entrada principal. Verifica DLLs del sistema, intérprete, sistema y permisos, y lanza la GUI |
| `gui.py` | Interfaz gráfica profesional con componentes modernos: botones con hover, tarjetas, búsqueda, menús contextuales, toasts y barra de estado con indicadores |
| `compat.py` | Detección de plataforma, matriz de soporte por versión de Windows y mensajes de no soporte |
| `win7_compat.py` | Diagnóstico preventivo en Windows 7/8: detecta DLLs faltantes (`api-ms-win-core-path-l1-1-0.dll`) y carpetas temporales problemáticas **antes** de que PyInstaller falle al cargar `python3x.dll` |
| `ui_components.py` | Componentes UI reutilizables: `BotonProfesional` (con hover), `Tarjeta`, `BarraBusqueda`, `IndicadorEstado`, `BarraProgreso`, `MenuContextual` y `DialogoProfesional` |
| `toast.py` | Sistema de notificaciones tipo *toast* no bloqueantes, apilables en la esquina de la pantalla |
| `temas.py` | Motor de temas sin tkinter: 5 paletas, acento personalizable, escalas de letra y validación WCAG |
| `ayuda.py` | Contenido de la ayuda visual, catálogo único de estados de unidad, traducción de estados de reparación y clase `ToolTip` |
| `scraper.py` | Consulta HTTPS y validación de 52 rutas candidatas de processchecker.com |
| `process_manager.py` | Diagnóstico de procesos y protección de rutas típicas EA/Origin |
| `usb_monitor.py` | Fachada multiplataforma del monitor USB (Windows, macOS, Linux y POSIX genérico) |
| `usb_monitor_windows.py` | Backend exclusivo de Windows: `pywin32`, IOCTLs y `WM_DEVICECHANGE` |
| `repair_engine.py` | Detección por firma exacta y restauración verificada con SHA-256 |
| `logger.py` | Sistema de logging centralizado (consola + archivo con rotación) |
| `requirements.txt` | Dependencias Python (`pywin32` marcado solo para Windows) |
| `requirements-dev.txt` | Dependencias de empaquetado (PyInstaller) |
| `Antivirus_EACoreServer.spec` | Configuración de PyInstaller con manifiesto de compatibilidad Win7-11 |
| `build.bat` | Script de compilación automatizado con verificaciones de Python 3.8 x86 |
| `installer.iss` | Script de Inno Setup para generar el instalador |
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
── Kaspersky\            ← carpeta que suplanta al antivirus
    └── Usb Drive\        ← aquí quedan OCULTOS sus archivos originales
        ├── documento.docx    ← SU CONTENIDO (se restaura a la raíz)
        ├── fotos\            ← SU CONTENIDO (se restaura a la raíz)
        └── 3.0\
            ├── 1337          ← fichero NUMÉRICO SIN EXTENSIÓN  ╮
            ├── 5.dat         ←                                │  firma
            ├── 6.dat         ←                                │  exacta
            └── 7.dat         ←                                ╯
```

La firma **exacta** exige los cuatro elementos a la vez:

| Elemento | Ubicación | Obligatorio |
|----------|-----------|-------------|
| `5.dat`, `6.dat`, `7.dat` | `Kaspersky\Usb Drive\3.0\` | Sí, los tres |
| Fichero numérico **sin extensión** (p. ej. `0`, `1337`, `20240517`) | `Kaspersky\Usb Drive\3.0\` | Al menos uno |

Una carpeta con el mismo nombre pero sin la firma completa queda marcada como **requiere revisión** y no se modifica. Si están los tres `.dat` pero falta el fichero numérico, el diagnóstico es **sospechoso**: los `.dat` sueltos no son prueba suficiente. Un *directorio* llamado `1234` tampoco cuenta como firma, solo archivos regulares cuyo nombre sea íntegramente numérico.

### Proceso de reparación seguro

1. Valida la firma exacta y solicita confirmación del usuario.
2. Quita atributos de oculto/sistema/solo lectura en la estructura validada (ACL de Win32 en Windows; permisos POSIX en macOS y Linux).
3. **Restaura por copia verificada, nunca con `shutil.move` a ciegas.** Cada archivo se calcula su SHA-256 en el origen, se copia al destino, se fuerza la escritura a disco con `fsync` y se vuelve a calcular el SHA-256 de la copia. **Solo si ambas sumas coinciden se retira el origen**; si difieren, la copia defectuosa se descarta y el archivo original permanece intacto.
4. Resuelve colisiones sin sobrescribir: crea un nombre con sufijo (`_1`, `_2`, …).
5. Elimina únicamente `5.dat`, `6.dat`, `7.dat` y los ficheros numéricos sin extensión dentro de `3.0\`.
6. Elimina `3.0\`, `Usb Drive\` y `Kaspersky\` **solo si están vacías**, usando `rmdir` y nunca `rmtree`. Si queda un elemento desconocido o bloqueado, lo conserva y registra el incidente.
7. No sigue enlaces simbólicos: un `symlink` dentro del USB no puede usarse para escribir fuera de él.
8. Guarda el estado de unidades completadas, las sumas SHA-256 verificadas y todas las acciones en el log.

---

## Principios de seguridad

`EACoreServer.exe` fue distribuido por productos legítimos de EA/Origin. Por eso, un nombre de archivo, una ruta histórica o una carpeta llamada `Kaspersky` no demuestran por sí solos una infección. Antes de eliminar un archivo, valide su firma digital, origen y contexto. La herramienta no sustituye a Microsoft Defender ni a un antivirus con firmas actualizadas.

**Reglas de seguridad implementadas:**
- Nunca se elimina un archivo por su nombre sin verificar su ruta.
- Las rutas típicas de EA/Origin y sus juegos quedan protegidas contra eliminación.
- La reparación nunca sobrescribe archivos existentes (usa sufijos).
- Nunca se usa borrado recursivo forzoso sobre contenido no reconocido.
- Los enlaces simbólicos no se siguen.
- Todo lo que la herramienta no identifica, lo conserva y lo registra.
- No existe reparación automática al insertar una unidad: siempre se requiere confirmación.

---

## Manejo de errores

La aplicación maneja los siguientes escenarios de error de forma conservadora:

- **Sin firma completa**: No genera fallos ni cambios; se informa como unidad limpia o que requiere revisión.
- **Archivos o carpetas bloqueados/desconocidos**: Se conservan y se reportan; no se fuerza un borrado recursivo.
- **Permisos insuficientes**: Se notifica al usuario; la finalización de procesos puede intentar `taskkill /F`.
- **Red inactiva**: Se usan las 52 rutas locales como fallback; la aplicación funciona sin internet.
- **Unidades sin formato**: Se detectan como no accesibles y se saltan con un mensaje claro.
- **DLLs del sistema faltantes** (Windows 7/8): El módulo `win7_compat.py` detecta el problema antes del arranque y muestra un diálogo explicativo.
- **Carpeta temporal no escribible**: Se detecta y se sugiere una alternativa en el perfil del usuario.
- **Copia corrupta durante reparación**: El SHA-256 de la copia no coincide con el origen → se descarta la copia y el original permanece intacto.

---

## Solución de problemas completa

### La aplicación no muestra todas las unidades

**Síntoma:** Conecta un USB pero no aparece en la pestaña "Reparación de unidades".

**Pasos:**
1. Verifique que la unidad tiene letra asignada: abra *Administración de discos* (`diskmgmt.msc`) y compruebe que la unidad tiene una letra (E:, F:, etc.).
2. Ejecute la aplicación como Administrador.
3. Pulse el botón **Refrescar unidades** o la tecla **F5**.
4. Pruebe con otro puerto USB (los puertos USB 3.0 azules a veces dan problemas; use un puerto USB 2.0 negro).
5. Si la unidad aparece como "Solo diagnóstico", es un disco interno o de red: no se puede reparar por seguridad.

### No se puede finalizar EACoreServer.exe

**Síntoma:** El botón "Finalizar" no funciona o el proceso reaparece.

**Pasos:**
1. Ejecute la aplicación como Administrador (clic derecho → *Ejecutar como administrador*).
2. Verifique si es un servicio de Windows: abra `services.msc` y busque "EACoreService". Si existe, deténgalo desde ahí.
3. Use la acción *"Detener y Eliminar EACoreService"* de la aplicación para detener el servicio, deshabilitarlo y eliminar los archivos.
4. Si el proceso es legítimo (EA/Origin), la aplicación lo identificará y no permitirá eliminarlo. Revise la firma digital en *Propiedades → Firmas digitales*.

### La reparación USB falla

**Síntoma:** La reparación comienza pero no termina, o termina con errores.

**Pasos:**
1. La unidad debe ser extraíble/USB físico y tener la firma exacta: `5.dat`, `6.dat`, `7.dat` y al menos un fichero numérico sin extensión dentro de `3.0\`.
2. Asegúrese de que la unidad no está en uso por otro programa (explorador de archivos, antivirus, etc.).
3. Verifique que la unidad tiene permisos de escritura: intente crear un archivo manualmente en la raíz.
4. Si se informa contenido no reconocido, haga una copia de seguridad y revíselo: la herramienta lo conserva deliberadamente.
5. Si la unidad está físicamente dañada, la copia puede fallar a mitad: copie los datos importantes primero con otra herramienta.

### Error: "Falta api-ms-win-core-path-l1-1-0.dll en el equipo"

**Síntoma:** Al hacer doble clic en el `.exe`, Windows muestra este error antes de que la aplicación se abra.

**Causa:** El ejecutable fue compilado con Python 3.11 o superior, que requiere esa DLL del sistema. **Windows 7, 8 y Vista no la tienen.**

**Solución:**
1. El desarrollador debe reconstruir el ejecutable con **Python 3.8 de 32 bits**.
2. Ejecutar `build.bat` en un entorno con Python 3.8 x86 (el script rechaza automáticamente cualquier otra versión).
3. Si es usuario final, solicite al desarrollador/administrador de TI una versión compilada correctamente.

### Error: "Failed to load Python DLL 'C:\Windows\TEMP\2\_MEI…\python312.dll'"

**Síntoma:** PyInstaller no puede cargar `python312.dll` desde el directorio temporal.

**Causa:** Dos problemas combinados: (1) el ejecutable se compiló con Python 3.12, y (2) la carpeta `%TEMP%` apunta a `C:\Windows\TEMP` sin permisos de escritura.

**Solución:**
1. Reconstruir con Python 3.8 de 32 bits (ejecutando `build.bat`).
2. El archivo `.spec` ya redirige el directorio temporal de PyInstaller a una carpeta de usuario (`%TEMP%\AntivirusEACoreServer_Temp`).
3. Si el problema persiste, establezca manualmente la variable TEMP antes de ejecutar:
   ```cmd
   set TEMP=%USERPROFILE%\AppData\Local\Temp
   Antivirus_EACoreServer.exe
   ```

### Error: "Failed to load Python DLL … LoadLibrary: <FormatMessageW failed.>"

**Síntoma:** Variante del error anterior. Windows no puede ni formatear el mensaje de error.

**Solución:** Idéntica: reconstruir con Python 3.8 x86.

### La aplicación no arranca en Windows XP

**Síntoma:** Aparece un aviso y la aplicación se cierra.

**Causa:** Es el comportamiento previsto. El último Python con instalador para Windows XP es **3.4.4** (2016), y las dependencias del proyecto (`requests`, `Pillow`) exigen Python 3.8 o superior.

**Solución:** Atienda esa unidad desde un equipo con Windows 7 o superior. La unidad USB se puede conectar en cualquier equipo compatible.

### En Linux, BSD o macOS la reparación aparece bloqueada

**Síntoma:** Las unidades aparecen pero el botón "Reparar" está deshabilitado.

**Causa:** Es deliberado. La reparación está diseñada para unidades con la estructura del malware en un medio extraíble, y la enumeración fiable de medios extraíbles depende de las APIs de Windows.

**Solución:** Fuera de Windows la herramienta opera en **modo de diagnóstico**: lista las unidades, analiza la firma y explica qué encontró, pero no modifica nada. Use un equipo con Windows para la reparación real.

### El scraping de rutas no funciona

**Síntoma:** La aplicación no obtiene rutas de processchecker.com.

**Pasos:**
1. Verifique conectividad a internet.
2. La URL `https://processchecker.com/file/EACoreServer.exe.html` puede estar caída.
3. La aplicación usa automáticamente un fallback con 52 rutas locales únicas; funciona sin internet.
4. El diagnóstico de procesos sigue funcionando con las rutas locales.

### Los colores de la interfaz no me gustan

**Solución:**
1. Menú **Ver → Tema**: elija entre 5 paletas o "Seguir al Sistema".
2. Menú **Ver → Color de acento**: elija entre 8 colores sugeridos o "Color personalizado…".
3. Menú **Ver → Tamaño de letra**: elija entre Pequeño, Normal, Grande y Muy grande.
4. **Ver → Restablecer apariencia** devuelve todo a los valores por defecto.

### La aplicación se cierra sola al abrir la guía

**Causa probable:** Error en el renderizado de la pestaña de ayuda.

**Solución:**
1. Revise el archivo de log en `%USERPROFILE%\Antivirus_EACoreServer_Logs\`.
2. Abra un issue en GitHub con el contenido del log y la versión de Python/SO.

---

## Pruebas automatizadas

Las pruebas no requieren una unidad USB física ni `pywin32`:

```bash
# Verificar sintaxis de todos los módulos
python -m py_compile main.py gui.py logger.py process_manager.py repair_engine.py scraper.py usb_monitor.py usb_monitor_windows.py compat.py temas.py ayuda.py win7_compat.py ui_components.py toast.py

# Ejecutar todas las pruebas unitarias
python -m unittest discover -s tests -v
```

En Linux hace falta una pantalla virtual para las pruebas de la interfaz; use Xvfb:

```bash
xvfb-run -a python -m unittest discover -s tests -v
```

**257 pruebas** cubren:

- ausencia de firma, firma incompleta y `.dat` completos sin fichero numérico;
- confirmación de la firma exacta con varios ficheros numéricos sin extensión;
- restauración con verificación SHA-256 y auditoría de las sumas;
- copia corrupta: el origen **no** se retira cuando el SHA-256 no coincide;
- resolución de colisiones y preservación de contenido no reconocido;
- enlaces simbólicos no seguidos;
- las 52 rutas únicas sin duplicados y su fusión con las rutas remotas;
- importación y comportamiento multiplataforma en Windows, macOS y Linux;
- la clasificación de cada edición de Windows (XP no soportado, Vista/7/8 con Python 3.8, 8.1 hasta 3.12) y de BSD, Solaris, AIX y sistemas desconocidos;
- contraste WCAG AA de las cinco paletas, de los ocho acentos sugeridos y de los tintes de fila, además de la legibilidad del texto sobre acentos extremos;
- que la leyenda de estados describa exactamente los textos que muestra la tabla;
- que todo estado del motor de reparación tenga traducción legible y que una reparación con errores no se muestre como si hubiera terminado bien;
- que el código siga siendo sintáctica y semánticamente válido en Python 3.8;
- la construcción real de la ventana y la aplicación de todas las combinaciones de tema, acento y tamaño de letra (se omite si no hay pantalla disponible).

`py_compile` solo valida sintaxis y no importa los módulos, por eso `usb_monitor_windows.py` puede compilarse también en Ubuntu y macOS.

---

## Logging

Todos los registros se almacenan en:

**Windows:**
```
C:\Users\[Usuario]\Antivirus_EACoreServer_Logs\antivirus_YYYYMMDD.log
```

**macOS / Linux:**
```
~/Antivirus_EACoreServer_Logs/antivirus_YYYYMMDD.log
```

**Características:**
- Rotación automática: 5 MB por archivo, 7 archivos de respaldo.
- Formato: `YYYY-MM-DD HH:MM:SS | NIVEL    | mensaje`
- Niveles: DEBUG, INFO, WARNING, ERROR, CRITICAL.
- Cada acción sobre unidades USB incluye el identificador de la unidad.
- Cada acción sobre procesos EACoreServer incluye la ruta y el resultado.
- Cada verificación SHA-256 queda registrada con la suma verificada.

---

## Integración continua

El flujo `.github/workflows/ci.yml` ejecuta cinco combinaciones sin `fail-fast`, para que cada una reporte su resultado aunque otra falle:

| Sistema | Python | Propósito |
|---------|--------|-----------|
| Ubuntu (latest) | 3.12 | Compatibilidad con Python moderno en Linux |
| macOS (latest) | 3.12 | Compatibilidad con Python moderno en macOS |
| Windows (latest) | 3.12 | Compatibilidad con Python moderno en Windows |
| Windows (latest) | **3.8** | Piso de compatibilidad (Vista/7/8) |
| Ubuntu 22.04 | **3.8** | Verificar que el código funciona con Python 3.8 en Linux |

Cada combinación comprueba:
1. Sintaxis de los trece módulos del proyecto.
2. Compatibilidad con Python 3.8 (sin `match/case`, sin uniones PEP 604, sin `dict[str,str]` en tiempo de ejecución).
3. Pruebas unitarias completas.
4. Las 52 rutas únicas sin duplicados.
5. Contraste WCAG AA de las paletas.

En Linux se instala **Xvfb** y hay un paso que **falla si las pruebas de la interfaz se omiten**, para que un entorno roto no pase desapercibido.

---

## Licencia

Aplicación de utilidad personal. Uso bajo su propia responsabilidad.

El código fuente es libre para consulta y aprendizaje. El ejecutable compilado puede distribuirse libremente dentro de organizaciones para uso interno.

---

## Soporte

Para problemas o preguntas, revise en este orden:

1. **El archivo de log** en `Antivirus_EACoreServer_Logs\` — contiene el detalle completo de todas las acciones.
2. **La pestaña "Registro"** de la interfaz gráfica — muestra los mensajes en tiempo real.
3. **El mensaje de error detallado** en la barra de estado inferior.
4. **La guía integrada** (F1) — explica cada función de la aplicación.
5. **La sección "Solución de problemas"** de este README.
6. **Los issues del repositorio** en GitHub: https://github.com/yhquintero/Antivirus_EACoreServer/issues

Al reportar un problema, incluya:
- Versión de la aplicación (barra de título o *Ayuda → Acerca de*).
- Sistema operativo y arquitectura (*Ayuda → Comprobar compatibilidad del sistema*).
- Versión de Python (si ejecuta desde código fuente).
- Contenido del archivo de log del día del problema.
- Captura de pantalla del error.

---

*Última actualización: Octubre 2026*
*Versión: 1.2.0*
*Python 3.8+ | Windows Vista a 11 (x86 y x64) · macOS · Linux · BSD · Solaris/illumos · AIX*
