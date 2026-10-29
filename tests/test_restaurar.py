"""v6.0 MR-107: restaurar un respaldo desde la aplicación."""
import os
import shutil
import sqlite3
import tempfile
import tkinter as tk
import unittest
from unittest import mock

import seguridad
from db import BaseDatos, BaseDeDatosOcupada, RespaldoInvalido
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
        self.ruta = os.path.join(self.dir, "testdata.db")
        shutil.copy(ORIGEN, self.ruta)
        self.db = BaseDatos(self.ruta)
        migrar(self.db.con)
        self.g = Gestion(self.db)

    def tearDown(self):
        BaseDatos.cerrar()
        shutil.rmtree(self.dir, ignore_errors=True)

    def alta(self, gno):
        self.g.registrar("student", {"name": "Ana", "lname": "Rojas", "gno": str(gno),
                                     "username": f"alu{gno}", "password": "clave1"})

    def existe(self, gno):
        return self.db.uno("SELECT 1 FROM StudentData WHERE gno = ?", (gno,)) is not None


class RestaurarTest(Base):
    def test_vuelve_al_estado_del_respaldo_y_guarda_el_actual(self):
        respaldo = self.db.respaldar()
        self.alta(7001)
        previo = self.db.restaurar(respaldo)
        self.assertFalse(self.existe(7001))
        # La base que se reemplazó quedó respaldada con el alta incluida.
        con = sqlite3.connect(previo)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM StudentData WHERE gno = 7001").fetchone()[0], 1)
        con.close()
        # La conexión sigue funcionando para escribir.
        self.alta(7002)
        self.assertTrue(self.existe(7002))
        self.assertEqual(self.db.uno("PRAGMA integrity_check")[0], "ok")

    def test_respaldo_de_version_anterior_se_migra(self):
        # La base original del proyecto: sin Curso, sin Matricula y con contraseñas planas.
        viejo = os.path.join(self.dir, "respaldo-v1.db")
        shutil.copy(ORIGEN, viejo)
        self.db.restaurar(viejo)
        tablas = {f[0] for f in self.db.consultar("SELECT name FROM sqlite_master WHERE type = 'table'")}
        self.assertTrue({"Curso", "Matricula"} <= tablas)
        self.assertIn("nota", self.db.columnas("Matricula"))
        clave = self.db.uno("SELECT password FROM PrincipalData")[0]
        self.assertTrue(seguridad.es_hash(clave))
        self.assertIsNotNone(self.db.autenticar("PrincipalData", "RajanUp12", "RUpadhyay123"))
        # El archivo elegido no se modifica: se abrió en solo lectura.
        con = sqlite3.connect(viejo)
        self.assertFalse(seguridad.es_hash(con.execute("SELECT password FROM PrincipalData").fetchone()[0]))
        con.close()

    def test_el_respaldo_mas_antiguo_no_se_pierde(self):
        carpeta = os.path.join(self.dir, "respaldos")
        respaldos = []
        for gno in range(7101, 7111):  # 10 respaldos: el límite que se conserva
            self.alta(gno)
            with mock.patch("db.datetime") as reloj:
                reloj.now.return_value.__format__ = lambda _s, _f, g=gno: f"20260101-0{g}"
                respaldos.append(self.db.respaldar(carpeta))
        mas_antiguo = sorted(os.listdir(carpeta))[0]
        self.assertEqual(os.path.basename(respaldos[0]), mas_antiguo)
        # El respaldo de seguridad borra el más antiguo... que es justo el elegido.
        self.db.restaurar(respaldos[0])
        self.assertFalse(os.path.exists(respaldos[0]))
        self.assertTrue(self.existe(7101))
        self.assertFalse(self.existe(7102))

    def test_ruta_con_espacios_y_tildes(self):
        carpeta = os.path.join(self.dir, "Mis respaldos ñandú")
        respaldo = self.db.respaldar(carpeta)
        self.alta(7201)
        self.db.restaurar(respaldo)
        self.assertFalse(self.existe(7201))


class RespaldoInvalidoTest(Base):
    def setUp(self):
        super().setUp()
        self.alta(7301)

    def assertSinCambios(self):
        self.assertTrue(self.existe(7301))
        self.assertEqual(self.db.uno("PRAGMA integrity_check")[0], "ok")

    def rechaza(self, ruta, texto):
        with self.assertRaises(RespaldoInvalido) as e:
            self.db.restaurar(ruta)
        self.assertIn(texto, str(e.exception))
        self.assertSinCambios()
        self.assertFalse(os.path.isdir(os.path.join(self.dir, "respaldos")))  # ni respaldo de seguridad

    def test_archivo_que_no_es_base(self):
        ruta = os.path.join(self.dir, "notas.db")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("esto no es una base de datos " * 50)
        self.rechaza(ruta, "no es una base de datos")

    def test_base_de_otro_programa(self):
        ruta = os.path.join(self.dir, "otra.db")
        con = sqlite3.connect(ruta)
        con.execute("CREATE TABLE Producto(id INTEGER)")
        con.close()
        self.rechaza(ruta, "le faltan las tablas")

    def test_respaldo_sin_director(self):
        ruta = os.path.join(self.dir, "sin-director.db")
        shutil.copy(ORIGEN, ruta)
        con = sqlite3.connect(ruta)
        con.execute("DELETE FROM PrincipalData")
        con.commit()
        con.close()
        self.rechaza(ruta, "ningún director")

    def test_la_base_en_uso(self):
        self.rechaza(self.ruta, "está en uso")

    def test_archivo_inexistente(self):
        self.rechaza(os.path.join(self.dir, "no-existe.db"), "No se encontró")

    def test_otro_programa_con_la_base_abierta(self):
        respaldo = os.path.join(self.dir, "copia.db")
        shutil.copy(ORIGEN, respaldo)
        with mock.patch("db.os.replace", side_effect=PermissionError("en uso")):
            with self.assertRaises(BaseDeDatosOcupada):
                self.db.restaurar(respaldo)
        self.assertSinCambios()
        self.assertFalse(os.path.exists(self.ruta + ".restaurando"))


class PantallaRestaurarTest(Base):
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

    def textos(self):
        return {w.cget("text") for w in widgets(self.root) if isinstance(w, tk.Button)}

    def test_restaura_y_pide_iniciar_sesion(self):
        respaldo = self.db.respaldar()
        self.alta(7401)
        self.assertIn("Restaurar", self.textos())
        with mock.patch("pantallas.filedialog.askopenfilename", return_value=respaldo), \
                mock.patch("pantallas.messagebox.askyesno", return_value=True), \
                mock.patch("pantallas.messagebox.showinfo") as info:
            self.app.restaurar()
        self.root.update()
        info.assert_called_once()
        self.assertFalse(self.existe(7401))
        self.assertIn("INGRESAR", self.textos())
        self.assertIsNone(self.app.nav.sesion)

    def test_cancelar_no_cambia_nada(self):
        respaldo = self.db.respaldar()
        self.alta(7402)
        with mock.patch("pantallas.filedialog.askopenfilename", return_value=respaldo), \
                mock.patch("pantallas.messagebox.askyesno", return_value=False):
            self.assertIsNone(self.app.restaurar())
        self.assertTrue(self.existe(7402))
        self.assertIn("Restaurar", self.textos())

    def test_respaldo_invalido_muestra_el_motivo(self):
        ruta = os.path.join(self.dir, "otra.db")
        sqlite3.connect(ruta).close()
        with mock.patch("pantallas.filedialog.askopenfilename", return_value=ruta), \
                mock.patch("pantallas.messagebox.askyesno", return_value=True), \
                mock.patch("pantallas.messagebox.showerror") as error:
            self.app.restaurar()
        self.assertIn("no se modificaron", error.call_args[0][1])
        self.assertIn("Restaurar", self.textos())


if __name__ == "__main__":
    unittest.main()
