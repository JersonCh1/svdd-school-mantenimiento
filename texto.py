"""Comparación de textos sin tildes ni mayúsculas (v6.0 — MR-101).

LIKE de SQLite solo ignora mayúsculas en letras ASCII: «lucia» no encontraba
a «Lucía» y «JOSÉ» no encontraba a «José». Se quita la tilde (forma NFD sin
marcas diacríticas) y se pasa a minúsculas con casefold() antes de comparar.
"""

import unicodedata


def plano(texto):
    """'Lucía Ñañez' -> 'lucia nanez'. None se queda en None."""
    if texto is None:
        return None
    descompuesto = unicodedata.normalize("NFD", str(texto))
    return "".join(c for c in descompuesto if not unicodedata.combining(c)).casefold()
