"""Validación de campos numéricos (v2.0 — R01).

Mobile No. y Aadhaar Card No. solo aceptan dígitos. La validación se hace en
dos capas:
  1. Al teclear: validatecommand de Tk rechaza cualquier carácter que no sea dígito.
  2. Al guardar: se comprueba la longitud exacta y se muestra un mensaje claro.
"""

import re
import tkinter as tk
from datetime import datetime

LONGITUDES = {
    "mno": (10, "El celular", "10 dígitos"),
    "adno": (12, "El N.° de Aadhaar", "12 dígitos"),
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


# --- v5.0 R06: validación de cada registro antes de guardarlo ---------------

NOMBRES = {
    "name": "Nombre", "lname": "Apellido", "username": "Usuario", "password": "Contraseña",
    "gno": "N.° de registro general", "trno": "N.° de registro docente", "rno": "N.° de lista",
    "hei": "Estatura", "wei": "Peso", "dob": "Fecha de nacimiento", "doa": "Fecha de ingreso al colegio",
    "codigo": "Código", "nombre": "Nombre del curso", "gno_alumno": "Alumno",
    "curso_id": "Curso", "periodo": "Periodo",
}

REGLAS = {
    "student": dict(obligatorios=("name", "lname", "gno", "username", "password"),
                    enteros=("gno", "rno"), decimales=("hei", "wei"), fechas=("dob", "doa")),
    "teacher": dict(obligatorios=("name", "lname", "trno", "username", "password"),
                    enteros=("trno",), fechas=("dob",)),
}
REGLAS["principal"] = REGLAS["teacher"]
REGLAS["curso"] = dict(obligatorios=("codigo", "nombre"), enteros=("trno",),
                       patrones={"codigo": (r"[A-Z0-9-]{2,12}",
                                            "Código debe tener de 2 a 12 letras, números o guiones (por ejemplo MAT-10).")})
REGLAS["matricula"] = dict(obligatorios=("gno", "curso_id", "periodo"), enteros=("gno", "curso_id"),
                           nombres={"gno": "Alumno"},
                           patrones={"periodo": (r"\d{4}-(I|II)",
                                                 "Periodo debe tener el formato año-I o año-II (por ejemplo 2026-II).")})

FORMATO_FECHA = "%d/%m/%Y"


class ErrorValidacion(Exception):
    """Uno o más campos no son válidos. 'errores' es una lista (columna, mensaje)."""

    def __init__(self, errores):
        self.errores = errores
        super().__init__("\n".join(m for _c, m in errores))


def _vacio(valor):
    return valor is None or str(valor).strip() == ""


def errores_registro(tipo, datos, parcial=False):
    """Revisa obligatorios y formatos según las reglas del tipo de registro.
    Con parcial=True solo se revisan las columnas presentes en 'datos' (edición
    de un solo campo). Devuelve [(columna, mensaje)]; vacía si todo es válido."""
    reglas = REGLAS[tipo]
    nombres = {**NOMBRES, **reglas.get("nombres", {})}
    errores = []
    for col in reglas.get("obligatorios", ()):
        if (col in datos or not parcial) and _vacio(datos.get(col)):
            errores.append((col, f"{nombres[col]} es obligatorio."))
    for col, valor in datos.items():
        if _vacio(valor) or any(c == col for c, _m in errores):
            continue
        texto = str(valor).strip()
        if col in reglas.get("enteros", ()) and not (texto.isdigit() and int(texto) > 0):
            errores.append((col, f"{nombres[col]} debe ser un número entero positivo."))
        elif col in reglas.get("decimales", ()) and not re.fullmatch(r"\d+([.,]\d+)?", texto):
            errores.append((col, f"{NOMBRES[col]} debe ser un número (por ejemplo 155.5)."))
        elif col in reglas.get("fechas", ()) and not fecha_valida(texto):
            errores.append((col, f"{NOMBRES[col]} debe tener el formato dd/mm/aaaa (por ejemplo 24/07/1968)."))
        elif col in reglas.get("patrones", {}) and not re.fullmatch(reglas["patrones"][col][0], texto.upper()):
            errores.append((col, reglas["patrones"][col][1]))
        elif col in LONGITUDES:
            error = error_numerico(col, texto)
            if error:
                errores.append((col, error))
    return errores


def periodo_actual(hoy=None):
    """Periodo académico de una fecha: enero-julio es el I, agosto-diciembre el II."""
    hoy = hoy or datetime.now()
    return f"{hoy.year}-{'I' if hoy.month <= 7 else 'II'}"


def fecha_valida(texto):
    try:
        datetime.strptime(texto, FORMATO_FECHA)
    except ValueError:
        return False
    return len(texto) == 10


def normalizar(tipo, datos):
    """Quita espacios sobrantes y convierte números; un campo vacío se guarda como NULL."""
    reglas = REGLAS[tipo]
    limpio = {}
    for col, valor in datos.items():
        if isinstance(valor, str):
            valor = valor.strip() or None
        if valor is not None and col in reglas.get("patrones", {}):
            valor = valor.upper()
        if valor is not None and col in reglas.get("enteros", ()):
            valor = int(valor)
        elif valor is not None and col in reglas.get("decimales", ()):
            valor = float(str(valor).replace(",", "."))
        limpio[col] = valor
    return limpio
