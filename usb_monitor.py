"""
Módulo multiplataforma de monitoreo de inserción de unidades USB/extraíbles.

Esta es la **fachada portable** del proyecto. Expone siempre la misma API
(:class:`UnidadExtraible`, :class:`MonitorUSB`, estado de unidades reparadas) y
delega la enumeración en un backend según el sistema operativo:

* **Windows** → :mod:`usb_monitor_windows` (``pywin32`` + ``ctypes.windll`` +
  ventana oculta ``WM_DEVICECHANGE``). El backend se importa de forma diferida
  para que ``pywin32`` no sea necesario en macOS ni Linux.
* **macOS** → ``diskutil info -plist`` sobre ``/Volumes``.
* **Linux** → ``/proc/mounts`` + ``/sys/block``.

En los tres sistemas el *polling* es la detección principal y funciona siempre;
la ventana de mensajes de Windows es solo una aceleración adicional.

Las unidades se enumeran para diagnóstico, pero únicamente los medios
extraíbles o los USB físicos se marcan como reparables.
"""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

from compat import (
    FAMILIA_AIX,
    FAMILIA_BSD,
    FAMILIA_DESCONOCIDA,
    FAMILIA_LINUX,
    FAMILIA_MACOS,
    FAMILIA_SOLARIS,
    obtener_familia_posix,
)
from logger import obtener_logger

logger = obtener_logger()

# ---------------------------------------------------------------------------
# Detección de plataforma
# ---------------------------------------------------------------------------
_SISTEMA = platform.system().lower()
ES_WINDOWS = os.name == "nt" or _SISTEMA.startswith("win")
ES_MACOS = _SISTEMA == "darwin"
ES_LINUX = _SISTEMA == "linux"
NOMBRE_PLATAFORMA = "Windows" if ES_WINDOWS else ("macOS" if ES_MACOS else ("Linux" if ES_LINUX else platform.system()))

# ---------------------------------------------------------------------------
# Tipos de unidad. Los valores numéricos coinciden con los de la API de Windows
# (GetDriveTypeW) para que la GUI y el motor usen una sola escala en los tres
# sistemas operativos.
# ---------------------------------------------------------------------------
DRIVE_UNKNOWN = 0
DRIVE_NO_ROOT_DIR = 1
DRIVE_REMOVABLE = 2
DRIVE_FIXED = 3
DRIVE_REMOTE = 4
DRIVE_CDROM = 5
DRIVE_RAMDISK = 6


class TipoUnidad(Enum):
    """Tipos de unidad (escala común basada en GetDriveTypeW de Windows)."""
    DESCONOCIDO = DRIVE_UNKNOWN
    NO_EXISTE = DRIVE_NO_ROOT_DIR
    EXTRAIBLE = DRIVE_REMOVABLE
    FIJA = DRIVE_FIXED
    RED = DRIVE_REMOTE
    CD_ROM = DRIVE_CDROM
    RAM_DISK = DRIVE_RAMDISK


@dataclass
class UnidadExtraible:
    """Información de una unidad extraíble detectada.

    En Windows ``letra`` es una letra de unidad (``"E:"``). En macOS y Linux no
    existen letras, por lo que ``letra`` contiene el punto de montaje
    (``"/Volumes/USB"`` o ``"/media/usuario/USB"``) y actúa como identificador.
    """
    letra: str
    ruta_raiz: str
    etiqueta: str = ""
    sistema_archivos: str = ""
    tamano_total: int = 0
    espacio_libre: int = 0
    numero_serie: str = ""
    tipo_drive: int = DRIVE_REMOVABLE
    # Los discos USB externos pueden aparecer como DRIVE_FIXED. Este campo se
    # calcula a partir del bus físico para que la GUI no trate el disco interno
    # o una unidad de red como destino de reparación automática.
    es_usb_fisico: bool = False

    @property
    def es_reparable_con_seguridad(self) -> bool:
        """Solo permite reparación guiada en medios extraíbles o USB físicos."""
        return self.tipo_drive == DRIVE_REMOVABLE or self.es_usb_fisico

    def __hash__(self):
        return hash(self.letra)

    def __eq__(self, other):
        if isinstance(other, UnidadExtraible):
            return self.letra == other.letra
        return False


# ---------------------------------------------------------------------------
# Identificadores de unidad multiplataforma
# ---------------------------------------------------------------------------
_PATRON_LETRA_WINDOWS = re.compile(r"[A-Za-z]:?\\?")


def normalizar_identificador_unidad(letra: str) -> str:
    """Normaliza un identificador de unidad según la plataforma.

    En Windows devuelve la forma canónica ``"E:"``. En macOS y Linux devuelve el
    punto de montaje sin barra final (salvo la raíz ``"/"``). Aplicar el recorte
    de Windows a una ruta POSIX la corrompería, de ahí la distinción.
    """
    texto = (letra or "").strip()
    if not texto:
        return ""
    if ES_WINDOWS and _PATRON_LETRA_WINDOWS.fullmatch(texto):
        return texto.rstrip("\\").rstrip(":").upper() + ":"
    if ES_WINDOWS:
        # Ruta completa de Windows: conservar tal cual, sin añadir dos puntos.
        return texto.rstrip("\\") or texto
    ruta = texto.replace("\\", "/")
    if len(ruta) > 1:
        ruta = ruta.rstrip("/")
    return ruta or "/"


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
    letra_normalizada = normalizar_identificador_unidad(letra)
    if letra_normalizada and letra_normalizada not in _unidades_reparadas:
        _unidades_reparadas.append(letra_normalizada)
        guardar_unidades_reparadas()
        logger.info(f"Unidad {letra_normalizada} marcada como reparada (guardada)")


def es_unidad_reparada(letra: str) -> bool:
    """Verifica si una unidad ya fue reparada anteriormente."""
    return normalizar_identificador_unidad(letra) in _unidades_reparadas


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
# Backend de Windows (importación diferida: pywin32 solo existe en Windows)
# ---------------------------------------------------------------------------
_backend_windows = None


def _windows():
    """Carga :mod:`usb_monitor_windows` la primera vez que se necesita."""
    global _backend_windows
    if _backend_windows is None:
        import usb_monitor_windows as modulo
        _backend_windows = modulo
    return _backend_windows


# ---------------------------------------------------------------------------
# Backend de macOS
# ---------------------------------------------------------------------------
_VOLUMENES_MACOS = Path("/Volumes")
_TIMEOUT_DISCO = 8


def _espacio_en_macos(montaje: Path) -> Tuple[int, int]:
    """Obtiene (total, libre) en bytes usando ``statvfs``."""
    try:
        st = os.statvfs(str(montaje))
        total = st.f_blocks * st.f_frsize
        libre = st.f_bavail * st.f_frsize
        return int(total), int(libre)
    except OSError:
        return 0, 0


def _info_disco_macos(montaje: Path) -> dict:
    """Consulta ``diskutil info -plist`` y devuelve el diccionario de metadatos."""
    try:
        import plistlib

        salida = subprocess.run(
            ["diskutil", "info", "-plist", str(montaje)],
            capture_output=True, timeout=_TIMEOUT_DISCO, check=False,
        )
        if salida.returncode != 0 or not salida.stdout:
            return {}
        return plistlib.loads(salida.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        logger.debug(f"diskutil no disponible para {montaje}: {e}")
        return {}


def _obtener_unidades_macos() -> List[UnidadExtraible]:
    """Enumera los volúmenes montados en macOS y clasifica los USB."""
    unidades: List[UnidadExtraible] = []
    if not _VOLUMENES_MACOS.is_dir():
        logger.debug("macOS: /Volumes no es accesible")
        return unidades

    for entrada in sorted(_VOLUMENES_MACOS.iterdir()):
        try:
            if entrada.is_symlink() or not entrada.is_dir():
                continue
            info = _info_disco_macos(entrada)
            protocolo = str(info.get("Protocol", "") or "").lower()
            removible = bool(info.get("Removable Media", info.get("Removable", False)))
            interno = bool(info.get("Internal", False))
            tipo = DRIVE_REMOVABLE if removible else (DRIVE_FIXED if interno else DRIVE_FIXED)
            es_usb = protocolo in ("usb", "thunderbolt", "firewire") or removible

            total, libre = _espacio_en_macos(entrada)
            total = int(info.get("Total Size", info.get("Size (Total)", total)) or total)
            libre = int(info.get("Free Space", info.get("Volume Free Space", libre)) or libre)

            unidades.append(UnidadExtraible(
                letra=str(entrada), ruta_raiz=str(entrada),
                etiqueta=str(info.get("Volume Name", entrada.name) or entrada.name),
                sistema_archivos=str(info.get("File System Personality Type",
                                              info.get("File System Type", "")) or ""),
                tamano_total=total, espacio_libre=libre,
                numero_serie=str(info.get("Volume UUID", "") or ""),
                tipo_drive=tipo, es_usb_fisico=es_usb,
            ))
        except OSError as e:
            logger.debug(f"macOS: no se pudo leer el volumen {entrada}: {e}")

    logger.debug(f"macOS: {len(unidades)} volúmenes enumerados")
    return unidades


# ---------------------------------------------------------------------------
# Backend de Linux
# ---------------------------------------------------------------------------
_PROC_MOUNTS = Path("/proc/mounts")
_SYS_BLOCK = Path("/sys/block")
_BY_LABEL = Path("/dev/disk/by-label")
_BY_ID = Path("/dev/disk/by-id")

# Sistemas de ficheros virtuales o de red: nunca son un USB reparable.
_FS_VIRTUALES = {
    "proc", "sysfs", "devtmpfs", "devpts", "tmpfs", "cgroup", "cgroup2", "overlay",
    "squashfs", "autofs", "mqueue", "hugetlbfs", "debugfs", "tracefs", "fusectl",
    "configfs", "binfmt_misc", "rpc_pipefs", "nsfs", "pstore", "securityfs",
    "bpf", "ramfs", "efivarfs", "selinuxfs", "fuse.gvfsd-fuse", "fuse.portal",
    "none", "nodev",
}
_FS_RED = {"nfs", "nfs4", "cifs", "smbfs", "smb3", "fuse.sshfs", "afs", "ceph", "glusterfs", "ncpfs"}
_PREFIJOS_DISCO_REAL = ("/dev/sd", "/dev/nvme", "/dev/mmcblk", "/dev/hd", "/dev/vd", "/dev/xvd")


def _leer_archivo_sysfs(ruta: Path) -> str:
    """Lee un archivo de sysfs sin propagar errores."""
    try:
        return ruta.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def _nombre_disco_base(dispositivo: str) -> str:
    """Extrae el disco base de una partición: ``/dev/sdb1`` -> ``sdb``."""
    nombre = Path(dispositivo).name
    m = re.match(r"(nvme\d+n\d+|mmcblk\d+)(p\d+)?$", nombre)
    if m:
        return m.group(1)
    m = re.match(r"([a-z]+?)(\d+)?$", nombre)
    return m.group(1) if m else nombre


def _es_usb_en_linux(disco: str) -> bool:
    """Determina si un disco base está conectado por bus USB.

    Se apoya en ``/sys/block/<disco>/removable`` y en la ruta real del
    dispositivo, que contiene ``usb`` cuando el controlador es USB.
    """
    if not disco:
        return False
    base = _SYS_BLOCK / disco
    if _leer_archivo_sysfs(base / "removable") == "1":
        return True
    try:
        ruta_real = os.path.realpath(str(base)).lower()
    except OSError:
        return False
    if "/usb" in ruta_real or ruta_real.endswith("usb"):
        return True
    # Algunos controladores exponen el bus en device/subsystem.
    for candidato in ("device/subsystem", "device"):
        enlace = base / candidato
        try:
            if enlace.exists() and "usb" in os.path.realpath(str(enlace)).lower():
                return True
        except OSError:
            continue
    return False


def _etiqueta_en_linux(dispositivo: str, montaje: str) -> str:
    """Obtiene la etiqueta del volumen desde ``/dev/disk/by-label``."""
    if _BY_LABEL.is_dir():
        try:
            for enlace in _BY_LABEL.iterdir():
                try:
                    if os.path.realpath(str(enlace)) == os.path.realpath(dispositivo):
                        return enlace.name
                except OSError:
                    continue
        except OSError:
            pass
    return Path(montaje).name or montaje


def _serie_en_linux(dispositivo: str) -> str:
    """Obtiene un identificador estable desde ``/dev/disk/by-id``."""
    if _BY_ID.is_dir():
        try:
            objetivo = os.path.realpath(dispositivo)
            for enlace in _BY_ID.iterdir():
                try:
                    if os.path.realpath(str(enlace)) == objetivo:
                        return enlace.name
                except OSError:
                    continue
        except OSError:
            pass
    disco = _nombre_disco_base(dispositivo)
    return _leer_archivo_sysfs(_SYS_BLOCK / disco / "device" / "serial")


def _obtener_unidades_linux() -> List[UnidadExtraible]:
    """Enumera los montajes reales de Linux y clasifica los USB."""
    unidades: List[UnidadExtraible] = []
    if not _PROC_MOUNTS.is_file():
        logger.debug("Linux: /proc/mounts no disponible")
        return unidades

    vistos: Set[str] = set()
    try:
        lineas = _PROC_MOUNTS.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as e:
        logger.debug(f"Linux: no se pudo leer /proc/mounts: {e}")
        return unidades

    for linea in lineas:
        partes = linea.split()
        if len(partes) < 3:
            continue
        dispositivo, montaje, fs = partes[0], partes[1], partes[2]
        # /proc/mounts escapa espacios y caracteres especiales con octales.
        montaje = montaje.encode("utf-8", "replace").decode("unicode_escape", "replace")
        dispositivo = dispositivo.encode("utf-8", "replace").decode("unicode_escape", "replace")

        if fs in _FS_VIRTUALES:
            continue
        if montaje in vistos:
            continue

        if fs in _FS_RED:
            vistos.add(montaje)
            unidades.append(UnidadExtraible(
                letra=montaje, ruta_raiz=montaje, etiqueta=Path(montaje).name or montaje,
                sistema_archivos=fs, tipo_drive=DRIVE_REMOTE, es_usb_fisico=False,
            ))
            continue

        if not dispositivo.startswith(_PREFIJOS_DISCO_REAL):
            # loop, zram, mapper y otros dispositivos no son medios extraíbles.
            continue

        vistos.add(montaje)
        disco = _nombre_disco_base(dispositivo)
        removible = _leer_archivo_sysfs(_SYS_BLOCK / disco / "removable") == "1"
        es_usb = _es_usb_en_linux(disco)
        total, libre = _espacio_en_macos(Path(montaje))  # statvfs es idéntico en POSIX

        unidades.append(UnidadExtraible(
            letra=montaje, ruta_raiz=montaje,
            etiqueta=_etiqueta_en_linux(dispositivo, montaje),
            sistema_archivos=fs,
            tamano_total=total, espacio_libre=libre,
            numero_serie=_serie_en_linux(dispositivo),
            tipo_drive=DRIVE_REMOVABLE if removible else DRIVE_FIXED,
            es_usb_fisico=es_usb,
        ))

    logger.debug(f"Linux: {len(unidades)} montajes enumerados")
    return unidades


# ---------------------------------------------------------------------------
# Backend POSIX genérico (BSD, Solaris/illumos, AIX y Unix no reconocidos)
# ---------------------------------------------------------------------------
# Estos sistemas no tienen ni /proc/mounts ni /sys/block, así que se enumeran los
# montajes con `df -kP`, cuyo formato POSIX está disponible en todos ellos.
_COMANDO_DF = ("df", "-kP")
_TIMEOUT_COMANDO = 8

# Patrones de dispositivo que en cada familia BSD/Unix suelen ser medios
# extraíbles conectados por USB. Son heurísticas: ante la duda la unidad se
# marca como no reparable y solo se diagnostica.
_DISPOSITIVOS_EXTRAIBLES_BSD = {
    "freebsd": ("da",),          # da* = acceso directo SCSI/USB; ada* = SATA interno
    "dragonfly": ("da",),
    "midnightbsd": ("da",),
    "openbsd": ("sd",),          # sd* = SCSI/USB; wd* = ATA interno
    "netbsd": ("sd", "ld",),
}
_DISPOSITIVOS_OPTICOS = ("cd", "acd", "mcd", "rscsi")

# Puntos de montaje típicos de medios extraíbles en sistemas Unix.
_RUTAS_EXTRAIBLES = ("/media/", "/mnt/", "/run/media/", "/var/run/media/", "/Volumes/")

# Sistemas de ficheros propios de memorias USB y medios ópticos.
_FS_MEDIO_EXTRAIBLE = {
    "msdosfs", "vfat", "fat", "fat32", "exfat", "ntfs", "fuseblk",
    "iso9660", "udf", "cd9660", "hfs", "hfsplus", "apfs",
}

# Montajes del sistema que nunca son una unidad del usuario.
_MONTAJES_SISTEMA = {
    "/", "/boot", "/usr", "/var", "/etc", "/dev", "/proc", "/sys", "/tmp", "/home",
    "/root", "/opt", "/sbin", "/bin", "/lib", "/libexec", "/usr/local", "/private",
    "/dev/fd", "/dev/stdin", "/dev/stdout", "/dev/stderr", "/proc/fs", "/system",
    "/Library", "/Applications", "/cores", "/var/run", "/run",
}

# Dispositivos que no representan un medio físico del usuario.
_DISPOSITIVOS_IGNORADOS = (
    "tmpfs", "devfs", "devtmpfs", "proc", "sysfs", "none", "swap", "map ",
    "/dev/loop", "/dev/md", "/dev/dm-", "/dev/zvol", "fdescfs", "linprocfs",
    "linsysfs", "cgroup", "mqueue", "shmfs", "objfs", "autofs", "-hosts",
)

_PATRON_MOUNT_BSD = re.compile(r"^(?P<dev>\S+)\s+on\s+(?P<mnt>.+?)\s+\((?P<fs>[^,)]+)")
_PATRON_MOUNT_LINUX = re.compile(r"^(?P<dev>\S+)\s+on\s+(?P<mnt>.+?)\s+type\s+(?P<fs>\S+)")


def _salida_comando(comando: tuple) -> str:
    """Ejecuta un comando y devuelve su stdout, o cadena vacía si falla."""
    try:
        salida = subprocess.run(
            comando, capture_output=True, text=True,
            timeout=_TIMEOUT_COMANDO, check=False,
        )
        return salida.stdout if salida.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug(f"Comando {comando[0]} no disponible: {e}")
        return ""


def _parsear_df() -> List[Tuple[str, str, int, int]]:
    """Interpreta ``df -kP`` y devuelve (dispositivo, montaje, total, libre).

    El formato POSIX garantiza una línea por sistema de ficheros con seis
    columnas; el punto de montaje es la última y puede contener espacios, por eso
    se divide con un máximo de cinco separaciones.
    """
    texto = _salida_comando(_COMANDO_DF)
    if not texto:
        return []
    resultados = []
    for linea in texto.splitlines()[1:]:  # la primera línea es la cabecera
        campos = linea.split(None, 5)
        if len(campos) < 6:
            continue
        dispositivo, bloques, _usado, disponible, _capacidad, montaje = campos
        try:
            total = int(bloques) * 1024
            libre = int(disponible) * 1024
        except ValueError:
            continue
        resultados.append((dispositivo, montaje, total, libre))
    return resultados


def _tipos_de_montaje() -> Dict[str, str]:
    """Mapa punto de montaje -> sistema de ficheros, a partir de ``mount``.

    Cubre las tres sintaxis habituales: Linux (``... type vfat (...)``),
    BSD/AIX (``... (msdosfs, local, ...)``) y cualquier otra, donde el tipo
    queda sin determinar.
    """
    texto = _salida_comando(("mount",))
    tipos: Dict[str, str] = {}
    if not texto:
        return tipos
    for linea in texto.splitlines():
        coincidencia = _PATRON_MOUNT_LINUX.match(linea) or _PATRON_MOUNT_BSD.match(linea)
        if coincidencia:
            tipos[coincidencia.group("mnt")] = coincidencia.group("fs").strip().lower()
    return tipos


def _nombre_dispositivo_base(dispositivo: str) -> str:
    """Extrae el prefijo alfabético del dispositivo: ``/dev/da0s1`` -> ``da``."""
    nombre = Path(dispositivo).name
    coincidencia = re.match(r"([a-zA-Z]+)", nombre)
    return coincidencia.group(1).lower() if coincidencia else ""


def _clasificar_extraible_posix(dispositivo: str, montaje: str, fs: str) -> Tuple[int, bool]:
    """Devuelve (tipo_drive, es_usb_fisico) de forma conservadora.

    Solo marca una unidad como USB físico cuando el prefijo del dispositivo es
    característico de medios extraíbles en esa familia, o cuando el punto de
    montaje es típico de medios removibles y el sistema de ficheros también lo es.
    """
    sistema = (platform.system() or "").lower()
    prefijo = _nombre_dispositivo_base(dispositivo)

    if prefijo in _DISPOSITIVOS_OPTICOS:
        return DRIVE_CDROM, False

    patrones_extraibles = _DISPOSITIVOS_EXTRAIBLES_BSD.get(sistema, ())
    por_dispositivo = bool(prefijo) and prefijo in patrones_extraibles

    por_montaje = any(montaje.startswith(ruta) for ruta in _RUTAS_EXTRAIBLES)
    por_sistema_archivos = fs in _FS_MEDIO_EXTRAIBLE

    if por_dispositivo:
        return DRIVE_REMOVABLE, True
    if por_montaje and por_sistema_archivos:
        return DRIVE_REMOVABLE, True
    if por_montaje:
        # Ruta típica de medio extraíble pero sistema de ficheros indeterminado:
        # se diagnostica sin habilitar la reparación.
        return DRIVE_FIXED, False
    return DRIVE_FIXED, False


def _obtener_unidades_posix_generico() -> List[UnidadExtraible]:
    """Enumera montajes en BSD, Solaris, AIX y Unix no reconocidos."""
    entradas = _parsear_df()
    if not entradas:
        logger.debug("POSIX genérico: `df -kP` no devolvió montajes")
        return []

    tipos = _tipos_de_montaje()
    unidades: List[UnidadExtraible] = []
    vistos: Set[str] = set()

    for dispositivo, montaje, total, libre in entradas:
        if montaje in vistos:
            continue
        if montaje in _MONTAJES_SISTEMA:
            continue
        if any(dispositivo.startswith(ignorado) for ignorado in _DISPOSITIVOS_IGNORADOS):
            continue
        if dispositivo in _FS_VIRTUALES:
            continue

        fs = tipos.get(montaje, "")
        if fs in _FS_VIRTUALES:
            continue
        if fs in _FS_RED:
            vistos.add(montaje)
            unidades.append(UnidadExtraible(
                letra=montaje, ruta_raiz=montaje,
                etiqueta=Path(montaje).name or montaje,
                sistema_archivos=fs, tipo_drive=DRIVE_REMOTE, es_usb_fisico=False,
            ))
            continue

        vistos.add(montaje)
        tipo, es_usb = _clasificar_extraible_posix(dispositivo, montaje, fs)
        unidades.append(UnidadExtraible(
            letra=montaje, ruta_raiz=montaje,
            etiqueta=_etiqueta_posix(montaje),
            sistema_archivos=fs,
            tamano_total=total, espacio_libre=libre,
            numero_serie=_serie_posix(dispositivo),
            tipo_drive=tipo, es_usb_fisico=es_usb,
        ))

    logger.debug(f"POSIX genérico ({NOMBRE_PLATAFORMA}): {len(unidades)} montajes enumerados")
    return unidades


def _etiqueta_posix(montaje: str) -> str:
    """Etiqueta del volumen; en Unix genérico se usa el nombre del montaje."""
    try:
        ruta = Path(montaje)
        etiqueta = ruta.name
        return etiqueta or montaje
    except Exception:
        return montaje


def _serie_posix(dispositivo: str) -> str:
    """Identificador estable del dispositivo, si el sistema lo expone."""
    return Path(dispositivo).name if dispositivo.startswith("/dev/") else ""


# ---------------------------------------------------------------------------
# Despacho multiplataforma
# ---------------------------------------------------------------------------
def obtener_unidades_extraibles() -> List[UnidadExtraible]:
    """
    Obtiene las unidades disponibles para diagnóstico en el sistema actual.

    La lista puede incluir discos fijos y de red, pero solo los medios
    extraíbles/USB físicos se marcan como reparables para evitar cambios
    accidentales en el sistema.
    """
    try:
        if ES_WINDOWS:
            return _windows().obtener_unidades_extraibles()

        familia = obtener_familia_posix()
        if familia == FAMILIA_MACOS:
            return _obtener_unidades_macos()
        if familia == FAMILIA_LINUX:
            # /proc/mounts es el origen más preciso; si el kernel no lo expone
            # (contenedores restringidos) se degrada al backend genérico.
            unidades = _obtener_unidades_linux()
            return unidades or _obtener_unidades_posix_generico()
        if familia in (FAMILIA_BSD, FAMILIA_SOLARIS, FAMILIA_AIX, FAMILIA_DESCONOCIDA):
            return _obtener_unidades_posix_generico()

        logger.warning(f"Plataforma no soportada para enumeración: {platform.system()}")
        return []
    except Exception as e:
        logger.error(f"Error enumerando unidades en {NOMBRE_PLATAFORMA}: {e}", exc_info=True)
        return []


# Alias interno conservado por compatibilidad con versiones anteriores.
_obtener_unidades_extraibles_interno = obtener_unidades_extraibles


# ---------------------------------------------------------------------------
# Monitor principal
# ---------------------------------------------------------------------------
class MonitorUSB:
    """
    Monitor de unidades extraíbles.

    En Windows combina la ventana oculta ``WM_DEVICECHANGE`` con *polling*; en
    macOS y Linux usa solo *polling*, que es la detección principal y funciona
    siempre en los tres sistemas.
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
        Inicia el monitor de USB.

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

        # Escanear unidades existentes al iniciar
        self._escanear_unidades_iniciales()

        # En Windows, crear la ventana para WM_DEVICECHANGE (opcional; si falla,
        # el polling cubre todo). En macOS/Linux no existe ese mecanismo.
        if ES_WINDOWS:
            backend = _windows()
            backend.configurar_callbacks_ventana(
                self._callback_llegada, self._callback_remocion, _sincronizar_unidades
            )
            hwnd = backend.registrar_y_crear_ventana(_sincronizar_unidades)
            if hwnd:
                self._ventana_hwnd = hwnd
                self._clase_ventana = backend.nombre_clase_ventana()
                logger.info("Ventana WM_DEVICECHANGE creada correctamente")
                try:
                    self._hilo_monitor = threading.Thread(target=self._bucle_mensajes, daemon=True)
                    self._hilo_monitor.start()
                except Exception as e:
                    logger.warning(f"No se pudo iniciar hilo de mensajes: {e}")
            else:
                logger.warning("No se pudo crear ventana WM_DEVICECHANGE - se usará solo polling")
        else:
            logger.info(f"{NOMBRE_PLATAFORMA}: monitoreo por polling (sin WM_DEVICECHANGE)")

        # Siempre iniciar polling como detección principal
        self._polling_activo = True
        self._hilo_polling = threading.Thread(target=self._bucle_polling, daemon=True)
        self._hilo_polling.start()
        logger.info("Polling de USB activado (detección principal)")

        _monitor_activo = True
        self._ejecutando = True
        logger.info(f"Monitor USB iniciado correctamente en {NOMBRE_PLATAFORMA}")
        return True

    def detener(self) -> None:
        """Detiene el monitor de USB."""
        global _monitor_activo
        self._ejecutando = False
        self._polling_activo = False

        if ES_WINDOWS and self._ventana_hwnd:
            backend = _windows()
            if self._hilo_monitor and self._hilo_monitor.is_alive():
                backend.solicitar_salida_bucle(self._ventana_hwnd)
                self._hilo_monitor.join(timeout=2)
            backend.destruir_ventana(self._ventana_hwnd)
            self._ventana_hwnd = None
        elif self._hilo_monitor and self._hilo_monitor.is_alive():
            self._hilo_monitor.join(timeout=2)

        if self._hilo_polling and self._hilo_polling.is_alive():
            self._hilo_polling.join(timeout=2)

        _monitor_activo = False
        logger.info("Monitor USB detenido")

    def _bucle_mensajes(self) -> None:
        """Solo Windows: bombea los mensajes de la ventana oculta."""
        if not ES_WINDOWS:
            return
        _windows().bucle_mensajes()

    def _bucle_polling(self) -> None:
        """Bucle de polling principal - detecta unidades cada segundo."""
        while self._polling_activo and self._ejecutando:
            try:
                time.sleep(1.0)
                if not self._ejecutando:
                    break

                unidades = obtener_unidades_extraibles()
                letras = {u.letra for u in unidades}
                nuevas, removidas = _sincronizar_unidades(letras)

                for unidad in unidades:
                    if unidad.letra in nuevas:
                        logger.info(f"Polling: unidad nueva {unidad.letra} ({unidad.etiqueta}) tipo={unidad.tipo_drive}")
                        try:
                            if self._callback_llegada:
                                self._callback_llegada(unidad)
                        except Exception as e:
                            logger.error(f"Error en callback de llegada: {e}")

                for letra in removidas:
                    logger.info(f"Polling: unidad removida {letra}")
                    try:
                        if self._callback_remocion:
                            self._callback_remocion(letra)
                    except Exception as e:
                        logger.error(f"Error en callback de remoción: {e}")

            except Exception as e:
                logger.debug(f"Error en polling: {e}")

    def _escanear_unidades_iniciales(self) -> None:
        """Escanea unidades extraíbles presentes al iniciar."""
        unidades = obtener_unidades_extraibles()
        letras = {u.letra for u in unidades}
        _sincronizar_unidades(letras)
        logger.info(f"Unidades disponibles iniciales ({len(unidades)}): {[u.letra for u in unidades]}")

    def obtener_unidades_actuales(self) -> List[UnidadExtraible]:
        """Retorna lista de unidades USB/extraíbles actualmente conectadas."""
        return obtener_unidades_extraibles()


_monitor_instancia: Optional[MonitorUSB] = None


def obtener_monitor_usb() -> MonitorUSB:
    """Retorna la instancia singleton del monitor USB."""
    global _monitor_instancia
    if _monitor_instancia is None:
        _monitor_instancia = MonitorUSB()
    return _monitor_instancia
