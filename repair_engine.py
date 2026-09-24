"""
Motor de reparación de unidades USB infectadas por el malware Kaspersky/Usb Drive.
Restaura archivos ocultos, elimina archivos del virus y limpia la estructura maliciosa.
"""

import os
import shutil
import stat
import time
import ctypes
from ctypes import wintypes
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Callable
from dataclasses import dataclass, field
from enum import Enum
from logger import obtener_logger

logger = obtener_logger()

# Constantes de atributos de archivo Windows
FILE_ATTRIBUTE_READONLY = 0x01
FILE_ATTRIBUTE_HIDDEN = 0x02
FILE_ATTRIBUTE_SYSTEM = 0x04
FILE_ATTRIBUTE_DIRECTORY = 0x10
FILE_ATTRIBUTE_ARCHIVE = 0x20

# Atributos que el virus pone: -a -r -h -s (archive, readonly, hidden, system)
ATRIBUTOS_VIRUS = (
    FILE_ATTRIBUTE_ARCHIVE | 
    FILE_ATTRIBUTE_READONLY | 
    FILE_ATTRIBUTE_HIDDEN | 
    FILE_ATTRIBUTE_SYSTEM
)

# Kernel32 para operaciones de atributos
kernel32 = ctypes.windll.kernel32
GetFileAttributesW = kernel32.GetFileAttributesW
GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
GetFileAttributesW.restype = wintypes.DWORD

SetFileAttributesW = kernel32.SetFileAttributesW
SetFileAttributesW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
SetFileAttributesW.restype = wintypes.BOOL


class EstadoReparacion(Enum):
    """Estados del proceso de reparación"""
    PENDIENTE = "pendiente"
    EN_PROGRESO = "en_progreso"
    COMPLETADO = "completado"
    COMPLETADO_CON_ERRORES = "completado_con_errores"
    FALLIDO = "fallido"
    SIN_INFECCION = "sin_infeccion"


@dataclass
class ResultadoReparacion:
    """Resultado de la reparación de una unidad"""
    unidad: str
    estado: EstadoReparacion
    archivos_movidos: int = 0
    carpetas_movidas: int = 0
    archivos_eliminados: List[str] = field(default_factory=list)
    carpetas_eliminadas: List[str] = field(default_factory=list)
    errores: List[str] = field(default_factory=list)
    tiempo_inicio: float = field(default_factory=time.time)
    tiempo_fin: Optional[float] = None
    
    @property
    def duracion(self) -> float:
        if self.tiempo_fin:
            return self.tiempo_fin - self.tiempo_inicio
        return time.time() - self.tiempo_inicio
    
    def agregar_error(self, error: str) -> None:
        self.errores.append(error)
        logger.log_accion_usb(self.unidad, "ERROR", error)
    
    def agregar_movido(self, origen: str, destino: str, es_carpeta: bool = False) -> None:
        if es_carpeta:
            self.carpetas_movidas += 1
        else:
            self.archivos_movidos += 1
        logger.log_accion_usb(self.unidad, "MOVIDO", f"{origen} -> {destino}")
    
    def agregar_eliminado_archivo(self, ruta: str) -> None:
        self.archivos_eliminados.append(ruta)
        logger.log_accion_usb(self.unidad, "ELIMINADO_ARCHIVO", ruta)
    
    def agregar_eliminada_carpeta(self, ruta: str) -> None:
        self.carpetas_eliminadas.append(ruta)
        logger.log_accion_usb(self.unidad, "ELIMINADA_CARPETA", ruta)


class MotorReparacionUSB:
    r"""
    Motor principal para reparar unidades USB infectadas.
    Estructura del virus:
    [Unidad]:\Kaspersky\Usb Drive\  (atributos -a -r -h -s)
        ├── [archivos y carpetas originales del usuario]
        └── 3.0\
            ├── 3.dat
            ├── 4.dat
            ├── 5.dat
            ├── 6.dat
            └── 7.dat
    """
    
    ARCHIVOS_VIRUS = ["3.dat", "4.dat", "5.dat", "6.dat", "7.dat"]
    CARPETA_VIRUS_PRINCIPAL = "Kaspersky"
    CARPETA_USB_DRIVE = "Usb Drive"
    CARPETA_BASES_DATOS = "3.0"
    
    def __init__(self) -> None:
        self._cancelar = False
    
    def cancelar(self) -> None:
        """Solicita cancelación de la reparación en curso."""
        self._cancelar = True
        logger.info("Cancelación de reparación solicitada")
    
    def reparar_unidad(self, letra_unidad: str, callback_progreso: Optional[Callable[[int, str], None]] = None) -> ResultadoReparacion:
        """
        Repara una unidad infectada.
        
        Args:
            letra_unidad: Letra de la unidad (ej: "E:" o "E:\\")
            callback_progreso: Función opcional(porcentaje: int, mensaje: str)
            
        Returns:
            ResultadoReparacion con detalles de la operación.
        """
        self._cancelar = False
        unidad = letra_unidad.rstrip("\\").rstrip(":") + ":"
        ruta_raiz = f"{unidad}\\"
        
        resultado = ResultadoReparacion(unidad=unidad, estado=EstadoReparacion.EN_PROGRESO)
        logger.log_accion_usb(unidad, "INICIO_REPARACION", f"Iniciando reparación de {ruta_raiz}")
        
        def actualizar_progreso(pct: int, msg: str):
            if callback_progreso:
                callback_progreso(pct, msg)
        
        try:
            # Paso 1: Verificar estructura del virus
            actualizar_progreso(10, "Verificando estructura del virus...")
            ruta_kaspersky = os.path.join(ruta_raiz, self.CARPETA_VIRUS_PRINCIPAL)
            ruta_usb_drive = os.path.join(ruta_kaspersky, self.CARPETA_USB_DRIVE)
            ruta_bases_datos = os.path.join(ruta_usb_drive, self.CARPETA_BASES_DATOS)
            
            if not os.path.exists(ruta_kaspersky):
                resultado.estado = EstadoReparacion.SIN_INFECCION
                resultado.tiempo_fin = time.time()
                logger.log_accion_usb(unidad, "SIN_INFECCION", "No se encontró carpeta Kaspersky")
                actualizar_progreso(100, "Unidad limpia - sin infección detectada")
                return resultado
            
            if not os.path.exists(ruta_usb_drive):
                resultado.agregar_error("Carpeta Kaspersky existe pero no contiene 'Usb Drive'")
                resultado.estado = EstadoReparacion.FALLIDO
                resultado.tiempo_fin = time.time()
                return resultado
            
            logger.log_accion_usb(unidad, "INFECCION_DETECTADA", f"Estructura encontrada en {ruta_kaspersky}")
            actualizar_progreso(20, "Infección detectada - quitando atributos...")
            
            # Paso 2: Quitar atributos de oculto/sistema/solo lectura
            self._quitar_atributos_recursivo(ruta_kaspersky, resultado)
            if self._cancelar:
                resultado.estado = EstadoReparacion.FALLIDO
                resultado.agregar_error("Reparación cancelada por el usuario")
                resultado.tiempo_fin = time.time()
                return resultado
            
            actualizar_progreso(40, "Moviendo archivos originales a la raíz...")
            
            # Paso 3: Mover contenido de Usb Drive\ a la raíz
            self._mover_contenido_a_raiz(ruta_usb_drive, ruta_raiz, resultado)
            if self._cancelar:
                resultado.estado = EstadoReparacion.FALLIDO
                resultado.agregar_error("Reparación cancelada por el usuario")
                resultado.tiempo_fin = time.time()
                return resultado
            
            actualizar_progreso(70, "Eliminando archivos del virus...")
            
            # Paso 4: Eliminar archivos .dat y carpetas del virus
            self._eliminar_archivos_virus(ruta_bases_datos, resultado)
            if self._cancelar:
                resultado.estado = EstadoReparacion.FALLIDO
                resultado.agregar_error("Reparación cancelada por el usuario")
                resultado.tiempo_fin = time.time()
                return resultado
            
            self._eliminar_carpetas_virus(ruta_usb_drive, ruta_kaspersky, resultado)
            if self._cancelar:
                resultado.estado = EstadoReparacion.FALLIDO
                resultado.agregar_error("Reparación cancelada por el usuario")
                resultado.tiempo_fin = time.time()
                return resultado
            
            actualizar_progreso(90, "Verificando limpieza...")
            
            # Paso 5: Verificar que quedó limpio
            if self._verificar_limpieza(ruta_raiz):
                resultado.estado = EstadoReparacion.COMPLETADO
                logger.log_accion_usb(unidad, "REPARACION_EXITOSA", 
                    f"Archivos movidos: {resultado.archivos_movidos}, Carpetas movidas: {resultado.carpetas_movidas}, "
                    f"Archivos eliminados: {len(resultado.archivos_eliminados)}")
            else:
                resultado.estado = EstadoReparacion.COMPLETADO_CON_ERRORES
                resultado.agregar_error("Quedan restos de la infección después de la reparación")
            
        except Exception as e:
            logger.log_accion_usb(unidad, "ERROR_CRITICO", str(e), )
            resultado.estado = EstadoReparacion.FALLIDO
            resultado.agregar_error(f"Error crítico: {e}")
        
        finally:
            resultado.tiempo_fin = time.time()
            actualizar_progreso(100, f"Finalizado: {resultado.estado.value}")
        
        return resultado
    
    def _quitar_atributos_recursivo(self, ruta_inicio: str, resultado: ResultadoReparacion) -> None:
        """Quita atributos de oculto, sistema, solo lectura y archivo recursivamente."""
        try:
            for raiz, dirs, archivos in os.walk(ruta_inicio, topdown=False):
                # Primero archivos
                for archivo in archivos:
                    ruta_completa = os.path.join(raiz, archivo)
                    self._quitar_atributos_archivo(ruta_completa, resultado)
                
                # Luego directorios
                for dir_name in dirs:
                    ruta_completa = os.path.join(raiz, dir_name)
                    self._quitar_atributos_archivo(ruta_completa, resultado)
            
            # Finalmente la raíz
            self._quitar_atributos_archivo(ruta_inicio, resultado)
            
        except Exception as e:
            resultado.agregar_error(f"Error quitando atributos: {e}")
    
    def _quitar_atributos_archivo(self, ruta: str, resultado: ResultadoReparacion) -> bool:
        """Quita los atributos de un archivo/carpeta específico."""
        try:
            # Obtener atributos actuales
            attrs = GetFileAttributesW(ruta)
            if attrs == 0xFFFFFFFF:  # INVALID_FILE_ATTRIBUTES
                error = ctypes.GetLastError()
                if error != 2:  # FILE_NOT_FOUND
                    resultado.agregar_error(f"No se pudieron obtener atributos de {ruta}: Error {error}")
                return False
            
            # Quitar atributos del virus (hidden, system, readonly, archive)
            nuevos_attrs = attrs & ~ATRIBUTOS_VIRUS
            
            # Asegurar que quede solo como archivo normal o directorio
            if attrs & FILE_ATTRIBUTE_DIRECTORY:
                nuevos_attrs = FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_ARCHIVE
            else:
                nuevos_attrs = FILE_ATTRIBUTE_ARCHIVE
            
            if nuevos_attrs != attrs:
                if not SetFileAttributesW(ruta, nuevos_attrs):
                    error = ctypes.GetLastError()
                    resultado.agregar_error(f"No se pudieron cambiar atributos de {ruta}: Error {error}")
                    return False
                logger.debug(f"Atributos cambiados: {ruta} (0x{attrs:X} -> 0x{nuevos_attrs:X})")
            
            return True
            
        except Exception as e:
            resultado.agregar_error(f"Excepción quitando atributos de {ruta}: {e}")
            return False
    
    def _mover_contenido_a_raiz(self, origen: str, destino: str, resultado: ResultadoReparacion) -> None:
        """Mueve todo el contenido de origen a destino, preservando estructura."""
        if not os.path.exists(origen):
            resultado.agregar_error(f"Origen no existe: {origen}")
            return
        
        try:
            for item in os.listdir(origen):
                if self._cancelar:
                    return
                    
                ruta_origen = os.path.join(origen, item)
                ruta_destino = os.path.join(destino, item)
                
                # Saltar la carpeta 3.0 (bases de datos del virus)
                if item == self.CARPETA_BASES_DATOS:
                    continue
                
                try:
                    if os.path.isdir(ruta_origen):
                        self._mover_carpeta(ruta_origen, ruta_destino, resultado)
                    else:
                        self._mover_archivo(ruta_origen, ruta_destino, resultado)
                except Exception as e:
                    resultado.agregar_error(f"Error moviendo {item}: {e}")
                    
        except Exception as e:
            resultado.agregar_error(f"Error listando contenido de {origen}: {e}")
    
    def _mover_archivo(self, origen: str, destino: str, resultado: ResultadoReparacion) -> None:
        """Mueve un archivo, manejando colisiones."""
        if os.path.exists(destino):
            # Si ya existe, crear nombre único
            base, ext = os.path.splitext(destino)
            contador = 1
            while os.path.exists(destino):
                destino = f"{base}_{contador}{ext}"
                contador += 1
            resultado.agregar_error(f"Colisión resuelta: {os.path.basename(origen)} -> {os.path.basename(destino)}")
        
        try:
            shutil.move(origen, destino)
            resultado.agregar_movido(origen, destino, es_carpeta=False)
        except Exception as e:
            resultado.agregar_error(f"Error moviendo archivo {origen}: {e}")
            raise
    
    def _mover_carpeta(self, origen: str, destino: str, resultado: ResultadoReparacion) -> None:
        """Mueve una carpeta recursivamente."""
        if os.path.exists(destino):
            # Fusionar carpetas
            self._fusionar_carpetas(origen, destino, resultado)
        else:
            try:
                shutil.move(origen, destino)
                resultado.agregar_movido(origen, destino, es_carpeta=True)
            except Exception as e:
                resultado.agregar_error(f"Error moviendo carpeta {origen}: {e}")
                raise
    
    def _fusionar_carpetas(self, origen: str, destino: str, resultado: ResultadoReparacion) -> None:
        """Fusiona el contenido de origen en destino."""
        for item in os.listdir(origen):
            if self._cancelar:
                return
                
            ruta_origen = os.path.join(origen, item)
            ruta_destino = os.path.join(destino, item)
            
            try:
                if os.path.isdir(ruta_origen):
                    if os.path.exists(ruta_destino):
                        self._fusionar_carpetas(ruta_origen, ruta_destino, resultado)
                    else:
                        shutil.move(ruta_origen, ruta_destino)
                        resultado.agregar_movido(ruta_origen, ruta_destino, es_carpeta=True)
                else:
                    self._mover_archivo(ruta_origen, ruta_destino, resultado)
            except Exception as e:
                resultado.agregar_error(f"Error fusionando {item}: {e}")
        
        # Intentar eliminar carpeta origen ya vacía
        try:
            os.rmdir(origen)
        except Exception:
            pass
    
    def _eliminar_archivos_virus(self, ruta_bases_datos: str, resultado: ResultadoReparacion) -> None:
        """Elimina los archivos .dat del virus."""
        if not os.path.exists(ruta_bases_datos):
            return
        
        for archivo_virus in self.ARCHIVOS_VIRUS:
            if self._cancelar:
                return
                
            ruta_archivo = os.path.join(ruta_bases_datos, archivo_virus)
            if os.path.exists(ruta_archivo):
                try:
                    # Asegurar atributos normales antes de eliminar
                    self._quitar_atributos_archivo(ruta_archivo, resultado)
                    os.remove(ruta_archivo)
                    resultado.agregar_eliminado_archivo(ruta_archivo)
                except Exception as e:
                    resultado.agregar_error(f"Error eliminando {archivo_virus}: {e}")
    
    def _eliminar_carpetas_virus(self, ruta_usb_drive: str, ruta_kaspersky: str, resultado: ResultadoReparacion) -> None:
        """Elimina las carpetas del virus en orden: 3.0, Usb Drive, Kaspersky."""
        # Orden de eliminación (de más interno a más externo)
        carpetas_eliminar = [
            (os.path.join(ruta_usb_drive, self.CARPETA_BASES_DATOS), "3.0"),
            (ruta_usb_drive, "Usb Drive"),
            (ruta_kaspersky, "Kaspersky"),
        ]
        
        for ruta_carpeta, nombre in carpetas_eliminar:
            if self._cancelar:
                return
                
            if os.path.exists(ruta_carpeta):
                try:
                    # Quitar atributos primero
                    self._quitar_atributos_recursivo(ruta_carpeta, resultado)
                    # Eliminar (debe estar vacía salvo 3.0 que ya eliminamos)
                    shutil.rmtree(ruta_carpeta, onerror=self._manejar_error_eliminar)
                    resultado.agregar_eliminada_carpeta(ruta_carpeta)
                except Exception as e:
                    resultado.agregar_error(f"Error eliminando carpeta {nombre}: {e}")
    
    def _manejar_error_eliminar(self, func, path, exc_info):
        """Manejador de errores para shutil.rmtree."""
        try:
            self._quitar_atributos_archivo(path, ResultadoReparacion(unidad=""))
            func(path)
        except Exception:
            pass
    
    def _verificar_limpieza(self, ruta_raiz: str) -> bool:
        """Verifica que no queden restos de la infección."""
        ruta_kaspersky = os.path.join(ruta_raiz, self.CARPETA_VIRUS_PRINCIPAL)
        return not os.path.exists(ruta_kaspersky)


# Instancia global
_motor_instancia: Optional[MotorReparacionUSB] = None


def obtener_motor_reparacion() -> MotorReparacionUSB:
    """Retorna la instancia singleton del motor de reparación."""
    global _motor_instancia
    if _motor_instancia is None:
        _motor_instancia = MotorReparacionUSB()
    return _motor_instancia