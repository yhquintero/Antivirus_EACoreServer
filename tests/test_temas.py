"""Pruebas del motor de temas (``temas.py``).

El módulo es deliberadamente independiente de tkinter para poder probarlo en el
CI sin entorno gráfico. Estas pruebas verifican dos cosas que importan al
usuario final: que las paletas sean accesibles (contraste WCAG AA/AAA) y que la
personalización de acento y tamaño de letra nunca produzca texto ilegible.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import temas
from temas import (
    ACENTOS_SUGERIDOS,
    CLAVES_PALETA,
    CONTRASTE_MINIMO_AA,
    CONTRASTE_MINIMO_TEXTO_GRANDE,
    ESCALA_POR_DEFECTO,
    ESCALAS_FUENTE,
    FUENTES_MONO_PREFERIDAS,
    FUENTES_PREFERIDAS,
    NOMBRES_ESCALAS,
    NOMBRES_PALETAS,
    PALETA_POR_DEFECTO,
    PALETAS,
    aclarar,
    color_texto_legible,
    construir_paleta,
    detectar_tema_sistema,
    elegir_fuente,
    es_color_valido,
    hex_a_rgb,
    listar_escalas,
    listar_paletas,
    luminancia_relativa,
    mezclar,
    oscurecer,
    ratio_contraste,
    recortar_proporcion,
    resolver_nombre_paleta,
    rgb_a_hex,
    tamano_fuente,
    validar_paleta,
)

# Umbrales WCAG 2.1
AA_NORMAL = 4.5
AA_GRANDE = 3.0
AAA_NORMAL = 7.0

# Pares texto/fondo que el usuario lee a tamaño normal: deben cumplir AA.
PARES_LECTURA = (
    ("fg", "bg"),
    ("texto_suave", "bg"),
    ("log_fg", "log_bg"),
    ("tree_fg", "tree_bg"),
    ("tooltip_fg", "tooltip_bg"),
)


class TestCatalogoDePaletas(unittest.TestCase):
    """El catálogo debe estar completo y ser coherente consigo mismo."""

    def test_hay_cinco_paletas_nominadas(self):
        self.assertEqual(
            sorted(PALETAS),
            sorted(["oscuro", "claro", "azul", "esmeralda", "contraste"]),
        )

    def test_la_paleta_por_defecto_existe(self):
        self.assertIn(PALETA_POR_DEFECTO, PALETAS)

    def test_cada_paleta_declara_todas_las_claves(self):
        for nombre, paleta in PALETAS.items():
            for clave in CLAVES_PALETA:
                self.assertIn(clave, paleta, f"{nombre} sin clave {clave}")

    def test_todos_los_colores_de_todas_las_paletas_son_hex_validos(self):
        for nombre, paleta in PALETAS.items():
            for clave in CLAVES_PALETA:
                self.assertTrue(
                    es_color_valido(paleta[clave]),
                    f"{nombre}.{clave} = {paleta[clave]!r} no es un color válido",
                )

    def test_toda_paleta_pasa_la_validacion_interna(self):
        for nombre in PALETAS:
            problemas = validar_paleta(construir_paleta(nombre))
            self.assertEqual(problemas, [], f"{nombre}: {problemas}")

    def test_los_nombres_amigables_cubren_paletas_y_la_opcion_sistema(self):
        for nombre in PALETAS:
            self.assertIn(nombre, NOMBRES_PALETAS)
            self.assertTrue(NOMBRES_PALETAS[nombre])
        # "sistema" es una opción del menú, no una paleta del catálogo.
        self.assertIn("sistema", NOMBRES_PALETAS)
        self.assertNotIn("sistema", PALETAS)

    def test_listar_paletas_incluye_la_opcion_sistema_al_final(self):
        claves = [clave for clave, _ in listar_paletas()]
        self.assertEqual(claves[:-1], list(PALETAS))
        self.assertEqual(claves[-1], "sistema")

    def test_las_paletas_son_realmente_distintas_entre_si(self):
        fondos = {construir_paleta(nombre)["bg"] for nombre in PALETAS}
        self.assertEqual(len(fondos), len(PALETAS), "hay paletas con el mismo fondo")

    def test_hay_paletas_oscuras_y_claras(self):
        oscuros = [n for n in PALETAS if luminancia_relativa(construir_paleta(n)["bg"]) < 0.4]
        claros = [n for n in PALETAS if luminancia_relativa(construir_paleta(n)["bg"]) >= 0.4]
        self.assertTrue(oscuros, "no queda ninguna paleta oscura")
        self.assertTrue(claros, "no queda ninguna paleta clara")


class TestAccesibilidadDePaletas(unittest.TestCase):
    """Ninguna paleta puede quedar por debajo del contraste WCAG AA."""

    def test_todos_los_pares_de_lectura_cumplen_aa(self):
        for nombre in PALETAS:
            paleta = construir_paleta(nombre)
            for frente, fondo in PARES_LECTURA:
                ratio = ratio_contraste(paleta[frente], paleta[fondo])
                self.assertGreaterEqual(
                    ratio, AA_NORMAL,
                    f"{nombre}: {frente}/{fondo} = {ratio:.2f} < {AA_NORMAL}",
                )

    def test_el_texto_sobre_el_acento_cumple_aa(self):
        for nombre in PALETAS:
            paleta = construir_paleta(nombre)
            ratio = ratio_contraste(paleta["texto_sobre_acento"], paleta["acento"])
            self.assertGreaterEqual(
                ratio, AA_NORMAL,
                f"{nombre}: texto sobre acento = {ratio:.2f}",
            )

    def test_los_colores_de_estado_cumplen_al_menos_aa_para_texto_grande(self):
        # exito/error/advertencia/info se usan sobre el fondo del panel.
        for nombre in PALETAS:
            paleta = construir_paleta(nombre)
            for estado in ("exito", "error", "advertencia", "info"):
                ratio = ratio_contraste(paleta[estado], paleta["bg"])
                self.assertGreaterEqual(
                    ratio, AA_GRANDE,
                    f"{nombre}: {estado}/bg = {ratio:.2f}",
                )

    def test_la_paleta_de_alto_contraste_cumple_aaa(self):
        paleta = construir_paleta("contraste")
        for frente, fondo in PARES_LECTURA:
            ratio = ratio_contraste(paleta[frente], paleta[fondo])
            self.assertGreaterEqual(
                ratio, AAA_NORMAL,
                f"contraste: {frente}/{fondo} = {ratio:.2f} < {AAA_NORMAL}",
            )

    def test_el_acento_se_distingue_del_fondo(self):
        for nombre in PALETAS:
            paleta = construir_paleta(nombre)
            self.assertGreaterEqual(
                ratio_contraste(paleta["acento"], paleta["bg"]), AA_GRANDE,
                f"{nombre}: acento indistinguible del fondo",
            )

    def test_validar_paleta_detecta_una_paleta_rota(self):
        rota = dict(construir_paleta(PALETA_POR_DEFECTO))
        rota["fg"] = rota["bg"]          # texto del mismo color que el fondo
        self.assertTrue(validar_paleta(rota))

    def test_validar_paleta_detecta_un_color_invalido(self):
        rota = dict(construir_paleta(PALETA_POR_DEFECTO))
        rota["acento"] = "azul-marino"
        self.assertTrue(validar_paleta(rota))


class TestAcentoPersonalizado(unittest.TestCase):
    """El selector de color debe derivar tonos legibles, no copiar el color a ciegas."""

    def test_el_acento_elegido_se_aplica(self):
        for acento in ACENTOS_SUGERIDOS:
            paleta = construir_paleta(PALETA_POR_DEFECTO, acento)
            self.assertEqual(paleta["acento"], acento)

    def test_todos_los_acentos_sugeridos_son_validos(self):
        for acento in ACENTOS_SUGERIDOS:
            self.assertTrue(es_color_valido(acento), acento)

    def test_el_texto_sobre_acento_siempre_es_legible(self):
        # Barrido exhaustivo: cada paleta con cada acento sugerido.
        for nombre in PALETAS:
            for acento in ACENTOS_SUGERIDOS:
                paleta = construir_paleta(nombre, acento)
                ratio = ratio_contraste(paleta["texto_sobre_acento"], paleta["acento"])
                self.assertGreaterEqual(
                    ratio, AA_NORMAL,
                    f"{nombre} + {acento}: texto sobre acento = {ratio:.2f}",
                )

    def test_acentos_extremos_eligen_blanco_o_negro_segun_corresponda(self):
        # Amarillo brillante -> texto oscuro; violeta profundo -> texto claro.
        claro = construir_paleta(PALETA_POR_DEFECTO, "#ffeb3b")
        self.assertEqual(claro["texto_sobre_acento"], "#000000")
        oscuro = construir_paleta(PALETA_POR_DEFECTO, "#311b92")
        self.assertEqual(oscuro["texto_sobre_acento"], "#ffffff")

    def test_los_tonos_derivados_del_acento_no_son_el_acento_a_secas(self):
        paleta = construir_paleta(PALETA_POR_DEFECTO, "#4f8cff")
        self.assertNotEqual(paleta["acento_oscuro"], paleta["acento"])
        self.assertNotEqual(paleta["acento_suave"], paleta["acento"])
        self.assertNotEqual(paleta["seleccion"], paleta["acento"])
        for clave in ("acento_oscuro", "acento_suave", "seleccion"):
            self.assertTrue(es_color_valido(paleta[clave]), clave)

    def test_el_acento_oscuro_es_efectivamente_mas_oscuro(self):
        paleta = construir_paleta(PALETA_POR_DEFECTO, "#4f8cff")
        self.assertLess(
            luminancia_relativa(paleta["acento_oscuro"]),
            luminancia_relativa(paleta["acento"]),
        )

    def test_un_acento_rojizo_no_deja_el_error_indistinguible(self):
        # Los colores semánticos conservan su significado aunque choquen.
        paleta = construir_paleta(PALETA_POR_DEFECTO, "#c62828")
        self.assertNotEqual(paleta["error"], paleta["acento"])
        self.assertGreaterEqual(ratio_contraste(paleta["error"], paleta["acento"]), 1.2)

    def test_acento_invalido_se_ignora_sin_romper(self):
        for invalido in ("", "   ", "rojo", "#12345", "#gggggg", None):
            paleta = construir_paleta(PALETA_POR_DEFECTO, invalido)
            self.assertEqual(paleta["acento"], PALETAS[PALETA_POR_DEFECTO]["acento"])
            self.assertEqual(validar_paleta(paleta), [])

    def test_el_acento_personalizado_no_altera_la_paleta_del_catalogo(self):
        antes = dict(PALETAS[PALETA_POR_DEFECTO])
        construir_paleta(PALETA_POR_DEFECTO, "#ff00ff")
        self.assertEqual(PALETAS[PALETA_POR_DEFECTO], antes)

    def test_la_legibilidad_se_mantiene_tras_reacentuar_cada_paleta(self):
        for nombre in PALETAS:
            paleta = construir_paleta(nombre, "#0f9d6e")
            for frente, fondo in PARES_LECTURA:
                self.assertGreaterEqual(
                    ratio_contraste(paleta[frente], paleta[fondo]), AA_NORMAL,
                    f"{nombre} reacentuada: {frente}/{fondo}",
                )


class TestResolucionDeTema(unittest.TestCase):

    def test_sistema_se_resuelve_a_una_paleta_real(self):
        self.assertIn(resolver_nombre_paleta("sistema"), PALETAS)

    def test_detectar_tema_sistema_devuelve_una_paleta_valida(self):
        self.assertIn(detectar_tema_sistema(), PALETAS)

    def test_nombre_desconocido_cae_en_la_paleta_por_defecto(self):
        for invalido in ("", "neon", "OSCURO", None, 123):
            self.assertEqual(resolver_nombre_paleta(invalido), PALETA_POR_DEFECTO)

    def test_nombre_conocido_se_conserva(self):
        for nombre in PALETAS:
            self.assertEqual(resolver_nombre_paleta(nombre), nombre)

    def test_construir_paleta_marca_la_paleta_resuelta(self):
        paleta = construir_paleta("sistema")
        self.assertIn(paleta["_paleta"], PALETAS)


class TestUtilidadesDeColor(unittest.TestCase):

    def test_conversion_hex_rgb_ida_y_vuelta(self):
        for color in ("#000000", "#ffffff", "#4f8cff", "#123456"):
            self.assertEqual(rgb_a_hex(*hex_a_rgb(color)), color)

    def test_hex_a_rgb_acepta_forma_corta_y_sin_almohadilla(self):
        self.assertEqual(hex_a_rgb("#fff"), (255, 255, 255))
        self.assertEqual(hex_a_rgb("000000"), (0, 0, 0))
        self.assertEqual(hex_a_rgb("#0b6bcb"), (11, 107, 203))

    def test_rgb_a_hex_rellena_ceros_y_usa_minusculas(self):
        self.assertEqual(rgb_a_hex(0, 0, 0), "#000000")
        self.assertEqual(rgb_a_hex(11, 107, 203), "#0b6bcb")

    def test_luminancia_de_negro_y_blanco(self):
        self.assertAlmostEqual(luminancia_relativa("#000000"), 0.0, places=3)
        self.assertAlmostEqual(luminancia_relativa("#ffffff"), 1.0, places=3)

    def test_ratio_de_contraste_maximo_es_21(self):
        self.assertAlmostEqual(ratio_contraste("#000000", "#ffffff"), 21.0, places=1)

    def test_ratio_de_contraste_es_simetrico(self):
        a, b = "#1e2430", "#f2f4f8"
        self.assertAlmostEqual(ratio_contraste(a, b), ratio_contraste(b, a), places=6)

    def test_ratio_de_un_color_consigo_mismo_es_uno(self):
        self.assertAlmostEqual(ratio_contraste("#4f8cff", "#4f8cff"), 1.0, places=6)

    def test_mezclar_en_los_extremos_devuelve_los_originales(self):
        self.assertEqual(mezclar("#000000", "#ffffff", 0.0), "#000000")
        self.assertEqual(mezclar("#000000", "#ffffff", 1.0), "#ffffff")

    def test_mezclar_a_la_mitad_da_el_punto_medio(self):
        self.assertEqual(mezclar("#000000", "#ffffff", 0.5), "#808080")

    def test_aclarar_sube_la_luminancia_y_oscurecer_la_baja(self):
        base = "#4f8cff"
        self.assertGreater(luminancia_relativa(aclarar(base, 0.3)),
                           luminancia_relativa(base))
        self.assertLess(luminancia_relativa(oscurecer(base, 0.3)),
                        luminancia_relativa(base))

    def test_aclarar_y_oscurecer_al_maximo_llegan_a_los_extremos(self):
        self.assertEqual(aclarar("#4f8cff", 1.0), "#ffffff")
        self.assertEqual(oscurecer("#4f8cff", 1.0), "#000000")

    def test_proporcion_fuera_de_rango_se_recorta(self):
        self.assertEqual(recortar_proporcion(-0.5), 0.0)
        self.assertEqual(recortar_proporcion(1.5), 1.0)
        self.assertEqual(recortar_proporcion(0.25), 0.25)

    def test_color_texto_legible_elige_por_contraste(self):
        self.assertEqual(color_texto_legible("#ffffff"), "#000000")
        self.assertEqual(color_texto_legible("#000000"), "#ffffff")
        self.assertEqual(color_texto_legible("#ffeb3b"), "#000000")
        self.assertEqual(color_texto_legible("#311b92"), "#ffffff")

    def test_color_texto_legible_siempre_cumple_aa(self):
        for fondo in ACENTOS_SUGERIDOS + ("#ffeb3b", "#311b92", "#808080"):
            texto = color_texto_legible(fondo)
            self.assertGreaterEqual(ratio_contraste(texto, fondo), AA_NORMAL, fondo)

    def test_es_color_valido_acepta_y_rechaza_correctamente(self):
        for valido in ("#000000", "#FFFFFF", "#fff", "#4f8cff"):
            self.assertTrue(es_color_valido(valido), valido)
        for invalido in ("", None, "negro", "#12345", "#gggggg", "00000000", "#12 45"):
            self.assertFalse(es_color_valido(invalido), invalido)

    def test_los_limites_de_contraste_son_los_de_wcag(self):
        self.assertEqual(CONTRASTE_MINIMO_AA, AA_NORMAL)
        self.assertEqual(CONTRASTE_MINIMO_TEXTO_GRANDE, AA_GRANDE)


class TestEscalasDeFuente(unittest.TestCase):

    def test_hay_cuatro_escalas_con_nombre_legible(self):
        self.assertEqual(sorted(ESCALAS_FUENTE), sorted(NOMBRES_ESCALAS))
        self.assertEqual(sorted(ESCALAS_FUENTE),
                         sorted(["pequena", "normal", "grande", "enorme"]))

    def test_la_escala_por_defecto_es_normal_y_vale_uno(self):
        self.assertEqual(ESCALA_POR_DEFECTO, "normal")
        self.assertEqual(ESCALAS_FUENTE[ESCALA_POR_DEFECTO], 1.0)

    def test_los_factores_estan_en_un_rango_razonable(self):
        for nombre, factor in ESCALAS_FUENTE.items():
            self.assertGreaterEqual(factor, 0.8, nombre)
            self.assertLessEqual(factor, 1.5, nombre)

    def test_tamano_fuente_es_monotono_segun_la_escala(self):
        orden = ["pequena", "normal", "grande", "enorme"]
        tamanos = [tamano_fuente(11, escala) for escala in orden]
        self.assertEqual(tamanos, sorted(tamanos))
        self.assertLess(tamanos[0], tamanos[-1])

    def test_tamano_nunca_baja_de_un_minimo_util(self):
        for escala in ESCALAS_FUENTE:
            for base in (8, 9, 10, 11, 12, 14, 20):
                self.assertGreaterEqual(tamano_fuente(base, escala), 7, (base, escala))

    def test_escala_desconocida_no_rompe(self):
        self.assertEqual(tamano_fuente(11, "inexistente"), tamano_fuente(11, "normal"))
        self.assertEqual(tamano_fuente(11, None), tamano_fuente(11, "normal"))

    def test_tamano_devuelve_entero(self):
        for escala in ESCALAS_FUENTE:
            self.assertIsInstance(tamano_fuente(11, escala), int)

    def test_listar_escalas_coincide_con_el_catalogo(self):
        self.assertEqual([c for c, _ in listar_escalas()], list(ESCALAS_FUENTE))
        for clave, nombre in listar_escalas():
            self.assertEqual(nombre, NOMBRES_ESCALAS[clave])


class TestSeleccionDeFuente(unittest.TestCase):
    """La familia de fuente se elige por plataforma, sin dar por hecha la de Windows."""

    def test_todas_las_familias_posibles_tienen_preferencias(self):
        familias = {"windows", "darwin", "linux", "bsd", "sunos", "aix", "desconocida"}
        self.assertEqual(set(FUENTES_PREFERIDAS), familias)
        self.assertEqual(set(FUENTES_MONO_PREFERIDAS), familias)

    def test_cada_lista_de_preferencias_no_esta_vacia(self):
        for tabla in (FUENTES_PREFERIDAS, FUENTES_MONO_PREFERIDAS):
            for clave, fuentes in tabla.items():
                self.assertTrue(fuentes, clave)
                for fuente in fuentes:
                    self.assertTrue(fuente.strip(), clave)

    def test_elige_la_primera_preferida_disponible(self):
        self.assertEqual(
            elegir_fuente(["Noto Sans", "DejaVu Sans"], ("DejaVu Sans", "Noto Sans"), "TkDefaultFont"),
            "DejaVu Sans",
        )

    def test_respeta_el_orden_de_preferencia_no_el_de_disponibilidad(self):
        self.assertEqual(
            elegir_fuente(["Arial", "Segoe UI"], ("Segoe UI", "Arial"), "TkDefaultFont"),
            "Segoe UI",
        )

    def test_devuelve_el_nombre_con_las_mayusculas_del_sistema(self):
        # Algunos backends normalizan mayúsculas; se devuelve la forma real.
        self.assertEqual(
            elegir_fuente(["dejavu sans"], ("DejaVu Sans",), "TkDefaultFont"),
            "dejavu sans",
        )

    def test_la_comparacion_ignora_mayusculas_y_espacios(self):
        self.assertEqual(
            elegir_fuente(["  SEGOE UI  "], ("Segoe UI",), "TkDefaultFont"),
            "SEGOE UI",
        )

    def test_usa_el_respaldo_cuando_no_hay_ninguna_preferida(self):
        self.assertEqual(
            elegir_fuente(["Fuente Rara"], ("Segoe UI", "Tahoma"), "TkDefaultFont"),
            "TkDefaultFont",
        )

    def test_lista_de_disponibles_vacia_o_nula_usa_el_respaldo(self):
        for disponibles in ([], (), None):
            self.assertEqual(
                elegir_fuente(disponibles, ("Segoe UI",), "TkDefaultFont"),
                "TkDefaultFont",
            )

    def test_preferencias_vacias_usan_el_respaldo(self):
        self.assertEqual(elegir_fuente(["Arial"], (), "TkDefaultFont"), "TkDefaultFont")

    def test_windows_prefiere_segoe_ui_y_linux_dejavu(self):
        self.assertEqual(FUENTES_PREFERIDAS["windows"][0], "Segoe UI")
        self.assertEqual(FUENTES_PREFERIDAS["linux"][0], "DejaVu Sans")
        self.assertEqual(FUENTES_MONO_PREFERIDAS["windows"][0], "Cascadia Mono")

    def test_ninguna_lista_incluye_una_fuente_exclusiva_de_windows_al_principio(self):
        # En Linux/macOS/BSD la primera candidata debe existir allí de serie.
        for clave in ("linux", "darwin", "bsd", "sunos", "aix", "desconocida"):
            self.assertNotEqual(FUENTES_PREFERIDAS[clave][0], "Segoe UI", clave)


if __name__ == "__main__":
    unittest.main(verbosity=2)
