"""Migraciones de datos de testdata.db. Todas son idempotentes: se ejecutan
al iniciar la aplicación y no hacen nada si la base ya está actualizada."""

import sqlite3

from validacion import LONGITUDES

TABLAS = ("StudentData", "TeacherData", "PrincipalData")


def _normalizar(columna, valor):
    """Convierte un valor heredado al formato de solo dígitos, o None si no se puede."""
    longitud = LONGITUDES[columna][0]
    if valor is None:
        return None
    texto = str(valor)
    if texto.isdigit() and len(texto) == longitud:
        return texto
    # "2345671234/4657382910": dos celulares en un mismo campo -> se conserva el primero
    primero = texto.split("/")[0]
    digitos = "".join(c for c in primero if c.isdigit())
    return digitos if len(digitos) == longitud else None


def v2_normalizar_numeros(con):
    """v2.0 R01: Mobile No. y Aadhaar Card No. quedan solo con dígitos.

    - "8829-3250-8844" -> "882932508844"
    - Registros de prueba con letras ("y65765uytj67") -> NULL, para que se
      vuelvan a ingresar desde el formulario de edición.
    """
    cambios = []
    for tabla in TABLAS:
        filas = con.execute(f"SELECT rowid, username, mno, adno FROM {tabla}").fetchall()
        for rowid, usuario, mno, adno in filas:
            for columna, valor in (("mno", mno), ("adno", adno)):
                nuevo = _normalizar(columna, valor)
                if nuevo != valor:
                    con.execute(f"UPDATE {tabla} SET {columna} = ? WHERE rowid = ?", (nuevo, rowid))
                    cambios.append((tabla, usuario, columna, valor, nuevo))
    con.commit()
    return cambios


def v2_columna_foto(con):
    """v2.0 R03: columna BLOB para guardar la imagen real de la foto.

    ALTER TABLE ... ADD COLUMN conserva todos los registros existentes; la
    columna de texto 'photo' se mantiene (guarda el nombre del archivo).
    """
    agregadas = []
    for tabla in TABLAS:
        columnas = [fila[1] for fila in con.execute(f"PRAGMA table_info({tabla})")]
        if "photo_blob" not in columnas:
            con.execute(f"ALTER TABLE {tabla} ADD COLUMN photo_blob BLOB")
            agregadas.append(tabla)
    con.commit()
    return agregadas


def v5_quitar_duplicados(con):
    """v5.0 R07: borra las copias exactas de un mismo registro (TeacherData
    tenía dos filas idénticas del usuario 5555). Se conserva la primera."""
    borradas = []
    for tabla in ("StudentData", "TeacherData"):
        columnas = ", ".join(f[1] for f in con.execute(f"PRAGMA table_info({tabla})"))
        cur = con.execute(f"DELETE FROM {tabla} WHERE rowid NOT IN "
                          f"(SELECT MIN(rowid) FROM {tabla} GROUP BY {columnas})")
        if cur.rowcount:
            borradas.append((tabla, cur.rowcount))
    con.commit()
    return borradas


# Identificadores que no pueden repetirse. Los índices únicos de gno y trno
# además permiten que Curso y Matricula los usen como claves foráneas.
UNICOS = (("StudentData", "gno"), ("StudentData", "username"),
          ("TeacherData", "trno"), ("TeacherData", "username"))


def v5_indices_unicos(con):
    """v5.0 R07: la base rechaza duplicados aunque algún formulario no los revise.
    Si quedan duplicados que no son copias exactas, avisa y no crea ese índice
    (habría que corregirlos a mano)."""
    avisos = []
    for tabla, columna in UNICOS:
        try:
            con.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS ux_{tabla}_{columna} ON {tabla}({columna})")
        except sqlite3.IntegrityError:
            repetidos = [f[0] for f in con.execute(
                f"SELECT {columna} FROM {tabla} WHERE {columna} IS NOT NULL "
                f"GROUP BY {columna} HAVING COUNT(*) > 1")]
            avisos.append((tabla, columna, repetidos))
    con.commit()
    return avisos


def v5_tabla_cursos(con):
    """v5.0 R03: cursos con identificador único (id interno + código único).

    El docente a cargo es una clave foránea: no se puede eliminar un docente
    que tiene cursos (ON DELETE RESTRICT) y, si cambia su N.° de registro,
    el curso lo sigue (ON UPDATE CASCADE)."""
    con.executescript("""
        CREATE TABLE IF NOT EXISTS Curso(
            id INTEGER PRIMARY KEY,
            codigo TEXT NOT NULL UNIQUE,
            nombre TEXT NOT NULL,
            grado TEXT,
            trno INTEGER REFERENCES TeacherData(trno) ON UPDATE CASCADE ON DELETE RESTRICT);
        CREATE INDEX IF NOT EXISTS ix_Curso_trno ON Curso(trno);
    """)


def migrar(con):
    for tabla in v2_columna_foto(con):
        print(f"[migración v2] {tabla}: columna photo_blob agregada")
    cambios = v2_normalizar_numeros(con)
    for tabla, usuario, columna, antes, despues in cambios:
        print(f"[migración v2] {tabla}.{columna} ({usuario}): {antes!r} -> {despues!r}")
    for tabla, cantidad in v5_quitar_duplicados(con):
        print(f"[migración v5] {tabla}: {cantidad} copia(s) exacta(s) eliminada(s)")
    for tabla, columna, repetidos in v5_indices_unicos(con):
        print(f"[migración v5] AVISO {tabla}.{columna} tiene valores repetidos {repetidos}: corrígelos")
    v5_tabla_cursos(con)
