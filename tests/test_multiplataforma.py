"""Pruebas de compatibilidad multiplataforma (Windows, macOS y Linux).

Garantizan que el proyecto puede importarse y ejercitarse en los tres sistemas
que cubre el CI, incluso cuando ``pywin32`` no está instalado. Ninguna prueba
requiere una unidad USB real ni privilegios de administrador.
"""

from __future__ import annotations

import os
import platform
import sys
import unittest
from pathlib import Path

import usb_monitor
from usb_monitor import (
    DRIVE_CDROM,
    DRIVE_FIXED,
    DRIVE_REMOTE,
    DRIVE_REMOVABLE,
    ES_LINUX,
    ES_MACOS,
    ES_WINDOWS,
    NOMBRE_PLATAFORMA,
    MonitorUSB,
    TipoUnidad,
    UnidadExtraible,
    normalizar_identificador_unidad,
    obtener_unidades_extraibles,
)

_SISTEMA = platform.system().lower()


class DeteccionPlataformaTests(unittest.TestCase):
    def test_existe_una_sola_plataforma_activa(self) -> None:
        marcas = [ES_WINDOWS, ES_MACOS, ES_LINUX]
        self.assertIn(sum(marcas), (0, 1), "Las banderas de plataforma deben ser excluyentes")
        if _SISTEMA.startswith("win"):
            self.assertTrue(ES_WINDOWS)
        elif _SISTEMA == "darwin":
            self.assertTrue(ES_MACOS)
        elif _SISTEMA == "linux":
            self.assertTrue(ES_LINUX)

    def test_nombre_plataforma_no_vacio(self) -> None:
        self.assertTrue(NOMBRE_PLATAFORMA)
        self.assertIsInstance(NOMBRE_PLATAFORMA, str)

    def test_es_windows_coincide_con_os_name(self) -> None:
        self.assertEqual(ES_WINDOWS, os.name == "nt")


class ModulosImportablesTests(unittest.TestCase):
    """Los módulos centrales no pueden depender de pywin32 fuera de Windows."""

    def test_modulos_centrales_importables(self) -> None:
        for nombre in ("logger", "usb_monitor", "repair_engine", "process_manager", "scraper"):
            with self.subTest(modulo=nombre):
                __import__(nombre)

    def test_main_importable_sin_ejecutar_elevacion(self) -> None:
        import main

        self.assertTrue(hasattr(main, "_verificar_admin"))
        self.assertIsInstance(main._verificar_admin(), bool)

    def test_backend_windows_no_se_carga_fuera_de_windows(self) -> None:
        """En macOS/Linux ``usb_monitor_windows`` jamás debe importarse."""
        if ES_WINDOWS:
            self.skipTest("Backend de Windows esperado en Windows")
        self.assertNotIn("usb_monitor_windows", sys.modules)
        self.assertIsNone(usb_monitor._backend_windows)

    def test_backend_windows_es_requerido_en_windows(self) -> None:
        if not ES_WINDOWS:
            self.skipTest("Solo aplica en Windows")
        backend = usb_monitor._windows()
        self.assertTrue(hasattr(backend, "obtener_unidades_extraibles"))


class NormalizacionIdentificadorTests(unittest.TestCase):
    def test_en_windows_normaliza_letras(self) -> None:
        if not ES_WINDOWS:
            self.skipTest("Solo aplica en Windows")
        for entrada in ("E", "E:", "E:\\", "e:", "e"):
            self.assertEqual(normalizar_identificador_unidad(entrada), "E:")

    def test_en_posix_conserva_el_punto_de_montaje(self) -> None:
        if ES_WINDOWS:
            self.skipTest("Solo aplica en macOS/Linux")
        self.assertEqual(normalizar_identificador_unidad("/Volumes/USB"), "/Volumes/USB")
        self.assertEqual(normalizar_identificador_unidad("/media/user/USB/"), "/media/user/USB")
        self.assertEqual(normalizar_identificador_unidad("/"), "/")
        # Recortar una ruta POSIX como si fuera una letra la corrompería.
        self.assertNotIn(":", normalizar_identificador_unidad("/media/user/USB"))

    def test_cadena_vacia(self) -> None:
        self.assertEqual(normalizar_identificador_unidad(""), "")
        self.assertEqual(normalizar_identificador_unidad("   "), "")

    def test_estado_de_unidades_reparadas_es_multiplataforma(self) -> None:
        identificador = "/Volumes/Prueba" if not ES_WINDOWS else "Z:"
        self.assertIsInstance(usb_monitor.es_unidad_reparada(identificador), bool)
        self.assertIsInstance(usb_monitor.obtener_unidades_reparadas(), list)


class ModeloUnidadTests(unittest.TestCase):
    def test_tipos_de_unidad_usan_la_escala_de_windows(self) -> None:
        self.assertEqual(TipoUnidad.EXTRAIBLE.value, DRIVE_REMOVABLE)
        self.assertEqual(TipoUnidad.FIJA.value, DRIVE_FIXED)
        self.assertEqual(TipoUnidad.RED.value, DRIVE_REMOTE)
        self.assertEqual(TipoUnidad.CD_ROM.value, DRIVE_CDROM)

    def test_solo_extraibles_y_usb_fisicos_son_reparables(self) -> None:
        extraible = UnidadExtraible(letra="E:", ruta_raiz="E:\\", tipo_drive=DRIVE_REMOVABLE)
        usb_fijo = UnidadExtraible(letra="F:", ruta_raiz="F:\\", tipo_drive=DRIVE_FIXED, es_usb_fisico=True)
        interno = UnidadExtraible(letra="C:", ruta_raiz="C:\\", tipo_drive=DRIVE_FIXED)
        red = UnidadExtraible(letra="Z:", ruta_raiz="Z:\\", tipo_drive=DRIVE_REMOTE)
        cd = UnidadExtraible(letra="D:", ruta_raiz="D:\\", tipo_drive=DRIVE_CDROM)

        self.assertTrue(extraible.es_reparable_con_seguridad)
        self.assertTrue(usb_fijo.es_reparable_con_seguridad)
        self.assertFalse(interno.es_reparable_con_seguridad)
        self.assertFalse(red.es_reparable_con_seguridad)
        self.assertFalse(cd.es_reparable_con_seguridad)

    def test_identidad_por_letra(self) -> None:
        a = UnidadExtraible(letra="E:", ruta_raiz="E:\\", etiqueta="UNO")
        b = UnidadExtraible(letra="E:", ruta_raiz="E:\\", etiqueta="DOS")
        self.assertEqual(a, b)
        self.assertEqual(len({a, b}), 1)
        self.assertNotEqual(a, "E:")


class EnumeracionTests(unittest.TestCase):
    def test_enumerar_no_lanza_excepciones(self) -> None:
        """En cualquier SO la enumeración degrada a lista vacía, nunca revienta."""
        unidades = obtener_unidades_extraibles()
        self.assertIsInstance(unidades, list)
        for unidad in unidades:
            self.assertIsInstance(unidad, UnidadExtraible)
            self.assertTrue(unidad.letra)
            self.assertTrue(unidad.ruta_raiz)

    def test_monitor_singleton(self) -> None:
        monitor = usb_monitor.obtener_monitor_usb()
        self.assertIsInstance(monitor, MonitorUSB)
        self.assertIs(monitor, usb_monitor.obtener_monitor_usb())

    def test_unidades_actuales_del_monitor(self) -> None:
        unidades = usb_monitor.obtener_monitor_usb().obtener_unidades_actuales()
        self.assertIsInstance(unidades, list)


class BackendLinuxTests(unittest.TestCase):
    """Cobertura del backend POSIX usando datos sintéticos."""

    def setUp(self) -> None:
        if not ES_LINUX:
            self.skipTest("Backend específico de Linux")

    def test_nombre_disco_base(self) -> None:
        casos = {
            "/dev/sdb1": "sdb",
            "/dev/sda": "sda",
            "/dev/nvme0n1p2": "nvme0n1",
            "/dev/mmcblk0p1": "mmcblk0",
        }
        for dispositivo, esperado in casos.items():
            with self.subTest(dispositivo=dispositivo):
                self.assertEqual(usb_monitor._nombre_disco_base(dispositivo), esperado)

    def test_fs_virtuales_excluidos(self) -> None:
        for fs in ("proc", "sysfs", "tmpfs", "cgroup2", "overlay", "squashfs"):
            self.assertIn(fs, usb_monitor._FS_VIRTUALES)

    def test_fs_de_red_clasificados_como_remotos(self) -> None:
        for fs in ("nfs", "nfs4", "cifs", "smb3"):
            self.assertIn(fs, usb_monitor._FS_RED)

    def test_disco_inexistente_no_es_usb(self) -> None:
        self.assertFalse(usb_monitor._es_usb_en_linux(""))
        self.assertFalse(usb_monitor._es_usb_en_linux("discoqueexiste9999"))


class BackendMacosTests(unittest.TestCase):
    def setUp(self) -> None:
        if not ES_MACOS:
            self.skipTest("Backend específico de macOS")

    def test_diskutil_no_disponible_devuelve_diccionario_vacio(self) -> None:
        info = usb_monitor._info_disco_macos(Path("/ruta/que/no/existe"))
        self.assertIsInstance(info, dict)

    def test_statvfs_devuelve_enteros(self) -> None:
        total, libre = usb_monitor._espacio_en_macos(Path("/"))
        self.assertIsInstance(total, int)
        self.assertIsInstance(libre, int)


class MotorReparacionMultiplataformaTests(unittest.TestCase):
    """El motor debe importarse y operar en los tres sistemas."""

    def test_motor_importable_sin_pywin32(self) -> None:
        import repair_engine

        motor = repair_engine.MotorReparacionUSB()
        self.assertEqual(motor.ARCHIVOS_VIRUS, ("5.dat", "6.dat", "7.dat"))
        self.assertTrue(motor.REQUIERE_ARCHIVO_NUMERICO)

    def test_sha256_funciona_en_la_plataforma_actual(self) -> None:
        import hashlib
        import tempfile

        import repair_engine

        motor = repair_engine.MotorReparacionUSB()
        with tempfile.TemporaryDirectory() as tmp:
            archivo = Path(tmp) / "datos.bin"
            contenido = b"contenido de prueba"
            archivo.write_bytes(contenido)
            self.assertEqual(
                motor._sha256(archivo), hashlib.sha256(contenido).hexdigest()
            )

    def test_sha256_de_archivo_inexistente_devuelve_none(self) -> None:
        import repair_engine

        motor = repair_engine.MotorReparacionUSB()
        self.assertIsNone(motor._sha256(Path("/no/existe/este/archivo.bin")))

    def test_sincronizar_a_disco_no_lanza(self) -> None:
        import tempfile

        import repair_engine

        motor = repair_engine.MotorReparacionUSB()
        with tempfile.TemporaryDirectory() as tmp:
            archivo = Path(tmp) / "salida.bin"
            archivo.write_bytes(b"datos")
            motor._sincronizar_a_disco(archivo)  # no debe propagar OSError
            self.assertTrue(archivo.is_file())

    def test_gestor_procesos_instanciable(self) -> None:
        from process_manager import GestorProcesosEA

        gestor = GestorProcesosEA()
        self.assertIsInstance(gestor._obtener_propietario(str(Path(__file__))), str)
        # Los servicios Win32 no aplican fuera de Windows.
        if not ES_WINDOWS:
            self.assertEqual(gestor._verificar_si_es_servicio("/bin/ls"), "")


class SimulacionWindowsTests(unittest.TestCase):
    """Ejercita la rama de Windows aunque el CI corra en Ubuntu o macOS.

    Se parchean las banderas de plataforma para validar que la normalización de
    letras de unidad y de rutas completas es correcta en Windows.
    """

    def setUp(self) -> None:
        import repair_engine

        self.repair_engine = repair_engine
        self._win_monitor = usb_monitor.ES_WINDOWS
        self._win_motor = repair_engine.ES_WINDOWS
        usb_monitor.ES_WINDOWS = True
        repair_engine.ES_WINDOWS = True

    def tearDown(self) -> None:
        usb_monitor.ES_WINDOWS = self._win_monitor
        self.repair_engine.ES_WINDOWS = self._win_motor

    def test_letras_de_unidad_se_canonicalizan(self) -> None:
        motor = self.repair_engine.MotorReparacionUSB()
        for entrada in ("E", "E:", "E:\\", "e", "e:", "e:\\"):
            with self.subTest(entrada=entrada):
                self.assertEqual(motor._ruta_desde_unidad(entrada), "E:\\")

    def test_rutas_completas_de_windows_no_se_recortan(self) -> None:
        motor = self.repair_engine.MotorReparacionUSB()
        ruta = "C:\\Archivos de programa\\Electronic Arts"
        self.assertEqual(motor._ruta_desde_unidad(ruta), ruta)

    def test_normalizador_de_letras_en_windows(self) -> None:
        for entrada in ("E", "E:", "E:\\", "e", "e:"):
            with self.subTest(entrada=entrada):
                self.assertEqual(normalizar_identificador_unidad(entrada), "E:")

    def test_normalizador_no_toca_rutas_completas(self) -> None:
        self.assertEqual(
            normalizar_identificador_unidad("C:\\Users\\usuario"), "C:\\Users\\usuario"
        )


class SimulacionPosixTests(unittest.TestCase):
    """Ejercita la rama POSIX aunque el CI corra en Windows."""

    def setUp(self) -> None:
        import repair_engine

        self.repair_engine = repair_engine
        self._win_monitor = usb_monitor.ES_WINDOWS
        self._win_motor = repair_engine.ES_WINDOWS
        usb_monitor.ES_WINDOWS = False
        repair_engine.ES_WINDOWS = False

    def tearDown(self) -> None:
        usb_monitor.ES_WINDOWS = self._win_monitor
        self.repair_engine.ES_WINDOWS = self._win_motor

    def test_puntos_de_montaje_no_se_corrompen(self) -> None:
        motor = self.repair_engine.MotorReparacionUSB()
        for ruta in ("/media/usuario/USB", "/Volumes/USB", "/mnt/usb"):
            with self.subTest(ruta=ruta):
                self.assertEqual(motor._ruta_desde_unidad(ruta), ruta)
                self.assertEqual(normalizar_identificador_unidad(ruta), ruta)

    def test_raiz_posix_se_conserva(self) -> None:
        self.assertEqual(normalizar_identificador_unidad("/"), "/")
        self.assertEqual(self.repair_engine.MotorReparacionUSB()._ruta_desde_unidad("/"), "/")


if __name__ == "__main__":
    unittest.main()
