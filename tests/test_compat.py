"""Pruebas de la matriz de compatibilidad de sistemas operativos.

Cubren el requisito de atender Windows antiguos (Vista, 7, 8, 8.1) además de
los sistemas modernos, y de degradar con elegancia en Unix no reconocidos.

Ninguna prueba depende del sistema donde se ejecuta: las versiones de Windows y
las familias Unix se simulan parcheando ``platform``, de modo que la matriz se
verifica por igual en los runners de Linux, macOS y Windows del CI.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import compat
from compat import (
    FAMILIA_AIX,
    FAMILIA_BSD,
    FAMILIA_DESCONOCIDA,
    FAMILIA_LINUX,
    FAMILIA_MACOS,
    FAMILIA_SOLARIS,
    KB_WINDOWS_7,
    MAXIMO_PYTHON_POR_WINDOWS,
    MINIMO_PYTHON,
    SOPORTE_COMPLETO,
    SOPORTE_DIAGNOSTICO,
    SOPORTE_NO_SOPORTADO,
    InfoPlataforma,
    detectar_plataforma,
    es_proceso_32_en_so_64,
    es_windows,
    mensaje_de_no_soporte,
    obtener_arquitectura,
    obtener_bits_proceso,
    obtener_familia_posix,
    obtener_info_plataforma,
    python_maximo_para_windows,
)

NIVELES_VALIDOS = {SOPORTE_COMPLETO, SOPORTE_DIAGNOSTICO, SOPORTE_NO_SOPORTADO}
FAMILIAS_VALIDAS = {
    "windows", FAMILIA_LINUX, FAMILIA_MACOS, FAMILIA_BSD,
    FAMILIA_SOLARIS, FAMILIA_AIX, FAMILIA_DESCONOCIDA,
}


class _SimuladorWindows:
    """Context manager que simula una edición concreta de Windows."""

    def __init__(self, version, nombre):
        self.version = version
        self.nombre = nombre
        self._parches = []

    def __enter__(self):
        objetivos = [
            mock.patch.object(compat.platform, "system", return_value="Windows"),
            mock.patch.object(compat.platform, "release", return_value=str(self.version[0])),
            mock.patch.object(compat, "obtener_version_windows", return_value=self.version),
            mock.patch.object(compat, "nombre_edicion_windows", return_value=self.nombre),
        ]
        for parche in objetivos:
            parche.start()
            self._parches.append(parche)
        return self

    def __exit__(self, *exc):
        for parche in reversed(self._parches):
            parche.stop()
        return False


class _SimuladorUnix:
    """Context manager que simula un sistema Unix concreto (BSD, Solaris, AIX...)."""

    def __init__(self, sistema, release="13.2-RELEASE"):
        self.sistema = sistema
        self.release = release
        self._parches = []

    def __enter__(self):
        objetivos = [
            mock.patch.object(compat.platform, "system", return_value=self.sistema),
            mock.patch.object(compat.platform, "release", return_value=self.release),
            mock.patch.object(compat.os, "name", "posix"),
        ]
        for parche in objetivos:
            parche.start()
            self._parches.append(parche)
        return self

    def __exit__(self, *exc):
        for parche in reversed(self._parches):
            parche.stop()
        return False


class TestMatrizPythonPorWindows(unittest.TestCase):
    """La tabla de Python máximo instalable debe coincidir con la de CPython."""

    def test_windows_xp_y_anteriores_quedan_en_python_34(self):
        # 5.0 = 2000, 5.1 = XP, 5.2 = XP x64 / Server 2003
        for version in ((5, 0), (5, 1), (5, 2)):
            self.assertEqual(MAXIMO_PYTHON_POR_WINDOWS[version], (3, 4), version)

    def test_vista_windows7_y_windows8_quedan_en_python_38(self):
        # 6.0 = Vista, 6.1 = 7, 6.2 = 8.0: desde 3.9 el intérprete no arranca
        for version in ((6, 0), (6, 1), (6, 2)):
            self.assertEqual(MAXIMO_PYTHON_POR_WINDOWS[version], (3, 8), version)

    def test_windows_81_llega_hasta_python_312(self):
        self.assertEqual(MAXIMO_PYTHON_POR_WINDOWS[(6, 3)], (3, 12))

    def test_windows_10_y_11_comparten_entrada_moderna(self):
        # 10.0 cubre Windows 10 y 11 (build >= 22000)
        self.assertEqual(MAXIMO_PYTHON_POR_WINDOWS[(10, 0)], (3, 14))

    def test_todos_los_maximos_cumplen_o_superan_el_minimo_salvo_xp(self):
        for version, maximo in MAXIMO_PYTHON_POR_WINDOWS.items():
            if version[0] <= 5:
                self.assertLess(maximo, MINIMO_PYTHON, version)
            else:
                self.assertGreaterEqual(maximo, MINIMO_PYTHON, version)

    def test_kb_de_windows_7_es_la_correcta(self):
        # Python 3.8 exige el update de la API de carga de DLL en Windows 7
        self.assertEqual(KB_WINDOWS_7, "KB2533623")


class TestDeteccionDeWindowsSimulados(unittest.TestCase):
    """Clasificación de cada edición de Windows, simulada para correr en cualquier SO."""

    def test_windows_xp_queda_explicitamente_no_soportado(self):
        with _SimuladorWindows((5, 1, 2600), "Windows XP"):
            info = detectar_plataforma()
        self.assertEqual(info.nivel_soporte, SOPORTE_NO_SOPORTADO)
        self.assertEqual(info.familia, "windows")
        # El mensaje debe explicar el porqué y dar una salida, no solo fallar.
        self.assertIn("3.4.4", info.motivo)
        self.assertIn("Vista", info.motivo)

    def test_windows_2000_y_server_2003_tambien_no_soportados(self):
        for version, nombre in (((5, 0, 2195), "Windows 2000"),
                                ((5, 2, 3790), "Windows Server 2003")):
            with _SimuladorWindows(version, nombre):
                info = detectar_plataforma()
            self.assertEqual(info.nivel_soporte, SOPORTE_NO_SOPORTADO, nombre)
            self.assertIn(nombre, info.motivo)

    def test_windows_vista_es_soporte_completo_con_aviso_de_python_38(self):
        with _SimuladorWindows((6, 0, 6002), "Windows Vista"):
            info = detectar_plataforma()
        self.assertEqual(info.nivel_soporte, SOPORTE_COMPLETO)
        self.assertIn("3.8", info.motivo)
        self.assertIn("3.9", info.motivo)

    def test_windows_7_es_soportado_y_menciona_el_kb_requerido(self):
        with _SimuladorWindows((6, 1, 7601), "Windows 7"):
            info = detectar_plataforma()
        self.assertEqual(info.nivel_soporte, SOPORTE_COMPLETO)
        self.assertIn(KB_WINDOWS_7, info.motivo)

    def test_windows_8_es_soportado_con_aviso_de_python_38(self):
        with _SimuladorWindows((6, 2, 9200), "Windows 8"):
            info = detectar_plataforma()
        self.assertEqual(info.nivel_soporte, SOPORTE_COMPLETO)
        self.assertIn("3.8", info.motivo)

    def test_windows_81_indica_su_rango_de_python(self):
        with _SimuladorWindows((6, 3, 9600), "Windows 8.1"):
            info = detectar_plataforma()
        self.assertEqual(info.nivel_soporte, SOPORTE_COMPLETO)
        self.assertIn("3.8", info.motivo)
        self.assertIn("3.12", info.motivo)

    def test_windows_10_y_11_no_cargan_avisos_innecesarios(self):
        for build, nombre in ((19045, "Windows 10"), (22631, "Windows 11")):
            with _SimuladorWindows((10, 0, build), nombre):
                info = detectar_plataforma()
            self.assertEqual(info.nivel_soporte, SOPORTE_COMPLETO, nombre)
            self.assertEqual(info.motivo, "", nombre)
            self.assertEqual(info.nombre_amigable, nombre)

    def test_el_nombre_amigable_se_conserva_en_windows(self):
        with _SimuladorWindows((6, 1, 7601), "Windows 7 Professional"):
            info = detectar_plataforma()
        self.assertEqual(info.nombre_amigable, "Windows 7 Professional")


class TestDeteccionDeUnix(unittest.TestCase):
    """BSD, Solaris y AIX deben reconocerse y degradar a modo diagnóstico."""

    def test_bsd_queda_en_modo_diagnostico(self):
        for sistema in ("FreeBSD", "OpenBSD", "NetBSD", "DragonFly"):
            with _SimuladorUnix(sistema):
                info = detectar_plataforma()
            self.assertEqual(info.familia, FAMILIA_BSD, sistema)
            self.assertEqual(info.nivel_soporte, SOPORTE_DIAGNOSTICO, sistema)
            # Debe advertir que la detección de extraíbles es conservadora.
            self.assertIn("conservadora", info.motivo)

    def test_solaris_e_illumos_quedan_en_modo_diagnostico(self):
        for sistema in ("SunOS", "illumos"):
            with _SimuladorUnix(sistema, "5.11"):
                info = detectar_plataforma()
            self.assertEqual(info.familia, FAMILIA_SOLARIS, sistema)
            self.assertEqual(info.nivel_soporte, SOPORTE_DIAGNOSTICO, sistema)

    def test_aix_queda_en_modo_diagnostico(self):
        with _SimuladorUnix("AIX", "7.2"):
            info = detectar_plataforma()
        self.assertEqual(info.familia, FAMILIA_AIX)
        self.assertEqual(info.nivel_soporte, SOPORTE_DIAGNOSTICO)

    def test_sistema_no_reconocido_no_rompe_y_avisa(self):
        with _SimuladorUnix("Plan9", "4.0"):
            info = detectar_plataforma()
        self.assertEqual(info.familia, FAMILIA_DESCONOCIDA)
        self.assertEqual(info.nivel_soporte, SOPORTE_DIAGNOSTICO)
        self.assertIn("no reconocido", info.motivo)

    def test_el_nombre_amigable_de_bsd_incluye_la_version(self):
        with _SimuladorUnix("FreeBSD", "13.2-RELEASE"):
            info = detectar_plataforma()
        self.assertEqual(info.nombre_amigable, "FreeBSD 13.2-RELEASE")


class TestPlataformaReal(unittest.TestCase):
    """Comprobaciones que sí dependen del sistema donde corre el test."""

    def setUp(self):
        self.info = obtener_info_plataforma(forzar=True)

    def tearDown(self):
        # Dejar la caché limpia para no contaminar otras pruebas.
        obtener_info_plataforma(forzar=True)

    def test_devuelve_un_infoplataforma_completo(self):
        self.assertIsInstance(self.info, InfoPlataforma)
        self.assertIn(self.info.nivel_soporte, NIVELES_VALIDOS)
        self.assertIn(self.info.familia, FAMILIAS_VALIDAS)
        self.assertTrue(self.info.sistema)
        self.assertTrue(self.info.nombre_amigable)
        self.assertTrue(self.info.python_version)

    def test_arquitectura_y_bits_son_coherentes(self):
        conocidas = {"x86", "x64", "arm64", "arm32"}
        arquitectura = self.info.arquitectura
        if arquitectura not in conocidas:
            # En CPU no catalogadas (s390x, ppc64le, riscv64...) la etiqueta
            # degrada a "<máquina>-<bits>bits" en vez de fallar.
            self.assertRegex(arquitectura, r"^[a-z0-9_]+-(32|64)bits$")
        self.assertIn(self.info.bits_proceso, (32, 64))
        if arquitectura == "x64":
            # Garantizado por el código: solo devuelve x64 cuando el proceso es
            # de 64 bits. La etiqueta "x86" en cambio también puede salir de una
            # máquina i386 con intérprete de 64 bits, así que no se afirma nada.
            self.assertEqual(self.info.bits_proceso, 64)

    def test_bits_del_proceso_y_arquitectura_coinciden_con_el_interprete(self):
        self.assertEqual(obtener_bits_proceso(), self.info.bits_proceso)
        self.assertEqual(obtener_arquitectura(), self.info.arquitectura)

    def test_es_proceso_32_en_so_64_devuelve_booleano(self):
        self.assertIsInstance(es_proceso_32_en_so_64(), bool)

    def test_es_windows_coincide_con_el_sistema_real(self):
        self.assertEqual(es_windows(), sys.platform.startswith("win"))

    def test_familia_posix_es_una_de_las_conocidas(self):
        self.assertIn(obtener_familia_posix(), FAMILIAS_VALIDAS)

    def test_la_caché_devuelve_la_misma_instancia_hasta_forzar(self):
        primera = obtener_info_plataforma()
        self.assertIs(primera, obtener_info_plataforma())
        self.assertIsNot(primera, obtener_info_plataforma(forzar=True))

    def test_python_maximo_es_nulo_fuera_de_windows(self):
        if sys.platform.startswith("win"):
            self.assertIsNotNone(python_maximo_para_windows())
        else:
            self.assertIsNone(python_maximo_para_windows())

    def test_mensaje_de_no_soporte_es_nulo_en_sistemas_atendidos(self):
        if self.info.nivel_soporte == SOPORTE_NO_SOPORTADO:
            self.assertTrue(mensaje_de_no_soporte())
        else:
            self.assertIsNone(mensaje_de_no_soporte())

    def test_en_linux_y_macos_la_herramienta_avisa_del_modo_diagnostico(self):
        if self.info.familia in (FAMILIA_LINUX, FAMILIA_MACOS):
            self.assertEqual(self.info.nivel_soporte, SOPORTE_COMPLETO)
            self.assertIn("diagnóstico", self.info.motivo)

    def test_la_deteccion_es_repetible(self):
        with mock.patch.object(compat, "_info_cache", None):
            otra = detectar_plataforma()
        self.assertEqual(otra.nivel_soporte, self.info.nivel_soporte)
        self.assertEqual(otra.familia, self.info.familia)
        self.assertEqual(otra.arquitectura, self.info.arquitectura)


class TestPythonInsuficiente(unittest.TestCase):
    """Si el intérprete es anterior al mínimo, nada debe presentarse como soportado."""

    def test_python_antiguo_marca_no_soportado_en_posix(self):
        antiguo = (3, 6)
        with mock.patch.object(compat.sys, "version_info", antiguo), \
                _SimuladorUnix("Linux", "5.10"):
            info = detectar_plataforma()
        self.assertEqual(info.nivel_soporte, SOPORTE_NO_SOPORTADO)
        self.assertIn("3.8", info.motivo)
        self.assertIn("3.6", info.motivo)

    def test_python_antiguo_marca_no_soportado_en_windows_moderno(self):
        antiguo = (3, 7)
        with mock.patch.object(compat.sys, "version_info", antiguo), \
                _SimuladorWindows((10, 0, 19045), "Windows 10"):
            info = detectar_plataforma()
        self.assertEqual(info.nivel_soporte, SOPORTE_NO_SOPORTADO)
        self.assertIn("3.8", info.motivo)

    def test_el_minimo_requerido_es_python_38(self):
        # Piso decidido para cubrir desde Windows Vista/7 hasta los Unix modernos.
        self.assertEqual(MINIMO_PYTHON, (3, 8))


if __name__ == "__main__":
    unittest.main(verbosity=2)
