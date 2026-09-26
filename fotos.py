"""Carga y vista previa de foto (v2.0 — R03)."""

import io
import os
import tkinter as tk
from tkinter import filedialog, messagebox

from PIL import Image, ImageTk, UnidentifiedImageError

FORMATOS = {"PNG", "JPEG", "GIF"}
MAX_BYTES = 2 * 1024 * 1024
TIPOS = [("Imágenes (PNG, JPG, GIF)", "*.png *.jpg *.jpeg *.gif")]
TAMANO_MINIATURA = (130, 150)
TAMANO_PANEL = (150, 170)


def leer_foto(ruta):
    """Lee y valida la imagen. Devuelve los bytes o lanza ValueError con el motivo."""
    if os.path.getsize(ruta) > MAX_BYTES:
        raise ValueError("La foto pesa más de 2 MB. Elige una imagen más liviana.")
    with open(ruta, "rb") as f:
        datos = f.read()
    try:
        with Image.open(io.BytesIO(datos)) as img:
            formato = img.format
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise ValueError("El archivo no es una imagen válida (¿extensión cambiada o archivo dañado?).")
    if formato not in FORMATOS:
        raise ValueError(f"Formato {formato} no admitido. Usa PNG, JPG o GIF.")
    return datos


def miniatura(datos, tamano):
    """PhotoImage escalado a 'tamano' conservando la proporción."""
    with Image.open(io.BytesIO(datos)) as img:
        img = img.convert("RGBA")
        img.thumbnail(tamano)
        return ImageTk.PhotoImage(img)


def mostrar(label, datos, tamano):
    """Pone la imagen en el label. Se guarda una referencia en el propio label:
    si el PhotoImage solo vive en una variable local, Python lo libera y Tk
    muestra un recuadro vacío."""
    foto = miniatura(datos, tamano)
    label.configure(image=foto, text="", width=tamano[0], height=tamano[1])
    label.image = foto


class SelectorFoto:
    """Botón 'Elegir foto...' + miniatura, para los formularios de alta.
    Quien lo usa decide dónde ubicar .boton y .vista."""

    def __init__(self, padre):
        self.padre = padre
        self.datos = None
        self.nombre = ""
        self.boton = tk.Button(padre, text="Elegir foto...", command=self.elegir,
                               fg='#18120F', bg='#C7A196', font=("Cambria", 10, "bold"))
        self.vista = tk.Label(padre, text="Sin foto", fg='#18120F', bg='#FDD4B8',
                              width=16, height=8)

    def elegir(self):
        ruta = filedialog.askopenfilename(parent=self.padre, title="Elegir foto", filetypes=TIPOS)
        if not ruta:
            return
        try:
            self.datos = leer_foto(ruta)
        except ValueError as e:
            messagebox.showerror("Foto no válida", str(e), parent=self.padre)
            return
        self.nombre = os.path.basename(ruta)
        mostrar(self.vista, self.datos, TAMANO_MINIATURA)
