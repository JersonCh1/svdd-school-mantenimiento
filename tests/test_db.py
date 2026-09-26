import os
import shutil
import sqlite3
import tempfile
import unittest

import db
from db import BaseDatos, BaseDeDatosOcupada

ORIGEN = os.path.join(os.path.dirname(__file__), "..", "testdata.db")


class BaseDatosTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.ruta = os.path.join(self.dir, "testdata.db")
        shutil.copy(ORIGEN, self.ruta)
        self.espera = db.ESPERA_MS
        db.ESPERA_MS = 300
        self.db = BaseDatos(self.ruta)

    def tearDown(self):
        BaseDatos.cerrar()
        db.ESPERA_MS = self.espera
        shutil.rmtree(self.dir, ignore_errors=True)

    def otro_proceso(self):
        """Segunda conexión, como la de un visor de SQLite abierto al mismo tiempo."""
        return sqlite3.connect(self.ruta, timeout=0.1, isolation_level=None)

    def test_singleton(self):
        self.assertIs(BaseDatos(), self.db)
        self.assertIs(BaseDatos(self.ruta), self.db)

    def test_modo_wal(self):
        self.assertEqual(self.db.uno("PRAGMA journal_mode")[0], "wal")

    def test_ruta_inexistente_no_crea_archivo_vacio(self):
        BaseDatos.cerrar()
        falsa = os.path.join(self.dir, "no_existe.db")
        with self.assertRaises(FileNotFoundError):
            BaseDatos(falsa)
        self.assertFalse(os.path.exists(falsa))
        self.db = BaseDatos(self.ruta)

    def test_autenticar(self):
        fila = self.db.autenticar("PrincipalData", "RajanUp12", "RUpadhyay123")
        self.assertEqual(fila["name"], "Rajan")
        self.assertIsNone(self.db.autenticar("PrincipalData", "RajanUp12", "mala"))

    def test_inyeccion_sql_no_entra(self):
        self.assertIsNone(self.db.autenticar("PrincipalData", "' OR '1'='1", "' OR '1'='1"))

    def test_apostrofo_en_los_datos(self):
        self.db.insertar("TeacherData", {"name": "Ana", "lname": "D'Souza", "username": "ana", "password": "x"})
        self.assertEqual(self.db.autenticar("TeacherData", "ana", "x")["lname"], "D'Souza")

    def test_columna_fuera_del_esquema(self):
        with self.assertRaises(ValueError):
            self.db.actualizar("TeacherData", "ano", "1", {"name": "Darshi"})
        with self.assertRaises(ValueError):
            self.db.actualizar("TeacherData", "name = 'x'; --", "1", {"name": "Darshi"})

    def test_actualizar_devuelve_filas_afectadas(self):
        self.assertEqual(self.db.actualizar("TeacherData", "ctfc", "9th A", {"name": "Darshi", "trno": "9999"}), 1)
        self.assertEqual(self.db.actualizar("TeacherData", "ctfc", "9th A", {"name": "Nadie", "trno": "0"}), 0)

    def test_lee_mientras_otro_proceso_escribe(self):
        otro = self.otro_proceso()
        otro.execute("BEGIN EXCLUSIVE")
        otro.execute("UPDATE TeacherData SET ctfc = 'x'")
        try:
            self.assertIsNotNone(self.db.autenticar("PrincipalData", "RajanUp12", "RUpadhyay123"))
        finally:
            otro.execute("ROLLBACK")
            otro.close()

    def test_sin_wal_la_lectura_se_bloquea(self):
        """Muestra por qué se activó WAL: en modo 'delete' la misma situación falla."""
        BaseDatos.cerrar()
        c = sqlite3.connect(self.ruta)
        c.execute("PRAGMA journal_mode = DELETE")
        c.close()
        otro = self.otro_proceso()
        otro.execute("BEGIN EXCLUSIVE")
        lector = sqlite3.connect(self.ruta, timeout=0.1)
        try:
            with self.assertRaisesRegex(sqlite3.OperationalError, "locked"):
                lector.execute("SELECT name FROM PrincipalData").fetchall()
        finally:
            lector.close()
            otro.execute("ROLLBACK")
            otro.close()
            self.db = BaseDatos(self.ruta)

    def test_escritura_bloqueada_da_error_claro(self):
        otro = self.otro_proceso()
        otro.execute("BEGIN IMMEDIATE")
        try:
            with self.assertRaisesRegex(BaseDeDatosOcupada, "otro programa"):
                self.db.actualizar("TeacherData", "ctfc", "9th A", {"name": "Darshi", "trno": "9999"})
        finally:
            otro.execute("ROLLBACK")
            otro.close()

    def test_cerrar_vuelca_el_wal(self):
        self.db.actualizar("TeacherData", "ctfc", "9th A", {"name": "Darshi", "trno": "9999"})
        self.assertTrue(os.path.exists(self.ruta + "-wal"))
        BaseDatos.cerrar()
        self.assertFalse(os.path.exists(self.ruta + "-wal"))
        c = sqlite3.connect(self.ruta)
        self.assertEqual(c.execute("SELECT ctfc FROM TeacherData WHERE trno = 9999").fetchone()[0], "9th A")
        c.close()
        self.db = BaseDatos(self.ruta)


if __name__ == "__main__":
    unittest.main()
