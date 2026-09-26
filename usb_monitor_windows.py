"""Backend exclusivo de Windows para el monitoreo de unidades USB.

Este módulo concentra **todo** el código que depende de Win32: ``pywin32``,
``ctypes.windll``, IOCTLs de almacenamiento y la ventana oculta que recibe
``WM_DEVICECHANGE``. Debe importarse únicamente en Windows; en macOS y Linux la
fachada :mod:`usb_monitor` usa sus propios backends.

La separación existe para que el resto del proyecto (motor de reparación, GUI,
pruebas y CI) pueda importarse y probarse en los tres sistemas operativos sin
que la ausencia de ``pywin32`` rompa la carga de módulos.
"""

from __future__ import annotations

import ctypes
import re
import threading
import time
from typing import Callable, List, Optional

import win32api
import win32con
import win32file
import win32gui

from logger import obtener_logger

# El modelo de datos y las constantes numéricas de tipo de unidad viven en la
# fachada multiplataforma para tener una única fuente de verdad.
from usb_monitor import (
    DRIVE_CDROM,
    DRIVE_FIXED,
    DRIVE_NO_ROOT_DIR,
    DRIVE_RAMDISK,
    DRIVE_REMOVABLE,
    DRIVE_UNKNOWN,
    UnidadExtraible,
)

logger = obtener_logger()

# ---------------------------------------------------------------------------
# Constantes de Windows
# ---------------------------------------------------------------------------
WM_DEVICECHANGE = 0x0219
DBT_DEVICEARRIVAL = 0x8000
DBT_DEVICEREMOVECOMPLETE = 0x8004
DBT_DEVTYP_VOLUME = 0x00000002
DEVICE_NOTIFY_WINDOW_HANDLE = 0x00000000

# IOCTLs de Windows
IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS = 0x00560000
IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400

# StorageBusType: BusTypeUsb = 0x0B (11)
BUS_TYPE_USB = 0x0B


# ---------------------------------------------------------------------------
# Estructuras ctypes para consultar el bus físico de un volumen
# ---------------------------------------------------------------------------
class _DISK_EXTENT(ctypes.Structure):
    _fields_ = [
        ("DiskNumber", ctypes.c_uint32),
        ("StartingOffset", ctypes.c_int64),
        ("ExtentLength", ctypes.c_int64),
    ]


class _VOLUME_DISK_EXTENTS(ctypes.Structure):
    _fields_ = [
        ("NumberOfDiskExtents", ctypes.c_uint32),
        ("Extents", _DISK_EXTENT * 1),
    ]


class _STORAGE_PROPERTY_QUERY(ctypes.Structure):
    _fields_ = [
        ("PropertyId", ctypes.c_uint32),      # StorageDeviceProperty = 0
        ("QueryType", ctypes.c_uint32),       # PropertyStandardQuery = 0
        ("AdditionalParameters", ctypes.c_ubyte * 1),
    ]


class _STORAGE_DEVICE_DESCRIPTOR(ctypes.Structure):
    _fields_ = [
        ("Version", ctypes.c_uint32),
        ("Size", ctypes.c_uint32),
        ("DeviceType", ctypes.c_ubyte),
        ("DeviceTypeModifier", ctypes.c_ubyte),
        ("RemovableMedia", ctypes.c_ubyte),
        ("CommandQueueing", ctypes.c_ubyte),
        ("VendorIdOffset", ctypes.c_uint32),
        ("ProductIdOffset", ctypes.c_uint32),
        ("SerialNumberOffset", ctypes.c_uint32),
        ("BusType", ctypes.c_uint32),
        ("RawPropertiesLength", ctypes.c_uint32),
        ("RawDeviceProperties", ctypes.c_ubyte * 1),
    ]


_DeviceIoControl = ctypes.windll.kernel32.DeviceIoControl
_DeviceIoControl.restype = ctypes.c_int

# Funciones ctypes de enumeración (independientes de pywin32)
GetLogicalDrives = ctypes.windll.kernel32.GetLogicalDrives
GetLogicalDrives.restype = ctypes.c_uint32

_GetDriveTypeW = ctypes.windll.kernel32.GetDriveTypeW
_GetDriveTypeW.argtypes = [ctypes.c_wchar_p]
_GetDriveTypeW.restype = ctypes.c_uint


# ---------------------------------------------------------------------------
# Detección de unidades
# ---------------------------------------------------------------------------
def obtener_info_unidad(letra: str) -> Optional[UnidadExtraible]:
    """Obtiene información detallada de una unidad (letra)."""
    ruta = f"{letra}:\\"
    etiqueta = ""
    sistema_archivos = ""
    numero_serie = ""
    try:
        # pywin32 GetVolumeInformation devuelve 6 valores:
        # (nombre, serie, maxLongitud, flags, sistemaArchivos, flagsFS)
        res = win32api.GetVolumeInformation(ruta)
        if len(res) >= 5:
            etiqueta = res[0] or ""
            numero_serie = res[1]
            sistema_archivos = res[4] or ""
    except Exception as e:
        logger.debug(f"Unidad {letra}: sin info de volumen ({e})")

    tamano_total = 0
    espacio_libre = 0
    try:
        libre, total, _ = win32file.GetDiskFreeSpaceEx(ruta)
        tamano_total = int(total)
        espacio_libre = int(libre)
    except Exception:
        try:
            sectores_por_cluster, bytes_por_sector, clusters_libres, clusters_totales = \
                win32file.GetDiskFreeSpace(ruta)
            bytes_por_cluster = sectores_por_cluster * bytes_por_sector
            tamano_total = clusters_totales * bytes_por_cluster
            espacio_libre = clusters_libres * bytes_por_cluster
        except Exception as e:
            logger.debug(f"Unidad {letra}: sin info de espacio ({e})")

    tipo = obtener_tipo_unidad(letra)
    try:
        serie = f"{numero_serie:08X}" if isinstance(numero_serie, int) and numero_serie else ""
    except Exception:
        serie = ""

    return UnidadExtraible(
        letra=f"{letra}:", ruta_raiz=ruta,
        etiqueta=etiqueta or "SIN_ETIQUETA",
        sistema_archivos=sistema_archivos,
        tamano_total=tamano_total,
        espacio_libre=espacio_libre,
        numero_serie=serie,
        tipo_drive=tipo
    )


def obtener_numero_disco_fisico(letra: str) -> Optional[int]:
    """Obtiene el número de disco físico que contiene el volumen."""
    try:
        manejador = win32file.CreateFile(
            f"\\\\.\\{letra}", 0,
            win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE | win32file.FILE_SHARE_DELETE,
            None, win32file.OPEN_EXISTING, 0, None
        )
    except Exception:
        return None

    try:
        buffer = ctypes.create_string_buffer(512)
        devueltos = ctypes.c_ulong(0)
        ok = _DeviceIoControl(
            int(manejador), IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS,
            None, 0, buffer, 512, ctypes.byref(devueltos), None
        )
        if not ok:
            return None
        extents = ctypes.cast(buffer, ctypes.POINTER(_VOLUME_DISK_EXTENTS)).contents
        if extents.NumberOfDiskExtents < 1:
            return None
        return extents.Extents[0].DiskNumber
    except Exception:
        return None
    finally:
        try:
            win32file.CloseHandle(manejador)
        except Exception:
            pass


def es_usb_por_bus_fisico(letra: str) -> bool:
    """
    Determina si el disco físico de un volumen es USB consultando STORAGE_DEVICE_DESCRIPTOR.
    Detecta correctamente memorias USB y discos externos que Windows
    clasifica como DRIVE_FIXED.
    """
    disco = obtener_numero_disco_fisico(letra)
    if disco is None:
        return False

    try:
        # Abrir con GENERIC_READ (privilegios mínimos); fallback a acceso 0
        try:
            manejador = win32file.CreateFile(
                f"\\\\.\\PhysicalDrive{disco}", win32file.GENERIC_READ,
                win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE | win32file.FILE_SHARE_DELETE,
                None, win32file.OPEN_EXISTING, 0, None
            )
        except Exception:
            manejador = win32file.CreateFile(
                f"\\\\.\\PhysicalDrive{disco}", 0,
                win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE | win32file.FILE_SHARE_DELETE,
                None, win32file.OPEN_EXISTING, 0, None
            )
    except Exception:
        return False

    try:
        consulta = _STORAGE_PROPERTY_QUERY()
        consulta.PropertyId = 0   # StorageDeviceProperty
        consulta.QueryType = 0    # PropertyStandardQuery
        buffer = ctypes.create_string_buffer(1024)
        devueltos = ctypes.c_ulong(0)
        ok = _DeviceIoControl(
            int(manejador), IOCTL_STORAGE_QUERY_PROPERTY,
            ctypes.byref(consulta), ctypes.sizeof(consulta),
            buffer, 1024, ctypes.byref(devueltos), None
        )
        if not ok:
            return False

        desc = ctypes.cast(buffer, ctypes.POINTER(_STORAGE_DEVICE_DESCRIPTOR)).contents
        logger.debug(
            f"Disco físico {disco} (unidad {letra}): BusType={desc.BusType}, "
            f"RemovableMedia={desc.RemovableMedia}"
        )
        return desc.BusType == BUS_TYPE_USB
    except Exception:
        return False
    finally:
        try:
            win32file.CloseHandle(manejador)
        except Exception:
            pass


def es_usb_por_wmi(letra: str) -> bool:
    """Verifica si un volumen pertenece a un disco USB mediante WMI.
    Funciona sin permisos elevados; complementa la consulta de bus físico."""
    try:
        import win32com.client
        wmi = win32com.client.GetObject("winmgmts:\\\\.\\root\\cimv2")

        # 1) Discos físicos con interfaz USB
        discos_usb = set()
        for disco in wmi.ExecQuery(
                "SELECT DeviceID FROM Win32_DiskDrive WHERE InterfaceType='USB'"):
            m = re.search(r"PHYSICALDRIVE(\d+)", str(disco.DeviceID or ""), re.IGNORECASE)
            if m:
                discos_usb.add(int(m.group(1)))
        if not discos_usb:
            return False

        # 2) Mapear el volumen (letra) a su disco físico
        letra_busca = f'"{letra}:"'
        for par in wmi.ExecQuery(
                "SELECT Antecedent, Dependent FROM Win32_LogicalDiskToPartition"):
            ant = str(getattr(par, "Antecedent", "")).lower().replace(" ", "")
            dep = str(getattr(par, "Dependent", ""))
            if letra_busca.lower() not in ant:
                continue
            m = re.search(r"Disk #(\d+)", dep, re.IGNORECASE)
            if m and int(m.group(1)) in discos_usb:
                logger.debug(f"WMI: unidad {letra} pertenece al disco USB físico #{m.group(1)}")
                return True
        return False
    except Exception as e:
        logger.debug(f"WMI no disponible para {letra}: {e}")
        return False


def enumerar_letras_existentes() -> List[str]:
    """Obtiene letras de unidades existentes con GetLogicalDrives (ctypes)."""
    mascara = GetLogicalDrives()
    letras = []
    for i in range(26):
        if mascara & (1 << i):
            letras.append(chr(ord("A") + i))
    return letras


def obtener_tipo_unidad(letra: str) -> int:
    """Obtiene el tipo de una unidad (GetDriveTypeW vía ctypes, con respaldo pywin32)."""
    try:
        return int(_GetDriveTypeW(f"{letra}:\\"))
    except Exception:
        try:
            return int(win32file.GetDriveType(f"{letra}:\\"))
        except Exception:
            return DRIVE_UNKNOWN


# Cache breve: consultar el bus físico en cada refresco de la GUI puede ser
# costoso y algunos lectores de tarjetas responden lentamente.
_cache_usb_fisico: dict[str, bool] = {}


def determinar_si_es_usb(letra: str, tipo: int) -> bool:
    """Clasifica de forma conservadora si la letra pertenece a un USB físico."""
    if tipo == DRIVE_REMOVABLE:
        return True
    if tipo != DRIVE_FIXED:
        return False
    if letra in _cache_usb_fisico:
        return _cache_usb_fisico[letra]
    es_usb = es_usb_por_bus_fisico(letra) or es_usb_por_wmi(letra)
    _cache_usb_fisico[letra] = es_usb
    return es_usb


def obtener_unidades_extraibles() -> List[UnidadExtraible]:
    """
    Obtiene las unidades con letra disponibles para diagnóstico. La lista puede
    incluir discos fijos y red, pero solo los medios extraíbles/USB físicos se
    marcan como reparables para evitar cambios accidentales en el sistema.
    """
    unidades = []
    unidades_existentes = []

    for letra in enumerar_letras_existentes():
        tipo = obtener_tipo_unidad(letra)

        # Registrar todas las unidades existentes para diagnóstico
        unidades_existentes.append((letra, tipo))

        if tipo in (DRIVE_UNKNOWN, DRIVE_NO_ROOT_DIR, DRIVE_CDROM, DRIVE_RAMDISK):
            logger.debug(f"Unidad {letra}: tipo={tipo} -> se omite (no escaneable)")
            continue

        info = obtener_info_unidad(letra)
        if info is None:
            # Red de seguridad: mostrar la unidad aunque los metadatos fallen
            info = UnidadExtraible(
                letra=f"{letra}:", ruta_raiz=f"{letra}:\\",
                etiqueta="(sin metadatos)", tipo_drive=tipo
            )
            logger.debug(f"Unidad {letra}: sin metadatos, agregada con datos mínimos")

        info.es_usb_fisico = determinar_si_es_usb(letra, tipo)
        unidades.append(info)
        logger.debug(
            f"Unidad detectada: {info.letra} tipo={tipo} usb_fisico={info.es_usb_fisico} "
            f"etiqueta='{info.etiqueta}' fs={info.sistema_archivos}"
        )

    if not unidades:
        logger.debug(f"No hay unidades disponibles. Letras existentes: "
                     f"{[f'{l}({t})' for l, t in unidades_existentes] or 'ninguna'}")

    return unidades


# ---------------------------------------------------------------------------
# Ventana oculta para WM_DEVICECHANGE
# ---------------------------------------------------------------------------
class _WindowProc:
    """Clase estática para almacenar el callback del procedimiento de ventana."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._callback_llegada: Optional[Callable] = None
        self._callback_remocion: Optional[Callable] = None
        self._enumerar: Callable[[], List[UnidadExtraible]] = obtener_unidades_extraibles
        self._sincronizar: Optional[Callable] = None

    def configurar_callbacks(self, llegada, remocion, sincronizar) -> None:
        """Configura los callbacks de llegada, remoción y sincronización."""
        self._callback_llegada = llegada
        self._callback_remocion = remocion
        self._sincronizar = sincronizar

    def WndProc(self, hwnd, msg, wparam, lparam):
        """Procedimiento de ventana que recibe mensajes WM_DEVICECHANGE."""
        if msg == WM_DEVICECHANGE:
            if wparam == DBT_DEVICEARRIVAL:
                threading.Thread(target=self._manejar_llegada, daemon=True).start()
            elif wparam == DBT_DEVICEREMOVECOMPLETE:
                threading.Thread(target=self._manejar_remocion, daemon=True).start()
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _manejar_llegada(self) -> None:
        """Maneja la llegada de un nuevo dispositivo."""
        try:
            time.sleep(0.4)
            unidades = self._enumerar()
            letras = {u.letra for u in unidades}
            nuevas, _ = self._sincronizar(letras) if self._sincronizar else (set(), set())

            for unidad in unidades:
                if unidad.letra in nuevas:
                    logger.info(f"Evento: nueva unidad extraíble {unidad.letra} ({unidad.etiqueta})")
                    if self._callback_llegada:
                        try:
                            self._callback_llegada(unidad)
                        except Exception as e:
                            logger.error(f"Error en callback de llegada USB: {e}")
        except Exception as e:
            logger.error(f"Error manejando llegada de dispositivo: {e}")

    def _manejar_remocion(self) -> None:
        """Maneja la remoción de un dispositivo."""
        try:
            time.sleep(0.3)
            unidades = self._enumerar()
            letras = {u.letra for u in unidades}
            _, removidas = self._sincronizar(letras) if self._sincronizar else (set(), set())

            for letra in removidas:
                logger.info(f"Evento: unidad extraíble removida {letra}")
                if self._callback_remocion:
                    try:
                        self._callback_remocion(letra)
                    except Exception as e:
                        logger.error(f"Error en callback de remoción USB: {e}")
        except Exception as e:
            logger.error(f"Error manejando remoción de dispositivo: {e}")


_window_proc = _WindowProc()


def nombre_clase_ventana() -> str:
    """Genera un nombre único para la clase de ventana."""
    pid = ctypes.windll.kernel32.GetCurrentProcessId()
    return f"AntivirusEACoreServer_{pid:X}"


def registrar_y_crear_ventana(sincronizar) -> Optional[int]:
    """Registra la clase de ventana y crea la ventana oculta para WM_DEVICECHANGE."""
    try:
        h_instance = win32api.GetModuleHandle(None)
        clase_nombre = nombre_clase_ventana()

        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = _window_proc.WndProc
        wc.lpszClassName = clase_nombre
        wc.hInstance = h_instance
        wc.style = win32con.CS_HREDRAW | win32con.CS_VREDRAW

        try:
            win32gui.RegisterClass(wc)
        except win32gui.error as e:
            if e.winerror != 1410:
                logger.warning(f"No se pudo registrar clase de ventana: {e}")
                return None

        hwnd = win32gui.CreateWindow(
            clase_nombre, "AntivirusEACoreServer_USBMonitor",
            0, 0, 0, 0, 0, 0, 0, h_instance, None
        )

        if not hwnd:
            logger.error("No se pudo crear ventana oculta para monitoreo USB")
            return None

        _window_proc.configurar_callbacks(None, None, sincronizar)
        registrar_notificacion_dispositivo(hwnd)
        return hwnd

    except Exception as e:
        logger.warning(f"Error al registrar ventana para monitoreo USB: {e}")
        return None


def registrar_notificacion_dispositivo(hwnd) -> None:
    """Registra la ventana para recibir notificaciones de cambio de dispositivo."""
    try:
        class _DEV_BROADCAST_HDR(ctypes.Structure):
            _fields_ = [
                ("dbch_size", ctypes.c_uint32),
                ("dbch_devicetype", ctypes.c_uint32),
                ("dbch_reserved", ctypes.c_uint32),
            ]

        dbh = _DEV_BROADCAST_HDR()
        dbh.dbch_size = ctypes.sizeof(_DEV_BROADCAST_HDR)
        dbh.dbch_devicetype = DBT_DEVTYP_VOLUME
        dbh.dbch_reserved = 0

        result = ctypes.windll.user32.RegisterDeviceNotificationW(
            int(hwnd), ctypes.byref(dbh), DEVICE_NOTIFY_WINDOW_HANDLE
        )
        if not result:
            logger.warning("RegisterDeviceNotification retornó nulo")
        else:
            logger.debug("Notificación de dispositivo registrada")
    except Exception as e:
        logger.warning(f"No se pudo registrar notificación de dispositivo: {e}")


def configurar_callbacks_ventana(llegada, remocion, sincronizar) -> None:
    """Expone la configuración de callbacks del procedimiento de ventana."""
    _window_proc.configurar_callbacks(llegada, remocion, sincronizar)


def bucle_mensajes() -> None:
    """Bombea los mensajes de la ventana oculta hasta recibir WM_QUIT."""
    try:
        win32gui.PumpMessages()
    except Exception as e:
        logger.error(f"Error en bucle de mensajes: {e}")


def solicitar_salida_bucle(hwnd: Optional[int]) -> None:
    """Pide a la ventana oculta que termine su bucle de mensajes."""
    if not hwnd:
        return
    try:
        win32gui.PostMessage(hwnd, win32con.WM_QUIT, 0, 0)
    except Exception:
        pass


def destruir_ventana(hwnd: Optional[int]) -> None:
    """Libera la ventana oculta creada para WM_DEVICECHANGE."""
    if not hwnd:
        return
    try:
        win32gui.DestroyWindow(hwnd)
    except Exception:
        pass
