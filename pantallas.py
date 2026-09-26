"""Pantallas de S.V.D.D. School con diseño adaptable (v4.0 — R02).

Antes cada Label/Entry se ubicaba con place(x, y) en píxeles fijos: al
cambiar el tamaño de la ventana, la fuente o la escala de Windows, los
textos se cortaban o quedaban márgenes vacíos. Ahora todo usa grid() con
pesos (columnconfigure/rowconfigure weight): los campos se estiran con la
ventana y los textos largos se reacomodan en varias líneas.

Las tres versiones duplicadas de cada pantalla (alumno, docente, director)
se reemplazan por una sola, guiada por las tablas de campos de abajo.
"""

import tkinter as tk
from tkinter import messagebox

import fotos
from db import TABLAS, BaseDeDatosOcupada
from navegacion import Navegador
from validacion import configurar_numerico, error_numerico

FONDO = '#583830'
FONDO_LOGIN = '#897C78'
ETIQUETA = '#C7A196'
VALOR = '#FDD4B8'
TEXTO = '#18120F'
F_TITULO = ("PT Sans", 20, "bold")
F_ETIQUETA = ("Cambria", 14, "bold")
F_VALOR = ("Cambria", 14)
F_BOTON = ("Cambria", 10, "bold")
F_LOGIN = ("Helvetica", 14, "bold")
F_RADIO = ("Helvetica", 12, "bold")

ROLES = {1: "principal", 2: "teacher", 3: "student"}
NOMBRE_ROL = {"principal": "Principal", "teacher": "Teacher", "student": "Student"}
LARGO = "largo"  # campo de varias líneas

# Filas de campos: (etiqueta, columna[, LARGO]). Las tres primeras filas van al lado de la foto.
PERSONALES = [
    [("First Name:", "name"), ("Last Name:", "lname")],
    [("Middle Name:", "fname"), ("Mother's Name:", "mname")],
    [("Date of Birth:", "dob"), ("Birth Place:", "bplace")],
]
CAMPOS = {
    "student": PERSONALES + [
        [("Nationality:", "nation"), ("Religion:", "relig"), ("Caste:", "caste")],
        [("Address:", "addr", LARGO)],
        [("Mobile No.:", "mno"), ("Height:", "hei"), ("Weight:", "wei")],
        [("Aadhaar Card No.:", "adno"), ("General Registration No.:", "gno")],
        [("Date of Admission in School:", "doa"), ("Standard:", "std"), ("Div:", "div")],
        [("Class Teacher's Name:", "ctname"), ("House Colour:", "hcolor"), ("Roll No.:", "rno")],
        [("Teacher's Remarks:", "trem", LARGO)],
    ],
    "teacher": PERSONALES + [
        [("Nationality:", "nation"), ("Religion:", "relig"), ("Caste:", "caste")],
        [("Address:", "addr", LARGO)],
        [("Mobile No.:", "mno"), ("Aadhaar Card No.:", "adno")],
        [("Teacher's Registration No.:", "trno"), ("Class Teacher for Class:", "ctfc")],
        [("Subjects Taught:", "staught")],
        [("Teacher For:", "tfor", LARGO)],
    ],
}
CAMPOS["principal"] = [[("Position:", "pos") if c[1] == "ctfc" else c for c in fila] for fila in CAMPOS["teacher"]]

# Formularios de edición: qué tabla, cómo se identifica el registro y qué campos se pueden cambiar.
EDICIONES = {
    "student": dict(tabla="StudentData", clave="gno", rol="teacher",
                    nombre="Enter Student's First Name:", registro="Enter Student's Gen. Reg. No.:"),
    "teacher": dict(tabla="TeacherData", clave="trno", rol="principal",
                    nombre="Enter Teacher's First Name:", registro="Enter Teacher's Reg. No.:"),
    "personal": dict(tabla="PrincipalData", clave="trno", rol="principal",
                     nombre="Enter Your First Name:", registro="Enter Your Reg. No.:"),
}
for _tipo, _conf in EDICIONES.items():
    _campos = CAMPOS["student" if _tipo == "student" else ("principal" if _tipo == "personal" else "teacher")]
    _conf["opciones"] = [(etq.rstrip(":"), col) for fila in _campos for etq, col, *_ in fila]


def etiqueta(padre, texto, **kw):
    return tk.Label(padre, text=texto, font=F_ETIQUETA, fg=TEXTO, bg=ETIQUETA, anchor="w", **kw)


def boton(padre, texto, comando, fuente=F_BOTON):
    return tk.Button(padre, text=texto, command=comando, fg=TEXTO, bg=ETIQUETA, font=fuente)


def ajustar_al_ancho(label):
    """El texto se reparte en varias líneas según el ancho real del label.

    Se ignoran los anchos diminutos del primer <Configure> (antes de que grid
    reparta el espacio): con ellos el texto se partía en decenas de líneas y
    la ventana se medía mucho más alta de lo necesario."""
    def ajustar(evento):
        if evento.width > 80:
            label.configure(wraplength=evento.width - 8)
    label.bind("<Configure>", ajustar)


def texto_de(widget):
    if isinstance(widget, tk.Text):
        return widget.get("1.0", "end-1c")
    return widget.get()


def filas_de_campos(padre, filas, crear_valor, desde=0):
    """Una fila de la grilla por cada fila de campos. La columna de cada valor
    tiene peso 1: al agrandar la ventana, los valores ocupan el espacio extra."""
    widgets = {}
    padre.columnconfigure(0, weight=1)
    for i, fila in enumerate(filas):
        marco = tk.Frame(padre, bg=FONDO)
        marco.grid(row=desde + i, column=0, sticky="ew", pady=5)
        for j, (texto, columna, *tipo) in enumerate(fila):
            etiqueta(marco, texto).grid(row=0, column=2 * j, sticky="nw", padx=(0 if j == 0 else 14, 4))
            valor = crear_valor(marco, columna, bool(tipo))
            valor.grid(row=0, column=2 * j + 1, sticky="new")
            marco.columnconfigure(2 * j + 1, weight=1, uniform="valores")
            widgets[columna] = valor
    return widgets


class Aplicacion:
    def __init__(self, root, db):
        self.root = root
        self.db = db
        self.nav = Navegador(root)
        self.rol = tk.IntVar(root)

    # --- login ------------------------------------------------------------

    def mostrar_login(self, usuario=""):
        p = self.nav.pantalla(bg=FONDO_LOGIN)
        p.columnconfigure((0, 1, 2), weight=1)
        p.rowconfigure((0, 5), weight=1)
        for fila, texto in ((1, "Username :"), (2, "Password :")):
            tk.Label(p, text=texto, font=F_LOGIN, fg=TEXTO, bg=VALOR).grid(row=fila, column=0, sticky="e", padx=(30, 8), pady=10)
        self.usuario = tk.Entry(p, width=20, font=("Helvetica", 14))
        self.clave = tk.Entry(p, width=20, font=("Helvetica", 14), show="*")
        self.usuario.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(0, 30))
        self.clave.grid(row=2, column=1, columnspan=2, sticky="ew", padx=(0, 30))
        radios = tk.Frame(p, bg=FONDO_LOGIN)
        radios.grid(row=3, column=0, columnspan=3, pady=8)
        for valor, texto in ((1, "Principal"), (2, "Teacher"), (3, "Student")):
            tk.Radiobutton(radios, text=texto, variable=self.rol, value=valor, font=F_RADIO, bg=FONDO_LOGIN,
                           fg=TEXTO, activebackground=FONDO_LOGIN).pack(side="left", padx=10)
        tk.Button(p, text="LOG IN", width=20, font=F_LOGIN, bg=ETIQUETA, activebackground=VALOR,
                  command=self.iniciar_sesion).grid(row=4, column=0, columnspan=3, pady=(6, 0))
        for e in (self.usuario, self.clave):
            e.bind("<Return>", lambda _e: self.iniciar_sesion())
        self.usuario.insert(0, usuario)
        (self.clave if usuario else self.usuario).focus_set()
        self.nav.ajustar(minimo=(420, 280))

    def iniciar_sesion(self):
        if self.rol.get() not in ROLES:
            messagebox.showerror('Select a role', 'Choose Principal, Teacher or Student before logging in.')
            return
        usuario, clave = self.usuario.get(), self.clave.get()
        if self.leer_sesion(self.rol.get(), usuario, clave) is None:
            messagebox.showerror('Incorrect Password', 'Your Username or Password was Incorrect.Try Again')
            return
        self.nav.sesion = (self.rol.get(), usuario, clave)
        self.mostrar_panel()

    def leer_sesion(self, rol, usuario, clave):
        try:
            return self.db.autenticar(TABLAS[ROLES[rol]], usuario, clave)
        except BaseDeDatosOcupada as e:
            messagebox.showerror("Base de datos ocupada", str(e))
            return None

    def cerrar_sesion(self):
        usuario = self.nav.sesion[1] if self.nav.sesion else ""
        self.nav.sesion = None
        self.mostrar_login(usuario)

    # --- panel de datos -----------------------------------------------------

    def encabezado(self, p, rol):
        tk.Label(p, text=f"Logged in as {NOMBRE_ROL[rol]}", font=F_TITULO, bg=VALOR, anchor="w",
                 padx=6).grid(row=0, column=0, sticky="ew")

    def mostrar_panel(self):
        rol_num, usuario, clave = self.nav.sesion
        rol = ROLES[rol_num]
        fila = self.leer_sesion(rol_num, usuario, clave)
        if fila is None:
            self.cerrar_sesion()
            return
        p = self.nav.pantalla()
        p.columnconfigure(0, weight=1)
        p.rowconfigure(1, weight=1)
        self.encabezado(p, rol)
        cuerpo = tk.Frame(p, bg=FONDO)
        cuerpo.grid(row=1, column=0, sticky="nsew", padx=14, pady=10)
        cuerpo.columnconfigure(0, weight=1)

        def valor(marco, columna, largo):
            dato = "" if fila[columna] is None else str(fila[columna])
            # Ancho mínimo según el dato: en el tamaño natural los valores cortos no
            # se parten; los largos (Address, Teacher For...) se reacomodan en líneas.
            ancho = 1 if largo else min(max(len(dato), 6), 24)
            lbl = tk.Label(marco, text=dato, font=F_VALOR, fg=TEXTO, bg=VALOR,
                           anchor="nw", justify="left", width=ancho)
            ajustar_al_ancho(lbl)
            return lbl

        arriba = tk.Frame(cuerpo, bg=FONDO)
        arriba.grid(row=0, column=0, sticky="ew")
        arriba.columnconfigure(0, weight=1)
        izquierda = tk.Frame(arriba, bg=FONDO)
        izquierda.grid(row=0, column=0, sticky="new")
        filas_de_campos(izquierda, PERSONALES, valor)
        foto = tk.Label(arriba, text=fila["photo"] or "", fg=TEXTO, bg=VALOR, width=18, height=9)
        foto.grid(row=0, column=1, sticky="n", padx=(14, 0), pady=5)
        if fila["photo_blob"]:
            fotos.mostrar(foto, fila["photo_blob"], fotos.TAMANO_PANEL)
        filas_de_campos(cuerpo, CAMPOS[rol][3:], valor, desde=1)

        botones = [("Back", self.cerrar_sesion)]
        if rol == "teacher":
            botones += [("Add New Student", lambda: self.mostrar_alta("student")),
                        ("Edit Student Info", lambda: self.mostrar_edicion("student"))]
        if rol == "principal":
            botones += [("Add New Teacher", lambda: self.mostrar_alta("teacher")),
                        ("Edit Personal Info", lambda: self.mostrar_edicion("personal")),
                        ("Edit Teacher Info", lambda: self.mostrar_edicion("teacher"))]
        self.barra_botones(p, botones)
        self.nav.ajustar(minimo=(640, 0))

    def barra_botones(self, p, botones, fila=2):
        barra = tk.Frame(p, bg=FONDO)
        barra.grid(row=fila, column=0, sticky="ew", padx=14, pady=(0, 14))
        for i, (texto, comando) in enumerate(botones):
            barra.columnconfigure(i, weight=1)
            boton(barra, texto, comando).grid(row=0, column=i, sticky="w" if i == 0 else "e", padx=4)

    # --- alta de alumno / docente -------------------------------------------

    def mostrar_alta(self, tipo):
        rol = ROLES[self.nav.sesion[0]]
        p = self.nav.pantalla()
        p.columnconfigure(0, weight=1)
        p.rowconfigure(1, weight=1)
        self.encabezado(p, rol)
        cuerpo = tk.Frame(p, bg=FONDO)
        cuerpo.grid(row=1, column=0, sticky="nsew", padx=14, pady=10)
        cuerpo.columnconfigure(0, weight=1)

        def entrada(marco, _columna, largo):
            if largo:
                return tk.Text(marco, width=10, height=3, font=F_VALOR, fg=TEXTO, bg=VALOR, wrap="word")
            return tk.Entry(marco, width=10, font=F_VALOR, fg=TEXTO, bg=VALOR)

        arriba = tk.Frame(cuerpo, bg=FONDO)
        arriba.grid(row=0, column=0, sticky="ew")
        arriba.columnconfigure(0, weight=1)
        izquierda = tk.Frame(arriba, bg=FONDO)
        izquierda.grid(row=0, column=0, sticky="new")
        campos = filas_de_campos(izquierda, PERSONALES, entrada)
        lateral = tk.Frame(arriba, bg=FONDO)
        lateral.grid(row=0, column=1, sticky="n", padx=(14, 0))
        selector = fotos.SelectorFoto(lateral)
        etiqueta(lateral, "Photo:").grid(row=0, column=0, sticky="w", pady=5)
        selector.boton.grid(row=0, column=1, sticky="w", padx=4)
        cuenta = {}
        for i, (texto, clave) in enumerate((("Username:", "username"), ("Password:", "password")), start=1):
            etiqueta(lateral, texto).grid(row=i, column=0, sticky="w", pady=5)
            cuenta[clave] = tk.Entry(lateral, width=15, font=F_VALOR, fg=TEXTO, bg=VALOR)
            cuenta[clave].grid(row=i, column=1, sticky="ew", padx=4)
        selector.vista.grid(row=3, column=0, columnspan=2, pady=6)
        campos.update(filas_de_campos(cuerpo, CAMPOS[tipo][3:], entrada, desde=1))
        configurar_numerico(campos["mno"], 10)
        configurar_numerico(campos["adno"], 12)

        def guardar():
            datos = {col: texto_de(w) for col, w in campos.items()}
            for columna in ("mno", "adno"):
                error = error_numerico(columna, datos[columna])
                if error:
                    messagebox.showerror("Dato no válido", error, parent=p)
                    return
            datos.update({clave: w.get() for clave, w in cuenta.items()})
            datos.update(photo=selector.nombre, photo_blob=selector.datos)
            try:
                self.db.insertar(TABLAS[tipo], datos)
            except BaseDeDatosOcupada as e:
                messagebox.showerror("Base de datos ocupada", str(e), parent=p)
                return
            quien = "Student" if tipo == "student" else "Teacher"
            messagebox.showinfo("Successful!", f"New {quien} Details Added Successfully", parent=p)

        self.barra_botones(p, [("Back", self.mostrar_panel), ("Enter", guardar)])
        self.nav.ajustar(minimo=(760, 0))

    # --- edición de un campo -------------------------------------------------

    def mostrar_edicion(self, tipo):
        conf = EDICIONES[tipo]
        p = self.nav.pantalla()
        p.columnconfigure(0, weight=1)
        p.rowconfigure(1, weight=1)
        self.encabezado(p, conf["rol"])
        cuerpo = tk.Frame(p, bg=FONDO)
        cuerpo.grid(row=1, column=0, sticky="nsew", padx=14, pady=10)
        cuerpo.columnconfigure(1, weight=1)
        cuerpo.rowconfigure(0, weight=1)

        lista = tk.Listbox(cuerpo, width=24, height=len(conf["opciones"]), fg=TEXTO, bg=VALOR, exportselection=False)
        for texto, _col in conf["opciones"]:
            lista.insert("end", texto)
        lista.grid(row=0, column=0, sticky="nsw")

        derecha = tk.Frame(cuerpo, bg=FONDO)
        derecha.grid(row=0, column=1, sticky="nsew", padx=(14, 0))
        derecha.columnconfigure(1, weight=1)
        boton(derecha, "Enter", lambda: elegir(), F_ETIQUETA).grid(row=0, column=0, sticky="w")
        # Los campos se crean una sola vez; el original apilaba widgets nuevos en cada Enter.
        detalle = tk.Frame(derecha, bg=FONDO)
        detalle.columnconfigure(1, weight=1)
        nombre, registro = tk.Entry(detalle, font=F_VALOR), tk.Entry(detalle, font=F_VALOR)
        etiqueta(detalle, conf["nombre"]).grid(row=0, column=0, sticky="w", pady=6)
        nombre.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        etiqueta(detalle, conf["registro"]).grid(row=1, column=0, sticky="w", pady=6)
        registro.grid(row=1, column=1, sticky="ew", padx=(8, 0))
        elegido = tk.StringVar(detalle)
        tk.Label(detalle, textvariable=elegido, font=F_ETIQUETA, fg=TEXTO, bg=ETIQUETA).grid(row=2, column=0, sticky="w", pady=6)
        nuevo = tk.Text(detalle, width=30, height=4, font=F_VALOR, wrap="word")
        nuevo.grid(row=3, column=0, columnspan=2, sticky="ew")
        actualizar_btn = boton(derecha, "UPDATE", lambda: actualizar(), F_ETIQUETA)
        estado = {"columna": None}

        def elegir():
            seleccion = lista.curselection()
            if not seleccion:
                messagebox.showerror("Error", "Please select an option", parent=p)
                return
            texto, estado["columna"] = conf["opciones"][seleccion[0]]
            elegido.set(texto)
            detalle.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
            actualizar_btn.grid(row=2, column=0, sticky="w", pady=12)
            self.nav.ajustar(minimo=(640, 0))  # la pantalla creció: se vuelve a medir

        def actualizar():
            columna, valor = estado["columna"], nuevo.get("1.0", "end-1c")
            error = error_numerico(columna, valor)
            if error:
                messagebox.showerror("Dato no válido", error, parent=p)
                return
            if columna in ("mno", "adno"):
                valor = valor.strip()
            try:
                filas = self.db.actualizar(conf["tabla"], columna, valor,
                                           {"name": nombre.get(), conf["clave"]: registro.get()})
            except BaseDeDatosOcupada as e:
                messagebox.showerror("Base de datos ocupada", str(e), parent=p)
                return
            if filas == 0:
                messagebox.showerror("Not found", "No record matches that name and registration number.", parent=p)
                return
            messagebox.showinfo('Updated', 'Updated Successfully', parent=p)

        self.barra_botones(p, [("Back", self.mostrar_panel)])
        self.nav.ajustar(minimo=(640, 0))

