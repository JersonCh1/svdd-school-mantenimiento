"""Navegación de ventana única (v4.0 — R01).

Toda la aplicación vive en una sola ventana raíz. Cada pantalla (login,
panel, formularios) es un Frame que reemplaza al anterior, así que no
pueden quedar ventanas huérfanas ni duplicadas.
"""

import tkinter as tk


class Navegador:
    def __init__(self, root):
        self.root = root
        self.actual = None
        self.sesion = None  # (rol, usuario, contraseña) mientras hay sesión abierta

    def pantalla(self, tamano, bg='#583830'):
        """Destruye la pantalla actual y devuelve un Frame vacío para la nueva."""
        if self.actual is not None:
            self.actual.destroy()
        self.actual = tk.Frame(self.root, bg=bg)
        self.actual.pack(fill="both", expand=True)
        self.root.geometry(tamano)
        return self.actual
