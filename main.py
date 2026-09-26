"""
Punto de entrada principal de Antivirus_EACoreServer.
Verifica la compatibilidad del sistema, los permisos de administrador,
inicializa componentes y lanza la GUI.

Orden de las comprobaciones
---------------------------
1. **Versión de Python.** Se comprueba primero y solo con ``sys``, antes de
   importar :mod:`compat`, porque ese módulo usa ``dataclasses`` (3.7+). Si el
   intérprete es demasiado antiguo, cualquier otra importación reventaría con un
   error críptico en lugar de un mensaje comprensible.
2. **Sistema operativo.** Windows 2000/XP/Server 2003 quedan fuera de forma
   definitiva (el último Python con instalador para XP es 3.4.4 y las
   dependencias exigen 3.8+). Vista, 7 y 8 requieren Python 3.8.
3. **Privilegios.** ``IsUserAnAdmin``/``ShellExecuteW`` en Windows, ``geteuid``
   con ``osascript`` en macOS y ``geteuid`` con ``pkexec`` o ``sudo`` en Linux.
"""

import sys
import os
import ctypes
import logging
import platform
from typing import Optional, Tuple

from logger import obtener_logger

logger = obtener_logger()

ES_WINDOWS = os.name == "nt"
_SISTEMA = platform.system().lower()
ES_MACOS = _SISTEMA == "darwin"
ES_LINUX = _SISTEMA == "linux"

# Suelo del proyecto. No se importa de compat a propósito: esta comprobación
# debe funcionar incluso cuando el resto del programa no puede cargarse.
MINIMO_PYTHON = (3, 8)


def _verificar_interprete() -> Tuple[bool, str]:
    """Comprueba la versión de Python sin importar ningún módulo del proyecto."""
    actual = sys.version_info[:3]
    if actual >= MINIMO_PYTHON:
        return True, ""
    return False, (
        f"Este programa requiere Python {MINIMO_PYTHON[0]}.{MINIMO_PYTHON[1]} o superior.\n"
        f"El intérprete actual es {actual[0]}.{actual[1]}.{actual[2]}.\n\n"
        f"Guía por sistema operativo:\n"
        f"  · Windows Vista, 7 y 8  →  Python 3.8 (única versión compatible)\n"
        f"  · Windows 8.1           →  Python 3.8 a 3.12\n"
        f"  · Windows 10 y 11       →  cualquier Python soportado\n"
        f"  · macOS y Linux         →  Python 3.8 o superior\n\n"
        f"Para el mayor alcance posible (Vista a 11, x86 y x64) instale Python 3.8\n"
        f"de 32 bits: un binario de 32 bits también funciona en Windows de 64 bits."
    )


def _verificar_sistema() -> Tuple[bool, str, str]:
    """Analiza el SO y devuelve ``(soportado, motivo, resumen)``."""
    try:
        from compat import SOPORTE_NO_SOPORTADO, obtener_info_plataforma
    except Exception as exc:  # pragma: no cover - defensivo
        logger.warning(f"No se pudo analizar la plataforma: {exc}")
        return True, "", f"plataforma sin analizar ({exc})"

    try:
        info = obtener_info_plataforma()
    except Exception as exc:  # pragma: no cover - defensivo
        logger.warning(f"Error detectando la plataforma: {exc}")
        return True, "", f"plataforma sin analizar ({exc})"

    return info.nivel_soporte != SOPORTE_NO_SOPORTADO, info.motivo, info.resumen()


def _mostrar_aviso(titulo: str, mensaje: str) -> None:
    """Muestra un diálogo si hay interfaz gráfica; si no, lo escribe en consola."""
    logger.error(f"{titulo}: {mensaje}")
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(titulo, mensaje)
        root.destroy()
    except Exception:
        print(f"\n{titulo}\n{'-' * len(titulo)}\n{mensaje}\n", file=sys.stderr)


def _verificar_admin() -> bool:
    """Verifica si la aplicación se ejecuta con privilegios elevados."""
    if ES_WINDOWS:
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    # macOS, Linux y BSD: el usuario efectivo 0 es root.
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def _ejecutar_como_admin() -> bool:
    """Re-ejecuta la aplicación con privilegios, conservando argumentos.

    En Windows ``ShellExecuteW`` recibe los parámetros como una sola cadena; usar
    ``list2cmdline`` evita que una instalación en una ruta con espacios falle.
    En macOS se delega en ``osascript`` y en Linux/BSD en ``pkexec`` o ``sudo``.
    """
    import shlex
    import subprocess

    if ES_WINDOWS:
        argumentos = subprocess.list2cmdline([os.path.abspath(sys.argv[0]), *sys.argv[1:]])
        resultado = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, argumentos, None, 1
        )
        if resultado <= 32:
            logger.error(f"No se pudo solicitar elevación de privilegios (código {resultado}).")
            return False
        return True

    comando = [sys.executable, os.path.abspath(sys.argv[0]), *sys.argv[1:]]

    if ES_MACOS:
        # osascript muestra el diálogo nativo de administrador.
        guion = (
            f'do shell script {shlex.quote(subprocess.list2cmdline(comando))} '
            f'with administrator privileges'
        )
        elevadores = [["osascript", "-e", guion]]
    else:
        elevadores = []
        for herramienta in ("pkexec", "sudo", "doas"):
            if _existe_ejecutable(herramienta):
                elevadores.append([herramienta, *comando])

    if not elevadores:
        logger.error("No se encontró ningún mecanismo de elevación en este sistema.")
        return False

    for elevador in elevadores:
        try:
            logger.info(f"Solicitando elevación con: {elevador[0]}")
            subprocess.Popen(elevador)
            return True
        except OSError as exc:
            logger.warning(f"{elevador[0]} no pudo iniciar la elevación: {exc}")
    return False


def _existe_ejecutable(nombre: str) -> bool:
    """Comprueba si un ejecutable está disponible en el PATH."""
    from shutil import which

    return which(nombre) is not None


def _solicitar_elevacion() -> Optional[bool]:
    """Pide elevar privilegios. Devuelve True si ya se relanzó la app elevada."""
    if _verificar_admin():
        return None

    logger.warning("Se requieren permisos de administrador para funcionar correctamente.")
    logger.info("Solicitando elevación de permisos...")

    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        resultado = messagebox.askyesno(
            "Permisos de Administrador",
            "Se requieren permisos de administrador para ejecutar esta aplicación.\n\n"
            "¿Desea continuar con elevación de permisos?\n\n"
            "Si elige 'No', la aplicación podría no funcionar correctamente."
        )
        root.destroy()

        if resultado:
            if _ejecutar_como_admin():
                # La nueva instancia elevada ya se lanzó; cerrar esta.
                return True
            logger.warning("Elevación cancelada o no disponible. Continuando sin permisos.")
        else:
            logger.warning("Ejecutando sin permisos de administrador. Funcionalidad limitada.")
    except Exception:
        logger.warning("No se pudo solicitar elevación. Continuando sin admin.")
    return None


def main():
    """Función principal de la aplicación."""
    logger.info("=" * 60)
    logger.info("Antivirus EACoreServer - Inicio de aplicación")
    logger.info("=" * 60)

    # 1) Intérprete: comprobación aislada, antes de importar nada del proyecto.
    interprete_ok, mensaje_interprete = _verificar_interprete()
    if not interprete_ok:
        _mostrar_aviso("Versión de Python no compatible", mensaje_interprete)
        sys.exit(1)

    # 2) Sistema operativo.
    soportado, motivo, resumen = _verificar_sistema()
    logger.info(f"Plataforma: {resumen}")
    if not soportado:
        _mostrar_aviso("Sistema operativo no soportado", motivo)
        sys.exit(1)
    if motivo:
        # Nota informativa: sistema soportado con matices (p. ej. Windows 7).
        logger.info(f"Compatibilidad: {motivo}")

    # 3) Privilegios.
    if _solicitar_elevacion():
        return

    # 4) Interfaz gráfica.
    try:
        from gui import ejecutar_aplicacion
        logger.info("Lanzando interfaz gráfica...")
        ejecutar_aplicacion()
    except ImportError as e:
        logger.error(f"No se pudo importar la interfaz gráfica: {e}")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"Error crítico al iniciar: {e}", exc_info=True)
        sys.exit(1)

    logger.info("Antivirus EACoreServer finalizado.")


if __name__ == "__main__":
    main()
