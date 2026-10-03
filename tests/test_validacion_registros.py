"""v5.0 R06: validación de los registros antes de guardarlos."""
import os
import shutil
import tempfile
import tkinter as tk
import unittest
from unittest import mock

from db import BaseDatos
from gestion import Gestion
from migraciones import migrar
from pantallas import ERROR, VALOR, Aplicacion
from validacion import ErrorValidacion, errores_registro, normalizar

ORIGEN = os.path.join(os.path.dirname(__file__), "..", "testdata.db")
ALUMNO = {"name": "Lucía", "lname": "Mamani", "gno": "5001", "username": "lucia", "password": "x1",
          "dob": "12/03/2012", "hei": "150,5", "mno": "", "adno": ""}


def widgets(w):
    yield w
    for c in w.winfo_children():
        yield from widgets(c)


def columnas(errores):
    return [c for c, _m in errores]


class ReglasTest(unittest.TestCase):
    def test_registro_valido(self):
        self.assertEqual(errores_registro("student", ALUMNO), [])

    def test_obligatorios_vacios(self):
        errores = errores_registro("student", {**ALUMNO, "name": "  ", "password": ""})
        self.assertEqual(columnas(errores), ["name", "password"])
        self.assertIn("Nombre es obligatorio", errores[0][1])

    def test_formatos_incorrectos(self):
        malos = {**ALUMNO, "gno": "12a", "hei": "alto", "dob": "31/02/2012", "mno": "98765"}
        self.assertEqual(sorted(columnas(errores_registro("student", malos))), ["dob", "gno", "hei", "mno"])

    def test_fecha_con_otro_formato(self):
        self.assertEqual(columnas(errores_registro("teacher", {"dob": "1968-07-24"}, parcial=True)), ["dob"])

    def test_edicion_parcial_solo_revisa_lo_presente(self):
        self.assertEqual(errores_registro("teacher", {"ctfc": "9th A"}, parcial=True), [])
        self.assertEqual(columnas(errores_registro("teacher", {"name": ""}, parcial=True)), ["name"])

    def test_normalizar(self):
        datos = normalizar("student", ALUMNO)
        self.assertEqual((datos["gno"], datos["hei"], datos["mno"]), (5001, 150.5, None))


class DuplicadosTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        ruta = os.path.join(self.dir, "testdata.db")
        shutil.copy(ORIGEN, ruta)
        self.db = BaseDatos(ruta)
        migrar(self.db.con)
        self.g = Gestion(self.db)

    def tearDown(self):
        BaseDatos.cerrar()
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_usuario_y_registro_repetidos(self):
        with self.assertRaises(ErrorValidacion) as e:
            self.g.registrar_persona("student", {**ALUMNO, "gno": "3644", "username": "Rushabh123"})
        self.assertEqual(columnas(e.exception.errores), ["gno", "username"])

    def test_al_editar_no_es_duplicado_de_si_mismo(self):
        datos = {**ALUMNO, "gno": "3644", "username": "Rushabh123"}
        self.assertEqual(self.g.validar_persona("student", datos, original=3644)["gno"], 3644)

    def test_alta_valida_se_guarda(self):
        self.g.registrar_persona("student", ALUMNO)
        self.assertEqual(self.db.uno("SELECT name FROM StudentData WHERE gno = 5001")[0], "Lucía")


class FormularioTest(unittest.TestCase):
    """El error se muestra sin perder lo que el usuario ya escribió."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        ruta = os.path.join(self.dir, "testdata.db")
        shutil.copy(ORIGEN, ruta)
        self.db = BaseDatos(ruta)
        migrar(self.db.con)
        self.root = tk.Tk()
        self.app = Aplicacion(self.root, self.db)
        self.app.nav.sesion = (2, "Darshi999", "darshik@26")

    def tearDown(self):
        self.root.destroy()
        BaseDatos.cerrar()
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_campos_marcados_y_datos_conservados(self):
        self.app.mostrar_formulario("student")
        self.root.update()
        entradas = [w for w in widgets(self.app.nav.actual) if isinstance(w, tk.Entry)]
        nombre, apellido = entradas[0], entradas[1]
        nombre.insert(0, "Lucía")
        guardar = next(w for w in widgets(self.app.nav.actual)
                       if isinstance(w, tk.Button) and w.cget("text") == "Guardar")
        with mock.patch("pantallas.messagebox.showerror") as error:
            guardar.invoke()
        self.assertIn("Apellido es obligatorio", error.call_args[0][1])
        self.assertEqual(nombre.get(), "Lucía")
        self.assertEqual(nombre.cget("bg"), VALOR)
        self.assertEqual(apellido.cget("bg"), ERROR)

if __name__ == "__main__":
    unittest.main()
