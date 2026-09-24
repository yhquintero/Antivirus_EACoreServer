"""
Módulo de monitoreo de inserción de unidades USB/extraíbles.
Detecta eventos de hardware en tiempo real usando WM_DEVICECHANGE.
Incluye polling con verificación del bus físico USB para máxima compatibilidad
(las memorias USB modernas o discos externos pueden aparecer como DRIVE_FIXED).
Guarda estado de unidades reparadas entre sesiones.
"""

import json
import re
import threading
import time
import ctypes
import win32api
import win32con
import win32gui
import win32file
from typing import List, Callable, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from logger import obtener_logger

logger = obtener_logger()

# Constantes de Windows
WM_DEVICECHANGE = 0x0219
DBT_DEVICEARRIVAL = 0x8000
DBT_DEVICEREMOVECOMPLETE = 0x8004
DBT_DEVTYP_VOLUME = 0x00000002
DEVICE_NOTIFY_WINDOW_HANDLE = 0x00000000

# Tipos de unidad Windows
DRIVE_UNKNOWN = 0
DRIVE_NO_ROOT_DIR = 1
DRIVE_REMOVABLE = 2
DRIVE_FIXED = 3
DRIVE_REMOTE = 4
DRIVE_CDROM = 5
DRIVE_RAMDISK = 6

# IOCTLs de Windows
IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS = 0x00560000
IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400

# StorageBusType: BusTypeUsb = 0x0B (11)
BUS_TYPE_USB = 0x0B


class TipoUnidad(Enum):
    """Tipos de unidad de Windows"""
    DESCONOCIDO = DRIVE_UNKNOWN
    NO_EXISTE = DRIVE_NO_ROOT_DIR
    EXTRAIBLE = DRIVE_REMOVABLE
    FIJA = DRIVE_FIXED
    RED = DRIVE_REMOTE
    CD_ROM = DRIVE_CDROM
    RAM_DISK = DRIVE_RAMDISK


# Estructuras ctypes para consultar el bus físico de un volumen
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


@dataclass
class UnidadExtraible:
    """Información de una unidad extraíble detectada"""
    letra: str
    ruta_raiz: str
    etiqueta: str = ""
    sistema_archivos: str = ""
    tamano_total: int = 0
    espacio_libre: int = 0
    numero_serie: str = ""
    tipo_drive: int = DRIVE_REMOVABLE

    def __hash__(self):
        return hash(self.letra)

    def __eq__(self, other):
        if isinstance(other, UnidadExtraible):
            return self.letra == other.letra
        return False


# ---------------------------------------------------------------------------
# Estado persistente de unidades reparadas
# ---------------------------------------------------------------------------
_ESTADO_ARCHIVO = Path.home() / "Antivirus_EACoreServer_Logs" / "unidades_reparadas.json"
_unidades_reparadas: List[str] = []


def cargar_unidades_reparadas() -> List[str]:
    """Carga la lista de unidades ya reparadas desde disco."""
    global _unidades_reparadas
    try:
        if _ESTADO_ARCHIVO.exists():
            with open(_ESTADO_ARCHIVO, "r", encoding="utf-8") as f:
                _unidades_reparadas = json.load(f)
            logger.info(f"Unidades reparadas cargadas desde disco: {_unidades_reparadas}")
    except Exception as e:
        logger.warning(f"Error cargando estado de unidades reparadas: {e}")
    return _unidades_reparadas


def guardar_unidades_reparadas() -> None:
    """Guarda la lista de unidades reparadas en disco."""
    try:
        _ESTADO_ARCHIVO.parent.mkdir(parents=True, exist_ok=True)
        with open(_ESTADO_ARCHIVO, "w", encoding="utf-8") as f:
            json.dump(_unidades_reparadas, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Error guardando estado de unidades reparadas: {e}")


def marcar_unidad_reparada(letra: str) -> None:
    """Marca una unidad como reparada y la guarda en disco."""
    global _unidades_reparadas
    letra_normalizada = letra.rstrip("\\").rstrip(":") + ":"
    if letra_normalizada not in _unidades_reparadas:
        _unidades_reparadas.append(letra_normalizada)
        guardar_unidades_reparadas()
        logger.info(f"Unidad {letra_normalizada} marcada como reparada (guardada)")


def es_unidad_reparada(letra: str) -> bool:
    """Verifica si una unidad ya fue reparada anteriormente."""
    letra_normalizada = letra.rstrip("\\").rstrip(":") + ":"
    return letra_normalizada in _unidades_reparadas


def obtener_unidades_reparadas() -> List[str]:
    """Retorna la lista de unidades reparadas (persistida)."""
    return list(_unidades_reparadas)


# Inicializar estado persistente
cargar_unidades_reparadas()


# ---------------------------------------------------------------------------
# Estado global del monitor (hilos compartidos)
# ---------------------------------------------------------------------------
_monitor_activo = False
_monitor_lock = threading.Lock()
_unidades_conocidas: Set[str] = set()


def _sincronizar_unidades(letras_actuales: Set[str]) -> Tuple[Set[str], Set[str]]:
    """
    Compara las letras actuales con las conocidas y actualiza el estado global.

    Returns:
        Tupla (nuevas, removidas).
    """
    global _unidades_conocidas
    with _monitor_lock:
        nuevas = letras_actuales - _unidades_conocidas
        removidas = _unidades_conocidas - letras_actuales
        _unidades_conocidas = letras_actuales
    return nuevas, removidas


# ---------------------------------------------------------------------------
# Detección de unidades
# ---------------------------------------------------------------------------
def _obtener_info_unidad_interna(letra: str) -> Optional[UnidadExtraible]:
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

    tipo = _obtener_tipo_unidad(letra)
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


def _obtener_numero_disco_fisico(letra: str) -> Optional[int]:
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


def _es_usb_por_bus_fisico(letra: str) -> bool:
    """
    Determina si el disco físico de un volumen es USB consultando STORAGE_DEVICE_DESCRIPTOR.
    Detecta correctamente memorias USB y discos externos que Windows
    clasifica como DRIVE_FIXED.
    """
    disco = _obtener_numero_disco_fisico(letra)
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


def _es_usb_por_wmi(letra: str) -> bool:
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


def _enumerar_letras_existentes() -> List[str]:
    """Obtiene letras de unidades existentes con GetLogicalDrives (ctypes)."""
    mascara = GetLogicalDrives()
    letras = []
    for i in range(26):
        if mascara & (1 << i):
            letras.append(chr(ord("A") + i))
    return letras


def _obtener_tipo_unidad(letra: str) -> int:
    """Obtiene el tipo de una unidad (GetDriveTypeW vía ctypes, con respaldo pywin32)."""
    try:
        return int(_GetDriveTypeW(f"{letra}:\\"))
    except Exception:
        try:
            return int(win32file.GetDriveType(f"{letra}:\\"))
        except Exception:
            return DRIVE_UNKNOWN


def _obtener_unidades_extraibles_interno() -> List[UnidadExtraible]:
    """
    Obtiene todas las unidades disponibles con letra (A-Z): memorias USB y
    tarjetas (extraíbles), discos fijos (SSD/HDD internos o externos USB) y
    unidades de red. Se omiten solo CD-ROM sin medio y RAM disks.
    """
    unidades = []
    unidades_existentes = []

    for letra in _enumerar_letras_existentes():
        tipo = _obtener_tipo_unidad(letra)

        # Registrar todas las unidades existentes para diagnóstico
        unidades_existentes.append((letra, tipo))

        if tipo in (DRIVE_UNKNOWN, DRIVE_NO_ROOT_DIR, DRIVE_CDROM, DRIVE_RAMDISK):
            logger.debug(f"Unidad {letra}: tipo={tipo} -> se omite (no escaneable)")
            continue

        info = _obtener_info_unidad_interna(letra)
        if info is None:
            # Red de seguridad: mostrar la unidad aunque los metadatos fallen
            info = UnidadExtraible(
                letra=f"{letra}:", ruta_raiz=f"{letra}:\\",
                etiqueta="(sin metadatos)", tipo_drive=tipo
            )
            logger.debug(f"Unidad {letra}: sin metadatos, agregada con datos mínimos")

        unidades.append(info)
        logger.debug(
            f"Unidad detectada: {info.letra} tipo={tipo} "
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
        self._callback_llegada = None
        self._callback_remocion = None

    def configurar_callbacks(self, llegada, remocion):
        """Configura los callbacks de llegada y remoción de dispositivos."""
        self._callback_llegada = llegada
        self._callback_remocion = remocion

    def WndProc(self, hwnd, msg, wparam, lparam):
        """Procedimiento de ventana que recibe mensajes WM_DEVICECHANGE."""
        if msg == WM_DEVICECHANGE:
            if wparam == DBT_DEVICEARRIVAL:
                threading.Thread(target=self._manejar_llegada, daemon=True).start()
            elif wparam == DBT_DEVICEREMOVECOMPLETE:
                threading.Thread(target=self._manejar_remocion, daemon=True).start()
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _manejar_llegada(self):
        """Maneja la llegada de un nuevo dispositivo."""
        try:
            time.sleep(0.4)
            unidades = _obtener_unidades_extraibles_interno()
            letras = {u.letra for u in unidades}
            nuevas, _ = _sincronizar_unidades(letras)

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

    def _manejar_remocion(self):
        """Maneja la remoción de un dispositivo."""
        try:
            time.sleep(0.3)
            unidades = _obtener_unidades_extraibles_interno()
            letras = {u.letra for u in unidades}
            _, removidas = _sincronizar_unidades(letras)

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


def _nombre_clase_ventana():
    """Genera un nombre único para la clase de ventana."""
    pid = ctypes.windll.kernel32.GetCurrentProcessId()
    return f"AntivirusEACoreServer_{pid:X}"


def _registrar_y_crear_ventana():
    """Registra la clase de ventana y crea la ventana oculta para WM_DEVICECHANGE."""
    try:
        h_instance = win32api.GetModuleHandle(None)
        clase_nombre = _nombre_clase_ventana()

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

        _registrar_notificacion_dispositivo(hwnd)
        return hwnd

    except Exception as e:
        logger.warning(f"Error al registrar ventana para monitoreo USB: {e}")
        return None


def _registrar_notificacion_dispositivo(hwnd):
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


# ---------------------------------------------------------------------------
# Monitor principal
# ---------------------------------------------------------------------------
class MonitorUSB:
    """
    Monitor de unidades extraíbles usando WM_DEVICECHANGE + polling.
    El polling es la detección principal y funciona siempre, incluso si
    la ventana oculta de mensajes no puede crearse.
    """

    def __init__(self) -> None:
        self._ventana_hwnd: Optional[int] = None
        self._clase_ventana: str = ""
        self._ejecutando = False
        self._hilo_monitor: Optional[threading.Thread] = None
        self._hilo_polling: Optional[threading.Thread] = None
        self._polling_activo = False
        self._callback_llegada: Optional[Callable] = None
        self._callback_remocion: Optional[Callable] = None

    def iniciar(self,
                callback_llegada: Callable[[UnidadExtraible], None],
                callback_remocion: Optional[Callable[[str], None]] = None) -> bool:
        """
        Inicia el monitor de USB con ventana de mensajes + polling.

        Args:
            callback_llegada: Función llamada cuando se detecta una unidad nueva.
            callback_remocion: Función opcional llamada cuando se quita una unidad.

        Returns:
            True si el monitor se inició correctamente.
        """
        global _monitor_activo

        with _monitor_lock:
            if _monitor_activo:
                logger.warning("Monitor USB ya está ejecutándose")
                return False

        self._callback_llegada = callback_llegada
        self._callback_remocion = callback_remocion or (lambda letra: None)

        # Configurar callbacks en el procedimiento de ventana
        _window_proc.configurar_callbacks(callback_llegada, callback_remocion)

        # Crear ventana para WM_DEVICECHANGE (opcional; si falla, polling cubre todo)
        hwnd = _registrar_y_crear_ventana()
        if hwnd:
            self._ventana_hwnd = hwnd
            self._clase_ventana = _nombre_clase_ventana()
            logger.info("Ventana WM_DEVICECHANGE creada correctamente")
        else:
            logger.warning("No se pudo crear ventana WM_DEVICECHANGE - se usará solo polling")

        # Escanear unidades existentes al iniciar
        self._escanear_unidades_iniciales()

        # Iniciar hilo de mensajes (si hay ventana)
        if self._ventana_hwnd:
            try:
                self._hilo_monitor = threading.Thread(target=self._bucle_mensajes, daemon=True)
                self._hilo_monitor.start()
            except Exception as e:
                logger.warning(f"No se pudo iniciar hilo de mensajes: {e}")

        # Siempre iniciar polling como detección principal
        self._polling_activo = True
        self._hilo_polling = threading.Thread(target=self._bucle_polling, daemon=True)
        self._hilo_polling.start()
        logger.info("Polling de USB activado (detección principal)")

        _monitor_activo = True
        self._ejecutando = True
        logger.info("Monitor USB iniciado correctamente")
        return True

    def detener(self) -> None:
        """Detiene el monitor de USB."""
        global _monitor_activo
        self._ejecutando = False
        self._polling_activo = False

        if self._hilo_monitor and self._hilo_monitor.is_alive():
            try:
                win32gui.PostMessage(self._ventana_hwnd, win32con.WM_QUIT, 0, 0)
                self._hilo_monitor.join(timeout=2)
            except Exception:
                pass

        if self._hilo_polling and self._hilo_polling.is_alive():
            self._hilo_polling.join(timeout=2)

        if self._ventana_hwnd:
            try:
                win32gui.DestroyWindow(self._ventana_hwnd)
            except Exception:
                pass
            self._ventana_hwnd = None

        _monitor_activo = False
        logger.info("Monitor USB detenido")

    def _bucle_mensajes(self) -> None:
        try:
            win32gui.PumpMessages()
        except Exception as e:
            logger.error(f"Error en bucle de mensajes: {e}")

    def _bucle_polling(self) -> None:
        """Bucle de polling principal - detecta unidades cada segundo."""
        while self._polling_activo and self._ejecutando:
            try:
                time.sleep(1.0)
                if not self._ejecutando:
                    break

                unidades = _obtener_unidades_extraibles_interno()
                letras = {u.letra for u in unidades}
                nuevas, removidas = _sincronizar_unidades(letras)

                for unidad in unidades:
                    if unidad.letra in nuevas:
                        logger.info(f"Polling: unidad nueva {unidad.letra} ({unidad.etiqueta}) tipo={unidad.tipo_drive}")
                        try:
                            self._callback_llegada(unidad)
                        except Exception as e:
                            logger.error(f"Error en callback de llegada: {e}")

                for letra in removidas:
                    logger.info(f"Polling: unidad removida {letra}")
                    try:
                        self._callback_remocion(letra)
                    except Exception as e:
                        logger.error(f"Error en callback de remoción: {e}")

            except Exception as e:
                logger.debug(f"Error en polling: {e}")

    def _escanear_unidades_iniciales(self) -> None:
        """Escanea unidades extraíbles presentes al iniciar."""
        unidades = _obtener_unidades_extraibles_interno()
        letras = {u.letra for u in unidades}
        _sincronizar_unidades(letras)
        logger.info(f"Unidades disponibles iniciales ({len(unidades)}): {[u.letra for u in unidades]}")

    def obtener_unidades_actuales(self) -> List[UnidadExtraible]:
        """Retorna lista de unidades USB/extraíbles actualmente conectadas."""
        return _obtener_unidades_extraibles_interno()


_monitor_instancia: Optional[MonitorUSB] = None


def obtener_monitor_usb() -> MonitorUSB:
    """Retorna la instancia singleton del monitor USB."""
    global _monitor_instancia
    if _monitor_instancia is None:
        _monitor_instancia = MonitorUSB()
    return _monitor_instancia