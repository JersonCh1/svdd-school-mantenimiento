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

    def pantalla(self, bg='#583830'):
        """Destruye la pantalla actual y devuelve un Frame vacío para la nueva."""
        if self.actual is not None:
            self.actual.destroy()
        self.actual = tk.Frame(self.root, bg=bg)
        self.actual.pack(fill="both", expand=True)
        return self.actual

    def ajustar(self, minimo=(0, 0)):
        """v4.0 R02: el tamaño sale del contenido (ya no de píxeles fijos).

        La ventana toma el tamaño natural de la pantalla nueva (sin pasar del
        área visible del monitor) y ese es también su mínimo: se puede agrandar
        y los campos se estiran, pero no achicar hasta aplastarlos.
        Si el usuario la maximizó, se respeta.
        """
        self.root.update_idletasks()
        ancho = self.actual.winfo_reqwidth()
        alto = self.actual.winfo_reqheight()
        max_ancho = self.root.winfo_screenwidth() - 40
        max_alto = self.root.winfo_screenheight() - 80
        ancho = min(max(ancho, minimo[0]), max_ancho)
        alto = min(max(alto, minimo[1]), max_alto)
        self.root.minsize(ancho, alto)
        if self.root.state() != "zoomed":
            self.root.geometry(f"{ancho}x{alto}")
