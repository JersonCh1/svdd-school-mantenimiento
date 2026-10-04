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
from tkinter import messagebox, ttk

import fotos
from db import TABLAS, BaseDeDatosOcupada, ErrorIntegridad
from navegacion import Navegador
from gestion import REGISTROS, ErrorValidacion, Gestion
from validacion import configurar_numerico, errores_registro, periodo_actual

FONDO = '#583830'
FONDO_LOGIN = '#897C78'
ETIQUETA = '#C7A196'
VALOR = '#FDD4B8'
TEXTO = '#18120F'
ERROR = '#F2A7A0'
F_TITULO = ("PT Sans", 20, "bold")
F_ETIQUETA = ("Cambria", 14, "bold")
F_VALOR = ("Cambria", 14)
F_BOTON = ("Cambria", 10, "bold")
F_LOGIN = ("Helvetica", 14, "bold")
F_RADIO = ("Helvetica", 12, "bold")

ROLES = {1: "principal", 2: "teacher", 3: "student"}
NOMBRE_ROL = {"principal": "Director", "teacher": "Docente", "student": "Alumno"}
LARGO = "largo"  # campo de varias líneas

# Filas de campos: (etiqueta, columna[, LARGO]). Las tres primeras filas van al lado de la foto.
PERSONALES = [
    [("Nombre:", "name"), ("Apellido:", "lname")],
    [("Segundo nombre:", "fname"), ("Nombre de la madre:", "mname")],
    [("Fecha de nacimiento:", "dob"), ("Lugar de nacimiento:", "bplace")],
]
CAMPOS = {
    "student": PERSONALES + [
        [("Nacionalidad:", "nation"), ("Religión:", "relig"), ("Casta:", "caste")],
        [("Dirección:", "addr", LARGO)],
        [("Celular:", "mno"), ("Estatura:", "hei"), ("Peso:", "wei")],
        [("N.° de Aadhaar:", "adno"), ("N.° de registro general:", "gno")],
        [("Fecha de ingreso al colegio:", "doa"), ("Grado:", "std"), ("Sección:", "div")],
        [("Tutor(a) del aula:", "ctname"), ("Color de casa:", "hcolor"), ("N.° de lista:", "rno")],
        [("Observaciones del docente:", "trem", LARGO)],
    ],
    "teacher": PERSONALES + [
        [("Nacionalidad:", "nation"), ("Religión:", "relig"), ("Casta:", "caste")],
        [("Dirección:", "addr", LARGO)],
        [("Celular:", "mno"), ("N.° de Aadhaar:", "adno")],
        [("N.° de registro docente:", "trno"), ("Tutor(a) del aula:", "ctfc")],
        [("Cursos que dicta:", "staught")],
        [("Aulas a cargo:", "tfor", LARGO)],
    ],
}
CAMPOS["principal"] = [[("Cargo:", "pos") if c[1] == "ctfc" else c for c in fila] for fila in CAMPOS["teacher"]]

# Listados de gestión (v5.0): título, cómo nombrar al registro y columnas (columna, título, ancho).
LISTADOS = {
    "student": dict(titulo="Gestión de alumnos", quien="alumno",
                    buscar="Buscar (N.° de registro o nombre):", columnas=[
        ("gno", "N.° registro", 90), ("name", "Nombre", 130), ("lname", "Apellido", 130),
        ("std", "Grado", 70), ("div", "Sección", 70), ("username", "Usuario", 120)]),
    "teacher": dict(titulo="Gestión de docentes", quien="docente",
                    buscar="Buscar (N.° de registro o nombre):", columnas=[
        ("trno", "N.° registro", 90), ("name", "Nombre", 130), ("lname", "Apellido", 130),
        ("staught", "Cursos que dicta", 200), ("username", "Usuario", 120)]),
    "curso": dict(titulo="Gestión de cursos", quien="curso",
                  buscar="Buscar (código, curso o docente):", columnas=[
        ("codigo", "Código", 90), ("nombre", "Curso", 200), ("grado", "Grado", 80), ("docente", "Docente", 180)]),
    "matricula": dict(titulo="Matrículas", quien="matrícula", editable=False,
                      buscar="Buscar (N.° de registro, alumno, curso o periodo):", columnas=[
        ("periodo", "Periodo", 80), ("gno", "N.° registro", 90), ("alumno", "Alumno", 180),
        ("codigo", "Código", 80), ("curso", "Curso", 160), ("grado", "Grado", 70), ("fecha", "Fecha", 100)]),
}

# Formularios de edición: qué tabla, cómo se identifica el registro y qué campos se pueden cambiar.
# (Desde la v5.0 los alumnos y docentes se editan con el formulario completo.)
EDICIONES = {
    "personal": dict(tabla="PrincipalData", clave="trno", rol="principal",
                     nombre="Tu nombre:", registro="Tu N.° de registro:"),
}
ROL_DE_EDICION = {"personal": "principal"}
for _tipo, _conf in EDICIONES.items():
    _campos = CAMPOS[ROL_DE_EDICION[_tipo]]
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


def marcar_errores(padre, campos, errores, titulo="Revisa los datos"):
    """v5.0 R06: pinta los campos con error, pone el cursor en el primero y
    explica todos los problemas juntos. No se borra nada de lo escrito: el
    usuario corrige solo lo marcado."""
    malos = {col for col, _m in errores}
    for col, w in campos.items():
        w.configure(bg=ERROR if col in malos else VALOR)
    for col, _m in errores:
        if col in campos:
            campos[col].focus_set()
            break
    detalle = "\n".join(f"• {m}" for _c, m in errores)
    messagebox.showerror(titulo, f"No se guardó. Corrige lo siguiente:\n\n{detalle}", parent=padre)


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
        self.gestion = Gestion(db)
        self.rol = tk.IntVar(root)

    # --- login ------------------------------------------------------------

    def mostrar_login(self, usuario=""):
        p = self.nav.pantalla(bg=FONDO_LOGIN)
        p.columnconfigure((0, 1, 2), weight=1)
        p.rowconfigure((0, 5), weight=1)
        for fila, texto in ((1, "Usuario :"), (2, "Contraseña :")):
            tk.Label(p, text=texto, font=F_LOGIN, fg=TEXTO, bg=VALOR).grid(row=fila, column=0, sticky="e", padx=(30, 8), pady=10)
        self.usuario = tk.Entry(p, width=20, font=("Helvetica", 14))
        self.clave = tk.Entry(p, width=20, font=("Helvetica", 14), show="*")
        self.usuario.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(0, 30))
        self.clave.grid(row=2, column=1, columnspan=2, sticky="ew", padx=(0, 30))
        radios = tk.Frame(p, bg=FONDO_LOGIN)
        radios.grid(row=3, column=0, columnspan=3, pady=8)
        for valor, texto in ((1, "Director"), (2, "Docente"), (3, "Alumno")):
            tk.Radiobutton(radios, text=texto, variable=self.rol, value=valor, font=F_RADIO, bg=FONDO_LOGIN,
                           fg=TEXTO, activebackground=FONDO_LOGIN).pack(side="left", padx=10)
        tk.Button(p, text="INGRESAR", width=20, font=F_LOGIN, bg=ETIQUETA, activebackground=VALOR,
                  command=self.iniciar_sesion).grid(row=4, column=0, columnspan=3, pady=(6, 0))
        for e in (self.usuario, self.clave):
            e.bind("<Return>", lambda _e: self.iniciar_sesion())
        self.usuario.insert(0, usuario)
        (self.clave if usuario else self.usuario).focus_set()
        self.nav.ajustar(minimo=(420, 280))

    def iniciar_sesion(self):
        if self.rol.get() not in ROLES:
            messagebox.showerror('Elige un rol', 'Marca Director, Docente o Alumno antes de ingresar.')
            return
        usuario, clave = self.usuario.get(), self.clave.get()
        if self.leer_sesion(self.rol.get(), usuario, clave) is None:
            messagebox.showerror('Datos incorrectos', 'El usuario o la contraseña no son correctos. Inténtalo de nuevo.')
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
        tk.Label(p, text=f"Sesión iniciada como {NOMBRE_ROL[rol]}", font=F_TITULO, bg=VALOR, anchor="w",
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

        botones = [("Cerrar sesión", self.cerrar_sesion)]
        if rol == "principal":
            botones += [("Editar mis datos", lambda: self.mostrar_edicion("personal")),
                        ("Docentes", lambda: self.mostrar_gestion("teacher"))]
        if rol in ("principal", "teacher"):
            botones += [("Alumnos", lambda: self.mostrar_gestion("student")),
                        ("Cursos", lambda: self.mostrar_gestion("curso")),
                        ("Matrículas", lambda: self.mostrar_gestion("matricula"))]
        self.barra_botones(p, botones)
        self.nav.ajustar(minimo=(640, 0))

    def barra_botones(self, p, botones, fila=2):
        barra = tk.Frame(p, bg=FONDO)
        barra.grid(row=fila, column=0, sticky="ew", padx=14, pady=(0, 14))
        for i, (texto, comando) in enumerate(botones):
            barra.columnconfigure(i, weight=1)
            boton(barra, texto, comando).grid(row=0, column=i, sticky="w" if i == 0 else "e", padx=4)

    # --- gestión: listado con altas, ediciones y bajas (v5.0) ---------------

    def mostrar_gestion(self, tipo, seleccion=None):
        conf = LISTADOS[tipo]
        p = self.nav.pantalla()
        p.columnconfigure(0, weight=1)
        p.rowconfigure(2, weight=1)
        self.encabezado(p, ROLES[self.nav.sesion[0]])
        tk.Label(p, text=conf["titulo"], font=F_ETIQUETA, fg=VALOR, bg=FONDO, anchor="w").grid(
            row=1, column=0, sticky="ew", padx=14, pady=(10, 0))
        cuerpo = tk.Frame(p, bg=FONDO)
        cuerpo.grid(row=2, column=0, sticky="nsew", padx=14, pady=10)
        cuerpo.columnconfigure(0, weight=1)
        cuerpo.rowconfigure(1, weight=1)

        # R05: búsqueda por identificador o nombre.
        buscador = tk.Frame(cuerpo, bg=FONDO)
        buscador.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        buscador.columnconfigure(1, weight=1)
        etiqueta(buscador, conf["buscar"]).grid(row=0, column=0, sticky="w", padx=(0, 8))
        filtro = tk.Entry(buscador, width=20, font=F_VALOR, fg=TEXTO, bg=VALOR)
        filtro.grid(row=0, column=1, sticky="ew")
        boton(buscador, "Buscar", lambda: cargar()).grid(row=0, column=2, padx=(8, 0))
        boton(buscador, "Mostrar todos", lambda: (filtro.delete(0, "end"), cargar())).grid(row=0, column=3, padx=(8, 0))
        filtro.bind("<Return>", lambda _e: cargar())

        columnas = [c for c, _t, _a in conf["columnas"]]
        tabla = ttk.Treeview(cuerpo, columns=columnas, show="headings", height=12, selectmode="browse")
        for col, titulo, ancho in conf["columnas"]:
            tabla.heading(col, text=titulo, anchor="w")
            tabla.column(col, width=ancho, minwidth=50, stretch=True)
        barra = ttk.Scrollbar(cuerpo, orient="vertical", command=tabla.yview)
        tabla.configure(yscrollcommand=barra.set)
        tabla.grid(row=1, column=0, sticky="nsew")
        barra.grid(row=1, column=1, sticky="ns")
        aviso = tk.Label(cuerpo, text="", font=F_VALOR, fg=VALOR, bg=FONDO, anchor="w")
        aviso.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        claves = {}  # iid del Treeview (texto) -> clave real del registro

        def cargar():
            tabla.delete(*tabla.get_children())
            claves.clear()
            buscado = filtro.get().strip()
            try:
                filas = self.gestion.listar(tipo, buscado)
            except BaseDeDatosOcupada as e:
                messagebox.showerror("Base de datos ocupada", str(e), parent=p)
                return
            for fila in filas:
                claves[str(fila["clave"])] = fila["clave"]
                tabla.insert("", "end", iid=str(fila["clave"]),
                             values=["" if fila[c] is None else fila[c] for c in columnas])
            if buscado and not filas:
                aviso.configure(text=f"No se encontraron coincidencias para «{buscado}».", fg=ERROR)
            elif buscado:
                aviso.configure(text=f"{len(filas)} coincidencia(s) para «{buscado}».", fg=VALOR)
            else:
                aviso.configure(text=f"{len(filas)} registro(s).", fg=VALOR)
            if seleccion is not None and tabla.exists(str(seleccion)):
                tabla.selection_set(str(seleccion))
                tabla.see(str(seleccion))

        def elegido():
            sel = tabla.selection()
            if not sel:
                messagebox.showerror("Falta elegir", f"Selecciona en la lista el {conf['quien']}.", parent=p)
                return None
            return claves[sel[0]]

        def editar():
            clave = elegido()
            if clave is not None:
                self.mostrar_formulario(tipo, clave)

        def eliminar():
            clave = elegido()
            if clave is None:
                return
            descripcion = " ".join(str(v) for v in tabla.item(str(clave), "values")[:3])
            accion = "Anular la" if tipo == "matricula" else "Eliminar el"
            if not messagebox.askyesno("Confirmar eliminación",
                                       f"¿{accion} {conf['quien']} {descripcion}?\n"
                                       "Esta acción no se puede deshacer.", parent=p):
                return
            if self.ejecutar(p, lambda: self.gestion.eliminar(tipo, clave)):
                hecho = "Se anuló la" if tipo == "matricula" else "Se eliminó el"
                messagebox.showinfo("Hecho", f"{hecho} {conf['quien']}.", parent=p)
                cargar()

        cargar()
        botones = [("Volver", self.mostrar_panel), ("Nuevo", lambda: self.mostrar_formulario(tipo))]
        if conf.get("editable", True):
            tabla.bind("<Double-1>", lambda _e: editar())
            botones += [("Editar", editar), ("Eliminar", eliminar)]
        else:
            botones += [("Anular", eliminar)]
        self.barra_botones(p, botones, fila=3)
        self.nav.ajustar(minimo=(760, 460))

    def ejecutar(self, p, operacion):
        """Corre una operación de escritura y explica cualquier fallo.
        Devuelve True si se guardó. Si falla, la transacción ya se revirtió (R07)."""
        try:
            operacion()
        except ErrorValidacion as e:
            messagebox.showerror("No se guardó", str(e), parent=p)
        except ErrorIntegridad as e:
            messagebox.showerror("No se guardó", f"{e}\nNo se guardó ningún cambio.", parent=p)
        except BaseDeDatosOcupada as e:
            messagebox.showerror("Base de datos ocupada", str(e), parent=p)
        else:
            return True
        return False

    # --- formulario de alumno / docente (alta y edición) ---------------------

    def mostrar_formulario(self, tipo, clave=None):
        """Sin 'clave' es un alta; con 'clave' se cargan los datos para editarlos."""
        if tipo == "curso":
            self.mostrar_formulario_curso(clave)
            return
        if tipo == "matricula":
            self.mostrar_formulario_matricula()
            return
        rol = ROLES[self.nav.sesion[0]]
        registro = self.gestion.obtener(tipo, clave) if clave is not None else None
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
        etiqueta(lateral, "Foto:").grid(row=0, column=0, sticky="w", pady=5)
        selector.boton.grid(row=0, column=1, sticky="w", padx=4)
        cuenta = {}
        for i, (texto, col) in enumerate((("Usuario:", "username"), ("Contraseña:", "password")), start=1):
            etiqueta(lateral, texto).grid(row=i, column=0, sticky="w", pady=5)
            cuenta[col] = tk.Entry(lateral, width=15, font=F_VALOR, fg=TEXTO, bg=VALOR)
            cuenta[col].grid(row=i, column=1, sticky="ew", padx=4)
        selector.vista.grid(row=3, column=0, columnspan=2, pady=6)
        campos.update(filas_de_campos(cuerpo, CAMPOS[tipo][3:], entrada, desde=1))
        configurar_numerico(campos["mno"], 10)
        configurar_numerico(campos["adno"], 12)

        if registro is not None:
            for col, w in {**campos, **cuenta}.items():
                valor = "" if registro[col] is None else str(registro[col])
                w.insert("1.0", valor) if isinstance(w, tk.Text) else w.insert(0, valor)
            # Si no se elige otra foto, se conserva la actual.
            selector.nombre, selector.datos = registro["photo"] or "", registro["photo_blob"]
            if selector.datos:
                fotos.mostrar(selector.vista, selector.datos, fotos.TAMANO_MINIATURA)

        quien = LISTADOS[tipo]["quien"]

        def guardar():
            datos = {col: texto_de(w) for col, w in campos.items()}
            datos.update({col: w.get() for col, w in cuenta.items()})
            datos.update(photo=selector.nombre, photo_blob=selector.datos)
            try:
                if registro is None:
                    guardados = self.gestion.registrar(tipo, datos)
                else:
                    guardados = self.gestion.actualizar(tipo, clave, datos)
            except ErrorValidacion as e:
                marcar_errores(p, {**campos, **cuenta}, e.errores)
                return
            except BaseDeDatosOcupada as e:
                messagebox.showerror("Base de datos ocupada", str(e), parent=p)
                return
            except ErrorIntegridad as e:
                messagebox.showerror("No se guardó", f"{e}\nNo se guardó ningún cambio.", parent=p)
                return
            if registro is None:
                messagebox.showinfo("Registro guardado", f"Se registraron los datos del nuevo {quien}.", parent=p)
            else:
                messagebox.showinfo("Registro actualizado", f"Se actualizaron los datos del {quien}.", parent=p)
            self.mostrar_gestion(tipo, seleccion=guardados[REGISTROS[tipo]["clave"]])

        self.barra_botones(p, [("Volver", lambda: self.mostrar_gestion(tipo, seleccion=clave)),
                               ("Guardar", guardar)])
        self.nav.ajustar(minimo=(760, 0))

    # --- formulario de curso (R03) ------------------------------------------

    def formulario_simple(self, titulo):
        """Pantalla con título y una grilla de dos columnas (etiqueta, valor)."""
        p = self.nav.pantalla()
        p.columnconfigure(0, weight=1)
        p.rowconfigure(2, weight=1)
        self.encabezado(p, ROLES[self.nav.sesion[0]])
        tk.Label(p, text=titulo, font=F_ETIQUETA, fg=VALOR, bg=FONDO, anchor="w").grid(
            row=1, column=0, sticky="ew", padx=14, pady=(10, 0))
        cuerpo = tk.Frame(p, bg=FONDO)
        cuerpo.grid(row=2, column=0, sticky="nsew", padx=14, pady=10)
        cuerpo.columnconfigure(1, weight=1)
        return p, cuerpo

    def mostrar_formulario_curso(self, clave=None):
        curso = self.gestion.obtener("curso", clave) if clave is not None else None
        p, cuerpo = self.formulario_simple("Editar curso" if curso else "Nuevo curso")
        campos = {}
        for i, (texto, col) in enumerate((("Código:", "codigo"), ("Nombre del curso:", "nombre"), ("Grado:", "grado"))):
            etiqueta(cuerpo, texto).grid(row=i, column=0, sticky="w", pady=5, padx=(0, 8))
            campos[col] = tk.Entry(cuerpo, width=30, font=F_VALOR, fg=TEXTO, bg=VALOR)
            campos[col].grid(row=i, column=1, sticky="ew")
            if curso is not None and curso[col] is not None:
                campos[col].insert(0, str(curso[col]))
        etiqueta(cuerpo, "Docente a cargo:").grid(row=3, column=0, sticky="w", pady=5, padx=(0, 8))
        docentes = [(None, "— Sin asignar —")] + [
            (f["trno"], f"{f['trno']} · {f['name']} {f['lname']}") for f in self.gestion.listar("teacher")]
        docente = ttk.Combobox(cuerpo, state="readonly", font=F_VALOR, values=[t for _k, t in docentes])
        docente.grid(row=3, column=1, sticky="ew")
        actual = curso["trno"] if curso is not None else None
        docente.current(next((i for i, (k, _t) in enumerate(docentes) if k == actual), 0))

        def guardar():
            datos = {col: w.get() for col, w in campos.items()}
            trno = docentes[docente.current()][0]
            datos["trno"] = "" if trno is None else str(trno)
            try:
                if curso is None:
                    guardado = self.gestion.registrar("curso", datos)
                else:
                    guardado = self.gestion.actualizar("curso", clave, datos)
            except ErrorValidacion as e:
                marcar_errores(p, campos, e.errores)
                return
            except (ErrorIntegridad, BaseDeDatosOcupada) as e:
                messagebox.showerror("No se guardó", f"{e}\nNo se guardó ningún cambio.", parent=p)
                return
            messagebox.showinfo("Curso guardado", f"Se guardó el curso {guardado['codigo']}.", parent=p)
            self.mostrar_gestion("curso", seleccion=guardado["id"])

        self.barra_botones(p, [("Volver", lambda: self.mostrar_gestion("curso", seleccion=clave)),
                               ("Guardar", guardar)], fila=3)
        campos["codigo"].focus_set()
        self.nav.ajustar(minimo=(640, 0))

    # --- registro de matrícula (R04) -----------------------------------------

    def mostrar_formulario_matricula(self):
        p, cuerpo = self.formulario_simple("Nueva matrícula")
        alumnos = [(f["gno"], f"{f['gno']} · {f['name']} {f['lname']}") for f in self.gestion.listar("student")]
        cursos = [(f["clave"], f"{f['codigo']} · {f['nombre']}" + (f" ({f['grado']})" if f["grado"] else ""))
                  for f in self.gestion.listar("curso")]
        campos = {}
        for i, (texto, col, opciones) in enumerate((("Alumno:", "gno", alumnos), ("Curso:", "curso_id", cursos))):
            etiqueta(cuerpo, texto).grid(row=i, column=0, sticky="w", pady=5, padx=(0, 8))
            campos[col] = ttk.Combobox(cuerpo, state="readonly", width=36, font=F_VALOR, values=[t for _k, t in opciones])
            campos[col].grid(row=i, column=1, sticky="ew")
        etiqueta(cuerpo, "Periodo:").grid(row=2, column=0, sticky="w", pady=5, padx=(0, 8))
        periodo = tk.Entry(cuerpo, width=12, font=F_VALOR, fg=TEXTO, bg=VALOR)
        periodo.insert(0, periodo_actual())
        periodo.grid(row=2, column=1, sticky="w")
        if not cursos:
            tk.Label(cuerpo, text="Todavía no hay cursos: regístralos primero en «Cursos».", font=F_VALOR,
                     fg=VALOR, bg=FONDO).grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

        def elegido(col, opciones):
            i = campos[col].current()
            return "" if i < 0 else str(opciones[i][0])

        def guardar():
            datos = {"gno": elegido("gno", alumnos), "curso_id": elegido("curso_id", cursos), "periodo": periodo.get()}
            try:
                self.gestion.registrar("matricula", datos)
            except ErrorValidacion as e:
                marcar_errores(p, {"periodo": periodo}, e.errores)
                return
            except (ErrorIntegridad, BaseDeDatosOcupada) as e:
                messagebox.showerror("No se guardó", f"{e}\nNo se guardó ningún cambio.", parent=p)
                return
            messagebox.showinfo("Matrícula registrada",
                                f"Se matriculó a {campos['gno'].get()} en {campos['curso_id'].get()} "
                                f"({periodo.get().strip().upper()}).", parent=p)
            # Se queda en el formulario para matricular al mismo alumno en otro curso.
            campos["curso_id"].set("")

        self.barra_botones(p, [("Volver", lambda: self.mostrar_gestion("matricula")),
                               ("Registrar", guardar)], fila=3)
        self.nav.ajustar(minimo=(640, 0))

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
        boton(derecha, "Elegir campo", lambda: elegir(), F_ETIQUETA).grid(row=0, column=0, sticky="w")
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
        actualizar_btn = boton(derecha, "Actualizar", lambda: actualizar(), F_ETIQUETA)
        estado = {"columna": None}

        def elegir():
            seleccion = lista.curselection()
            if not seleccion:
                messagebox.showerror("Falta elegir", "Selecciona en la lista el campo que quieres cambiar.", parent=p)
                return
            texto, estado["columna"] = conf["opciones"][seleccion[0]]
            elegido.set(texto)
            detalle.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
            actualizar_btn.grid(row=2, column=0, sticky="w", pady=12)
            self.nav.ajustar(minimo=(640, 0))  # la pantalla creció: se vuelve a medir

        def actualizar():
            columna, valor = estado["columna"], nuevo.get("1.0", "end-1c")
            errores = errores_registro(ROL_DE_EDICION[tipo], {columna: valor}, parcial=True)
            if errores:
                messagebox.showerror("Dato no válido", errores[0][1], parent=p)
                return
            if columna in ("mno", "adno"):
                valor = valor.strip()
            try:
                filas = self.db.actualizar(conf["tabla"], columna, valor,
                                           {"name": nombre.get(), conf["clave"]: registro.get()})
            except BaseDeDatosOcupada as e:
                messagebox.showerror("Base de datos ocupada", str(e), parent=p)
                return
            except ErrorIntegridad as e:
                messagebox.showerror("No se actualizó", f"{e}\nNo se guardó ningún cambio.", parent=p)
                return
            if filas == 0:
                messagebox.showerror("No encontrado", "Ningún registro coincide con ese nombre y número de registro.", parent=p)
                return
            messagebox.showinfo('Actualizado', 'El dato se actualizó correctamente.', parent=p)

        self.barra_botones(p, [("Volver", self.mostrar_panel)])
        self.nav.ajustar(minimo=(640, 0))

