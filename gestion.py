"""Reglas de negocio de los registros (v5.0), separadas de la interfaz para
poder probarlas sin abrir ventanas.

Cada operación valida primero (R06) y escribe dentro de una transacción
(R07): si algo falla, la base queda exactamente como estaba.
"""

from db import ErrorIntegridad
from validacion import ErrorValidacion, errores_registro, normalizar

PERSONAS = {
    "student": dict(tabla="StudentData", clave="gno", quien="alumno",
                    listado=("gno", "name", "lname", "std", "div", "username")),
    "teacher": dict(tabla="TeacherData", clave="trno", quien="docente",
                    listado=("trno", "name", "lname", "staught", "username")),
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

    # --- personas (R01 alumnos, R02 docentes) -----------------------------

    def listar(self, tipo):
        """Filas para el listado: 'clave' identifica el registro."""
        conf = PERSONAS[tipo]
        return self.db.consultar(f"SELECT {conf['clave']} AS clave, {', '.join(conf['listado'])} "
                                 f"FROM {conf['tabla']} ORDER BY name COLLATE NOCASE, lname COLLATE NOCASE")

    def obtener(self, tipo, clave):
        conf = PERSONAS[tipo]
        return self.db.uno(f"SELECT * FROM {conf['tabla']} WHERE {conf['clave']} = ?", (clave,))

    def registrar_persona(self, tipo, datos):
        datos = self.validar_persona(tipo, datos)
        with self.db.transaccion():
            self.db.insertar(PERSONAS[tipo]["tabla"], datos)
        return datos

    def actualizar_persona(self, tipo, original, datos):
        """Reemplaza todos los datos del registro 'original' (su N.° de registro)."""
        datos = self.validar_persona(tipo, datos, original=original)
        conf = PERSONAS[tipo]
        with self.db.transaccion():
            if self.db.actualizar_fila(conf["tabla"], datos, {conf["clave"]: original}) == 0:
                raise ErrorValidacion([(conf["clave"], f"El {conf['quien']} ya no existe: quizá otro usuario lo eliminó.")])
        return datos

    def eliminar(self, tipo, clave):
        conf = PERSONAS[tipo]
        with self.db.transaccion():
            return self.db.eliminar(conf["tabla"], {conf["clave"]: clave})


__all__ = ["Gestion", "ErrorValidacion", "ErrorIntegridad", "PERSONAS"]
