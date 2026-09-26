import os
import tempfile
import tkinter as tk
import unittest

import fotos

DEMO = os.path.join(os.path.dirname(__file__), "..", "docs", "fotos-demo")


class LeerFotoTest(unittest.TestCase):
    def test_jpg_valido(self):
        datos = fotos.leer_foto(os.path.join(DEMO, "docente_ana_rojas.jpg"))
        self.assertTrue(datos.startswith(b"\xff\xd8"))

    def test_png_valido(self):
        self.assertTrue(fotos.leer_foto(os.path.join(DEMO, "director_rajan.png")).startswith(b"\x89PNG"))

    def test_texto_con_extension_png(self):
        with self.assertRaisesRegex(ValueError, "no es una imagen"):
            fotos.leer_foto(os.path.join(DEMO, "no_es_imagen.png"))

    def test_mayor_a_2mb(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\0" * (fotos.MAX_BYTES + 1))
        try:
            with self.assertRaisesRegex(ValueError, "2 MB"):
                fotos.leer_foto(f.name)
        finally:
            os.remove(f.name)

    def test_formato_no_admitido(self):
        from PIL import Image
        ruta = os.path.join(tempfile.gettempdir(), "svdd_prueba.bmp")
        Image.new("RGB", (10, 10)).save(ruta, "BMP")
        try:
            with self.assertRaisesRegex(ValueError, "BMP no admitido"):
                fotos.leer_foto(ruta)
        finally:
            os.remove(ruta)


class MiniaturaTest(unittest.TestCase):
    def test_conserva_proporcion_y_referencia(self):
        root = tk.Tk()
        try:
            label = tk.Label(root)
            fotos.mostrar(label, fotos.leer_foto(os.path.join(DEMO, "director_rajan.png")), (130, 150))
            self.assertEqual((label.image.width(), label.image.height()), (125, 150))
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
