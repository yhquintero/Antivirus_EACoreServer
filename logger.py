"""
Módulo de logging centralizado para la aplicación Antivirus EACoreServer.
Todos los mensajes se registran en español.
"""

import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


class AntivirusLogger:
    """Gestor de logs para la aplicación antivirus."""
    
    _instance: Optional['AntivirusLogger'] = None
    _logger: Optional[logging.Logger] = None
    
    def __new__(cls) -> 'AntivirusLogger':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        if self._logger is not None:
            return
            
        self._logger = logging.getLogger("AntivirusEACoreServer")
        self._logger.setLevel(logging.DEBUG)
        
        # Evitar duplicados si ya se inicializó
        if self._logger.handlers:
            return
        
        # Formato de log
        log_format = logging.Formatter(
            fmt='%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Handler para consola
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(log_format)
        self._logger.addHandler(console_handler)
        
        # Handler para archivo con rotación
        log_dir = Path.home() / "Antivirus_EACoreServer_Logs"
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f"antivirus_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=7,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(log_format)
        self._logger.addHandler(file_handler)
    
    def info(self, mensaje: str) -> None:
        """Registra mensaje informativo."""
        self._logger.info(mensaje)
    
    def debug(self, mensaje: str) -> None:
        """Registra mensaje de depuración."""
        self._logger.debug(mensaje)
    
    def warning(self, mensaje: str) -> None:
        """Registra advertencia."""
        self._logger.warning(mensaje)
    
    def error(self, mensaje: str, exc_info: bool = False) -> None:
        """Registra error."""
        self._logger.error(mensaje, exc_info=exc_info)
    
    def critical(self, mensaje: str, exc_info: bool = True) -> None:
        """Registra error crítico."""
        self._logger.critical(mensaje, exc_info=exc_info)
    
    def log_accion_usb(self, unidad: str, accion: str, detalle: str = "") -> None:
        """Registra acción específica de reparación USB."""
        msg = f"[USB:{unidad}] {accion}"
        if detalle:
            msg += f" - {detalle}"
        self._logger.info(msg)
    
    def log_proceso_ea(self, ruta: str, accion: str, exito: bool = True) -> None:
        """Registra acción sobre proceso EACoreServer."""
        estado = "ÉXITO" if exito else "FALLO"
        self._logger.info(f"[EACoreServer] {ruta} | {accion} | {estado}")


# Instancia global
logger = AntivirusLogger()


def obtener_logger() -> AntivirusLogger:
    """Retorna la instancia del logger."""
    return logger