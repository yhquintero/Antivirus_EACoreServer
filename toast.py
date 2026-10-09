"""
Sistema de notificaciones tipo ``toast`` para Antivirus EACoreServer.

Muestra avisos breves y no bloqueantes en una esquina de la pantalla para
confirmar acciones (reparación iniciada, unidad detectada, etc.) sin interrumpir
el flujo del usuario. Cada toast desaparece automáticamente tras unos segundos.

Diseño
------
* Las notificaciones se apilan verticalmente en la esquina inferior derecha.
* Cada una tiene un icono según su tipo (éxito, error, información, advertencia).
* Al pasar el ratón sobre un toast, este se detiene y no se cierra automáticamente.
* Los colores se derivan de la paleta de :mod:`temas`.
* Funciona en Windows, macOS y Linux (usa ``Toplevel`` estándar de tkinter).
"""

from __future__ import annotations

import tkinter as tk
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Deque, Dict, List, Optional


class TipoToast(str, Enum):
    EXITO = "exito"
    ERROR = "error"
    INFO = "info"
    ADVERTENCIA = "advertencia"


@dataclass(frozen=True)
class _ConfiguracionToast:
    """Valores por defecto para un tipo de toast."""
    icono: str
    color_fondo: str
    color_texto: str
    color_borde: str
    duracion_ms: int


_CONFIGURACIONES: Dict[TipoToast, _ConfiguracionToast] = {
    TipoToast.EXITO: _ConfiguracionToast(
        icono="✓", color_fondo="#0f5132", color_texto="#ffffff",
        color_borde="#12805c", duracion_ms=4500,
    ),
    TipoToast.ERROR: _ConfiguracionToast(
        icono="✕", color_fondo="#7f1d1d", color_texto="#ffffff",
        color_borde="#b3261e", duracion_ms=6000,
    ),
    TipoToast.INFO: _ConfiguracionToast(
        icono="ℹ", color_fondo="#0b3d91", color_texto="#ffffff",
        color_borde="#0b6bcb", duracion_ms=4000,
    ),
    TipoToast.ADVERTENCIA: _ConfiguracionToast(
        icono="", color_fondo="#78350f", color_texto="#ffffff",
        color_borde="#f5a623", duracion_ms=5000,
    ),
}


class NotificadorToast:
    """Muestra notificaciones tipo ``toast`` apiladas en la esquina inferior derecha.

    Uso::

        notificador = NotificadorToast(raiz_tk)
        notificador.mostrar("Unidad E:\\\\ detectada", TipoToast.INFO)
        notificador.mostrar("Reparación completada", TipoToast.EXITO)

    Todas las llamadas son seguras desde hilos secundarios: internamente se
    encolan y se ejecutan en el hilo principal vía ``root.after``.
    """

    ALTURA_TOAST = 56
    MARGEN_INFERIOR = 16
    MARGEN_DERECHO = 16
    ANCHO_TOAST = 340
    TRANSICION_MS = 150

    def __init__(self, raiz: tk.Tk) -> None:
        self._raiz = raiz
        self._toasts_activos: List[tk.Toplevel] = []
        self._cola: Deque[tuple] = []  # type: ignore[type-arg]
        self._bloqueado = False
        # Configuraciones por defecto; se pueden sobrescribir con cambiar_tema.
        self._configs = dict(_CONFIGURACIONES)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def mostrar(
        self,
        mensaje: str,
        tipo: TipoToast = TipoToast.INFO,
        duracion_ms: Optional[int] = None,
        desde_hilo: bool = False,
    ) -> None:
        """Muestra un toast con ``mensaje`` del ``tipo`` indicado.

        Si ``desde_hilo`` es ``True``, la llamada proviene de un hilo de trabajo
        y se reenvía al hilo principal.
        """
        if desde_hilo:
            self._raiz.after(0, self.mostrar, mensaje, tipo, duracion_ms, False)
            return
        self._cola.append((mensaje, tipo, duracion_ms))
        if not self._bloqueado:
            self._procesar_cola()

    def mostrar_exito(self, mensaje: str, duracion_ms: Optional[int] = None) -> None:
        self.mostrar(mensaje, TipoToast.EXITO, duracion_ms)

    def mostrar_error(self, mensaje: str, duracion_ms: Optional[int] = None) -> None:
        self.mostrar(mensaje, TipoToast.ERROR, duracion_ms)

    def mostrar_info(self, mensaje: str, duracion_ms: Optional[int] = None) -> None:
        self.mostrar(mensaje, TipoToast.INFO, duracion_ms)

    def mostrar_advertencia(self, mensaje: str, duracion_ms: Optional[int] = None) -> None:
        self.mostrar(mensaje, TipoToast.ADVERTENCIA, duracion_ms)

    def limpiar_todos(self) -> None:
        """Cierra todos los toasts activos de inmediato."""
        for toast in self._toasts_activos[:]:
            try:
                toast.destroy()
            except tk.TclError:
                pass
        self._toasts_activos.clear()

    # ------------------------------------------------------------------
    # Lógica interna
    # ------------------------------------------------------------------
    def _procesar_cola(self) -> None:
        if not self._cola:
            self._bloqueado = False
            return
        self._bloqueado = True
        mensaje, tipo, duracion = self._cola.popleft()
        self._crear_toast(mensaje, tipo, duracion)
        # Procesar el siguiente con un pequeño retardo para apilar.
        self._raiz.after(self.TRANSICION_MS, self._procesar_cola)

    def _crear_toast(
        self, mensaje: str, tipo: TipoToast, duracion_ms: Optional[int]
    ) -> None:
        config = self._configs.get(tipo, _CONFIGURACIONES[TipoToast.INFO])
        duracion = duracion_ms if duracion_ms is not None else config.duracion_ms

        toast = tk.Toplevel(self._raiz)
        toast.wm_overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(background=config.color_fondo)
        # Transparencia en sistemas que la soporten (Windows, macOS).
        try:
            toast.attributes("-alpha", 0.95)
        except tk.TclError:
            pass

        # Marco interior con borde simulado.
        borde = tk.Frame(toast, background=config.color_borde, highlightthickness=0)
        borde.pack(fill="both", expand=True, padx=1, pady=1)

        interior = tk.Frame(borde, background=config.color_fondo, highlightthickness=0)
        interior.pack(fill="both", expand=True)

        # Icono.
        lbl_icono = tk.Label(
            interior, text=config.icono, background=config.color_fondo,
            foreground=config.color_texto, font=("Segoe UI", 16, "bold"),
            padx=10,
        )
        lbl_icono.pack(side="left", fill="y")

        # Mensaje.
        lbl_mensaje = tk.Label(
            interior, text=mensaje, background=config.color_fondo,
            foreground=config.color_texto, font=("Segoe UI", 10),
            anchor="w", justify="left", wraplength=self.ANCHO_TOAST - 70,
        )
        lbl_mensaje.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=8)

        # Botón de cerrar.
        lbl_cerrar = tk.Label(
            interior, text="✕", background=config.color_fondo,
            foreground=config.color_texto, font=("Segoe UI", 10, "bold"),
            cursor="hand2", padx=8,
        )
        lbl_cerrar.pack(side="right")

        def _cerrar() -> None:
            self._quitar_toast(toast)

        lbl_cerrar.bind("<Button-1>", lambda _e: _cerrar())
        lbl_cerrar.bind("<Enter>", lambda _e: lbl_cerrar.configure(foreground="#ff6b60"))
        lbl_cerrar.bind("<Leave>", lambda _e: lbl_cerrar.configure(foreground=config.color_texto))

        # Posicionar en la esquina inferior derecha.
        self._raiz.update_idletasks()
        try:
            pantalla_ancho = self._raiz.winfo_screenwidth()
            pantalla_alto = self._raiz.winfo_screenheight()
            x = pantalla_ancho - self.ANCHO_TOAST - self.MARGEN_DERECHO
            y = pantalla_alto - (len(self._toasts_activos) + 1) * (self.ALTURA_TOAST + 6) - self.MARGEN_INFERIOR
            if y < 10:
                y = 10
            toast.geometry(f"{self.ANCHO_TOAST}x{self.ALTURA_TOAST}+{x}+{y}")
        except tk.TclError:
            pass

        self._toasts_activos.append(toast)

        # Auto-cierre tras la duración (respetando si el ratón está encima).
        def _auto_cerrar() -> None:
            self._quitar_toast(toast)

        self._raiz.after(duracion, _auto_cerrar)

        # Si el ratón entra, cancelar el auto-cierre.
        def _al_entrar(_e: tk.Event) -> None:
            try:
                self._raiz.after_cancel(id_auto)
            except tk.TclError:
                pass

        def _al_salir(_e: tk.Event) -> None:
            # Re-programar el cierre.
            self._raiz.after(duracion // 2, _auto_cerrar)

        id_auto = self._raiz.after(duracion, _auto_cerrar)
        toast.bind("<Enter>", _al_entrar)
        toast.bind("<Leave>", _al_salir)

    def _quitar_toast(self, toast: tk.Toplevel) -> None:
        try:
            if toast in self._toasts_activos:
                self._toasts_activos.remove(toast)
            toast.destroy()
        except tk.TclError:
            pass
        # Reposicionar los toasts restantes.
        self._reorganizar()

    def _reorganizar(self) -> None:
        try:
            pantalla_ancho = self._raiz.winfo_screenwidth()
            pantalla_alto = self._raiz.winfo_screenheight()
        except tk.TclError:
            return
        for indice, toast in enumerate(reversed(self._toasts_activos)):
            try:
                x = pantalla_ancho - self.ANCHO_TOAST - self.MARGEN_DERECHO
                y = pantalla_alto - (indice + 1) * (self.ALTURA_TOAST + 6) - self.MARGEN_INFERIOR
                toast.geometry(f"+{x}+{y}")
            except tk.TclError:
                pass

    def cambiar_tema(self, configs: Optional[Dict[TipoToast, _ConfiguracionToast]] = None) -> None:
        """Actualiza las configuraciones de color. Los toasts activos no se recolorean."""
        if configs:
            self._configs = configs


# ---------------------------------------------------------------------------
# Singleton para acceder desde cualquier módulo
# ---------------------------------------------------------------------------
_instancia: Optional[NotificadorToast] = None


def obtener_notificador(raiz: Optional[tk.Tk] = None) -> NotificadorToast:
    """Devuelve (y crea si es necesario) el notificador toast singleton.

    Requiere haber pasado la raíz ``tk.Tk`` la primera vez.
    """
    global _instancia
    if _instancia is None:
        if raiz is None:
            raise RuntimeError("Se necesita la raíz tkinter para crear el notificador")
        _instancia = NotificadorToast(raiz)
    return _instancia


def reiniciar_notificador() -> None:
    """Limpia el singleton. Útil para pruebas."""
    global _instancia
    if _instancia is not None:
        _instancia.limpiar_todos()
    _instancia = None
