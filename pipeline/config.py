"""Configuracion centralizada del pipeline ETL PayGlobal Fintech.

Rutas, tasas de cambio y constantes usadas por las etapas del pipeline.
"""

import os

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_NAME = "fintech_transacciones.db"
DB_PATH = os.path.join(BASE_DIR, DB_NAME)

SALIDAS_DIR = os.path.join(BASE_DIR, "salidas")
CSV_LIMPIAS = os.path.join(SALIDAS_DIR, "transacciones_limpias.csv")
PARQUET_SERIE = os.path.join(SALIDAS_DIR, "serie_acumulada.parquet")
JSON_RESOLUCION = os.path.join(SALIDAS_DIR, "alertas_resolucion.json")

# Columnas esperadas del resultado de la extraccion (etapa 1)
COLUMNAS_EXTRAIDAS = [
    "id_transaccion",
    "pais_usuario",
    "categoria_comercio",
    "monto_original",
    "moneda",
    "fecha_hora",
    "estado",
]

# ---------------------------------------------------------------------------
# Tasas de cambio (Etapa 2 - conversion a USD)
# Enunciado: 1 USD = 500 CRC | 17 MXN | 4000 COP
# Factor = monto_original * TCambio para pasar a USD:
#   CRC -> 1/500, MXN -> 1/17, COP -> 1/4000, USD -> 1.0
# ---------------------------------------------------------------------------
TASA_CRC = 1.0 / 500.0
TASA_MXN = 1.0 / 17.0
TASA_COP = 1.0 / 4000.0
TASA_USD = 1.0

TASAS_CAMBIO = {
    "USD": TASA_USD,
    "CRC": TASA_CRC,
    "MXN": TASA_MXN,
    "COP": TASA_COP,
}

# Valor por defecto para usuarios sin pais
PAIS_DEFECTO = "Internacional"

# Umbral de anomalia por Z-score (|Z| > 3)
UMBRAL_ZSCORE = 3.0

# Umbral para descartar outliers de tiempo de investigacion (dias)
UMBRAL_TIEMPO_OUTLIER = 1000.0


def asegurar_salidas():
    """Crea el directorio de salidas si no existe."""
    os.makedirs(SALIDAS_DIR, exist_ok=True)
