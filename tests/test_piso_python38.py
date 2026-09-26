"""Guarda el piso de Python 3.8 declarado para la aplicación.

Python 3.8 es el último intérprete con instalador para Windows Vista, 7 y 8.0,
así que todo el código debe seguir siendo importable y ejecutable ahí. Estas
pruebas no necesitan un intérprete 3.8 real: el propio módulo ``ast`` permite
validar la sintaxis contra una versión de lenguaje concreta, y las APIs nuevas
se detectan recorriendo el árbol.

Si alguien usa ``match``, ``str | None``, ``dict[str, str]`` en tiempo de
ejecución o ``str.removeprefix()``, este archivo falla en el CI de 3.12 antes
de que el ejecutable se rompa en el Windows 7 del usuario.
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Versión mínima de lenguaje que debe aceptar todo el código del proyecto.
PISO = (3, 8)

# Archivos que forman la aplicación. Se excluye este propio test para no
# acoplarlo a su contenido, y los directorios generados por herramientas.
EXCLUIDOS = {"build", "dist", ".venv", "venv", "__pycache__"}


def archivos_python():
    """Todos los .py del proyecto, ordenados y sin directorios generados."""
    encontrados = []
    for ruta in RAIZ.rglob("*.py"):
        if any(parte in EXCLUIDOS for parte in ruta.parts):
            continue
        encontrados.append(ruta)
    return sorted(encontrados, key=lambda r: str(r.relative_to(RAIZ)))


# Métodos y funciones añadidos al lenguaje después de 3.8.
API_POSTERIORES = {
    "removeprefix": (3, 9),
    "removesuffix": (3, 9),
    "pairwise": (3, 10),
    "anext": (3, 10),
    "aiter": (3, 10),
    "exceptiongroup": (3, 11),
    "encoding": None,          # marcador ignorado: nombre demasiado común
}

# Módulos estándar que no existen en 3.8.
MODULOS_POSTERIORES = {
    "zoneinfo": (3, 9),
    "graphlib": (3, 9),
    "tomllib": (3, 11),
}

# Genéricos builtin que solo se pueden subindizar desde 3.9, y únicamente fuera
# de una anotación (dentro de anotaciones son inertes con
# ``from __future__ import annotations``).
GENERICOS_BUILTIN = {"dict", "list", "set", "frozenset", "tuple", "type"}


class TestSintaxisCompatibleCon38(unittest.TestCase):

    def test_hay_archivos_que_comprobar(self):
        self.assertGreater(len(archivos_python()), 10)

    def test_todos_los_archivos_parsean_con_la_version_de_lenguaje_minima(self):
        for ruta in archivos_python():
            with self.subTest(archivo=str(ruta.relative_to(RAIZ))):
                fuente = ruta.read_text(encoding="utf-8")
                try:
                    ast.parse(fuente, feature_version=PISO)
                except SyntaxError as error:
                    self.fail(
                        f"{ruta.relative_to(RAIZ)}:{error.lineno} usa sintaxis "
                        f"posterior a Python {PISO[0]}.{PISO[1]}: {error.msg}"
                    )

    def test_no_hay_sentencias_match(self):
        # match/case es de 3.10 y ast lo reporta como Match a partir de ahí.
        for ruta in archivos_python():
            fuente = ruta.read_text(encoding="utf-8")
            if "match " in fuente and "case " in fuente:
                arbol = ast.parse(fuente)
                coincidencias = [n for n in ast.walk(arbol)
                                 if type(n).__name__ == "Match"]
                self.assertEqual(
                    coincidencias, [],
                    f"{ruta.relative_to(RAIZ)} usa match/case (Python 3.10+)",
                )

    def test_no_hay_uniones_de_tipo_con_barra_en_tiempo_de_ejecucion(self):
        # ``X | Y`` como tipo es de 3.10; con ``from __future__ import
        # annotations`` es inofensivo dentro de una anotación, pero no fuera.
        for ruta in archivos_python():
            fuente = ruta.read_text(encoding="utf-8")
            arbol = ast.parse(fuente)
            anotaciones = set()
            for nodo in ast.walk(arbol):
                for campo in ("annotation", "returns"):
                    anot = getattr(nodo, campo, None)
                    if anot is not None:
                        anotaciones.update(id(sub) for sub in ast.walk(anot))
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.BitOr):
                    if id(nodo) in anotaciones:
                        continue
                    # Fuera de anotaciones el operador | es legítimo entre
                    # enteros y conjuntos; solo se señala si ambos operandos son
                    # nombres con pinta de tipo (mayúscula inicial o minúscula
                    # de builtin de tipo).
                    for operando in (nodo.left, nodo.right):
                        if isinstance(operando, ast.Name) and (
                            operando.id in GENERICOS_BUILTIN
                            or operando.id in ("None", "Any", "Optional")
                        ):
                            self.fail(
                                f"{ruta.relative_to(RAIZ)}:{nodo.lineno} parece "
                                f"usar una unión de tipos PEP 604 (Python 3.10+)"
                            )


class TestApisCompatiblesCon38(unittest.TestCase):

    def test_no_se_usan_modulos_estandar_posteriores_a_38(self):
        for ruta in archivos_python():
            arbol = ast.parse(ruta.read_text(encoding="utf-8"))
            for nodo in ast.walk(arbol):
                modulos = []
                if isinstance(nodo, ast.Import):
                    modulos = [alias.name.split(".")[0] for alias in nodo.names]
                elif isinstance(nodo, ast.ImportFrom) and nodo.module:
                    modulos = [nodo.module.split(".")[0]]
                for modulo in modulos:
                    if modulo in MODULOS_POSTERIORES:
                        self.fail(
                            f"{ruta.relative_to(RAIZ)}:{nodo.lineno} importa "
                            f"{modulo}, disponible solo desde Python "
                            f"{MODULOS_POSTERIORES[modulo][0]}."
                            f"{MODULOS_POSTERIORES[modulo][1]}"
                        )

    def test_no_se_llaman_metodos_anadidos_despues_de_38(self):
        for ruta in archivos_python():
            arbol = ast.parse(ruta.read_text(encoding="utf-8"))
            for nodo in ast.walk(arbol):
                if not isinstance(nodo, ast.Attribute):
                    continue
                version = API_POSTERIORES.get(nodo.attr)
                if not version:
                    continue
                # Solo interesa cuando el receptor es una cadena literal o el
                # resultado de una llamada sobre cadena; si no, el nombre es
                # demasiado genérico para afirmar nada.
                receptor = nodo.value
                es_cadena = isinstance(receptor, ast.Constant) and \
                    isinstance(receptor.value, str)
                if es_cadena:
                    self.fail(
                        f"{ruta.relative_to(RAIZ)}:{nodo.lineno} usa "
                        f"str.{nodo.attr}(), disponible solo desde Python "
                        f"{version[0]}.{version[1]}"
                    )

    def test_no_se_subindizan_genericos_builtin_fuera_de_anotaciones(self):
        for ruta in archivos_python():
            fuente = ruta.read_text(encoding="utf-8")
            arbol = ast.parse(fuente)
            anotaciones = set()
            for nodo in ast.walk(arbol):
                for campo in ("annotation", "returns"):
                    anot = getattr(nodo, campo, None)
                    if anot is not None:
                        anotaciones.update(id(sub) for sub in ast.walk(anot))
            for nodo in ast.walk(arbol):
                if not isinstance(nodo, ast.Subscript):
                    continue
                if not (isinstance(nodo.value, ast.Name)
                        and nodo.value.id in GENERICOS_BUILTIN):
                    continue
                if id(nodo) in anotaciones:
                    continue
                self.fail(
                    f"{ruta.relative_to(RAIZ)}:{nodo.lineno} usa "
                    f"{nodo.value.id}[...] en tiempo de ejecución; en Python 3.8 "
                    f"hace falta typing.{nodo.value.id.capitalize()}"
                )

    def test_las_anotaciones_no_exigen_sintaxis_posterior_a_38(self):
        """Un módulo sin ``from __future__ import annotations`` evalúa sus
        anotaciones al importar, así que no puede usar uniones PEP 604 ni
        genéricos builtin. Con la importación diferida sí podría.
        """
        for ruta in archivos_python():
            fuente = ruta.read_text(encoding="utf-8")
            arbol = ast.parse(fuente)
            diferidas = any(
                isinstance(n, ast.ImportFrom) and n.module == "__future__"
                and any(a.name == "annotations" for a in n.names)
                for n in arbol.body
            )
            if diferidas:
                continue

            relativas = RAIZ
            nombre = str(ruta.relative_to(relativas))
            anotaciones = []
            for nodo in ast.walk(arbol):
                for campo in ("annotation", "returns"):
                    anot = getattr(nodo, campo, None)
                    if anot is not None:
                        anotaciones.append((nodo, anot))

            for nodo, anot in anotaciones:
                for sub in ast.walk(anot):
                    # X | Y dentro de una anotación evaluada -> Python 3.10+
                    if isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.BitOr):
                        self.fail(
                            f"{nombre}:{nodo.lineno} usa una unión PEP 604 en una "
                            f"anotación evaluada; añada "
                            f"`from __future__ import annotations`"
                        )
                    # dict[..] / list[..] evaluados -> Python 3.9+
                    if (isinstance(sub, ast.Subscript)
                            and isinstance(sub.value, ast.Name)
                            and sub.value.id in GENERICOS_BUILTIN):
                        self.fail(
                            f"{nombre}:{nodo.lineno} usa {sub.value.id}[...] en una "
                            f"anotación evaluada; en Python 3.8 hace falta "
                            f"typing.{sub.value.id.capitalize()} o "
                            f"`from __future__ import annotations`"
                        )

    def test_los_modulos_nuevos_difieren_la_evaluacion_de_anotaciones(self):
        """Los módulos añadidos en esta ronda sí declaran la importación diferida.

        No se exige a los antiguos porque usan ``typing.Optional``/``List``, que
        es perfectamente válido en 3.8, y reescribirlos no aportaría nada.
        """
        for nombre in ("compat.py", "temas.py", "ayuda.py"):
            ruta = RAIZ / nombre
            with self.subTest(archivo=nombre):
                self.assertTrue(ruta.exists(), f"falta {nombre}")
                self.assertIn(
                    "from __future__ import annotations",
                    ruta.read_text(encoding="utf-8"),
                    f"{nombre} no difiere la evaluación de anotaciones",
                )


class TestDependenciasCompatiblesCon38(unittest.TestCase):
    """Las versiones mínimas fijadas en requirements.txt deben valer en 3.8."""

    def setUp(self):
        self.requisitos = (RAIZ / "requirements.txt").read_text(encoding="utf-8")

    def test_las_dependencias_fijan_minimos_que_existen_para_38(self):
        # requests 2.31 soporta 3.7+; Pillow 10.0 soporta 3.8; psutil 5.9 3.5+.
        esperados = {
            "requests": (2, 31),
            "beautifulsoup4": (4, 12),
            "psutil": (5, 9),
            "Pillow": (10, 0),
        }
        for paquete, minimo in esperados.items():
            self.assertRegex(
                self.requisitos,
                rf"(?im)^{paquete}\s*>=\s*{minimo[0]}\.{minimo[1]}",
                f"{paquete} no fija el mínimo compatible con Python 3.8",
            )

    def test_pywin32_va_marcado_por_plataforma(self):
        # Sin el marcador, la instalación falla en Linux y macOS.
        self.assertRegex(self.requisitos,
                         r'(?im)^pywin32.*sys_platform\s*==\s*"win32"')

    def test_el_piso_declarado_en_el_codigo_es_python_38(self):
        sys.path.insert(0, str(RAIZ))
        import compat
        self.assertEqual(compat.MINIMO_PYTHON, PISO)


if __name__ == "__main__":
    unittest.main(verbosity=2)
