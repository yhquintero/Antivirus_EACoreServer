"""
Módulo para detección y finalización de procesos EACoreServer.exe.
Usa psutil para gestión de procesos y win32api para operaciones de Windows.
"""

import os
import time
import psutil
import win32api
import win32con
import win32security
import win32process
import win32service
import win32serviceutil
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from logger import obtener_logger

logger = obtener_logger()


class EstadoProceso(Enum):
    """Estados posibles del proceso EACoreServer.exe."""
    NO_ENCONTRADO = "no_encontrado"
    ENCONTRADO_INACTIVO = "encontrado_inactivo"  # Archivo existe pero no se ejecuta
    ACTIVO = "activo"  # Proceso corriendo
    ERROR_ACCESO = "error_acceso"
    FINALIZADO = "finalizado"
    ERROR_FINALIZAR = "error_finalizar"


class ClasificacionRuta(Enum):
    """Clasificación prudente; un nombre de archivo no demuestra malware."""
    POSIBLE_COMPONENTE_EA = "posible_componente_ea"
    SIN_VERIFICAR = "sin_verificar"


@dataclass
class InfoRutaEACore:
    """Información de una ruta candidata de EACoreServer.exe"""
    ruta: str
    indice: int
    estado: EstadoProceso = EstadoProceso.NO_ENCONTRADO
    pid: Optional[int] = None
    nombre_proceso: str = ""
    usuario_propietario: str = ""
    tamano_bytes: int = 0
    fecha_modificacion: float = 0.0
    es_servicio: bool = False
    nombre_servicio: str = ""
    mensaje_error: str = ""
    clasificacion: ClasificacionRuta = ClasificacionRuta.SIN_VERIFICAR
    
    def a_dict(self) -> Dict:
        """Convierte a diccionario para la tabla de la GUI"""
        return {
            "indice": self.indice,
            "ruta": self.ruta,
            "estado": self.estado.value,
            "pid": self.pid if self.pid else "—",
            "usuario": self.usuario_propietario or "—",
            "tamano_kb": round(self.tamano_bytes / 1024, 1) if self.tamano_bytes else "—",
            # "servicio" es la clave consumida por la tabla de la GUI. Antes
            # se devolvía solo "es_servicio", lo que provocaba un KeyError al
            # mostrar cualquier resultado de escaneo.
            "servicio": self.nombre_servicio or ("Sí" if self.es_servicio else "—"),
            "clasificacion": (
                "Posible EA/Origin"
                if self.clasificacion is ClasificacionRuta.POSIBLE_COMPONENTE_EA
                else "Sin verificar"
            ),
            "error": self.mensaje_error or "—",
        }


class GestorProcesosEA:
    """Gestiona el diagnóstico de procesos llamados EACoreServer.exe.

    EACoreServer.exe ha sido distribuido legítimamente por EA/Origin y juegos
    de EA. Por ello, el nombre o una ruta publicada no se consideran evidencia
    de malware y las acciones destructivas se bloquean para ubicaciones de
    producto conocidas.
    """

    _MARCADORES_EA_CONOCIDOS = (
        "\\electronic arts\\",
        "\\origin games\\",
        "\\origin\\",
        "\\origin~",
        "\\eadm\\",
        "\\eadownloadmanager\\",
        "\\origin\\legacypm\\",
        "\\crytek\\crysis",
    )

    def __init__(self) -> None:
        self._cache_servicios: Dict[str, str] = {}  # ruta -> nombre_servicio

    @classmethod
    def ruta_probablemente_legitima(cls, ruta: str) -> bool:
        """Devuelve True para rutas típicas de componentes y juegos de EA.

        No sustituye una comprobación de firma digital, pero evita que una ruta
        de instalación conocida sea tratada como malware solo por su nombre.
        """
        ruta_normalizada = os.path.normcase(os.path.normpath(ruta))
        return any(marcador in ruta_normalizada for marcador in cls._MARCADORES_EA_CONOCIDOS)
    
    def escanear_rutas(self, rutas: List[str]) -> List[InfoRutaEACore]:
        """
        Escanea una lista de rutas y devuelve información de cada una.
        
        Args:
            rutas: Lista de rutas candidatas a verificar.
            
        Returns:
            Lista de InfoRutaEACore con estado de cada ruta.
        """
        resultados = []
        
        for idx, ruta in enumerate(rutas, 1):
            info = self._verificar_ruta(ruta, idx)
            resultados.append(info)
            logger.debug(f"Ruta {idx}: {ruta} -> {info.estado.value}")
        
        return resultados
    
    def _verificar_ruta(self, ruta: str, indice: int) -> InfoRutaEACore:
        """Verifica una ruta individual."""
        info = InfoRutaEACore(ruta=ruta, indice=indice)
        if self.ruta_probablemente_legitima(ruta):
            info.clasificacion = ClasificacionRuta.POSIBLE_COMPONENTE_EA

        try:
            # Verificar si el archivo existe
            if not os.path.exists(ruta):
                info.estado = EstadoProceso.NO_ENCONTRADO
                return info
            
            # Archivo existe, obtener metadatos
            stat = os.stat(ruta)
            info.tamano_bytes = stat.st_size
            info.fecha_modificacion = stat.st_mtime
            
            # Intentar obtener propietario
            try:
                info.usuario_propietario = self._obtener_propietario(ruta)
            except Exception:
                info.usuario_propietario = "Desconocido"
            
            # Verificar si está corriendo como proceso
            proceso_encontrado = self._buscar_proceso_por_ruta(ruta)
            if proceso_encontrado:
                info.pid = proceso_encontrado.pid
                info.nombre_proceso = proceso_encontrado.name()
                info.estado = EstadoProceso.ACTIVO
            else:
                info.estado = EstadoProceso.ENCONTRADO_INACTIVO
            
            # Verificar si es un servicio de Windows
            nombre_servicio = self._verificar_si_es_servicio(ruta)
            if nombre_servicio:
                info.es_servicio = True
                info.nombre_servicio = nombre_servicio
            
        except PermissionError:
            info.estado = EstadoProceso.ERROR_ACCESO
            info.mensaje_error = "Sin permisos para acceder al archivo"
            logger.warning(f"Sin permisos para acceder a: {ruta}")
        except Exception as e:
            info.estado = EstadoProceso.ERROR_ACCESO
            info.mensaje_error = str(e)
            logger.error(f"Error verificando ruta {ruta}: {e}")
        
        return info
    
    def _buscar_proceso_por_ruta(self, ruta: str) -> Optional[psutil.Process]:
        """Busca un proceso en ejecución que coincida con la ruta."""
        ruta_normalizada = os.path.normpath(ruta).lower()
        
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                if proc.info['exe']:
                    exe_normalizado = os.path.normpath(proc.info['exe']).lower()
                    if exe_normalizado == ruta_normalizada:
                        return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            except Exception:
                continue
        return None
    
    @staticmethod
    def _extraer_ejecutable_servicio(comando: str) -> str:
        """Extrae el ejecutable de un BinaryPathName de servicio de Windows."""
        comando = (comando or "").strip()
        if not comando:
            return ""
        if comando.startswith('"'):
            cierre = comando.find('"', 1)
            return comando[1:cierre] if cierre > 1 else ""
        # Un ejecutable sin comillas no puede contener espacios de forma fiable;
        # se conserva el primer token para no hacer comparaciones por subcadena.
        return comando.split(None, 1)[0]

    def _verificar_si_es_servicio(self, ruta: str) -> str:
        """Verifica con igualdad exacta si la ruta es el binario de un servicio."""
        ruta_norm = os.path.normcase(os.path.normpath(ruta))
        if ruta_norm in self._cache_servicios:
            return self._cache_servicios[ruta_norm]

        scm = None
        try:
            scm = win32service.OpenSCManager(
                None, None, win32service.SC_MANAGER_ENUMERATE_SERVICE
            )
            servicios = win32service.EnumServicesStatusEx(
                scm, win32service.SC_ENUM_PROCESS_INFO, win32service.SERVICE_WIN32
            )
            for servicio in servicios:
                nombre_servicio = servicio[0]
                h_servicio = None
                try:
                    h_servicio = win32service.OpenService(
                        scm, nombre_servicio, win32service.SERVICE_QUERY_CONFIG
                    )
                    config = win32service.QueryServiceConfig(h_servicio)
                    ruta_servicio = self._extraer_ejecutable_servicio(config[3])
                    if ruta_servicio and os.path.normcase(os.path.normpath(ruta_servicio)) == ruta_norm:
                        self._cache_servicios[ruta_norm] = nombre_servicio
                        return nombre_servicio
                except Exception:
                    continue
                finally:
                    if h_servicio:
                        try:
                            win32service.CloseServiceHandle(h_servicio)
                        except Exception:
                            pass
        except Exception as e:
            logger.debug(f"Error verificando servicios para {ruta}: {e}")
        finally:
            if scm:
                try:
                    win32service.CloseServiceHandle(scm)
                except Exception:
                    pass
        return ""
    
    def _obtener_propietario(self, ruta: str) -> str:
        """Obtiene el propietario del archivo."""
        try:
            sd = win32security.GetFileSecurity(
                ruta, win32security.OWNER_SECURITY_INFORMATION
            )
            owner_sid = sd.GetSecurityDescriptorOwner()
            nombre, dominio, _ = win32security.LookupAccountSid(None, owner_sid)
            return f"{dominio}\\{nombre}" if dominio else nombre
        except Exception:
            return "Desconocido"
    
    def finalizar_proceso(self, info: InfoRutaEACore) -> Tuple[bool, str]:
        """
        Intenta finalizar el proceso EACoreServer.exe.
        
        Returns:
            Tupla (exito, mensaje)
        """
        if info.estado != EstadoProceso.ACTIVO or not info.pid:
            return False, "No hay proceso activo para finalizar"
        
        try:
            # Primero intentar terminar el proceso suavemente
            proc = psutil.Process(info.pid)
            proc.terminate()
            
            # Esperar un poco
            try:
                proc.wait(timeout=5)
                logger.log_proceso_ea(info.ruta, "Finalizado (terminate)", True)
                info.estado = EstadoProceso.FINALIZADO
                info.pid = None
                return True, "Proceso finalizado correctamente"
            except psutil.TimeoutExpired:
                # Forzar terminación
                proc.kill()
                proc.wait(timeout=3)
                logger.log_proceso_ea(info.ruta, "Finalizado (kill forzado)", True)
                info.estado = EstadoProceso.FINALIZADO
                info.pid = None
                return True, "Proceso finalizado forzosamente"
                
        except psutil.NoSuchProcess:
            info.estado = EstadoProceso.FINALIZADO
            info.pid = None
            return True, "El proceso ya no existe"
        except psutil.AccessDenied:
            # Intentar con privilegios de administrador vía taskkill
            return self._finalizar_con_taskkill(info)
        except Exception as e:
            logger.log_proceso_ea(info.ruta, f"Error al finalizar: {e}", False)
            info.estado = EstadoProceso.ERROR_FINALIZAR
            info.mensaje_error = str(e)
            return False, f"Error: {e}"
    
    def _finalizar_con_taskkill(self, info: InfoRutaEACore) -> Tuple[bool, str]:
        """Intenta finalizar usando taskkill con elevación."""
        try:
            import subprocess
            # Usar taskkill /F /PID
            resultado = subprocess.run(
                ["taskkill", "/F", "/PID", str(info.pid), "/T"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if resultado.returncode == 0:
                logger.log_proceso_ea(info.ruta, "Finalizado (taskkill)", True)
                info.estado = EstadoProceso.FINALIZADO
                info.pid = None
                return True, "Proceso finalizado con taskkill"
            else:
                return False, f"taskkill falló: {resultado.stderr}"
        except Exception as e:
            return False, f"Error en taskkill: {e}"
    
    def detener_servicio(self, info: InfoRutaEACore) -> Tuple[bool, str]:
        """Detiene el servicio de Windows si existe."""
        if not info.es_servicio or not info.nombre_servicio:
            return False, "No es un servicio registrado"
        
        try:
            # Intentar detener el servicio
            win32serviceutil.StopService(info.nombre_servicio)
            logger.log_proceso_ea(info.ruta, f"Servicio {info.nombre_servicio} detenido", True)
            return True, f"Servicio {info.nombre_servicio} detenido"
        except Exception as e:
            logger.log_proceso_ea(info.ruta, f"Error deteniendo servicio: {e}", False)
            return False, f"Error deteniendo servicio: {e}"
    
    def deshabilitar_servicio(self, info: InfoRutaEACore) -> Tuple[bool, str]:
        """Deshabilita el servicio para que no inicie automáticamente."""
        if not info.es_servicio or not info.nombre_servicio:
            return False, "No es un servicio registrado"
        
        try:
            win32serviceutil.ChangeServiceConfig(
                info.nombre_servicio,
                startType=win32service.SERVICE_DISABLED
            )
            return True, f"Servicio {info.nombre_servicio} deshabilitado"
        except Exception as e:
            return False, f"Error deshabilitando servicio: {e}"
    
    def finalizar_todo(self, infos: List[InfoRutaEACore]) -> Dict[str, Tuple[bool, str]]:
        """
        Finaliza todos los procesos EACoreServer activos.
        
        Returns:
            Diccionario ruta -> (exito, mensaje)
        """
        resultados = {}
        for info in infos:
            if info.estado == EstadoProceso.ACTIVO:
                exito, msg = self.finalizar_proceso(info)
                resultados[info.ruta] = (exito, msg)
            elif info.es_servicio:
                exito, msg = self.detener_servicio(info)
                resultados[info.ruta] = (exito, msg)
            else:
                resultados[info.ruta] = (True, "No requiere acción")
        return resultados
    
    def _quitar_atributos_archivo(self, ruta: str) -> None:
        """Quita atributos de solo lectura/oculto/sistema de un archivo."""
        try:
            win32api.SetFileAttributes(ruta, win32con.FILE_ATTRIBUTE_NORMAL)
        except Exception:
            pass
    
    def _eliminar_archivo_con_reintentos(self, ruta: str, intentos: int = 6,
                                         espera: float = 0.5) -> bool:
        """
        Elimina un archivo por completo, reintentando mientras esté bloqueado
        (p. ej. mientras Windows aún lo tiene en uso tras detener el servicio).
        """
        if not os.path.exists(ruta):
            logger.log_proceso_ea(ruta, "No existe (no requiere eliminación)", True)
            return True
        
        for intento in range(intentos):
            try:
                self._quitar_atributos_archivo(ruta)
                os.remove(ruta)
                logger.log_proceso_ea(ruta, "Eliminado por completo", True)
                return True
            except PermissionError:
                logger.debug(
                    f"Archivo bloqueado (reintento {intento + 1}/{intentos}): {ruta}")
                time.sleep(espera)
            except Exception as e:
                logger.log_proceso_ea(ruta, f"Error eliminando: {e}", False)
                time.sleep(espera)
        return False
    
    def detener_y_eliminar_archivos(
        self, ruta_exe: str, permitir_componente_ea: bool = False
    ) -> Dict[str, object]:
        """Detiene y elimina una instalación no confiable bajo confirmación.

        El nombre ``EACoreServer.exe`` pertenece también a software legítimo de
        EA. Por defecto, una ruta típica de EA/Origin queda protegida; el
        llamador debe optar explícitamente por ``permitir_componente_ea`` tras
        una revisión humana para anular esa protección.
        """
        resultados = {
            "ruta_exe": ruta_exe,
            "servicio_detenido": False,
            "servicio_deshabilitado": False,
            "exe_eliminado": False,
            "dat_eliminado": False,
            "accion_bloqueada": False,
            "detalles": [],
        }
        if self.ruta_probablemente_legitima(ruta_exe) and not permitir_componente_ea:
            resultados["accion_bloqueada"] = True
            resultados["detalles"].append(
                "Acción bloqueada: la ruta parece pertenecer a una instalación legítima de EA/Origin. "
                "Revise firma digital y origen del archivo antes de eliminarlo."
            )
            logger.warning(f"Eliminación bloqueada para posible componente EA: {ruta_exe}")
            return resultados

        # 1) Finalizar el proceso si está activo
        info = InfoRutaEACore(ruta=ruta_exe, indice=0)
        try:
            proc = self._buscar_proceso_por_ruta(ruta_exe)
            if proc:
                info.pid = proc.pid
                info.estado = EstadoProceso.ACTIVO
                exito, msg = self.finalizar_proceso(info)
                resultados["detalles"].append(f"Proceso activo finalizado: {msg}")
        except Exception as e:
            resultados["detalles"].append(f"Error finalizando proceso: {e}")
        
        # 2) Detener y deshabilitar el servicio asociado (si lo hay) para que
        #    no se reinicie solo y vuelva a crear los ficheros.
        try:
            nombre_servicio = self._verificar_si_es_servicio(ruta_exe)
            if nombre_servicio:
                info.es_servicio = True
                info.nombre_servicio = nombre_servicio
                exito, msg = self.detener_servicio(info)
                resultados["servicio_detenido"] = exito
                resultados["detalles"].append(f"Servicio '{nombre_servicio}': {msg}")
                try:
                    self.deshabilitar_servicio(info)
                    resultados["servicio_deshabilitado"] = True
                    resultados["detalles"].append(
                        f"Servicio '{nombre_servicio}' deshabilitado (no arrancará solo)")
                except Exception as e:
                    resultados["detalles"].append(
                        f"No se pudo deshabilitar el servicio: {e}")
        except Exception as e:
            resultados["detalles"].append(f"Error gestionando servicio: {e}")
        
        # 3) Esperar a que se liberen y eliminar ambos ficheros
        carpeta = os.path.dirname(ruta_exe)
        ruta_dat = os.path.join(carpeta, "EACore.dat")
        resultados["exe_eliminado"] = self._eliminar_archivo_con_reintentos(ruta_exe)
        resultados["dat_eliminado"] = self._eliminar_archivo_con_reintentos(ruta_dat)
        
        return resultados
    
    def detener_y_eliminar_servicio_programdata(self) -> Dict[str, object]:
        """
        Atajo: detiene el servicio EACoreService de ProgramData y elimina
        EACoreServer.exe + EACore.dat de esa carpeta (ruta #57).
        """
        ruta = r"C:\ProgramData\EACoreService\EACoreServer.exe"
        if not os.path.exists(ruta):
            return {"ruta_exe": ruta, "error": "El servicio EACoreService no está instalado en este equipo"}
        return self.detener_y_eliminar_archivos(ruta)


# Instancia global
_gestor_instancia: Optional[GestorProcesosEA] = None


def obtener_gestor_procesos() -> GestorProcesosEA:
    """Retorna la instancia singleton del gestor de procesos."""
    global _gestor_instancia
    if _gestor_instancia is None:
        _gestor_instancia = GestorProcesosEA()
    return _gestor_instancia