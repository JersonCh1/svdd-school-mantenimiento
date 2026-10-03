"""v5.0 R03: gestión de cursos."""
import os
import shutil
import tempfile
import tkinter as tk
import unittest
from tkinter import ttk
from unittest import mock

from db import BaseDatos, ErrorIntegridad
from gestion import Gestion
from migraciones import migrar, v5_tabla_cursos
from pantallas import Aplicacion
from validacion import ErrorValidacion

ORIGEN = os.path.join(os.path.dirname(__file__), "..", "testdata.db")


def widgets(w):
    yield w
    for c in w.winfo_children():
        yield from widgets(c)


class Base(unittest.TestCase):
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

    def nuevo(self, **extra):
        return self.g.registrar("curso", {"codigo": "mat-10", "nombre": "Matemática", "grado": "10th",
                                          "trno": "9999", **extra})


class CursosTest(Base):
    def test_ciclo_completo(self):
        curso = self.nuevo()
        self.assertEqual(curso["codigo"], "MAT-10")  # se guarda en mayúsculas
        fila = self.g.listar("curso")[0]
        self.assertEqual((fila["codigo"], fila["docente"]), ("MAT-10", "Darshi Kamani"))
        self.g.actualizar("curso", curso["id"], {"codigo": "MAT-10", "nombre": "Álgebra", "grado": "10th", "trno": ""})
        self.assertIsNone(self.g.obtener("curso", curso["id"])["trno"])
        self.assertEqual(self.g.eliminar("curso", curso["id"]), 1)

    def test_codigo_unico_y_obligatorios(self):
        self.nuevo()
        with self.assertRaises(ErrorValidacion) as e:
            self.nuevo(nombre="")
        self.assertEqual([c for c, _m in e.exception.errores], ["nombre"])
        with self.assertRaisesRegex(ErrorValidacion, "Ya existe un curso"):
            self.nuevo(codigo="MAT-10")
        with self.assertRaisesRegex(ErrorValidacion, "Código debe tener"):
            self.nuevo(codigo="mat 10!")

    def test_docente_inexistente(self):
        with self.assertRaisesRegex(ErrorValidacion, "no está registrado"):
            self.nuevo(trno="4242")

    def test_no_se_elimina_docente_con_cursos(self):
        self.nuevo()
        with self.assertRaisesRegex(ErrorValidacion, "1 curso"):
            self.g.eliminar("teacher", 9999)
        self.assertIsNotNone(self.g.obtener("teacher", 9999))

    def test_la_clave_foranea_es_la_segunda_barrera(self):
        self.nuevo()
        with self.assertRaisesRegex(ErrorIntegridad, "relacionado"):
            self.db.eliminar("TeacherData", {"trno": 9999})

    def test_el_curso_sigue_al_docente_si_cambia_su_registro(self):
        curso = self.nuevo()
        self.db.actualizar("TeacherData", "trno", 9998, {"trno": 9999})
        self.assertEqual(self.g.obtener("curso", curso["id"])["trno"], 9998)

    def test_migracion_idempotente(self):
        v5_tabla_cursos(self.db.con)
        self.assertEqual(self.g.listar("curso"), [])


class PantallaCursosTest(Base):
    def setUp(self):
        super().setUp()
        self.root = tk.Tk()
        self.app = Aplicacion(self.root, self.db)
        self.app.nav.sesion = (2, "Darshi999", "darshik@26")

    def tearDown(self):
        self.root.destroy()
        super().tearDown()

    def boton(self, texto):
        next(w for w in widgets(self.app.nav.actual) if isinstance(w, tk.Button) and w.cget("text") == texto).invoke()
        self.root.update()

    def test_alta_desde_la_pantalla(self):
        self.app.mostrar_panel()
        self.boton("Cursos")
        self.boton("Nuevo")
        codigo, nombre, grado = [w for w in widgets(self.app.nav.actual) if isinstance(w, tk.Entry)][:3]
        combo = next(w for w in widgets(self.app.nav.actual) if isinstance(w, ttk.Combobox))
        codigo.insert(0, "HIS-9")
        nombre.insert(0, "Historia")
        combo.current(2)
        with mock.patch("pantallas.messagebox.showinfo"):
            self.boton("Guardar")
        tabla = next(w for w in widgets(self.app.nav.actual) if isinstance(w, ttk.Treeview))
        self.assertEqual(len(tabla.get_children()), 1)
        self.assertEqual(tabla.item(tabla.selection()[0], "values")[0], "HIS-9")


if __name__ == "__main__":
    unittest.main()
