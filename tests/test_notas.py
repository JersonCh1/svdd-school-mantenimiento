"""v6.0 MR-106: nota de cada matrícula."""
import os
import shutil
import sqlite3
import tempfile
import tkinter as tk
import unittest
from tkinter import ttk
from unittest import mock

from db import BaseDatos
from gestion import ErrorValidacion, Gestion, estado_nota
from migraciones import (migrar, v2_columna_foto, v5_indices_unicos, v5_quitar_duplicados, v5_tabla_cursos,
                         v5_tabla_matriculas, v6_columna_nota)
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
        # Matemática la dicta Darshi999 (N.° 9999); Historia, RamSharma01 (N.° 1111).
        self.mat = self.g.registrar("curso", {"codigo": "MAT-10", "nombre": "Matemática", "trno": "9999"})["id"]
        self.his = self.g.registrar("curso", {"codigo": "HIS-10", "nombre": "Historia", "trno": "1111"})["id"]

    def tearDown(self):
        BaseDatos.cerrar()
        shutil.rmtree(self.dir, ignore_errors=True)

    def matricular(self, curso, gno="3644", periodo="2026-II"):
        self.g.registrar("matricula", {"gno": gno, "curso_id": str(curso), "periodo": periodo})
        return self.db.uno("SELECT MAX(id) FROM Matricula")[0]

    def nota(self, clave):
        return self.db.uno("SELECT nota FROM Matricula WHERE id = ?", (clave,))[0]


class MigracionNotaTest(unittest.TestCase):
    """La columna se agrega sin perder las matrículas que ya existían."""

    def test_conserva_matriculas_y_es_idempotente(self):
        carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, carpeta, ignore_errors=True)
        ruta = os.path.join(carpeta, "testdata.db")
        shutil.copy(ORIGEN, ruta)
        con = sqlite3.connect(ruta)
        # Base tal como quedó en la v5.0: Matricula todavía sin nota.
        for paso in (v2_columna_foto, v5_quitar_duplicados, v5_indices_unicos, v5_tabla_cursos, v5_tabla_matriculas):
            paso(con)
        con.execute("INSERT INTO Curso(codigo, nombre) VALUES ('MAT-10', 'Matemática')")
        con.execute("INSERT INTO Matricula(gno, curso_id, periodo, fecha) VALUES (3644, 1, '2026-I', '01/03/2026')")
        con.commit()
        self.assertTrue(v6_columna_nota(con))
        self.assertFalse(v6_columna_nota(con))
        self.assertEqual(con.execute("SELECT gno, periodo, nota FROM Matricula").fetchall(), [(3644, "2026-I", None)])
        con.close()

    def test_la_base_rechaza_nota_fuera_de_rango(self):
        carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, carpeta, ignore_errors=True)
        ruta = os.path.join(carpeta, "testdata.db")
        shutil.copy(ORIGEN, ruta)
        con = sqlite3.connect(ruta)
        migrar(con)
        con.execute("INSERT INTO Curso(codigo, nombre) VALUES ('MAT-10', 'Matemática')")
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute("INSERT INTO Matricula(gno, curso_id, periodo, fecha, nota) "
                        "VALUES (3644, 1, '2026-I', '01/03/2026', 21)")
        con.close()


class RegistrarNotaTest(Base):
    def test_director_registra_y_se_ve_en_el_listado(self):
        clave = self.matricular(self.mat)
        self.assertEqual(self.g.registrar_nota(clave, " 15 "), 15)
        fila = next(f for f in self.g.listar("matricula") if f["clave"] == clave)
        self.assertEqual(fila["nota"], 15)

    def test_vacia_quita_la_nota(self):
        clave = self.matricular(self.mat)
        self.g.registrar_nota(clave, "8")
        self.assertIsNone(self.g.registrar_nota(clave, ""))
        self.assertIsNone(self.nota(clave))

    def test_limites(self):
        clave = self.matricular(self.mat)
        self.assertEqual(self.g.registrar_nota(clave, "0"), 0)
        self.assertEqual(self.g.registrar_nota(clave, "20"), 20)

    def test_valores_invalidos_no_cambian_nada(self):
        clave = self.matricular(self.mat)
        self.g.registrar_nota(clave, "12")
        for malo in ("21", "-1", "abc", "15.5", "1 5"):
            with self.subTest(malo=malo), self.assertRaises(ErrorValidacion):
                self.g.registrar_nota(clave, malo)
        self.assertEqual(self.nota(clave), 12)

    def test_solo_el_docente_a_cargo(self):
        clave = self.matricular(self.mat)
        self.assertEqual(self.g.registrar_nota(clave, "17", trno=9999), 17)
        with self.assertRaises(ErrorValidacion) as e:
            self.g.registrar_nota(clave, "05", trno=1111)
        self.assertIn("docente a cargo", str(e.exception))
        self.assertEqual(self.nota(clave), 17)

    def test_matricula_anulada(self):
        clave = self.matricular(self.mat)
        self.g.eliminar("matricula", clave)
        with self.assertRaises(ErrorValidacion):
            self.g.registrar_nota(clave, "14")

    def test_notas_del_alumno(self):
        a = self.matricular(self.mat, periodo="2026-I")
        b = self.matricular(self.his, periodo="2026-II")
        c = self.matricular(self.mat, periodo="2026-II")
        self.g.registrar_nota(a, "10")
        self.g.registrar_nota(b, "11")
        notas = self.g.notas_de(3644)
        self.assertEqual([(f["clave"], f["estado"]) for f in notas],
                         [(b, "Aprobado"), (c, "Sin nota"), (a, "Desaprobado")])
        self.assertEqual(self.g.notas_de(9999), [])
        self.assertEqual(estado_nota(None), "Sin nota")


class PantallasNotaTest(Base):
    def setUp(self):
        super().setUp()
        self.clave = self.matricular(self.mat)
        self.root = tk.Tk()
        self.app = Aplicacion(self.root, self.db)

    def tearDown(self):
        self.root.destroy()
        super().tearDown()

    def entrar(self, rol, usuario, clave):
        self.app.nav.sesion = (rol, usuario, clave)
        self.app.mostrar_panel()
        self.root.update()

    def boton(self, texto):
        return next(w for w in widgets(self.root) if isinstance(w, tk.Button) and w.cget("text") == texto)

    def poner_nota(self, valor):
        self.app.mostrar_formulario_nota(self.clave)
        self.root.update()
        entrada = [w for w in widgets(self.root) if isinstance(w, tk.Entry)][0]
        entrada.delete(0, "end")
        entrada.insert(0, valor)
        with mock.patch("pantallas.messagebox.showinfo") as info, \
                mock.patch("pantallas.messagebox.showerror") as error:
            self.boton("Guardar").invoke()
        self.root.update()
        return info, error

    def test_docente_a_cargo_registra(self):
        self.entrar(2, "Darshi999", "darshik@26")
        info, error = self.poner_nota("16")
        info.assert_called_once()
        error.assert_not_called()
        self.assertEqual(self.nota(self.clave), 16)
        # Vuelve a Matrículas con la columna Nota llena.
        tabla = next(w for w in widgets(self.root) if isinstance(w, ttk.Treeview))
        self.assertEqual(str(tabla.set(str(self.clave), "nota")), "16")

    def test_otro_docente_no_puede(self):
        self.db.escribir("UPDATE Curso SET trno = 1111 WHERE id = ?", (self.mat,))
        self.entrar(2, "Darshi999", "darshik@26")
        info, error = self.poner_nota("16")
        info.assert_not_called()
        error.assert_called_once()
        self.assertIsNone(self.nota(self.clave))

    def test_la_entrada_solo_acepta_dos_digitos(self):
        self.entrar(1, "RajanUp12", "RUpadhyay123")
        self.app.mostrar_formulario_nota(self.clave)
        self.root.update()
        entrada = [w for w in widgets(self.root) if isinstance(w, tk.Entry)][0]
        for tecla in "1a5-9":  # letras, signos y un tercer dígito se rechazan
            entrada.insert("end", tecla)
        self.assertEqual(entrada.get(), "15")

    def test_alumno_ve_sus_notas(self):
        self.g.registrar_nota(self.clave, "13")
        self.entrar(3, "Rushabh123", "12345678")
        self.boton("Mis notas").invoke()
        self.root.update()
        tabla = next(w for w in widgets(self.root) if isinstance(w, ttk.Treeview))
        filas = [tabla.item(i, "values") for i in tabla.get_children()]
        self.assertEqual(len(filas), 1)
        self.assertEqual(list(filas[0][-2:]), ["13", "Aprobado"])
        # El alumno no tiene botones para cambiar notas.
        textos = {w.cget("text") for w in widgets(self.root) if isinstance(w, tk.Button)}
        self.assertEqual(textos, {"Volver"})


if __name__ == "__main__":
    unittest.main()
