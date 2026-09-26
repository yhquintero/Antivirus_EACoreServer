"""
Punto de entrada principal de Antivirus_EACoreServer.
Verifica permisos de administrador, inicializa componentes y lanza la GUI.

La comprobación de privilegios y la elevación son multiplataforma:
``IsUserAnAdmin``/``ShellExecuteW`` en Windows, ``geteuid`` con ``osascript`` en
macOS y ``geteuid`` con ``pkexec`` o ``sudo`` en Linux.
"""

import sys
import os
import ctypes
import logging
import platform

from logger import obtener_logger

logger = obtener_logger()

ES_WINDOWS = os.name == "nt"
_SISTEMA = platform.system().lower()
ES_MACOS = _SISTEMA == "darwin"
ES_LINUX = _SISTEMA == "linux"


def _verificar_admin() -> bool:
    """Verifica si la aplicación se ejecuta con privilegios elevados."""
    if ES_WINDOWS:
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    # macOS y Linux: el usuario efectivo 0 es root.
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def _ejecutar_como_admin() -> bool:
    """Re-ejecuta la aplicación con privilegios, conservando argumentos.

    En Windows ``ShellExecuteW`` recibe los parámetros como una sola cadena; usar
    ``list2cmdline`` evita que una instalación en una ruta con espacios falle.
    En macOS se delega en ``osascript`` y en Linux en ``pkexec`` o ``sudo``.
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
        for herramienta in ("pkexec", "sudo"):
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


def main():
    """Función principal de la aplicación."""
    logger.info("=" * 60)
    logger.info("Antivirus EACoreServer - Inicio de aplicación")
    logger.info("=" * 60)
    
    # Verificar permisos de administrador
    if not _verificar_admin():
        logger.warning("Se requieren permisos de administrador para funcionar correctamente.")
        logger.info("Solicitando elevación de permisos...")
        
        # Mostrar diálogo al usuario
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
                    return
                logger.warning("Elevación cancelada o no disponible. Continuando sin permisos.")
            else:
                logger.warning("Ejecutando sin permisos de administrador. Funcionalidad limitada.")
        except Exception:
            logger.warning("No se pudo solicitar elevación. Continuando sin admin.")
    
    # Importar y lanzar la GUI
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