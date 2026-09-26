"""Recorrido completo de la app real, con los tres roles.

Uso (desde la raíz del repositorio):  python herramientas/verificar_app.py

- Trabaja sobre una COPIA temporal del programa y de testdata.db: la base del
  repositorio no se modifica.
- Revisa en cada pantalla que no haya ventanas extra, ni etiquetas cortadas
  o solapadas, ni excepciones.
- Deja las capturas en herramientas/capturas/ (carpeta ignorada por Git).
- Termina con código 1 si encontró algún problema.
"""
import glob
import os
import shutil
import sqlite3
import sys
import tempfile
import tkinter as tk

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
from conductor_gui import find, log, pick_file, pump, run, shot, walk, with_dialogs  # noqa: E402

OUT = os.path.join(AQUI, "capturas")
DEMO = os.path.join(RAIZ, "docs", "fotos-demo")
PROBLEMAS = []


def btn(root, texto):
    find(root, tk.Button, texto)[0].invoke()
    pump(root, .3)


def revisar(root, paso):
    root.update()
    malos = []
    for f in walk(root):
        if not isinstance(f, tk.Frame):
            continue
        fila = sorted([w for w in f.winfo_children() if w.winfo_manager() == "grid" and w.grid_info()["row"] == 0
                       and isinstance(w, (tk.Label, tk.Entry, tk.Text))], key=lambda w: w.winfo_x())
        for a, b in zip(fila, fila[1:]):
            if a.winfo_x() + a.winfo_width() > b.winfo_x() + 1:
                malos.append(("solapado", a.cget("text") if isinstance(a, tk.Label) else a.winfo_class()))
        for w in fila:
            if isinstance(w, tk.Label) and w.cget("bg") == "#C7A196" and w.winfo_width() < w.winfo_reqwidth():
                malos.append(("cortada", w.cget("text")))
    extra = [w for w in walk(root) if isinstance(w, tk.Toplevel)]
    if extra:
        malos.append(("ventanas extra", len(extra)))
    log(f"[{paso}] ventana={root.geometry()} problemas={malos}")
    PROBLEMAS.extend((paso, m) for m in malos)


def login(root, usuario, clave, rol):
    e = [w for w in walk(root) if isinstance(w, tk.Entry)]
    e[0].delete(0, "end"); e[1].delete(0, "end")
    e[0].insert(0, usuario); e[1].insert(0, clave)
    [r for r in walk(root) if isinstance(r, tk.Radiobutton)][rol - 1].invoke()
    btn(root, "INGRESAR")


def escenario(root, _globales):
    errores = []
    root.report_callback_exception = lambda *a: errores.append(repr(a[1]))
    root.geometry("+20+20"); pump(root)
    revisar(root, "login"); shot(os.path.join(OUT, "login.png"), windows=[root])

    login(root, "RajanUp12", "RUpadhyay123", 1)
    revisar(root, "panel director"); shot(os.path.join(OUT, "panel_director.png"), windows=[root])
    root.geometry("1350x760"); pump(root, .5); revisar(root, "panel director ancho")

    btn(root, "Nuevo docente"); revisar(root, "alta docente")
    campos = [w for w in walk(root) if isinstance(w, (tk.Entry, tk.Text))]
    valores = ["Luis", "Quispe", "Alberto", "Carmen", "05/05/1985", "Cusco", "luisq", "luis123", "Peruvian",
               "Catholic", "None", "Calle Mercaderes 200, Arequipa", "9123456780", "432143214321", "3030",
               "10th B", "History , Civics", "History(10th B) , Civics(9th C)"]
    for w, v in zip(campos, valores):
        w.insert("1.0", v) if isinstance(w, tk.Text) else w.insert(0, v)
    log("Foto:", with_dialogs(root, find(root, tk.Button, "Elegir foto...")[0].invoke,
                              [pick_file(os.path.join(DEMO, "docente_ana_rojas.jpg"))]))
    shot(os.path.join(OUT, "alta_docente.png"), windows=[root])
    log("Guardar:", with_dialogs(root, lambda: btn(root, "Guardar"), [lambda *a: None]))
    fila = sqlite3.connect("testdata.db").execute(
        "SELECT name, mno, adno, length(photo_blob) FROM TeacherData WHERE username='luisq'").fetchone()
    log("En la base:", fila)
    if not fila or not fila[3]:
        PROBLEMAS.append(("alta docente", "no se guardó el registro o la foto"))

    btn(root, "Volver"); btn(root, "Editar docente"); revisar(root, "editar docente")
    [w for w in walk(root) if isinstance(w, tk.Listbox)][0].selection_set(10)
    btn(root, "Elegir campo")
    e = [w for w in walk(root) if isinstance(w, tk.Entry)]
    e[0].insert(0, "Luis"); e[1].insert(0, "3030")
    t = [w for w in walk(root) if isinstance(w, tk.Text)][0]
    t.insert("1.0", "98765")
    log("Celular corto:", with_dialogs(root, lambda: btn(root, "Actualizar"), [lambda *a: None]))
    t.delete("1.0", "end"); t.insert("1.0", "9988776655")
    log("Celular válido:", with_dialogs(root, lambda: btn(root, "Actualizar"), [lambda *a: None]))
    btn(root, "Volver"); btn(root, "Cerrar sesión")

    login(root, "luisq", "luis123", 2)
    revisar(root, "panel docente"); shot(os.path.join(OUT, "panel_docente.png"), windows=[root])
    btn(root, "Nuevo alumno"); revisar(root, "alta alumno"); btn(root, "Volver")
    btn(root, "Editar alumno"); revisar(root, "editar alumno"); btn(root, "Volver"); btn(root, "Cerrar sesión")

    login(root, "Rushabh123", "12345678", 3)
    revisar(root, "panel alumno"); shot(os.path.join(OUT, "panel_alumno.png"), windows=[root])
    btn(root, "Cerrar sesión")
    log("Excepciones:", errores)
    PROBLEMAS.extend(("excepción", e) for e in errores)


if __name__ == "__main__":
    copia = tempfile.mkdtemp(prefix="svdd_verificacion_")
    for archivo in glob.glob(os.path.join(RAIZ, "*.py")) + [os.path.join(RAIZ, "testdata.db")]:
        shutil.copy(archivo, copia)
    run(os.path.join(copia, "SchoolManagementSystem.py"), escenario)
    print("\nRESULTADO:", "OK, sin problemas" if not PROBLEMAS else f"{len(PROBLEMAS)} problema(s): {PROBLEMAS}")
    sys.exit(1 if PROBLEMAS else 0)
