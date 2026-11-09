"""Etapa 3 - Exportacion declarativa con pandas (APIs de alto nivel).

Exporta:
  salidas/alertas_resolucion.json  -> diccionario consolidado del Map/Reduce
  salidas/transacciones_limpias.csv -> todas las transacciones limpias con
                                       monto_usd y zscore
  salidas/serie_acumulada.parquet   -> serie temporal ordenada con Vacum
                                       (compresion columnar)

Regla: no abrir ni escribir archivos linea por linea. Solo to_json / to_csv /
to_parquet de pandas.
"""

import json
import pandas as pd

from pipeline.config import (
    JSON_RESOLUCION,
    CSV_LIMPIAS,
    PARQUET_SERIE,
    asegurar_salidas,
)


def exportar_json(alertas, ruta=JSON_RESOLUCION):
    """Escribe el diccionario del Map/Reduce a JSON con pandas.

    Construye el objeto con pandas y lo vuelca de una sola vez (no linea por
    linea) para que quede como un objeto JSON plano, no como una lista.
    """
    df = pd.DataFrame([alertas])
    objeto = json.loads(df.to_json(orient="records", force_ascii=False))[0]
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(objeto, f, ensure_ascii=False, indent=2)


def exportar_csv(limpio, vectorial, ruta=CSV_LIMPIAS):
    """Escribe todas las transacciones limpias con monto_usd y zscore a CSV.

    Alinea monto_usd y zscore por id_transaccion (orden original de la etapa 1).
    """
    df = pd.DataFrame(limpio)

    df_alineado = pd.DataFrame(
        {
            "id_transaccion": vectorial["id_transaccion"],
            "monto_usd": vectorial["monto_usd"],
            "zscore": vectorial["zscore"],
        }
    )

    df = df.merge(df_alineado, on="id_transaccion", how="left")

    columnas_base = list(
        filter(lambda c: c not in ("monto_usd", "zscore"), df.columns)
    )
    column_order = columnas_base + ["monto_usd", "zscore"]
    df = df[column_order]

    df.to_csv(ruta, index=False, encoding="utf-8")


def exportar_parquet(vectorial, ruta=PARQUET_SERIE):
    """Escribe la serie temporal ordenada con Vacum a Parquet (compresion columnar)."""
    df = vectorial["df_parquet"].copy()
    df.to_parquet(ruta, index=False, compression="snappy")


def exportar(limpio, vectorial, alertas):
    """Ejecuta las tres exportaciones y devuelve las rutas generadas."""
    asegurar_salidas()
    exportar_json(alertas)
    exportar_csv(limpio, vectorial)
    exportar_parquet(vectorial)
    return {
        "json": JSON_RESOLUCION,
        "csv": CSV_LIMPIAS,
        "parquet": PARQUET_SERIE,
    }
