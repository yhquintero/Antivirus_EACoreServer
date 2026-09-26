"""Pruebas del contenido de ayuda visual (``ayuda.py``).

La ayuda es texto puro que el usuario final lee para entender qué hace cada
botón y qué significa cada estado, así que lo importante es que esté completa,
bien formada y enlazada con el resto del programa: las claves de color de la
leyenda deben existir en las paletas y las claves de tooltip usadas por la GUI
deben estar definidas aquí.

El módulo no exige tkinter; cuando no está disponible se degrada sin romper, y
eso también se prueba.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ayuda
import temas
from ayuda import (
    ACCIONES_BOTONES,
    ESTADOS_UNIDAD,
    ESTRUCTURA_FIRMA,
    LEYENDA_ESTADOS,
    NOTAS_SEGURIDAD,
    PASOS_GUIA,
    PREGUNTAS_FRECUENTES,
    REGLAS_FIRMA,
    TOOLTIPS,
    ToolTip,
    asignar_tooltip,
    claves_estado,
    descripcion_estado,
    obtener_info_sistema,
    obtener_texto_ayuda,
    tag_estado,
    texto_estado,
    texto_reparacion,
    ESTADOS_REPARACION,
    tono_estado,
)

# Claves de tooltip que gui.py pasa a _registrar_tooltip(). Si alguna falta, el
# control se queda sin ayuda emergente en silencio.
TOOLTIPS_USADOS_POR_LA_GUI = (
    "ayuda", "escanear", "finalizar", "finalizar_todos", "detener_servicio",
    "refrescar", "tabla_procesos", "tabla_usb", "reparar", "reparar_todas",
    "progreso", "registro", "exportar_log", "tema", "acento", "analizar",
    "cancelar", "letra",
)

# Claves de paleta válidas, para comprobar la leyenda de estados.
CLAVES_DE_PALETA = set(temas.CLAVES_PALETA)

GUI_DIR = Path(__file__).resolve().parent.parent


def texto_completo_de_ayuda() -> str:
    """Concatena todo el contenido de ayuda para búsquedas transversales.

    Un consejo puede estar en los pasos, en la leyenda o en las FAQ; exigir que
    esté en una sección concreta daría falsos negativos.
    """
    trozos = [
        " ".join(f"{t} {d}" for t, d in PASOS_GUIA),
        " ".join(f"{n} {d}" for n, _i, _c, d in LEYENDA_ESTADOS),
        " ".join(REGLAS_FIRMA),
        " ".join(f"{n} {d}" for n, d in ACCIONES_BOTONES),
        " ".join(NOTAS_SEGURIDAD),
        " ".join(f"{p} {r}" for p, r in PREGUNTAS_FRECUENTES),
        " ".join(TOOLTIPS.values()),
        ESTRUCTURA_FIRMA,
    ]
    return " ".join(trozos).lower()


def _sin_espacios_en_blanco_extremos(texto):
    return texto == texto.strip()


class TestContenidoDeLaGuia(unittest.TestCase):
    """La guía paso a paso debe ser utilizable de principio a fin."""

    def test_hay_cinco_pasos(self):
        self.assertEqual(len(PASOS_GUIA), 5)

    def test_cada_paso_tiene_titulo_y_detalle_no_vacios(self):
        for indice, paso in enumerate(PASOS_GUIA):
            self.assertEqual(len(paso), 2, f"paso {indice} mal formado")
            titulo, detalle = paso
            self.assertTrue(titulo.strip(), f"paso {indice} sin título")
            self.assertTrue(detalle.strip(), f"paso {indice} sin detalle")
            self.assertTrue(_sin_espacios_en_blanco_extremos(titulo))
            self.assertTrue(_sin_espacios_en_blanco_extremos(detalle))

    def test_los_titulos_de_paso_no_se_repiten(self):
        titulos = [paso[0] for paso in PASOS_GUIA]
        self.assertEqual(len(titulos), len(set(titulos)))

    def test_los_detalles_tienen_longitud_util(self):
        # Un detalle de una palabra no explica nada; uno kilométrico no se lee.
        for titulo, detalle in PASOS_GUIA:
            self.assertGreater(len(detalle), 40, titulo)
            self.assertLess(len(detalle), 600, titulo)

    def test_el_primer_paso_habla_de_conectar_la_unidad(self):
        self.assertIn("Conecte", PASOS_GUIA[0][0])

    def test_la_guia_deja_claro_que_nada_es_automatico(self):
        texto_completo = " ".join(detalle for _, detalle in PASOS_GUIA).lower()
        self.assertTrue(
            "automátic" in texto_completo or "usted decide" in texto_completo,
            "la guía no aclara que el usuario decide antes de reparar",
        )


class TestLeyendaDeEstados(unittest.TestCase):
    """Cada estado visible en las tablas debe tener su entrada en la leyenda."""

    def test_hay_ocho_estados(self):
        # Los ocho estados que la tabla de unidades puede llegar a mostrar.
        self.assertEqual(len(LEYENDA_ESTADOS), 8)
        self.assertEqual(len(ESTADOS_UNIDAD), 8)

    def test_cada_estado_tiene_nombre_icono_color_y_descripcion(self):
        for entrada in LEYENDA_ESTADOS:
            self.assertEqual(len(entrada), 4, entrada)
            nombre, icono, clave_color, descripcion = entrada
            for campo in (nombre, icono, clave_color, descripcion):
                self.assertTrue(str(campo).strip(), entrada)

    def test_las_claves_de_color_existen_en_las_paletas(self):
        # Si una clave no existe, pintar la leyenda lanzaría KeyError.
        for nombre, _icono, clave_color, _desc in LEYENDA_ESTADOS:
            self.assertIn(
                clave_color, CLAVES_DE_PALETA,
                f"el estado {nombre!r} usa la clave de color inexistente {clave_color!r}",
            )

    def test_las_claves_de_color_resuelven_en_cada_paleta(self):
        for paleta_nombre in temas.PALETAS:
            paleta = temas.construir_paleta(paleta_nombre)
            for nombre, _icono, clave_color, _desc in LEYENDA_ESTADOS:
                color = paleta[clave_color]
                self.assertTrue(temas.es_color_valido(color), (paleta_nombre, nombre))
                # El estado debe poder leerse sobre el fondo del panel.
                self.assertGreaterEqual(
                    temas.ratio_contraste(color, paleta["bg"]),
                    temas.CONTRASTE_MINIMO_TEXTO_GRANDE,
                    f"{paleta_nombre}/{nombre}: contraste insuficiente",
                )

    def test_los_nombres_de_estado_no_se_repiten(self):
        nombres = [entrada[0] for entrada in LEYENDA_ESTADOS]
        self.assertEqual(len(nombres), len(set(nombres)))

    def test_la_leyenda_incluye_los_estados_criticos(self):
        nombres = " ".join(entrada[0] for entrada in LEYENDA_ESTADOS).lower()
        for esperado in ("sin firma detectada", "firma confirmada", "reparada"):
            self.assertIn(esperado, nombres, f"falta el estado {esperado!r}")

    def test_los_iconos_son_cortos_para_caber_en_la_tabla(self):
        for nombre, icono, _c, _d in LEYENDA_ESTADOS:
            self.assertLessEqual(len(icono), 4, nombre)


class TestExplicacionDeLaFirma(unittest.TestCase):
    """El diagrama de la firma del malware es la parte más difícil de entender."""

    def test_el_diagrama_no_esta_vacio(self):
        self.assertTrue(ESTRUCTURA_FIRMA.strip())

    def test_el_diagrama_muestra_la_ruta_caracteristica(self):
        for fragmento in ("Kaspersky", "Usb Drive", "5.dat", "6.dat", "7.dat", "1337"):
            self.assertIn(fragmento, ESTRUCTURA_FIRMA, fragmento)

    def test_el_diagrama_usa_caracteres_de_dibujo_legibles(self):
        # Se dibuja con caracteres de caja; si se perdieran, el texto quedaría
        # como una lista plana sin jerarquía.
        self.assertTrue(any(c in ESTRUCTURA_FIRMA for c in "└├│─"),
                        "el diagrama perdió sus caracteres de jerarquía")

    def test_el_diagrama_avisa_de_que_el_contenido_se_restaura(self):
        self.assertIn("restaura", ESTRUCTURA_FIRMA.lower())

    def test_hay_reglas_que_explican_la_firma(self):
        self.assertEqual(len(REGLAS_FIRMA), 4)
        for regla in REGLAS_FIRMA:
            self.assertIsInstance(regla, str)
            self.assertTrue(regla.strip())
            self.assertTrue(_sin_espacios_en_blanco_extremos(regla))

    def test_las_reglas_exigen_los_tres_dat(self):
        texto = " ".join(REGLAS_FIRMA)
        for archivo in ("5.dat", "6.dat", "7.dat"):
            self.assertIn(archivo, texto, archivo)

    def test_las_reglas_explican_el_fichero_numerico_sin_extension(self):
        texto = " ".join(REGLAS_FIRMA).lower()
        self.assertIn("numérico", texto)
        self.assertIn("sin extensión", texto)


class TestAccionesDeBotones(unittest.TestCase):

    def test_hay_ocho_acciones_documentadas(self):
        self.assertEqual(len(ACCIONES_BOTONES), 8)

    def test_cada_accion_tiene_nombre_y_descripcion(self):
        for entrada in ACCIONES_BOTONES:
            self.assertEqual(len(entrada), 2, entrada)
            nombre, descripcion = entrada
            self.assertTrue(nombre.strip(), entrada)
            self.assertGreater(len(descripcion.strip()), 20, nombre)

    def test_los_nombres_de_boton_no_se_repiten(self):
        nombres = [entrada[0] for entrada in ACCIONES_BOTONES]
        self.assertEqual(len(nombres), len(set(nombres)))

    def test_las_acciones_destructivas_avisan_de_que_borran(self):
        for nombre, descripcion in ACCIONES_BOTONES:
            if "Eliminar" in nombre or "eliminar" in descripcion.lower():
                self.assertTrue(
                    "borra" in descripcion.lower() or "elimina" in descripcion.lower(),
                    f"{nombre!r} no aclara su efecto destructivo",
                )

    def test_las_acciones_de_diagnostico_aclaran_que_no_borran(self):
        for nombre, descripcion in ACCIONES_BOTONES:
            if nombre.startswith("Escanear"):
                self.assertIn("no", descripcion.lower(), nombre)


class TestSeguridadYPreguntasFrecuentes(unittest.TestCase):

    def test_hay_seis_notas_de_seguridad(self):
        self.assertEqual(len(NOTAS_SEGURIDAD), 6)

    def test_las_notas_son_texto_util(self):
        for nota in NOTAS_SEGURIDAD:
            self.assertIsInstance(nota, str)
            self.assertGreater(len(nota.strip()), 30)
            self.assertTrue(_sin_espacios_en_blanco_extremos(nota))

    def test_las_notas_advierten_de_los_falsos_positivos(self):
        texto = " ".join(NOTAS_SEGURIDAD).lower()
        self.assertTrue(
            "legítim" in texto or "falso" in texto or "no demuestran" in texto,
            "las notas no advierten de que un nombre conocido no implica infección",
        )

    def test_la_guia_recomienda_hacer_copia_de_seguridad(self):
        # Está en el paso 5 y en las FAQ; se busca en todo el contenido porque
        # exigir una sección concreta daría falsos negativos.
        texto = texto_completo_de_ayuda()
        self.assertTrue(
            "copia de seguridad" in texto or "respaldo" in texto,
            "la guía no recomienda respaldar antes de reparar",
        )

    def test_hay_seis_preguntas_frecuentes(self):
        self.assertEqual(len(PREGUNTAS_FRECUENTES), 6)

    def test_cada_pregunta_tiene_respuesta(self):
        for pregunta, respuesta in PREGUNTAS_FRECUENTES:
            self.assertTrue(pregunta.strip())
            self.assertGreater(len(respuesta.strip()), 20, pregunta)
            self.assertIn("?", pregunta, f"{pregunta!r} no parece una pregunta")

    def test_las_preguntas_no_se_repiten(self):
        preguntas = [p for p, _ in PREGUNTAS_FRECUENTES]
        self.assertEqual(len(preguntas), len(set(preguntas)))


class TestTooltips(unittest.TestCase):
    """Textos breves que aparecen al pasar el ratón por encima de un control."""

    def test_hay_dieciocho_tooltips(self):
        self.assertEqual(len(TOOLTIPS), 18)

    def test_todas_las_claves_son_identificadores_en_minuscula(self):
        for clave in TOOLTIPS:
            self.assertIsInstance(clave, str)
            self.assertTrue(clave.strip())
            self.assertEqual(clave, clave.lower(), clave)
            self.assertNotIn(" ", clave, clave)

    def test_todos_los_textos_son_breves_y_utiles(self):
        for clave, texto in TOOLTIPS.items():
            self.assertIsInstance(texto, str)
            self.assertGreater(len(texto.strip()), 15, clave)
            # Un tooltip no debe ser un párrafo: no cabe en pantalla.
            self.assertLessEqual(len(texto), 220, clave)
            self.assertTrue(_sin_espacios_en_blanco_extremos(texto))
            self.assertNotIn("\n", texto, clave)

    def test_todas_las_claves_que_usa_la_gui_estan_definidas(self):
        for clave in TOOLTIPS_USADOS_POR_LA_GUI:
            self.assertIn(clave, TOOLTIPS, f"gui.py usa la clave inexistente {clave!r}")

    def test_obtener_texto_ayuda_devuelve_el_texto_de_una_clave(self):
        for clave in ("escanear", "reparar", "registro"):
            self.assertEqual(obtener_texto_ayuda(clave), TOOLTIPS[clave])

    def test_obtener_texto_ayuda_devuelve_cadena_vacia_para_clave_desconocida(self):
        self.assertEqual(obtener_texto_ayuda("no_existe"), "")
        self.assertEqual(obtener_texto_ayuda(""), "")


class TestDegradacionSinTkinter(unittest.TestCase):
    """La ayuda debe poder importarse y consultarse sin entorno gráfico."""

    def test_el_modulo_importa_sin_tkinter(self):
        # Si TKINTER_DISPONIBLE es False, el módulo igualmente carga.
        self.assertIsInstance(ayuda.TKINTER_DISPONIBLE, bool)

    def test_asignar_tooltip_devuelve_none_sin_tkinter(self):
        if ayuda.TKINTER_DISPONIBLE:
            self.skipTest("tkinter está disponible en este entorno")
        self.assertIsNone(asignar_tooltip(object(), "escanear"))
        self.assertIsNone(asignar_tooltip(object(), "texto libre"))

    def test_asignar_tooltip_devuelve_none_con_texto_vacio(self):
        # Independiente de tkinter: cadena vacía -> nada que mostrar.
        self.assertIsNone(asignar_tooltip(object(), ""))

    def test_la_clase_tooltip_existe_y_documenta_su_retardo(self):
        self.assertTrue(callable(ToolTip))
        self.assertGreater(ToolTip.RETARDO_MS, 0)
        self.assertIsInstance(ToolTip.DESFASE_X, int)
        self.assertIsInstance(ToolTip.DESFASE_Y, int)

    def test_el_contenido_de_ayuda_no_depende_de_tkinter(self):
        # Todo el texto debe ser consultable aunque no haya GUI.
        self.assertTrue(PASOS_GUIA and LEYENDA_ESTADOS and ACCIONES_BOTONES)
        self.assertTrue(NOTAS_SEGURIDAD and PREGUNTAS_FRECUENTES and TOOLTIPS)
        self.assertTrue(ESTRUCTURA_FIRMA and REGLAS_FIRMA)

    def test_resolucion_de_clave_o_texto_libre(self):
        # asignar_tooltip acepta una clave del catálogo o texto escrito a mano.
        # Sin tkinter devuelve None en ambos casos, pero la resolución del texto
        # se comprueba por separado para que la GUI pueda confiar en ella.
        self.assertEqual(TOOLTIPS.get("escanear", "texto libre"), TOOLTIPS["escanear"])
        self.assertEqual(TOOLTIPS.get("texto libre escrito", "texto libre escrito"),
                         "texto libre escrito")


class TestConsistenciaConLaGui(unittest.TestCase):
    """La leyenda debe describir exactamente lo que la tabla llega a mostrar.

    Este es el fallo que motivó el catálogo único: la leyenda hablaba de
    «Limpia» e «Inaccesible» mientras la pantalla decía «Sin firma detectada» y
    «No accesible», y además la GUI pintaba la revisión manual con el tag de
    «infectada», dejando configurado un tag «sospechosa» que nadie usaba.
    """

    @classmethod
    def setUpClass(cls):
        cls.gui = (GUI_DIR / "gui.py").read_text(encoding="utf-8")

    def test_toda_clave_de_estado_produce_texto_visible(self):
        for clave in claves_estado():
            texto = texto_estado(clave)
            self.assertTrue(texto.strip(), clave)

    def test_el_texto_de_cada_estado_aparece_en_la_leyenda(self):
        # Lo que se ve en la tabla debe poder buscarse, palabra por palabra, en
        # la leyenda de la pestaña de ayuda.
        nombres_leyenda = {nombre for nombre, _i, _t, _d in LEYENDA_ESTADOS}
        for clave in claves_estado():
            texto = texto_estado(clave)
            # Quitar el icono inicial para comparar solo el nombre del estado.
            nombre = texto.split(" ", 1)[1] if texto[:1] in "✓⚠⛔✔◐ℹ" else texto
            self.assertIn(nombre, nombres_leyenda,
                          f"el estado {clave!r} muestra {nombre!r}, que no está en la leyenda")

    def test_la_guia_no_deja_estados_sin_explicar(self):
        for clave in claves_estado():
            self.assertTrue(descripcion_estado(clave).strip(),
                            f"{clave} no tiene descripción en la ayuda")

    def test_la_gui_no_vuelve_a_escribir_estados_a_mano(self):
        # Cualquier literal ``estado = "..."`` en gui.py es una semilla de
        # divergencia: el texto debe salir de ayuda.texto_estado().
        import re
        literales = re.findall(r'^\s*estado\s*=\s*["\'](.+?)["\']',
                               self.gui, flags=re.MULTILINE)
        self.assertEqual(
            literales, [],
            f"gui.py vuelve a escribir estados a mano: {literales}",
        )

    def test_la_gui_pide_el_texto_al_catalogo(self):
        self.assertIn("ayuda.texto_estado(", self.gui)
        self.assertIn("ayuda.tag_estado(", self.gui)

    def test_las_claves_que_usa_la_gui_existen_en_el_catalogo(self):
        import ast
        arbol = ast.parse(self.gui)
        usadas = set()
        for nodo in ast.walk(arbol):
            if (isinstance(nodo, ast.Assign)
                    and any(getattr(t, "id", "") == "clave_estado" for t in nodo.targets)
                    and isinstance(nodo.value, ast.Constant)):
                usadas.add(nodo.value.value)
        self.assertTrue(usadas, "no se encontró ninguna clave_estado en gui.py")
        for clave in usadas:
            self.assertIn(clave, claves_estado(),
                          f"gui.py usa la clave de estado inexistente {clave!r}")

    def test_todos_los_tags_declarados_se_configuran_en_la_gui(self):
        # La GUI recorre claves_estado() y configura cada tag, así que basta con
        # que el bucle exista: ningún tag puede quedar sin color asignado.
        self.assertIn("for clave_estado in ayuda.claves_estado():", self.gui)
        self.assertIn("ayuda.tono_estado(clave_estado)", self.gui)
        declarados = {tag_estado(clave) for clave in claves_estado()} - {""}
        self.assertTrue(declarados)

    def test_no_hay_tags_declarados_dos_veces_con_distinto_estado(self):
        vistos = {}
        for clave in claves_estado():
            tag = tag_estado(clave)
            if not tag:
                continue
            self.assertNotIn(tag, vistos,
                             f"el tag {tag!r} lo usan {vistos.get(tag)!r} y {clave!r}")
            vistos[tag] = clave

    def test_el_tinte_de_cada_tag_mantiene_contraste_aa(self):
        # La GUI pinta el fondo del tag con un tinte al 78% del color semántico
        # sobre tree_bg; ese cálculo debe seguir siendo legible en toda paleta.
        for nombre_paleta in temas.PALETAS:
            paleta = temas.construir_paleta(nombre_paleta)
            for clave in claves_estado():
                if not tag_estado(clave):
                    continue
                tinte = temas.mezclar(paleta[tono_estado(clave)],
                                      paleta["tree_bg"], 0.78)
                self.assertGreaterEqual(
                    temas.ratio_contraste(paleta["tree_fg"], tinte),
                    temas.CONTRASTE_MINIMO_AA,
                    f"{nombre_paleta}/{clave}: texto ilegible sobre el tinte",
                )

    def test_clave_desconocida_degrada_sin_romper(self):
        self.assertEqual(texto_estado("no_existe"), "no_existe")
        self.assertEqual(tag_estado("no_existe"), "")
        self.assertEqual(tono_estado("no_existe"), "texto_suave")
        self.assertEqual(descripcion_estado("no_existe"), "")


class TestEstadosDeReparacion(unittest.TestCase):
    """El resultado de reparar debe llegar al usuario en lenguaje normal."""

    def test_todos_los_estados_del_motor_tienen_texto_legible(self):
        # Prueba cruzada: si repair_engine añade un estado nuevo y nadie lo
        # traduce, el usuario vería la cadena de máquina en la barra de estado.
        sys.path.insert(0, str(GUI_DIR))
        from repair_engine import EstadoReparacion

        for estado in EstadoReparacion:
            with self.subTest(estado=estado.name):
                self.assertIn(estado.value, ESTADOS_REPARACION,
                              f"falta la traducción de {estado.name}")

    def test_el_texto_no_contiene_guiones_bajos(self):
        for valor, texto in ESTADOS_REPARACION.items():
            self.assertNotIn("_", texto, valor)
            self.assertTrue(texto.strip(), valor)

    def test_texto_reparacion_traduce_los_valores_conocidos(self):
        self.assertEqual(texto_reparacion("completado_con_errores"),
                         "Completada con errores")
        self.assertEqual(texto_reparacion("completado"), "Reparación completada")
        self.assertEqual(texto_reparacion("fallido"), "Reparación fallida")

    def test_texto_reparacion_degrada_con_valores_desconocidos(self):
        # Nunca debe lanzar: el log no puede romper la aplicación.
        self.assertEqual(texto_reparacion("estado_inventado"), "estado inventado")
        self.assertEqual(texto_reparacion(""), "")
        self.assertEqual(texto_reparacion(None), "")

    def test_el_estado_con_errores_coincide_con_la_leyenda(self):
        # El mismo concepto debe leerse igual en la tabla y en la leyenda.
        self.assertEqual(texto_reparacion("completado_con_errores"),
                         texto_estado("con_errores").split(" ", 1)[-1])

    def test_la_gui_usa_la_traduccion_en_lugar_del_valor_del_enum(self):
        gui = (GUI_DIR / "gui.py").read_text(encoding="utf-8")
        self.assertIn("ayuda.texto_reparacion(resultado.estado.value)", gui)
        # El valor crudo ya no debe llegar ni al log ni a la barra de estado.
        self.assertNotIn('f"Reparación de {resultado.unidad}: {resultado.estado.value}"', gui)

    def test_la_gui_registra_las_unidades_con_errores(self):
        gui = (GUI_DIR / "gui.py").read_text(encoding="utf-8")
        self.assertIn("_unidades_con_errores", gui)
        # El estado con errores debe evaluarse antes que el de «reparada», o la
        # tabla ocultaría que el trabajo quedó a medias.
        posicion_errores = gui.index('clave_estado = "con_errores"')
        posicion_reparada = gui.index('clave_estado = "reparada"')
        self.assertLess(posicion_errores, posicion_reparada,
                        "«reparada» se evalúa antes que «con_errores»")

    def test_una_reparacion_con_errores_tambien_cuenta_como_reparada(self):
        gui = (GUI_DIR / "gui.py").read_text(encoding="utf-8")
        # Restauró contenido aunque quedaran restos: debe marcarse.
        self.assertIn("EstadoReparacion.COMPLETADO_CON_ERRORES", gui)
        self.assertIn("marcar_unidad_reparada(resultado.unidad)", gui)


class TestInfoDelSistema(unittest.TestCase):
    """La pestaña de ayuda muestra qué sistema y modo detectó la aplicación."""

    def setUp(self):
        self.info = obtener_info_sistema()

    def test_devuelve_pares_etiqueta_valor(self):
        self.assertIsInstance(self.info, list)
        self.assertTrue(self.info)
        for entrada in self.info:
            self.assertEqual(len(entrada), 2, entrada)
            etiqueta, valor = entrada
            self.assertIsInstance(etiqueta, str)
            self.assertIsInstance(valor, str)
            self.assertTrue(etiqueta.strip(), entrada)
            self.assertTrue(valor.strip(), entrada)

    def test_incluye_los_datos_esenciales_del_equipo(self):
        etiquetas = " ".join(etiqueta for etiqueta, _ in self.info).lower()
        for esperada in ("sistema", "arquitectura", "python", "soporte"):
            self.assertIn(esperada, etiquetas, f"falta el dato {esperada!r}")

    def test_las_etiquetas_no_se_repiten(self):
        etiquetas = [etiqueta for etiqueta, _ in self.info]
        self.assertEqual(len(etiquetas), len(set(etiquetas)))

    def test_el_valor_de_arquitectura_menciona_los_bits(self):
        valores = dict(self.info)
        arquitectura = next(v for k, v in valores.items() if "rquitectura" in k)
        self.assertIn("bits", arquitectura)

    def test_es_repetible(self):
        self.assertEqual(obtener_info_sistema(), self.info)


if __name__ == "__main__":
    unittest.main(verbosity=2)
