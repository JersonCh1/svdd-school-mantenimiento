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
        a = self.nav.pantalla()
        b = self.nav.pantalla()
        self.assertFalse(a.winfo_exists())
        self.assertTrue(b.winfo_exists())
        self.assertEqual(self.root.winfo_children(), [b])

    def test_nunca_crea_ventanas_nuevas(self):
        for _ in range(5):
            tk.Label(self.nav.pantalla(), text="x").pack()
        self.assertEqual([w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)], [])

    def test_el_tamano_sale_del_contenido(self):
        p = self.nav.pantalla()
        tk.Frame(p, width=500, height=300).pack()
        self.nav.ajustar(minimo=(600, 0))
        self.root.update_idletasks()
        self.assertEqual(self.root.geometry().split("+")[0], "600x300")
        self.assertEqual(self.root.minsize(), (600, 300))


if __name__ == "__main__":
    unittest.main()
