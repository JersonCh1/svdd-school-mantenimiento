"""v5.0 R05: búsqueda y consulta por identificador o nombre."""
import os
import shutil
import tempfile
import tkinter as tk
import unittest
from tkinter import ttk

from db import BaseDatos
from gestion import Gestion
from migraciones import migrar
from pantallas import Aplicacion

ORIGEN = os.path.join(os.path.dirname(__file__), "..", "testdata.db")


def widgets(w):
    yield w
    for c in w.winfo_children():
        yield from widgets(c)


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        shutil.copy(ORIGEN, os.path.join(self.dir, "testdata.db"))
        self.db = BaseDatos(os.path.join(self.dir, "testdata.db"))
        migrar(self.db.con)
        self.g = Gestion(self.db)

    def tearDown(self):
        BaseDatos.cerrar()
        shutil.rmtree(self.dir, ignore_errors=True)

    def claves(self, tipo, filtro):
        return [f["clave"] for f in self.g.listar(tipo, filtro)]


class BusquedaTest(Base):
    def test_por_identificador_exacto(self):
        self.assertEqual(self.claves("student", "3644"), [3644])
        self.assertEqual(self.claves("student", "364"), [])  # el N.° debe ser completo

    def test_por_nombre_o_apellido_parcial_sin_mayusculas(self):
        self.assertEqual(self.claves("student", "gala"), [3644])
        self.assertEqual(self.claves("student", "rushabh g"), [3644])
        self.assertEqual(sorted(self.claves("teacher", "sha")), [1111, 2222])  # Sharma y Shah

    def test_sin_coincidencias(self):
        self.assertEqual(self.claves("teacher", "Zzz"), [])

    def test_comodines_se_buscan_literalmente(self):
        self.assertEqual(self.claves("student", "%"), [])
        self.assertEqual(self.claves("student", "_"), [])

    def test_inyeccion_sql_no_entra(self):
        self.assertEqual(self.claves("student", "' OR '1'='1"), [])

    def test_cursos_y_matriculas(self):
        curso = self.g.registrar("curso", {"codigo": "MAT-10", "nombre": "Matemática", "trno": "9999"})["id"]
        self.g.registrar("matricula", {"gno": "3644", "curso_id": str(curso), "periodo": "2026-II"})
        self.assertEqual(self.claves("curso", "mat-10"), [curso])
        self.assertEqual(self.claves("curso", "kamani"), [curso])  # por docente
        self.assertEqual(len(self.claves("matricula", "2026-II")), 1)
        self.assertEqual(len(self.claves("matricula", "Rushabh")), 1)
        self.assertEqual(self.claves("matricula", "2025-I"), [])


class PantallaBusquedaTest(Base):
    def setUp(self):
        super().setUp()
        self.root = tk.Tk()
        self.app = Aplicacion(self.root, self.db)
        self.app.nav.sesion = (2, "Darshi999", "darshik@26")
        self.app.mostrar_gestion("student")
        self.root.update()
        self.filtro = next(w for w in widgets(self.app.nav.actual) if isinstance(w, tk.Entry))
        self.tabla = next(w for w in widgets(self.app.nav.actual) if isinstance(w, ttk.Treeview))

    def tearDown(self):
        self.root.destroy()
        super().tearDown()

    def boton(self, texto):
        next(w for w in widgets(self.app.nav.actual) if isinstance(w, tk.Button) and w.cget("text") == texto).invoke()

    def aviso(self):
        return [w.cget("text") for w in widgets(self.app.nav.actual)
                if isinstance(w, tk.Label) and "coincidencia" in str(w.cget("text"))]

    def test_buscar_y_mostrar_todos(self):
        self.filtro.insert(0, "Darshi")
        self.boton("Buscar")
        self.assertEqual(self.tabla.get_children(), ("9999",))
        self.assertEqual(self.aviso(), ["1 coincidencia(s) para «Darshi»."])
        self.boton("Mostrar todos")
        self.assertEqual(len(self.tabla.get_children()), 7)
        self.assertEqual(self.filtro.get(), "")

    def test_informa_cuando_no_hay_coincidencias(self):
        self.filtro.insert(0, "Nadie")
        self.filtro.focus_force()
        self.root.update()
        self.filtro.event_generate("<Return>")
        self.root.update()
        self.assertEqual(self.tabla.get_children(), ())
        self.assertEqual(self.aviso(), ["No se encontraron coincidencias para «Nadie»."])


if __name__ == "__main__":
    unittest.main()
