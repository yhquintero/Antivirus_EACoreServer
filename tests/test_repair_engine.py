"""Pruebas del motor de reparación conservadora.

Se ejecutan con la biblioteca estándar y no requieren una unidad USB real.
Cubren la firma exacta (5.dat, 6.dat, 7.dat + fichero numérico sin extensión),
la restauración verificada por SHA-256 y la conservación de contenido ajeno.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from repair_engine import EstadoDeteccion, EstadoReparacion, MotorReparacionUSB
from usb_monitor import ES_WINDOWS

# Firma exacta atendida por el motor.
ARCHIVOS_DAT = ("5.dat", "6.dat", "7.dat")
ARCHIVO_NUMERICO = "1337"


class MotorReparacionUSBTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directorio_temporal = tempfile.TemporaryDirectory()
        self.raiz = Path(self.directorio_temporal.name)
        self.motor = MotorReparacionUSB()

    def tearDown(self) -> None:
        self.directorio_temporal.cleanup()

    def _crear_firma(
        self,
        archivos: tuple[str, ...] = ARCHIVOS_DAT,
        numericos: tuple[str, ...] = (ARCHIVO_NUMERICO,),
    ) -> Path:
        base = self.raiz / "Kaspersky" / "Usb Drive" / "3.0"
        base.mkdir(parents=True, exist_ok=True)
        for nombre in archivos:
            (base / nombre).write_text("firma", encoding="utf-8")
        # El fichero numérico no lleva extensión: es parte de la firma exacta.
        for nombre in numericos:
            (base / nombre).write_text("indice", encoding="utf-8")
        return base

    def test_unidad_sin_estructura_es_limpia(self) -> None:
        diagnostico = self.motor.analizar_ruta(self.raiz)

        self.assertEqual(diagnostico.estado, EstadoDeteccion.LIMPIA)
        resultado = self.motor.reparar_ruta(self.raiz)
        self.assertEqual(resultado.estado, EstadoReparacion.SIN_INFECCION)

    def test_firma_incompleta_no_modifica_archivos(self) -> None:
        self._crear_firma(("5.dat",))
        archivo_usuario = self.raiz / "Kaspersky" / "Usb Drive" / "foto.jpg"
        archivo_usuario.write_text("foto", encoding="utf-8")

        diagnostico = self.motor.analizar_ruta(self.raiz)
        resultado = self.motor.reparar_ruta(self.raiz)

        self.assertEqual(diagnostico.estado, EstadoDeteccion.SOSPECHOSA)
        self.assertEqual(resultado.estado, EstadoReparacion.REQUIERE_REVISION)
        self.assertTrue(archivo_usuario.exists())
        self.assertTrue((self.raiz / "Kaspersky").exists())

    def test_dat_completos_sin_fichero_numerico_es_sospechoso(self) -> None:
        """Los .dat solos no bastan: falta el fichero numérico sin extensión."""
        self._crear_firma(numericos=())
        archivo_usuario = self.raiz / "Kaspersky" / "Usb Drive" / "trabajo.docx"
        archivo_usuario.write_text("importante", encoding="utf-8")

        diagnostico = self.motor.analizar_ruta(self.raiz)
        resultado = self.motor.reparar_ruta(self.raiz)

        self.assertEqual(diagnostico.estado, EstadoDeteccion.SOSPECHOSA)
        self.assertEqual(diagnostico.archivos_firma, ARCHIVOS_DAT)
        self.assertEqual(diagnostico.archivos_numericos, ())
        self.assertEqual(resultado.estado, EstadoReparacion.REQUIERE_REVISION)
        self.assertIn("fichero numérico", diagnostico.detalle)
        self.assertTrue(archivo_usuario.exists())

    def test_directorio_numerico_no_cuenta_como_firma(self) -> None:
        """Una carpeta llamada 1234 no es un fichero de firma."""
        base = self._crear_firma(numericos=())
        (base / "1234").mkdir()

        diagnostico = self.motor.analizar_ruta(self.raiz)

        self.assertEqual(diagnostico.estado, EstadoDeteccion.SOSPECHOSA)
        self.assertEqual(diagnostico.archivos_numericos, ())

    def test_firma_exacta_se_confirma_con_numericos_sin_extension(self) -> None:
        base = self._crear_firma(numericos=("1337", "20240517"))

        diagnostico = self.motor.analizar_ruta(self.raiz)

        self.assertEqual(diagnostico.estado, EstadoDeteccion.CONFIRMADA)
        self.assertTrue(diagnostico.confirmada)
        self.assertEqual(diagnostico.archivos_firma, ARCHIVOS_DAT)
        self.assertEqual(diagnostico.archivos_numericos, ("1337", "20240517"))
        self.assertEqual(len(diagnostico.firma_completa), 5)
        self.assertTrue(base.is_dir())

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
        # 5.dat, 6.dat, 7.dat + el fichero numérico 1337.
        self.assertEqual(len(resultado.archivos_eliminados), 4)
        self.assertFalse(any(nombre in resultado.archivos_eliminados
                             for nombre in ("documento.txt", "nota.txt")))

    def test_restauracion_verifica_sha256_antes_de_retirar_origen(self) -> None:
        """Cada archivo restaurado queda auditado con su SHA-256."""
        import hashlib

        self._crear_firma()
        origen = self.raiz / "Kaspersky" / "Usb Drive"
        contenido = "datos del usuario"
        (origen / "informe.pdf").write_text(contenido, encoding="utf-8")
        suma_esperada = hashlib.sha256(contenido.encode("utf-8")).hexdigest()

        resultado = self.motor.reparar_ruta(self.raiz)

        self.assertEqual(resultado.estado, EstadoReparacion.COMPLETADO)
        restaurado = self.raiz / "informe.pdf"
        self.assertEqual(restaurado.read_text(encoding="utf-8"), contenido)
        self.assertEqual(resultado.sumas_sha256.get(str(restaurado)), suma_esperada)
        self.assertEqual(len(resultado.sumas_sha256), resultado.archivos_movidos)
        # El origen solo se retira después de verificar la copia.
        self.assertFalse((origen / "informe.pdf").exists())

    def test_copia_corrupta_conserva_el_archivo_original(self) -> None:
        """Si el SHA-256 no coincide, no se retira el origen."""
        self._crear_firma()
        origen = self.raiz / "Kaspersky" / "Usb Drive"
        (origen / "foto.jpg").write_bytes(b"imagen original intacta")

        def copiar_corrupta(src, dst, **kwargs):
            Path(dst).write_bytes(b"bits danados por el medio")

        with mock.patch("repair_engine.shutil.copy2", side_effect=copiar_corrupta):
            resultado = self.motor.reparar_ruta(self.raiz)

        self.assertTrue((origen / "foto.jpg").exists())
        self.assertEqual((origen / "foto.jpg").read_bytes(), b"imagen original intacta")
        self.assertTrue(any("SHA-256" in error for error in resultado.errores))
        self.assertNotEqual(resultado.estado, EstadoReparacion.COMPLETADO)
        self.assertNotIn(str(self.raiz / "foto.jpg"), resultado.sumas_sha256)

    def test_conserva_contenido_no_reconocido_en_lugar_de_borrarlo(self) -> None:
        base = self._crear_firma()
        desconocido = base / "conservar.bin"
        desconocido.write_bytes(b"no borrar")

        resultado = self.motor.reparar_ruta(self.raiz)

        self.assertEqual(resultado.estado, EstadoReparacion.COMPLETADO_CON_ERRORES)
        self.assertTrue(desconocido.exists())
        self.assertTrue(any("no reconocidos" in error for error in resultado.errores))

    def test_enlace_simbolico_no_se_sigue_ni_se_copia(self) -> None:
        """Un symlink dentro del USB no puede usarse para escribir fuera de él."""
        self._crear_firma()
        origen = self.raiz / "Kaspersky" / "Usb Drive"
        fuera = self.raiz.parent / "objetivo_fuera_del_usb.txt"
        try:
            enlace = origen / "enlace"
            enlace.symlink_to(fuera, target_is_directory=False)
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("El sistema de ficheros no permite enlaces simbólicos")

        resultado = self.motor.reparar_ruta(self.raiz)

        self.assertTrue(any("Enlace simbólico" in error for error in resultado.errores))
        self.assertTrue(enlace.is_symlink())

    def test_ruta_desde_unidad_segun_plataforma(self) -> None:
        """En Windows normaliza letras; en macOS/Linux conserva la ruta de montaje."""
        self._crear_firma()

        if ES_WINDOWS:
            self.assertEqual(self.motor._ruta_desde_unidad("E"), "E:\\")
            self.assertEqual(self.motor._ruta_desde_unidad("E:"), "E:\\")
            self.assertEqual(self.motor._ruta_desde_unidad("E:\\"), "E:\\")
        else:
            # Aplicar el recorte de letras a una ruta POSIX la corrompería.
            punto_montaje = str(self.raiz)
            self.assertEqual(self.motor._ruta_desde_unidad(punto_montaje), punto_montaje)
            self.assertEqual(Path(self.motor._ruta_desde_unidad(punto_montaje)), self.raiz)

        diagnostico = self.motor.analizar_ruta(self.raiz)
        self.assertEqual(diagnostico.estado, EstadoDeteccion.CONFIRMADA)


if __name__ == "__main__":
    unittest.main()
