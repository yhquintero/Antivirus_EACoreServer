"""Detección de plataforma y matriz de sistemas operativos soportados.

Centraliza todo lo relacionado con «¿en qué sistema estoy y hasta dónde puedo
llegar?»: versión y edición de Windows, arquitectura (x86/x64/arm), versión de
Python y familia POSIX. Lo consumen el arranque (:mod:`main`), el monitor de
unidades (:mod:`usb_monitor`) y la GUI para mostrar información honesta al
usuario en lugar de fallar con errores crípticos.

Límites reales que motivan este módulo
--------------------------------------
* **Windows XP y Vista no son alcanzables.** El último CPython que funciona en
  XP es 3.4 (con instalador binario hasta 3.4.4) y en Vista es 3.8. Este
  proyecto usa *f-strings* (3.6+) y ``dataclasses`` (3.7+), y sus dependencias
  actuales (``requests``, ``Pillow``) exigen Python 3.8+. Por eso el suelo es
  3.8: **Windows 7, 8, 8.1, 10 y 11**, en x86 y x64.
* Windows Vista / 7 / 8.0 → **solo Python 3.8** (3.9 ya no arranca ahí). En
  Windows 7, Python 3.8 exige además el update KB2533623.
* Windows 8.1 → Python 3.8 a 3.12.
* Windows 10/11 → cualquier Python soportado.

Para el mayor alcance posible (Vista a 11, x86 y x64) el ejecutable debe
construirse con **Python 3.8 de 32 bits**: un binario de 32 bits corre también
en Windows de 64 bits, mientras que al revés es imposible.

En un sistema no soportado la aplicación no debe reventar: informa con claridad
y continúa en modo de solo diagnóstico cuando es posible.
"""

from __future__ import annotations

import os
import platform
import struct
import sys
from dataclasses import dataclass
from typing import Optional, Tuple

# Suelo de Python del proyecto. Bajar de 3.8 rompería Windows 7 y subirlo por
# encima dejaría fuera a Windows 7 y 8.0.
MINIMO_PYTHON: Tuple[int, int] = (3, 8)

# Niveles de soporte que entiende la GUI.
SOPORTE_COMPLETO = "completo"
SOPORTE_DIAGNOSTICO = "diagnostico"
SOPORTE_NO_SOPORTADO = "no_soportado"

# Familias POSIX con backend propio o genérico en usb_monitor.
FAMILIA_LINUX = "linux"
FAMILIA_MACOS = "darwin"
FAMILIA_BSD = "bsd"
FAMILIA_SOLARIS = "sunos"
FAMILIA_AIX = "aix"
FAMILIA_DESCONOCIDA = "desconocida"

_SISTEMAS_BSD = {"freebsd", "openbsd", "netbsd", "dragonfly", "midnightbsd"}
_SISTEMAS_SOLARIS = {"sunos", "solaris", "illumos"}
_SISTEMAS_AIX = {"aix"}


# ---------------------------------------------------------------------------
# Versión de Windows
# ---------------------------------------------------------------------------
# (major, minor) -> nombre comercial. Windows 10 y 11 comparten 10.0 y se
# distinguen por el número de compilación (22000 y superior es Windows 11).
_TABLA_WINDOWS = {
    (5, 0): "Windows 2000",
    (5, 1): "Windows XP",
    (5, 2): "Windows XP x64 / Server 2003",
    (6, 0): "Windows Vista / Server 2008",
    (6, 1): "Windows 7 / Server 2008 R2",
    (6, 2): "Windows 8 / Server 2012",
    (6, 3): "Windows 8.1 / Server 2012 R2",
    (10, 0): "Windows 10 / 11",
}

# Windows que no pueden ejecutar Python 3.8 ni, por tanto, este programa.
# El último CPython con instalador para XP es 3.4.4 (2016).
_WINDOWS_TOO_ANTIGUOS = {(5, 0), (5, 1), (5, 2)}

BUILD_WINDOWS_11 = 22000

# Python máximo instalable en cada Windows, según la documentación oficial de
# CPython («Using Python on Windows»). Sirve para guiar el empaquetado: quien
# quiera el mayor alcance posible debe construir con Python 3.8 de 32 bits.
MAXIMO_PYTHON_POR_WINDOWS = {
    (5, 0): (3, 4),   # Windows 2000
    (5, 1): (3, 4),   # Windows XP
    (5, 2): (3, 4),   # Windows XP x64 / Server 2003
    (6, 0): (3, 8),   # Windows Vista
    (6, 1): (3, 8),   # Windows 7 / Server 2008 R2
    (6, 2): (3, 8),   # Windows 8 / Server 2012
    (6, 3): (3, 12),  # Windows 8.1 / Server 2012 R2
    (10, 0): (3, 14),  # Windows 10 / 11
}

# Windows 7 necesita este parche para que Python 3.8 pueda arrancar.
KB_WINDOWS_7 = "KB2533623"


def python_maximo_para_windows() -> Optional[Tuple[int, int]]:
    """Versión máxima de Python usable en el Windows en ejecución."""
    version = obtener_version_windows()
    if version is None:
        return None
    return MAXIMO_PYTHON_POR_WINDOWS.get((version[0], version[1]))


def obtener_version_windows() -> Optional[Tuple[int, int, int]]:
    """Devuelve ``(major, minor, build)`` de Windows, o ``None`` fuera de Windows.

    Se usa ``sys.getwindowsversion`` en lugar de ``platform.version`` porque
    desde Windows 8.1 este último devuelve valores falseados por el manifiesto
    de compatibilidad de la aplicación.
    """
    obtener = getattr(sys, "getwindowsversion", None)
    if obtener is None:
        return None
    try:
        info = obtener()
        return int(info.major), int(info.minor), int(info.build)
    except Exception:
        return None


def nombre_edicion_windows() -> str:
    """Nombre comercial legible de la edición de Windows en ejecución."""
    version = obtener_version_windows()
    if version is None:
        return platform.system() or "Windows"
    major, minor, build = version
    nombre = _TABLA_WINDOWS.get((major, minor))
    if nombre is None:
        return f"Windows (versión {major}.{minor}, build {build})"
    if (major, minor) == (10, 0):
        return "Windows 11" if build >= BUILD_WINDOWS_11 else "Windows 10"
    if (major, minor) == (6, 1):
        return "Windows 7 / Server 2008 R2"
    return nombre


# ---------------------------------------------------------------------------
# Arquitectura
# ---------------------------------------------------------------------------
_MAQUINAS_64_X86 = {"amd64", "x86_64", "x64"}
_MAQUINAS_32_X86 = {"i386", "i486", "i586", "i686", "x86"}
_MAQUINAS_ARM64 = {"arm64", "aarch64"}
_MAQUINAS_ARM32 = {"armv7l", "armv6l", "arm", "armv8l"}


def obtener_bits_proceso() -> int:
    """Ancho de puntero del intérprete: 32 o 64 bits.

    Es el dato que importa para el ejecutable que genere PyInstaller, y puede
    diferir del del sistema (Python de 32 bits sobre Windows de 64 bits).
    """
    return struct.calcsize("P") * 8


def obtener_arquitectura() -> str:
    """Etiqueta corta de arquitectura: ``x86``, ``x64``, ``arm64``, ``arm32``."""
    bits = obtener_bits_proceso()
    maquina = (platform.machine() or "").lower()
    if maquina in _MAQUINAS_64_X86:
        return "x64" if bits == 64 else "x86"
    if maquina in _MAQUINAS_32_X86:
        return "x86"
    if maquina in _MAQUINAS_ARM64:
        return "arm64" if bits == 64 else "arm32"
    if maquina in _MAQUINAS_ARM32:
        return "arm32"
    if maquina:
        return f"{maquina}-{bits}bits"
    return f"desconocida-{bits}bits"


def es_proceso_32_en_so_64() -> bool:
    """Detecta WOW64: intérprete de 32 bits sobre un Windows de 64 bits."""
    if os.name != "nt":
        return False
    if obtener_bits_proceso() != 32:
        return False
    # PROCESSOR_ARCHITEW6432 solo existe dentro de un proceso WOW64.
    return bool(os.environ.get("PROCESSOR_ARCHITEW6432"))


# ---------------------------------------------------------------------------
# Familias POSIX
# ---------------------------------------------------------------------------
def obtener_familia_posix() -> str:
    """Clasifica el sistema en ``linux``, ``darwin``, ``bsd``, ``sunos``, ``aix``."""
    sistema = (platform.system() or "").lower()
    if os.name == "nt" or sistema.startswith("win"):
        return "windows"
    if sistema == "linux":
        return FAMILIA_LINUX
    if sistema == "darwin":
        return FAMILIA_MACOS
    if sistema in _SISTEMAS_BSD:
        return FAMILIA_BSD
    if sistema in _SISTEMAS_SOLARIS:
        return FAMILIA_SOLARIS
    if sistema in _SISTEMAS_AIX:
        return FAMILIA_AIX
    return FAMILIA_DESCONOCIDA


def obtener_distribucion_linux() -> str:
    """Nombre de la distribución Linux, o cadena vacía si no se puede determinar."""
    try:
        with open("/etc/os-release", "r", encoding="utf-8", errors="replace") as archivo:
            datos = {}
            for linea in archivo:
                if "=" in linea:
                    clave, _, valor = linea.partition("=")
                    datos[clave.strip()] = valor.strip().strip('"')
        return datos.get("PRETTY_NAME") or datos.get("NAME", "")
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# Información consolidada
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class InfoPlataforma:
    """Retrato completo del sistema donde se ejecuta la aplicación."""

    sistema: str
    nombre_amigable: str
    familia: str
    arquitectura: str
    bits_proceso: int
    python_version: str
    nivel_soporte: str
    motivo: str

    @property
    def soportado(self) -> bool:
        return self.nivel_soporte != SOPORTE_NO_SOPORTADO

    @property
    def es_windows(self) -> bool:
        return self.familia == "windows"

    @property
    def es_windows_legacy(self) -> bool:
        """Windows Vista, 7, 8 u 8.1: soportados, con Python acotado por versión."""
        version = obtener_version_windows() if self.es_windows else None
        return bool(version and (version[0], version[1]) in {(6, 0), (6, 1), (6, 2), (6, 3)})

    @property
    def es_windows_obsoleto(self) -> bool:
        """Windows 2000/XP/Server 2003: no pueden ejecutar este programa."""
        version = obtener_version_windows() if self.es_windows else None
        return bool(version and (version[0], version[1]) in _WINDOWS_TOO_ANTIGUOS)

    def resumen(self) -> str:
        """Línea legible para el log y la barra de estado."""
        return (
            f"{self.nombre_amigable} · {self.arquitectura} ({self.bits_proceso} bits) · "
            f"Python {self.python_version} · soporte {self.nivel_soporte}"
        )


def _python_cumple_minimo() -> Tuple[bool, str]:
    actual = sys.version_info[:2]
    if actual >= MINIMO_PYTHON:
        return True, ""
    return False, (
        f"Se requiere Python {MINIMO_PYTHON[0]}.{MINIMO_PYTHON[1]} o superior; "
        f"el intérprete actual es {actual[0]}.{actual[1]}."
    )


def detectar_plataforma() -> InfoPlataforma:
    """Analiza el sistema actual y determina su nivel de soporte."""
    sistema = platform.system() or "desconocido"
    familia = obtener_familia_posix()
    arquitectura = obtener_arquitectura()
    bits = obtener_bits_proceso()
    python_version = platform.python_version()

    ok_python, motivo_python = _python_cumple_minimo()

    if familia == "windows":
        nombre = nombre_edicion_windows()
        version = obtener_version_windows()
        pareja = (version[0], version[1]) if version else None

        if pareja in _WINDOWS_TOO_ANTIGUOS:
            return InfoPlataforma(
                sistema, nombre, familia, arquitectura, bits, python_version,
                SOPORTE_NO_SOPORTADO,
                f"{nombre} no puede ejecutar este programa. El último Python con "
                f"instalador para Windows XP es 3.4.4 (2016), y las dependencias "
                f"actuales (requests, Pillow) exigen Python 3.8 o superior. "
                f"Se requiere Windows Vista o, preferiblemente, Windows 7+. "
                f"Puede atender esta unidad desde un equipo con Windows 7 o "
                f"superior.",
            )
        if not ok_python:
            return InfoPlataforma(
                sistema, nombre, familia, arquitectura, bits, python_version,
                SOPORTE_NO_SOPORTADO, motivo_python,
            )
        if pareja in {(6, 0), (6, 1), (6, 2)}:
            nota = (
                f"{nombre} está soportado únicamente con Python 3.8: desde Python "
                f"3.9 el intérprete ya no arranca en este sistema."
            )
            if pareja == (6, 1):
                nota += (
                    f" Además, Python 3.8 requiere tener instalado el update "
                    f"{KB_WINDOWS_7} de Windows."
                )
            return InfoPlataforma(
                sistema, nombre, familia, arquitectura, bits, python_version,
                SOPORTE_COMPLETO, nota,
            )
        if pareja == (6, 3):
            return InfoPlataforma(
                sistema, nombre, familia, arquitectura, bits, python_version,
                SOPORTE_COMPLETO,
                f"{nombre} está soportado con Python 3.8 a 3.12.",
            )
        return InfoPlataforma(
            sistema, nombre, familia, arquitectura, bits, python_version,
            SOPORTE_COMPLETO, "",
        )

    if not ok_python:
        return InfoPlataforma(
            sistema, sistema, familia, arquitectura, bits, python_version,
            SOPORTE_NO_SOPORTADO, motivo_python,
        )

    if familia == FAMILIA_MACOS:
        release = platform.mac_ver()[0] or platform.release()
        return InfoPlataforma(
            sistema, f"macOS {release}", familia, arquitectura, bits, python_version,
            SOPORTE_COMPLETO,
            "La reparación está diseñada para unidades con estructura Windows; en "
            "macOS la herramienta opera en modo de diagnóstico y prueba.",
        )

    if familia == FAMILIA_LINUX:
        distro = obtener_distribucion_linux()
        nombre = distro or f"Linux {platform.release()}"
        return InfoPlataforma(
            sistema, nombre, familia, arquitectura, bits, python_version,
            SOPORTE_COMPLETO,
            "La reparación está diseñada para unidades con estructura Windows; en "
            "Linux la herramienta opera en modo de diagnóstico y prueba.",
        )

    if familia in (FAMILIA_BSD, FAMILIA_SOLARIS, FAMILIA_AIX):
        release = platform.release()
        return InfoPlataforma(
            sistema, f"{sistema} {release}".strip(), familia, arquitectura, bits,
            python_version, SOPORTE_DIAGNOSTICO,
            "Sistema Unix reconocido con backend genérico de montaje. La detección "
            "de medios extraíbles es conservadora: ante la duda la unidad se marca "
            "como no reparable y solo se diagnostica.",
        )

    return InfoPlataforma(
        sistema, f"{sistema} {platform.release()}".strip(), familia, arquitectura,
        bits, python_version, SOPORTE_DIAGNOSTICO,
        "Sistema no reconocido. La aplicación funciona en modo de solo diagnóstico; "
        "la enumeración de unidades puede estar incompleta.",
    )


_info_cache: Optional[InfoPlataforma] = None


def obtener_info_plataforma(forzar: bool = False) -> InfoPlataforma:
    """Devuelve la información de plataforma, calculada una sola vez."""
    global _info_cache
    if _info_cache is None or forzar:
        _info_cache = detectar_plataforma()
    return _info_cache


def es_windows() -> bool:
    return obtener_info_plataforma().es_windows


def mensaje_de_no_soporte() -> Optional[str]:
    """Texto para mostrar al usuario si el sistema no está soportado."""
    info = obtener_info_plataforma()
    if info.nivel_soporte == SOPORTE_NO_SOPORTADO:
        return info.motivo
    return None
