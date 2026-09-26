"""Migraciones de datos de testdata.db. Todas son idempotentes: se ejecutan
al iniciar la aplicación y no hacen nada si la base ya está actualizada."""

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


def migrar(con):
    for tabla in v2_columna_foto(con):
        print(f"[migración v2] {tabla}: columna photo_blob agregada")
    cambios = v2_normalizar_numeros(con)
    for tabla, usuario, columna, antes, despues in cambios:
        print(f"[migración v2] {tabla}.{columna} ({usuario}): {antes!r} -> {despues!r}")
