"""v5.0 R07: persistencia e integridad de la información."""
import os
import shutil
import tempfile
import unittest

from db import BaseDatos, ErrorIntegridad
from migraciones import migrar, v5_indices_unicos, v5_quitar_duplicados

ORIGEN = os.path.join(os.path.dirname(__file__), "..", "testdata.db")


class PersistenciaTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.ruta = os.path.join(self.dir, "testdata.db")
        shutil.copy(ORIGEN, self.ruta)
        self.db = BaseDatos(self.ruta)
        migrar(self.db.con)

    def tearDown(self):
        BaseDatos.cerrar()
        shutil.rmtree(self.dir, ignore_errors=True)

    def contar(self, tabla, **donde):
        cond = " AND ".join(f"{c} = ?" for c in donde) or "1"
        return self.db.uno(f"SELECT COUNT(*) FROM {tabla} WHERE {cond}", tuple(donde.values()))[0]

    def test_claves_foraneas_activas(self):
        self.assertEqual(self.db.uno("PRAGMA foreign_keys")[0], 1)

    def test_migracion_quita_la_copia_exacta_del_5555(self):
        self.assertEqual(self.contar("TeacherData", username="5555"), 1)

    def test_migracion_es_idempotente(self):
        self.assertEqual(v5_quitar_duplicados(self.db.con), [])
        self.assertEqual(v5_indices_unicos(self.db.con), [])

    def test_duplicado_rechazado_con_mensaje_claro(self):
        with self.assertRaisesRegex(ErrorIntegridad, "ese usuario"):
            self.db.insertar("TeacherData", {"name": "X", "username": "Darshi999", "trno": 7777})
        with self.assertRaisesRegex(ErrorIntegridad, "registro docente"):
            self.db.insertar("TeacherData", {"name": "X", "username": "nuevo", "trno": 9999})
        self.assertEqual(self.contar("TeacherData", username="nuevo"), 0)

    def test_error_a_mitad_revierte_todo(self):
        antes = self.contar("StudentData")
        with self.assertRaises(ErrorIntegridad):
            with self.db.transaccion():
                self.db.insertar("StudentData", {"name": "Ana", "username": "ana01", "gno": 5001})
                self.db.insertar("StudentData", {"name": "Otra", "username": "ana01", "gno": 5002})
        self.assertEqual(self.contar("StudentData"), antes)

    def test_excepcion_cualquiera_tambien_revierte(self):
        with self.assertRaises(RuntimeError):
            with self.db.transaccion():
                self.db.actualizar("StudentData", "name", "Cambiado", {"gno": 3644})
                raise RuntimeError("falla al guardar")
        self.assertEqual(self.contar("StudentData", name="Cambiado"), 0)

    def test_los_datos_se_recuperan_al_reiniciar(self):
        self.db.insertar("StudentData", {"name": "Lucía", "username": "lucia", "gno": 6001})
        self.db.actualizar_fila("StudentData", {"std": "5th", "div": "A"}, {"gno": 6001})
        BaseDatos.cerrar()
        self.db = BaseDatos(self.ruta)
        fila = self.db.uno("SELECT name, std, div FROM StudentData WHERE gno = 6001")
        self.assertEqual(tuple(fila), ("Lucía", "5th", "A"))

    def test_eliminar(self):
        self.assertEqual(self.db.eliminar("StudentData", {"gno": 1100}), 1)
        self.assertEqual(self.db.eliminar("StudentData", {"gno": 1100}), 0)


if __name__ == "__main__":
    unittest.main()
