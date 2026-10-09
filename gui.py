"""
Interfaz gráfica profesional de Antivirus EACoreServer.

Rediseñada con componentes modernos: botones con efecto ``hover``, tarjetas
agrupadoras, menús contextuales en tablas, sistema de notificaciones ``toast``,
barra de búsqueda en el registro e indicadores de estado en tiempo real.

Todo el texto está en español. Usa tkinter y los componentes de
:mod:`ui_components` y :mod:`toast`.
"""

from __future__ import annotations

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
from ui_components import (
    BotonProfesional, Tarjeta, BarraBusqueda, IndicadorEstado,
    BarraProgreso, MenuContextual, separador_horizontal, espaciado,
)
from toast import obtener_notificador, TipoToast
from logger import obtener_logger

logger = obtener_logger()


# ---------------------------------------------------------------------------
# Constantes de versión y marca
# ---------------------------------------------------------------------------
VERSION_APP = "1.2.0"
NOMBRE_APP = "Antivirus EACoreServer"


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


PALETAS = temas.PALETAS


class AntivirusGUI:
    """Interfaz gráfica principal, rediseñada con componentes profesionales."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"{NOMBRE_APP} v{VERSION_APP}")

        if not getattr(root, "_geometria_controlada", False):
            self.root.geometry("1320x820")

        # Tamaño mínimo adaptado a la pantalla.
        w_area = max(self.root.winfo_screenwidth() - 20, 640)
        h_area = max(self.root.winfo_screenheight() - 60, 480)
        self.root.minsize(min(1100, w_area), min(700, h_area))

        # Estado de la aplicación.
        self._proceso_en_ejecucion = False
        self._cancelar_reparacion = False
        self._ultimo_conteo_usb = -1
        self._resultados_procesos: List[InfoRutaEACore] = []

        # Preferencias de apariencia.
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

        # Tooltips registrados.
        self._tooltips: List["ayuda.ToolTip"] = []
        self._paleta: dict = {}

        # Unidades con errores (persistido).
        self._unidades_con_errores: set = {
            str(letra) for letra in (config.get("unidades_con_errores") or [])
        }

        # Inicializar la fuente antes de crear widgets.
        self._inicializar_fuentes()

        # Fondo de la ventana con la paleta inicial (evita destellos).
        paleta = self._paleta_actual()
        self.root.configure(bg=paleta["bg"])

        # --- Construir interfaz ---
        self._crear_cabecera_profesional()
        self._crear_menu()
        self._crear_interfaz_principal()

        # Aplicar tema completo.
        self._configurar_estilos_ttk()
        self._aplicar_tema(self._tema_seleccion)

        # Inicializar el notificador toast.
        self._notificador = obtener_notificador(self.root)

        # Logs y monitor.
        self._agregar_log("Aplicación iniciada correctamente.", "INFO")
        self._agregar_log("Monitoreo USB activo.", "INFO")
        self._iniciar_monitor_usb()

        # Atajos de teclado globales.
        self._registrar_atajos()

        # Bienvenida la primera vez.
        self.root.after(500, self._mostrar_bienvenida)

    # =======================================================================
    # Cabecera profesional
    # =======================================================================
    def _crear_cabecera_profesional(self) -> None:
        """Crea una cabecera moderna con logo, título y estado del sistema."""
        paleta = self._paleta_actual()

        cabecera = tk.Frame(self.root, background=paleta["header"], height=64)
        cabecera.pack(fill="x")
        cabecera.pack_propagate(False)

        # Logo/ícono.
        lbl_logo = tk.Label(
            cabecera, text="🛡", background=paleta["header"],
            foreground=paleta["acento"], font=("Segoe UI", 26)
        )
        lbl_logo.pack(side="left", padx=(16, 8))

        # Título y subtítulo.
        titulo_frame = tk.Frame(cabecera, background=paleta["header"])
        titulo_frame.pack(side="left", fill="y", padx=4)

        lbl_titulo = tk.Label(
            titulo_frame, text=f"{NOMBRE_APP}",
            background=paleta["header"], foreground=paleta["blanco"],
            font=("Segoe UI", 15, "bold")
        )
        lbl_titulo.pack(anchor="w")

        self.lbl_subtitulo = tk.Label(
            titulo_frame,
            text=f"v{VERSION_APP}  ·  Protección USB  ·  Gestión de procesos",
            background=paleta["header"], foreground=paleta["texto_suave"],
            font=("Segoe UI", 9)
        )
        self.lbl_subtitulo.pack(anchor="w")

        # Espacio flexible.
        tk.Frame(cabecera, background=paleta["header"]).pack(side="left", fill="x", expand=True)

        # Indicadores de estado en la cabecera.
        info = compat.obtener_info_plataforma()
        self._indicador_sistema = IndicadorEstado(
            cabecera,
            texto=f"{info.nombre_amigable}  ·  {info.arquitectura}",
            color_punto=paleta["exito"] if info.soportado else paleta["error"],
            color_texto=paleta["blanco"],
            fondo=paleta["header"],
            fuente=("Segoe UI", 9),
        )
        self._indicador_sistema.pack(side="right", padx=(0, 12))

        # Botón de ayuda rápido en la cabecera.
        self.btn_ayuda_rapido = BotonProfesional(
            cabecera,
            text="Ayuda (F1)",
            command=self._abrir_guia,
            color_fondo=paleta["header"],
            color_fondo_hover=paleta["acento"],
            color_texto=paleta["blanco"],
            color_texto_hover="#ffffff",
            color_borde=paleta["borde"],
            fuente=("Segoe UI", 10, "bold"),
            ancho_min=120,
            alto=34,
        )
        self.btn_ayuda_rapido.pack(side="right", padx=(0, 12))

        # Separador bajo la cabecera.
        separador_horizontal(self.root, color=paleta["borde"], grosor=2)

    # =======================================================================
    # Fuentes
    # =======================================================================
    def _inicializar_fuentes(self) -> None:
        """Elige familias de letra disponibles en este sistema."""
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

    def _fuente(self, base: int, negrita: bool = False) -> tuple:
        return (self._fuente_base,
                temas.tamano_fuente(base, self._escala_seleccion),
                "bold" if negrita else "normal")

    def _fuente_mono(self, base: int, negrita: bool = False) -> tuple:
        return (self._fuente_mono_base,
                temas.tamano_fuente(base, self._escala_seleccion),
                "bold" if negrita else "normal")

    def _paleta_actual(self) -> dict:
        return temas.construir_paleta(self._tema_seleccion, self._acento_seleccion)

    # =======================================================================
    # Estilos ttk
    # =======================================================================
    def _configurar_estilos_ttk(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        self._aplicar_estilos_tema(self._paleta_actual())

    def _aplicar_estilos_tema(self, p: dict) -> None:
        style = ttk.Style()
        style.theme_use("clam")

        # Etiquetas.
        style.configure("Title.TLabel", font=self._fuente(14, True), foreground=p["acento"])
        style.configure("Subtitle.TLabel", font=self._fuente(9), foreground=p["texto_suave"])
        style.configure("Status.TLabel", font=self._fuente(9), foreground=p["fg"], background=p["status_bg"])
        style.configure("Header.TLabel", font=self._fuente(10, True), foreground=p["blanco"], background=p["header"])

        # Estados semánticos.
        style.configure("Green.TLabel", foreground=p["exito"], font=self._fuente(10, True))
        style.configure("Red.TLabel", foreground=p["error"], font=self._fuente(10, True))
        style.configure("Yellow.TLabel", foreground=p["advertencia"], font=self._fuente(10, True))
        style.configure("Info.TLabel", foreground=p["info"], font=self._fuente(10, True))
        style.configure("Muted.TLabel", foreground=p["texto_suave"], font=self._fuente(9))

        # Superficies.
        style.configure("TFrame", background=p["bg"])
        style.configure("Panel.TFrame", background=p["panel"])
        style.configure("PanelAlt.TFrame", background=p["panel_alt"])
        style.configure("TLabelframe", background=p["bg"], foreground=p["fg"], bordercolor=p["borde"])
        style.configure("TLabelframe.Label", background=p["bg"], foreground=p["acento"], font=self._fuente(10, True))

        # Botones ttk base (respaldo cuando no se usa BotonProfesional).
        style.configure("TButton", font=self._fuente(10, True), background=p["frame"],
                        foreground=p["fg"], borderwidth=1, bordercolor=p["borde"], padding=(10, 5))
        style.map("TButton",
                  background=[("active", p["acento_suave"]), ("pressed", p["acento_oscuro"])],
                  foreground=[("active", p["fg"]), ("pressed", p["texto_sobre_acento"])])

        # Pestañas mejoradas.
        style.configure("TNotebook", background=p["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=p["frame"], foreground=p["texto_suave"],
                        font=self._fuente(10, True), padding=(16, 8), bordercolor=p["borde"])
        style.map("TNotebook.Tab",
                  background=[("selected", p["acento"])],
                  foreground=[("selected", p["texto_sobre_acento"])],
                  expand=[("selected", (0, 0, 0, 2))])

        # Barra de progreso.
        style.configure("TProgressbar", thickness=temas.tamano_fuente(20, self._escala_seleccion),
                        troughcolor=p["frame"], background=p["acento"], bordercolor=p["borde"])

        # Separadores.
        style.configure("TSeparator", background=p["borde"])

        # Treeview.
        style.configure("Custom.Treeview",
                        rowheight=temas.tamano_fuente(28, self._escala_seleccion),
                        font=self._fuente_mono(9),
                        background=p["tree_bg"], foreground=p["tree_fg"],
                        fieldbackground=p["field"], borderwidth=1, bordercolor=p["borde"])
        style.configure("Custom.Treeview.Heading", font=self._fuente(9, True),
                        background=p["header"], foreground=p["blanco"], bordercolor=p["borde"])
        style.map("Custom.Treeview",
                  background=[("selected", p["seleccion"])],
                  foreground=[("selected", p["fg"])])
        style.map("Custom.Treeview.Heading", background=[("active", p["acento_oscuro"])])

        # Scrollbars.
        style.configure("Vertical.TScrollbar", background=p["frame"], troughcolor=p["bg"],
                        arrowcolor=p["fg"], bordercolor=p["borde"])
        style.configure("Horizontal.TScrollbar", background=p["frame"], troughcolor=p["bg"],
                        arrowcolor=p["fg"], bordercolor=p["borde"])

        # Combos y campos.
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
            self.log_text.tag_configure("INFO", foreground=p["info"])
            self.log_text.tag_configure("WARNING", foreground=p["advertencia"])
            self.log_text.tag_configure("ERROR", foreground=p["error"])
            self.log_text.tag_configure("CRITICAL", foreground=p["error"])
            self.log_text.tag_configure("EXITO", foreground=p["exito"])

        if hasattr(self, "lbl_plataforma"):
            self.lbl_plataforma.configure(foreground=p["texto_suave"], font=self._fuente(9))
        if hasattr(self, "lbl_reparadas"):
            self.lbl_reparadas.configure(foreground=p["fg"])

        if hasattr(self, "tree_procesos"):
            self.tree_procesos.tag_configure("activo", background=p["activo_bg"])
            self.tree_procesos.tag_configure("inactivo", background=p["inactivo_bg"])
            self.tree_procesos.tag_configure("legitimo", background=p["acento_suave"])

        if hasattr(self, "tree_usb"):
            for clave_estado in ayuda.claves_estado():
                tag = ayuda.tag_estado(clave_estado)
                if not tag:
                    continue
                tinte = temas.mezclar(p[ayuda.tono_estado(clave_estado)], p["tree_bg"], 0.78)
                self.tree_usb.tag_configure(tag, background=tinte)

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
        if not hasattr(self, "ayuda_text"):
            return
        for etiqueta, color, peso in (
            ("titulo", p["acento"], "bold"), ("subtitulo", p["fg"], "bold"),
            ("cuerpo", p["fg"], "normal"), ("suave", p["texto_suave"], "normal"),
            ("exito", p["exito"], "bold"), ("error", p["error"], "bold"),
            ("advertencia", p["advertencia"], "bold"), ("info", p["info"], "bold"),
            ("mono", p["fg"], "normal"), ("aviso", p["advertencia"], "bold"),
        ):
            fuente = self._fuente_mono(9) if etiqueta == "mono" else self._fuente(
                12 if etiqueta == "titulo" else 10, peso == "bold"
            )
            self.ayuda_text.tag_configure(etiqueta, foreground=color, font=fuente)

    def _aplicar_tema(self, tema: str) -> None:
        if tema not in temas.PALETAS and tema != "sistema":
            tema = temas.PALETA_POR_DEFECTO
        self._tema_seleccion = tema
        self._tema_var.set(tema)
        self._refrescar_apariencia()
        self._persistir_apariencia()
        resuelto = temas.resolver_nombre_paleta(tema)
        logger.info(f"Tema aplicado: {temas.NOMBRES_PALETAS.get(tema, tema)} (resuelto: {resuelto})")

    def _aplicar_acento(self, acento: str) -> None:
        if acento and not temas.es_color_valido(acento):
            logger.warning(f"Color de acento no válido: {acento!r}")
            return
        self._acento_seleccion = acento or None
        self._acento_var.set(acento or "")
        self._refrescar_apariencia()
        self._persistir_apariencia()
        logger.info(f"Color de acento aplicado: {acento or 'el de la paleta'}")

    def _aplicar_escala(self, escala: str) -> None:
        if escala not in temas.ESCALAS_FUENTE:
            escala = temas.ESCALA_POR_DEFECTO
        self._escala_seleccion = escala
        self._escala_var.set(escala)
        self._refrescar_apariencia()
        self._persistir_apariencia()
        logger.info(f"Tamaño de letra aplicado: {temas.NOMBRES_ESCALAS[escala]}")

    def _refrescar_apariencia(self) -> None:
        paleta = self._paleta_actual()
        self._paleta = paleta
        problemas = temas.validar_paleta(paleta)
        for problema in problemas:
            logger.warning(f"Paleta con contraste mejorable: {problema}")
        self._aplicar_estilos_tema(paleta)
        self._recolorear_widgets(paleta)

    def _persistir_apariencia(self) -> None:
        config = _cargar_config()
        config["tema"] = self._tema_seleccion
        config["acento"] = self._acento_seleccion or ""
        config["escala_letra"] = self._escala_seleccion
        _guardar_config(config)

    # =======================================================================
    # Menú
    # =======================================================================
    def _crear_menu(self) -> None:
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
        menu_ayuda.add_command(label="Guía de uso", command=self._abrir_guia, accelerator="F1")
        menu_ayuda.add_command(label="Atajos de teclado", command=self._mostrar_atajos)
        menu_ayuda.add_command(label="Comprobar compatibilidad del sistema", command=self._mostrar_compatibilidad)
        menu_ayuda.add_separator()
        menu_ayuda.add_command(label="Acerca de", command=self._acerca_de)
        menubar.add_cascade(label="Ayuda", menu=menu_ayuda)

        self.root.config(menu=menubar)

    def _crear_menu_temas(self, padre) -> tk.Menu:
        menu = tk.Menu(padre, tearoff=0)
        for clave, nombre in temas.listar_paletas():
            muestra = "" if clave == "sistema" else f"   ● {temas.PALETAS[clave]['acento']}"
            menu.add_radiobutton(
                label=f"{nombre}{muestra}", value=clave, variable=self._tema_var,
                command=lambda c=clave: self._aplicar_tema(c),
            )
        return menu

    def _crear_menu_acento(self, padre) -> tk.Menu:
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
        menu = tk.Menu(padre, tearoff=0)
        for clave, nombre in temas.listar_escalas():
            menu.add_radiobutton(
                label=nombre, value=clave, variable=self._escala_var,
                command=lambda c=clave: self._aplicar_escala(c),
            )
        return menu

    def _elegir_acento_dialogo(self) -> None:
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
        self._acento_seleccion = None
        self._acento_var.set("")
        self._escala_seleccion = temas.ESCALA_POR_DEFECTO
        self._escala_var.set(temas.ESCALA_POR_DEFECTO)
        self._aplicar_tema("sistema")
        logger.info("Apariencia restablecida")

    # =======================================================================
    # Atajos de teclado
    # =======================================================================
    def _registrar_atajos(self) -> None:
        self.root.bind("<Control-q>", lambda e: self._salir())
        self.root.bind("<F1>", lambda e: self._abrir_guia())
        self.root.bind("<Control-h>", lambda e: self._abrir_guia())
        self.root.bind("<F5>", lambda e: self._refrescar_unidades())
        self.root.bind("<Control-r>", lambda e: self._escanear_rutas())
        self.root.bind("<Control-l>", lambda e: self._limpiar_log())
        self.root.bind("<Control-e>", lambda e: self._exportar_log())

    def _mostrar_atajos(self) -> None:
        atajos = (
            "Atajos de teclado disponibles:\n\n"
            "  F1 / Ctrl+H  →  Abrir guía de uso\n"
            "  F5           →  Refrescar unidades USB\n"
            "  Ctrl+R       →  Escanear rutas EACoreServer\n"
            "  Ctrl+L       →  Limpiar el registro\n"
            "  Ctrl+E       →  Exportar el registro\n"
            "  Ctrl+Q       →  Salir de la aplicación\n\n"
            "En la tabla de procesos:\n"
            "  Clic derecho  →  Menú contextual con acciones rápidas\n"
            "  Supr          →  Finalizar proceso seleccionado\n\n"
            "En la tabla de unidades:\n"
            "  Clic derecho  →  Menú contextual con acciones rápidas\n"
            "  Enter         →  Reparar unidad seleccionada"
        )
        messagebox.showinfo("Atajos de teclado", atajos)

    # =======================================================================
    # Interfaz principal
    # =======================================================================
    def _crear_interfaz_principal(self) -> None:
        """Crea la interfaz principal con pestañas profesionales."""
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 8))

        # Notebook (pestañas).
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self._crear_pestana_procesos()
        self._crear_pestana_usb()
        self._crear_pestana_log()
        self._crear_pestana_ayuda()

        # Barra de estado profesional.
        self._crear_barra_estado_profesional()

    # =======================================================================
    # Pestaña de procesos (rediseñada)
    # =======================================================================
    def _crear_pestana_procesos(self) -> None:
        self.tab_procesos = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_procesos, text="  Gestión de procesos  ")

        # Tarjeta superior: controles de escaneo.
        tarjeta_controles = Tarjeta(
            self.tab_procesos, titulo="Escaneo de rutas EACoreServer",
            color_fondo=self._paleta_actual()["panel"],
            color_borde=self._paleta_actual()["borde"],
            color_titulo=self._paleta_actual()["acento"],
            fuente_titulo=self._fuente(10, True),
            padding=10,
        )
        tarjeta_controles.cuerpo.pack(fill="x")

        control_frame = tarjeta_controles.cuerpo

        self.btn_escanear = BotonProfesional(
            control_frame, text="Escanear rutas", command=self._escanear_rutas,
            color_fondo=self._paleta_actual()["acento"],
            color_fondo_hover=self._paleta_actual()["acento_oscuro"],
            color_texto="#ffffff", color_texto_hover="#ffffff",
            color_borde=self._paleta_actual()["borde"],
            fuente=self._fuente(10, True), alto=32,
        )
        self.btn_escanear.pack(side="left", padx=(0, 6))
        self._registrar_tooltip(self.btn_escanear, "escanear")

        self.btn_finalizar_todos = BotonProfesional(
            control_frame, text="Finalizar todos", command=self._finalizar_todos,
            color_fondo=self._paleta_actual()["acento_suave"],
            color_fondo_hover=self._paleta_actual()["acento"],
            color_texto=self._paleta_actual()["fg"], color_texto_hover="#ffffff",
            color_borde=self._paleta_actual()["borde"],
            fuente=self._fuente(10, True), alto=32,
        )
        self.btn_finalizar_todos.pack(side="left", padx=4)
        self._registrar_tooltip(self.btn_finalizar_todos, "finalizar_todos")

        self.btn_refrescar_procesos = BotonProfesional(
            control_frame, text="Refrescar", command=self._refrescar_procesos,
            color_fondo=self._paleta_actual()["frame"],
            color_fondo_hover=self._paleta_actual()["acento_suave"],
            color_texto=self._paleta_actual()["fg"], color_texto_hover=self._paleta_actual()["fg"],
            color_borde=self._paleta_actual()["borde"],
            fuente=self._fuente(10, True), alto=32,
        )
        self.btn_refrescar_procesos.pack(side="left", padx=4)
        self._registrar_tooltip(self.btn_refrescar_procesos, "refrescar")

        self.lbl_proceso_count = tk.Label(
            control_frame, text="Sin escanear",
            background=self._paleta_actual()["panel"],
            foreground=self._paleta_actual()["texto_suave"],
            font=self._fuente(9)
        )
        self.lbl_proceso_count.pack(side="right", padx=10)

        # Tabla de rutas con menú contextual.
        table_frame = ttk.Frame(self.tab_procesos)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(6, 4))

        columns = ("indice", "ruta", "estado", "pid", "usuario", "tamano_kb",
                   "servicio", "clasificacion", "error")
        self.tree_procesos = ttk.Treeview(
            table_frame, columns=columns, show="headings",
            style="Custom.Treeview", height=14
        )
        self._registrar_tooltip(self.tree_procesos, "tabla_procesos")

        self.tree_procesos.heading("indice", text="N°")
        self.tree_procesos.heading("ruta", text="Ruta del archivo")
        self.tree_procesos.heading("estado", text="Estado")
        self.tree_procesos.heading("pid", text="PID")
        self.tree_procesos.heading("usuario", text="Usuario")
        self.tree_procesos.heading("tamano_kb", text="Tamaño KB")
        self.tree_procesos.heading("servicio", text="Servicio")
        self.tree_procesos.heading("clasificacion", text="Confianza")
        self.tree_procesos.heading("error", text="Error")

        self.tree_procesos.column("indice", width=40, anchor="center")
        self.tree_procesos.column("ruta", width=380)
        self.tree_procesos.column("estado", width=110, anchor="center")
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

        # Menú contextual para la tabla de procesos.
        self._menu_procesos = MenuContextual(
            self.tree_procesos,
            color_fondo=self._paleta_actual()["frame"],
            color_texto=self._paleta_actual()["fg"],
            color_hover=self._paleta_actual()["acento"],
            color_borde=self._paleta_actual()["borde"],
            fuente=self._fuente(10),
        )
        self._menu_procesos.agregar("Finalizar proceso", self._finalizar_seleccionado, icono="")
        self._menu_procesos.agregar("Finalizar por ruta", self._finalizar_por_ruta, icono="🔍")
        self._menu_procesos.agregar_separador()
        self._menu_procesos.agregar(
            "Eliminar .exe + .dat + .dll", self._eliminar_exe_dat_seleccionado, icono="🗑"
        )
        self._menu_procesos.agregar_separador()
        self._menu_procesos.agregar("Copiar ruta", self._copiar_ruta_seleccionada, icono="📋")
        self._menu_procesos.agregar("Abrir carpeta", self._abrir_carpeta_seleccionada, icono="📂")

        self.tree_procesos.bind("<Button-3>", self._mostrar_menu_procesos)
        self.tree_procesos.bind("<Delete>", lambda _e: self._finalizar_seleccionado())

        # Tarjeta inferior: acciones individuales.
        tarjeta_acciones = Tarjeta(
            self.tab_procesos, titulo="Acciones sobre la selección",
            color_fondo=self._paleta_actual()["panel"],
            color_borde=self._paleta_actual()["borde"],
            color_titulo=self._paleta_actual()["acento"],
            fuente_titulo=self._fuente(10, True),
            padding=10,
        )
        tarjeta_acciones.cuerpo.pack(fill="x", pady=(0, 4))

        accion_frame = tarjeta_acciones.cuerpo

        self.btn_finalizar_sel = BotonProfesional(
            accion_frame, text="Finalizar seleccionado",
            command=self._finalizar_seleccionado,
            color_fondo=self._paleta_actual()["frame"],
            color_fondo_hover=self._paleta_actual()["acento"],
            color_texto=self._paleta_actual()["fg"], color_texto_hover="#ffffff",
            color_borde=self._paleta_actual()["borde"],
            fuente=self._fuente(10, True), alto=30,
        )
        self.btn_finalizar_sel.pack(side="left", padx=(0, 6))
        self._registrar_tooltip(self.btn_finalizar_sel, "finalizar")

        self.btn_eliminar_sel = BotonProfesional(
            accion_frame, text="Eliminar archivos seleccionados",
            command=self._eliminar_exe_dat_seleccionado,
            color_fondo=self._paleta_actual()["error"],
            color_fondo_hover="#ff4040",
            color_texto="#ffffff", color_texto_hover="#ffffff",
            color_borde=self._paleta_actual()["borde"],
            estilo_semantico="peligro",
            fuente=self._fuente(10, True), alto=30,
        )
        self.btn_eliminar_sel.pack(side="left", padx=4)
        self._registrar_tooltip(self.btn_eliminar_sel, "detener_servicio")

        # Separador.
        separador_horizontal(self.tab_procesos, color=self._paleta_actual()["borde"])

        # Acción del servicio ProgramData.
        self.btn_servicio = BotonProfesional(
            self.tab_procesos,
            text="Detener y eliminar EACoreService de ProgramData",
            command=self._eliminar_servicio_programdata,
            color_fondo=self._paleta_actual()["error"],
            color_fondo_hover="#ff4040",
            color_texto="#ffffff", color_texto_hover="#ffffff",
            color_borde=self._paleta_actual()["borde"],
            estilo_semantico="peligro",
            fuente=self._fuente(10, True), alto=34,
        )
        self.btn_servicio.pack(fill="x", pady=(2, 6))
        self._registrar_tooltip(self.btn_servicio, "detener_servicio")

    # =======================================================================
    # Pestaña USB (rediseñada)
    # =======================================================================
    def _crear_pestana_usb(self) -> None:
        self.tab_usb = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_usb, text="  Reparación de unidades  ")

        # Tarjeta superior: unidades detectadas.
        tarjeta_unidades = Tarjeta(
            self.tab_usb, titulo="Unidades detectadas",
            color_fondo=self._paleta_actual()["panel"],
            color_borde=self._paleta_actual()["borde"],
            color_titulo=self._paleta_actual()["acento"],
            fuente_titulo=self._fuente(10, True),
            padding=10,
        )
        tarjeta_unidades.cuerpo.pack(fill="both", expand=True)

        columns_usb = ("letra", "etiqueta", "serie", "tamano", "libre", "estado")
        self.tree_usb = ttk.Treeview(
            tarjeta_unidades.cuerpo, columns=columns_usb, show="headings",
            style="Custom.Treeview", height=8
        )
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
        self.tree_usb.column("estado", width=200, anchor="center")

        self.tree_usb.pack(side="left", fill=tk.BOTH, expand=True)

        scrollbar_usb = ttk.Scrollbar(tarjeta_unidades.cuerpo, orient="vertical", command=self.tree_usb.yview)
        self.tree_usb.configure(yscrollcommand=scrollbar_usb.set)
        scrollbar_usb.pack(side="right", fill="y")

        # Menú contextual para la tabla USB.
        self._menu_usb = MenuContextual(
            self.tree_usb,
            color_fondo=self._paleta_actual()["frame"],
            color_texto=self._paleta_actual()["fg"],
            color_hover=self._paleta_actual()["acento"],
            color_borde=self._paleta_actual()["borde"],
            fuente=self._fuente(10),
        )
        self._menu_usb.agregar("Reparar unidad", self._reparar_unidad_seleccionada, icono="🔧")
        self._menu_usb.agregar("Refrescar unidades", self._refrescar_unidades, icono="")
        self._menu_usb.agregar_separador()
        self._menu_usb.agregar("Copiar letra", self._copiar_letra_seleccionada, icono="📋")

        self.tree_usb.bind("<Button-3>", self._mostrar_menu_usb)
        self.tree_usb.bind("<Return>", lambda _e: self._reparar_unidad_seleccionada())

        # Barra de progreso profesional.
        separador_horizontal(self.tab_usb, color=self._paleta_actual()["borde"])

        tarjeta_progreso = Tarjeta(
            self.tab_usb, titulo="Progreso de reparación",
            color_fondo=self._paleta_actual()["panel"],
            color_borde=self._paleta_actual()["borde"],
            color_titulo=self._paleta_actual()["acento"],
            fuente_titulo=self._fuente(10, True),
            padding=10,
        )
        tarjeta_progreso.cuerpo.pack(fill="x", pady=(4, 0))

        self._barra_progreso = BarraProgreso(
            tarjeta_progreso.cuerpo, maximo=100,
            color_fondo=self._paleta_actual()["frame"],
            color_barra=self._paleta_actual()["acento"],
            color_texto=self._paleta_actual()["fg"],
            color_borde=self._paleta_actual()["borde"],
            fuente=self._fuente(9, True),
        )
        self._barra_progreso.pack(fill="x")

        self.lbl_progreso = tk.Label(
            tarjeta_progreso.cuerpo, text="Esperando operación…",
            background=self._paleta_actual()["panel"],
            foreground=self._paleta_actual()["texto_suave"],
            font=self._fuente(9)
        )
        self.lbl_progreso.pack(anchor="w", pady=(6, 0))

        # Botones de acción.
        separador_horizontal(self.tab_usb, color=self._paleta_actual()["borde"])

        tarjeta_acciones_usb = Tarjeta(
            self.tab_usb, titulo="Acciones",
            color_fondo=self._paleta_actual()["panel"],
            color_borde=self._paleta_actual()["borde"],
            color_titulo=self._paleta_actual()["acento"],
            fuente_titulo=self._fuente(10, True),
            padding=10,
        )
        tarjeta_acciones_usb.cuerpo.pack(fill="x", pady=(4, 4))

        self.btn_reparar = BotonProfesional(
            tarjeta_acciones_usb.cuerpo, text="Reparar seleccionada",
            command=self._reparar_unidad_seleccionada,
            color_fondo=self._paleta_actual()["exito"],
            color_fondo_hover="#2ebd6e",
            color_texto="#ffffff", color_texto_hover="#ffffff",
            color_borde=self._paleta_actual()["borde"],
            estilo_semantico="exito",
            fuente=self._fuente(10, True), alto=34,
        )
        self.btn_reparar.pack(side="left", padx=(0, 6))
        self._registrar_tooltip(self.btn_reparar, "reparar")

        self.btn_reparar_todas = BotonProfesional(
            tarjeta_acciones_usb.cuerpo, text="Reparar todas (confirmadas)",
            command=self._reparar_todas_usb,
            color_fondo=self._paleta_actual()["exito"],
            color_fondo_hover="#2ebd6e",
            color_texto="#ffffff", color_texto_hover="#ffffff",
            color_borde=self._paleta_actual()["borde"],
            estilo_semantico="exito",
            fuente=self._fuente(10, True), alto=34,
        )
        self.btn_reparar_todas.pack(side="left", padx=4)
        self._registrar_tooltip(self.btn_reparar_todas, "reparar_todas")

        self.btn_refrescar_usb = BotonProfesional(
            tarjeta_acciones_usb.cuerpo, text="Refrescar unidades",
            command=self._refrescar_unidades,
            color_fondo=self._paleta_actual()["frame"],
            color_fondo_hover=self._paleta_actual()["acento_suave"],
            color_texto=self._paleta_actual()["fg"], color_texto_hover=self._paleta_actual()["fg"],
            color_borde=self._paleta_actual()["borde"],
            fuente=self._fuente(10, True), alto=34,
        )
        self.btn_refrescar_usb.pack(side="left", padx=4)
        self._registrar_tooltip(self.btn_refrescar_usb, "refrescar")

        self.btn_cancelar = BotonProfesional(
            tarjeta_acciones_usb.cuerpo, text="Cancelar",
            command=self._cancelar_reparacion_actual,
            color_fondo=self._paleta_actual()["advertencia"],
            color_fondo_hover="#e09010",
            color_texto="#000000", color_texto_hover="#000000",
            color_borde=self._paleta_actual()["borde"],
            estilo_semantico="advertencia",
            fuente=self._fuente(10, True), alto=34,
        )
        self.btn_cancelar.pack(side="right", padx=(6, 0))
        self._registrar_tooltip(self.btn_cancelar, "cancelar")

        # Contador de reparadas.
        self.lbl_reparadas = tk.Label(
            self.tab_usb, text="Unidades reparadas: ninguna",
            background=self._paleta_actual()["panel"],
            foreground=self._paleta_actual()["texto_suave"],
            font=self._fuente(9)
        )
        self.lbl_reparadas.pack(anchor="w", padx=10, pady=(0, 4))

    def _cancelar_reparacion_actual(self) -> None:
        """Cancela la reparación en curso."""
        if not self._proceso_en_ejecucion:
            return
        self._cancelar_reparacion = True
        self._agregar_log("Cancelación de reparación solicitada.", "WARNING")
        self._notificador.mostrar_advertencia("Cancelando reparación…")

    # =======================================================================
    # Pestaña de log (rediseñada con búsqueda)
    # =======================================================================
    def _crear_pestana_log(self) -> None:
        self.tab_log = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_log, text="  Registro  ")

        # Barra de búsqueda en la parte superior.
        self._barra_busqueda_log = BarraBusqueda(
            self.tab_log,
            placeholder="Filtrar registro…",
            callback=self._filtrar_log,
            color_fondo=self._paleta_actual()["field"],
            color_texto=self._paleta_actual()["fg"],
            color_borde=self._paleta_actual()["borde"],
            color_placeholder=self._paleta_actual()["texto_suave"],
            fuente=self._fuente(10),
        )
        self._barra_busqueda_log.pack(fill="x", padx=8, pady=(8, 4))

        # Área de texto.
        self.log_text = scrolledtext.ScrolledText(
            self.tab_log, wrap=tk.WORD, font=self._fuente_mono(9),
            relief="flat", borderwidth=0,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 8))
        self.log_text.configure(state=tk.DISABLED)
        self._registrar_tooltip(self.log_text, "registro")

        # Botones de control.
        log_control = tk.Frame(self.tab_log, background=self._paleta_actual()["bg"])
        log_control.pack(fill="x", padx=8, pady=(0, 8))

        self.btn_limpiar_log = BotonProfesional(
            log_control, text="Limpiar", command=self._limpiar_log,
            color_fondo=self._paleta_actual()["frame"],
            color_fondo_hover=self._paleta_actual()["acento_suave"],
            color_texto=self._paleta_actual()["fg"],
            color_texto_hover=self._paleta_actual()["fg"],
            color_borde=self._paleta_actual()["borde"],
            fuente=self._fuente(10), alto=30,
        )
        self.btn_limpiar_log.pack(side="left", padx=(0, 6))

        self.btn_exportar_log = BotonProfesional(
            log_control, text="Exportar", command=self._exportar_log,
            color_fondo=self._paleta_actual()["frame"],
            color_fondo_hover=self._paleta_actual()["acento_suave"],
            color_texto=self._paleta_actual()["fg"],
            color_texto_hover=self._paleta_actual()["fg"],
            color_borde=self._paleta_actual()["borde"],
            fuente=self._fuente(10), alto=30,
        )
        self.btn_exportar_log.pack(side="left", padx=4)
        self._registrar_tooltip(self.btn_exportar_log, "exportar_log")

        self._log_original = ""

    def _filtrar_log(self, texto: str) -> None:
        """Filtra el contenido del log según el texto de búsqueda."""
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)

        if not texto:
            self.log_text.insert(tk.END, self._log_original)
        else:
            lineas = self._log_original.splitlines()
            filtradas = [l for l in lineas if texto.lower() in l.lower()]
            self.log_text.insert(tk.END, "\n".join(filtradas) + "\n" if filtradas else "")

        self.log_text.configure(state=tk.DISABLED)
        self.log_text.see(tk.END)

    # =======================================================================
    # Pestaña de ayuda (mejorada)
    # =======================================================================
    def _crear_pestana_ayuda(self) -> None:
        self.tab_ayuda = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_ayuda, text="  Ayuda  ")

        contenedor = tk.Frame(self.tab_ayuda, background=self._paleta_actual()["bg"])
        contenedor.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Cabecera de la pestaña.
        cabecera = tk.Frame(contenedor, background=self._paleta_actual()["bg"])
        cabecera.pack(fill="x", pady=(0, 8))

        lbl_titulo_ayuda = tk.Label(
            cabecera, text="Guía visual de uso",
            background=self._paleta_actual()["bg"],
            foreground=self._paleta_actual()["acento"],
            font=self._fuente(14, True)
        )
        lbl_titulo_ayuda.pack(side="left")

        btn_compat = BotonProfesional(
            cabecera, text="Comprobar mi sistema",
            command=self._mostrar_compatibilidad,
            color_fondo=self._paleta_actual()["acento"],
            color_fondo_hover=self._paleta_actual()["acento_oscuro"],
            color_texto="#ffffff", color_texto_hover="#ffffff",
            color_borde=self._paleta_actual()["borde"],
            fuente=self._fuente(10, True), alto=30,
        )
        btn_compat.pack(side="right", padx=(0, 6))

        btn_exportar = BotonProfesional(
            cabecera, text="Exportar guía",
            command=self._exportar_guia,
            color_fondo=self._paleta_actual()["frame"],
            color_fondo_hover=self._paleta_actual()["acento_suave"],
            color_texto=self._paleta_actual()["fg"],
            color_texto_hover=self._paleta_actual()["fg"],
            color_borde=self._paleta_actual()["borde"],
            fuente=self._fuente(10), alto=30,
        )
        btn_exportar.pack(side="right", padx=(0, 6))

        # Texto de ayuda.
        marco = tk.Frame(contenedor, background=self._paleta_actual()["panel"])
        marco.pack(fill=tk.BOTH, expand=True)

        self.ayuda_text = tk.Text(
            marco, wrap="word", relief="flat", padx=18, pady=16,
            spacing1=3, spacing3=6, cursor="arrow",
            font=self._fuente(10),
        )
        barra = ttk.Scrollbar(marco, orient="vertical", command=self.ayuda_text.yview)
        self.ayuda_text.configure(yscrollcommand=barra.set, state="normal")
        barra.pack(side="right", fill="y")
        self.ayuda_text.pack(side="left", fill=tk.BOTH, expand=True)

        self._volcar_contenido_ayuda()
        self.ayuda_text.configure(state="disabled")

        pie = tk.Label(
            contenedor,
            text="Consejo: F1 abre esta guía desde cualquier pestaña. Pase el ratón por los botones para ver ayuda emergente.",
            background=self._paleta_actual()["bg"],
            foreground=self._paleta_actual()["texto_suave"],
            font=self._fuente(9), justify="left"
        )
        pie.pack(fill="x", pady=(8, 0))

    # =======================================================================
    # Barra de estado profesional
    # =======================================================================
    def _crear_barra_estado_profesional(self) -> None:
        """Barra de estado con múltiples indicadores."""
        paleta = self._paleta_actual()

        barra = tk.Frame(self.root, background=paleta["status_bg"], height=28)
        barra.pack(side="bottom", fill="x")
        barra.pack_propagate(False)

        self._indicador_usb = IndicadorEstado(
            barra, texto="USB: monitoreando",
            color_punto=paleta["exito"], color_texto=paleta["fg"],
            fondo=paleta["status_bg"], fuente=self._fuente(9),
        )
        self._indicador_usb.pack(side="left", padx=(8, 4))

        self.status_var = tk.StringVar(value="Iniciado")
        lbl_status = tk.Label(
            barra, textvariable=self.status_var,
            background=paleta["status_bg"], foreground=paleta["fg"],
            font=self._fuente(9)
        )
        lbl_status.pack(side="left", padx=(0, 8))

        tk.Frame(barra, background=paleta["borde"], width=1).pack(side="left", fill="y", padx=4)

        self._indicador_proceso = IndicadorEstado(
            barra, texto="Sin procesos en ejecución",
            color_punto=paleta["texto_suave"], color_texto=paleta["fg"],
            fondo=paleta["status_bg"], fuente=self._fuente(9),
        )
        self._indicador_proceso.pack(side="left", padx=4)

        tk.Frame(barra, background=paleta["borde"], width=1).pack(side="left", fill="y", padx=4)

        info = compat.obtener_info_plataforma()
        self.lbl_plataforma = tk.Label(
            barra,
            text=f"{info.nombre_amigable} · {info.arquitectura} · soporte {info.nivel_soporte}",
            background=paleta["status_bg"], foreground=paleta["texto_suave"],
            font=self._fuente(9)
        )
        self.lbl_plataforma.pack(side="right", padx=(0, 10))
        self._registrar_tooltip(self.lbl_plataforma,
                                "Detalle en Ayuda → Comprobar compatibilidad del sistema")

    # =======================================================================
    # Funciones auxiliares
    # =======================================================================
    def _agregar_log(self, mensaje: str, nivel: str = "INFO") -> None:
        """Agrega un mensaje al log y lo filtra si hay búsqueda activa."""
        linea = f"[{nivel}] {mensaje}\n"
        self._log_original += linea

        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, linea)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

        # Si hay filtro activo, reaplicar.
        filtro = self._barra_busqueda_log.obtener_texto()
        if filtro:
            self._filtrar_log(filtro)

    def _registrar_tooltip(self, widget, clave_o_texto: str) -> None:
        tooltip = ayuda.asignar_tooltip(widget, clave_o_texto)
        if tooltip is not None:
            paleta = self._paleta_actual()
            tooltip.aplicar_colores(paleta["tooltip_bg"], paleta["tooltip_fg"], paleta["borde"])
            self._tooltips.append(tooltip)

    def _mostrar_menu_procesos(self, evento: tk.Event) -> None:
        seleccion = self.tree_procesos.selection()
        if seleccion:
            self._menu_procesos.mostrar(evento)

    def _mostrar_menu_usb(self, evento: tk.Event) -> None:
        seleccion = self.tree_usb.selection()
        if seleccion:
            self._menu_usb.mostrar(evento)

    def _copiar_ruta_seleccionada(self) -> None:
        seleccion = self.tree_procesos.selection()
        if seleccion:
            values = self.tree_procesos.item(seleccion[0])["values"]
            ruta = values[1] if len(values) > 1 else ""
            if ruta:
                self.root.clipboard_clear()
                self.root.clipboard_append(ruta)
                self._notificador.mostrar_info(f"Ruta copiada: {ruta}")

    def _abrir_carpeta_seleccionada(self) -> None:
        import subprocess
        seleccion = self.tree_procesos.selection()
        if seleccion:
            values = self.tree_procesos.item(seleccion[0])["values"]
            ruta = values[1] if len(values) > 1 else ""
            if ruta and os.path.isdir(os.path.dirname(ruta)):
                carpeta = os.path.dirname(ruta)
                if sys.platform == "win32":
                    os.startfile(carpeta)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", carpeta])
                else:
                    subprocess.Popen(["xdg-open", carpeta])

    def _copiar_letra_seleccionada(self) -> None:
        seleccion = self.tree_usb.selection()
        if seleccion:
            values = self.tree_usb.item(seleccion[0])["values"]
            letra = values[0] if values else ""
            if letra:
                self.root.clipboard_clear()
                self.root.clipboard_append(letra)
                self._notificador.mostrar_info(f"Letra copiada: {letra}")

    # =======================================================================
    # Bienvenida y compatibilidad
    # =======================================================================
    def _mostrar_bienvenida(self) -> None:
        config = _cargar_config()
        if config.get("bienvenida_vista"):
            return
        info = compat.obtener_info_plataforma()
        mensaje = (
            f"Bienvenido a {NOMBRE_APP} v{VERSION_APP}\n\n"
            "Esta herramienta hace tres cosas:\n\n"
            "  1.  Detecta unidades USB con la estructura falsa\n"
            "      Kaspersky\\Usb Drive y restaura sus archivos.\n"
            "  2.  Busca procesos y rutas de EACoreServer.exe.\n"
            "  3.  Registra todo con verificación SHA-256.\n\n"
            "Es conservadora: nunca borra lo que no reconoce y\n"
            "siempre pide confirmación antes de reparar.\n\n"
            f"Sistema: {info.nombre_amigable} ({info.arquitectura})\n"
            f"Soporte: {info.nivel_soporte}\n\n"
            "Pulse F1 para la guía completa.\n"
            "Cambie colores y tamaño en el menú Ver."
        )
        if info.motivo:
            mensaje += f"\n\nNota: {info.motivo}"

        try:
            messagebox.showinfo(f"Bienvenido a {NOMBRE_APP}", mensaje)
        finally:
            config["bienvenida_vista"] = True
            _guardar_config(config)

    def _mostrar_compatibilidad(self) -> None:
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
            "Sistemas atendidos:\n"
            "    · Windows Vista, 7, 8, 8.1, 10 y 11 (x86 y x64)\n"
            "    · macOS, Linux, FreeBSD, OpenBSD, NetBSD, Solaris y AIX\n\n"
            "Windows XP y Server 2003 no son compatibles."
        )

    def _exportar_guia(self) -> None:
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
            self._notificador.mostrar_exito(f"Guía exportada a {ruta}")
        except OSError as exc:
            logger.error(f"No se pudo exportar la guía: {exc}")
            messagebox.showerror("Error al exportar", f"No se pudo guardar la guía:\n{exc}")

    # =======================================================================
    # Volcado de ayuda
    # =======================================================================
    def _volcar_contenido_ayuda(self) -> None:
        texto = self.ayuda_text
        texto.configure(state="normal")
        texto.delete("1.0", "end")

        def escribir(contenido: str, etiqueta: str = "cuerpo") -> None:
            texto.insert("end", contenido + "\n", etiqueta)

        def espacio(lineas: int = 1) -> None:
            for _ in range(lineas):
                texto.insert("end", "\n", "cuerpo")

        escribir(f"{NOMBRE_APP} v{VERSION_APP} - Guía de uso", "titulo")
        escribir("Herramienta de diagnóstico y reparación conservadora.", "suave")
        espacio()

        escribir("1. Pasos recomendados", "subtitulo")
        for numero, (titulo, detalle) in enumerate(ayuda.PASOS_GUIA, 1):
            escribir(f"   {numero}.  {titulo}", "info")
            for linea in self._ajustar_texto(detalle, 86):
                escribir(f"        {linea}", "cuerpo")
            espacio()

        escribir("2. Qué significan los estados", "subtitulo")
        for nombre, simbolo, tono, descripcion in ayuda.LEYENDA_ESTADOS:
            escribir(f"   {simbolo}  {nombre}", tono if tono in ("exito", "error", "advertencia") else "cuerpo")
            for linea in self._ajustar_texto(descripcion, 86):
                escribir(f"        {linea}", "suave")
        espacio()

        escribir("3. La firma que se busca en el USB", "subtitulo")
        escribir("   Solo se repara cuando aparece esta estructura completa:", "cuerpo")
        espacio()
        for linea in ayuda.ESTRUCTURA_FIRMA.splitlines():
            escribir(f"   {linea}", "mono")
        espacio()
        for regla in ayuda.REGLAS_FIRMA:
            for linea in self._ajustar_texto("•  " + regla, 90):
                escribir(f"   {linea}", "cuerpo")
        espacio()

        escribir("4. Qué hace cada botón", "subtitulo")
        for boton, descripcion in ayuda.ACCIONES_BOTONES:
            escribir(f"   ▸  {boton}", "info")
            for linea in self._ajustar_texto(descripcion, 86):
                escribir(f"        {linea}", "cuerpo")
        espacio()

        escribir("5. Avisos de seguridad", "subtitulo")
        for nota in ayuda.NOTAS_SEGURIDAD:
            for linea in self._ajustar_texto("⚠  " + nota, 90):
                escribir(f"   {linea}", "aviso" if linea.startswith("⚠") else "cuerpo")
        espacio()

        escribir("6. Preguntas frecuentes", "subtitulo")
        for pregunta, respuesta in ayuda.PREGUNTAS_FRECUENTES:
            escribir(f"   ?  {pregunta}", "subtitulo")
            for linea in self._ajustar_texto(respuesta, 86):
                escribir(f"        {linea}", "cuerpo")
            espacio()

        escribir("7. Su sistema", "subtitulo")
        for campo, valor in ayuda.obtener_info_sistema():
            escribir(f"   {campo}:", "info")
            for linea in self._ajustar_texto(str(valor), 86):
                escribir(f"        {linea}", "cuerpo")

        self._recolorear_tags_ayuda(self._paleta_actual())

    @staticmethod
    def _ajustar_texto(texto: str, ancho: int) -> List[str]:
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
        if hasattr(self, "tab_ayuda"):
            self.notebook.select(self.tab_ayuda)

    # =======================================================================
    # Funciones de procesos
    # =======================================================================
    def _escanear_rutas(self) -> None:
        if self._proceso_en_ejecucion:
            messagebox.showwarning("Aviso", "Ya hay una operación en ejecución.")
            return

        self._proceso_en_ejecucion = True
        self.status_var.set("Escaneando rutas…")
        self._indicador_proceso.cambiar_estado(self._paleta_actual()["advertencia"], "Escaneando…")
        self._agregar_log("Iniciando escaneo de rutas EACoreServer…", "INFO")

        def _trabajo():
            try:
                rutas = obtener_rutas_candidatas()
                self.root.after(0, self._agregar_log,
                                f"{len(rutas)} rutas candidatas analizadas.", "INFO")

                gestor = obtener_gestor_procesos()
                resultados = gestor.escanear_rutas(rutas)
                self.root.after(0, self._actualizar_tabla_procesos, resultados)

                activos = sum(1 for r in resultados if r.estado == EstadoProceso.ACTIVO)
                inactivos = sum(1 for r in resultados if r.estado == EstadoProceso.ENCONTRADO_INACTIVO)
                self.root.after(0, lambda: self._agregar_log(
                    f"Escaneo completado: {activos} activos, {inactivos} inactivos.", "INFO"))
                self.root.after(0, lambda: self.status_var.set(
                    f"{activos} activos, {inactivos} inactivos"))
                self.root.after(0, lambda: self._indicador_proceso.cambiar_estado(
                    self._paleta_actual()["error"] if activos else self._paleta_actual()["exito"],
                    f"{activos} activos"))

                if activos > 0:
                    self.root.after(0, lambda: self._notificador.mostrar_advertencia(
                        f"Se detectaron {activos} proceso(s) activo(s)"))
            except Exception as e:
                self.root.after(0, lambda: self._agregar_log(f"Error en escaneo: {e}", "ERROR"))
                self.root.after(0, lambda: self.status_var.set("Error en escaneo"))
            finally:
                self.root.after(0, lambda: setattr(self, "_proceso_en_ejecucion", False))

        threading.Thread(target=_trabajo, daemon=True).start()

    def _actualizar_tabla_procesos(self, resultados: List[InfoRutaEACore]) -> None:
        self._resultados_procesos = list(resultados)
        for item in self.tree_procesos.get_children():
            self.tree_procesos.delete(item)

        for info in resultados:
            d = info.a_dict()
            tags = ()
            if d["estado"] == "activo":
                tags = ("activo",)
            elif d["estado"] == "encontrado_inactivo":
                tags = ("inactivo",)
            self.tree_procesos.insert("", "end", values=(
                d["indice"], d["ruta"], d["estado"], d["pid"],
                d["usuario"], d["tamano_kb"], d["servicio"],
                d["clasificacion"], d["error"]
            ), tags=tags)

        activos = sum(1 for r in resultados if r.estado == EstadoProceso.ACTIVO)
        self.lbl_proceso_count.config(text=f"Total: {len(resultados)} | Activos: {activos}")

    def _refrescar_procesos(self) -> None:
        self._escanear_rutas()

    def _finalizar_todos(self) -> None:
        if self._proceso_en_ejecucion:
            messagebox.showwarning("Aviso", "Ya hay una operación en ejecución.")
            return
        rutas_activas = [
            info.ruta for info in self._resultados_procesos
            if info.estado == EstadoProceso.ACTIVO
        ]
        if not rutas_activas:
            messagebox.showinfo("Info", "No hay procesos activos para finalizar.")
            return
        if not messagebox.askyesno(
            "Finalizar procesos",
            f"Se finalizarán {len(rutas_activas)} proceso(s) activos.\n\n"
            "EACoreServer.exe puede ser legítimo (EA/Origin). "
            "No se eliminarán archivos.\n\n¿Continuar?",
        ):
            return

        self._proceso_en_ejecucion = True
        self.status_var.set("Finalizando procesos…")
        self._agregar_log("Finalizando procesos activos…", "INFO")

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
        seleccion = self.tree_procesos.selection()
        if not seleccion:
            messagebox.showwarning("Aviso", "No hay ninguna ruta seleccionada.")
            return

        values = self.tree_procesos.item(seleccion[0])["values"]
        ruta = values[1]
        estado = values[2]

        if estado != "activo":
            messagebox.showinfo("Info", "La ruta seleccionada no tiene un proceso activo.")
            return

        self._agregar_log(f"Finalizando proceso: {ruta}", "INFO")

        def _trabajo():
            try:
                gestor = obtener_gestor_procesos()
                rutas = obtener_rutas_candidatas()
                infos = gestor.escanear_rutas(rutas)
                objetivo = next((i for i in infos if i.ruta == ruta), None)
                if objetivo and objetivo.estado == EstadoProceso.ACTIVO and objetivo.pid:
                    exito, msg = gestor.finalizar_proceso(objetivo)
                    self.root.after(0, lambda: self._agregar_log(
                        f"Proceso {ruta}: {msg}", "EXITO" if exito else "ERROR"))
                    nuevos = gestor.escanear_rutas(rutas)
                    self.root.after(0, lambda: self._actualizar_tabla_procesos(nuevos))
                else:
                    self.root.after(0, lambda: self._agregar_log(
                        "El proceso ya no está activo.", "INFO"))
            except Exception as e:
                self.root.after(0, lambda: self._agregar_log(f"Error: {e}", "ERROR"))

        threading.Thread(target=_trabajo, daemon=True).start()

    def _finalizar_por_ruta(self) -> None:
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
                            f"Finalización de {ruta}: {msg}", "EXITO" if exito else "ERROR"))
                        rutas = obtener_rutas_candidatas()
                        nuevos = gestor.escanear_rutas(rutas)
                        self.root.after(0, lambda: self._actualizar_tabla_procesos(nuevos))
                    except Exception as e:
                        self.root.after(0, lambda: self._agregar_log(f"Error: {e}", "ERROR"))
                    finally:
                        self.root.after(0, lambda: setattr(self, "_proceso_en_ejecucion", False))
                threading.Thread(target=_trabajo, daemon=True).start()
            else:
                messagebox.showinfo("Info", "El proceso no está activo o no se encontró.")

    def _eliminar_exe_dat_seleccionado(self) -> None:
        seleccion = self.tree_procesos.selection()
        if not seleccion:
            messagebox.showwarning("Aviso", "No hay ninguna ruta seleccionada.")
            return
        values = self.tree_procesos.item(seleccion[0])["values"]
        ruta = values[1]
        if not ruta or "eacoreserver.exe" not in ruta.lower():
            messagebox.showwarning("Aviso", "La fila no corresponde a EACoreServer.exe.")
            return
        gestor = obtener_gestor_procesos()
        if gestor.ruta_probablemente_legitima(ruta):
            messagebox.showwarning(
                "Componente de EA protegido",
                "La ruta parece pertenecer a EA/Origin o a un juego legítimo.\n\n"
                "Por seguridad no se eliminará. Revise la firma digital.",
            )
            return
        ruta_dat1 = os.path.join(os.path.dirname(ruta), "EACore.dat")
        ruta_dat2 = os.path.join(os.path.dirname(ruta), "EACore.dll")
        if not messagebox.askyesno(
            "Eliminar archivos",
            "Se detendrá el proceso/servicio y se eliminarán:\n\n"
            f"  {ruta}\n  {ruta_dat1}\n  {ruta_dat2}\n\n¿Continuar?",
        ):
            return
        self._ejecutar_trabajo_eliminacion(ruta, "fila seleccionada")

    def _eliminar_servicio_programdata(self) -> None:
        ruta = r"C:\ProgramData\EACoreService\EACoreServer.exe"
        if not os.path.exists(ruta):
            messagebox.showinfo("Info",
                "EACoreService no está instalado\n(no existe C:\\ProgramData\\EACoreService\\EACoreServer.exe).")
            return
        ruta_dat1 = os.path.join(os.path.dirname(ruta), "EACore.dat")
        ruta_dat2 = os.path.join(os.path.dirname(ruta), "EACore.dll")
        if not messagebox.askyesno(
            "Detener y eliminar EACoreService",
            "Se detendrá y deshabilitará el servicio y se eliminarán:\n\n"
            f"  {ruta}\n  {ruta_dat1}\n  {ruta_dat2}\n\n"
            "Nota: podría afectar a EA App/Origin hasta reiniciar.\n¿Continuar?",
        ):
            return
        self._ejecutar_trabajo_eliminacion(ruta, "ProgramData")

    def _ejecutar_trabajo_eliminacion(self, ruta: str, origen: str) -> None:
        if self._proceso_en_ejecucion:
            messagebox.showwarning("Aviso", "Ya hay una operación en ejecución.")
            return
        self._proceso_en_ejecucion = True
        self.status_var.set(f"Eliminando archivos de {ruta}...")
        self._agregar_log(f"Iniciando eliminación completa ({origen}): {ruta}", "WARNING")

        def _trabajo():
            try:
                gestor = obtener_gestor_procesos()
                resultados = gestor.detener_y_eliminar_archivos(ruta)
                self.root.after(0, lambda: self._agregar_log(
                    f"Servicio detenido: {resultados['servicio_detenido']} | "
                    f"Servicio deshabilitado: {resultados['servicio_deshabilitado']} | "
                    f"exe: {resultados['exe_eliminado']} | "
                    f"dat: {resultados['dat_eliminado']} | "
                    f"dll: {resultados['dll_eliminado']}", "INFO"))
                for detalle in resultados.get("detalles", []):
                    self.root.after(0, lambda d=detalle: self._agregar_log(f"  - {d}", "INFO"))
                rutas = obtener_rutas_candidatas()
                nuevos = gestor.escanear_rutas(rutas)
                self.root.after(0, lambda: self._actualizar_tabla_procesos(nuevos))
                self.root.after(0, lambda: self.status_var.set("Eliminación completada"))
                self.root.after(0, lambda: self._notificador.mostrar_exito(
                    "Archivos eliminados correctamente"))
            except Exception as e:
                self.root.after(0, lambda: self._agregar_log(f"Error eliminando: {e}", "ERROR"))
                self.root.after(0, lambda: self.status_var.set("Error en la eliminación"))
                self.root.after(0, lambda: self._notificador.mostrar_error(f"Error: {e}"))
            finally:
                self.root.after(0, lambda: setattr(self, "_proceso_en_ejecucion", False))

        threading.Thread(target=_trabajo, daemon=True).start()

    # =======================================================================
    # Funciones de USB
    # =======================================================================
    def _iniciar_monitor_usb(self) -> None:
        monitor = obtener_monitor_usb()

        def on_usb_insertada(unidad: UnidadExtraible) -> None:
            detalle = f" ({unidad.etiqueta})" if unidad.etiqueta and unidad.etiqueta not in ("(sin metadatos)", "SIN_ETIQUETA") else ""
            self.root.after(0, self._agregar_log, f"Unidad detectada: {unidad.letra}{detalle}", "INFO")
            self.root.after(0, self._refrescar_unidades)
            self.root.after(0, lambda: self.status_var.set(f"Unidad {unidad.letra} detectada"))
            self.root.after(0, lambda: self._indicador_usb.cambiar_estado(
                self._paleta_actual()["exito"], f"USB: {unidad.letra} detectada"))
            self.root.after(0, lambda: self._notificador.mostrar_info(
                f"Unidad {unidad.letra} detectada{detalle}"))
            self.root.after(1000, lambda: self._verificar_y_reparar(unidad.letra))

        def on_usb_removida(letra: str) -> None:
            self.root.after(0, self._agregar_log, f"Unidad {letra} removida.", "INFO")
            self.root.after(0, self._refrescar_unidades)

        if monitor.iniciar(on_usb_insertada, on_usb_removida):
            self._agregar_log("Monitor USB activado.", "INFO")
        else:
            self._agregar_log("Monitor USB en modo polling.", "WARNING")

        self._refrescar_unidades()
        self.root.after(3000, self._auto_refrescar_usb)

    def _auto_refrescar_usb(self) -> None:
        if self.root.winfo_exists():
            self._refrescar_unidades()
            self.root.after(3000, self._auto_refrescar_usb)

    def _refrescar_unidades(self) -> None:
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
                self._agregar_log("Sin unidades conectadas.", "DEBUG")
            self._ultimo_conteo_usb = 0
        else:
            for unidad in unidades:
                tamano_gb = round(unidad.tamano_total / (1024 ** 3), 1)
                libre_gb = round(unidad.espacio_libre / (1024 ** 3), 1)
                diagnostico = motor.analizar_ruta(unidad.ruta_raiz)

                if not unidad.es_reparable_con_seguridad:
                    clave_estado = "solo_diagnostico"
                elif diagnostico.estado is EstadoDeteccion.CONFIRMADA:
                    clave_estado = "confirmada"
                elif diagnostico.estado is EstadoDeteccion.SOSPECHOSA:
                    clave_estado = "sospechosa"
                elif diagnostico.estado is EstadoDeteccion.INACCESIBLE:
                    clave_estado = "inaccesible"
                elif unidad.letra in self._unidades_con_errores:
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
            self.lbl_reparadas.config(text=f"Unidades reparadas: {', '.join(reparadas)}")
        else:
            self.lbl_reparadas.config(text="Unidades reparadas: ninguna")

    def _reparar_todas_usb(self) -> None:
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
            messagebox.showinfo("Sin reparaciones pendientes",
                "No hay unidades con firma completa confirmada.")
            return
        letras = ", ".join(u.letra for u in candidatas)
        if not messagebox.askyesno("Confirmar reparación",
            f"Se repararán: {letras}.\n\nNo se borrará contenido no reconocido. ¿Continuar?"):
            return

        self._proceso_en_ejecucion = True
        self._cancelar_reparacion = False
        self.status_var.set("Reparando unidades…")
        self._agregar_log(f"Iniciando reparación de: {letras}", "INFO")

        def _trabajo() -> None:
            try:
                for unidad in candidatas:
                    if self._cancelar_reparacion:
                        break
                    self.root.after(0, lambda: self._barra_progreso.establecer(0))
                    self.root.after(0, lambda u=unidad: self.lbl_progreso.config(
                        text=f"Procesando {u.letra}…"))
                    resultado = motor.reparar_unidad(
                        unidad.letra, callback_progreso=self._actualizar_progreso)
                    self.root.after(0, self._registrar_resultado_reparacion, resultado)
            except Exception as exc:
                self.root.after(0, lambda: self._agregar_log(f"Error: {exc}", "ERROR"))
            finally:
                self.root.after(0, lambda: setattr(self, "_cancelar_reparacion", False))
                self.root.after(0, lambda: setattr(self, "_proceso_en_ejecucion", False))
                self.root.after(0, lambda: self.status_var.set("Reparación finalizada"))
                self.root.after(0, self._refrescar_unidades)

        threading.Thread(target=_trabajo, daemon=True).start()

    def _reparar_unidad_seleccionada(self) -> None:
        if self._proceso_en_ejecucion:
            messagebox.showwarning("Aviso", "Ya hay una operación en ejecución.")
            return
        seleccion = self.tree_usb.selection()
        if not seleccion:
            messagebox.showwarning("Aviso", "No hay unidad seleccionada.")
            return
        valores = self.tree_usb.item(seleccion[0])["values"]
        letra = valores[0]
        if not letra:
            messagebox.showwarning("Aviso", "No hay unidad disponible.")
            return

        unidad = next(
            (u for u in obtener_monitor_usb().obtener_unidades_actuales() if u.letra == letra), None)
        if not unidad or not unidad.es_reparable_con_seguridad:
            messagebox.showwarning("Destino no permitido",
                "Solo se reparan medios extraíbles o USB físicos.")
            return
        diagnostico = obtener_motor_reparacion().analizar_ruta(unidad.ruta_raiz)
        if diagnostico.estado is not EstadoDeteccion.CONFIRMADA:
            messagebox.showwarning("Firma no confirmada",
                f"La estructura no está completa.\n\nDetalle: {diagnostico.detalle or 'Sin firma.'}")
            return
        if not messagebox.askyesno("Confirmar reparación",
            f"Unidad {letra}: firma completa detectada.\n\n"
            "Se restaurarán archivos y se eliminarán solo los ficheros de firma.\n¿Continuar?"):
            return
        self._reparar_unidad_internal(letra)

    def _registrar_resultado_reparacion(self, resultado: ResultadoReparacion) -> None:
        nivel = "INFO" if resultado.estado is EstadoReparacion.COMPLETADO else "WARNING"
        resumen = ayuda.texto_reparacion(resultado.estado.value)
        self._agregar_log(f"Reparación de {resultado.unidad}: {resumen}", nivel)
        self._agregar_log(
            f"Archivos movidos: {resultado.archivos_movidos}; carpetas: "
            f"{resultado.carpetas_movidas}; eliminados: {len(resultado.archivos_eliminados)}; "
            f"SHA-256 verificados: {len(resultado.sumas_sha256)}; errores: {len(resultado.errores)}",
            "INFO")
        for error in resultado.errores:
            self._agregar_log(f"Detalle: {error}", "ERROR")
        self.status_var.set(f"{resultado.unidad}: {resumen}")

        terminado = resultado.estado in (
            EstadoReparacion.COMPLETADO, EstadoReparacion.COMPLETADO_CON_ERRORES)
        if terminado:
            marcar_unidad_reparada(resultado.unidad)
        con_errores = resultado.estado is EstadoReparacion.COMPLETADO_CON_ERRORES
        if con_errores:
            self._unidades_con_errores.add(resultado.unidad)
        else:
            self._unidades_con_errores.discard(resultado.unidad)
        self._persistir_unidades_con_errores()

        self._refrescar_unidades()

        if terminado:
            self._notificador.mostrar_exito(f"{resultado.unidad}: {resumen}")
        elif con_errores:
            self._notificador.mostrar_advertencia(f"{resultado.unidad}: {resumen}")
        else:
            self._notificador.mostrar_error(f"{resultado.unidad}: {resumen}")

    def _persistir_unidades_con_errores(self) -> None:
        try:
            config = _cargar_config()
            config["unidades_con_errores"] = sorted(self._unidades_con_errores)
            _guardar_config(config)
        except Exception as exc:
            logger.warning(f"No se pudieron guardar las unidades con errores: {exc}")

    def _reparar_unidad_internal(self, letra: str) -> None:
        self._proceso_en_ejecucion = True
        self._cancelar_reparacion = False
        self.status_var.set(f"Reparando {letra}…")
        self._barra_progreso.restablecer()

        def _trabajo() -> None:
            try:
                resultado = obtener_motor_reparacion().reparar_unidad(
                    letra, callback_progreso=self._actualizar_progreso)
                self.root.after(0, self._registrar_resultado_reparacion, resultado)
            except Exception as exc:
                self.root.after(0, lambda: self._agregar_log(f"Error en {letra}: {exc}", "ERROR"))
            finally:
                self.root.after(0, lambda: setattr(self, "_proceso_en_ejecucion", False))
                self.root.after(0, lambda: setattr(self, "_cancelar_reparacion", False))

        threading.Thread(target=_trabajo, daemon=True).start()

    def _verificar_y_reparar(self, letra: str) -> None:
        try:
            unidad = next(
                (u for u in obtener_monitor_usb().obtener_unidades_actuales() if u.letra == letra), None)
            if not unidad or not unidad.es_reparable_con_seguridad:
                return
            diagnostico = obtener_motor_reparacion().analizar_ruta(unidad.ruta_raiz)
            if diagnostico.estado is EstadoDeteccion.CONFIRMADA:
                self._agregar_log(f"Firma completa en {letra}. Requiere confirmación.", "WARNING")
                self.status_var.set(f"Firma en {letra}; revise Reparación de unidades.")
            elif diagnostico.estado is EstadoDeteccion.SOSPECHOSA:
                self._agregar_log(f"Estructura incompleta en {letra}.", "WARNING")
        except Exception as exc:
            logger.error(f"Error verificando {letra}: {exc}")

    def _actualizar_progreso(self, pct: int, mensaje: str) -> None:
        self.root.after(0, lambda: self._barra_progreso.establecer(pct))
        self.root.after(0, lambda: self.lbl_progreso.config(text=mensaje))

    # =======================================================================
    # Funciones de log
    # =======================================================================
    def _limpiar_log(self) -> None:
        self._log_original = ""
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state=tk.DISABLED)
        self._notificador.mostrar_info("Registro limpiado")

    def _exportar_log(self) -> None:
        ruta = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Archivos de log", "*.log"), ("Todos los archivos", "*.*")],
            title="Exportar Log")
        if ruta:
            try:
                contenido = self.log_text.get(1.0, tk.END)
                with open(ruta, "w", encoding="utf-8") as f:
                    f.write(contenido)
                self._agregar_log(f"Log exportado a: {ruta}", "INFO")
                self._notificador.mostrar_exito(f"Log exportado a {ruta}")
            except Exception as e:
                self._agregar_log(f"Error exportando log: {e}", "ERROR")
                self._notificador.mostrar_error(f"Error exportando: {e}")

    def _acerca_de(self) -> None:
        info = compat.obtener_info_plataforma()
        messagebox.showinfo(
            f"Acerca de {NOMBRE_APP}",
            f"{NOMBRE_APP} v{VERSION_APP}\n"
            "Protección contra malware USB y gestión de procesos\n\n"
            "Sistemas: Windows Vista a 11 (x86/x64), macOS, Linux, BSD,\n"
            "Solaris/illumos y AIX.\n\n"
            f"Sistema actual: {info.nombre_amigable}\n"
            f"Arquitectura: {info.arquitectura} ({info.bits_proceso} bits)\n"
            f"Python: {info.python_version}\n\n"
            "Requiere Python 3.8+\n"
            "Ing. Yosvany Hernández Quintero",
        )

    def _salir(self) -> None:
        self._agregar_log("Cerrando aplicación…", "INFO")
        monitor = obtener_monitor_usb()
        monitor.detener()
        self._notificador.limpiar_todos()
        self.root.destroy()


def _apariencia_guardada() -> Dict[str, Any]:
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
    try:
        import ctypes
        from ctypes import wintypes
        rect = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
        if rect.right > rect.left and rect.bottom > rect.top:
            return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
    except Exception:
        pass
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    return 0, 0, sw, max(sh - 60, 400)


def _ajustar_ventana_a_pantalla(root: tk.Tk) -> None:
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

    apariencia = _apariencia_guardada()
    paleta_inicial = temas.construir_paleta(apariencia["tema"], apariencia["acento"])
    root.configure(bg=paleta_inicial["bg"])

    root.title(f"{NOMBRE_APP} v{VERSION_APP}")

    VENTANA_ANCHO = 1320
    VENTANA_ALTO = 820

    x0, y0, w_area, h_area = _area_trabajo_pantalla(root)
    ancho = min(VENTANA_ANCHO, w_area - 10)
    alto = min(VENTANA_ALTO, h_area - 10)
    x = x0 + max((w_area - ancho) // 2, 0)
    y = y0 + max((h_area - alto) // 2, 0)
    root.geometry(f"{ancho}x{alto}+{x}+{y}")
    root._geometria_controlada = True

    root.minsize(min(1100, max(w_area - 10, 640)), min(700, max(h_area - 10, 480)))

    try:
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icono.ico")
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception:
        pass

    app = AntivirusGUI(root)
    root.protocol("WM_DELETE_WINDOW", app._salir)

    _ajustar_ventana_a_pantalla(root)

    root.mainloop()


if __name__ == "__main__":
    ejecutar_aplicacion()
