import tkinter as tk
import unittest

from navegacion import Navegador


class NavegadorTest(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.nav = Navegador(self.root)

    def tearDown(self):
        self.root.destroy()

    def test_una_sola_pantalla_a_la_vez(self):
        a = self.nav.pantalla("300x200")
        b = self.nav.pantalla("400x300")
        self.assertFalse(a.winfo_exists())
        self.assertTrue(b.winfo_exists())
        self.assertEqual(self.root.winfo_children(), [b])

    def test_nunca_crea_ventanas_nuevas(self):
        for _ in range(5):
            tk.Label(self.nav.pantalla("300x200"), text="x").pack()
        self.assertEqual([w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)], [])

    def test_ajusta_el_tamano_de_la_ventana(self):
        self.nav.pantalla("640x480")
        self.root.update_idletasks()
        self.assertEqual(self.root.geometry().split("+")[0], "640x480")


if __name__ == "__main__":
    unittest.main()
