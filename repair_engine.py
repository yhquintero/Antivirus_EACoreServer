"""Reparación conservadora de unidades afectadas por Kaspersky/Usb Drive.

El motor no considera una carpeta llamada ``Kaspersky`` como prueba suficiente de
infección. Solo modifica una unidad después de encontrar la firma completa:
``Kaspersky/Usb Drive/3.0`` y los archivos de datos conocidos. Esta
precaución evita borrar carpetas legítimas que tengan un nombre parecido.
"""

from __future__ import annotations

import ctypes
import os
import shutil
import stat
import time
from ctypes import wintypes
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from logger import obtener_logger

logger = obtener_logger()

# Atributos de archivo de Windows. El módulo también puede importarse fuera de
# Windows para ejecutar las pruebas de detección; la reparación real está
# dirigida exclusivamente a unidades de Windows.
FILE_ATTRIBUTE_READONLY = 0x01
FILE_ATTRIBUTE_HIDDEN = 0x02
FILE_ATTRIBUTE_SYSTEM = 0x04
FILE_ATTRIBUTE_DIRECTORY = 0x10
FILE_ATTRIBUTE_ARCHIVE = 0x20
ATRIBUTOS_VIRUS = (
    FILE_ATTRIBUTE_ARCHIVE
    | FILE_ATTRIBUTE_READONLY
    | FILE_ATTRIBUTE_HIDDEN
    | FILE_ATTRIBUTE_SYSTEM
)
INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF

if os.name == "nt":
    _kernel32 = ctypes.windll.kernel32
    GetFileAttributesW = _kernel32.GetFileAttributesW
    GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
    GetFileAttributesW.restype = wintypes.DWORD
    SetFileAttributesW = _kernel32.SetFileAttributesW
    SetFileAttributesW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
    SetFileAttributesW.restype = wintypes.BOOL
else:  # pragma: no cover - usado para importación y pruebas multiplataforma
    GetFileAttributesW = None
    SetFileAttributesW = None


class EstadoDeteccion(Enum):
    """Resultado de validar la firma de infección antes de reparar."""

    LIMPIA = "limpia"
    SOSPECHOSA = "sospechosa"
    CONFIRMADA = "confirmada"
    INACCESIBLE = "inaccesible"


@dataclass(frozen=True)
class DeteccionInfeccion:
    """Diagnóstico no destructivo de una ruta de unidad."""

    ruta_raiz: str
    estado: EstadoDeteccion
    archivos_firma: Tuple[str, ...] = ()
    detalle: str = ""

    @property
    def confirmada(self) -> bool:
        return self.estado is EstadoDeteccion.CONFIRMADA


class EstadoReparacion(Enum):
    """Estados finales de una reparación."""

    PENDIENTE = "pendiente"
    EN_PROGRESO = "en_progreso"
    COMPLETADO = "completado"
    COMPLETADO_CON_ERRORES = "completado_con_errores"
    FALLIDO = "fallido"
    SIN_INFECCION = "sin_infeccion"
    REQUIERE_REVISION = "requiere_revision"


@dataclass
class ResultadoReparacion:
    """Detalle auditable de una reparación."""

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
        return (self.tiempo_fin or time.time()) - self.tiempo_inicio

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
    """Restaura archivos sin borrar contenido no reconocido.

    La firma requerida contiene *todos* los archivos 5.dat al 7.dat. Cuando la
    estructura está incompleta se informa como sospechosa y se deja intacta para
    revisión humana. Durante la limpieza solo se eliminan dichos archivos y las
    carpetas que queden vacías; nunca se usa ``rmtree`` sobre contenido que no
    haya sido identificado.
    """

    ARCHIVOS_VIRUS = ("5.dat", "6.dat", "7.dat")
    CARPETA_VIRUS_PRINCIPAL = "Kaspersky"
    CARPETA_USB_DRIVE = "Usb Drive"
    CARPETA_BASES_DATOS = "3.0"

    def __init__(self) -> None:
        self._cancelar = False

    def cancelar(self) -> None:
        """Solicita una cancelación cooperativa de la operación en curso."""
        self._cancelar = True
        logger.info("Cancelación de reparación solicitada")

    def analizar_unidad(self, letra_unidad: str) -> DeteccionInfeccion:
        """Analiza una letra de unidad sin modificar archivos."""
        return self.analizar_ruta(self._ruta_desde_unidad(letra_unidad))

    def analizar_ruta(self, ruta_raiz: str | Path) -> DeteccionInfeccion:
        """Analiza una ruta raíz; útil para la GUI y pruebas no destructivas."""
        raiz = Path(ruta_raiz)
        ruta_kaspersky = raiz / self.CARPETA_VIRUS_PRINCIPAL
        ruta_usb_drive = ruta_kaspersky / self.CARPETA_USB_DRIVE
        ruta_bases = ruta_usb_drive / self.CARPETA_BASES_DATOS

        try:
            if not ruta_kaspersky.exists():
                return DeteccionInfeccion(str(raiz), EstadoDeteccion.LIMPIA)
            if not ruta_usb_drive.is_dir():
                return DeteccionInfeccion(
                    str(raiz), EstadoDeteccion.SOSPECHOSA,
                    detalle="Existe la carpeta Kaspersky, pero no la estructura Usb Drive.",
                )
            if not ruta_bases.is_dir():
                return DeteccionInfeccion(
                    str(raiz), EstadoDeteccion.SOSPECHOSA,
                    detalle="Existe Usb Drive, pero falta la carpeta de datos 3.0.",
                )

            encontrados = tuple(
                nombre for nombre in self.ARCHIVOS_VIRUS if (ruta_bases / nombre).is_file()
            )
            if len(encontrados) == len(self.ARCHIVOS_VIRUS):
                return DeteccionInfeccion(
                    str(raiz), EstadoDeteccion.CONFIRMADA, encontrados,
                    "Se encontró la firma completa Kaspersky/Usb Drive/3.0.",
                )
            return DeteccionInfeccion(
                str(raiz), EstadoDeteccion.SOSPECHOSA, encontrados,
                "La estructura coincide parcialmente, pero no contiene los cinco archivos de firma.",
            )
        except OSError as exc:
            return DeteccionInfeccion(
                str(raiz), EstadoDeteccion.INACCESIBLE,
                detalle=f"No se pudo leer la unidad: {exc}",
            )

    def reparar_unidad(
        self,
        letra_unidad: str,
        callback_progreso: Optional[Callable[[int, str], None]] = None,
    ) -> ResultadoReparacion:
        """Repara una letra de unidad después de validar la firma completa."""
        unidad = letra_unidad.rstrip("\\").rstrip(":") + ":"
        return self.reparar_ruta(self._ruta_desde_unidad(unidad), callback_progreso, unidad)

    def reparar_ruta(
        self,
        ruta_raiz: str | Path,
        callback_progreso: Optional[Callable[[int, str], None]] = None,
        nombre_unidad: Optional[str] = None,
    ) -> ResultadoReparacion:
        """Repara una raíz ya validada.

        Esta variante permite probar el motor en un directorio temporal. La GUI
        usa :meth:`reparar_unidad` para letras de unidad Windows.
        """
        self._cancelar = False
        raiz = Path(ruta_raiz)
        unidad = nombre_unidad or str(raiz)
        resultado = ResultadoReparacion(unidad=unidad, estado=EstadoReparacion.EN_PROGRESO)

        def progreso(porcentaje: int, mensaje: str) -> None:
            if callback_progreso:
                callback_progreso(porcentaje, mensaje)

        logger.log_accion_usb(unidad, "INICIO_REPARACION", f"Iniciando reparación de {raiz}")
        try:
            progreso(5, "Validando firma de infección…")
            deteccion = self.analizar_ruta(raiz)
            if deteccion.estado is EstadoDeteccion.LIMPIA:
                resultado.estado = EstadoReparacion.SIN_INFECCION
                progreso(100, "Unidad limpia: no se detectó la firma de infección")
                return resultado
            if not deteccion.confirmada:
                resultado.estado = EstadoReparacion.REQUIERE_REVISION
                resultado.agregar_error(deteccion.detalle or "Firma de infección no confirmada")
                progreso(100, "Revisión manual requerida; no se modificó ningún archivo")
                return resultado

            ruta_kaspersky = raiz / self.CARPETA_VIRUS_PRINCIPAL
            ruta_usb_drive = ruta_kaspersky / self.CARPETA_USB_DRIVE
            ruta_bases = ruta_usb_drive / self.CARPETA_BASES_DATOS
            logger.log_accion_usb(unidad, "INFECCION_CONFIRMADA", deteccion.detalle)

            progreso(15, "Quitando atributos protectores…")
            self._quitar_atributos_recursivo(ruta_kaspersky, resultado)
            if self._fue_cancelada(resultado):
                return resultado

            progreso(40, "Restaurando archivos originales a la raíz…")
            self._mover_contenido_a_raiz(ruta_usb_drive, raiz, resultado)
            if self._fue_cancelada(resultado):
                return resultado

            progreso(70, "Eliminando únicamente los archivos de firma…")
            self._eliminar_archivos_virus(ruta_bases, resultado)
            if self._fue_cancelada(resultado):
                return resultado

            progreso(85, "Eliminando solo carpetas vacías…")
            self._eliminar_carpetas_vacias(ruta_bases, ruta_usb_drive, ruta_kaspersky, resultado)
            if self._fue_cancelada(resultado):
                return resultado

            progreso(95, "Verificando limpieza…")
            if not ruta_kaspersky.exists():
                resultado.estado = EstadoReparacion.COMPLETADO
                logger.log_accion_usb(
                    unidad,
                    "REPARACION_EXITOSA",
                    f"Archivos movidos: {resultado.archivos_movidos}; "
                    f"carpetas movidas: {resultado.carpetas_movidas}; "
                    f"archivos eliminados: {len(resultado.archivos_eliminados)}",
                )
            else:
                # No se fuerza el borrado de restos desconocidos. El resultado
                # deja una pista clara en el log para la revisión manual.
                resultado.estado = EstadoReparacion.COMPLETADO_CON_ERRORES
                resultado.agregar_error(
                    "Quedó contenido no reconocido o bloqueado; no se eliminó de forma forzada."
                )
        except Exception as exc:
            logger.error(f"Error crítico reparando {unidad}: {exc}", exc_info=True)
            resultado.estado = EstadoReparacion.FALLIDO
            resultado.agregar_error(f"Error crítico: {exc}")
        finally:
            resultado.tiempo_fin = time.time()
            progreso(100, f"Finalizado: {resultado.estado.value}")

        return resultado

    @staticmethod
    def _ruta_desde_unidad(letra_unidad: str) -> str:
        return letra_unidad.rstrip("\\").rstrip(":") + ":\\"

    def _fue_cancelada(self, resultado: ResultadoReparacion) -> bool:
        if not self._cancelar:
            return False
        resultado.estado = EstadoReparacion.FALLIDO
        resultado.agregar_error("Reparación cancelada por el usuario")
        return True

    def _quitar_atributos_recursivo(self, ruta_inicio: Path, resultado: ResultadoReparacion) -> None:
        """Quita atributos Windows sin seguir enlaces simbólicos."""
        try:
            for raiz, directorios, archivos in os.walk(ruta_inicio, topdown=False, followlinks=False):
                for archivo in archivos:
                    self._quitar_atributos_archivo(Path(raiz) / archivo, resultado)
                for directorio in directorios:
                    self._quitar_atributos_archivo(Path(raiz) / directorio, resultado)
            self._quitar_atributos_archivo(ruta_inicio, resultado)
        except OSError as exc:
            resultado.agregar_error(f"Error quitando atributos: {exc}")

    def _quitar_atributos_archivo(self, ruta: Path, resultado: ResultadoReparacion) -> bool:
        """Normaliza atributos para permitir la restauración o eliminación."""
        try:
            if os.name != "nt":
                # Modo de prueba/no Windows: asegurar escritura sin cambiar el
                # tipo de archivo. La API real de atributos es exclusiva de Win32.
                ruta.chmod(ruta.stat().st_mode | stat.S_IWRITE)
                return True

            assert GetFileAttributesW is not None and SetFileAttributesW is not None
            atributos = GetFileAttributesW(str(ruta))
            if atributos == INVALID_FILE_ATTRIBUTES:
                error = ctypes.get_last_error()
                if error != 2:  # ERROR_FILE_NOT_FOUND
                    resultado.agregar_error(f"No se pudieron leer atributos de {ruta}: error {error}")
                return False

            nuevos = FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_ARCHIVE if atributos & FILE_ATTRIBUTE_DIRECTORY else FILE_ATTRIBUTE_ARCHIVE
            if atributos != nuevos and not SetFileAttributesW(str(ruta), nuevos):
                resultado.agregar_error(
                    f"No se pudieron cambiar atributos de {ruta}: error {ctypes.get_last_error()}"
                )
                return False
            return True
        except OSError as exc:
            resultado.agregar_error(f"No se pudieron cambiar atributos de {ruta}: {exc}")
            return False

    def _mover_contenido_a_raiz(self, origen: Path, destino: Path, resultado: ResultadoReparacion) -> None:
        for ruta_origen in origen.iterdir():
            if self._cancelar:
                return
            if ruta_origen.name == self.CARPETA_BASES_DATOS:
                continue
            if ruta_origen.is_symlink():
                resultado.agregar_error(f"Enlace simbólico omitido por seguridad: {ruta_origen}")
                continue

            ruta_destino = destino / ruta_origen.name
            try:
                if ruta_origen.is_dir():
                    self._mover_carpeta(ruta_origen, ruta_destino, resultado)
                else:
                    self._mover_archivo(ruta_origen, ruta_destino, resultado)
            except OSError as exc:
                resultado.agregar_error(f"Error moviendo {ruta_origen.name}: {exc}")

    def _mover_archivo(self, origen: Path, destino: Path, resultado: ResultadoReparacion) -> None:
        destino_final = self._ruta_sin_colision(destino)
        if destino_final != destino:
            resultado.agregar_error(
                f"Colisión resuelta: {origen.name} -> {destino_final.name}"
            )
        shutil.move(str(origen), str(destino_final))
        resultado.agregar_movido(str(origen), str(destino_final), es_carpeta=False)

    def _mover_carpeta(self, origen: Path, destino: Path, resultado: ResultadoReparacion) -> None:
        if not destino.exists():
            shutil.move(str(origen), str(destino))
            resultado.agregar_movido(str(origen), str(destino), es_carpeta=True)
            return
        self._fusionar_carpetas(origen, destino, resultado)

    def _fusionar_carpetas(self, origen: Path, destino: Path, resultado: ResultadoReparacion) -> None:
        for ruta_origen in list(origen.iterdir()):
            if self._cancelar:
                return
            if ruta_origen.is_symlink():
                resultado.agregar_error(f"Enlace simbólico omitido por seguridad: {ruta_origen}")
                continue
            ruta_destino = destino / ruta_origen.name
            try:
                if ruta_origen.is_dir():
                    if ruta_destino.exists():
                        self._fusionar_carpetas(ruta_origen, ruta_destino, resultado)
                    else:
                        shutil.move(str(ruta_origen), str(ruta_destino))
                        resultado.agregar_movido(str(ruta_origen), str(ruta_destino), es_carpeta=True)
                else:
                    self._mover_archivo(ruta_origen, ruta_destino, resultado)
            except OSError as exc:
                resultado.agregar_error(f"Error fusionando {ruta_origen.name}: {exc}")
        self._eliminar_directorio_si_vacio(origen, resultado, "contenido restaurado")

    @staticmethod
    def _ruta_sin_colision(destino: Path) -> Path:
        if not destino.exists():
            return destino
        contador = 1
        while True:
            candidata = destino.with_name(f"{destino.stem}_{contador}{destino.suffix}")
            if not candidata.exists():
                return candidata
            contador += 1

    def _eliminar_archivos_virus(self, ruta_bases: Path, resultado: ResultadoReparacion) -> None:
        for nombre in self.ARCHIVOS_VIRUS:
            if self._cancelar:
                return
            ruta = ruta_bases / nombre
            if not ruta.exists():
                continue
            try:
                self._quitar_atributos_archivo(ruta, resultado)
                ruta.unlink()
                resultado.agregar_eliminado_archivo(str(ruta))
            except OSError as exc:
                resultado.agregar_error(f"Error eliminando {nombre}: {exc}")

    def _eliminar_carpetas_vacias(
        self,
        ruta_bases: Path,
        ruta_usb_drive: Path,
        ruta_kaspersky: Path,
        resultado: ResultadoReparacion,
    ) -> None:
        for ruta, nombre in (
            (ruta_bases, "3.0"),
            (ruta_usb_drive, "Usb Drive"),
            (ruta_kaspersky, "Kaspersky"),
        ):
            if self._cancelar:
                return
            self._eliminar_directorio_si_vacio(ruta, resultado, nombre)

    def _eliminar_directorio_si_vacio(
        self, ruta: Path, resultado: ResultadoReparacion, nombre: str
    ) -> bool:
        if not ruta.exists():
            return True
        try:
            ruta.rmdir()
            resultado.agregar_eliminada_carpeta(str(ruta))
            return True
        except OSError:
            # No usar rmtree: cualquier elemento restante no es parte de la
            # firma conocida y se conserva para revisión.
            resultado.agregar_error(
                f"La carpeta {nombre} contiene elementos no reconocidos o está bloqueada; se conservó."
            )
            return False


_motor_instancia: Optional[MotorReparacionUSB] = None


def obtener_motor_reparacion() -> MotorReparacionUSB:
    """Retorna la instancia singleton del motor de reparación."""
    global _motor_instancia
    if _motor_instancia is None:
        _motor_instancia = MotorReparacionUSB()
    return _motor_instancia
