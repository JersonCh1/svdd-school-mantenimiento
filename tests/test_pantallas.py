import os
import shutil
import tempfile
import tkinter as tk
import unittest

from db import BaseDatos
from migraciones import migrar
from pantallas import ETIQUETA, Aplicacion

ORIGEN = os.path.join(os.path.dirname(__file__), "..", "testdata.db")


def widgets(w):
    yield w
    for c in w.winfo_children():
        yield from widgets(c)


class DisenoAdaptableTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        ruta = os.path.join(self.dir, "testdata.db")
        shutil.copy(ORIGEN, ruta)
        self.db = BaseDatos(ruta)
        migrar(self.db.con)
        self.root = tk.Tk()
        self.app = Aplicacion(self.root, self.db)

    def tearDown(self):
        self.root.destroy()
        BaseDatos.cerrar()
        shutil.rmtree(self.dir, ignore_errors=True)

    def abrir_panel(self):
        self.app.nav.sesion = (1, "RajanUp12", "RUpadhyay123")
        self.app.mostrar_panel()
        self.root.update()

    def problemas(self):
        self.root.update()
        malos = []
        for w in widgets(self.root):
            if isinstance(w, tk.Label) and w.cget("bg") == ETIQUETA and w.winfo_width() < w.winfo_reqwidth():
                malos.append(("etiqueta cortada", w.cget("text")))
            if isinstance(w, tk.Frame):
                fila = sorted((c for c in w.winfo_children() if c.winfo_manager() == "grid"
                               and c.grid_info()["row"] == 0), key=lambda c: c.winfo_x())
                for a, b in zip(fila, fila[1:]):
                    if a.winfo_x() + a.winfo_width() > b.winfo_x() + 1:
                        malos.append(("solapado", str(a)))
        return malos

    def test_sin_cortes_con_escala_normal_y_grande(self):
        for escala in (1.0, 1.75):
            with self.subTest(escala=escala):
                self.root.tk.call("tk", "scaling", escala)
                self.abrir_panel()
                self.assertEqual(self.problemas(), [])

    def test_los_valores_se_estiran_con_la_ventana(self):
        self.abrir_panel()
        direccion = next(w for w in widgets(self.root) if isinstance(w, tk.Label) and "Great Heights" in str(w.cget("text")))
        antes = direccion.winfo_width()
        self.root.geometry(f"{self.root.winfo_width() + 400}x{self.root.winfo_height()}")
        self.root.update()
        self.assertGreaterEqual(direccion.winfo_width(), antes + 350)
        self.assertEqual(self.problemas(), [])

    def test_no_se_puede_achicar_hasta_aplastar(self):
        self.abrir_panel()
        ancho, alto = self.root.minsize()
        self.assertGreater(ancho, 0)
        self.root.geometry("300x200")
        self.root.update()
        self.assertGreaterEqual(self.root.winfo_width(), ancho)


if __name__ == "__main__":
    unittest.main()
