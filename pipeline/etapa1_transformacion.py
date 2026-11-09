"""Etapa 1 - Transformacion funcional (solo map, filter y lambda).

Funciones puras: no mutan estado global ni tienen efectos secundarios.
Cada función recibe una fila (dict) y devuelve una NUEVA fila.

Transformaciones:
1. Fechas: descarta filas con fecha_hora None o 'N/A' (filter).
   Si fecha_hora es timestamp UNIX (solo digitos), lo convierte a ISO 8601.
2. Montos: limpia simbolos no numericos, convierte a float y aplica valor
   absoluto si es negativo.
3. Usuarios sin pais: reemplaza pais_usuario nulo por 'Internacional'.
"""

import re
from datetime import datetime

from pipeline.config import PAIS_DEFECTO

# ---------------------------------------------------------------------------
# Helpers puros (sin efectos secundarios)
# ---------------------------------------------------------------------------

def _es_timestamp_unix(valor):
    """Devuelve True si valor es una cadena compuesta solo por digitos."""
    return isinstance(valor, str) and valor.isdigit()


def convertir_fecha_a_iso(valor):
    """Convierte un timestamp UNIX a ISO 8601. Devuelve el valor igual si
    ya es una fecha ISO o no es aplicable. Retorna None para None/'N/A'."""
    if valor is None or valor == "N/A":
        return None
    if _es_timestamp_unix(valor):
        return datetime.fromtimestamp(int(valor)).isoformat()
    return valor


def limpiar_monto_a_float(valor):
    """Limpia simbolos no numericos de un monto, lo convierte a float y
    aplica valor absoluto si es negativo. Devuelve 0.0 ante error."""
    try:
        if isinstance(valor, str):
            limpio = re.sub(r"[^0-9.\-]", "", valor)
        else:
            limpio = str(valor)
        return abs(float(limpio))
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# Transformaciones de fila (puras: copian el diccionario antes de modificar)
# ---------------------------------------------------------------------------

def fila_fecha_valida(fila):
    """Predicate puro: True si la fila tiene fecha_hora utilizable."""
    fh = fila.get("fecha_hora")
    return fh is not None and fh != "N/A"


def normalizar_fecha(fila):
    """Devuelve copia de la fila con fecha_hora en ISO 8601."""
    nueva = dict(fila)
    nueva["fecha_hora"] = convertir_fecha_a_iso(fila.get("fecha_hora"))
    return nueva


def normalizar_monto(fila):
    """Devuelve copia de la fila con monto_original como float >= 0."""
    nueva = dict(fila)
    nueva["monto_original"] = limpiar_monto_a_float(fila.get("monto_original"))
    return nueva


def normalizar_pais(fila):
    """Devuelve copia de la fila con pais_usuario reemplazado si es nulo."""
    nueva = dict(fila)
    if nueva.get("pais_usuario") is None:
        nueva["pais_usuario"] = PAIS_DEFECTO
    return nueva


# ---------------------------------------------------------------------------
# Orquestador funcional de la transformacion
# ---------------------------------------------------------------------------

def transformar(filas):
    """Aplica todas las transformaciones funcionalmente.

    Orden:
      1. filter  : descarta filas sin fecha valida
      2. map     : normaliza fecha a ISO 8601
      3. map     : normaliza monto a float (absoluto)
      4. map     : reemplaza pais nulo por 'Internacional'
    """
    sin_fecha_invalida = list(
        filter(lambda f: fila_fecha_valida(f), filas)
    )
    con_fecha_iso = list(
        map(lambda f: normalizar_fecha(f), sin_fecha_invalida)
    )
    con_monto_limpio = list(
        map(lambda f: normalizar_monto(f), con_fecha_iso)
    )
    con_pais_defecto = list(
        map(lambda f: normalizar_pais(f), con_monto_limpio)
    )
    return con_pais_defecto


if __name__ == "__main__":  # pragma: no cover - prueba rapida manual
    from pipeline.etapa1_extraccion import extraer_transacciones

    crudo = extraer_transacciones()
    limpio = transformar(crudo)
    print(f"Crudo: {len(crudo)} | Limpio: {len(limpio)}")
    print("Ejemplo limpio:", limpio[0] if limpio else None)
