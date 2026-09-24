"""
Punto de entrada principal de Antivirus_EACoreServer.
Verifica permisos de administrador, inicializa componentes y lanza la GUI.
"""

import sys
import os
import ctypes
import logging

from logger import obtener_logger

logger = obtener_logger()


def _verificar_admin() -> bool:
    """Verifica si la aplicación se ejecuta como administrador."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def _ejecutar_como_admin():
    """Re-ejecuta la aplicación con privilegios de administrador."""
    import subprocess
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, os.path.abspath(sys.argv[0]), None, 1
    )
    sys.exit(0)


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
                _ejecutar_como_admin()
                return
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