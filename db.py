"""Centralización de la conexión a SQLite (v4.0 — R03).

Toda la aplicación usa una sola conexión (Singleton) a testdata.db:
  - Ruta absoluta junto al programa: ejecutarlo desde otra carpeta ya no crea
    un testdata.db vacío.
  - journal_mode=WAL: las lecturas no se bloquean mientras otro proceso
    (p. ej. un visor de SQLite) tiene una escritura abierta.
  - busy_timeout: ante un bloqueo, espera antes de fallar.
  - Consultas parametrizadas; los nombres de columna se validan contra el
    esquema real (no se pueden pasar como parámetro '?').
"""

import os
import sqlite3
import threading

RUTA_POR_DEFECTO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata.db")
ESPERA_MS = 3000

TABLAS = {
    "student": "StudentData",
    "teacher": "TeacherData",
    "principal": "PrincipalData",
}


class BaseDeDatosOcupada(Exception):
    """La base sigue bloqueada por otro proceso tras la espera."""


class BaseDatos:
    _instancia = None
    _candado = threading.Lock()

    def __new__(cls, ruta=None):
        with cls._candado:
            if cls._instancia is None:
                instancia = super().__new__(cls)
                instancia._abrir(ruta or RUTA_POR_DEFECTO)
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
        self._columnas = {}

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

    def escribir(self, sql, params=()):
        with self.con:  # commit, o rollback si falla
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
        """Fila del usuario si usuario y contraseña coinciden; si no, None."""
        self.columnas(tabla)
        return self.uno(f"SELECT rowid, * FROM {tabla} WHERE username = ? AND password = ?",
                        (usuario, clave))

    def insertar(self, tabla, datos):
        cols = [self._columna(tabla, c) for c in datos]
        marcas = ", ".join("?" for _ in cols)
        return self.escribir(f"INSERT INTO {tabla} ({', '.join(cols)}) VALUES ({marcas})",
                             tuple(datos.values()))

    def actualizar(self, tabla, columna, valor, donde):
        """UPDATE de una columna; 'donde' es un dict columna -> valor. Devuelve filas afectadas."""
        col = self._columna(tabla, columna)
        condiciones = " AND ".join(f"{self._columna(tabla, c)} = ?" for c in donde)
        return self.escribir(f"UPDATE {tabla} SET {col} = ? WHERE {condiciones}",
                             (valor, *donde.values()))
