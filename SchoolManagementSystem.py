"""S.V.D.D. School — sistema de gestión escolar (Tkinter + SQLite).

Punto de entrada. Desde la v4.0 la aplicación está repartida en módulos:
  db.py          conexión única a SQLite (R03)
  navegacion.py  ventana única con pantallas intercambiables (R01)
  pantallas.py   login, paneles y formularios con diseño adaptable (R02)
  validacion.py, fotos.py, migraciones.py  (v2.0)
"""

import ctypes
import sys
import tkinter as tk

from db import BaseDatos
from migraciones import migrar
from pantallas import Aplicacion


def activar_dpi():
    # Sin esto Windows estira la ventana como imagen en pantallas con escala
    # (125 %, 150 %) y el texto se ve borroso. Con el diseño en grid, las
    # fuentes más grandes ya no cortan las etiquetas.
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass


def main():
    activar_dpi()
    db = BaseDatos()
    migrar(db.con)
    window = tk.Tk()
    window.title("S.V.D.D. School")
    window.configure(bg='#583830')
    app = Aplicacion(window, db)
    app.mostrar_login()
    try:
        window.mainloop()
    finally:
        BaseDatos.cerrar()
    return app


if __name__ == "__main__":
    main()
