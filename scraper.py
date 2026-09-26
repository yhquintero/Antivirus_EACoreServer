"""
Módulo de consulta para obtener rutas candidatas de EACoreServer.exe
desde la versión HTTPS de processchecker.com.
"""

import re
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from logger import obtener_logger

logger = obtener_logger()

# Solo HTTPS: la lista remota no debe poder ser alterada en tránsito.
URL_PROCESSCHECKER = "https://processchecker.com/file/EACoreServer.exe.html"
TIMEOUT_SEGUNDOS = 10
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class ScraperEACoreServer:
    """Scraper para obtener rutas de EACoreServer.exe desde processchecker.com"""
    
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self._rutas_cache: Optional[List[str]] = None
    
    def obtener_rutas_candidatas(self, forzar_actualizacion: bool = False) -> List[str]:
        """
        Obtiene la lista de rutas candidatas desde la web.
        
        Args:
            forzar_actualizacion: Si True, ignora el cache y hace scraping fresco.
            
        Returns:
            Lista de rutas candidatas (strings).
        """
        if self._rutas_cache is not None and not forzar_actualizacion:
            logger.debug("Retornando rutas desde cache")
            return self._rutas_cache
        
        try:
            logger.info("Iniciando scraping de rutas EACoreServer.exe desde processchecker.com")
            respuesta = self.session.get(URL_PROCESSCHECKER, timeout=TIMEOUT_SEGUNDOS)
            respuesta.raise_for_status()
            
            rutas = self._extraer_rutas_html(respuesta.text)
            
            if not rutas:
                logger.warning("No se encontraron rutas en el scraping, usando rutas por defecto")
                rutas = self._rutas_por_defecto()
            else:
                # Fusionar con las 57 rutas por defecto para garantizar cobertura total
                rutas = self._fusionar_con_defecto(rutas)
            
            self._rutas_cache = rutas
            logger.info(f"Scraping completado: {len(rutas)} rutas candidatas obtenidas")
            return rutas
            
        except requests.RequestException as e:
            logger.error(f"Error de red en scraping: {e}")
            logger.info("Usando rutas por defecto como respaldo")
            self._rutas_cache = self._rutas_por_defecto()
            return self._rutas_cache
        except Exception as e:
            logger.error(f"Error inesperado en scraping: {e}", exc_info=True)
            self._rutas_cache = self._rutas_por_defecto()
            return self._rutas_cache
    
    def _extraer_rutas_html(self, html: str) -> List[str]:
        """Extrae las rutas del HTML de processchecker.com"""
        soup = BeautifulSoup(html, "html.parser")
        rutas = []

        # Buscar en tablas, listas o divs que contengan rutas de archivos
        # Processchecker suele mostrar las rutas en una tabla o lista
        
        # Estrategia 1: Buscar en tablas
        for tabla in soup.find_all("table"):
            for fila in tabla.find_all("tr"):
                celdas = fila.find_all(["td", "th"])
                for celda in celdas:
                    texto = self._normalizar_ruta(celda.get_text(" ", strip=True))
                    if self._es_ruta_valida(texto):
                        rutas.append(texto)
        
        # Estrategia 2: Buscar en elementos con clase/path
        for elem in soup.find_all(text=re.compile(r"[A-Za-z]:\\.*EACoreServer\.exe", re.IGNORECASE)):
            texto_limpio = self._normalizar_ruta(str(elem))
            if self._es_ruta_valida(texto_limpio):
                rutas.append(texto_limpio)
        
        # Estrategia 3: Buscar en todos los textos que parezcan rutas de Windows
        patron_ruta = re.compile(r"[A-Za-z]:(?:\\|\/)(?:[^\\/:*?\"<>|\r\n]+\\)*EACoreServer\.exe", re.IGNORECASE)
        for match in patron_ruta.finditer(html):
            ruta = self._normalizar_ruta(match.group(0))
            if self._es_ruta_valida(ruta):
                rutas.append(ruta)
        
        # Deduplicar manteniendo orden
        vistas = set()
        rutas_unicas = []
        for ruta in rutas:
            ruta_norm = ruta.lower()
            if ruta_norm not in vistas:
                vistas.add(ruta_norm)
                rutas_unicas.append(ruta)
        
        return rutas_unicas
    
    @staticmethod
    def _normalizar_ruta(texto: str) -> str:
        """Devuelve una ruta Windows limpia, sin texto accesorio de la página."""
        texto = (texto or "").strip().strip('"\'`')
        texto = texto.replace("/", "\\")
        # Una celda puede traer puntuación o espacios al final de una frase.
        return texto.rstrip(" .;,)")

    def _es_ruta_valida(self, texto: str) -> bool:
        """Verifica que el texto sea exactamente una ruta a EACoreServer.exe."""
        if not texto or len(texto) < 10:
            return False
        return bool(re.fullmatch(
            r"[A-Za-z]:\\(?:[^\\/:*?\"<>|\r\n]+\\)*EACoreServer\.exe",
            texto,
            re.IGNORECASE,
        ))

    def _fusionar_con_defecto(self, rutas: List[str]) -> List[str]:
        """Fusiona las rutas obtenidas de la web con las 57 por defecto,
        deduplicando (insensible a mayúsculas) y respetando el orden."""
        vistas = set()
        combinadas = []
        for ruta in list(rutas) + self._rutas_por_defecto():
            clave = ruta.lower()
            if clave not in vistas:
                vistas.add(clave)
                combinadas.append(ruta)
        return combinadas
    
    def _rutas_por_defecto(self) -> List[str]:
        """
        Las 57 rutas exactas de EACoreServer.exe reportadas en
        https://processchecker.com/file/EACoreServer.exe.html
        (orden de la tabla original: Path / Product / Vendor / Version / Size / MD5).
        """
        rutas_base = [
            # 1-3: EADM y Crysis 2 en Program Files
            r"C:\Program Files\Electronic Arts\EADM\EACoreServer.exe",
            r"C:\Program Files\Electronic Arts\Crytek\Crysis 2\bin32\EACore\EACoreServer.exe",
            r"C:\Program Files (x86)\Electronic Arts\Crytek\Crysis 2\bin32\EACore\EACoreServer.exe",
            # 4-6
            r"E:\Crysis 2\bin32\EACore\EACoreServer.exe",
            r"C:\Program Files\Electronic Arts\EADownloadManager\EACoreServer.exe",
            r"C:\Program Files (x86)\Electronic Arts\EADownloadManager\EACoreServer.exe",
            # 7-12: Crysis 2 (bin32\EACore) en varias unidades
            r"D:\game\Core\EACoreServer.exe",
            r"D:\Program Files\Electronic Arts\Crytek\Crysis 2\bin32\EACore\EACoreServer.exe",
            r"D:\descargas en d\juegos\crysis2\instalado\bin32\EACore\EACoreServer.exe",
            r"D:\Crytek\Crysis 2\bin32\EACore\EACoreServer.exe",
            r"F:\cri\bin32\EACore\EACoreServer.exe",
            r"D:\Games\Crysis 2\bin32\EACore\EACoreServer.exe",
            # 13-20: Battlefield 3 (Core\EACoreServer.exe)
            r"E:\BF3\Battlefield 3\Core\EACoreServer.exe",
            r"C:\PROGRA~2\ORIGIN~1\BATTLE~3\Core\EACoreServer.exe",
            r"G:\Core\EACoreServer.exe",
            r"D:\jeux\Core\EACoreServer.exe",
            r"C:\Program Files (x86)\Electronic Arts\EADM\EACoreServer.exe",
            r"E:\OriginGames\Battlefield 3\Core\EACoreServer.exe",
            r"C:\Program Files (x86)\Origin Games\Battlefield 3\Core\EACoreServer.exe",
            r"D:\Gry\Battlefield 3\Core\EACoreServer.exe",
            # 21-30: NFS, Crysis 2 FARSI, Origin, Battlefield 3
            r"C:\PROGRA~2\ELECTR~1\NEEDFO~1\Core\EACoreServer.exe",
            r"C:\Archivos de programa\Electronic Arts\Crytek\Crysis 2\bin32\EACore\EACoreServer.exe",
            r"D:\games\NeedforSpeedHotPursuit\Core\EACoreServer.exe",
            r"C:\Program Files\SarirGame\Crysis 2 [FARSI]\bin32\EACore\EACoreServer.exe",
            r"D:\Origin\Battlefield 3\Core\EACoreServer.exe",
            r"F:\Jeux Origin\Battlefield 3\Core\EACoreServer.exe",
            r"F:\Program Files (x86)\Origin Games\Battlefield 4\Battlefield 3\Core\EACoreServer.exe",
            r"G:\Crysis 2\bin32\EACore\EACoreServer.exe",
            r"D:\Program Files (x86)\Origin Games\Bejeweled 3\Bejeweled 3 DE\Core\EACoreServer.exe",
            r"D:\GAMES\nfs\Core\EACoreServer.exe",
            # 31-39: Battlefield 3 nosTEAM, EADM, Mass Effect, Need for Speed, Battlefield
            r"E:\New folder\New folder\Battlefield 3 nosTEAM\Core\EACoreServer.exe",
            r"D:\Games\EADM\EACoreServer.exe",
            r"C:\PROGRA~2\ORIGIN~1\MASSEF~1\binaries\Win32\Core\EACoreServer.exe",
            r"D:\PROGRA~2\ORIGIN~1\BATTLE~1\Core\EACoreServer.exe",
            r"C:\PROGRA~2\ORIGIN~1\MASSEF~2\binaries\Win32\Core\EACoreServer.exe",
            r"C:\PROGRA~2\ORIGIN~1\BATTLE~1\Core\EACoreServer.exe",
            r"C:\PROGRA~2\NEEDFO~1\Core\EACoreServer.exe",
            r"E:\Battlefield 3\Core\EACoreServer.exe",
            r"C:\PROGRA~2\Origin\LegacyPM\EACoreServer.exe",
            # 40-46: Origin LegacyPM (x64), EADM, Origin games, Battlefield, Plants vs Zombies
            r"C:\PROGRA~1\Origin\LegacyPM\EACoreServer.exe",
            r"C:\PROGRA~2\ELECTR~1\EADM\EACoreServer.exe",
            r"C:\PROGRA~1\ELECTR~1\EADM\EACoreServer.exe",
            r"E:\Program Files (x86)\Origin Games\Battlefield 3\Core\EACoreServer.exe",
            r"C:\PROGRA~2\ORIGIN~1\PLANTS~1.ZOM\PLANTS~2.ZOM\Core\EACoreServer.exe",
            r"D:\torrent oyun\crysis 2\bin32\EACore\EACoreServer.exe",
            r"D:\BATTLE~1\Core\EACoreServer.exe",
            # 47-52: EADM, FIFA 12, Origin Games, unidad A:, ProgramData (servicio EA)
            r"D:\BFV\FIFA 12\Game\Core\EACoreServer.exe",
            r"D:\Program Files (x86)\Origin Games\Battlefield 3\Core\EACoreServer.exe",
            r"A:\GAMES\BATTLE~1\Core\EACoreServer.exe",
            r"D:\Origin Games\Battlefield 3\Core\EACoreServer.exe",
            r"D:\Games\BATTLE~1\Core\EACoreServer.exe",
            r"C:\ProgramData\EACoreService\EACoreServer.exe",
        ]

        return rutas_base


# Instancia global
_scraper_instancia: Optional[ScraperEACoreServer] = None


def obtener_scraper() -> ScraperEACoreServer:
    """Retorna la instancia singleton del scraper."""
    global _scraper_instancia
    if _scraper_instancia is None:
        _scraper_instancia = ScraperEACoreServer()
    return _scraper_instancia


def obtener_rutas_candidatas(forzar_actualizacion: bool = False) -> List[str]:
    """Función de conveniencia para obtener rutas candidatas."""
    return obtener_scraper().obtener_rutas_candidatas(forzar_actualizacion)