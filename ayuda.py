"""Ayuda visual para el usuario final.

Separa el **contenido** de la ayuda (datos puros, sin tkinter, por tanto
comprobables en el CI sin entorno gráfico) de su **presentación** (la clase
:class:`ToolTip` y los textos que consume la pestaña «Ayuda» de la GUI).

``tkinter`` se importa de forma opcional: si no está instalado el contenido
sigue siendo importable y testeable, y solo la construcción de widgets falla con
un mensaje claro.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

try:  # pragma: no cover - depende del entorno
    import tkinter as tk

    TKINTER_DISPONIBLE = True
except ImportError:  # pragma: no cover - entornos sin tkinter
    tk = None  # type: ignore[assignment]
    TKINTER_DISPONIBLE = False


# ---------------------------------------------------------------------------
# Guía paso a paso
# ---------------------------------------------------------------------------
PASOS_GUIA: Tuple[Tuple[str, str], ...] = (
    (
        "Conecte la unidad afectada",
        "Inserte la memoria USB o el disco externo. La aplicación la detecta en un "
        "segundo como máximo y la lista en la pestaña «Reparación Unidades». "
        "No se repara nada de forma automática: usted decide siempre.",
    ),
    (
        "Revise el diagnóstico",
        "Cada unidad muestra un estado. Solo «Firma confirmada» permite reparar. "
        "«Sospechosa» significa que la estructura se parece pero está incompleta, "
        "y «Requiere revisión» que hay contenido que la herramienta no reconoce y "
        "no va a tocar.",
    ),
    (
        "Haga copia de seguridad si puede",
        "La restauración copia y verifica con SHA-256 antes de borrar nada, pero un "
        "medio físicamente dañado puede fallar a mitad. Si los datos importan, "
        "cópielos antes a otro sitio.",
    ),
    (
        "Pulse «Reparar» y confirme",
        "Aparecerá un resumen exacto de lo que se va a hacer. Lea el cuadro de "
        "confirmación: indica qué archivos se restauran y cuáles se eliminan.",
    ),
    (
        "Compruebe el resultado",
        "La barra de progreso y el registro detallan cada archivo restaurado, cada "
        "suma SHA-256 verificada y cualquier incidencia. Revise la raíz de la "
        "unidad: sus archivos deben estar ahí.",
    ),
)

# ---------------------------------------------------------------------------
# Leyenda de estados (color + icono + texto: no depender solo del color)
# ---------------------------------------------------------------------------
# Cada estado lleva un símbolo textual además del color para que la información
# siga siendo legible en impresoras en blanco y negro y para personas con
# daltonismo.
# ---------------------------------------------------------------------------
# Estados de unidad: fuente única de verdad
# ---------------------------------------------------------------------------
# El texto que aparece en la tabla de unidades, su icono, su color semántico y
# el tag de Treeview salen todos de esta tabla. Antes cada sitio tenía su propia
# cadena escrita a mano y la leyenda acabó describiendo estados que la pantalla
# nunca mostraba ("Limpia" frente a "Sin firma detectada", "Inaccesible" frente
# a "No accesible"). Derivar todo de aquí hace imposible que vuelvan a divergir.
#
# Campos: clave, texto_visible, icono, tono (clave de paleta), tag, descripcion
ESTADOS_UNIDAD: Tuple[Tuple[str, str, str, str, str, str], ...] = (
    ("sin_unidad", "Sin unidad", "—", "texto_suave", "",
     "Fila de espera: todavía no hay ninguna unidad conectada al equipo."),

    ("limpia", "Sin firma detectada", "✓", "exito", "",
     "No se encontró la estructura del malware. No hay nada que hacer."),

    ("confirmada", "Firma confirmada", "⚠", "advertencia", "infectada",
     "Se encontró la firma completa (5.dat, 6.dat, 7.dat y un fichero numérico "
     "sin extensión). La unidad puede repararse de forma segura."),

    ("sospechosa", "Revisión manual requerida", "⚠", "error", "sospechosa",
     "La estructura coincide en parte pero está incompleta. La aplicación no "
     "modifica nada: abra la unidad y revise el contenido usted mismo."),

    ("inaccesible", "No accesible", "⛔", "error", "inaccesible",
     "No se pudo leer la unidad. Pruebe con otro puerto USB, otro cable o "
     "compruebe los permisos."),

    ("solo_diagnostico", "Solo diagnóstico (disco interno/red)", "ℹ", "info",
     "diagnostico",
     "Es un disco interno o una unidad de red. Se muestra para que vea su "
     "estado, pero la reparación está bloqueada a propósito para no dañar el "
     "sistema."),

    ("reparada", "Reparada", "✔", "exito", "reparada",
     "La restauración terminó y la unidad ya no muestra la firma del malware."),

    ("con_errores", "Completada con errores", "◐", "advertencia", "con_errores",
     "Se restauró lo posible, pero quedaron restos que no se borraron a la "
     "fuerza. Revise la unidad antes de dar el trabajo por terminado."),
)

_INDICE_ESTADOS = {estado[0]: estado for estado in ESTADOS_UNIDAD}


def texto_estado(clave: str) -> str:
    """Texto tal y como se muestra en la tabla: icono + descripción corta."""
    estado = _INDICE_ESTADOS.get(clave)
    if estado is None:
        return clave
    _, texto, icono, _tono, _tag, _desc = estado
    return f"{icono} {texto}" if icono and icono != "—" else texto


def tag_estado(clave: str) -> str:
    """Tag de Treeview asociado al estado (cadena vacía si no lleva ninguno)."""
    estado = _INDICE_ESTADOS.get(clave)
    return estado[4] if estado else ""


def tono_estado(clave: str) -> str:
    """Clave de paleta con el color semántico del estado."""
    estado = _INDICE_ESTADOS.get(clave)
    return estado[3] if estado else "texto_suave"


def descripcion_estado(clave: str) -> str:
    """Explicación larga del estado, para la pestaña de ayuda."""
    estado = _INDICE_ESTADOS.get(clave)
    return estado[5] if estado else ""


def claves_estado() -> Tuple[str, ...]:
    """Todas las claves de estado conocidas, en el orden de la leyenda."""
    return tuple(estado[0] for estado in ESTADOS_UNIDAD)


# Texto legible de los estados finales de una reparación. El valor del enum
# ("completado_con_errores") es una cadena de máquina pensada para el log
# interno y no debería asomar en la interfaz ni en la barra de estado.
ESTADOS_REPARACION: Dict[str, str] = {
    "pendiente": "En espera",
    "en_progreso": "Reparación en curso",
    "completado": "Reparación completada",
    "completado_con_errores": "Completada con errores",
    "fallido": "Reparación fallida",
    "sin_infeccion": "Sin firma de infección",
    "requiere_revision": "Requiere revisión manual",
}


def texto_reparacion(valor: str) -> str:
    """Traduce el valor del enum ``EstadoReparacion`` a texto para el usuario."""
    if not valor:
        return ""
    return ESTADOS_REPARACION.get(str(valor), str(valor).replace("_", " "))


# La leyenda se deriva del catálogo: no puede contradecir a la tabla.
LEYENDA_ESTADOS: Tuple[Tuple[str, str, str, str], ...] = tuple(
    (texto, icono, tono, descripcion)
    for _clave, texto, icono, tono, _tag, descripcion in ESTADOS_UNIDAD
)

# ---------------------------------------------------------------------------
# Estructura de la firma USB
# ---------------------------------------------------------------------------
ESTRUCTURA_FIRMA = """[Unidad]:\\
└── Kaspersky\\            ← carpeta que suplanta al antivirus
    └── Usb Drive\\        ← aquí quedan OCULTOS sus archivos originales
        ├── documento.docx    ← SU CONTENIDO (se restaura a la raíz)
        ├── fotos\\            ← SU CONTENIDO (se restaura a la raíz)
        └── 3.0\\
            ├── 1337          ← fichero NUMÉRICO SIN EXTENSIÓN  ╮
            ├── 5.dat         ←                                │  firma
            ├── 6.dat         ←                                │  exacta
            └── 7.dat         ←                                ╯"""

REGLAS_FIRMA: Tuple[str, ...] = (
    "La firma exige los tres archivos 5.dat, 6.dat y 7.dat **y** al menos un "
    "fichero de nombre puramente numérico y sin extensión (0, 1337, 20240517…).",
    "Si faltan piezas, la unidad se marca como «Sospechosa» y no se modifica.",
    "Una carpeta llamada «Kaspersky» por sí sola NO es prueba de infección.",
    "Un directorio llamado 1234 no cuenta como firma: solo archivos regulares.",
)

# ---------------------------------------------------------------------------
# Qué hace cada botón
# ---------------------------------------------------------------------------
ACCIONES_BOTONES: Tuple[Tuple[str, str], ...] = (
    ("Escanear EACoreServer",
     "Busca las 52 rutas históricas donde se ha visto EACoreServer.exe y dice si el "
     "archivo existe y si hay un proceso en ejecución. No borra nada."),
    ("Refrescar Unidades USB",
     "Vuelve a enumerar las unidades inmediatamente, sin esperar al siguiente "
     "ciclo de detección automática."),
    ("Reparar",
     "Restaura sus archivos desde Kaspersky\\Usb Drive a la raíz de la unidad, "
     "verificando cada copia con SHA-256, y elimina solo los ficheros de firma."),
    ("Reparar Todas las Unidades",
     "Repara una a una todas las unidades con firma confirmada. Pide confirmación "
     "global antes de empezar."),
    ("Finalizar Proceso",
     "Termina el proceso EACoreServer.exe en ejecución. No elimina el archivo."),
    ("Detener y Eliminar EACoreService",
     "Detiene el servicio, lo deshabilita para que no se reinicie solo y borra "
     "EACoreServer.exe, EACore.dat y EACore.dll de C:\\ProgramData\\EACoreService."),
    ("Cancelar",
     "Interrumpe la reparación en curso. Los archivos ya verificados se conservan; "
     "los que estaban a medio copiar quedan en su sitio original."),
    ("Exportar Log",
     "Guarda el registro completo en un archivo de texto para adjuntarlo a una "
     "consulta de soporte."),
)

# ---------------------------------------------------------------------------
# Avisos de seguridad
# ---------------------------------------------------------------------------
NOTAS_SEGURIDAD: Tuple[str, ...] = (
    "EACoreServer.exe fue distribuido legítimamente por EA/Origin y por juegos de "
    "EA. Un nombre de archivo, una ruta histórica o una carpeta «Kaspersky» no "
    "demuestran por sí solos una infección.",
    "Antes de eliminar un ejecutable, valide su firma digital, su origen y su "
    "contexto. Las rutas típicas de EA/Origin quedan protegidas contra el borrado "
    "por nombre.",
    "Esta herramienta no sustituye a Microsoft Defender ni a un antivirus con "
    "firmas actualizadas. Es un complemento para un caso concreto.",
    "La restauración nunca sobrescribe: ante una colisión crea un nombre con "
    "sufijo (archivo_1, archivo_2…).",
    "Nunca se usa borrado recursivo forzoso sobre contenido no reconocido. Lo que "
    "la herramienta no identifica, lo conserva y lo registra.",
    "Los enlaces simbólicos dentro de la unidad no se siguen: así un enlace no "
    "puede usarse para escribir fuera del USB.",
)

# ---------------------------------------------------------------------------
# Preguntas frecuentes
# ---------------------------------------------------------------------------
PREGUNTAS_FRECUENTES: Tuple[Tuple[str, str], ...] = (
    (
        "¿La unidad aparece pero no me deja repararla?",
        "Solo se pueden reparar medios extraíbles o USB físicos. Los discos "
        "internos y las unidades de red aparecen para diagnóstico pero con la "
        "acción bloqueada, para evitar daños en el sistema.",
    ),
    (
        "¿Dice «Sospechosa» y no hace nada?",
        "Es el comportamiento correcto: faltan piezas de la firma. Revisar a mano "
        "es más seguro que borrar por parecido. Copie sus datos manualmente si los "
        "ve accesibles.",
    ),
    (
        "¿Perderé archivos durante la reparación?",
        "El diseño lo evita: cada archivo se copia, se fuerza su escritura a disco "
        "y se compara su SHA-256 con el original. Solo si coinciden se retira el "
        "origen. Si la copia falla, el original permanece intacto y se registra el "
        "incidente.",
    ),
    (
        "¿Quedó contenido dentro de Kaspersky tras reparar?",
        "Significa que había algo que la herramienta no reconoció y prefirió "
        "conservar. El estado será «Completada con errores» y el registro indicará "
        "la carpeta. Revíselo y bórrelo usted si confirma que es basura.",
    ),
    (
        "¿Funciona en mi sistema operativo?",
        "Windows Vista, 7, 8, 8.1, 10 y 11 en x86 y x64; macOS; Linux; y BSD, "
        "Solaris y AIX con detección conservadora de medios. Consulte la sección "
        "«Sistema» de esta ayuda para ver el detalle exacto de su equipo.",
    ),
    (
        "¿En Windows 7 no arranca?",
        "Windows 7, 8 y Vista requieren Python 3.8 exactamente: desde Python 3.9 "
        "el intérprete ya no arranca en esos sistemas. En Windows 7 hace falta "
        "además el update KB2533623. Windows 8.1 admite hasta Python 3.12.",
    ),
)

# ---------------------------------------------------------------------------
# Textos emergentes (tooltips) por control
# ---------------------------------------------------------------------------
TOOLTIPS: Dict[str, str] = {
    "escanear": "Busca EACoreServer.exe en las 52 rutas históricas conocidas. "
                "Solo diagnostica: no elimina nada.",
    "finalizar": "Termina el proceso EACoreServer.exe seleccionado. El archivo "
                 "permanece en disco.",
    "finalizar_todos": "Termina todos los procesos EACoreServer.exe activos.",
    "detener_servicio": "Detiene y deshabilita el servicio EACoreService, y borra "
                        "EACoreServer.exe, EACore.dat y EACore.dll de ProgramData.",
    "refrescar": "Vuelve a listar las unidades conectadas ahora mismo.",
    "reparar": "Restaura sus archivos y elimina la firma del malware. Siempre pide "
               "confirmación antes de tocar nada.",
    "reparar_todas": "Repara todas las unidades con firma confirmada, una por una.",
    "cancelar": "Interrumpe la reparación en curso. Lo ya verificado se conserva.",
    "analizar": "Diagnostica la unidad sin modificar ningún archivo.",
    "exportar_log": "Guarda el registro completo en un archivo de texto.",
    "tema": "Cambia la paleta de colores. La elección se recuerda entre sesiones.",
    "acento": "Personaliza el color de acento. Los tonos derivados y el color del "
              "texto se recalculan solos para mantener la legibilidad.",
    "letra": "Ajusta el tamaño del texto de toda la interfaz.",
    "ayuda": "Abre esta guía: pasos, leyenda de estados, firma USB y avisos de "
             "seguridad.",
    "tabla_procesos": "Rutas examinadas. Verde: archivo presente. Rojo: proceso en "
                      "ejecución. Amarillo: posible componente legítimo de EA.",
    "tabla_usb": "Unidades detectadas. Solo las extraíbles o USB físicos admiten "
                 "reparación.",
    "registro": "Todas las acciones quedan aquí con marca de tiempo, incluido cada "
                "SHA-256 verificado.",
    "progreso": "Progreso de la reparación en curso.",
}


def obtener_texto_ayuda(nombre: str) -> str:
    """Devuelve el texto de ayuda de un control, o cadena vacía si no existe."""
    return TOOLTIPS.get(nombre, "")


# ---------------------------------------------------------------------------
# Información del sistema para la pestaña de ayuda
# ---------------------------------------------------------------------------
def obtener_info_sistema() -> List[Tuple[str, str]]:
    """Pares (campo, valor) con el retrato del equipo donde se ejecuta la app."""
    try:
        import compat
    except Exception as exc:  # pragma: no cover - defensivo
        return [("Plataforma", f"no se pudo detectar ({exc})")]

    try:
        info = compat.obtener_info_plataforma()
    except Exception as exc:  # pragma: no cover - defensivo
        return [("Plataforma", f"no se pudo detectar ({exc})")]

    datos = [
        ("Sistema", info.nombre_amigable),
        ("Familia", info.familia),
        ("Arquitectura", f"{info.arquitectura} · proceso de {info.bits_proceso} bits"),
        ("Python", info.python_version),
        ("Nivel de soporte", info.nivel_soporte),
    ]
    if info.motivo:
        datos.append(("Nota", info.motivo))
    if info.es_windows:
        maximo = compat.python_maximo_para_windows()
        if maximo:
            datos.append(("Python máximo en este Windows", f"{maximo[0]}.{maximo[1]}"))
        if compat.es_proceso_32_en_so_64():
            datos.append(("WOW64", "intérprete de 32 bits sobre Windows de 64 bits"))
    return datos


# ---------------------------------------------------------------------------
# Tooltips
# ---------------------------------------------------------------------------
class ToolTip:
    """Ayuda emergente al pasar el ratón, sin dependencias externas.

    Funciona en Windows, macOS, Linux y BSD con el tkinter estándar. Usa una
    ventana ``Toplevel`` sin decoraciones que aparece tras un retardo breve y
    desaparece al salir del control, al pulsar o al perder el foco.
    """

    RETARDO_MS = 450
    DESFASE_X = 14
    DESFASE_Y = 18

    def __init__(self, widget, texto: str) -> None:
        if not TKINTER_DISPONIBLE:
            raise RuntimeError("tkinter no está disponible en este entorno")
        if not texto:
            raise ValueError("El tooltip necesita un texto")
        self.widget = widget
        self.texto = texto
        self._ventana = None
        self._temporizador = None
        widget.bind("<Enter>", self._programar, add="+")
        widget.bind("<Leave>", self._ocultar, add="+")
        widget.bind("<ButtonPress>", self._ocultar, add="+")
        widget.bind("<Destroy>", self._al_destruir, add="+")

    # -- ciclo de vida ----------------------------------------------------
    def _programar(self, _evento=None) -> None:
        self._cancelar_temporizador()
        self._temporizador = self.widget.after(self.RETARDO_MS, self._mostrar)

    def _cancelar_temporizador(self) -> None:
        if self._temporizador is not None:
            try:
                self.widget.after_cancel(self._temporizador)
            except Exception:
                pass
            self._temporizador = None

    def _mostrar(self) -> None:
        if self._ventana is not None:
            return
        try:
            if not self.widget.winfo_exists():
                return
            x = self.widget.winfo_rootx() + self.DESFASE_X
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + self.DESFASE_Y

            ventana = tk.Toplevel(self.widget)
            ventana.wm_overrideredirect(True)
            ventana.wm_geometry(f"+{x}+{y}")
            ventana.attributes("-topmost", True)

            marco = tk.Frame(ventana, highlightthickness=1)
            marco.pack()
            etiqueta = tk.Label(
                marco, text=self.texto, justify="left", wraplength=340,
                padx=9, pady=6,
            )
            etiqueta.pack()

            self._ventana = ventana
            self._marco = marco
            self._etiqueta = etiqueta
            self.aplicar_colores()
        except Exception:
            # Un tooltip nunca debe romper la interfaz.
            self._ventana = None

    def _ocultar(self, _evento=None) -> None:
        self._cancelar_temporizador()
        if self._ventana is not None:
            try:
                self._ventana.destroy()
            except Exception:
                pass
            self._ventana = None

    def _al_destruir(self, _evento=None) -> None:
        self._ocultar()

    # -- integración con el tema -----------------------------------------
    def aplicar_colores(self, fondo: str = "#2d3748", frente: str = "#f2f4f8",
                        borde: str = "#4a5568") -> None:
        """Recolorea el tooltip si está visible; útil al cambiar de tema."""
        self._colores = (fondo, frente, borde)
        if self._ventana is None:
            return
        try:
            self._etiqueta.configure(background=fondo, foreground=frente)
            self._marco.configure(background=fondo, highlightbackground=borde)
            self._ventana.configure(background=fondo)
        except Exception:
            pass

    @property
    def colores(self) -> Tuple[str, str, str]:
        return getattr(self, "_colores", ("#2d3748", "#f2f4f8", "#4a5568"))


def asignar_tooltip(widget, clave_o_texto: str) -> "ToolTip | None":
    """Crea un tooltip a partir de una clave de :data:`TOOLTIPS` o de texto libre."""
    if not TKINTER_DISPONIBLE:
        return None
    texto = TOOLTIPS.get(clave_o_texto, clave_o_texto)
    if not texto:
        return None
    try:
        return ToolTip(widget, texto)
    except Exception:
        return None
