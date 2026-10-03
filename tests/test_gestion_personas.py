"""v5.0 R01/R02: alta, consulta, edición y baja de alumnos y docentes."""
import os
import shutil
import tempfile
import tkinter as tk
import unittest
from tkinter import ttk
from unittest import mock

from db import BaseDatos
from gestion import Gestion
from migraciones import migrar
from pantallas import Aplicacion
from validacion import ErrorValidacion

ORIGEN = os.path.join(os.path.dirname(__file__), "..", "testdata.db")


def widgets(w):
    yield w
    for c in w.winfo_children():
        yield from widgets(c)


class BaseTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.ruta = os.path.join(self.dir, "testdata.db")
        shutil.copy(ORIGEN, self.ruta)
        self.db = BaseDatos(self.ruta)
        migrar(self.db.con)
        self.g = Gestion(self.db)

    def tearDown(self):
        BaseDatos.cerrar()
        shutil.rmtree(self.dir, ignore_errors=True)


class AlumnosTest(BaseTest):
    ALUMNO = {"name": "Lucía", "lname": "Mamani", "gno": "5001", "username": "lucia", "password": "x1"}

    def test_listar_incluye_a_todos(self):
        claves = [f["clave"] for f in self.g.listar("student")]
        self.assertIn(3644, claves)
        self.assertEqual(len(claves), 7)

    def test_ciclo_completo(self):
        self.g.registrar_persona("student", self.ALUMNO)
        self.g.actualizar_persona("student", 5001, {**self.ALUMNO, "gno": "5002", "std": "6th"})
        self.assertIsNone(self.g.obtener("student", 5001))
        self.assertEqual(self.g.obtener("student", 5002)["std"], "6th")
        self.assertEqual(self.g.eliminar("student", 5002), 1)
        self.assertIsNone(self.g.obtener("student", 5002))

    def test_editar_registro_borrado(self):
        with self.assertRaisesRegex(ErrorValidacion, "ya no existe"):
            self.g.actualizar_persona("student", 9876, self.ALUMNO)


class PantallaGestionTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.root = tk.Tk()
        self.app = Aplicacion(self.root, self.db)
        self.app.nav.sesion = (2, "Darshi999", "darshik@26")

    def tearDown(self):
        self.root.destroy()
        super().tearDown()

    def boton(self, texto):
        b = next(w for w in widgets(self.app.nav.actual) if isinstance(w, tk.Button) and w.cget("text") == texto)
        b.invoke()
        self.root.update()

    def tabla(self):
        return next(w for w in widgets(self.app.nav.actual) if isinstance(w, ttk.Treeview))

    def test_el_panel_del_docente_lleva_a_alumnos(self):
        self.app.mostrar_panel()
        self.boton("Alumnos")
        self.assertEqual(len(self.tabla().get_children()), 7)

    def test_editar_desde_la_lista_conserva_los_datos(self):
        self.app.mostrar_gestion("student")
        self.tabla().selection_set("3644")
        self.boton("Editar")
        entradas = [w for w in widgets(self.app.nav.actual) if isinstance(w, tk.Entry)]
        self.assertEqual(entradas[0].get(), "Rushabh")
        entradas[0].delete(0, "end")
        entradas[0].insert(0, "Rushabh M.")
        with mock.patch("pantallas.messagebox.showinfo") as info:
            self.boton("Guardar")
        self.assertIn("Se actualizaron", info.call_args[0][1])
        self.assertEqual(self.g.obtener("student", 3644)["name"], "Rushabh M.")
        self.assertIsNotNone(self.g.obtener("student", 3644)["photo"])
        self.assertEqual(self.tabla().selection(), ("3644",))  # vuelve a la lista, en el mismo alumno

    def test_eliminar_pide_confirmacion(self):
        self.app.mostrar_gestion("student")
        self.tabla().selection_set("1100")
        with mock.patch("pantallas.messagebox.askyesno", return_value=False):
            self.boton("Eliminar")
        self.assertIsNotNone(self.g.obtener("student", 1100))
        with mock.patch("pantallas.messagebox.askyesno", return_value=True), \
                mock.patch("pantallas.messagebox.showinfo"):
            self.boton("Eliminar")
        self.assertIsNone(self.g.obtener("student", 1100))
        self.assertNotIn("1100", self.tabla().get_children())

    def test_sin_seleccion_avisa(self):
        self.app.mostrar_gestion("student")
        with mock.patch("pantallas.messagebox.showerror") as error:
            self.boton("Editar")
        self.assertIn("Selecciona", error.call_args[0][1])


if __name__ == "__main__":
    unittest.main()
