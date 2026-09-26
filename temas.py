"""Motor de temas y color de la interfaz.

Contiene toda la lógica de color **sin importar tkinter**, de modo que las
paletas, el contraste y la derivación del color de acento pueden probarse en el
CI de Ubuntu, macOS y Windows sin necesidad de un entorno gráfico.

Qué ofrece
----------
* Cinco paletas con nombre (Grafito Oscuro, Claro Neutro, Azul Corporativo,
  Esmeralda y Alto Contraste) más el seguimiento del tema del sistema.
* Color de acento elegido por el usuario, del que se derivan automáticamente los
  tonos claros, oscuros y de selección, y el color de texto legible sobre él.
* Escala de tamaño de letra (Pequeño, Normal, Grande, Muy grande).
* Validación de contraste según WCAG 2.1 para que ninguna combinación quede
  ilegible.
"""

from __future__ import annotations

import os
import platform
import subprocess
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Claves que toda paleta debe definir. La GUI las consume por nombre, así que
# una paleta incompleta se detecta aquí y no en tiempo de ejecución.
# ---------------------------------------------------------------------------
CLAVES_PALETA: Tuple[str, ...] = (
    "bg", "frame", "panel", "panel_alt", "header", "borde",
    "fg", "texto_suave", "acento", "acento_suave", "acento_oscuro",
    "exito", "error", "advertencia", "info", "blanco", "negro",
    "tree_bg", "tree_fg", "field", "log_bg", "log_fg", "status_bg",
    "activo_bg", "inactivo_bg", "seleccion", "tooltip_bg", "tooltip_fg",
)

# Contraste mínimo exigido por WCAG 2.1 nivel AA para texto normal.
CONTRASTE_MINIMO_AA = 4.5
# Para texto grande (18 pt o 14 pt en negrita) WCAG permite 3:1.
CONTRASTE_MINIMO_TEXTO_GRANDE = 3.0


# ---------------------------------------------------------------------------
# Utilidades de color
# ---------------------------------------------------------------------------
def hex_a_rgb(color: str) -> Tuple[int, int, int]:
    """Convierte ``#rrggbb`` (o ``#rgb``) en una tupla de enteros 0-255."""
    texto = (color or "").strip().lstrip("#")
    if len(texto) == 3:
        texto = "".join(c * 2 for c in texto)
    if len(texto) != 6:
        raise ValueError(f"Color hexadecimal no válido: {color!r}")
    return int(texto[0:2], 16), int(texto[2:4], 16), int(texto[4:6], 16)


def rgb_a_hex(rojo: int, verde: int, azul: int) -> str:
    """Convierte enteros 0-255 en ``#rrggbb`` minúsculo."""
    limitar = lambda v: max(0, min(255, int(round(v))))  # noqa: E731
    return f"#{limitar(rojo):02x}{limitar(verde):02x}{limitar(azul):02x}"


def mezclar(color_a: str, color_b: str, proporcion: float) -> str:
    """Mezcla dos colores. ``proporcion=0`` devuelve A y ``1`` devuelve B."""
    ra, ga, ba = hex_a_rgb(color_a)
    rb, gb, bb = hex_a_rgb(color_b)
    p = max(0.0, min(1.0, proporcion))
    return rgb_a_hex(ra + (rb - ra) * p, ga + (gb - ga) * p, ba + (bb - ba) * p)


def aclarar(color: str, proporcion: float) -> str:
    """Aclara un color mezclándolo con blanco."""
    return mezclar(color, "#ffffff", proporcion)


def recortar_proporcion(proporcion: float) -> float:
    """Recorta una proporción al rango 0-1."""
    return max(0.0, min(1.0, float(proporcion)))


def oscurecer(color: str, proporcion: float) -> str:
    """Oscurece un color mezclándolo con negro."""
    return mezclar(color, "#000000", recortar_proporcion(proporcion))


def luminancia_relativa(color: str) -> float:
    """Luminancia relativa según la definición de WCAG 2.1."""
    canales = []
    for componente in hex_a_rgb(color):
        normalizado = componente / 255.0
        canales.append(
            normalizado / 12.92
            if normalizado <= 0.03928
            else ((normalizado + 0.055) / 1.055) ** 2.4
        )
    rojo, verde, azul = canales
    return 0.2126 * rojo + 0.7152 * verde + 0.0722 * azul


def ratio_contraste(color_a: str, color_b: str) -> float:
    """Ratio de contraste WCAG entre dos colores, de 1:1 a 21:1."""
    lum_a = luminancia_relativa(color_a)
    lum_b = luminancia_relativa(color_b)
    claro, oscuro = max(lum_a, lum_b), min(lum_a, lum_b)
    return (claro + 0.05) / (oscuro + 0.05)


def color_texto_legible(fondo: str) -> str:
    """Devuelve negro o blanco, el que mejor contraste dé sobre ``fondo``.

    Garantiza que un acento elegido por el usuario nunca produzca texto ilegible
    (por ejemplo, amarillo con texto blanco).
    """
    return "#ffffff" if ratio_contraste("#ffffff", fondo) >= ratio_contraste("#000000", fondo) else "#000000"


def es_color_valido(color: str) -> bool:
    """Comprueba que una cadena sea un color hexadecimal aceptable."""
    try:
        hex_a_rgb(color)
        return True
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Paletas
# ---------------------------------------------------------------------------
PALETAS: Dict[str, Dict[str, str]] = {
    # Oscuro refinado, con acento azul vivo y buena separación de superficies.
    "oscuro": {
        "bg": "#1b1d23", "frame": "#24262e", "panel": "#20222a", "panel_alt": "#282b34",
        "header": "#2d3748", "borde": "#3a3f4b",
        "fg": "#e6e8ee", "texto_suave": "#a7adbb", "acento": "#4f8cff",
        "acento_suave": "#2b3d63", "acento_oscuro": "#2f6ad6",
        "exito": "#35d07f", "error": "#ff6b60", "advertencia": "#f5a623", "info": "#49b6d6",
        "blanco": "#ffffff", "negro": "#000000",
        "tree_bg": "#20222a", "tree_fg": "#e6e8ee", "field": "#262932",
        "log_bg": "#171920", "log_fg": "#d7dae2", "status_bg": "#24262e",
        "activo_bg": "#5c2f2c", "inactivo_bg": "#55472a", "seleccion": "#2f4a7a",
        "tooltip_bg": "#2d3748", "tooltip_fg": "#f2f4f8",
    },
    # Claro neutro, estilo herramienta profesional de escritorio.
    "claro": {
        "bg": "#f5f6f8", "frame": "#ffffff", "panel": "#ffffff", "panel_alt": "#eef0f4",
        "header": "#2c3e50", "borde": "#d3d8e0",
        "fg": "#1c1e21", "texto_suave": "#5a6270", "acento": "#1f6feb",
        "acento_suave": "#d6e4fb", "acento_oscuro": "#1657bd",
        "exito": "#1a7f37", "error": "#cf222e", "advertencia": "#9a6700", "info": "#0b6e99",
        "blanco": "#ffffff", "negro": "#000000",
        "tree_bg": "#ffffff", "tree_fg": "#1c1e21", "field": "#ffffff",
        "log_bg": "#ffffff", "log_fg": "#1c1e21", "status_bg": "#e8eaef",
        "activo_bg": "#ffe3e0", "inactivo_bg": "#fff2cf", "seleccion": "#cfe2ff",
        "tooltip_bg": "#2c3e50", "tooltip_fg": "#ffffff",
    },
    # Azul corporativo: serio, alto contraste y acento institucional.
    "azul": {
        "bg": "#eaeff7", "frame": "#ffffff", "panel": "#f4f7fc", "panel_alt": "#e2eaf6",
        "header": "#0b3d91", "borde": "#c3d2ea",
        "fg": "#0f2140", "texto_suave": "#4a5f80", "acento": "#0b6bcb",
        "acento_suave": "#cfe2fb", "acento_oscuro": "#084e96",
        "exito": "#0f7b4f", "error": "#b3261e", "advertencia": "#8a5b00", "info": "#0b6e99",
        "blanco": "#ffffff", "negro": "#000000",
        "tree_bg": "#ffffff", "tree_fg": "#0f2140", "field": "#ffffff",
        "log_bg": "#fbfcfe", "log_fg": "#0f2140", "status_bg": "#dce6f5",
        "activo_bg": "#ffdcd8", "inactivo_bg": "#ffedcc", "seleccion": "#bcd8f7",
        "tooltip_bg": "#0b3d91", "tooltip_fg": "#ffffff",
    },
    # Esmeralda: llamativo pero sobrio, útil para distinguir estados.
    "esmeralda": {
        "bg": "#e9f5ef", "frame": "#ffffff", "panel": "#f3faf6", "panel_alt": "#e0f1e8",
        "header": "#0f5132", "borde": "#bcdccd",
        "fg": "#10281d", "texto_suave": "#4a6155", "acento": "#0f9d6e",
        "acento_suave": "#cdeedd", "acento_oscuro": "#0a7452",
        "exito": "#12805c", "error": "#b3261e", "advertencia": "#8a5b00", "info": "#0b6e99",
        "blanco": "#ffffff", "negro": "#000000",
        "tree_bg": "#ffffff", "tree_fg": "#10281d", "field": "#ffffff",
        "log_bg": "#fbfefc", "log_fg": "#10281d", "status_bg": "#d8ece1",
        "activo_bg": "#ffdcd8", "inactivo_bg": "#ffedcc", "seleccion": "#bfe6d2",
        "tooltip_bg": "#0f5132", "tooltip_fg": "#ffffff",
    },
    # Alto contraste para accesibilidad: cumple AAA en todos los textos.
    "contraste": {
        "bg": "#000000", "frame": "#0c0c0c", "panel": "#050505", "panel_alt": "#151515",
        "header": "#000000", "borde": "#ffffff",
        "fg": "#ffffff", "texto_suave": "#e8e8e8", "acento": "#ffff00",
        "acento_suave": "#3a3a00", "acento_oscuro": "#cccc00",
        "exito": "#00ff7f", "error": "#ff5555", "advertencia": "#ffd700", "info": "#66d9ff",
        "blanco": "#ffffff", "negro": "#000000",
        "tree_bg": "#000000", "tree_fg": "#ffffff", "field": "#000000",
        "log_bg": "#000000", "log_fg": "#ffffff", "status_bg": "#0c0c0c",
        "activo_bg": "#4d0f0f", "inactivo_bg": "#4d3b00", "seleccion": "#000080",
        "tooltip_bg": "#ffff00", "tooltip_fg": "#000000",
    },
}

# Nombres mostrados en el menú, en el orden preferido.
NOMBRES_PALETAS: Dict[str, str] = {
    "oscuro": "Grafito Oscuro",
    "claro": "Claro Neutro",
    "azul": "Azul Corporativo",
    "esmeralda": "Verde Esmeralda",
    "contraste": "Alto Contraste",
    "sistema": "Seguir al Sistema",
}

PALETA_POR_DEFECTO = "oscuro"

# Colores de acento predefinidos para el selector rápido.
ACENTOS_SUGERIDOS: Tuple[str, ...] = (
    "#4f8cff",  # Azul vivo
    "#0b6bcb",  # Azul institucional
    "#0f9d6e",  # Esmeralda
    "#7c4dff",  # Violeta
    "#e0559b",  # Magenta
    "#e8590c",  # Naranja
    "#c62828",  # Rojo
    "#00838f",  # Cian profundo
)

# ---------------------------------------------------------------------------
# Escalas de letra
# ---------------------------------------------------------------------------
ESCALAS_FUENTE: Dict[str, float] = {
    "pequena": 0.90,
    "normal": 1.00,
    "grande": 1.15,
    "enorme": 1.30,
}

NOMBRES_ESCALAS: Dict[str, str] = {
    "pequena": "Pequeño",
    "normal": "Normal",
    "grande": "Grande",
    "enorme": "Muy grande",
}

ESCALA_POR_DEFECTO = "normal"


def tamano_fuente(base: int, escala: str) -> int:
    """Aplica la escala de letra elegida por el usuario a un tamaño base."""
    factor = ESCALAS_FUENTE.get(escala, 1.0)
    return max(6, int(round(base * factor)))


# ---------------------------------------------------------------------------
# Detección del tema del sistema
# ---------------------------------------------------------------------------
def detectar_tema_sistema() -> str:
    """Detecta si el sistema usa tema claro u oscuro.

    * **Windows**: ``AppsUseLightTheme`` en el registro de personalización.
    * **macOS**: ``defaults read -g AppleInterfaceStyle`` (existe solo en oscuro).
    * **Linux**: ``color-scheme`` de GNOME vía ``gsettings``, con respaldo en el
      nombre del tema GTK.
    Ante cualquier fallo devuelve el tema oscuro, que es el predeterminado.
    """
    sistema = platform.system().lower()

    if os.name == "nt" or sistema.startswith("win"):
        try:
            import winreg

            clave = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            try:
                valor, _ = winreg.QueryValueEx(clave, "AppsUseLightTheme")
                return "claro" if valor else "oscuro"
            finally:
                winreg.CloseKey(clave)
        except Exception:
            return PALETA_POR_DEFECTO

    if sistema == "darwin":
        try:
            salida = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, text=True, timeout=5, check=False,
            )
            if salida.returncode == 0 and "dark" in salida.stdout.strip().lower():
                return "oscuro"
            # La clave solo existe cuando el tema es oscuro; si falta, es claro.
            return "claro"
        except Exception:
            return PALETA_POR_DEFECTO

    # Linux y BSD: intentar GNOME y luego GTK.
    for comando, oscuro_si in (
        (["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"], "prefer-dark"),
        (["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"], "dark"),
    ):
        try:
            salida = subprocess.run(comando, capture_output=True, text=True,
                                    timeout=5, check=False)
            if salida.returncode == 0 and salida.stdout.strip():
                return "oscuro" if oscuro_si in salida.stdout.strip().lower() else "claro"
        except Exception:
            continue
    return PALETA_POR_DEFECTO


def resolver_nombre_paleta(tema: str) -> str:
    """Resuelve ``sistema`` al tema real y valida nombres desconocidos."""
    if tema == "sistema":
        return detectar_tema_sistema()
    return tema if tema in PALETAS else PALETA_POR_DEFECTO


# ---------------------------------------------------------------------------
# Construcción de paletas con acento personalizado
# ---------------------------------------------------------------------------
def construir_paleta(
    nombre: str,
    acento_personalizado: Optional[str] = None,
) -> Dict[str, str]:
    """Devuelve una paleta completa, opcionalmente reacentuada.

    Si se pasa ``acento_personalizado``, se recalculan los tonos derivados
    (claro, oscuro, selección y texto sobre acento) para que combinen con la
    paleta base en lugar de chocar con ella.
    """
    resuelto = resolver_nombre_paleta(nombre)
    base = dict(PALETAS.get(resuelto, PALETAS[PALETA_POR_DEFECTO]))
    base["_paleta"] = resuelto

    if acento_personalizado and es_color_valido(acento_personalizado):
        acento = acento_personalizado.strip()
        fondo = base["bg"]
        es_fondo_oscuro = luminancia_relativa(fondo) < 0.4

        base["acento"] = acento
        base["acento_oscuro"] = oscurecer(acento, 0.25)
        base["acento_suave"] = (
            mezclar(acento, fondo, 0.75) if es_fondo_oscuro else mezclar(acento, fondo, 0.85)
        )
        base["seleccion"] = mezclar(acento, fondo, 0.55 if es_fondo_oscuro else 0.70)
        # El texto sobre el acento se elige por contraste, no a mano.
        base["blanco"] = "#ffffff"
        base["texto_sobre_acento"] = color_texto_legible(acento)
        # Los colores semánticos se conservan: rojo sigue siendo error aunque el
        # acento también sea rojizo, para no perder el significado del estado.
        if ratio_contraste(base["error"], acento) < 1.2:
            base["error"] = aclarar(base["error"], 0.25) if es_fondo_oscuro else oscurecer(base["error"], 0.25)
    else:
        base["texto_sobre_acento"] = color_texto_legible(base["acento"])

    return base


def validar_paleta(paleta: Dict[str, str]) -> List[str]:
    """Devuelve la lista de problemas de una paleta; vacía si es correcta."""
    problemas: List[str] = []

    for clave in CLAVES_PALETA:
        if clave not in paleta:
            problemas.append(f"falta la clave {clave!r}")
        elif not es_color_valido(paleta[clave]):
            problemas.append(f"{clave!r} no es un color válido: {paleta[clave]!r}")

    if problemas:
        return problemas

    pares_texto = (
        ("fg", "bg", "texto principal"),
        ("fg", "panel", "texto sobre panel"),
        ("tree_fg", "tree_bg", "texto de tabla"),
        ("log_fg", "log_bg", "texto del registro"),
        ("texto_suave", "bg", "texto secundario"),
        ("blanco", "header", "texto de cabecera"),
        ("tooltip_fg", "tooltip_bg", "texto de ayuda emergente"),
    )
    for frente, fondo, descripcion in pares_texto:
        ratio = ratio_contraste(paleta[frente], paleta[fondo])
        if ratio < CONTRASTE_MINIMO_AA:
            problemas.append(
                f"contraste insuficiente en {descripcion}: {ratio:.2f}:1 "
                f"({paleta[frente]} sobre {paleta[fondo]}), mínimo {CONTRASTE_MINIMO_AA}:1"
            )
    return problemas


def listar_paletas() -> List[Tuple[str, str]]:
    """Pares ``(clave, nombre visible)`` en el orden del menú."""
    orden = ["oscuro", "claro", "azul", "esmeralda", "contraste", "sistema"]
    return [(clave, NOMBRES_PALETAS[clave]) for clave in orden if clave in NOMBRES_PALETAS]


def listar_escalas() -> List[Tuple[str, str]]:
    """Pares ``(clave, nombre visible)`` de tamaño de letra."""
    orden = ["pequena", "normal", "grande", "enorme"]
    return [(clave, NOMBRES_ESCALAS[clave]) for clave in orden if clave in NOMBRES_ESCALAS]


# ---------------------------------------------------------------------------
# Familias de letra por plataforma
# ---------------------------------------------------------------------------
# "Segoe UI" solo existe en Windows y "Consolas" tampoco está en macOS/Linux; si
# se piden a ciegas, tkinter degrada a una fuente genérica de aspecto pobre. Se
# lista una preferencia por sistema y la GUI elige la primera que exista.
FUENTES_PREFERIDAS: Dict[str, Tuple[str, ...]] = {
    "windows": ("Segoe UI", "Tahoma", "DejaVu Sans", "Arial"),
    "darwin": (".AppleSystemUIFont", "Helvetica Neue", "Helvetica", "DejaVu Sans"),
    "linux": ("DejaVu Sans", "Ubuntu", "Cantarell", "Noto Sans", "Liberation Sans"),
    "bsd": ("DejaVu Sans", "Liberation Sans", "Noto Sans", "Helvetica"),
    "sunos": ("DejaVu Sans", "Liberation Sans", "Helvetica"),
    "aix": ("DejaVu Sans", "Helvetica", "Liberation Sans"),
    "desconocida": ("DejaVu Sans", "Arial", "Helvetica"),
}

FUENTES_MONO_PREFERIDAS: Dict[str, Tuple[str, ...]] = {
    "windows": ("Cascadia Mono", "Consolas", "Lucida Console", "Courier New"),
    "darwin": ("Menlo", "Monaco", "SF Mono", "Courier New"),
    "linux": ("DejaVu Sans Mono", "Ubuntu Mono", "Liberation Mono", "Courier New"),
    "bsd": ("DejaVu Sans Mono", "Liberation Mono", "Courier New"),
    "sunos": ("DejaVu Sans Mono", "Courier New"),
    "aix": ("DejaVu Sans Mono", "Courier New"),
    "desconocida": ("DejaVu Sans Mono", "Courier New"),
}


def familia_de_claves() -> str:
    """Clave de plataforma usada para elegir las familias de letra."""
    try:
        import compat

        familia = compat.obtener_familia_posix()
    except Exception:
        familia = "desconocida"
    if familia == "windows":
        return "windows"
    return familia if familia in FUENTES_PREFERIDAS else "desconocida"


def fuentes_preferidas() -> Tuple[str, ...]:
    """Familias de letra proporcionales, en orden de preferencia."""
    return FUENTES_PREFERIDAS.get(familia_de_claves(), FUENTES_PREFERIDAS["desconocida"])


def fuentes_mono_preferidas() -> Tuple[str, ...]:
    """Familias monoespaciadas, en orden de preferencia."""
    return FUENTES_MONO_PREFERIDAS.get(
        familia_de_claves(), FUENTES_MONO_PREFERIDAS["desconocida"]
    )


def elegir_fuente(disponibles, preferidas: Tuple[str, ...], respaldo: str) -> str:
    """Devuelve la primera familia preferida que exista en el sistema.

    Es una función pura: recibe la lista de familias disponibles y no toca
    tkinter, de modo que puede probarse en el CI sin entorno gráfico. La
    comparación ignora mayúsculas porque algunos backends las normalizan.
    """
    disponibles_norm = {str(nombre).strip().lower(): str(nombre).strip()
                        for nombre in (disponibles or ())}
    for candidata in preferidas:
        encontrada = disponibles_norm.get(candidata.strip().lower())
        if encontrada:
            return encontrada
    return respaldo
