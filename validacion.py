"""Validación de campos numéricos (v2.0 — R01).

Mobile No. y Aadhaar Card No. solo aceptan dígitos. La validación se hace en
dos capas:
  1. Al teclear: validatecommand de Tk rechaza cualquier carácter que no sea dígito.
  2. Al guardar: se comprueba la longitud exacta y se muestra un mensaje claro.
"""

import tkinter as tk

LONGITUDES = {
    "mno": (10, "Mobile No.", "10 dígitos"),
    "adno": (12, "Aadhaar Card No.", "12 dígitos"),
}


def _solo_digitos(propuesto, maximo):
    return propuesto == "" or (propuesto.isdigit() and len(propuesto) <= int(maximo))


def configurar_numerico(entry, maximo):
    """Restringe un tk.Entry a dígitos, con un máximo de caracteres."""
    vcmd = (entry.register(_solo_digitos), "%P", maximo)
    entry.configure(validate="key", validatecommand=vcmd)

    def pegar(_evento):
        # Un número pegado como "8829-3250-8844" sería rechazado entero por el
        # validatecommand; se limpian los separadores antes de insertarlo.
        try:
            texto = entry.clipboard_get()
        except tk.TclError:
            return "break"
        digitos = "".join(c for c in texto if c.isdigit())
        try:
            entry.delete("sel.first", "sel.last")
        except tk.TclError:
            pass
        libre = maximo - len(entry.get())
        entry.insert("insert", digitos[:max(libre, 0)])
        return "break"

    entry.bind("<<Paste>>", pegar)


def error_numerico(columna, valor):
    """Devuelve el mensaje de error para el campo, o None si el valor es válido."""
    if columna not in LONGITUDES:
        return None
    longitud, etiqueta, texto = LONGITUDES[columna]
    valor = valor.strip()
    if not valor.isdigit():
        return f"{etiqueta} solo admite números (sin letras, espacios ni guiones)."
    if len(valor) != longitud:
        return f"{etiqueta} debe tener exactamente {texto}; ingresaste {len(valor)}."
    return None
