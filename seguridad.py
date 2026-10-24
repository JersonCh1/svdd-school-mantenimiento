"""Contraseñas con hash (v6.0 — MR-105).

La base guardaba las contraseñas en texto plano: cualquiera que abriera
testdata.db (un visor de SQLite, una copia de respaldo) las podía leer.
Ahora se guarda solo un hash PBKDF2-SHA256 con una sal aleatoria por usuario:

    pbkdf2_sha256$<iteraciones>$<sal en hex>$<hash en hex>

Con la sal, dos usuarios con la misma contraseña tienen hashes distintos, y
las iteraciones encarecen probar contraseñas por fuerza bruta.
"""

import hashlib
import hmac
import secrets

ALGORITMO = "pbkdf2_sha256"
ITERACIONES = 120_000


def es_hash(valor):
    return isinstance(valor, str) and valor.startswith(ALGORITMO + "$") and valor.count("$") == 3


def hashear(clave, sal=None, iteraciones=ITERACIONES):
    sal = sal or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), bytes.fromhex(sal), iteraciones)
    return f"{ALGORITMO}${iteraciones}${sal}${digest.hex()}"


def verificar(clave, guardada):
    """True si 'clave' corresponde al hash guardado. Un valor que no es hash
    (texto plano que no pasó por la migración) nunca se acepta."""
    if clave is None or not es_hash(guardada):
        return False
    _alg, iteraciones, sal, _digest = guardada.split("$")
    try:
        calculado = hashear(clave, sal, int(iteraciones))
    except ValueError:  # hash corrupto
        return False
    # compare_digest tarda lo mismo acierte o no: no da pistas por el tiempo.
    return hmac.compare_digest(calculado, guardada)
