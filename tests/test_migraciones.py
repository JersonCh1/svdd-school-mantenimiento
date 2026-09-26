import sqlite3
import unittest

from migraciones import v2_normalizar_numeros

ESQUEMA = "CREATE TABLE {}(username TEXT, mno TEXT, adno TEXT)"


class NormalizarNumerosTest(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        for t in ("StudentData", "TeacherData", "PrincipalData"):
            self.con.execute(ESQUEMA.format(t))
        self.con.executemany("INSERT INTO StudentData VALUES(?,?,?)", [
            ("ok", "9920061467", "8829-3250-8844"),
            ("basura", "y65765uytj67", "juu67u456456"),
        ])
        self.con.execute("INSERT INTO PrincipalData VALUES('dir','2345671234/4657382910','101010101010')")

    def fila(self, tabla, usuario):
        return self.con.execute(f"SELECT mno, adno FROM {tabla} WHERE username=?", (usuario,)).fetchone()

    def test_quita_guiones_del_aadhaar(self):
        v2_normalizar_numeros(self.con)
        self.assertEqual(self.fila("StudentData", "ok"), ("9920061467", "882932508844"))

    def test_registros_con_letras_quedan_vacios(self):
        v2_normalizar_numeros(self.con)
        self.assertEqual(self.fila("StudentData", "basura"), (None, None))

    def test_dos_celulares_conserva_el_primero(self):
        v2_normalizar_numeros(self.con)
        self.assertEqual(self.fila("PrincipalData", "dir"), ("2345671234", "101010101010"))

    def test_es_idempotente(self):
        self.assertTrue(v2_normalizar_numeros(self.con))
        self.assertEqual(v2_normalizar_numeros(self.con), [])


if __name__ == "__main__":
    unittest.main()
