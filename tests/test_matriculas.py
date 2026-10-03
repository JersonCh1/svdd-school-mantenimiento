"""v5.0 R04: registro y consulta de matrículas."""
import os
import shutil
import tempfile
import tkinter as tk
import unittest
from datetime import datetime
from tkinter import ttk
from unittest import mock

from db import BaseDatos, ErrorIntegridad
from gestion import Gestion
from migraciones import migrar
from pantallas import Aplicacion
from validacion import ErrorValidacion, periodo_actual

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
        self.curso = self.g.registrar("curso", {"codigo": "MAT-10", "nombre": "Matemática", "grado": "10th"})["id"]

    def tearDown(self):
        BaseDatos.cerrar()
        shutil.rmtree(self.dir, ignore_errors=True)

    def matricular(self, gno="3644", periodo="2026-II", curso=None):
        return self.g.registrar("matricula", {"gno": gno, "curso_id": str(curso or self.curso), "periodo": periodo})


class MatriculasTest(Base):
    def test_registrar_y_consultar(self):
        self.matricular()
        fila = self.g.listar("matricula")[0]
        self.assertEqual((fila["periodo"], fila["alumno"], fila["codigo"]), ("2026-II", "Rushabh Gala", "MAT-10"))
        self.assertEqual(fila["fecha"], datetime.now().strftime("%d/%m/%Y"))

    def test_no_se_duplica_en_el_mismo_periodo(self):
        self.matricular()
        with self.assertRaisesRegex(ErrorValidacion, "ya está matriculado"):
            self.matricular()
        self.matricular(periodo="2027-I")  # otro periodo sí
        self.assertEqual(len(self.g.listar("matricula")), 2)

    def test_el_indice_unico_respalda_la_regla(self):
        self.matricular()
        with self.assertRaisesRegex(ErrorIntegridad, "ya está matriculado"):
            self.db.insertar("Matricula", {"gno": 3644, "curso_id": self.curso, "periodo": "2026-II", "fecha": "x"})

    def test_alumno_y_curso_deben_existir(self):
        with self.assertRaisesRegex(ErrorValidacion, "alumno no está registrado"):
            self.matricular(gno="4242")
        with self.assertRaisesRegex(ErrorValidacion, "curso no está registrado"):
            self.matricular(curso=999)

    def test_obligatorios_y_formato_del_periodo(self):
        with self.assertRaises(ErrorValidacion) as e:
            self.g.registrar("matricula", {"gno": "", "curso_id": "", "periodo": "2026"})
        self.assertEqual([c for c, _m in e.exception.errores], ["gno", "curso_id", "periodo"])
        self.assertIn("Alumno es obligatorio", str(e.exception))
        self.assertEqual(self.matricular(periodo=" 2026-ii ")["periodo"], "2026-II")

    def test_relaciones_bloquean_la_eliminacion(self):
        m = self.matricular()
        with self.assertRaisesRegex(ErrorValidacion, "matrícula"):
            self.g.eliminar("student", 3644)
        with self.assertRaisesRegex(ErrorValidacion, "matriculado"):
            self.g.eliminar("curso", self.curso)
        self.g.eliminar("matricula", m["id"])
        self.assertEqual(self.g.eliminar("curso", self.curso), 1)

    def test_la_matricula_sigue_al_alumno_si_cambia_su_registro(self):
        self.matricular()
        self.g.actualizar("student", 3644, {**dict(self.g.obtener("student", 3644)), "gno": "3645",
                                            "photo_blob": None})
        self.assertEqual(self.g.listar("matricula")[0]["gno"], 3645)

    def test_periodo_actual(self):
        self.assertEqual(periodo_actual(datetime(2026, 3, 1)), "2026-I")
        self.assertEqual(periodo_actual(datetime(2026, 10, 3)), "2026-II")


class PantallaMatriculasTest(Base):
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

    def test_matricular_desde_la_pantalla(self):
        self.app.mostrar_panel()
        self.boton("Matrículas")
        self.boton("Nuevo")
        alumno, curso = [w for w in widgets(self.app.nav.actual) if isinstance(w, ttk.Combobox)]
        alumno.current(0)
        with mock.patch("pantallas.messagebox.showerror") as error:
            self.boton("Registrar")
        self.assertIn("Curso es obligatorio", error.call_args[0][1])
        curso.current(0)
        with mock.patch("pantallas.messagebox.showinfo"):
            self.boton("Registrar")
        with mock.patch("pantallas.messagebox.showerror") as error:
            curso.current(0)
            self.boton("Registrar")
        self.assertIn("ya está matriculado", error.call_args[0][1])
        self.boton("Volver")
        tabla = next(w for w in widgets(self.app.nav.actual) if isinstance(w, ttk.Treeview))
        self.assertEqual(len(tabla.get_children()), 1)
        textos = [w.cget("text") for w in widgets(self.app.nav.actual) if isinstance(w, tk.Button)]
        self.assertIn("Anular", textos)
        self.assertNotIn("Editar", textos)


if __name__ == "__main__":
    unittest.main()
