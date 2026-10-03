"""Reglas de negocio de los registros (v5.0), separadas de la interfaz para
poder probarlas sin abrir ventanas.

Cada operación valida primero (R06) y escribe dentro de una transacción
(R07): si algo falla, la base queda exactamente como estaba.
"""

from db import ErrorIntegridad
from validacion import ErrorValidacion, errores_registro, normalizar

PERSONAS = {
    "student": dict(tabla="StudentData", clave="gno", quien="alumno"),
    "teacher": dict(tabla="TeacherData", clave="trno", quien="docente"),
}

# Columnas que no pueden repetirse dentro de cada tabla, con el texto del mensaje.
UNICAS = {
    "student": (("gno", "Ya existe un alumno con ese N.° de registro general."),
                ("username", "Ese usuario ya está en uso por otro alumno.")),
    "teacher": (("trno", "Ya existe un docente con ese N.° de registro docente."),
                ("username", "Ese usuario ya está en uso por otro docente.")),
}


class Gestion:
    def __init__(self, db):
        self.db = db

    # --- validación (R06) ------------------------------------------------

    def validar_persona(self, tipo, datos, original=None):
        """Devuelve los datos normalizados o lanza ErrorValidacion con TODOS
        los problemas encontrados (no solo el primero). 'original' es la clave
        del registro que se está editando: no cuenta como duplicado de sí mismo."""
        errores = errores_registro(tipo, datos)
        if errores:
            raise ErrorValidacion(errores)
        datos = normalizar(tipo, datos)
        conf = PERSONAS[tipo]
        for columna, mensaje in UNICAS[tipo]:
            if columna not in datos:
                continue
            sql = f"SELECT 1 FROM {conf['tabla']} WHERE {columna} = ?"
            params = [datos[columna]]
            if original is not None:
                sql += f" AND {conf['clave']} IS NOT ?"
                params.append(original)
            if self.db.uno(sql, params):
                errores.append((columna, mensaje))
        if errores:
            raise ErrorValidacion(errores)
        return datos

    # --- personas ---------------------------------------------------------

    def registrar_persona(self, tipo, datos):
        datos = self.validar_persona(tipo, datos)
        with self.db.transaccion():
            self.db.insertar(PERSONAS[tipo]["tabla"], datos)
        return datos


__all__ = ["Gestion", "ErrorValidacion", "ErrorIntegridad", "PERSONAS"]
