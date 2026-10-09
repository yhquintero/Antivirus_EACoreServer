"""
Componentes de interfaz reutilizables y profesionales.

Proporciona widgets tkinter de aspecto moderno (botones con hover, tarjetas,
barras de búsqueda, diálogos personalizados, indicadores de estado) que la GUI
principal consume en lugar de los ttk estándar, sin sacrificar compatibilidad
con Windows Vista a 11, macOS y Linux.

Por qué un módulo propio y no ttk directo
-----------------------------------------
tkinter/ttk ofrece controles funcionales pero estéticamente planos: los botones
no tienen estado ``hover`` visible, las tarjetas no existen, los diálogos son
cajas de texto monolíticas. Este módulo añade lo que falta sobre ``tkinter`` y
``ttk`` manteniendo la portabilidad multiplataforma y sin dependencias externas.

Todos los colores se derivan de la paleta activa de :mod:`temas`, de modo que
los componentes cambian automáticamente al alternar entre tema claro y oscuro.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Botón profesional con efecto ``hover`` y ``pressed``
# ---------------------------------------------------------------------------
class BotonProfesional(tk.Frame):
    """Botón con tres estados visuales (normal, hover, pulsado) y un icono opcional.

    A diferencia de ``ttk.Button``, este botón siempre muestra un cambio de
    color al pasar el ratón, incluso en temas ttk que no lo soportan.
    """

    def __init__(
        self,
        parent: tk.Misc,
        text: str = "",
        command: Optional[Callable[[], None]] = None,
        color_fondo: str = "#24262e",
        color_fondo_hover: str = "#2f6ad6",
        color_texto: str = "#e6e8ee",
        color_texto_hover: str = "#ffffff",
        color_borde: str = "#3a3f4b",
        fuente: Tuple = ("Segoe UI", 10, "bold"),
        ancho_min: int = 110,
        alto: int = 32,
        padding_x: int = 14,
        icono: str = "",
        estilo_semantico: str = "",
    ) -> None:
        super().__init__(parent, background=color_fondo, highlightthickness=0)
        self._color_fondo = color_fondo
        self._color_fondo_hover = color_fondo_hover
        self._color_texto = color_texto
        self._color_texto_hover = color_texto_hover
        self._color_borde = color_borde
        self._ancho_min = ancho_min
        self._alto = alto
        self._padding_x = padding_x
        self._command = command
        self._activado = True

        # Borde exterior simulado con highlightthickness=0 y un frame interior.
        self._borde = tk.Frame(self, background=color_borde, highlightthickness=0)
        self._interior = tk.Frame(self._borde, background=color_fondo, highlightthickness=0)
        self._etiqueta = tk.Label(
            self._interior,
            text=f"{icono}  {text}".strip() if icono else text,
            background=color_fondo,
            foreground=color_texto,
            font=fuente,
            padx=padding_x,
            pady=6,
            cursor="hand2",
            anchor="center",
        )
        self._etiqueta.pack(fill="both", expand=True)
        self._interior.pack(fill="both", expand=True, padx=1, pady=1)
        self._borde.pack(fill="both", expand=True)

        # Eventos de ratón para el efecto hover.
        self._etiqueta.bind("<Enter>", self._al_entrar)
        self._etiqueta.bind("<Leave>", self._al_salir)
        self._etiqueta.bind("<ButtonPress-1>", self._al_pulsar)
        self._etiqueta.bind("<ButtonRelease-1>", self._al_soltar)
        # Zona muerta del borde: que también reaccione al hover.
        self._borde.bind("<Enter>", self._al_entrar)
        self._borde.bind("<Leave>", self._al_salir)

        # Estilo semántico (éxito, peligro, advertencia) para cambiar los colores.
        if estilo_semantico == "exito":
            self._color_fondo_hover = "#35d07f"
            self._color_texto_hover = "#ffffff"
        elif estilo_semantico == "peligro":
            self._color_fondo_hover = "#ff6b60"
            self._color_texto_hover = "#ffffff"
        elif estilo_semantico == "advertencia":
            self._color_fondo_hover = "#f5a623"
            self._color_texto_hover = "#000000"

    def _al_entrar(self, _evento=None) -> None:
        if not self._activado:
            return
        self._interior.configure(background=self._color_fondo_hover)
        self._etiqueta.configure(
            background=self._color_fondo_hover, foreground=self._color_texto_hover
        )

    def _al_salir(self, _evento=None) -> None:
        self._interior.configure(background=self._color_fondo)
        self._etiqueta.configure(
            background=self._color_fondo, foreground=self._color_texto
        )

    def _al_pulsar(self, _evento=None) -> None:
        if not self._activado:
            return
        self._interior.configure(background=self._color_fondo_hover)
        self._etiqueta.configure(
            background=self._color_fondo_hover, foreground=self._color_texto_hover
        )

    def _al_soltar(self, _evento=None) -> None:
        if not self._activado:
            return
        if self._command is not None:
            try:
                self._command()
            except Exception as exc:  # pragma: no cover - defensivo
                self._etiqueta.configure(text=f"Error: {exc}")
        self._al_entrar()

    def desactivar(self) -> None:
        """Deshabilita el botón visualmente y funcionalmente."""
        self._activado = False
        self._interior.configure(background=self._color_fondo)
        self._etiqueta.configure(
            background=self._color_fondo, foreground=self._color_texto, cursor="arrow"
        )

    def activar(self) -> None:
        """Vuelve a habilitar el botón."""
        self._activado = True
        self._etiqueta.configure(cursor="hand2")


# ---------------------------------------------------------------------------
# Tarjeta (Card): superficie elevada para agrupar controles relacionados
# ---------------------------------------------------------------------------
class Tarjeta(tk.Frame):
    """Contenedor con título opcional, borde sutil y fondo diferenciado.

    Útil para agrupar controles en las pestañas de la GUI, evitando la
    sensación de "lista plana de botones".
    """

    def __init__(
        self,
        parent: tk.Misc,
        titulo: str = "",
        color_fondo: str = "#20222a",
        color_borde: str = "#3a3f4b",
        color_titulo: str = "#4f8cff",
        fuente_titulo: Tuple = ("Segoe UI", 11, "bold"),
        padding: int = 10,
    ) -> None:
        super().__init__(parent, background=color_fondo, highlightthickness=0)
        self._color_fondo = color_fondo
        self._color_borde = color_borde

        # Marco exterior que simula el borde.
        self._borde = tk.Frame(self, background=color_borde, highlightthickness=0)
        self._interior = tk.Frame(self._borde, background=color_fondo, highlightthickness=0)
        self._interior.pack(fill="both", expand=True, padx=1, pady=1)
        self._borde.pack(fill="both", expand=True)

        if titulo:
            self._cabecera = tk.Frame(self._interior, background=color_fondo, highlightthickness=0)
            self._cabecera.pack(fill="x", padx=padding, pady=(padding, 4))
            self._etiqueta_titulo = tk.Label(
                self._cabecera,
                text=titulo,
                background=color_fondo,
                foreground=color_titulo,
                font=fuente_titulo,
                anchor="w",
            )
            self._etiqueta_titulo.pack(side="left")
            separador = tk.Frame(self._cabecera, background=color_borde, height=1)
            separador.pack(side="right", fill="y", padx=(8, 0))
            self._cuerpo = tk.Frame(self._interior, background=color_fondo, highlightthickness=0)
            self._cuerpo.pack(fill="both", expand=True, padx=padding, pady=(0, padding))
        else:
            self._cabecera = None
            self._cuerpo = tk.Frame(self._interior, background=color_fondo, highlightthickness=0)
            self._cuerpo.pack(fill="both", expand=True, padx=padding, pady=padding)

    @property
    def cuerpo(self) -> tk.Frame:
        return self._cuerpo

    def cambiar_tema(self, color_fondo: str, color_borde: str, color_titulo: str = "") -> None:
        """Recolorea la tarjeta al cambiar de tema."""
        self._color_fondo = color_fondo
        self._color_borde = color_borde
        self.configure(background=color_fondo)
        self._borde.configure(background=color_borde)
        self._interior.configure(background=color_fondo)
        if self._cuerpo is not None:
            self._cuerpo.configure(background=color_fondo)
        if self._cabecera is not None:
            self._cabecera.configure(background=color_fondo)
            self._etiqueta_titulo.configure(background=color_fondo)
            if color_titulo:
                self._etiqueta_titulo.configure(foreground=color_titulo)


# ---------------------------------------------------------------------------
# Barra de búsqueda / filtro
# ---------------------------------------------------------------------------
class BarraBusqueda(tk.Frame):
    """Campo de búsqueda con icono, placeholder y botón de limpiar.

    La barra notifica al ``callback`` cada vez que el texto cambia, de modo que
    la tabla puede filtrarse en tiempo real.
    """

    def __init__(
        self,
        parent: tk.Misc,
        placeholder: str = "Buscar…",
        callback: Optional[Callable[[str], None]] = None,
        color_fondo: str = "#262932",
        color_texto: str = "#e6e8ee",
        color_borde: str = "#3a3f4b",
        color_placeholder: str = "#a7adbb",
        fuente: Tuple = ("Segoe UI", 10),
    ) -> None:
        super().__init__(parent, background=color_borde, highlightthickness=0)
        self._color_fondo = color_fondo
        self._color_texto = color_texto
        self._color_borde = color_borde
        self._color_placeholder = color_placeholder
        self._placeholder = placeholder
        self._callback = callback
        self._valor_actual = ""

        interior = tk.Frame(self, background=color_fondo, highlightthickness=0)
        interior.pack(fill="both", expand=True, padx=1, pady=1)

        self._entrada = tk.Entry(
            interior,
            background=color_fondo,
            foreground=color_texto,
            insertbackground=color_texto,
            font=fuente,
            relief="flat",
            borderwidth=0,
        )
        self._entrada.insert(0, placeholder)
        self._entrada.configure(fg=color_placeholder)
        self._entrada.pack(side="left", fill="x", expand=True, padx=6, pady=4)
        self._entrada.bind("<FocusIn>", self._al_enfocar)
        self._entrada.bind("<FocusOut>", self._al_desenfocar)
        self._entrada.bind("<KeyRelease>", self._al_escribir)

        self._btn_limpiar = tk.Label(
            interior,
            text="✕",
            background=color_fondo,
            foreground=color_texto,
            font=(*fuente, "bold"),
            cursor="hand2",
            padx=6,
        )
        self._btn_limpiar.pack(side="right", padx=(0, 4))
        self._btn_limpiar.bind("<Button-1>", self._limpiar)
        self._btn_limpiar.bind("<Enter>", lambda _e: self._btn_limpiar.configure(foreground="#4f8cff"))
        self._btn_limpiar.bind("<Leave>", lambda _e: self._btn_limpiar.configure(foreground=color_texto))

    def _al_enfocar(self, _evento=None) -> None:
        if self._entrada.get() == self._placeholder:
            self._entrada.delete(0, "end")
            self._entrada.configure(fg=self._color_texto)

    def _al_desenfocar(self, _evento=None) -> None:
        if not self._entrada.get():
            self._entrada.insert(0, self._placeholder)
            self._entrada.configure(fg=self._color_placeholder)
            self._valor_actual = ""
            if self._callback:
                self._callback("")

    def _al_escribir(self, _evento=None) -> None:
        texto = self._entrada.get()
        if texto != self._placeholder and texto != self._valor_actual:
            self._valor_actual = texto
            if self._callback:
                self._callback(texto)

    def _limpiar(self, _evento=None) -> None:
        self._entrada.delete(0, "end")
        self._entrada.insert(0, self._placeholder)
        self._entrada.configure(fg=self._color_placeholder)
        self._valor_actual = ""
        if self._callback:
            self._callback("")
        self._entrada.focus_set()

    def obtener_texto(self) -> str:
        texto = self._entrada.get()
        return "" if texto == self._placeholder else texto

    def cambiar_tema(self, color_fondo: str, color_texto: str, color_borde: str) -> None:
        self._color_fondo = color_fondo
        self._color_texto = color_texto
        self._color_borde = color_borde
        self.configure(background=color_borde)
        self._entrada.configure(
            background=color_fondo, foreground=color_texto, insertbackground=color_texto
        )
        self._btn_limpiar.configure(background=color_fondo, foreground=color_texto)


# ---------------------------------------------------------------------------
# Indicador de estado (punto de color + etiqueta)
# ---------------------------------------------------------------------------
class IndicadorEstado(tk.Frame):
    """Pequeño punto de color con texto descriptivo. Útil en barras de estado."""

    def __init__(
        self,
        parent: tk.Misc,
        texto: str,
        color_punto: str = "#35d07f",
        color_texto: str = "#e6e8ee",
        fondo: str = "#24262e",
        fuente: Tuple = ("Segoe UI", 9),
    ) -> None:
        super().__init__(parent, background=fondo, highlightthickness=0)
        self._canvas = tk.Canvas(
            self, width=10, height=10, background=fondo, highlightthickness=0
        )
        self._canvas.pack(side="left", padx=(4, 6))
        self._circulo = self._canvas.create_oval(1, 1, 9, 9, fill=color_punto, outline="")
        self._etiqueta = tk.Label(
            self, text=texto, background=fondo, foreground=color_texto, font=fuente
        )
        self._etiqueta.pack(side="left", padx=(0, 8))
        self._color_punto = color_punto

    def cambiar_estado(self, color: str, texto: str = "") -> None:
        self._color_punto = color
        self._canvas.itemconfigure(self._circulo, fill=color)
        if texto:
            self._etiqueta.configure(text=texto)


# ---------------------------------------------------------------------------
# Barra de progreso mejorada con porcentaje visible
# ---------------------------------------------------------------------------
class BarraProgreso(tk.Frame):
    """Barra de progreso con etiqueta de porcentaje integrada."""

    def __init__(
        self,
        parent: tk.Misc,
        maximo: int = 100,
        color_fondo: str = "#24262e",
        color_barra: str = "#4f8cff",
        color_texto: str = "#e6e8ee",
        color_borde: str = "#3a3f4b",
        fuente: Tuple = ("Segoe UI", 9, "bold"),
        altura: int = 22,
    ) -> None:
        super().__init__(parent, background=color_borde, highlightthickness=0)
        self._maximo = maximo
        self._valor = 0
        self._color_fondo = color_fondo
        self._color_barra = color_barra
        self._color_texto = color_texto

        interior = tk.Frame(self, background=color_fondo, highlightthickness=0)
        interior.pack(fill="both", expand=True, padx=1, pady=1)

        self._canvas = tk.Canvas(
            interior, background=color_fondo, highlightthickness=0, height=altura
        )
        self._canvas.pack(fill="both", expand=True)
        self._rect_fondo = self._canvas.create_rectangle(0, 0, 0, 0, fill=color_fondo, outline="")
        self._rect_progreso = self._canvas.create_rectangle(0, 0, 0, 0, fill=color_barra, outline="")

        self._etiqueta = tk.Label(
            self, text="0%", background=color_fondo, foreground=color_texto, font=fuente
        )
        self._etiqueta.place(relx=0.5, rely=0.5, anchor="center")

        self._canvas.bind("<Configure>", self._redibujar)

    def establecer(self, valor: int) -> None:
        self._valor = max(0, min(self._maximo, valor))
        self._etiqueta.configure(text=f"{self._valor}%")
        self._redibujar()

    def restablecer(self) -> None:
        self.establecer(0)

    def _redibujar(self, _evento=None) -> None:
        try:
            ancho = self._canvas.winfo_width()
            alto = self._canvas.winfo_height()
        except tk.TclError:
            return
        if ancho <= 0 or alto <= 0:
            return
        self._canvas.coords(self._rect_fondo, 0, 0, ancho, alto)
        proporcion = self._valor / self._maximo if self._maximo > 0 else 0
        ancho_progreso = int(ancho * proporcion)
        self._canvas.coords(self._rect_progreso, 0, 0, ancho_progreso, alto)

    def cambiar_tema(self, color_fondo: str, color_barra: str, color_texto: str) -> None:
        self._color_fondo = color_fondo
        self._color_barra = color_barra
        self._color_texto = color_texto
        self.configure(background=color_barra)  # borde
        self._canvas.configure(background=color_fondo)
        self._canvas.itemconfigure(self._rect_fondo, fill=color_fondo)
        self._canvas.itemconfigure(self._rect_progreso, fill=color_barra)
        self._etiqueta.configure(background=color_fondo, foreground=color_texto)


# ---------------------------------------------------------------------------
# Diálogo profesional personalizado (reemplaza messagebox en algunos casos)
# ---------------------------------------------------------------------------
class DialogoProfesional:
    """Diálogo modal con título, mensaje formateado, icono y botones personalizados.

    A diferencia de ``messagebox``, este diálogo:
    * Respeta la paleta activa (fondo, texto, acento).
    * Permite mensajes largos con formato (saltos de línea, negritas simuladas).
    * Ofrece botones con texto personalizado.
    * Se centra en la ventana padre.
    """

    def __init__(
        self,
        padre: tk.Misc,
        titulo: str,
        mensaje: str,
        tipo: str = "info",
        botones: Optional[List[Tuple[str, bool]]] = None,
        color_fondo: str = "#1b1d23",
        color_texto: str = "#e6e8ee",
        color_acento: str = "#4f8cff",
        color_texto_acento: str = "#ffffff",
        color_borde: str = "#3a3f4b",
        ancho_max: int = 480,
    ) -> None:
        self._respuesta: Optional[str] = None
        self._ventana = tk.Toplevel(padre)
        self._ventana.title(titulo)
        self._ventana.resizable(False, False)
        self._ventana.configure(background=color_fondo)
        self._ventana.attributes("-topmost", True)

        # Icono según tipo.
        iconos = {"info": "ℹ", "error": "✕", "warning": "", "question": "?"}
        icono = iconos.get(tipo, "")

        # Contenido.
        contenido = tk.Frame(self._ventana, background=color_fondo)
        contenido.pack(fill="both", expand=True, padx=20, pady=20)

        cabecera = tk.Frame(contenido, background=color_fondo)
        cabecera.pack(fill="x", pady=(0, 12))

        lbl_icono = tk.Label(
            cabecera, text=icono, background=color_fondo,
            foreground=color_acento, font=("Segoe UI", 24, "bold")
        )
        lbl_icono.pack(side="left", padx=(0, 14))

        lbl_titulo = tk.Label(
            cabecera, text=titulo, background=color_fondo,
            foreground=color_texto, font=("Segoe UI", 12, "bold"), anchor="w"
        )
        lbl_titulo.pack(side="left", fill="x", expand=True)

        # Mensaje con saltos de línea.
        lbl_mensaje = tk.Label(
            contenido, text=mensaje, background=color_fondo,
            foreground=color_texto, font=("Segoe UI", 10),
            justify="left", anchor="nw", wraplength=ancho_max - 40
        )
        lbl_mensaje.pack(fill="x", pady=(0, 16))

        # Separador.
        separador = tk.Frame(contenido, background=color_borde, height=1)
        separador.pack(fill="x", pady=(0, 12))

        # Botones.
        botones_frame = tk.Frame(contenido, background=color_fondo)
        botones_frame.pack(fill="x")

        if botones is None:
            botones = [("Aceptar", True)]

        for texto_boton, es_primario in reversed(botones):
            btn = BotonProfesional(
                botones_frame,
                text=texto_boton,
                color_fondo=color_borde if not es_primario else color_acento,
                color_fondo_hover=color_acento if not es_primario else "#2f6ad6",
                color_texto=color_texto if not es_primario else color_texto_acento,
                color_texto_hover=color_texto_acento,
                color_borde=color_borde,
                fuente=("Segoe UI", 10, "bold" if es_primario else "normal"),
                ancho_min=90,
                alto=30,
                padding_x=16,
            )
            btn.pack(side="right", padx=(8, 0))

            def _crear_handler(resp: str, v: tk.Misc) -> Callable:
                def handler() -> None:
                    self._respuesta = resp
                    try:
                        v.destroy()
                    except tk.TclError:
                        pass
                return handler

            btn._command = _crear_handler(texto_boton, self._ventana)

        # Posicionar centrado respecto al padre.
        self._ventana.update_idletasks()
        try:
            pw = padre.winfo_rootx() + padre.winfo_width() // 2
            ph = padre.winfo_rooty() + padre.winfo_height() // 2
            vw = self._ventana.winfo_width()
            vh = self._ventana.winfo_height()
            self._ventana.geometry(f"+{pw - vw // 2}+{ph - vh // 2}")
        except tk.TclError:
            pass

        self._ventana.transient(padre)
        self._ventana.grab_set()
        self._ventana.wait_window()

    @property
    def respuesta(self) -> Optional[str]:
        return self._respuesta


# ---------------------------------------------------------------------------
# Menú contextual (clic derecho) para tablas
# ---------------------------------------------------------------------------
class MenuContextual:
    """Menú flotante que aparece al hacer clic derecho sobre un widget."""

    def __init__(
        self,
        padre: tk.Misc,
        color_fondo: str = "#24262e",
        color_texto: str = "#e6e8ee",
        color_hover: str = "#2f6ad6",
        color_borde: str = "#3a3f4b",
        fuente: Tuple = ("Segoe UI", 10),
    ) -> None:
        self._menu = tk.Menu(
            padre, tearoff=0,
            background=color_fondo, foreground=color_texto,
            activebackground=color_hover, activeforeground="#ffffff",
            borderwidth=1, relief="solid",
            font=fuente,
        )
        self._color_fondo = color_fondo
        self._color_texto = color_texto
        self._color_hover = color_hover
        self._color_borde = color_borde

    def agregar(self, texto: str, comando: Callable[[], None], icono: str = "") -> None:
        etiqueta = f"{icono}  {texto}" if icono else texto
        self._menu.add_command(label=etiqueta, command=comando)

    def agregar_separador(self) -> None:
        self._menu.add_separator()

    def mostrar(self, evento: tk.Event) -> None:
        try:
            self._menu.tk_popup(evento.x_root, evento.y_root)
        finally:
            self._menu.grab_release()

    def cambiar_tema(self, color_fondo: str, color_texto: str, color_hover: str) -> None:
        self._menu.configure(
            background=color_fondo, foreground=color_texto,
            activebackground=color_hover,
        )


# ---------------------------------------------------------------------------
# Utilidades de layout
# ---------------------------------------------------------------------------
def separador_horizontal(padre: tk.Misc, color: str = "#3a3f4b", grosor: int = 1) -> tk.Frame:
    """Crea un separador visual de 1 píxel de alto."""
    frame = tk.Frame(padre, background=color, height=grosor)
    frame.pack(fill="x", pady=2)
    return frame


def espaciado(padre: tk.Misc, alto: int = 8) -> tk.Frame:
    """Añade espacio vertical."""
    frame = tk.Frame(padre, height=alto, background=padre.cget("background"))
    frame.pack(fill="x")
    return frame
