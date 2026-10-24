"""Centralización de la conexión a SQLite (v4.0 — R03).

Toda la aplicación usa una sola conexión (Singleton) a testdata.db:
  - Ruta absoluta junto al programa: ejecutarlo desde otra carpeta ya no crea
    un testdata.db vacío.
  - journal_mode=WAL: las lecturas no se bloquean mientras otro proceso
    (p. ej. un visor de SQLite) tiene una escritura abierta.
  - busy_timeout: ante un bloqueo, espera antes de fallar.
  - Consultas parametrizadas; los nombres de columna se validan contra el
    esquema real (no se pueden pasar como parámetro '?').

v5.0 R07 — persistencia e integridad:
  - PRAGMA foreign_keys = ON: SQLite no revisa las relaciones (cursos,
    matrículas) si no se activa en cada conexión.
  - transaccion(): varias escrituras se confirman juntas o se revierten
    todas si una falla.
  - Un duplicado o una relación rota llegan como ErrorIntegridad, con un
    mensaje claro, y nunca dejan la base a medio escribir.

v6.0:
  - MR-101: función plano() registrada en la conexión para buscar sin tildes.
  - MR-103: si la carpeta del .exe no admite escritura (Program Files), la
    base se ubica en la carpeta de datos del usuario.
  - MR-104: respaldar() copia la base con la API de respaldo de SQLite.
  - MR-105: autenticar() compara contra el hash de la contraseña.
"""

import os
import shutil
import sqlite3
import sys
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime

import seguridad
from texto import plano

ESPERA_MS = 3000
NOMBRE = "testdata.db"
RESPALDOS_CONSERVADOS = 10

TABLAS = {
    "student": "StudentData",
    "teacher": "TeacherData",
    "principal": "PrincipalData",
    "curso": "Curso",
    "matricula": "Matricula",
}

# Nombre legible de las columnas que tienen índice único (mensajes de duplicado).
UNICOS = {
    "username": "ese usuario",
    "gno": "ese N.° de registro general",
    "trno": "ese N.° de registro docente",
    "codigo": "ese código de curso",
}


def carpeta_de_datos():
    """Carpeta de datos del usuario: %LOCALAPPDATA%\\SVDD-School en Windows,
    ~/.local/share/SVDD-School en otros sistemas."""
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "SVDD-School")


def se_puede_escribir(carpeta):
    # os.access() no sirve en Windows: dice que sí en Program Files aunque
    # luego crear un archivo falle. Se prueba creando uno de verdad.
    try:
        with tempfile.TemporaryFile(dir=carpeta):
            return True
    except OSError:
        return False


def ubicar_base(carpeta_programa, incluida):
    """MR-103: testdata.db junto al programa si esa carpeta admite escritura;
    si no (instalado en C:\\Program Files, carpeta de solo lectura), en la
    carpeta de datos del usuario. SQLite en modo WAL necesita crear -wal y
    -shm junto a la base: en una carpeta de solo lectura ni siquiera se podía
    iniciar sesión. La primera vez se copia la base existente o la incluida."""
    ruta = os.path.join(carpeta_programa, NOMBRE)
    if se_puede_escribir(carpeta_programa):
        if not os.path.exists(ruta) and incluida and os.path.exists(incluida):
            shutil.copy(incluida, ruta)
        return ruta
    datos = carpeta_de_datos()
    os.makedirs(datos, exist_ok=True)
    destino = os.path.join(datos, NOMBRE)
    if not os.path.exists(destino):
        origen = ruta if os.path.exists(ruta) else incluida
        if origen and os.path.exists(origen):
            shutil.copy(origen, destino)
    return destino


def ruta_por_defecto():
    """testdata.db junto al programa.

    En el .exe de PyInstaller, __file__ apunta a una carpeta temporal que se
    borra al cerrar: los cambios se perderían. Ahí se usa la carpeta del .exe
    (o la de datos del usuario, MR-103) y, la primera vez, se copia la base
    incluida en el ejecutable."""
    if getattr(sys, "frozen", False):
        return ubicar_base(os.path.dirname(sys.executable),
                           os.path.join(getattr(sys, "_MEIPASS", ""), NOMBRE))
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), NOMBRE)


def _orden_respaldo(nombre):
    """'testdata-20261024-101010-2.db' -> ('20261024-101010', 2). Por texto,
    '-2.db' quedaría antes que '.db' y se borraría el respaldo más nuevo."""
    partes = nombre[len("testdata-"):-len(".db")].split("-")
    return "-".join(partes[:2]), int(partes[2]) if len(partes) > 2 and partes[2].isdigit() else 0


class BaseDeDatosOcupada(Exception):
    """La base sigue bloqueada por otro proceso tras la espera."""


class ErrorIntegridad(Exception):
    """Duplicado o relación rota: la operación se revirtió completa."""


def mensaje_integridad(error):
    texto = str(error)
    if "UNIQUE" in texto:
        if "Matricula" in texto:
            return "El alumno ya está matriculado en ese curso para ese periodo."
        columna = texto.rsplit(".", 1)[-1]
        return f"Ya existe un registro con {UNICOS.get(columna, 'esos datos')}."
    if "FOREIGN KEY" in texto:
        return ("El registro está relacionado con otros (cursos o matrículas): "
                "no se puede eliminar ni dejar esa relación sin destino.")
    return f"La base de datos rechazó la operación: {texto}"


class BaseDatos:
    _instancia = None
    _candado = threading.Lock()

    def __new__(cls, ruta=None):
        with cls._candado:
            if cls._instancia is None:
                instancia = super().__new__(cls)
                instancia._abrir(ruta or ruta_por_defecto())
                cls._instancia = instancia
            return cls._instancia

    def _abrir(self, ruta):
        if not os.path.exists(ruta):
            # sqlite3.connect() crearía un archivo vacío y el error aparecería
            # recién en la primera consulta ("no such table").
            raise FileNotFoundError(f"No se encontró la base de datos: {ruta}")
        self.ruta = ruta
        self.con = sqlite3.connect(ruta, timeout=ESPERA_MS / 1000)
        self.con.row_factory = sqlite3.Row
        self.con.execute(f"PRAGMA busy_timeout = {ESPERA_MS}")
        self.con.execute("PRAGMA journal_mode = WAL")
        self.con.execute("PRAGMA foreign_keys = ON")
        # MR-101: plano(col) LIKE plano(?) compara sin tildes ni mayúsculas.
        self.con.create_function("plano", 1, plano, deterministic=True)
        self._columnas = {}
        self._en_transaccion = False

    @classmethod
    def cerrar(cls):
        """Cierra la conexión. SQLite vuelca el WAL al archivo principal
        (checkpoint) al cerrarse la última conexión."""
        with cls._candado:
            if cls._instancia is not None:
                cls._instancia.con.close()
                cls._instancia = None

    # --- acceso genérico -------------------------------------------------

    def _ejecutar(self, sql, params=()):
        try:
            return self.con.execute(sql, params)
        except sqlite3.OperationalError as e:
            if "locked" in str(e) or "busy" in str(e):
                raise BaseDeDatosOcupada(
                    "La base de datos está siendo usada por otro programa. "
                    "Ciérralo e inténtalo de nuevo.") from e
            raise

    def consultar(self, sql, params=()):
        return self._ejecutar(sql, params).fetchall()

    def uno(self, sql, params=()):
        return self._ejecutar(sql, params).fetchone()

    @contextmanager
    def transaccion(self):
        """Commit al final si todo salió bien; rollback de TODO si algo falla.

        Se puede anidar: solo la transacción externa confirma. (Con 'with con:'
        anidados, el interno confirmaba a mitad de la operación.)"""
        if self._en_transaccion:
            yield self
            return
        self._en_transaccion = True
        try:
            yield self
        except sqlite3.IntegrityError as e:
            self.con.rollback()
            raise ErrorIntegridad(mensaje_integridad(e)) from e
        except BaseException:
            self.con.rollback()
            raise
        else:
            self.con.commit()
        finally:
            self._en_transaccion = False

    def escribir(self, sql, params=()):
        with self.transaccion():
            return self._ejecutar(sql, params).rowcount

    def columnas(self, tabla):
        if tabla not in TABLAS.values():
            raise ValueError(f"Tabla desconocida: {tabla}")
        if tabla not in self._columnas:
            self._columnas[tabla] = [f[1] for f in self.con.execute(f"PRAGMA table_info({tabla})")]
        return self._columnas[tabla]

    def _columna(self, tabla, columna):
        if columna not in self.columnas(tabla):
            raise ValueError(f"{tabla} no tiene la columna {columna!r}")
        return columna

    # --- operaciones de la aplicación -----------------------------------

    def autenticar(self, tabla, usuario, clave):
        """Fila del usuario si usuario y contraseña coinciden; si no, None.
        MR-105: la contraseña ya no se compara en el SQL sino contra su hash."""
        self.columnas(tabla)
        fila = self.uno(f"SELECT rowid, * FROM {tabla} WHERE username = ?", (usuario,))
        if fila is None or not seguridad.verificar(clave, fila["password"]):
            return None
        return fila

    def respaldar(self, carpeta=None, conservar=RESPALDOS_CONSERVADOS):
        """MR-104: copia de la base en 'respaldos/testdata-AAAAMMDD-HHMMSS.db'.

        Copiar el archivo con shutil no sirve en modo WAL: los últimos cambios
        siguen en testdata.db-wal y la copia saldría sin ellos (o a medio
        escribir). Connection.backup() copia página por página una imagen
        consistente, incluido lo que está en el WAL. Se conservan las
        'conservar' copias más recientes. Devuelve la ruta del respaldo."""
        carpeta = carpeta or os.path.join(os.path.dirname(self.ruta), "respaldos")
        os.makedirs(carpeta, exist_ok=True)
        sello = f"{datetime.now():%Y%m%d-%H%M%S}"
        # Dos respaldos en el mismo segundo: el nuevo lleva el número siguiente
        # (no el primero libre, que podría ser uno ya borrado y ordenaría antes).
        mismos = [_orden_respaldo(f)[1] for f in os.listdir(carpeta) if f.startswith(f"testdata-{sello}")]
        sufijo = f"-{max(mismos) + 1}" if mismos else ""
        destino = os.path.join(carpeta, f"testdata-{sello}{sufijo}.db")
        copia = sqlite3.connect(destino)
        try:
            self.con.backup(copia)
        except sqlite3.OperationalError as e:
            copia.close()
            os.remove(destino)
            if "locked" in str(e) or "busy" in str(e):
                raise BaseDeDatosOcupada(
                    "La base de datos está siendo usada por otro programa. "
                    "Ciérralo e inténtalo de nuevo.") from e
            raise
        copia.close()
        respaldos = sorted((f for f in os.listdir(carpeta) if f.startswith("testdata-") and f.endswith(".db")),
                           key=_orden_respaldo)
        for viejo in respaldos[:-conservar] if conservar else ():
            os.remove(os.path.join(carpeta, viejo))
        return destino

    def insertar(self, tabla, datos):
        cols = [self._columna(tabla, c) for c in datos]
        marcas = ", ".join("?" for _ in cols)
        return self.escribir(f"INSERT INTO {tabla} ({', '.join(cols)}) VALUES ({marcas})",
                             tuple(datos.values()))

    def _condiciones(self, tabla, donde):
        return " AND ".join(f"{self._columna(tabla, c)} = ?" for c in donde)

    def actualizar(self, tabla, columna, valor, donde):
        """UPDATE de una columna; 'donde' es un dict columna -> valor. Devuelve filas afectadas."""
        return self.actualizar_fila(tabla, {columna: valor}, donde)

    def actualizar_fila(self, tabla, datos, donde):
        """UPDATE de varias columnas a la vez. Devuelve filas afectadas."""
        asignaciones = ", ".join(f"{self._columna(tabla, c)} = ?" for c in datos)
        return self.escribir(f"UPDATE {tabla} SET {asignaciones} WHERE {self._condiciones(tabla, donde)}",
                             (*datos.values(), *donde.values()))

    def eliminar(self, tabla, donde):
        """DELETE de los registros que cumplen 'donde'. Devuelve filas afectadas."""
        return self.escribir(f"DELETE FROM {tabla} WHERE {self._condiciones(tabla, donde)}",
                             tuple(donde.values()))
