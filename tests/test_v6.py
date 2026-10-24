"""v6.0: MR-101 a MR-105."""
import os
import shutil
import sqlite3
import tempfile
import tkinter as tk
import unittest
from unittest import mock

import db
import seguridad
from db import BaseDatos, ubicar_base
from gestion import ErrorValidacion, Gestion
from migraciones import migrar, v6_hashear_contrasenas
from pantallas import Aplicacion
from texto import plano

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

    def claves(self, tipo, filtro):
        return [f["clave"] for f in self.g.listar(tipo, filtro)]


class BusquedaSinTildesTest(Base):
    """MR-101 (correctivo): LIKE solo ignoraba mayúsculas en ASCII."""

    def setUp(self):
        super().setUp()
        self.g.registrar("student", {"name": "Lucía", "lname": "Ñahui", "gno": "5001", "username": "lucia", "password": "x1"})
        self.g.registrar("student", {"name": "José", "lname": "Quispe", "gno": "5002", "username": "jose", "password": "x2"})

    def test_plano(self):
        self.assertEqual(plano("Lucía ÑAHUI"), "lucia nahui")
        self.assertIsNone(plano(None))

    def test_sin_tilde_encuentra_con_tilde(self):
        self.assertEqual(self.claves("student", "lucia"), [5001])
        self.assertEqual(self.claves("student", "nahui"), [5001])

    def test_mayusculas_con_tilde(self):
        self.assertEqual(self.claves("student", "JOSÉ"), [5002])
        self.assertEqual(self.claves("student", "jose quispe"), [5002])

    def test_comodines_siguen_siendo_literales(self):
        self.assertEqual(self.claves("student", "%"), [])


class ContrasenasTest(Base):
    """MR-105 (preventivo): ninguna contraseña queda en texto plano."""

    def test_migracion_hashea_todas(self):
        for tabla in ("StudentData", "TeacherData", "PrincipalData"):
            for (clave,) in self.db.consultar(f"SELECT password FROM {tabla} WHERE password IS NOT NULL"):
                self.assertTrue(seguridad.es_hash(clave), (tabla, clave))

    def test_migracion_idempotente(self):
        self.assertEqual(v6_hashear_contrasenas(self.db.con), [])

    def test_mismos_usuarios_siguen_entrando(self):
        self.assertIsNotNone(self.db.autenticar("PrincipalData", "RajanUp12", "RUpadhyay123"))
        self.assertIsNotNone(self.db.autenticar("TeacherData", "Darshi999", "darshik@26"))
        self.assertIsNone(self.db.autenticar("PrincipalData", "RajanUp12", "mala"))

    def test_el_hash_guardado_no_sirve_como_contrasena(self):
        guardada = self.db.uno("SELECT password FROM PrincipalData")[0]
        self.assertIsNone(self.db.autenticar("PrincipalData", "RajanUp12", guardada))

    def test_misma_clave_hash_distinto(self):
        self.assertNotEqual(seguridad.hashear("abc"), seguridad.hashear("abc"))

    def test_texto_plano_no_se_acepta(self):
        self.assertFalse(seguridad.verificar("abc", "abc"))

    def test_alta_y_edicion(self):
        self.g.registrar("student", {"name": "Ana", "lname": "Ruiz", "gno": "6001", "username": "ana", "password": "s3creta"})
        self.assertNotEqual(self.g.obtener("student", 6001)["password"], "s3creta")
        self.assertIsNotNone(self.db.autenticar("StudentData", "ana", "s3creta"))
        # Contraseña vacía al editar = se conserva la anterior.
        self.g.actualizar("student", 6001, {"name": "Ana", "lname": "Ruiz", "gno": "6001", "username": "ana", "password": ""})
        self.assertIsNotNone(self.db.autenticar("StudentData", "ana", "s3creta"))
        self.g.actualizar("student", 6001, {"name": "Ana", "lname": "Ruiz", "gno": "6001", "username": "ana", "password": "nueva"})
        self.assertIsNone(self.db.autenticar("StudentData", "ana", "s3creta"))
        self.assertIsNotNone(self.db.autenticar("StudentData", "ana", "nueva"))

    def test_alta_sin_contrasena_sigue_rechazada(self):
        with self.assertRaises(ErrorValidacion):
            self.g.registrar("student", {"name": "Ana", "lname": "Ruiz", "gno": "6001", "username": "ana", "password": ""})


class EdicionDirectorTest(Base):
    """MR-102 (correctivo): el director edita sus datos con el formulario completo."""

    def setUp(self):
        super().setUp()
        self.root = tk.Tk()
        self.app = Aplicacion(self.root, self.db)
        self.app.nav.sesion = (1, "RajanUp12", "RUpadhyay123")
        self.app.mostrar_panel()
        self.root.update()

    def tearDown(self):
        self.root.destroy()
        super().tearDown()

    def entradas(self):
        return [w for w in widgets(self.root) if isinstance(w, (tk.Entry, tk.Text))]

    def boton(self, texto):
        return next(w for w in widgets(self.root) if isinstance(w, tk.Button) and w.cget("text") == texto)

    def test_formulario_precargado_y_guardado_limpio(self):
        self.boton("Editar mis datos").invoke()
        self.root.update()
        textos = [w.get() for w in self.entradas() if isinstance(w, tk.Entry)]
        self.assertIn("Rajan", textos)          # datos cargados, sin escribir nombre ni N.° a mano
        self.assertNotIn("RUpadhyay123", textos)  # la contraseña no se muestra
        lugar = next(w for w in self.entradas() if isinstance(w, tk.Entry) and w.get() == "Rajan")
        lugar.delete(0, "end")
        lugar.insert(0, "  Rajan  ")
        with mock.patch("pantallas.messagebox.showinfo"):
            self.boton("Guardar").invoke()
        self.root.update()
        fila = self.db.uno("SELECT name, password FROM PrincipalData")
        self.assertEqual(fila["name"], "Rajan")  # sin espacios ni saltos de línea sobrantes
        self.assertTrue(seguridad.es_hash(fila["password"]))
        # Volvió al panel con la sesión intacta.
        self.assertTrue(any(isinstance(w, tk.Button) and w.cget("text") == "Respaldo" for w in widgets(self.root)))

    def test_fecha_invalida_no_se_guarda(self):
        self.boton("Editar mis datos").invoke()
        self.root.update()
        antes = self.db.uno("SELECT dob FROM PrincipalData")[0]
        dob = next(w for w in self.entradas() if isinstance(w, tk.Entry) and w.get() == (antes or ""))
        dob.delete(0, "end")
        dob.insert(0, "31/02/2012")
        with mock.patch("pantallas.messagebox.showerror"):
            self.boton("Guardar").invoke()
        self.assertEqual(self.db.uno("SELECT dob FROM PrincipalData")[0], antes)

    def test_respaldo_desde_el_panel(self):
        with mock.patch("pantallas.messagebox.showinfo") as info:
            destino = self.app.respaldar()
        self.assertTrue(os.path.exists(destino))
        info.assert_called_once()


class UbicacionBaseTest(unittest.TestCase):
    """MR-103 (adaptativo): .exe instalado en una carpeta de solo lectura."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.programa = os.path.join(self.dir, "Program Files", "SVDD-School")
        self.datos = os.path.join(self.dir, "AppData", "Local")
        os.makedirs(self.programa)
        self.incluida = os.path.join(self.dir, "_MEI", "testdata.db")
        os.makedirs(os.path.dirname(self.incluida))
        shutil.copy(ORIGEN, self.incluida)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_carpeta_escribible_usa_la_del_programa(self):
        ruta = ubicar_base(self.programa, self.incluida)
        self.assertEqual(ruta, os.path.join(self.programa, "testdata.db"))
        self.assertTrue(os.path.exists(ruta))

    def test_solo_lectura_usa_carpeta_de_datos(self):
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": self.datos}), \
                mock.patch("db.se_puede_escribir", return_value=False):
            ruta = ubicar_base(self.programa, self.incluida)
        self.assertEqual(ruta, os.path.join(self.datos, "SVDD-School", "testdata.db"))
        self.assertTrue(os.path.exists(ruta))
        self.assertFalse(os.path.exists(os.path.join(self.programa, "testdata.db")))

    def test_conserva_la_base_que_ya_estaba_junto_al_programa(self):
        anterior = os.path.join(self.programa, "testdata.db")
        shutil.copy(ORIGEN, anterior)
        con = sqlite3.connect(anterior)
        con.execute("UPDATE PrincipalData SET name = 'Copiado'")
        con.commit()
        con.close()
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": self.datos}), \
                mock.patch("db.se_puede_escribir", return_value=False):
            ruta = ubicar_base(self.programa, self.incluida)
        con = sqlite3.connect(ruta)
        self.assertEqual(con.execute("SELECT name FROM PrincipalData").fetchone()[0], "Copiado")
        con.close()

    def test_se_puede_escribir_real(self):
        self.assertTrue(db.se_puede_escribir(self.programa))
        self.assertFalse(db.se_puede_escribir(os.path.join(self.dir, "no_existe")))


class RespaldoTest(Base):
    """MR-104 (perfectivo): respaldo consistente aun con cambios en el WAL."""

    def test_respaldo_incluye_cambios_sin_volcar(self):
        self.g.registrar("student", {"name": "Lucía", "lname": "Mamani", "gno": "5001", "username": "lucia", "password": "x"})
        self.assertTrue(os.path.getsize(self.ruta + "-wal") > 0)  # el cambio aún está en el WAL
        destino = self.db.respaldar()
        copia = sqlite3.connect(destino)
        self.assertEqual(copia.execute("SELECT name FROM StudentData WHERE gno = 5001").fetchone()[0], "Lucía")
        self.assertEqual(copia.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        copia.close()

    def test_conserva_solo_los_mas_recientes(self):
        carpeta = os.path.join(self.dir, "respaldos")
        rutas = [self.db.respaldar(carpeta, conservar=3) for _ in range(5)]
        self.assertEqual(len(os.listdir(carpeta)), 3)
        self.assertTrue(os.path.exists(rutas[-1]))


if __name__ == "__main__":
    unittest.main()
