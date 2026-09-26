"""Pruebas de la lista local de rutas históricas de EACoreServer.exe.

La lista de respaldo debe contener exactamente 52 rutas únicas, sin duplicados
ni siquiera insensibles a mayúsculas, y todas deben apuntar a EACoreServer.exe.
"""

from __future__ import annotations

import re
import unittest

from scraper import (
    ScraperEACoreServer,
    cantidad_rutas_por_defecto,
    obtener_rutas_por_defecto,
)

CANTIDAD_ESPERADA = 52
PATRON_RUTA = re.compile(
    r"[A-Za-z]:\\(?:[^\\/:*?\"<>|\r\n]+\\)*EACoreServer\.exe",
    re.IGNORECASE,
)


class RutasPorDefectoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rutas = obtener_rutas_por_defecto()

    def test_hay_exactamente_52_rutas(self) -> None:
        self.assertEqual(len(self.rutas), CANTIDAD_ESPERADA)
        self.assertEqual(cantidad_rutas_por_defecto(), CANTIDAD_ESPERADA)

    def test_no_hay_duplicados(self) -> None:
        """Ni duplicados exactos ni duplicados que difieran solo en mayúsculas."""
        minusculas = [ruta.lower() for ruta in self.rutas]
        self.assertEqual(len(set(minusculas)), CANTIDAD_ESPERADA)
        self.assertEqual(len(set(self.rutas)), CANTIDAD_ESPERADA)

    def test_lista_literal_tampoco_tiene_duplicados(self) -> None:
        """Detecta que alguien añada una entrada repetida al código fuente."""
        literal = ScraperEACoreServer._rutas_base()
        self.assertEqual(len(literal), len({r.lower() for r in literal}))

    def test_todas_apuntan_a_eacoreserver_exe(self) -> None:
        for ruta in self.rutas:
            with self.subTest(ruta=ruta):
                self.assertRegex(ruta, PATRON_RUTA)
                self.assertTrue(ruta.lower().endswith("eacoreserver.exe"))

    def test_rutas_sin_espacios_al_inicio_ni_al_final(self) -> None:
        for ruta in self.rutas:
            self.assertEqual(ruta, ruta.strip())

    def test_incluye_la_ruta_del_servicio_en_programdata(self) -> None:
        """La ruta #52 es el servicio instalado en ProgramData."""
        self.assertIn(r"C:\ProgramData\EACoreService\EACoreServer.exe", self.rutas)
        self.assertEqual(
            self.rutas[-1], r"C:\ProgramData\EACoreService\EACoreServer.exe"
        )

    def test_deduplicacion_al_fusionar_con_rutas_remotas(self) -> None:
        """Una ruta remota repetida no aumenta el total."""
        scraper = ScraperEACoreServer()
        remota_duplicada = self.rutas[0].upper()
        fusion = scraper._fusionar_con_defecto([remota_duplicada])

        self.assertEqual(len(fusion), CANTIDAD_ESPERADA)
        self.assertEqual(len({r.lower() for r in fusion}), CANTIDAD_ESPERADA)

    def test_fusion_con_ruta_nueva_la_anade_una_sola_vez(self) -> None:
        scraper = ScraperEACoreServer()
        nueva = r"Z:\Juegos\Battlefield 3\Core\EACoreServer.exe"
        fusion = scraper._fusionar_con_defecto([nueva, nueva])

        self.assertEqual(len(fusion), CANTIDAD_ESPERADA + 1)
        self.assertEqual(fusion.count(nueva), 1)

    def test_validacion_rechaza_texto_que_no_es_una_ruta(self) -> None:
        scraper = ScraperEACoreServer()
        self.assertFalse(scraper._es_ruta_valida("EACoreServer.exe"))
        self.assertFalse(scraper._es_ruta_valida("C:\\Program Files\\otro.exe"))
        self.assertFalse(scraper._es_ruta_valida(
            "La ruta es C:\\Program Files\\Electronic Arts\\EADM\\EACoreServer.exe."
        ))
        self.assertTrue(scraper._es_ruta_valida(
            r"C:\Program Files\Electronic Arts\EADM\EACoreServer.exe"
        ))


if __name__ == "__main__":
    unittest.main()
