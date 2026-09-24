"""Pruebas del motor de reparación conservadora.

Se ejecutan con la biblioteca estándar y no requieren una unidad USB real.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from repair_engine import EstadoDeteccion, EstadoReparacion, MotorReparacionUSB


class MotorReparacionUSBTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directorio_temporal = tempfile.TemporaryDirectory()
        self.raiz = Path(self.directorio_temporal.name)
        self.motor = MotorReparacionUSB()

    def tearDown(self) -> None:
        self.directorio_temporal.cleanup()

    def _crear_firma(self, archivos: tuple[str, ...] = ("3.dat", "4.dat", "5.dat", "6.dat", "7.dat")) -> Path:
        base = self.raiz / "Kaspersky" / "Usb Drive" / "3.0"
        base.mkdir(parents=True)
        for nombre in archivos:
            (base / nombre).write_text("firma", encoding="utf-8")
        return base

    def test_unidad_sin_estructura_es_limpia(self) -> None:
        diagnostico = self.motor.analizar_ruta(self.raiz)

        self.assertEqual(diagnostico.estado, EstadoDeteccion.LIMPIA)
        resultado = self.motor.reparar_ruta(self.raiz)
        self.assertEqual(resultado.estado, EstadoReparacion.SIN_INFECCION)

    def test_firma_incompleta_no_modifica_archivos(self) -> None:
        self._crear_firma(("3.dat",))
        archivo_usuario = self.raiz / "Kaspersky" / "Usb Drive" / "foto.jpg"
        archivo_usuario.write_text("foto", encoding="utf-8")

        diagnostico = self.motor.analizar_ruta(self.raiz)
        resultado = self.motor.reparar_ruta(self.raiz)

        self.assertEqual(diagnostico.estado, EstadoDeteccion.SOSPECHOSA)
        self.assertEqual(resultado.estado, EstadoReparacion.REQUIERE_REVISION)
        self.assertTrue(archivo_usuario.exists())
        self.assertTrue((self.raiz / "Kaspersky").exists())

    def test_repara_solo_tras_firma_completa_y_resuelve_colisiones(self) -> None:
        self._crear_firma()
        origen = self.raiz / "Kaspersky" / "Usb Drive"
        (origen / "documento.txt").write_text("original", encoding="utf-8")
        (self.raiz / "documento.txt").write_text("existente", encoding="utf-8")
        (origen / "carpeta").mkdir()
        (origen / "carpeta" / "nota.txt").write_text("nota", encoding="utf-8")

        resultado = self.motor.reparar_ruta(self.raiz)

        self.assertEqual(resultado.estado, EstadoReparacion.COMPLETADO)
        self.assertEqual((self.raiz / "documento.txt").read_text(encoding="utf-8"), "existente")
        self.assertEqual((self.raiz / "documento_1.txt").read_text(encoding="utf-8"), "original")
        self.assertTrue((self.raiz / "carpeta" / "nota.txt").is_file())
        self.assertFalse((self.raiz / "Kaspersky").exists())
        self.assertEqual(len(resultado.archivos_eliminados), 5)

    def test_conserva_contenido_no_reconocido_en_lugar_de_borrarlo(self) -> None:
        base = self._crear_firma()
        desconocido = base / "conservar.bin"
        desconocido.write_bytes(b"no borrar")

        resultado = self.motor.reparar_ruta(self.raiz)

        self.assertEqual(resultado.estado, EstadoReparacion.COMPLETADO_CON_ERRORES)
        self.assertTrue(desconocido.exists())
        self.assertTrue(any("no reconocidos" in error for error in resultado.errores))


if __name__ == "__main__":
    unittest.main()
