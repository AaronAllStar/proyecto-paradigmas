"""Etapa 1 - Extraccion declarativa (solo SQL).

Cruza Transacciones, Usuarios y Comercios resolviendo las llaves foraneas.
Extrae: id_transaccion, pais_usuario, categoria_comercio, monto_original,
moneda, fecha_hora y estado.

Regla: cero ciclos for/while y cero comprensiones; solo SQL + map/zip/dict.
"""

import sqlite3

from pipeline.config import DB_PATH, COLUMNAS_EXTRAIDAS

# Consulta declarativa con JOINs resolviendo las llaves foraneas.
SQL_EXTRAER = """
SELECT
    t.id           AS id_transaccion,
    u.pais         AS pais_usuario,
    c.categoria    AS categoria_comercio,
    t.monto_original,
    t.moneda,
    t.fecha_hora,
    t.estado
FROM Transacciones AS t
JOIN Usuarios      AS u ON t.usuario_id = u.id
JOIN Comercios     AS c ON t.comercio_id = c.id
"""


def extraer_transacciones(db_path=DB_PATH):
    """Ejecuta la consulta SQL y devuelve una lista de diccionarios.

    No usa ciclos for/while ni comprensiones: mapea cada fila a un diccionario
    con map + zip sobre los nombres de columna.
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(SQL_EXTRAER)
        filas = cursor.fetchall()
    finally:
        conn.close()

    return list(
        map(lambda fila: dict(zip(COLUMNAS_EXTRAIDAS, fila)), filas)
    )


if __name__ == "__main__":  # pragma: no cover - prueba rapida manual
    datos = extraer_transacciones()
    print(f"Filas extraidas: {len(datos)}")
    print("Ejemplo:", datos[0] if datos else None)
