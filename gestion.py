"""Reglas de negocio de los registros (v5.0), separadas de la interfaz para
poder probarlas sin abrir ventanas.

Cada operación valida primero (R06) y escribe dentro de una transacción
(R07): si algo falla, la base queda exactamente como estaba.
"""

from datetime import datetime

from db import ErrorIntegridad
from validacion import FORMATO_FECHA, ErrorValidacion, errores_registro, normalizar

REGISTROS = {
    "student": dict(tabla="StudentData", clave="gno", quien="alumno", orden="name COLLATE NOCASE, lname COLLATE NOCASE",
                    listado="SELECT gno AS clave, gno, name, lname, std, div, username FROM StudentData"),
    "teacher": dict(tabla="TeacherData", clave="trno", quien="docente", orden="name COLLATE NOCASE, lname COLLATE NOCASE",
                    listado="SELECT trno AS clave, trno, name, lname, staught, username FROM TeacherData"),
    "curso": dict(tabla="Curso", clave="id", quien="curso", orden="c.codigo",
                  listado="SELECT c.id AS clave, c.codigo, c.nombre, c.grado, c.trno, "
                          "TRIM(COALESCE(t.name, '') || ' ' || COALESCE(t.lname, '')) AS docente "
                          "FROM Curso c LEFT JOIN TeacherData t ON t.trno = c.trno"),
    "matricula": dict(tabla="Matricula", clave="id", quien="matrícula",
                      orden="m.periodo DESC, s.name COLLATE NOCASE, s.lname COLLATE NOCASE, c.codigo",
                      listado="SELECT m.id AS clave, m.periodo, m.gno, s.name || ' ' || s.lname AS alumno, "
                              "c.codigo, c.nombre AS curso, c.grado, m.fecha "
                              "FROM Matricula m JOIN StudentData s ON s.gno = m.gno JOIN Curso c ON c.id = m.curso_id"),
}
PERSONAS = {t: REGISTROS[t] for t in ("student", "teacher")}

# R05: en qué se busca. El identificador debe coincidir completo; los textos
# (nombre, apellido, usuario, curso) basta con que contengan lo buscado.
BUSQUEDA = {
    "student": dict(exactos=("gno",), textos=("name || ' ' || lname", "username")),
    "teacher": dict(exactos=("trno",), textos=("name || ' ' || lname", "username")),
    "curso": dict(exactos=("c.codigo",), textos=("c.nombre", "c.codigo", "t.name || ' ' || t.lname")),
    "matricula": dict(exactos=("m.gno", "m.periodo"), textos=("s.name || ' ' || s.lname", "c.codigo", "c.nombre")),
}

# Columnas que no pueden repetirse dentro de cada tabla, con el texto del mensaje.
UNICAS = {
    "student": (("gno", "Ya existe un alumno con ese N.° de registro general."),
                ("username", "Ese usuario ya está en uso por otro alumno.")),
    "teacher": (("trno", "Ya existe un docente con ese N.° de registro docente."),
                ("username", "Ese usuario ya está en uso por otro docente.")),
    "curso": (("codigo", "Ya existe un curso con ese código."),),
    "matricula": (),
}

# Antes de eliminar se revisan las relaciones (consulta que cuenta, mensaje).
RELACIONES = {
    "teacher": (("SELECT COUNT(*) FROM Curso WHERE trno = ?",
                 "El docente tiene {n} curso(s) a su cargo. Asigna esos cursos a otro docente antes de eliminarlo."),),
    "student": (("SELECT COUNT(*) FROM Matricula WHERE gno = ?",
                 "El alumno tiene {n} matrícula(s). Anúlalas antes de eliminarlo."),),
    "curso": (("SELECT COUNT(*) FROM Matricula WHERE curso_id = ?",
               "El curso tiene {n} alumno(s) matriculado(s). Anula esas matrículas antes de eliminarlo."),),
}


class Gestion:
    def __init__(self, db):
        self.db = db

    # --- validación (R06) ------------------------------------------------

    def validar(self, tipo, datos, original=None):
        """Devuelve los datos normalizados o lanza ErrorValidacion con TODOS
        los problemas encontrados (no solo el primero). 'original' es la clave
        del registro que se está editando: no cuenta como duplicado de sí mismo."""
        errores = errores_registro(tipo, datos)
        if errores:
            raise ErrorValidacion(errores)
        datos = normalizar(tipo, datos)
        conf = REGISTROS[tipo]
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
        if tipo == "curso" and datos.get("trno") is not None and \
                not self.db.uno("SELECT 1 FROM TeacherData WHERE trno = ?", (datos["trno"],)):
            errores.append(("trno", "El docente elegido no está registrado."))
        if tipo == "matricula":
            errores += self._errores_matricula(datos)
        if errores:
            raise ErrorValidacion(errores)
        return datos

    def _errores_matricula(self, datos):
        """R04: el alumno y el curso deben existir y no puede repetirse la
        misma matrícula (alumno + curso + periodo)."""
        errores = []
        if not self.db.uno("SELECT 1 FROM StudentData WHERE gno = ?", (datos["gno"],)):
            errores.append(("gno", "El alumno no está registrado."))
        if not self.db.uno("SELECT 1 FROM Curso WHERE id = ?", (datos["curso_id"],)):
            errores.append(("curso_id", "El curso no está registrado."))
        if not errores and self.db.uno("SELECT 1 FROM Matricula WHERE gno = ? AND curso_id = ? AND periodo = ?",
                                       (datos["gno"], datos["curso_id"], datos["periodo"])):
            errores.append(("curso_id", f"El alumno ya está matriculado en ese curso en el periodo {datos['periodo']}."))
        return errores

    # --- registrar, consultar, actualizar y eliminar ------------------------
    # R01 alumnos, R02 docentes, R03 cursos, R04 matrículas (solo registrar,
    # consultar y anular: una matrícula equivocada se anula y se registra otra).

    def listar(self, tipo, filtro=""):
        """Filas para el listado: 'clave' identifica el registro. Con 'filtro'
        (R05) solo las que coinciden por identificador o por nombre."""
        conf = REGISTROS[tipo]
        sql, params = conf["listado"], []
        filtro = filtro.strip()
        if filtro:
            busqueda = BUSQUEDA[tipo]
            patron = "%" + filtro.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            condiciones = [f"CAST({c} AS TEXT) = ? COLLATE NOCASE" for c in busqueda["exactos"]]
            condiciones += [f"{c} LIKE ? ESCAPE '\\'" for c in busqueda["textos"]]
            params = [filtro] * len(busqueda["exactos"]) + [patron] * len(busqueda["textos"])
            sql += " WHERE " + " OR ".join(condiciones)
        return self.db.consultar(f"{sql} ORDER BY {conf['orden']}", params)

    def obtener(self, tipo, clave):
        conf = REGISTROS[tipo]
        return self.db.uno(f"SELECT * FROM {conf['tabla']} WHERE {conf['clave']} = ?", (clave,))

    def registrar(self, tipo, datos):
        datos = self.validar(tipo, datos)
        if tipo == "matricula":
            datos["fecha"] = datetime.now().strftime(FORMATO_FECHA)
        with self.db.transaccion():
            self.db.insertar(REGISTROS[tipo]["tabla"], datos)
            if REGISTROS[tipo]["clave"] not in datos:  # id autogenerado (cursos)
                datos[REGISTROS[tipo]["clave"]] = self.db.uno("SELECT last_insert_rowid()")[0]
        return datos

    def actualizar(self, tipo, original, datos):
        """Reemplaza los datos del registro cuya clave es 'original'."""
        datos = self.validar(tipo, datos, original=original)
        conf = REGISTROS[tipo]
        with self.db.transaccion():
            if self.db.actualizar_fila(conf["tabla"], datos, {conf["clave"]: original}) == 0:
                raise ErrorValidacion([(conf["clave"], f"El {conf['quien']} ya no existe: quizá otro usuario lo eliminó.")])
        datos.setdefault(conf["clave"], original)
        return datos

    def eliminar(self, tipo, clave):
        """Revisa primero las relaciones; si hay registros que dependen de este,
        no borra nada y explica qué hay que hacer. La clave foránea de SQLite
        es la segunda barrera (R07)."""
        conf = REGISTROS[tipo]
        with self.db.transaccion():
            for sql, mensaje in RELACIONES.get(tipo, ()):
                n = self.db.uno(sql, (clave,))[0]
                if n:
                    raise ErrorValidacion([(conf["clave"], mensaje.format(n=n))])
            return self.db.eliminar(conf["tabla"], {conf["clave"]: clave})


__all__ = ["Gestion", "ErrorValidacion", "ErrorIntegridad", "REGISTROS", "PERSONAS"]
