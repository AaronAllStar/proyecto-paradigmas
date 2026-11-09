"""Etapa 2 - Analisis vectorial con numpy (sin bucles for/while ni comprensiones).

Operaciones:
1. Conversion a USD con broadcasting: MUSD = MOriginal x TCambio.
   Tasas: CRC = 1/500, MXN = 1/17, COP = 1/4000, USD = 1.0 (np.select).
2. Z-score global: Z = (MUSD - mu) / sigma.
3. Volumen acumulado: ordena por fecha, filtra estado == 'COMPLETADA' y
   calcula Vacum con np.cumsum.

Devuelve claves en ORDEN ORIGINAL de entrada (para exportacion CSV)
y claves con sufijo _ord ordenadas por fecha (para Parquet).
"""

import numpy as np

from pipeline.config import TASAS_CAMBIO, UMBRAL_ZSCORE


def _extraer_columnas(filas):
    """Extrae columnas de la lista de diccionarios como arrays numpy.

    Usa map + list (nunca comprensiones ni ciclos).
    """
    ids = np.array(list(map(lambda f: f.get("id_transaccion"), filas)))
    monedas = np.array(list(map(lambda f: f.get("moneda"), filas)))
    montos = np.array(
        list(map(lambda f: float(f.get("monto_original", 0.0) or 0.0), filas)),
        dtype=float,
    )
    fechas = np.array(list(map(lambda f: f.get("fecha_hora"), filas)))
    estados = np.array(list(map(lambda f: f.get("estado"), filas)))
    return ids, monedas, montos, fechas, estados


def convertir_a_usd(monedas, montos):
    """Convierte montos a USD aplicando la tasa de cambio por moneda.

    Aplica la tasa con np.select (mapeo vectorizado) y broadcasting:
    MUSD = MOriginal x TCambio.
    """
    claves = np.array(list(TASAS_CAMBIO.keys()))
    valores = np.array(list(TASAS_CAMBIO.values()), dtype=float)
    condiciones = list(map(lambda k: monedas == k, claves))
    tasas = np.select(condiciones, list(valores), default=1.0)
    return montos * tasas  # broadcasting elemento a elemento


def calcular_zscore(musd):
    """Z-score global: Z = (MUSD - mu) / sigma."""
    mu = float(np.mean(musd))
    sigma = float(np.std(musd))
    if sigma > 0:
        z = (musd - mu) / sigma
    else:
        z = np.zeros_like(musd)
    return z, mu, sigma


def volumen_acumulado(fechas, musd, estados):
    """Serie temporal ordenada por fecha con volumen acumulado de COMPLETADA.

    Ordena por fecha (strings ISO 8601 se ordenan lexicograficamente),
    filtra estado == 'COMPLETADA' (mascara) y calcula Vacum con np.cumsum.
    Devuelve arrays ya ordenados por fecha.
    """
    orden = np.argsort(fechas)  # ordenamiento vectorial
    fechas_ord = fechas[orden]
    musd_ord = musd[orden]
    estados_ord = estados[orden]

    mascara_completada = estados_ord == "COMPLETADA"
    montos_completada = np.where(mascara_completada, musd_ord, 0.0)
    vacum = np.cumsum(montos_completada)  # acumulacion vectorial

    return fechas_ord, musd_ord, estados_ord, mascara_completada, vacum, orden


def detectar_anomalias(z):
    """Mascaras de anomalia: |Z| > umbral."""
    return np.abs(z) > UMBRAL_ZSCORE


def analizar_vectorial(filas):
    """Ejecuta todo el analisis vectorial y devuelve un diccionario de resultados.

    Claves en orden original de entrada: id_transaccion, monedas, montos_original,
    fechas, estados, monto_usd, zscore, anomillas, mu_usd, sigma_usd,
    total_transacciones, volumen_total_usd, completadas.
    Claves ordenadas por fecha (sufijo _ord): fechas_ord, estados_ord,
    monto_usd_ord, zscore_ord, mascara_completada_ord, vacum, df_parquet.
    """
    ids, monedas, montos, fechas, estados = _extraer_columnas(filas)
    musd = convertir_a_usd(monedas, montos)          # orden original
    z, mu, sigma = calcular_zscore(musd)             # orden original
    anomalias = detectar_anomalias(z)                # orden original

    fechas_ord, musd_ord, estados_ord, mascara_completada, vacum, orden = (
        volumen_acumulado(fechas, musd, estados)
    )
    z_ord = z[orden]
    anomalias_ord = anomalias[orden]

    import pandas as pd

    df_parquet = pd.DataFrame(
        {
            "fecha_hora": fechas_ord,
            "estado": estados_ord,
            "monto_usd": musd_ord,
            "zscore": z_ord,
            "vacum": vacum,
        }
    )

    return {
        # --- orden original (para CSV / alineamiento) ---
        "id_transaccion": ids,
        "monedas": monedas,
        "montos_original": montos,
        "fechas": fechas,
        "estados": estados,
        "monto_usd": musd,
        "zscore": z,
        "anomillas": anomalias,
        # --- metricas globales ---
        "mu_usd": mu,
        "sigma_usd": sigma,
        "total_transacciones": int(len(filas)),
        "volumen_total_usd": float(np.sum(musd)),
        "completadas": int(np.sum(estados_ord == "COMPLETADA")),
        "anomalias_conteo": int(np.count_nonzero(anomalias)),
        "vacum_final": float(vacum[-1]) if len(vacum) else 0.0,
        # --- ordenado por fecha (para Parquet / grafica linea) ---
        "fechas_ord": fechas_ord,
        "estados_ord": estados_ord,
        "monto_usd_ord": musd_ord,
        "zscore_ord": z_ord,
        "anomillas_ord": anomalias_ord,
        "mascara_completada_ord": mascara_completada,
        "vacum": vacum,
        "df_parquet": df_parquet,
    }
