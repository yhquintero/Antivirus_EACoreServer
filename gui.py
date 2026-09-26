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
from typing import List, Optional, Tuple
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


# Paletas de colores para los temas (claro / oscuro)
PALETAS = {
    "oscuro": {
        "bg": "#1e1e1e", "frame": "#2b2b2b", "header": "#2c3e50",
        "fg": "#d4d4d4", "acento": "#3498db", "exito": "#2ecc71",
        "error": "#e74c3c", "advertencia": "#f39c12", "blanco": "#ffffff",
        "tree_bg": "#252526", "tree_fg": "#e8e8e8", "field": "#252526",
        "log_bg": "#1e1e1e", "log_fg": "#d4d4d4", "status_bg": "#2b2b2b",
        "activo_bg": "#593232", "inactivo_bg": "#5a4a25", "seleccion": "#264f78",
    },
    "claro": {
        "bg": "#f0f0f0", "frame": "#ffffff", "header": "#2c3e50",
        "fg": "#1a1a1a", "acento": "#0078d4", "exito": "#107c10",
        "error": "#c42b1c", "advertencia": "#8a6d00", "blanco": "#ffffff",
        "tree_bg": "#ffffff", "tree_fg": "#1a1a1a", "field": "#ffffff",
        "log_bg": "#ffffff", "log_fg": "#1a1a1a", "status_bg": "#e5e5e5",
        "activo_bg": "#ffebee", "inactivo_bg": "#fff3e0", "seleccion": "#cce4f7",
    },
}


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
        
        # Configuración persistente (tema guardado entre sesiones)
        config = _cargar_config()
        tema_guardado = config.get("tema", "sistema")
        self._tema_seleccion = tema_guardado if tema_guardado in ("oscuro", "claro", "sistema") else "sistema"
        self._tema_var = tk.StringVar(value=self._tema_seleccion)
        
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
    
    def _configurar_estilos(self) -> None:
        """Configura estilos base (tema oscuro por defecto)."""
        style = ttk.Style()
        style.theme_use("clam")
        self._aplicar_estilos_tema(PALETAS["oscuro"])
    
    def _detectar_tema_sistema(self) -> str:
        """Detecta el tema del sistema Windows (claro/oscuro) vía registro."""
        try:
            import winreg
            clave = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            )
            try:
                valor, _ = winreg.QueryValueEx(clave, "AppsUseLightTheme")
                return "claro" if valor else "oscuro"
            finally:
                winreg.CloseKey(clave)
        except Exception:
            return "oscuro"
    
    def _aplicar_estilos_tema(self, p: dict) -> None:
        """Aplica los colores de una paleta a todos los estilos ttk."""
        style = ttk.Style()
        style.theme_use("clam")
        
        # Etiquetas generales
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"),
                        foreground=p["acento"], background=p["bg"])
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10),
                        foreground=p["fg"], background=p["bg"])
        style.configure("Status.TLabel", font=("Segoe UI", 10),
                        foreground=p["fg"], background=p["status_bg"])
        style.configure("Header.TLabel", font=("Segoe UI", 11, "bold"), foreground=p["blanco"])
        style.configure("Header.TFrame", background=p["header"])
        
        style.configure("Green.TLabel", foreground=p["exito"], font=("Segoe UI", 10, "bold"),
                        background=p["bg"])
        style.configure("Red.TLabel", foreground=p["error"], font=("Segoe UI", 10, "bold"),
                        background=p["bg"])
        style.configure("Yellow.TLabel", foreground=p["advertencia"], font=("Segoe UI", 10, "bold"),
                        background=p["bg"])
        
        # Frames y contenedores
        style.configure("TFrame", background=p["bg"])
        style.configure("TLabelframe", background=p["bg"], foreground=p["fg"])
        style.configure("TLabelframe.Label", background=p["bg"], foreground=p["fg"])
        
        # Botones
        style.configure("TButton", font=("Segoe UI", 10, "bold"), background=p["frame"],
                        foreground=p["fg"], borderwidth=1)
        style.map("TButton",
                  background=[("active", p["seleccion"]), ("pressed", p["acento"])],
                  foreground=[("active", p["blanco"]), ("pressed", p["blanco"])])
        style.configure("Action.TButton", background=p["acento"], foreground=p["blanco"])
        style.map("Action.TButton",
                  background=[("active", p["seleccion"])], foreground=[("active", p["blanco"])])
        style.configure("Repair.TButton", background=p["exito"], foreground=p["blanco"])
        style.map("Repair.TButton",
                  background=[("active", p["seleccion"])], foreground=[("active", p["blanco"])])
        style.configure("Stop.TButton", background=p["error"], foreground=p["blanco"])
        style.map("Stop.TButton",
                  background=[("active", p["seleccion"])], foreground=[("active", p["blanco"])])
        
        # Notebook / pestañas
        style.configure("TNotebook", background=p["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=p["frame"], foreground=p["fg"],
                        padding=(12, 6))
        style.map("TNotebook.Tab",
                  background=[("selected", p["header"])],
                  foreground=[("selected", p["blanco"])])
        
        # Barra de progreso
        style.configure("TProgressbar", thickness=20, troughcolor=p["frame"],
                        background=p["acento"])
        
        # Treeview
        style.configure("Custom.Treeview", rowheight=26, font=("Consolas", 9),
                        background=p["tree_bg"], foreground=p["tree_fg"],
                        fieldbackground=p["field"], borderwidth=0)
        style.configure("Custom.Treeview.Heading", font=("Segoe UI", 9, "bold"),
                        background=p["header"], foreground=p["blanco"])
        style.map("Custom.Treeview", background=[("selected", p["seleccion"])])
        
        # Scrollbars
        style.configure("Vertical.TScrollbar", background=p["frame"], troughcolor=p["bg"],
                        arrowcolor=p["fg"], bordercolor=p["bg"])
        style.configure("Horizontal.TScrollbar", background=p["frame"], troughcolor=p["bg"],
                        arrowcolor=p["fg"], bordercolor=p["bg"])
    
    def _recolorear_widgets(self, p: dict) -> None:
        """Reaplica colores a widgets no gestionados por ttk (texto, tags)."""
        self.root.configure(bg=p["bg"])
        
        if hasattr(self, "log_text"):
            self.log_text.configure(bg=p["log_bg"], fg=p["log_fg"], insertbackground=p["fg"])
        
        if hasattr(self, "lbl_subtitulo"):
            self.lbl_subtitulo.configure(foreground=p["fg"])
        
        if hasattr(self, "lbl_reparadas"):
            self.lbl_reparadas.configure(foreground=p["fg"])
        
        # Tags de la tabla de procesos
        if hasattr(self, "tree_procesos"):
            self.tree_procesos.tag_configure("activo", background=p["activo_bg"])
            self.tree_procesos.tag_configure("inactivo", background=p["inactivo_bg"])
        
        # Tags de la tabla USB
        if hasattr(self, "tree_usb"):
            self.tree_usb.tag_configure("reparada", background=p["inactivo_bg"])
            self.tree_usb.tag_configure("infectada", background=p["activo_bg"])
    
    def _aplicar_tema(self, tema: str) -> None:
        """Aplica un tema (oscuro/claro/sistema) y guarda la preferencia."""
        if tema not in ("oscuro", "claro", "sistema"):
            tema = "sistema"
        self._tema_seleccion = tema
        self._tema_var.set(tema)
        
        # Resolver tema "sistema" al tema real de Windows
        resuelto = self._detectar_tema_sistema() if tema == "sistema" else tema
        paleta = PALETAS.get(resuelto, PALETAS["oscuro"])
        
        self._aplicar_estilos_tema(paleta)
        self._recolorear_widgets(paleta)
        
        # Persistir preferencia del usuario
        config = _cargar_config()
        config["tema"] = tema
        _guardar_config(config)
        
        logger.info(f"Tema aplicado: {tema} (resuelto: {resuelto})")
    
    def _crear_menu(self) -> None:
        """Crea la barra de menú."""
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
        
        # Menú Ver con selector de tema (claro / oscuro / sistema)
        menu_tema = tk.Menu(menubar, tearoff=0)
        menu_tema.add_radiobutton(label="Tema Oscuro", value="oscuro", variable=self._tema_var,
                                  command=lambda: self._aplicar_tema("oscuro"))
        menu_tema.add_radiobutton(label="Tema Claro", value="claro", variable=self._tema_var,
                                  command=lambda: self._aplicar_tema("claro"))
        menu_tema.add_radiobutton(label="Tema del Sistema", value="sistema", variable=self._tema_var,
                                  command=lambda: self._aplicar_tema("sistema"))
        menu_ver = tk.Menu(menubar, tearoff=0)
        menu_ver.add_cascade(label="Tema", menu=menu_tema)
        menubar.add_cascade(label="Ver", menu=menu_ver)
        
        menu_ayuda = tk.Menu(menubar, tearoff=0)
        menu_ayuda.add_command(label="Acerca de", command=self._acerca_de)
        menubar.add_cascade(label="Ayuda", menu=menu_ayuda)
        
        self.root.config(menu=menubar)
        self.root.bind("<Control-q>", lambda e: self._salir())
    
    def _crear_interfaz(self) -> None:
        """Crea la interfaz principal con pestañas."""
        # Frame principal
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Título principal con marco decorativo
        titulo_frame = ttk.Frame(main_frame, style="Header.TFrame")
        titulo_frame.pack(fill="x", pady=(0, 3))
        
        ttk.Label(titulo_frame, text="🛡️ Antivirus EACoreServer v1.1",
                   style="Title.TLabel").pack(side="left", padx=10)
        self.lbl_subtitulo = ttk.Label(titulo_frame, text="Protección USB | Gestión de Procesos",
                   font=("Segoe UI", 9), foreground="#d4d4d4")
        self.lbl_subtitulo.pack(side="left", padx=10)
        
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
        
        # Barra de estado
        self._crear_barra_estado()
    
    def _crear_pestana_procesos(self) -> None:
        """Crea la pestaña de gestión de procesos EACoreServer."""
        self.tab_procesos = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_procesos, text="  Procesos EACoreServer  ")
        
        # Frame de controles
        control_frame = ttk.Frame(self.tab_procesos)
        control_frame.pack(fill="x", pady=5)
        
        ttk.Button(control_frame, text="Escanear Rutas", command=self._escanear_rutas,
                   style="Action.TButton").pack(side="left", padx=5)
        ttk.Button(control_frame, text="Finalizar Todos", command=self._finalizar_todos,
                   style="Action.TButton").pack(side="left", padx=5)
        ttk.Button(control_frame, text="Refrescar", command=self._refrescar_procesos,
                   style="Action.TButton").pack(side="left", padx=5)
        
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
        
        ttk.Button(accion_frame, text="Finalizar Seleccionado", 
                   command=self._finalizar_seleccionado).pack(side="left", padx=5)
        ttk.Button(accion_frame, text="Finalizar por Ruta", 
                   command=self._finalizar_por_ruta).pack(side="left", padx=5)
        ttk.Button(accion_frame, text="Eliminar .exe + .dat + .dll Seleccionado", 
                   command=self._eliminar_exe_dat_seleccionado).pack(side="left", padx=5)
        
        # Acción excepcional para la ruta no estándar de ProgramData. Requiere
        # confirmación; el nombre EACoreServer.exe no basta para identificar malware.
        servicio_frame = ttk.Frame(self.tab_procesos)
        servicio_frame.pack(fill="x", pady=(0, 5))
        ttk.Button(servicio_frame, text="Detener y Eliminar EACoreService (.exe + .dat + .dll)",
                   command=self._eliminar_servicio_programdata).pack(side="left", padx=5)
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
        
        ttk.Label(top_frame, text="Unidades Detectadas:", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        
        # Lista de unidades
        list_frame = ttk.Frame(self.tab_usb)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        columns_usb = ("letra", "etiqueta", "serie", "tamano", "libre", "estado")
        self.tree_usb = ttk.Treeview(list_frame, columns=columns_usb, show="headings",
                                      style="Custom.Treeview", height=8)
        
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
        
        ttk.Button(control_frame, text="Reparar Unidad Seleccionada", 
                   command=self._reparar_unidad_seleccionada,
                   style="Repair.TButton").pack(side="left", padx=5)
        ttk.Button(control_frame, text="Reparar Todas", 
                   command=self._reparar_todas_usb,
                   style="Repair.TButton").pack(side="left", padx=5)
        ttk.Button(control_frame, text="Refrescar Unidades", 
                   command=self._refrescar_unidades).pack(side="left", padx=5)
        
        # Progreso
        self.progreso_var = tk.DoubleVar(value=0)
        self.progreso = ttk.Progressbar(self.tab_usb, variable=self.progreso_var, maximum=100)
        self.progreso.pack(fill="x", padx=5, pady=5)
        
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
        self.log_text = scrolledtext.ScrolledText(
            self.tab_log, wrap=tk.WORD, font=("Consolas", 9),
            bg="#1e1e1e", fg="#d4d4d4", insertbackground="white"
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.log_text.configure(state=tk.DISABLED)
        
        # Frame de controles de log
        log_control = ttk.Frame(self.tab_log)
        log_control.pack(fill="x", pady=5)
        
        ttk.Button(log_control, text="Limpiar Log", command=self._limpiar_log).pack(side="left", padx=5)
        ttk.Button(log_control, text="Exportar Log", command=self._exportar_log).pack(side="left", padx=5)
    
    def _crear_barra_estado(self) -> None:
        """Crea la barra de estado inferior."""
        self.status_var = tk.StringVar(value="Iniciado - Monitoreo USB activo")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief="sunken",
                                anchor="w", style="Status.TLabel")
        status_bar.pack(side="bottom", fill="x")
    
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
                self.root.after(0, lambda: self._agregar_log(f"Error en escaneo: {e}", "ERROR"))
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
                self.root.after(0, lambda: self._agregar_log(f"Error: {e}", "ERROR"))
        
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
                        self.root.after(0, lambda: self._agregar_log(f"Error: {e}", "ERROR"))
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
                self.root.after(0, lambda: self._agregar_log(f"Error eliminando archivos: {e}", "ERROR"))
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
                "", "Conecte una unidad USB…", "—", "—", "—", "Sin unidad"))
            if self._ultimo_conteo_usb != 0:
                self._agregar_log("No hay unidades USB conectadas.", "DEBUG")
            self._ultimo_conteo_usb = 0
        else:
            for unidad in unidades:
                tamano_gb = round(unidad.tamano_total / (1024 ** 3), 1)
                libre_gb = round(unidad.espacio_libre / (1024 ** 3), 1)
                diagnostico = motor.analizar_ruta(unidad.ruta_raiz)
                tags = ()
                if not unidad.es_reparable_con_seguridad:
                    estado = "Solo diagnóstico (disco interno/red)"
                elif diagnostico.estado is EstadoDeteccion.CONFIRMADA:
                    estado = "⚠ Firma confirmada"
                    tags = ("infectada",)
                elif diagnostico.estado is EstadoDeteccion.SOSPECHOSA:
                    estado = "⚠ Revisión manual requerida"
                    tags = ("infectada",)
                elif diagnostico.estado is EstadoDeteccion.INACCESIBLE:
                    estado = "No accesible"
                elif es_unidad_reparada(unidad.letra):
                    estado = "✓ Reparada"
                    tags = ("reparada",)
                else:
                    estado = "Sin firma detectada"

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
            "Se restaurarán los archivos de Usb Drive y se eliminarán solo los ficheros 5.dat al 7.dat. "
            "El contenido no reconocido se conservará.\n\n¿Desea continuar?",
        ):
            return
        self._reparar_unidad_internal(letra)

    def _registrar_resultado_reparacion(self, resultado: ResultadoReparacion) -> None:
        """Muestra en el hilo de interfaz el resultado ya calculado."""
        nivel = "INFO" if resultado.estado is EstadoReparacion.COMPLETADO else "WARNING"
        self._agregar_log(
            f"Reparación de {resultado.unidad}: {resultado.estado.value}", nivel
        )
        self._agregar_log(
            f"Archivos movidos: {resultado.archivos_movidos}; carpetas movidas: "
            f"{resultado.carpetas_movidas}; archivos eliminados: "
            f"{len(resultado.archivos_eliminados)}; errores: {len(resultado.errores)}",
            "INFO",
        )
        for error in resultado.errores:
            self._agregar_log(f"Detalle: {error}", "ERROR")
        self.status_var.set(f"Reparación {resultado.unidad}: {resultado.estado.value}")
        if resultado.estado is EstadoReparacion.COMPLETADO:
            marcar_unidad_reparada(resultado.unidad)
        self._refrescar_unidades()

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
        """Muestra el diálogo Acerca de."""
        messagebox.showinfo("Acerca de", 
                           "Antivirus EACoreServer v1.1\n"
                           "Protección contra malware USB\n"
                           "y gestión de procesos EACoreServer.exe\n\n"
                           "Desarrollado en Python 3.12+\n"
                           "Ing. Yosvany Hernández Quintero")
    
    def _salir(self) -> None:
        """Cierra la aplicación correctamente."""
        self._agregar_log("Cerrando aplicación...", "INFO")
        monitor = obtener_monitor_usb()
        monitor.detener()
        self.root.destroy()


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
    
    # Configurar estilo oscuro de la ventana
    root.configure(bg="#1e1e1e")
    
    # Título de la ventana
    root.title("Antivirus EACoreServer v1.1 - Protección USB y Procesos")
    
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