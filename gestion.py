"""Reglas de negocio de los registros (v5.0), separadas de la interfaz para
poder probarlas sin abrir ventanas.

Cada operación valida primero (R06) y escribe dentro de una transacción
(R07): si algo falla, la base queda exactamente como estaba.

v6.0: la búsqueda ignora tildes (MR-101), el director edita sus datos con
el mismo formulario y reglas que alumnos y docentes (MR-102), las
contraseñas se guardan con hash (MR-105) y cada matrícula tiene su nota
(MR-106).
"""

from datetime import datetime

import seguridad
from db import ErrorIntegridad
from texto import plano
from validacion import FORMATO_FECHA, ErrorValidacion, errores_registro, normalizar

REGISTROS = {
    "student": dict(tabla="StudentData", clave="gno", quien="alumno", orden="name COLLATE NOCASE, lname COLLATE NOCASE",
                    listado="SELECT gno AS clave, gno, name, lname, std, div, username FROM StudentData"),
    "teacher": dict(tabla="TeacherData", clave="trno", quien="docente", orden="name COLLATE NOCASE, lname COLLATE NOCASE",
                    listado="SELECT trno AS clave, trno, name, lname, staught, username FROM TeacherData"),
    # MR-102: el director solo edita su propio registro (no tiene listado).
    "principal": dict(tabla="PrincipalData", clave="trno", quien="director", orden="name",
                      listado="SELECT trno AS clave, trno, name, lname, username FROM PrincipalData"),
    "curso": dict(tabla="Curso", clave="id", quien="curso", orden="c.codigo",
                  listado="SELECT c.id AS clave, c.codigo, c.nombre, c.grado, c.trno, "
                          "TRIM(COALESCE(t.name, '') || ' ' || COALESCE(t.lname, '')) AS docente "
                          "FROM Curso c LEFT JOIN TeacherData t ON t.trno = c.trno"),
    "matricula": dict(tabla="Matricula", clave="id", quien="matrícula",
                      orden="m.periodo DESC, s.name COLLATE NOCASE, s.lname COLLATE NOCASE, c.codigo",
                      listado="SELECT m.id AS clave, m.periodo, m.gno, s.name || ' ' || s.lname AS alumno, "
                              "c.codigo, c.nombre AS curso, c.grado, m.fecha, m.nota "
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
    "principal": (("trno", "Ya existe un director con ese N.° de registro."),
                  ("username", "Ese usuario ya está en uso por otro director.")),
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

# MR-106: escala vigesimal; desde 11 el curso está aprobado.
NOTA_MAXIMA = 20
NOTA_APROBATORIA = 11


def estado_nota(nota):
    if nota is None:
        return "Sin nota"
    return "Aprobado" if nota >= NOTA_APROBATORIA else "Desaprobado"


class Gestion:
    def __init__(self, db):
        self.db = db

    # --- validación (R06) ------------------------------------------------

    def validar(self, tipo, datos, original=None):
        """Devuelve los datos normalizados o lanza ErrorValidacion con TODOS
        los problemas encontrados (no solo el primero). 'original' es la clave
        del registro que se está editando: no cuenta como duplicado de sí mismo.

        MR-105: al editar, una contraseña vacía significa «no cambiarla» (el
        formulario ya no muestra la guardada, que ahora es un hash)."""
        conservar_clave = original is not None and "password" in datos and \
            (datos["password"] is None or not str(datos["password"]).strip())
        if conservar_clave:
            datos = {c: v for c, v in datos.items() if c != "password"}
        errores = [e for e in errores_registro(tipo, datos) if not (conservar_clave and e[0] == "password")]
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
            # MR-101: el texto y la columna se comparan sin tildes ni mayúsculas.
            buscado = plano(filtro)
            patron = "%" + buscado.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            condiciones = [f"CAST({c} AS TEXT) = ? COLLATE NOCASE" for c in busqueda["exactos"]]
            condiciones += [f"plano({c}) LIKE ? ESCAPE '\\'" for c in busqueda["textos"]]
            params = [filtro] * len(busqueda["exactos"]) + [patron] * len(busqueda["textos"])
            sql += " WHERE " + " OR ".join(condiciones)
        return self.db.consultar(f"{sql} ORDER BY {conf['orden']}", params)

    def obtener(self, tipo, clave):
        conf = REGISTROS[tipo]
        return self.db.uno(f"SELECT * FROM {conf['tabla']} WHERE {conf['clave']} = ?", (clave,))

    @staticmethod
    def _con_hash(datos):
        """MR-105: la contraseña nunca llega a la base en texto plano."""
        if datos.get("password") is not None:
            datos["password"] = seguridad.hashear(datos["password"])
        return datos

    def registrar(self, tipo, datos):
        datos = self._con_hash(self.validar(tipo, datos))
        if tipo == "matricula":
            datos["fecha"] = datetime.now().strftime(FORMATO_FECHA)
        with self.db.transaccion():
            self.db.insertar(REGISTROS[tipo]["tabla"], datos)
            if REGISTROS[tipo]["clave"] not in datos:  # id autogenerado (cursos)
                datos[REGISTROS[tipo]["clave"]] = self.db.uno("SELECT last_insert_rowid()")[0]
        return datos

    def actualizar(self, tipo, original, datos):
        """Reemplaza los datos del registro cuya clave es 'original'."""
        datos = self._con_hash(self.validar(tipo, datos, original=original))
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

    # --- notas por matrícula (MR-106) ----------------------------------------

    def matricula_detalle(self, clave):
        """Alumno, curso, docente a cargo y nota de una matrícula."""
        return self.db.uno(
            "SELECT m.id, m.periodo, m.gno, s.name || ' ' || s.lname AS alumno, c.codigo, "
            "c.nombre AS curso, c.trno, m.nota FROM Matricula m JOIN StudentData s ON s.gno = m.gno "
            "JOIN Curso c ON c.id = m.curso_id WHERE m.id = ?", (clave,))

    def registrar_nota(self, clave, nota, trno=None):
        """Guarda la nota (0 a 20) de la matrícula 'clave'; vacía la borra.

        Con 'trno' (sesión de docente) solo se acepta si ese docente está a
        cargo del curso; el director registra sin esa restricción."""
        texto = "" if nota is None else str(nota).strip()
        if texto and not (texto.isdigit() and int(texto) <= NOTA_MAXIMA):
            raise ErrorValidacion([("nota", f"Nota debe ser un número entero de 0 a {NOTA_MAXIMA}.")])
        valor = int(texto) if texto else None
        with self.db.transaccion():
            fila = self.matricula_detalle(clave)
            if fila is None:
                raise ErrorValidacion([("nota", "La matrícula ya no existe: quizá otro usuario la anuló.")])
            if trno is not None and fila["trno"] != trno:
                raise ErrorValidacion([("nota", "Solo el docente a cargo del curso puede registrar esta nota.")])
            self.db.actualizar("Matricula", "nota", valor, {"id": clave})
        return valor

    def notas_de(self, gno):
        """Matrículas de un alumno con su nota y estado, del periodo más reciente al más antiguo."""
        filas = self.db.consultar(
            "SELECT m.id AS clave, m.periodo, c.codigo, c.nombre AS curso, m.nota "
            "FROM Matricula m JOIN Curso c ON c.id = m.curso_id WHERE m.gno = ? "
            "ORDER BY m.periodo DESC, c.codigo", (gno,))
        return [dict(f, estado=estado_nota(f["nota"])) for f in filas]


__all__ = ["Gestion", "ErrorValidacion", "ErrorIntegridad", "REGISTROS", "PERSONAS"]
