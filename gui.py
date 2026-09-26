"""
Interfaz gráfica de la aplicación Antivirus EACoreServer.
Todo el texto está en español. Usa tkinter para la interfaz.
"""

import json
import os
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, simpledialog
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from scraper import obtener_rutas_candidatas
from process_manager import obtener_gestor_procesos, InfoRutaEACore, EstadoProceso
from usb_monitor import (
    obtener_monitor_usb, UnidadExtraible,
    es_unidad_reparada, marcar_unidad_reparada, obtener_unidades_reparadas,
)
from repair_engine import (
    obtener_motor_reparacion,
    EstadoDeteccion,
    EstadoReparacion,
    ResultadoReparacion,
)
import ayuda
import compat
import temas
from logger import obtener_logger

logger = obtener_logger()


# ---------------------------------------------------------------------------
# Configuración persistente (tema de la interfaz)
# ---------------------------------------------------------------------------
_ARCHIVO_CONFIG = Path.home() / "Antivirus_EACoreServer_Logs" / "config.json"


def _cargar_config() -> dict:
    """Carga el archivo de configuración persistente."""
    try:
        if _ARCHIVO_CONFIG.exists():
            with open(_ARCHIVO_CONFIG, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _guardar_config(config: dict) -> None:
    """Guarda el archivo de configuración persistente."""
    try:
        _ARCHIVO_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        with open(_ARCHIVO_CONFIG, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# Las paletas, el contraste WCAG y la derivación del color de acento viven en
# temas.py, que no depende de tkinter y por tanto es comprobable en el CI.
PALETAS = temas.PALETAS


class AntivirusGUI:
    """Interfaz gráfica principal de la aplicación antivirus."""
    
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Antivirus EACoreServer - Protección USB y Procesos")

        # Si ejecutar_aplicacion ya ajustó y centró la ventana (flag explícito),
        # respetarla; si no, usar un tamaño seguro.
        if not getattr(root, "_geometria_controlada", False):
            self.root.geometry("1280x780")

        # Tamaño mínimo acorde a la pantalla para no ocultar la barra de estado inferior
        w_area = max(self.root.winfo_screenwidth() - 20, 640)
        h_area = max(self.root.winfo_screenheight() - 60, 480)
        self.root.minsize(min(1000, w_area), min(650, h_area))
        
        # Estado de la aplicación
        self._proceso_en_ejecucion = False
        self._cancelar_reparacion = False
        self._ultimo_conteo_usb = -1
        # Fuente de verdad de la tabla: evita leer widgets tkinter desde un
        # hilo de trabajo al finalizar procesos.
        self._resultados_procesos: List[InfoRutaEACore] = []
        
        # Apariencia persistente: paleta, color de acento y tamaño de letra.
        # Los valores guardados se validan contra el catálogo actual para que una
        # configuración antigua o corrupta no rompa el arranque.
        config = _cargar_config()

        tema_guardado = config.get("tema", "sistema")
        self._tema_seleccion = (
            tema_guardado if tema_guardado in temas.PALETAS or tema_guardado == "sistema"
            else temas.PALETA_POR_DEFECTO
        )
        self._tema_var = tk.StringVar(value=self._tema_seleccion)

        acento_guardado = (config.get("acento") or "").strip()
        self._acento_seleccion = (
            acento_guardado if temas.es_color_valido(acento_guardado) else None
        )
        self._acento_var = tk.StringVar(value=self._acento_seleccion or "")

        escala_guardada = config.get("escala_letra", temas.ESCALA_POR_DEFECTO)
        self._escala_seleccion = (
            escala_guardada if escala_guardada in temas.ESCALAS_FUENTE
            else temas.ESCALA_POR_DEFECTO
        )
        self._escala_var = tk.StringVar(value=self._escala_seleccion)

        # Tooltips registrados, para recolorearlos al cambiar de tema.
        self._tooltips: List["ayuda.ToolTip"] = []
        self._paleta: dict = {}

        # Unidades cuya reparación terminó con errores. Sin este registro la
        # tabla volvería a mostrarlas como «Sin firma detectada» y el usuario
        # daría por bueno un trabajo que quedó a medias.
        self._unidades_con_errores: set = {
            str(letra) for letra in (config.get("unidades_con_errores") or [])
        }
        
        # Configuración de estilo
        self._configurar_estilos()
        
        # Crear interfaz
        self._crear_menu()
        self._crear_interfaz()
        
        # Aplicar tema guardado (reconfigura estilos y colores de widgets)
        self._aplicar_tema(self._tema_seleccion)
        
        # Logger de ventana
        self._agregar_log("Aplicación Antivirus EACoreServer iniciada.", "INFO")
        self._agregar_log("Esperando detección de unidades (USB, discos y red)...", "INFO")
        
        # Iniciar monitor USB
        self._iniciar_monitor_usb()

        # Guía breve la primera vez; se recuerda en config.json
        self.root.after(350, self._mostrar_bienvenida)

    
    def _configurar_estilos(self) -> None:
        """Configura los estilos ttk base con la paleta resuelta."""
        self._inicializar_fuentes()
        style = ttk.Style()
        style.theme_use("clam")
        self._aplicar_estilos_tema(self._paleta_actual())

    def _inicializar_fuentes(self) -> None:
        """Elige las familias de letra que existen realmente en este sistema.

        «Segoe UI» y «Consolas» solo están en Windows; pedirlos a ciegas en macOS
        o Linux degrada a una fuente genérica. Se consulta a tkinter y se toma la
        primera familia disponible de la lista de preferencia.
        """
        try:
            from tkinter import font as tkfont

            disponibles = tuple(tkfont.families(self.root))
        except Exception:
            disponibles = ()
        self._fuente_base = temas.elegir_fuente(
            disponibles, temas.fuentes_preferidas(), "TkDefaultFont"
        )
        self._fuente_mono_base = temas.elegir_fuente(
            disponibles, temas.fuentes_mono_preferidas(), "TkFixedFont"
        )
        logger.debug(
            f"Fuentes elegidas: {self._fuente_base} / {self._fuente_mono_base}"
        )

    def _fuente(self, base: int, negrita: bool = False) -> tuple:
        """Fuente proporcional con la escala elegida por el usuario."""
        return (self._fuente_base,
                temas.tamano_fuente(base, self._escala_seleccion),
                "bold" if negrita else "normal")

    def _fuente_mono(self, base: int, negrita: bool = False) -> tuple:
        """Fuente monoespaciada con la escala elegida por el usuario."""
        return (self._fuente_mono_base,
                temas.tamano_fuente(base, self._escala_seleccion),
                "bold" if negrita else "normal")

    def _paleta_actual(self) -> dict:
        """Resuelve la paleta efectiva combinando tema y acento personalizado."""
        return temas.construir_paleta(self._tema_seleccion, self._acento_seleccion)

    def _detectar_tema_sistema(self) -> str:
        """Detecta el tema claro/oscuro del sistema. Ver :mod:`temas`."""
        return temas.detectar_tema_sistema()

    def _aplicar_estilos_tema(self, p: dict) -> None:
        """Aplica una paleta a todos los estilos ttk."""
        style = ttk.Style()
        style.theme_use("clam")

        # Etiquetas generales
        style.configure("Title.TLabel", font=self._fuente(16, True),
                        foreground=p["acento"], background=p["header"])
        style.configure("Subtitle.TLabel", font=self._fuente(10),
                        foreground=p["texto_suave"], background=p["bg"])
        style.configure("Status.TLabel", font=self._fuente(10),
                        foreground=p["fg"], background=p["status_bg"])
        style.configure("Header.TLabel", font=self._fuente(11, True),
                        foreground=p["blanco"], background=p["header"])
        style.configure("Header.TFrame", background=p["header"])

        # Estados semánticos: color + símbolo, para no depender solo del color
        style.configure("Green.TLabel", foreground=p["exito"], font=self._fuente(10, True),
                        background=p["bg"])
        style.configure("Red.TLabel", foreground=p["error"], font=self._fuente(10, True),
                        background=p["bg"])
        style.configure("Yellow.TLabel", foreground=p["advertencia"], font=self._fuente(10, True),
                        background=p["bg"])
        style.configure("Info.TLabel", foreground=p["info"], font=self._fuente(10, True),
                        background=p["bg"])
        style.configure("Muted.TLabel", foreground=p["texto_suave"],
                        font=self._fuente(9), background=p["bg"])

        # Superficies: tres niveles para dar profundidad sin saturar
        style.configure("TFrame", background=p["bg"])
        style.configure("Panel.TFrame", background=p["panel"])
        style.configure("PanelAlt.TFrame", background=p["panel_alt"])
        style.configure("TLabelframe", background=p["bg"], foreground=p["fg"],
                        bordercolor=p["borde"])
        style.configure("TLabelframe.Label", background=p["bg"], foreground=p["acento"],
                        font=self._fuente(10, True))

        # Botones
        style.configure("TButton", font=self._fuente(10, True), background=p["frame"],
                        foreground=p["fg"], borderwidth=1, bordercolor=p["borde"],
                        padding=(10, 5))
        style.map("TButton",
                  background=[("active", p["acento_suave"]), ("pressed", p["acento_oscuro"])],
                  foreground=[("active", p["fg"]), ("pressed", p["texto_sobre_acento"])])
        # Los botones de acción usan el acento elegido por el usuario y un color
        # de texto calculado por contraste, nunca fijo en blanco.
        for estilo in ("Action.TButton", "Repair.TButton", "Stop.TButton"):
            color = {"Action.TButton": p["acento"],
                     "Repair.TButton": p["exito"],
                     "Stop.TButton": p["error"]}[estilo]
            style.configure(estilo, background=color,
                            foreground=temas.color_texto_legible(color),
                            borderwidth=0, padding=(12, 6))
            style.map(estilo,
                      background=[("active", temas.aclarar(color, 0.18)),
                                  ("disabled", temas.mezclar(color, p["bg"], 0.55))],
                      foreground=[("active", temas.color_texto_legible(temas.aclarar(color, 0.18)))])

        # Pestañas
        style.configure("TNotebook", background=p["bg"], borderwidth=0, tabmargins=(4, 4, 4, 0))
        style.configure("TNotebook.Tab", background=p["frame"], foreground=p["texto_suave"],
                        font=self._fuente(10, True), padding=(14, 7), bordercolor=p["borde"])
        style.map("TNotebook.Tab",
                  background=[("selected", p["acento"])],
                  foreground=[("selected", p["texto_sobre_acento"])],
                  expand=[("selected", (0, 0, 0, 2))])

        # Barra de progreso
        style.configure("TProgressbar", thickness=temas.tamano_fuente(20, self._escala_seleccion),
                        troughcolor=p["frame"], background=p["acento"],
                        bordercolor=p["borde"], lightcolor=p["acento"], darkcolor=p["acento"])

        # Separadores
        style.configure("TSeparator", background=p["borde"])

        # Treeview
        style.configure("Custom.Treeview",
                        rowheight=temas.tamano_fuente(26, self._escala_seleccion),
                        font=self._fuente_mono(9),
                        background=p["tree_bg"], foreground=p["tree_fg"],
                        fieldbackground=p["field"], borderwidth=1, bordercolor=p["borde"])
        style.configure("Custom.Treeview.Heading", font=self._fuente(9, True),
                        background=p["header"], foreground=p["blanco"],
                        bordercolor=p["borde"])
        style.map("Custom.Treeview",
                  background=[("selected", p["seleccion"])],
                  foreground=[("selected", p["fg"])])
        style.map("Custom.Treeview.Heading",
                  background=[("active", p["acento_oscuro"])])

        # Barras de desplazamiento
        style.configure("Vertical.TScrollbar", background=p["frame"], troughcolor=p["bg"],
                        arrowcolor=p["fg"], bordercolor=p["borde"])
        style.configure("Horizontal.TScrollbar", background=p["frame"], troughcolor=p["bg"],
                        arrowcolor=p["fg"], bordercolor=p["borde"])

        # Combos y campos
        style.configure("TCombobox", fieldbackground=p["field"], background=p["frame"],
                        foreground=p["fg"], arrowcolor=p["fg"], bordercolor=p["borde"])
        style.configure("TCheckbutton", background=p["bg"], foreground=p["fg"])
        style.map("TCheckbutton", background=[("active", p["bg"])])
        style.configure("TRadiobutton", background=p["bg"], foreground=p["fg"])
        style.map("TRadiobutton", background=[("active", p["bg"])])

    def _recolorear_widgets(self, p: dict) -> None:
        """Reaplica colores a widgets no gestionados por ttk."""
        self.root.configure(bg=p["bg"])

        if hasattr(self, "log_text"):
            self.log_text.configure(
                bg=p["log_bg"], fg=p["log_fg"], insertbackground=p["acento"],
                selectbackground=p["seleccion"], selectforeground=p["fg"],
                font=self._fuente_mono(9),
            )
            # Tags semánticos del registro
            self.log_text.tag_configure("INFO", foreground=p["info"])
            self.log_text.tag_configure("WARNING", foreground=p["advertencia"])
            self.log_text.tag_configure("ERROR", foreground=p["error"])
            self.log_text.tag_configure("CRITICAL", foreground=p["error"])
            self.log_text.tag_configure("EXITO", foreground=p["exito"])

        if hasattr(self, "lbl_subtitulo"):
            self.lbl_subtitulo.configure(foreground=p["texto_suave"], font=self._fuente(9))
        if hasattr(self, "lbl_reparadas"):
            self.lbl_reparadas.configure(foreground=p["fg"])
        if hasattr(self, "lbl_plataforma"):
            self.lbl_plataforma.configure(foreground=p["texto_suave"], font=self._fuente(9))

        # Tags de la tabla de procesos
        if hasattr(self, "tree_procesos"):
            self.tree_procesos.tag_configure("activo", background=p["activo_bg"])
            self.tree_procesos.tag_configure("inactivo", background=p["inactivo_bg"])
            self.tree_procesos.tag_configure("legitimo", background=p["acento_suave"])

        # Tags de la tabla USB: uno por estado del catálogo de ayuda. El fondo es
        # un tinte del color semántico sobre el de la tabla, calibrado para que el
        # texto siga cumpliendo contraste WCAG AA en las cinco paletas.
        if hasattr(self, "tree_usb"):
            for clave_estado in ayuda.claves_estado():
                tag = ayuda.tag_estado(clave_estado)
                if not tag:
                    continue
                tinte = temas.mezclar(p[ayuda.tono_estado(clave_estado)],
                                      p["tree_bg"], 0.78)
                self.tree_usb.tag_configure(tag, background=tinte)

        # Ayuda y tooltips
        if hasattr(self, "_tooltips"):
            for tooltip in self._tooltips:
                tooltip.aplicar_colores(p["tooltip_bg"], p["tooltip_fg"], p["borde"])
        if hasattr(self, "ayuda_text"):
            self.ayuda_text.configure(
                bg=p["panel"], fg=p["fg"], insertbackground=p["acento"],
                selectbackground=p["seleccion"], font=self._fuente(10),
            )
            self._recolorear_tags_ayuda(p)

    def _recolorear_tags_ayuda(self, p: dict) -> None:
        """Colorea los estilos de texto de la pestaña de ayuda."""
        if not hasattr(self, "ayuda_text"):
            return
        for etiqueta, color, peso in (
            ("titulo", p["acento"], "bold"),
            ("subtitulo", p["fg"], "bold"),
            ("cuerpo", p["fg"], "normal"),
            ("suave", p["texto_suave"], "normal"),
            ("exito", p["exito"], "bold"),
            ("error", p["error"], "bold"),
            ("advertencia", p["advertencia"], "bold"),
            ("info", p["info"], "bold"),
            ("mono", p["fg"], "normal"),
            ("aviso", p["advertencia"], "bold"),
        ):
            fuente = self._fuente_mono(9) if etiqueta == "mono" else self._fuente(
                12 if etiqueta == "titulo" else 10, peso == "bold"
            )
            self.ayuda_text.tag_configure(etiqueta, foreground=color, font=fuente)

    def _aplicar_tema(self, tema: str) -> None:
        """Aplica una paleta y guarda la preferencia."""
        if tema not in temas.PALETAS and tema != "sistema":
            tema = temas.PALETA_POR_DEFECTO
        self._tema_seleccion = tema
        self._tema_var.set(tema)
        self._refrescar_apariencia()
        self._persistir_apariencia()

        resuelto = temas.resolver_nombre_paleta(tema)
        logger.info(f"Tema aplicado: {temas.NOMBRES_PALETAS.get(tema, tema)} (resuelto: {resuelto})")

    def _aplicar_acento(self, acento: str) -> None:
        """Aplica un color de acento personalizado y lo guarda."""
        if acento and not temas.es_color_valido(acento):
            logger.warning(f"Color de acento no válido: {acento!r}")
            return
        self._acento_seleccion = acento or None
        self._acento_var.set(acento or "")
        self._refrescar_apariencia()
        self._persistir_apariencia()
        logger.info(f"Color de acento aplicado: {acento or 'el de la paleta'}")

    def _aplicar_escala(self, escala: str) -> None:
        """Aplica un tamaño de letra y lo guarda."""
        if escala not in temas.ESCALAS_FUENTE:
            escala = temas.ESCALA_POR_DEFECTO
        self._escala_seleccion = escala
        self._escala_var.set(escala)
        self._refrescar_apariencia()
        self._persistir_apariencia()
        logger.info(f"Tamaño de letra aplicado: {temas.NOMBRES_ESCALAS[escala]}")

    def _refrescar_apariencia(self) -> None:
        """Recalcula la paleta y la vuelca en estilos y widgets."""
        paleta = self._paleta_actual()
        self._paleta = paleta
        problemas = temas.validar_paleta(paleta)
        for problema in problemas:
            logger.warning(f"Paleta con contraste mejorable: {problema}")
        self._aplicar_estilos_tema(paleta)
        self._recolorear_widgets(paleta)

    def _persistir_apariencia(self) -> None:
        """Guarda tema, acento y tamaño de letra entre sesiones."""
        config = _cargar_config()
        config["tema"] = self._tema_seleccion
        config["acento"] = self._acento_seleccion or ""
        config["escala_letra"] = self._escala_seleccion
        _guardar_config(config)

    def _crear_menu(self) -> None:
        """Crea la barra de menú, incluidos apariencia y ayuda."""
        menubar = tk.Menu(self.root)

        menu_archivo = tk.Menu(menubar, tearoff=0)
        menu_archivo.add_command(label="Exportar Log", command=self._exportar_log)
        menu_archivo.add_separator()
        menu_archivo.add_command(label="Salir", command=self._salir, accelerator="Ctrl+Q")
        menubar.add_cascade(label="Archivo", menu=menu_archivo)

        menu_herramientas = tk.Menu(menubar, tearoff=0)
        menu_herramientas.add_command(label="Escanear EACoreServer", command=self._escanear_rutas)
        menu_herramientas.add_command(label="Reparar Todas las Unidades", command=self._reparar_todas_usb)
        menu_herramientas.add_separator()
        menu_herramientas.add_command(label="Refrescar Unidades USB", command=self._refrescar_unidades)
        menu_herramientas.add_separator()
        menu_herramientas.add_command(
            label="Detener y Eliminar EACoreService (exe + .dat + .dll)",
            command=self._eliminar_servicio_programdata)
        menubar.add_cascade(label="Herramientas", menu=menu_herramientas)

        menu_ver = tk.Menu(menubar, tearoff=0)
        menu_ver.add_cascade(label="Tema", menu=self._crear_menu_temas(menubar))
        menu_ver.add_cascade(label="Color de acento", menu=self._crear_menu_acento(menubar))
        menu_ver.add_cascade(label="Tamaño de letra", menu=self._crear_menu_escala(menubar))
        menu_ver.add_separator()
        menu_ver.add_command(label="Restablecer apariencia", command=self._restablecer_apariencia)
        menubar.add_cascade(label="Ver", menu=menu_ver)

        menu_ayuda = tk.Menu(menubar, tearoff=0)
        menu_ayuda.add_command(label="Guía de uso", command=self._abrir_guia,
                               accelerator="F1")
        menu_ayuda.add_command(label="Comprobar compatibilidad del sistema",
                               command=self._mostrar_compatibilidad)
        menu_ayuda.add_separator()
        menu_ayuda.add_command(label="Acerca de", command=self._acerca_de)
        menubar.add_cascade(label="Ayuda", menu=menu_ayuda)

        self.root.config(menu=menubar)
        self.root.bind("<Control-q>", lambda e: self._salir())
        self.root.bind("<F1>", lambda e: self._abrir_guia())
        self.root.bind("<Control-h>", lambda e: self._abrir_guia())

    def _crear_menu_temas(self, padre) -> tk.Menu:
        """Selector de paletas con nombre."""
        menu = tk.Menu(padre, tearoff=0)
        for clave, nombre in temas.listar_paletas():
            # La muestra de color hace reconocible la paleta sin abrirla.
            muestra = "" if clave == "sistema" else f"   ● {temas.PALETAS[clave]['acento']}"
            menu.add_radiobutton(
                label=f"{nombre}{muestra}", value=clave, variable=self._tema_var,
                command=lambda c=clave: self._aplicar_tema(c),
            )
        return menu

    def _crear_menu_acento(self, padre) -> tk.Menu:
        """Selector de color de acento, con opción personalizada."""
        menu = tk.Menu(padre, tearoff=0)
        menu.add_radiobutton(
            label="El de la paleta (recomendado)", value="", variable=self._acento_var,
            command=lambda: self._aplicar_acento(""),
        )
        menu.add_separator()
        for color in temas.ACENTOS_SUGERIDOS:
            menu.add_radiobutton(
                label=f"   ● {color}", value=color, variable=self._acento_var,
                command=lambda c=color: self._aplicar_acento(c),
            )
        menu.add_separator()
        menu.add_command(label="Color personalizado…", command=self._elegir_acento_dialogo)
        return menu

    def _crear_menu_escala(self, padre) -> tk.Menu:
        """Selector de tamaño de letra."""
        menu = tk.Menu(padre, tearoff=0)
        for clave, nombre in temas.listar_escalas():
            menu.add_radiobutton(
                label=nombre, value=clave, variable=self._escala_var,
                command=lambda c=clave: self._aplicar_escala(c),
            )
        return menu

    def _elegir_acento_dialogo(self) -> None:
        """Abre el selector nativo de color para el acento."""
        try:
            from tkinter import colorchooser

            inicial = self._acento_seleccion or self._paleta_actual()["acento"]
            _, hexadecimal = colorchooser.askcolor(color=inicial, title="Color de acento")
        except Exception as exc:
            logger.warning(f"Selector de color no disponible: {exc}")
            messagebox.showinfo(
                "Selector de color",
                "Este sistema no ofrece selector de color gráfico.\n"
                "Puede indicar el valor hexadecimal en Ver → Color de acento.",
            )
            return
        if hexadecimal:
            self._aplicar_acento(hexadecimal)

    def _restablecer_apariencia(self) -> None:
        """Vuelve a la apariencia recomendada: tema del sistema y letra normal."""
        self._acento_seleccion = None
        self._acento_var.set("")
        self._escala_seleccion = temas.ESCALA_POR_DEFECTO
        self._escala_var.set(temas.ESCALA_POR_DEFECTO)
        self._aplicar_tema("sistema")
        logger.info("Apariencia restablecida a los valores recomendados")

    def _crear_interfaz(self) -> None:
        """Crea la interfaz principal con pestañas."""
        # Frame principal
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Cabecera con título, acceso directo a la ayuda y sistema detectado
        titulo_frame = ttk.Frame(main_frame, style="Header.TFrame")
        titulo_frame.pack(fill="x", pady=(0, 3))

        ttk.Label(titulo_frame, text="🛡️ Antivirus EACoreServer v1.2",
                  style="Title.TLabel").pack(side="left", padx=10, pady=4)
        self.lbl_subtitulo = ttk.Label(titulo_frame,
                                       text="Protección USB  |  Gestión de Procesos",
                                       style="Subtitle.TLabel")
        self.lbl_subtitulo.pack(side="left", padx=6)

        # Botón de ayuda siempre visible: el usuario no tiene que buscarlo en el menú.
        self.btn_ayuda = ttk.Button(titulo_frame, text="  ❔ Ayuda  ",
                                    style="Action.TButton", command=self._abrir_guia)
        self.btn_ayuda.pack(side="right", padx=10, pady=4)
        self._registrar_tooltip(self.btn_ayuda, "ayuda")

        ttk.Separator(main_frame, orient="horizontal").pack(fill="x", pady=(0, 3))

        # Notebook (pestañas)
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Pestaña 1: EACoreServer Proceso
        self._crear_pestana_procesos()

        # Pestaña 2: Reparación de Unidades
        self._crear_pestana_usb()

        # Pestaña 3: Log
        self._crear_pestana_log()

        # Pestaña 4: Ayuda visual para el usuario final
        self._crear_pestana_ayuda()

        # Barra de estado
        self._crear_barra_estado()

    def _crear_pestana_ayuda(self) -> None:
        """Crea la pestaña de ayuda visual con guía, leyenda y avisos."""
        self.tab_ayuda = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_ayuda, text="  ❔ Ayuda  ")

        contenedor = ttk.Frame(self.tab_ayuda)
        contenedor.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        cabecera = ttk.Frame(contenedor)
        cabecera.pack(fill="x", pady=(0, 6))
        ttk.Label(cabecera, text="Guía visual de uso",
                  style="Title.TLabel").pack(side="left")
        ttk.Button(cabecera, text="Comprobar mi sistema",
                   style="Action.TButton",
                   command=self._mostrar_compatibilidad).pack(side="right", padx=4)
        ttk.Button(cabecera, text="Imprimir / exportar guía",
                   command=self._exportar_guia).pack(side="right", padx=4)

        # Un único Text desplazable: permite maquetar títulos, listas, tabla de
        # leyenda y el diagrama monoespaciado de la firma sin añadir widgets.
        marco = ttk.Frame(contenedor, style="Panel.TFrame")
        marco.pack(fill=tk.BOTH, expand=True)

        self.ayuda_text = tk.Text(
            marco, wrap="word", relief="flat", padx=16, pady=14,
            spacing1=2, spacing3=4, cursor="arrow",
        )
        barra = ttk.Scrollbar(marco, orient="vertical", command=self.ayuda_text.yview)
        self.ayuda_text.configure(yscrollcommand=barra.set, state="normal")
        barra.pack(side="right", fill="y")
        self.ayuda_text.pack(side="left", fill=tk.BOTH, expand=True)

        self._volcar_contenido_ayuda()
        self.ayuda_text.configure(state="disabled")

        pie = ttk.Label(contenedor,
                        text="Consejo: pase el ratón por encima de cualquier botón "
                             "para ver una explicación breve. Pulse F1 en cualquier "
                             "momento para volver a esta guía.",
                        style="Muted.TLabel", justify="left")
        pie.pack(fill="x", pady=(6, 0))

    def _volcar_contenido_ayuda(self) -> None:
        """Escribe la ayuda estructurada en el widget de texto."""
        texto = self.ayuda_text
        texto.configure(state="normal")
        texto.delete("1.0", "end")

        def escribir(contenido: str, etiqueta: str = "cuerpo") -> None:
            texto.insert("end", contenido + "\n", etiqueta)

        def espacio(lineas: int = 1) -> None:
            for _ in range(lineas):
                texto.insert("end", "\n", "cuerpo")

        escribir("Cómo usar Antivirus EACoreServer", "titulo")
        escribir("Esta herramienta diagnostica y repara unidades USB afectadas por la "
                 "estructura falsa Kaspersky\\Usb Drive, y gestiona procesos llamados "
                 "EACoreServer.exe. Está pensada para ser conservadora: nunca borra lo "
                 "que no reconoce.", "suave")
        espacio()

        escribir("1. Pasos recomendados", "subtitulo")
        for numero, (titulo, detalle) in enumerate(ayuda.PASOS_GUIA, 1):
            escribir(f"   {numero}.  {titulo}", "info")
            for linea in self._ajustar_texto(detalle, 88):
                escribir(f"        {linea}", "cuerpo")
            espacio()

        escribir("2. Qué significan los estados", "subtitulo")
        escribir("   Cada estado lleva un símbolo además del color, para que se pueda "
                 "leer también impreso en blanco y negro.", "suave")
        for nombre, simbolo, tono, descripcion in ayuda.LEYENDA_ESTADOS:
            escribir(f"   {simbolo}  {nombre}", tono if tono in ("exito", "error", "advertencia") else "cuerpo")
            for linea in self._ajustar_texto(descripcion, 88):
                escribir(f"        {linea}", "suave")
        espacio()

        escribir("3. La firma que se busca en el USB", "subtitulo")
        escribir("   Solo se repara cuando aparece esta estructura completa:", "cuerpo")
        espacio()
        for linea in ayuda.ESTRUCTURA_FIRMA.splitlines():
            escribir(f"   {linea}", "mono")
        espacio()
        for regla in ayuda.REGLAS_FIRMA:
            for linea in self._ajustar_texto("•  " + regla, 92):
                escribir(f"   {linea}", "cuerpo")
        espacio()

        escribir("4. Qué hace cada botón", "subtitulo")
        for boton, descripcion in ayuda.ACCIONES_BOTONES:
            escribir(f"   ▸  {boton}", "info")
            for linea in self._ajustar_texto(descripcion, 88):
                escribir(f"        {linea}", "cuerpo")
        espacio()

        escribir("5. Avisos de seguridad importantes", "subtitulo")
        for nota in ayuda.NOTAS_SEGURIDAD:
            for linea in self._ajustar_texto("⚠  " + nota, 92):
                escribir(f"   {linea}", "aviso" if linea.startswith("⚠") else "cuerpo")
        espacio()

        escribir("6. Preguntas frecuentes", "subtitulo")
        for pregunta, respuesta in ayuda.PREGUNTAS_FRECUENTES:
            escribir(f"   ?  {pregunta}", "subtitulo")
            for linea in self._ajustar_texto(respuesta, 88):
                escribir(f"        {linea}", "cuerpo")
            espacio()

        escribir("7. Su sistema", "subtitulo")
        for campo, valor in ayuda.obtener_info_sistema():
            escribir(f"   {campo}:", "info")
            for linea in self._ajustar_texto(str(valor), 88):
                escribir(f"        {linea}", "cuerpo")

        self._recolorear_tags_ayuda(self._paleta_actual())

    @staticmethod
    def _ajustar_texto(texto: str, ancho: int) -> List[str]:
        """Parte un párrafo en líneas de como mucho ``ancho`` caracteres.

        Se hace a mano y no con ``textwrap`` para preservar los saltos que ya
        traiga el texto y no partir palabras a la mitad en el diagrama.
        """
        lineas: List[str] = []
        for parrafo in texto.split("\n"):
            palabras = parrafo.split()
            if not palabras:
                lineas.append("")
                continue
            actual = palabras[0]
            for palabra in palabras[1:]:
                if len(actual) + 1 + len(palabra) <= ancho:
                    actual += " " + palabra
                else:
                    lineas.append(actual)
                    actual = palabra
            lineas.append(actual)
        return lineas

    def _abrir_guia(self) -> None:
        """Salta a la pestaña de ayuda."""
        if hasattr(self, "tab_ayuda"):
            self.notebook.select(self.tab_ayuda)

    def _mostrar_compatibilidad(self) -> None:
        """Muestra el detalle de compatibilidad del sistema actual."""
        info = compat.obtener_info_plataforma()
        filas = ayuda.obtener_info_sistema()
        cuerpo = "\n".join(f"{campo}:\n    {valor}" for campo, valor in filas)
        nivel = {
            compat.SOPORTE_COMPLETO: "Soporte completo",
            compat.SOPORTE_DIAGNOSTICO: "Solo diagnóstico",
            compat.SOPORTE_NO_SOPORTADO: "Sistema no soportado",
        }.get(info.nivel_soporte, info.nivel_soporte)

        messagebox.showinfo(
            "Compatibilidad del sistema",
            f"{nivel}\n\n{cuerpo}\n\n"
            f"Sistemas atendidos:\n"
            f"    · Windows Vista, 7, 8, 8.1, 10 y 11 (x86 y x64)\n"
            f"    · macOS, Linux, FreeBSD, OpenBSD, NetBSD, Solaris y AIX\n\n"
            f"Windows XP y Server 2003 no son compatibles: el último Python que\n"
            f"funciona en XP es 3.4.4 (2016) y las dependencias exigen 3.8+.",
        )

    def _exportar_guia(self) -> None:
        """Guarda la guía en un archivo de texto para imprimirla o compartirla."""
        from tkinter import filedialog

        ruta = filedialog.asksaveasfilename(
            title="Exportar guía de uso",
            defaultextension=".txt",
            filetypes=[("Texto", "*.txt"), ("Todos los archivos", "*.*")],
            initialfile="guia_antivirus_eacoreserver.txt",
        )
        if not ruta:
            return
        try:
            contenido = self.ayuda_text.get("1.0", "end").rstrip()
            with open(ruta, "w", encoding="utf-8") as archivo:
                archivo.write(contenido + "\n")
            self._agregar_log(f"Guía exportada a {ruta}", "INFO")
            messagebox.showinfo("Guía exportada", f"La guía se guardó en:\n{ruta}")
        except OSError as exc:
            logger.error(f"No se pudo exportar la guía: {exc}")
            messagebox.showerror("Error al exportar", f"No se pudo guardar la guía:\n{exc}")

    def _registrar_tooltip(self, widget, clave_o_texto: str) -> None:
        """Asocia una ayuda emergente a un control y la recuerda para el tema."""
        tooltip = ayuda.asignar_tooltip(widget, clave_o_texto)
        if tooltip is not None:
            paleta = self._paleta_actual()
            tooltip.aplicar_colores(paleta["tooltip_bg"], paleta["tooltip_fg"], paleta["borde"])
            self._tooltips.append(tooltip)

    def _mostrar_bienvenida(self) -> None:
        """Asistente breve la primera vez que se abre la aplicación."""
        config = _cargar_config()
        if config.get("bienvenida_vista"):
            return
        info = compat.obtener_info_plataforma()
        mensaje = (
            "Bienvenido a Antivirus EACoreServer\n\n"
            "Esta herramienta hace tres cosas:\n\n"
            "  1.  Detecta unidades USB con la estructura falsa\n"
            "      Kaspersky\\Usb Drive y restaura sus archivos.\n"
            "  2.  Busca procesos y rutas de EACoreServer.exe.\n"
            "  3.  Registra todo lo que hace, con verificación SHA-256.\n\n"
            "Es conservadora a propósito: nunca borra contenido que no\n"
            "reconoce y siempre pide confirmación antes de reparar.\n\n"
            f"Sistema detectado: {info.nombre_amigable} ({info.arquitectura})\n"
            f"Nivel de soporte: {info.nivel_soporte}\n\n"
            "Pulse F1 en cualquier momento para abrir la guía completa.\n"
            "Puede cambiar colores y tamaño de letra en el menú Ver."
        )
        if info.motivo:
            mensaje += f"\n\nNota de compatibilidad:\n{info.motivo}"

        try:
            messagebox.showinfo("Bienvenido", mensaje)
        finally:
            config["bienvenida_vista"] = True
            _guardar_config(config)

    def _crear_pestana_procesos(self) -> None:
        """Crea la pestaña de gestión de procesos EACoreServer."""
        self.tab_procesos = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_procesos, text="  Procesos EACoreServer  ")
        
        # Frame de controles
        control_frame = ttk.Frame(self.tab_procesos)
        control_frame.pack(fill="x", pady=5)
        
        self.btn_escanear = ttk.Button(control_frame, text="Escanear Rutas",
                                       command=self._escanear_rutas, style="Action.TButton")
        self.btn_escanear.pack(side="left", padx=5)
        self._registrar_tooltip(self.btn_escanear, "escanear")

        self.btn_finalizar_todos = ttk.Button(control_frame, text="Finalizar Todos",
                                              command=self._finalizar_todos, style="Action.TButton")
        self.btn_finalizar_todos.pack(side="left", padx=5)
        self._registrar_tooltip(self.btn_finalizar_todos, "finalizar_todos")

        self.btn_refrescar_procesos = ttk.Button(control_frame, text="Refrescar",
                                                 command=self._refrescar_procesos, style="Action.TButton")
        self.btn_refrescar_procesos.pack(side="left", padx=5)
        self._registrar_tooltip(self.btn_refrescar_procesos, "refrescar")
        
        self.lbl_proceso_count = ttk.Label(control_frame, text="")
        self.lbl_proceso_count.pack(side="right", padx=10)
        
        # Tabla de rutas
        table_frame = ttk.Frame(self.tab_procesos)
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = (
            "indice", "ruta", "estado", "pid", "usuario", "tamano_kb",
            "servicio", "clasificacion", "error",
        )
        self.tree_procesos = ttk.Treeview(table_frame, columns=columns, show="headings",
                                           style="Custom.Treeview", height=15)
        self._registrar_tooltip(self.tree_procesos, "tabla_procesos")
        
        self.tree_procesos.heading("indice", text="N°")
        self.tree_procesos.heading("ruta", text="Ruta del Archivo")
        self.tree_procesos.heading("estado", text="Estado")
        self.tree_procesos.heading("pid", text="PID")
        self.tree_procesos.heading("usuario", text="Usuario")
        self.tree_procesos.heading("tamano_kb", text="Tamaño KB")
        self.tree_procesos.heading("servicio", text="Servicio")
        self.tree_procesos.heading("clasificacion", text="Confianza")
        self.tree_procesos.heading("error", text="Error")
        
        self.tree_procesos.column("indice", width=40, anchor="center")
        self.tree_procesos.column("ruta", width=350)
        self.tree_procesos.column("estado", width=100, anchor="center")
        self.tree_procesos.column("pid", width=60, anchor="center")
        self.tree_procesos.column("usuario", width=120)
        self.tree_procesos.column("tamano_kb", width=80, anchor="center")
        self.tree_procesos.column("servicio", width=100, anchor="center")
        self.tree_procesos.column("clasificacion", width=130, anchor="center")
        self.tree_procesos.column("error", width=150)
        
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree_procesos.yview)
        self.tree_procesos.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree_procesos.pack(fill=tk.BOTH, expand=True)
        
        # Frame de acciones individuales
        accion_frame = ttk.Frame(self.tab_procesos)
        accion_frame.pack(fill="x", pady=5)
        
        self.btn_finalizar_sel = ttk.Button(accion_frame, text="Finalizar Seleccionado",
                                            command=self._finalizar_seleccionado)
        self.btn_finalizar_sel.pack(side="left", padx=5)
        self._registrar_tooltip(self.btn_finalizar_sel, "finalizar")

        self.btn_finalizar_ruta = ttk.Button(accion_frame, text="Finalizar por Ruta",
                                             command=self._finalizar_por_ruta)
        self.btn_finalizar_ruta.pack(side="left", padx=5)
        self._registrar_tooltip(self.btn_finalizar_ruta, "finalizar")

        self.btn_eliminar_sel = ttk.Button(accion_frame, text="Eliminar .exe + .dat + .dll Seleccionado",
                                           style="Stop.TButton",
                                           command=self._eliminar_exe_dat_seleccionado)
        self.btn_eliminar_sel.pack(side="left", padx=5)
        self._registrar_tooltip(self.btn_eliminar_sel, "detener_servicio")
        
        # Acción excepcional para la ruta no estándar de ProgramData. Requiere
        # confirmación; el nombre EACoreServer.exe no basta para identificar malware.
        servicio_frame = ttk.Frame(self.tab_procesos)
        servicio_frame.pack(fill="x", pady=(0, 5))
        self.btn_servicio = ttk.Button(servicio_frame,
                                       text="Detener y Eliminar EACoreService (.exe + .dat + .dll)",
                                       style="Stop.TButton",
                                       command=self._eliminar_servicio_programdata)
        self.btn_servicio.pack(side="left", padx=5)
        self._registrar_tooltip(self.btn_servicio, "detener_servicio")
        ttk.Label(servicio_frame,
                  text="Detiene el servicio de C:\\ProgramData\\EACoreService y borra ambos ficheros por completo.")\
            .pack(side="left", padx=5)
    
    def _crear_pestana_usb(self) -> None:
        """Crea la pestaña de reparación de USB."""
        self.tab_usb = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_usb, text="  Reparación Unidades  ")
        
        # Frame superior - Unidades detectadas
        top_frame = ttk.Frame(self.tab_usb)
        top_frame.pack(fill="x", pady=5)
        
        ttk.Label(top_frame, text="Unidades Detectadas:",
                  font=self._fuente(10, True)).pack(anchor="w")
        
        # Lista de unidades
        list_frame = ttk.Frame(self.tab_usb)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        columns_usb = ("letra", "etiqueta", "serie", "tamano", "libre", "estado")
        self.tree_usb = ttk.Treeview(list_frame, columns=columns_usb, show="headings",
                                      style="Custom.Treeview", height=8)
        self._registrar_tooltip(self.tree_usb, "tabla_usb")
        
        self.tree_usb.heading("letra", text="Unidad")
        self.tree_usb.heading("etiqueta", text="Etiqueta")
        self.tree_usb.heading("serie", text="N° Serie")
        self.tree_usb.heading("tamano", text="Tamaño")
        self.tree_usb.heading("libre", text="Libre")
        self.tree_usb.heading("estado", text="Estado")
        
        self.tree_usb.column("letra", width=70, anchor="center")
        self.tree_usb.column("etiqueta", width=150)
        self.tree_usb.column("serie", width=90, anchor="center")
        self.tree_usb.column("tamano", width=80, anchor="center")
        self.tree_usb.column("libre", width=80, anchor="center")
        self.tree_usb.column("estado", width=150, anchor="center")
        
        self.tree_usb.pack(side="left", fill=tk.BOTH, expand=True)
        
        scrollbar_usb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree_usb.yview)
        self.tree_usb.configure(yscrollcommand=scrollbar_usb.set)
        scrollbar_usb.pack(side="right", fill="y")
        
        # Frame de controles
        control_frame = ttk.Frame(self.tab_usb)
        control_frame.pack(fill="x", pady=5)
        
        self.btn_reparar = ttk.Button(control_frame, text="Reparar Unidad Seleccionada",
                                      command=self._reparar_unidad_seleccionada,
                                      style="Repair.TButton")
        self.btn_reparar.pack(side="left", padx=5)
        self._registrar_tooltip(self.btn_reparar, "reparar")

        self.btn_reparar_todas = ttk.Button(control_frame, text="Reparar Todas",
                                            command=self._reparar_todas_usb,
                                            style="Repair.TButton")
        self.btn_reparar_todas.pack(side="left", padx=5)
        self._registrar_tooltip(self.btn_reparar_todas, "reparar_todas")

        self.btn_refrescar_usb = ttk.Button(control_frame, text="Refrescar Unidades",
                                            command=self._refrescar_unidades)
        self.btn_refrescar_usb.pack(side="left", padx=5)
        self._registrar_tooltip(self.btn_refrescar_usb, "refrescar")
        
        # Progreso
        self.progreso_var = tk.DoubleVar(value=0)
        self.progreso = ttk.Progressbar(self.tab_usb, variable=self.progreso_var, maximum=100)
        self.progreso.pack(fill="x", padx=5, pady=5)
        self._registrar_tooltip(self.progreso, "progreso")
        
        self.lbl_progreso = ttk.Label(self.tab_usb, text="Listo")
        self.lbl_progreso.pack(anchor="w", padx=5)
        
        # Contador de unidades reparadas (persistido entre sesiones)
        self.lbl_reparadas = ttk.Label(self.tab_usb, text="Unidades reparadas (guardadas): ninguna",
                                       style="Subtitle.TLabel")
        self.lbl_reparadas.pack(anchor="w", padx=5, pady=(2, 0))
    
    def _crear_pestana_log(self) -> None:
        """Crea la pestaña de registro de log."""
        self.tab_log = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_log, text="  Registro (Log)  ")
        
        # Área de texto con scroll
        # Los colores y la fuente reales los fija el tema activo; estos valores
        # iniciales solo evitan un parpadeo blanco antes de aplicar la paleta.
        self.log_text = scrolledtext.ScrolledText(
            self.tab_log, wrap=tk.WORD, font=self._fuente_mono(9),
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.log_text.configure(state=tk.DISABLED)
        self._registrar_tooltip(self.log_text, "registro")
        
        # Frame de controles de log
        log_control = ttk.Frame(self.tab_log)
        log_control.pack(fill="x", pady=5)
        
        self.btn_limpiar_log = ttk.Button(log_control, text="Limpiar Log", command=self._limpiar_log)
        self.btn_limpiar_log.pack(side="left", padx=5)

        self.btn_exportar_log = ttk.Button(log_control, text="Exportar Log", command=self._exportar_log)
        self.btn_exportar_log.pack(side="left", padx=5)
        self._registrar_tooltip(self.btn_exportar_log, "exportar_log")
    
    def _crear_barra_estado(self) -> None:
        """Crea la barra de estado inferior con el sistema detectado."""
        self.status_var = tk.StringVar(value="Iniciado - Monitoreo USB activo")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief="sunken",
                                anchor="w", style="Status.TLabel")
        status_bar.pack(side="bottom", fill="x")

        # El usuario debe poder ver de un vistazo en qué sistema y modo está.
        info = compat.obtener_info_plataforma()
        self.lbl_plataforma = ttk.Label(
            self.root, text=f"{info.nombre_amigable} · {info.arquitectura} · soporte {info.nivel_soporte}",
            anchor="e", style="Status.TLabel",
        )
        self.lbl_plataforma.pack(side="bottom", fill="x")
        self._registrar_tooltip(self.lbl_plataforma,
                                "Detalle en Ayuda → Comprobar compatibilidad del sistema")
    
    def _agregar_log(self, mensaje: str, nivel: str = "INFO") -> None:
        """Agrega un mensaje al log de la interfaz."""
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{nivel}] {mensaje}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)
    
    # ==================== FUNCIONES DE PROCESOS ====================
    
    def _escanear_rutas(self) -> None:
        """Escanea las rutas candidatas de EACoreServer."""
        if self._proceso_en_ejecucion:
            messagebox.showwarning("Aviso", "Ya hay una operación en ejecución.")
            return
        
        self._proceso_en_ejecucion = True
        self.status_var.set("Escaneando rutas de EACoreServer...")
        self._agregar_log("Iniciando escaneo de rutas EACoreServer...", "INFO")
        
        def _trabajo():
            try:
                # Obtener rutas del scraping
                rutas = obtener_rutas_candidatas()
                self.root.after(0, self._agregar_log,
                                f"Se obtuvieron {len(rutas)} rutas candidatas.", "INFO")

                # Escanear cada ruta
                gestor = obtener_gestor_procesos()
                resultados = gestor.escanear_rutas(rutas)
                
                # Actualizar tabla
                self.root.after(0, self._actualizar_tabla_procesos, resultados)
                
                activos = sum(1 for r in resultados if r.estado == EstadoProceso.ACTIVO)
                inactivos = sum(1 for r in resultados if r.estado == EstadoProceso.ENCONTRADO_INACTIVO)
                
                self.root.after(0, lambda: self._agregar_log(
                    f"Escaneo completado: {activos} activos, {inactivos} inactivos.", "INFO"))
                self.root.after(0, lambda: self.status_var.set(
                    f"Escaneo completado: {activos} activos, {inactivos} inactivos"))
            except Exception as e:
                self.root.after(0, lambda mensaje=str(e): self._agregar_log(f"Error en escaneo: {mensaje}", "ERROR"))
                self.root.after(0, lambda: self.status_var.set("Error en escaneo"))
            finally:
                self.root.after(0, lambda: setattr(self, '_proceso_en_ejecucion', False))
        
        threading.Thread(target=_trabajo, daemon=True).start()
    
    def _actualizar_tabla_procesos(self, resultados: List[InfoRutaEACore]) -> None:
        """Actualiza la tabla de procesos con los resultados (hilo principal)."""
        self._resultados_procesos = list(resultados)
        # Limpiar tabla
        for item in self.tree_procesos.get_children():
            self.tree_procesos.delete(item)
        
        for info in resultados:
            d = info.a_dict()
            tags = ()
            if d["estado"] == "activo":
                tags = ("activo",)
            elif d["estado"] == "encontrado_inactivo":
                tags = ("inactivo",)
            
            item_id = self.tree_procesos.insert("", "end", values=(
                d["indice"], d["ruta"], d["estado"], d["pid"],
                d["usuario"], d["tamano_kb"], d["servicio"],
                d["clasificacion"], d["error"]
            ), tags=tags)
        
        activos = sum(1 for r in resultados if r.estado == EstadoProceso.ACTIVO)
        self.lbl_proceso_count.config(text=f"Total: {len(resultados)} | Activos: {activos}")
    
    def _refrescar_procesos(self) -> None:
        """Refresca el escaneo de procesos."""
        self._escanear_rutas()
    
    def _finalizar_todos(self) -> None:
        """Finaliza procesos activos previamente detectados, en segundo plano."""
        if self._proceso_en_ejecucion:
            messagebox.showwarning("Aviso", "Ya hay una operación en ejecución.")
            return
        rutas_activas = [
            info.ruta for info in self._resultados_procesos
            if info.estado == EstadoProceso.ACTIVO
        ]
        if not rutas_activas:
            messagebox.showinfo("Info", "No hay procesos EACoreServer activos para finalizar.")
            return
        if not messagebox.askyesno(
            "Finalizar procesos",
            f"Se volverán a comprobar y finalizarán {len(rutas_activas)} proceso(s) activos.\n\n"
            "EACoreServer.exe puede pertenecer a EA/Origin o a un juego legítimo. "
            "No se eliminarán archivos.\n\n¿Desea continuar?",
        ):
            return

        self._proceso_en_ejecucion = True
        self.status_var.set("Finalizando procesos EACoreServer…")
        self._agregar_log("Iniciando finalización de procesos activos…", "INFO")

        def _trabajo() -> None:
            try:
                gestor = obtener_gestor_procesos()
                activos = [
                    info for info in gestor.escanear_rutas(rutas_activas)
                    if info.estado == EstadoProceso.ACTIVO
                ]
                if activos:
                    resultados = gestor.finalizar_todo(activos)
                    exitos = sum(1 for exito, _ in resultados.values() if exito)
                    self.root.after(0, self._agregar_log,
                                    f"Procesos finalizados: {exitos}/{len(activos)}.", "INFO")
                else:
                    self.root.after(0, self._agregar_log,
                                    "Los procesos ya no estaban activos.", "INFO")
                nuevos = gestor.escanear_rutas(obtener_rutas_candidatas())
                self.root.after(0, self._actualizar_tabla_procesos, nuevos)
            except Exception as exc:
                self.root.after(0, self._agregar_log,
                                f"Error finalizando procesos: {exc}", "ERROR")
            finally:
                self.root.after(0, lambda: setattr(self, "_proceso_en_ejecucion", False))
                self.root.after(0, self.status_var.set, "Finalización completada")

        threading.Thread(target=_trabajo, daemon=True).start()

    def _finalizar_seleccionado(self) -> None:
        """Finaliza el proceso seleccionado en la tabla."""
        seleccion = self.tree_procesos.selection()
        if not seleccion:
            messagebox.showwarning("Aviso", "No hay ninguna ruta seleccionada.")
            return
        
        item = seleccion[0]
        values = self.tree_procesos.item(item)["values"]
        ruta = values[1]
        estado = values[2]
        
        if estado != "activo":
            messagebox.showinfo("Info", "La ruta seleccionada no tiene un proceso activo.")
            return
        
        gestor = obtener_gestor_procesos()
        info = None
        # Buscar el InfoRutaEACore correspondiente
        # (simplificado: buscar por ruta)
        
        self._agregar_log(f"Finalizando proceso: {ruta}", "INFO")
        
        def _trabajo():
            try:
                # Recrear infos
                rutas = obtener_rutas_candidatas()
                infos = gestor.escanear_rutas(rutas)
                objetivo = next((i for i in infos if i.ruta == ruta), None)
                if objetivo and objetivo.estado == EstadoProceso.ACTIVO and objetivo.pid:
                    exito, msg = gestor.finalizar_proceso(objetivo)
                    estado_str = "Finalizado" if exito else "Error"
                    self.root.after(0, lambda: self._agregar_log(
                        f"Proceso {ruta}: {msg}", estado_str))
                    
                    # Refrescar tabla
                    nuevos = gestor.escanear_rutas(rutas)
                    self.root.after(0, lambda: self._actualizar_tabla_procesos(nuevos))
                else:
                    self.root.after(0, lambda: self._agregar_log(
                        f"El proceso ya no está activo o no se encontró.", "INFO"))
            except Exception as e:
                self.root.after(0, lambda mensaje=str(e): self._agregar_log(f"Error: {mensaje}", "ERROR"))
        
        threading.Thread(target=_trabajo, daemon=True).start()
    
    def _finalizar_por_ruta(self) -> None:
        """Finaliza un proceso por ruta específica."""
        ruta = simpledialog.askstring("Finalizar por Ruta", 
                                          "Ingrese la ruta completa de EACoreServer.exe:")
        if ruta:
            gestor = obtener_gestor_procesos()
            info = None
            try:
                rutas = obtener_rutas_candidatas()
                infos = gestor.escanear_rutas(rutas)
                info = next((i for i in infos if i.ruta.lower() == ruta.lower().strip()), None)
            except Exception:
                pass
            
            if info and info.estado == EstadoProceso.ACTIVO and info.pid:
                self._proceso_en_ejecucion = True
                def _trabajo():
                    try:
                        exito, msg = gestor.finalizar_proceso(info)
                        self.root.after(0, lambda: self._agregar_log(
                            f"Finalización de {ruta}: {msg}", "Éxito" if exito else "Error"))
                        rutas = obtener_rutas_candidatas()
                        nuevos = gestor.escanear_rutas(rutas)
                        self.root.after(0, lambda: self._actualizar_tabla_procesos(nuevos))
                    except Exception as e:
                        self.root.after(0, lambda mensaje=str(e): self._agregar_log(f"Error: {mensaje}", "ERROR"))
                    finally:
                        self.root.after(0, lambda: setattr(self, '_proceso_en_ejecucion', False))
                threading.Thread(target=_trabajo, daemon=True).start()
            else:
                messagebox.showinfo("Info", "El proceso no está activo o no se encontró.")
    
    def _eliminar_exe_dat_seleccionado(self) -> None:
        """Detiene proceso/servicio y elimina EACoreServer.exe + EACore.dat + EACore.dll de la fila seleccionada."""
        seleccion = self.tree_procesos.selection()
        if not seleccion:
            messagebox.showwarning("Aviso", "No hay ninguna ruta seleccionada.")
            return
        values = self.tree_procesos.item(seleccion[0])["values"]
        ruta = values[1]
        if not ruta or "eacoreserver.exe" not in ruta.lower():
            messagebox.showwarning("Aviso", "La fila seleccionada no corresponde a EACoreServer.exe.")
            return
        gestor = obtener_gestor_procesos()
        if gestor.ruta_probablemente_legitima(ruta):
            messagebox.showwarning(
                "Componente de EA protegido",
                "La ruta seleccionada parece pertenecer a EA/Origin o a un juego legítimo.\n\n"
                "Por seguridad, la aplicación no detendrá ni eliminará este archivo solo por su nombre. "
                "Revise la firma digital y use el desinstalador del producto si corresponde.",
            )
            return
        ruta_dat1 = os.path.join(os.path.dirname(ruta), "EACore.dat")
        ruta_dat2 = os.path.join(os.path.dirname(ruta), "EACore.dll")
        confirmar = messagebox.askyesno(
            "Eliminar archivos por completo",
            "Se detendrá el proceso/servicio asociado y se eliminarán por completo:\n\n"
            f"  {ruta}\n  {ruta_dat1}\n  {ruta_dat2}\n\n"
            "¿Desea continuar?"
        )
        if not confirmar:
            return
        self._ejecutar_trabajo_eliminacion(ruta, "fila seleccionada")
    
    def _eliminar_servicio_programdata(self) -> None:
        """Detiene el servicio EACoreService y elimina exe + dat + dll de ProgramData."""
        ruta = r"C:\ProgramData\EACoreService\EACoreServer.exe"
        if not os.path.exists(ruta):
            messagebox.showinfo(
                "Info",
                "El servicio EACoreService no está instalado en este equipo\n"
                "(no existe C:\\ProgramData\\EACoreService\\EACoreServer.exe).")
            return
        ruta_dat1 = os.path.join(os.path.dirname(ruta), "EACore.dat")
        ruta_dat2 = os.path.join(os.path.dirname(ruta), "EACore.dll")
        confirmar = messagebox.askyesno(
            "Detener y eliminar EACoreService",
            "Se detendrá y deshabilitará el servicio EACoreService y se eliminarán:\n\n"
            f"  {ruta}\n  {ruta_dat1}\n  {ruta_dat2}\n\n"
            "Nota: podría afectar a EA App / Origin hasta reiniciar el equipo.\n"
            "¿Desea continuar?"
        )
        if not confirmar:
            return
        self._ejecutar_trabajo_eliminacion(ruta, "ProgramData")
    
    def _ejecutar_trabajo_eliminacion(self, ruta: str, origen: str) -> None:
        """Ejecuta la eliminación completa (.exe + .dat + .dll) en un hilo secundario."""
        if self._proceso_en_ejecucion:
            messagebox.showwarning("Aviso", "Ya hay una operación en ejecución.")
            return
        self._proceso_en_ejecucion = True
        self.status_var.set(f"Deteniendo y eliminando ficheros de {ruta}...")
        self._agregar_log(f"Iniciando eliminación completa ({origen}): {ruta}", "WARNING")
        
        def _trabajo():
            try:
                gestor = obtener_gestor_procesos()
                resultados = gestor.detener_y_eliminar_archivos(ruta)
                
                self.root.after(0, lambda: self._agregar_log(
                    f"Servicio detenido: {resultados['servicio_detenido']} | "
                    f"Servicio deshabilitado: {resultados['servicio_deshabilitado']} | "
                    f"EACoreServer.exe eliminado: {resultados['exe_eliminado']} | "
                    f"EACore.dat eliminado: {resultados['dat_eliminado']} | "
                    f"EACore.dll eliminado: {resultados['dll_eliminado']}", "INFO"))
                for detalle in resultados.get("detalles", []):
                    self.root.after(0, lambda d=detalle: self._agregar_log(f"  - {d}", "INFO"))
                
                # Re-escanear para actualizar la tabla de procesos
                rutas = obtener_rutas_candidatas()
                nuevos = gestor.escanear_rutas(rutas)
                self.root.after(0, lambda: self._actualizar_tabla_procesos(nuevos))
                self.root.after(0, lambda: self.status_var.set("Eliminación completada"))
            except Exception as e:
                self.root.after(0, lambda mensaje=str(e): self._agregar_log(f"Error eliminando archivos: {mensaje}", "ERROR"))
                self.root.after(0, lambda: self.status_var.set("Error en la eliminación"))
            finally:
                self.root.after(0, lambda: setattr(self, '_proceso_en_ejecucion', False))
        
        threading.Thread(target=_trabajo, daemon=True).start()
    
    # ==================== FUNCIONES DE USB ====================
    
    def _iniciar_monitor_usb(self) -> None:
        """Inicia el monitor de detección de USB."""
        monitor = obtener_monitor_usb()
        
        def on_usb_insertada(unidad: UnidadExtraible) -> None:
            detalle = f" ({unidad.etiqueta})" if unidad.etiqueta and unidad.etiqueta not in ("(sin metadatos)", "SIN_ETIQUETA") else ""
            self.root.after(0, self._agregar_log, 
                          f"¡Unidad detectada: {unidad.letra}{detalle}", "INFO")
            self.root.after(0, self._refrescar_unidades)
            self.root.after(0, lambda: self.status_var.set(
                f"Unidad {unidad.letra} detectada. Revise la pestaña USB."))
            self.root.after(1000, lambda: self._verificar_y_reparar(unidad.letra))
        
        def on_usb_removida(letra: str) -> None:
            self.root.after(0, self._agregar_log, f"Unidad {letra} removida.", "INFO")
            self.root.after(0, self._refrescar_unidades)
        
        if monitor.iniciar(on_usb_insertada, on_usb_removida):
            self._agregar_log("Monitor USB activado (ventana + polling).", "INFO")
        else:
            self._agregar_log("Error al activar monitor USB. Usando modo polling.", "WARNING")
        
        self._refrescar_unidades()
        self.root.after(3000, self._auto_refrescar_usb)
    
    def _auto_refrescar_usb(self) -> None:
        """Auto-refresca la lista de USB cada 3 segundos."""
        if self.root.winfo_exists():
            self._refrescar_unidades()
            self.root.after(3000, self._auto_refrescar_usb)
    
    def _refrescar_unidades(self) -> None:
        """Refresca el inventario y muestra el diagnóstico no destructivo."""
        monitor = obtener_monitor_usb()
        unidades = monitor.obtener_unidades_actuales()
        motor = obtener_motor_reparacion()

        for item in self.tree_usb.get_children():
            self.tree_usb.delete(item)

        reparadas = obtener_unidades_reparadas()
        if not unidades:
            self.tree_usb.insert("", "end", values=(
                "", "Conecte una unidad USB…", "—", "—", "—",
                ayuda.texto_estado("sin_unidad")))
            if self._ultimo_conteo_usb != 0:
                self._agregar_log("No hay unidades USB conectadas.", "DEBUG")
            self._ultimo_conteo_usb = 0
        else:
            for unidad in unidades:
                tamano_gb = round(unidad.tamano_total / (1024 ** 3), 1)
                libre_gb = round(unidad.espacio_libre / (1024 ** 3), 1)
                diagnostico = motor.analizar_ruta(unidad.ruta_raiz)

                # La clave decide texto, icono, color y tag a la vez, de modo que
                # lo que ve el usuario y lo que explica la leyenda son lo mismo.
                if not unidad.es_reparable_con_seguridad:
                    clave_estado = "solo_diagnostico"
                elif diagnostico.estado is EstadoDeteccion.CONFIRMADA:
                    clave_estado = "confirmada"
                elif diagnostico.estado is EstadoDeteccion.SOSPECHOSA:
                    clave_estado = "sospechosa"
                elif diagnostico.estado is EstadoDeteccion.INACCESIBLE:
                    clave_estado = "inaccesible"
                elif unidad.letra in self._unidades_con_errores:
                    # Antes que «reparada»: el trabajo quedó a medias y el
                    # usuario debe seguir viéndolo.
                    clave_estado = "con_errores"
                elif es_unidad_reparada(unidad.letra):
                    clave_estado = "reparada"
                else:
                    clave_estado = "limpia"

                estado = ayuda.texto_estado(clave_estado)
                tag = ayuda.tag_estado(clave_estado)
                tags = (tag,) if tag else ()

                self.tree_usb.insert("", "end", values=(
                    unidad.letra, unidad.etiqueta, unidad.numero_serie or "—",
                    f"{tamano_gb} GB", f"{libre_gb} GB", estado
                ), tags=tags)

            if self._ultimo_conteo_usb != len(unidades):
                self._agregar_log(f"Unidades detectadas: {len(unidades)}", "DEBUG")
            self._ultimo_conteo_usb = len(unidades)

        if reparadas:
            self.lbl_reparadas.config(
                text=f"Unidades reparadas (guardadas): {', '.join(reparadas)}")
        else:
            self.lbl_reparadas.config(text="Unidades reparadas (guardadas): ninguna")

    def _reparar_todas_usb(self) -> None:
        """Repara solo medios USB con una firma completa confirmada."""
        if self._proceso_en_ejecucion:
            messagebox.showwarning("Aviso", "Ya hay una operación en ejecución.")
            return
        monitor = obtener_monitor_usb()
        motor = obtener_motor_reparacion()
        candidatas = [
            unidad for unidad in monitor.obtener_unidades_actuales()
            if unidad.es_reparable_con_seguridad
            and motor.analizar_ruta(unidad.ruta_raiz).estado is EstadoDeteccion.CONFIRMADA
        ]
        if not candidatas:
            messagebox.showinfo(
                "Sin reparaciones pendientes",
                "No hay unidades USB con la firma completa confirmada.\n\n"
                "Las estructuras incompletas se conservan para revisión manual y los discos internos/red "
                "solo se muestran en modo diagnóstico.",
            )
            return
        letras = ", ".join(unidad.letra for unidad in candidatas)
        if not messagebox.askyesno(
            "Confirmar reparación",
            f"Se restaurarán archivos y se eliminarán únicamente los archivos de firma conocidos en: {letras}.\n\n"
            "No se borrará contenido no reconocido. ¿Desea continuar?",
        ):
            return

        self._proceso_en_ejecucion = True
        self._cancelar_reparacion = False
        self.status_var.set("Reparando unidades USB confirmadas…")
        self._agregar_log(f"Iniciando reparación de: {letras}", "INFO")

        def _trabajo() -> None:
            try:
                for unidad in candidatas:
                    if self._cancelar_reparacion:
                        break
                    self.root.after(0, self.progreso_var.set, 0)
                    self.root.after(0, self.lbl_progreso.config,
                                    {"text": f"Procesando {unidad.letra}…"})
                    resultado = motor.reparar_unidad(
                        unidad.letra, callback_progreso=self._actualizar_progreso
                    )
                    self.root.after(0, self._registrar_resultado_reparacion, resultado)
            except Exception as exc:
                self.root.after(0, self._agregar_log,
                                f"Error reparando unidades: {exc}", "ERROR")
            finally:
                self.root.after(0, lambda: setattr(self, "_cancelar_reparacion", False))
                self.root.after(0, lambda: setattr(self, "_proceso_en_ejecucion", False))
                self.root.after(0, self.status_var.set, "Reparación finalizada")
                self.root.after(0, self._refrescar_unidades)

        threading.Thread(target=_trabajo, daemon=True).start()

    def _reparar_unidad_seleccionada(self) -> None:
        """Solicita confirmación antes de reparar una unidad USB concreta."""
        if self._proceso_en_ejecucion:
            messagebox.showwarning("Aviso", "Ya hay una operación en ejecución.")
            return
        seleccion = self.tree_usb.selection()
        if not seleccion:
            messagebox.showwarning("Aviso", "No hay ninguna unidad seleccionada.")
            return
        valores = self.tree_usb.item(seleccion[0])["values"]
        letra = valores[0]
        if not letra:
            messagebox.showwarning("Aviso", "No hay ninguna unidad disponible para reparar.")
            return

        unidad = next(
            (u for u in obtener_monitor_usb().obtener_unidades_actuales() if u.letra == letra),
            None,
        )
        if not unidad or not unidad.es_reparable_con_seguridad:
            messagebox.showwarning(
                "Destino no permitido",
                "Por seguridad solo se reparan medios extraíbles o discos USB físicos. "
                "Los discos internos y las unidades de red se mantienen en modo diagnóstico.",
            )
            return
        diagnostico = obtener_motor_reparacion().analizar_ruta(unidad.ruta_raiz)
        if diagnostico.estado is not EstadoDeteccion.CONFIRMADA:
            messagebox.showwarning(
                "Firma no confirmada",
                "No se realizó ningún cambio. La estructura debe contener Kaspersky/Usb Drive/3.0 "
                "y los archivos de firma para poder repararse de forma segura.\n\n"
                f"Detalle: {diagnostico.detalle or 'Sin firma detectada.'}",
            )
            return
        if not messagebox.askyesno(
            "Confirmar reparación",
            f"Unidad {letra}: se encontró la firma completa.\n\n"
            "Se restaurarán los archivos de Usb Drive copiándolos y verificando su SHA-256 "
            "antes de retirar el origen. Se eliminarán solo los ficheros 5.dat, 6.dat y 7.dat "
            "y el fichero numérico sin extensión de la carpeta 3.0. "
            "El contenido no reconocido se conservará.\n\n¿Desea continuar?",
        ):
            return
        self._reparar_unidad_internal(letra)

    def _registrar_resultado_reparacion(self, resultado: ResultadoReparacion) -> None:
        """Muestra en el hilo de interfaz el resultado ya calculado."""
        nivel = "INFO" if resultado.estado is EstadoReparacion.COMPLETADO else "WARNING"
        resumen = ayuda.texto_reparacion(resultado.estado.value)
        self._agregar_log(f"Reparación de {resultado.unidad}: {resumen}", nivel)
        self._agregar_log(
            f"Archivos movidos: {resultado.archivos_movidos}; carpetas movidas: "
            f"{resultado.carpetas_movidas}; archivos eliminados: "
            f"{len(resultado.archivos_eliminados)}; copias verificadas por SHA-256: "
            f"{len(resultado.sumas_sha256)}; errores: {len(resultado.errores)}",
            "INFO",
        )
        for error in resultado.errores:
            self._agregar_log(f"Detalle: {error}", "ERROR")
        self.status_var.set(f"Reparación {resultado.unidad}: {resumen}")

        # Una reparación con errores también restauró contenido, así que se
        # marca como reparada; pero se anota el error para que la tabla lo siga
        # mostrando en vez de dar el trabajo por terminado en silencio.
        terminado = resultado.estado in (
            EstadoReparacion.COMPLETADO, EstadoReparacion.COMPLETADO_CON_ERRORES
        )
        if terminado:
            marcar_unidad_reparada(resultado.unidad)
        con_errores = resultado.estado is EstadoReparacion.COMPLETADO_CON_ERRORES
        if con_errores:
            self._unidades_con_errores.add(resultado.unidad)
        else:
            self._unidades_con_errores.discard(resultado.unidad)
        self._persistir_unidades_con_errores()

        self._refrescar_unidades()

    def _persistir_unidades_con_errores(self) -> None:
        """Guarda las unidades con reparación incompleta para la próxima sesión."""
        try:
            config = _cargar_config()
            config["unidades_con_errores"] = sorted(self._unidades_con_errores)
            _guardar_config(config)
        except Exception as exc:
            logger.warning(f"No se pudieron guardar las unidades con errores: {exc}")

    def _reparar_unidad_internal(self, letra: str) -> None:
        """Ejecuta una reparación ya confirmada en un hilo secundario."""
        self._proceso_en_ejecucion = True
        self._cancelar_reparacion = False
        self.status_var.set(f"Reparando {letra}…")

        def _trabajo() -> None:
            try:
                resultado = obtener_motor_reparacion().reparar_unidad(
                    letra, callback_progreso=self._actualizar_progreso
                )
                self.root.after(0, self._registrar_resultado_reparacion, resultado)
            except Exception as exc:
                self.root.after(0, self._agregar_log,
                                f"Error reparando {letra}: {exc}", "ERROR")
            finally:
                self.root.after(0, lambda: setattr(self, "_proceso_en_ejecucion", False))
                self.root.after(0, lambda: setattr(self, "_cancelar_reparacion", False))

        threading.Thread(target=_trabajo, daemon=True).start()

    def _verificar_y_reparar(self, letra: str) -> None:
        """Notifica una detección; nunca repara automáticamente al conectar USB."""
        try:
            unidad = next(
                (u for u in obtener_monitor_usb().obtener_unidades_actuales() if u.letra == letra),
                None,
            )
            if not unidad or not unidad.es_reparable_con_seguridad:
                return
            diagnostico = obtener_motor_reparacion().analizar_ruta(unidad.ruta_raiz)
            if diagnostico.estado is EstadoDeteccion.CONFIRMADA:
                self._agregar_log(
                    f"Firma completa detectada en {letra}. Se requiere confirmación manual para reparar.",
                    "WARNING",
                )
                self.status_var.set(f"Firma detectada en {letra}; revise la pestaña Reparación Unidades.")
            elif diagnostico.estado is EstadoDeteccion.SOSPECHOSA:
                self._agregar_log(
                    f"Estructura incompleta en {letra}; no se modificó ningún archivo.", "WARNING"
                )
        except Exception as exc:
            logger.error(f"Error verificando {letra}: {exc}")

    def _actualizar_progreso(self, pct: int, mensaje: str) -> None:
        """Actualiza la barra de progreso desde cualquier hilo."""
        self.root.after(0, self.progreso_var.set, pct)
        self.root.after(0, self.lbl_progreso.config, {"text": mensaje})

    # ==================== FUNCIONES DE LOG ====================
    
    def _limpiar_log(self) -> None:
        """Limpia el área de log."""
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state=tk.DISABLED)
    
    def _exportar_log(self) -> None:
        """Exporta el log a un archivo."""
        ruta = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Archivos de log", "*.log"), ("Todos los archivos", "*.*")],
            title="Exportar Log"
        )
        if ruta:
            try:
                contenido = self.log_text.get(1.0, tk.END)
                with open(ruta, "w", encoding="utf-8") as f:
                    f.write(contenido)
                self._agregar_log(f"Log exportado a: {ruta}", "INFO")
            except Exception as e:
                self._agregar_log(f"Error exportando log: {e}", "ERROR")
    
    def _acerca_de(self) -> None:
        """Muestra el diálogo Acerca de con el sistema donde se ejecuta."""
        info = compat.obtener_info_plataforma()
        messagebox.showinfo(
            "Acerca de",
            "Antivirus EACoreServer v1.2\n"
            "Protección contra malware USB\n"
            "y gestión de procesos EACoreServer.exe\n\n"
            "Sistemas atendidos:\n"
            "    Windows Vista, 7, 8, 8.1, 10 y 11 (x86 y x64)\n"
            "    macOS, Linux, FreeBSD, OpenBSD, NetBSD,\n"
            "    Solaris/illumos y AIX\n\n"
            f"Ejecutándose en: {info.nombre_amigable}\n"
            f"Arquitectura: {info.arquitectura} ({info.bits_proceso} bits)\n"
            f"Python: {info.python_version}\n\n"
            "Requiere Python 3.8 o superior.\n"
            "Ing. Yosvany Hernández Quintero",
        )
    
    def _salir(self) -> None:
        """Cierra la aplicación correctamente."""
        self._agregar_log("Cerrando aplicación...", "INFO")
        monitor = obtener_monitor_usb()
        monitor.detener()
        self.root.destroy()


def _apariencia_guardada() -> Dict[str, Any]:
    """Lee tema, acento y escala de config.json sin construir la GUI.

    Sirve para pintar la ventana con el fondo correcto desde el primer frame,
    evitando un destello de color equivocado al arrancar. Los valores se validan
    con las mismas reglas que ``AntivirusGUI.__init__`` para que una
    configuración antigua o corrupta no rompa el arranque.
    """
    config = _cargar_config()

    tema = config.get("tema", "sistema")
    if tema not in temas.PALETAS and tema != "sistema":
        tema = temas.PALETA_POR_DEFECTO

    acento = str(config.get("acento") or "").strip()
    if not temas.es_color_valido(acento):
        acento = None

    escala = config.get("escala_letra", temas.ESCALA_POR_DEFECTO)
    if escala not in temas.ESCALAS_FUENTE:
        escala = temas.ESCALA_POR_DEFECTO

    return {"tema": tema, "acento": acento, "escala": escala}


def _area_trabajo_pantalla(root: tk.Tk) -> Tuple[int, int, int, int]:
    """Devuelve (x, y, ancho, alto) del área de trabajo (pantalla sin barra de tareas)."""
    try:
        import ctypes
        from ctypes import wintypes
        rect = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
        if rect.right > rect.left and rect.bottom > rect.top:
            return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
    except Exception:
        pass
    # Respaldo: pantalla completa menos margen estimado de la barra de tareas
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    return 0, 0, sw, max(sh - 60, 400)


def _ajustar_ventana_a_pantalla(root: tk.Tk) -> None:
    """Recoloca/redimensiona la ventana para que toda ella (incluida la barra de
    estado inferior) quede dentro de la zona visible."""
    try:
        root.update_idletasks()
        geo = root.geometry()
        parte, _posicion = geo.split("+", 1)
        w_act, h_act = map(int, parte.split("x"))
        x0, y0, w_area, h_area = _area_trabajo_pantalla(root)
        if w_act > w_area - 10:
            w_act = max(w_area - 10, 640)
        if h_act > h_area - 10:
            h_act = max(h_area - 10, 480)
        x = x0 + max((w_area - w_act) // 2, 0)
        y = y0 + max((h_area - h_act) // 2, 0)
        root.geometry(f"{w_act}x{h_act}+{x}+{y}")
    except Exception:
        pass


def ejecutar_aplicacion() -> None:
    """Punto de entrada para la aplicación GUI."""
    root = tk.Tk()

    # Pintar la ventana con el fondo del tema guardado antes de crear widgets,
    # para que no haya un destello de color equivocado al arrancar.
    apariencia = _apariencia_guardada()
    paleta_inicial = temas.construir_paleta(apariencia["tema"], apariencia["acento"])
    root.configure(bg=paleta_inicial["bg"])

    # Título de la ventana
    root.title("Antivirus EACoreServer v1.2 - Protección USB y Procesos")
    
    # Dimensiones deseadas de la ventana
    VENTANA_ANCHO = 1280
    VENTANA_ALTO = 780
    
    # Ajustar tamaño al área de trabajo (sin barra de tareas) y centrar la ventana
    x0, y0, w_area, h_area = _area_trabajo_pantalla(root)
    ancho = min(VENTANA_ANCHO, w_area - 10)
    alto = min(VENTANA_ALTO, h_area - 10)
    x = x0 + max((w_area - ancho) // 2, 0)
    y = y0 + max((h_area - alto) // 2, 0)
    root.geometry(f"{ancho}x{alto}+{x}+{y}")
    # Marcar que la geometría ya está controlada (AntivirusGUI no la sobrescribirá)
    root._geometria_controlada = True
    
    # Tamaño mínimo acorde a la pantalla para que la barra de estado sea visible
    root.minsize(min(1024, max(w_area - 10, 640)), min(650, max(h_area - 10, 480)))
    
    # Icono de la ventana (si existe archivo .ico)
    try:
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icono.ico")
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception:
        pass
    
    app = AntivirusGUI(root)
    root.protocol("WM_DELETE_WINDOW", app._salir)
    
    # Garantizar que toda la ventana quede dentro de la zona visible
    _ajustar_ventana_a_pantalla(root)
    
    root.mainloop()


if __name__ == "__main__":
    ejecutar_aplicacion()