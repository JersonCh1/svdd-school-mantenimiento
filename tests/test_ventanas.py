import tkinter as tk
import unittest

import ventanas


class VentanasTest(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.panel = tk.Toplevel(self.root)

    def tearDown(self):
        self.root.destroy()

    def abrir(self, clave):
        if ventanas.enfocar_si_abierta(clave):
            return None
        v = tk.Toplevel(self.panel)
        ventanas.registrar(clave, v, self.panel)
        return v

    def hijas(self):
        return [w for w in self.panel.winfo_children() if isinstance(w, tk.Toplevel)]

    def test_no_duplica_formularios(self):
        self.assertIsNotNone(self.abrir("alta"))
        self.assertIsNone(self.abrir("alta"))
        self.assertEqual(len(self.hijas()), 1)

    def test_cerrar_permite_reabrir(self):
        self.abrir("alta")
        ventanas.cerrar("alta")
        self.assertEqual(self.hijas(), [])
        self.assertIsNotNone(self.abrir("alta"))

    def test_cerrar_sesion_vuelve_al_login(self):
        limpiado = []
        cerrar_sesion = ventanas.abrir_panel(self.root, self.panel, lambda: limpiado.append(True))
        self.abrir("alta")
        self.assertEqual(self.root.state(), "withdrawn")
        cerrar_sesion()
        self.assertEqual(self.root.state(), "normal")
        self.assertEqual(limpiado, [True])
        self.assertFalse(ventanas.enfocar_si_abierta("alta"))


if __name__ == "__main__":
    unittest.main()
