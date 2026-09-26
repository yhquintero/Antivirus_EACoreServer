"""Prueba de humo de la interfaz gráfica.

Estas pruebas construyen la ventana de verdad y ejercitan el sistema de temas
completo. Como requieren un entorno gráfico, se omiten automáticamente cuando
no hay tkinter o no hay pantalla disponible; en el CI de Linux se ejecutan bajo
Xvfb y en Windows y macOS directamente.

Lo que protegen: que ninguna combinación de paleta, acento y tamaño de letra
lance una excepción, que todas las pestañas existan y que la leyenda de estados
tenga color asignado en la tabla.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

RAIZ = Path(__file__).resolve().parent.parent

try:
    import tkinter as tk
    from tkinter import ttk

    TKINTER_DISPONIBLE = True
except Exception:                                     # pragma: no cover
    tk = None                                         # type: ignore[assignment]
    ttk = None                                        # type: ignore[assignment]
    TKINTER_DISPONIBLE = False

if TKINTER_DISPONIBLE:
    import ayuda
    import gui
    import temas
    import usb_monitor


def _hay_pantalla() -> bool:
    """Comprueba si se puede crear una ventana en este entorno."""
    if not TKINTER_DISPONIBLE:
        return False
    try:
        raiz = tk.Tk()
    except Exception:
        return False
    raiz.destroy()
    return True


@unittest.skipUnless(_hay_pantalla(),
                     "se necesita tkinter y una pantalla (use xvfb-run en Linux)")
class TestConstruccionDeLaInterfaz(unittest.TestCase):
    """La ventana debe construirse completa y sin diálogos bloqueantes."""

    @classmethod
    def setUpClass(cls):
        cls._temporal = tempfile.TemporaryDirectory()
        cls._config = Path(cls._temporal.name) / "config.json"

        # Nada de diálogos modales: se registran en vez de mostrarse.
        cls._parches = [
            mock.patch.object(gui, "_ARCHIVO_CONFIG", cls._config),
            mock.patch.object(gui.messagebox, "showinfo"),
            mock.patch.object(gui.messagebox, "showerror"),
            mock.patch.object(gui.messagebox, "showwarning"),
            mock.patch.object(gui.messagebox, "askyesno", return_value=False),
        ]
        cls.dialogos = {}
        for parche in cls._parches:
            obj = parche.start()
            if parche.attribute in ("showinfo", "showerror", "showwarning", "askyesno"):
                cls.dialogos[parche.attribute] = obj

        cls.raiz = tk.Tk()
        cls.raiz.withdraw()          # no molestar en pantallas reales
        cls.app = gui.AntivirusGUI(cls.raiz)

    @classmethod
    def tearDownClass(cls):
        try:
            usb_monitor.obtener_monitor_usb().detener()
        except Exception:
            pass
        try:
            cls.raiz.destroy()
        except Exception:
            pass
        for parche in reversed(cls._parches):
            parche.stop()
        cls._temporal.cleanup()

    # -- estructura ---------------------------------------------------------
    def test_las_cuatro_pestanas_existen(self):
        for atributo in ("tab_procesos", "tab_usb", "tab_log", "tab_ayuda"):
            self.assertTrue(hasattr(self.app, atributo), atributo)

    def test_el_orden_de_las_pestanas_es_el_esperado(self):
        # Ayuda va al final: la pestaña de trabajo no debe quedar desplazada.
        textos = [self.app.notebook.tab(pestana, "text").strip()
                  for pestana in self.app.notebook.tabs()]
        self.assertEqual(len(textos), 4)
        self.assertIn("Procesos", textos[0])
        self.assertIn("Unidades", textos[1])
        self.assertEqual(textos[2].lower(), "log")
        self.assertIn("Ayuda", textos[3])

    def test_la_pestana_activa_inicial_es_la_de_procesos(self):
        self.assertEqual(self.app.notebook.select(), str(self.app.tab_procesos))

    def test_la_barra_de_estado_muestra_el_sistema_detectado(self):
        self.assertTrue(hasattr(self.app, "lbl_plataforma"))
        texto = self.app.lbl_plataforma.cget("text")
        self.assertIn("·", texto)
        self.assertIn("soporte", texto)

    def test_hay_botones_de_ayuda_accesibles(self):
        self.assertTrue(hasattr(self.app, "btn_ayuda"))
        self.assertIn("Ayuda", self.app.btn_ayuda.cget("text"))

    # -- contenido de la ayuda ---------------------------------------------
    def test_la_pestana_ayuda_tiene_contenido_volcado(self):
        contenido = self.app.ayuda_text.get("1.0", "end")
        self.assertGreater(len(contenido.strip()), 500)
        # Debe explicar la firma del malware y los pasos.
        self.assertIn("Kaspersky", contenido)
        self.assertIn("5.dat", contenido)

    def test_abrir_guia_selecciona_la_pestana_de_ayuda(self):
        self.app.notebook.select(self.app.tab_procesos)
        self.app._abrir_guia()
        self.assertEqual(self.app.notebook.select(), str(self.app.tab_ayuda))

    def test_cada_estado_de_la_leyenda_tiene_color_en_la_tabla(self):
        for clave in ayuda.claves_estado():
            tag = ayuda.tag_estado(clave)
            if not tag:
                continue
            fondo = self.app.tree_usb.tag_configure(tag, "background")
            self.assertTrue(fondo, f"el tag {tag!r} del estado {clave!r} no tiene fondo")

    # -- tooltips -----------------------------------------------------------
    def test_los_tooltips_quedan_registrados(self):
        self.assertTrue(getattr(self.app, "_tooltips", None),
                        "ningún control tiene ayuda emergente asociada")

    def test_los_tooltips_tienen_texto_y_colores(self):
        for tooltip in self.app._tooltips:
            self.assertTrue(str(tooltip.texto).strip())
            fondo, frente, borde = tooltip.colores
            for color in (fondo, frente, borde):
                self.assertTrue(temas.es_color_valido(color))

    # -- temas --------------------------------------------------------------
    def test_todas_las_paletas_se_aplican_sin_excepcion(self):
        for nombre in list(temas.PALETAS) + ["sistema"]:
            with self.subTest(tema=nombre):
                self.app._aplicar_tema(nombre)
                self.raiz.update_idletasks()
                self.assertTrue(self.app._paleta_actual())

    def test_todos_los_acentos_sugeridos_se_aplican(self):
        for acento in temas.ACENTOS_SUGERIDOS:
            with self.subTest(acento=acento):
                self.app._aplicar_acento(acento)
                self.raiz.update_idletasks()
                self.assertEqual(self.app._paleta_actual()["acento"], acento)

    def test_todas_las_escalas_se_aplican(self):
        for escala in temas.ESCALAS_FUENTE:
            with self.subTest(escala=escala):
                self.app._aplicar_escala(escala)
                self.raiz.update_idletasks()

    def test_la_combinacion_mas_extrema_no_rompe(self):
        self.app._aplicar_tema("claro")
        self.app._aplicar_acento("#ffeb3b")     # amarillo: el peor caso de contraste
        self.app._aplicar_escala("enorme")
        self.raiz.update_idletasks()
        paleta = self.app._paleta_actual()
        # El texto sobre un acento amarillo debe ser negro, no blanco.
        self.assertEqual(paleta["texto_sobre_acento"], "#000000")

    def test_el_fondo_de_la_ventana_sigue_a_la_paleta(self):
        for nombre in ("oscuro", "claro", "contraste"):
            with self.subTest(tema=nombre):
                self.app._aplicar_tema(nombre)
                esperado = temas.construir_paleta(nombre)["bg"]
                self.assertEqual(self.raiz.cget("bg"), esperado)

    def test_restablecer_apariencia_vuelve_a_los_valores_por_defecto(self):
        self.app._aplicar_tema("esmeralda")
        self.app._aplicar_acento("#ff00ff")
        self.app._aplicar_escala("enorme")
        self.app._restablecer_apariencia()
        self.raiz.update_idletasks()
        self.assertEqual(self.app._tema_seleccion, temas.PALETA_POR_DEFECTO)
        self.assertIn(self.app._escala_seleccion, temas.ESCALAS_FUENTE)

    def test_la_apariencia_se_persiste_en_config(self):
        self.app._aplicar_tema("azul")
        self.app._aplicar_escala("grande")
        self.assertTrue(self._config.exists(), "no se escribió config.json")
        import json
        datos = json.loads(self._config.read_text(encoding="utf-8"))
        self.assertEqual(datos.get("tema"), "azul")
        self.assertEqual(datos.get("escala_letra"), "grande")

    # -- bienvenida ---------------------------------------------------------
    def test_la_bienvenida_se_muestra_una_sola_vez(self):
        import json
        self.assertFalse(json.loads(self._config.read_text(encoding="utf-8"))
                         .get("bienvenida_vista", False),
                         "la bienvenida ya estaba marcada antes de pedirlo")
        self.app._mostrar_bienvenida()
        self.dialogos["showinfo"].assert_called()
        datos = json.loads(self._config.read_text(encoding="utf-8"))
        self.assertTrue(datos.get("bienvenida_vista"))

        self.dialogos["showinfo"].reset_mock()
        self.app._mostrar_bienvenida()
        self.dialogos["showinfo"].assert_not_called()

    def test_el_texto_de_bienvenida_explica_las_tres_funciones(self):
        import json
        config = json.loads(self._config.read_text(encoding="utf-8"))
        config.pop("bienvenida_vista", None)
        gui._guardar_config(config)

        self.dialogos["showinfo"].reset_mock()
        self.app._mostrar_bienvenida()
        mensaje = self.dialogos["showinfo"].call_args[0][1]
        for esperado in ("USB", "EACoreServer", "SHA-256", "F1"):
            self.assertIn(esperado, mensaje, esperado)

    def test_comprobar_compatibilidad_abre_un_dialogo(self):
        self.dialogos["showinfo"].reset_mock()
        self.app._mostrar_compatibilidad()
        self.dialogos["showinfo"].assert_called()
        mensaje = self.dialogos["showinfo"].call_args[0][1]
        self.assertTrue(mensaje.strip())

    def test_exportar_guia_escribe_un_archivo(self):
        destino = Path(self._temporal.name) / "guia.txt"
        with mock.patch.object(gui.filedialog, "asksaveasfilename",
                               return_value=str(destino)):
            self.app._exportar_guia()
        self.assertTrue(destino.exists())
        self.assertGreater(len(destino.read_text(encoding="utf-8").strip()), 500)


@unittest.skipUnless(TKINTER_DISPONIBLE, "tkinter no está instalado")
class TestUtilidadesDeModulo(unittest.TestCase):
    """Funciones de módulo que no necesitan ventana construida."""

    def test_apariencia_guardada_devuelve_valores_validos(self):
        with tempfile.TemporaryDirectory() as carpeta:
            config = Path(carpeta) / "config.json"
            with mock.patch.object(gui, "_ARCHIVO_CONFIG", config):
                # Sin archivo: valores por defecto válidos.
                por_defecto = gui._apariencia_guardada()
                self.assertIn(por_defecto["tema"], list(temas.PALETAS) + ["sistema"])
                self.assertIn(por_defecto["escala"], temas.ESCALAS_FUENTE)
                self.assertIsNone(por_defecto["acento"])

                # Con valores guardados correctos: se respetan.
                gui._guardar_config({"tema": "esmeralda", "acento": "#0f9d6e",
                                     "escala_letra": "grande"})
                guardada = gui._apariencia_guardada()
                self.assertEqual(guardada["tema"], "esmeralda")
                self.assertEqual(guardada["acento"], "#0f9d6e")
                self.assertEqual(guardada["escala"], "grande")

    def test_apariencia_guardada_sobrevive_a_config_corrupta(self):
        with tempfile.TemporaryDirectory() as carpeta:
            config = Path(carpeta) / "config.json"
            config.write_text("{ esto no es json", encoding="utf-8")
            with mock.patch.object(gui, "_ARCHIVO_CONFIG", config):
                apariencia = gui._apariencia_guardada()
            self.assertIn(apariencia["tema"], list(temas.PALETAS) + ["sistema"])

    def test_apariencia_guardada_rechaza_valores_desconocidos(self):
        with tempfile.TemporaryDirectory() as carpeta:
            config = Path(carpeta) / "config.json"
            with mock.patch.object(gui, "_ARCHIVO_CONFIG", config):
                gui._guardar_config({"tema": "neon", "acento": "rojo",
                                     "escala_letra": "gigante"})
                apariencia = gui._apariencia_guardada()
            self.assertEqual(apariencia["tema"], temas.PALETA_POR_DEFECTO)
            self.assertIsNone(apariencia["acento"])
            self.assertEqual(apariencia["escala"], temas.ESCALA_POR_DEFECTO)

    def test_el_color_inicial_de_ventana_es_un_color_de_paleta(self):
        for nombre in ("oscuro", "claro", "contraste"):
            with tempfile.TemporaryDirectory() as carpeta:
                config = Path(carpeta) / "config.json"
                with mock.patch.object(gui, "_ARCHIVO_CONFIG", config):
                    gui._guardar_config({"tema": nombre})
                    apariencia = gui._apariencia_guardada()
                    paleta = temas.construir_paleta(apariencia["tema"],
                                                     apariencia["acento"])
                    self.assertEqual(paleta["bg"],
                                     temas.PALETAS[nombre]["bg"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
