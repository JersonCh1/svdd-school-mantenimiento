"""Navegación estable entre paneles (v2.0 — R02).

Registro de ventanas abiertas para que cada formulario exista una sola vez:
si el usuario vuelve a pulsar el botón, se trae al frente la ventana que ya
estaba abierta en lugar de crear un duplicado.
"""

import tkinter as tk

_abiertas = {}


def _viva(ventana):
    # winfo_exists() lanza TclError (en vez de devolver False) si el intérprete
    # Tk de esa ventana ya fue destruido.
    try:
        return ventana is not None and bool(ventana.winfo_exists())
    except tk.TclError:
        return False


def enfocar_si_abierta(clave):
    """Si la ventana 'clave' sigue abierta, la trae al frente y devuelve True."""
    ventana = _abiertas.get(clave)
    if _viva(ventana):
        ventana.deiconify()
        ventana.lift()
        ventana.focus_force()
        return True
    _abiertas.pop(clave, None)
    return False


def registrar(clave, ventana, padre):
    """Registra un formulario hijo: queda encima de su panel y la X equivale a Back."""
    _abiertas[clave] = ventana
    ventana.transient(padre)
    ventana.protocol("WM_DELETE_WINDOW", lambda: cerrar(clave))


def cerrar(clave):
    """Cierra el formulario y devuelve el foco al panel que lo abrió."""
    ventana = _abiertas.pop(clave, None)
    if not _viva(ventana):
        return
    padre = ventana.master
    ventana.destroy()
    if _viva(padre):
        padre.lift()
        padre.focus_force()


def abrir_panel(login, panel, limpiar):
    """Muestra el panel de la sesión y oculta el login.

    Back y la X del panel cierran la sesión: destruyen el panel (y con él
    todos sus formularios hijos) y vuelven a mostrar el login limpio.
    """
    def cerrar_sesion():
        for clave, ventana in list(_abiertas.items()):
            if not _viva(ventana) or str(ventana).startswith(str(panel)):
                _abiertas.pop(clave, None)
        panel.destroy()
        limpiar()
        login.deiconify()
        login.lift()

    login.withdraw()
    panel.protocol("WM_DELETE_WINDOW", cerrar_sesion)
    return cerrar_sesion
