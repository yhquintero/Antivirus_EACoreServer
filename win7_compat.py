"""
Compatibilidad con Windows 7 y versiones heredadas.

Detecta **antes de cualquier importación pesada** si faltan DLLs del sistema
que impedirían el arranque de la aplicación, y muestra un mensaje claro al
usuario en lugar de un error críptico de PyInstaller.

Por qué es necesario
--------------------
Python 3.11+ introdujo una dependencia de ``api-ms-win-core-path-l1-1-0.dll``
que no existe en Windows 7 ni en Windows 8.0. Cuando PyInstaller construye un
ejecutable con Python 3.11+ y el usuario lo ejecuta en Windows 7, el cargador
de Windows muestra un cuadro de error del sistema antes de que el programa
pueda siquiera ejecutar código Python:

    "El programa no puede iniciarse porque falta
     api-ms-win-core-path-l1-1-0.dll en el equipo."

Además, en modo onefile PyInstaller extrae ``python3x.dll`` al directorio
temporal definido por ``%TEMP%``. Si la variable apunta a ``C:\\Windows\\TEMP``
(o a cualquier ruta sin permisos de lectura), la carga de la DLL falla con:

    "Failed to load Python DLL 'C:\\Windows\\TEMP\\2\\_MEI...\python3x.dll'.
     LoadLibrary: No se puede encontrar el módulo especificado."

Este módulo centraliza la detección de estos problemas y ofrece mensajes
comprensibles en español.
"""

from __future__ import annotations

import os
import sys
import ctypes
import ctypes.util
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

# Solo es relevante en Windows. En otras plataformas todos los controles
# pasan sin efecto.
ES_WINDOWS = os.name == "nt"


# ---------------------------------------------------------------------------
# Resultado del diagnóstico
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ResultadoCompatWindows:
    """Resultado del diagnóstico de compatibilidad con Windows."""

    soportado: bool
    problemas: Tuple[str, ...]
    advertencias: Tuple[str, ...]
    sugerencias: Tuple[str, ...]

    @property
    def tiene_problemas(self) -> bool:
        return bool(self.problemas)

    @property
    def tiene_advertencias(self) -> bool:
        return bool(self.advertencias)


# ---------------------------------------------------------------------------
# Detección de DLLs del sistema
# ---------------------------------------------------------------------------
# Las DLLs de la familia ``api-ms-win-core-*`` son "API sets" de Windows.
# En Windows 10 todas están disponibles, pero en Windows 7/8 algunas no
# existen o tienen nombres distintos.

_DLLS_CRITICAS_WIN7: Tuple[str, ...] = (
    # Requerida por Python 3.11+. Su ausencia impide el arranque en Win7.
    "api-ms-win-core-path-l1-1-0.dll",
    # Requerida por Python 3.8+ en algunas rutas de ``os.path``.
    "api-ms-win-core-file-l2-1-0.dll",
)


def _dll_sistema_disponible(nombre: str) -> bool:
    """Comprueba si una DLL del sistema está disponible para cargar.

    Usa ``kernel32.LoadLibraryW`` que es la misma ruta que PyInstaller emplea
    al intentar cargar ``python3x.dll``. Si falla, la aplicación tampoco
    podrá arrancar.
    """
    if not ES_WINDOWS:
        return True
    try:
        kernel32 = ctypes.windll.kernel32
        # Evitar que Windows muestre el cuadro de error modal cuando la DLL
        # no se encuentra: SEM_FAILCRITICALERRORS.
        modo_anterior = kernel32.SetErrorMode(0x0001)
        try:
            resultado = kernel32.LoadLibraryW(nombre)
            return bool(resultado)
        finally:
            kernel32.SetErrorMode(modo_anterior)
    except Exception:
        # Si ``ctypes.windll`` no está disponible (p. ej. en Wine antiguo),
        # asumimos que la DLL está presente.
        return True


def _version_windows() -> Optional[Tuple[int, int, int]]:
    """Versión ``(major, minor, build)`` de Windows, o ``None`` si no es Windows."""
    if not ES_WINDOWS:
        return None
    obtener = getattr(sys, "getwindowsversion", None)
    if obtener is None:
        return None
    try:
        info = obtener()
        return int(info.major), int(info.minor), int(info.build)
    except Exception:
        return None


def _nombre_windows(version: Tuple[int, int, int]) -> str:
    """Nombre comercial legible de la versión de Windows."""
    tabla = {
        (6, 0): "Windows Vista",
        (6, 1): "Windows 7",
        (6, 2): "Windows 8",
        (6, 3): "Windows 8.1",
        (10, 0): "Windows 10" if version[2] < 22000 else "Windows 11",
    }
    return tabla.get((version[0], version[1]), f"Windows {version[0]}.{version[1]}")


# ---------------------------------------------------------------------------
# Diagnóstico de la carpeta temporal
# ---------------------------------------------------------------------------
def _directorio_temporal_seguro() -> Optional[Path]:
    """Devuelve una carpeta temporal escribible y libre, o ``None``.

    PyInstaller en modo onefile extrae ``python3x.dll`` al directorio temporal
    de ejecución. Si ``%TEMP%`` apunta a ``C:\\Windows\\TEMP`` (una carpeta
    del sistema) o a una ruta sin permisos de lectura, la extracción y carga
    fallan.

    Esta función propone alternativas en orden de preferencia:
    1. ``%TEMP%`` / ``%TMP%`` si son escribibles por el usuario actual.
    2. ``%USERPROFILE%\\AppData\\Local\\Temp``.
    3. Carpeta local de la aplicación en ``%USERPROFILE%``.
    """
    if not ES_WINDOWS:
        return None

    candidatos: List[Path] = []

    # Variables de entorno del usuario (las más seguras).
    for var in ("TEMP", "TMP"):
        valor = os.environ.get(var)
        if valor:
            candidatos.append(Path(valor))

    # Ruta canónica de Temp en el perfil del usuario.
    perfil = Path(os.environ.get("USERPROFILE", ""))
    if perfil.exists():
        candidatos.append(perfil / "AppData" / "Local" / "Temp")

    # Carpeta local de la aplicación como último recurso.
    if perfil.exists():
        candidatos.append(perfil / "Antivirus_EACoreServer_Temp")

    for ruta in candidatos:
        try:
            ruta.mkdir(parents=True, exist_ok=True)
            # Comprobar escritura real creando un archivo efímero.
            archivo_prueba = ruta / ".aeac_probe.tmp"
            archivo_prueba.write_text("ok", encoding="utf-8")
            archivo_prueba.unlink()
            if os.access(str(ruta), os.W_OK | os.R_OK):
                return ruta
        except OSError:
            continue
    return None


def _temporal_es_problematica() -> Tuple[bool, str, Optional[Path]]:
    """Indica si la carpeta temporal actual puede causar problemas.

    Returns:
        Tupla ``(problematica, motivo, alternativa)``.
    """
    temp_actual = tempfile.gettempdir()
    ruta_actual = Path(temp_actual)

    # C:\Windows\TEMP es una carpeta del sistema que suele requerir
    # privilegios de administrador. Aunque el ejecutable se ejecute como
    # admin, otros procesos pueden bloquearla.
    es_carpeta_sistema = any(
        ruta_actual == Path(ruta_sistema)
        for ruta_sistema in (
            "C:\\Windows\\TEMP",
            "C:\\Windows\\Temp",
            "C:\\TEMP",
            "C:\\Temp",
        )
    )

    # Comprobar lectura/escritura real.
    escribible = True
    try:
        archivo_prueba = ruta_actual / ".aeac_probe.tmp"
        archivo_prueba.write_text("ok", encoding="utf-8")
        archivo_prueba.unlink()
    except OSError:
        escribible = False

    if es_carpeta_sistema and not escribible:
        alternativa = _directorio_temporal_seguro()
        ruta_ejemplo = (
            str(alternativa) if alternativa
            else "C:\\Users\\<usuario>\\AppData\\Local\\Temp"
        )
        return (
            True,
            (
                f"La carpeta temporal del sistema ({ruta_actual}) no es escribible. "
                "PyInstaller necesita una carpeta temporal de usuario para extraer "
                "los archivos del ejecutable. "
                f"Establezca la variable de entorno TEMP a una carpeta de su perfil, "
                f"por ejemplo: {ruta_ejemplo}"
            ),
            alternativa,
        )

    if not escribible:
        alternativa = _directorio_temporal_seguro()
        return (
            True,
            (
                f"La carpeta temporal ({ruta_actual}) no tiene permisos de escritura. "
                "La aplicación necesita extraer archivos temporales para arrancar. "
                f"Alternativa sugerida: {alternativa or 'una carpeta de su perfil de usuario'}"
            ),
            alternativa,
        )

    return False, "", None


# ---------------------------------------------------------------------------
# Diagnóstico completo
# ---------------------------------------------------------------------------
def diagnosticar_compatibilidad_windows() -> ResultadoCompatWindows:
    """Analiza el sistema actual y devuelve problemas y advertencias.

    Este diagnóstico es **preventivo**: se ejecuta antes de que PyInstaller
    intente cargar ``python3x.dll`` y detecta condiciones que harían fallar
    el arranque con un error críptico.

    No lanza excepciones; si algo falla durante el diagnóstico se reporta
    como advertencia en lugar de como problema bloqueante.
    """
    problemas: List[str] = []
    advertencias: List[str] = []
    sugerencias: List[str] = []

    if not ES_WINDOWS:
        return ResultadoCompatWindows(
            soportado=True,
            problemas=tuple(problemas),
            advertencias=tuple(advertencias),
            sugerencias=tuple(sugerencias),
        )

    version = _version_windows()

    # --- Detección de DLLs críticas faltantes ---
    dlls_faltantes: List[str] = []
    for dll in _DLLS_CRITICAS_WIN7:
        if not _dll_sistema_disponible(dll):
            dlls_faltantes.append(dll)

    if dlls_faltantes:
        lista = ", ".join(dlls_faltantes)
        if version and version[:2] in {(6, 0), (6, 1), (6, 2)}:
            nombre = _nombre_windows(version)
            problemas.append(
                f"Faltan DLLs del sistema necesarias: {lista}.\n\n"
                f"Estas DLLs no están disponibles en {nombre}. "
                f"Este programa fue construido con una versión de Python que "
                f"las requiere (Python 3.11 o superior).\n\n"
                f"Solución: reconstruya el ejecutable con Python 3.8 de 32 bits, "
                f"que es la última versión compatible con {nombre}."
            )
            sugerencias.append(
                "Recompile con Python 3.8 x86 y ejecute build.bat en ese entorno."
            )
        else:
            problemas.append(
                f"Faltan DLLs del sistema necesarias: {lista}.\n\n"
                "Esto suele indicar una instalación de Windows dañada o "
                "incompleta. Ejecute 'sfc /scannow' desde un símbolo del sistema "
                "elevado para reparar los archivos del sistema."
            )
            sugerencias.append("Ejecute: sfc /scannow")
            sugerencias.append("Reinicie el equipo después de la reparación.")

    # --- Carpeta temporal problemática ---
    temp_problematica, motivo_temp, alternativa_temp = _temporal_es_problematica()
    if temp_problematica:
        problemas.append(motivo_temp)
        if alternativa_temp:
            sugerencias.append(f"Establezca TEMP={alternativa_temp} antes de ejecutar el programa.")

    # --- Advertencias preventivas ---
    if version:
        mayor, menor, compilacion = version
        if (mayor, menor) == (6, 1):
            # Windows 7: comprobar KB2533623 (necesario para Python 3.8).
            advertencias.append(
                "Windows 7 detectado: asegúrese de tener instalado el update "
                "KB2533623. Sin este parche, Python 3.8 no puede arrancar."
            )

        if (mayor, menor) == (6, 2):
            advertencias.append(
                "Windows 8 detectado: solo Python 3.8 es compatible con este sistema."
            )

        if (mayor, menor) == (6, 0):
            advertencias.append(
                "Windows Vista detectado: esta versión de Windows está obsoleta "
                "y tiene soporte limitado. Solo Python 3.8 funciona aquí."
            )

    # --- Versión de Python del ejecutable embebido ---
    if ES_WINDOWS:
        # ``sys.version_info`` es la versión con la que se compiló el ejecutable.
        if sys.version_info >= (3, 11):
            advertencias.append(
                f"El ejecutable fue compilado con Python {sys.version_info.major}."
                f"{sys.version_info.minor}, que no es compatible con Windows 7/8. "
                f"Recompile con Python 3.8 x86."
            )

    return ResultadoCompatWindows(
        soportado=not problemas,
        problemas=tuple(problemas),
        advertencias=tuple(advertencias),
        sugerencias=tuple(sugerencias),
    )


# ---------------------------------------------------------------------------
# Mensaje de error al usuario
# ---------------------------------------------------------------------------
def _mostrar_dialogo_error(titulo: str, mensaje: str) -> None:
    """Muestra un cuadro de diálogo de error sin depender de tkinter.

    Usa ``MessageBoxW`` de Windows para que el mensaje aparezca incluso cuando
    tkinter no pueda inicializarse (p. ej. antes de cargar python3x.dll).
    """
    if not ES_WINDOWS:
        print(f"\n{titulo}\n{'=' * len(titulo)}\n{mensaje}\n", file=sys.stderr)
        return

    try:
        kernel32 = ctypes.windll.kernel32
        # Evitar cuadro modal de Windows cuando falta una DLL.
        kernel32.SetErrorMode(0x0001)
        user32 = ctypes.windll.user32
        MB_ICONERROR = 0x00000010
        MB_OK = 0x00000000
        MB_SETFOREGROUND = 0x00010000
        user32.MessageBoxW(
            None,
            mensaje,
            titulo,
            MB_ICONERROR | MB_OK | MB_SETFOREGROUND,
        )
    except Exception:
        print(f"\n{titulo}\n{'=' * len(titulo)}\n{mensaje}\n", file=sys.stderr)


def comprobar_y_reportar() -> bool:
    """Ejecuta el diagnóstico y muestra un diálogo si hay problemas.

    Returns:
        ``True`` si el sistema puede ejecutar la aplicación.
        ``False`` si hay problemas bloqueantes y la aplicación debe cerrarse.
    """
    resultado = diagnosticar_compatibilidad_windows()

    if resultado.tiene_problemas:
        mensaje = "\n\n".join(resultado.problemas)
        if resultado.sugerencias:
            mensaje += "\n\nSugerencias:\n" + "\n".join(
                f"  · {s}" for s in resultado.sugerencias
            )
        _mostrar_dialogo_error("Error de compatibilidad", mensaje)
        return False

    # Advertencias: se loguean pero no bloquean el arranque.
    if resultado.tiene_advertencias:
        try:
            from logger import obtener_logger
            logger = obtener_logger()
            for advertencia in resultado.advertencias:
                logger.warning(f"[Compatibilidad] {advertencia}")
        except ImportError:
            for advertencia in resultado.advertencias:
                print(f"[AVISO] {advertencia}", file=sys.stderr)

    return True
