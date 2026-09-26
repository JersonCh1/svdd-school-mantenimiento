import tkinter as tk
import unittest

from validacion import configurar_numerico, error_numerico


class ErrorNumericoTest(unittest.TestCase):
    def test_movil_valido(self):
        self.assertIsNone(error_numerico("mno", "9920061467"))

    def test_movil_con_letras(self):
        self.assertIn("solo admite números", error_numerico("mno", "99200a1467"))

    def test_movil_corto(self):
        self.assertIn("10 dígitos", error_numerico("mno", "12345"))

    def test_aadhaar_con_guiones(self):
        self.assertIn("solo admite números", error_numerico("adno", "8829-3250-8844"))

    def test_aadhaar_valido_con_espacios_alrededor(self):
        self.assertIsNone(error_numerico("adno", " 882932508844\n"))

    def test_columna_no_numerica_no_se_valida(self):
        self.assertIsNone(error_numerico("name", "Rajan"))


class EntryNumericoTest(unittest.TestCase):
    def setUp(self):
        # La ventana debe estar mapeada: Tk descarta los eventos virtuales
        # (<<Paste>>) dirigidos a widgets que no se muestran.
        self.root = tk.Tk()
        self.entry = tk.Entry(self.root)
        self.entry.pack()
        configurar_numerico(self.entry, 12)
        self.root.update()

    def tearDown(self):
        self.root.destroy()

    def test_rechaza_letras_al_teclear(self):
        for c in "12ab-34":
            self.entry.insert("end", c)
        self.assertEqual(self.entry.get(), "1234")

    def test_respeta_el_maximo(self):
        self.entry.insert("end", "1234567890123")  # 13 dígitos: se rechaza entero
        self.assertEqual(self.entry.get(), "")

    def test_pegar_limpia_separadores(self):
        self.root.clipboard_clear()
        self.root.clipboard_append("8829-3250-8844")
        self.entry.focus_force()
        self.root.update()
        self.entry.event_generate("<<Paste>>")
        self.assertEqual(self.entry.get(), "882932508844")


if __name__ == "__main__":
    unittest.main()
