"""Pruebas de integracion del Pipeline ETL PayGlobal Fintech.

Verifica la calidad y consistencia de los datos en todas las etapas:
- Etapa 1: extraccion y transformacion (limpieza de fechas, montos y paises).
- Etapa 2: conversion vectorial USD, z-score y Map/Reduce de fraude.
- Etapa 3: existencia y esquema de archivos exportados (CSV, JSON, Parquet).
"""

import json
import os
import sqlite3
import numpy as np
import pandas as pd
import pytest

from pipeline.config import (
    DB_PATH,
    CSV_LIMPIAS,
    JSON_RESOLUCION,
    PARQUET_SERIE,
    TASAS_CAMBIO,
    UMBRAL_TIEMPO_OUTLIER,
)
from pipeline.etapa1_extraccion import extraer_transacciones
from pipeline.etapa1_transformacion import transformar
from pipeline.etapa2_vectorial import analizar_vectorial
from pipeline.etapa2_mapreduce import map_reduce_fraude


@pytest.fixture(scope="module")
def datos_limpios():
    crudo = extraer_transacciones()
    return transformar(crudo)


def test_etapa1_limpieza_fechas_y_montos(datos_limpios):
    """Verifica que no queden fechas invalidas, montos negativos ni paises nulos."""
    assert len(datos_limpios) > 0, "Debe haber transacciones limpias"

    for fila in datos_limpios[:500]:
        # Fecha debe ser valida y no 'N/A' ni None
        assert fila["fecha_hora"] is not None
        assert fila["fecha_hora"] != "N/A"
        assert "T" in fila["fecha_hora"] or len(fila["fecha_hora"]) >= 10

        # Monto debe ser float >= 0
        assert isinstance(fila["monto_original"], float)
        assert fila["monto_original"] >= 0.0

        # Pais no debe ser nulo
        assert fila["pais_usuario"] is not None
        assert fila["pais_usuario"] != ""


def test_etapa2_analisis_vectorial(datos_limpios):
    """Verifica metricas globales, conversion USD y serie acumulada."""
    vectorial = analizar_vectorial(datos_limpios)

    assert vectorial["total_transacciones"] == len(datos_limpios)
    assert vectorial["volumen_total_usd"] > 0
    assert vectorial["mu_usd"] > 0
    assert vectorial["sigma_usd"] > 0
    assert vectorial["vacum_final"] > 0

    # Vacum debe ser no decreciente
    vacum = vectorial["vacum"]
    assert np.all(np.diff(vacum) >= -1e-6), "Vacum debe ser monotonicamente no decreciente"


def test_etapa2_map_reduce_fraude():
    """Verifica que Map/Reduce descarte outliers > 1000 dias y agrupe correctamente."""
    fraude = map_reduce_fraude()

    assert "por_resolucion" in fraude
    assert "por_categoria" in fraude

    for res, datos in fraude["por_resolucion"].items():
        assert "tiempo_promedio_dias" in datos
        assert "conteo" in datos
        assert datos["tiempo_promedio_dias"] <= UMBRAL_TIEMPO_OUTLIER
        assert datos["conteo"] > 0


def test_etapa3_archivos_exportados():
    """Verifica que los tres artefactos requeridos existan y sean validos."""
    assert os.path.exists(CSV_LIMPIAS), "El CSV debe existir"
    assert os.path.exists(JSON_RESOLUCION), "El JSON debe existir"
    assert os.path.exists(PARQUET_SERIE), "El Parquet debe existir"

    # CSV
    df_csv = pd.read_csv(CSV_LIMPIAS)
    assert "monto_usd" in df_csv.columns
    assert "zscore" in df_csv.columns
    assert "id_transaccion" in df_csv.columns
    assert len(df_csv) > 0

    # JSON
    with open(JSON_RESOLUCION, "r", encoding="utf-8") as f:
        datos_json = json.load(f)
    assert "por_resolucion" in datos_json
    assert "por_categoria" in datos_json

    # Parquet
    df_parquet = pd.read_parquet(PARQUET_SERIE)
    assert "vacum" in df_parquet.columns
    assert "fecha_hora" in df_parquet.columns
    assert len(df_parquet) > 0

