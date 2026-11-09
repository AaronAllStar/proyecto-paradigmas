"""Orquestador del pipeline ETL PayGlobal Fintech.

Ejecuta las etapas en orden:
  Etapa 1: extraccion SQL + transformacion funcional
  Etapa 2: analisis vectorial (numpy) + Map/Reduce (concurrent.futures)
  Etapa 3: exportacion JSON / CSV / Parquet (pandas)

Ejecucion:  python pipeline/main.py   (o python -m pipeline.main)
"""

import os
import sys

import numpy as np

# Asegura que `import pipeline.*` funcione al invocar como script:
#   python pipeline/main.py
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from pipeline.config import asegurar_salidas
from pipeline.etapa1_extraccion import extraer_transacciones
from pipeline.etapa1_transformacion import transformar
from pipeline.etapa2_vectorial import analizar_vectorial
from pipeline.etapa2_mapreduce import map_reduce_fraude
from pipeline.etapa3_exportacion import exportar


def ejecutar_etapa1():
    print("=== Etapa 1: Extraccion y Transformacion ===")
    crudo = extraer_transacciones()
    print(f"  Filas extraidas (SQL JOIN): {len(crudo)}")
    limpio = transformar(crudo)
    print(f"  Filas despues de transformacion: {len(limpio)}")
    if limpio:
        print("  Ejemplo fila limpia:", limpio[0])
    return limpio


def ejecutar_etapa2(limpio):
    print("\n=== Etapa 2: Analisis Vectorial + Map/Reduce ===")
    vectorial = analizar_vectorial(limpio)
    print(f"  Total transacciones: {vectorial['total_transacciones']}")
    print(f"  Volumen total USD: {vectorial['volumen_total_usd']:.2f}")
    print(f"  Completadas: {vectorial['completadas']}")
    print(f"  mu_usd: {vectorial['mu_usd']:.2f} | sigma_usd: {vectorial['sigma_usd']:.2f}")
    print(f"  Anomalias |Z|>3: {vectorial['anomalias_conteo']}")
    print(f"  Vacum final: {vectorial['vacum_final']:.2f}")
    print("  Ejemplo fila vectorial (orden fecha):", {
        "fecha": str(vectorial["fechas_ord"][0]),
        "monto_usd": round(float(vectorial["monto_usd_ord"][0]), 2),
        "zscore": round(float(vectorial["zscore_ord"][0]), 2),
        "vacum": round(float(vectorial["vacum"][0]), 2),
    })

    fraude = map_reduce_fraude()
    print("  Map/Reduce por resolucion:", fraude["por_resolucion"])
    print("  Map/Reduce por categoria:", fraude["por_categoria"])
    return vectorial, fraude


def ejecutar_etapa3(limpio, vectorial, fraude):
    print("\n=== Etapa 3: Exportacion declarativa ===")
    rutas = exportar(limpio, vectorial, fraude)
    for nombre, ruta in rutas.items():
        print(f"  {nombre}: {ruta}")
    return rutas


def main():
    asegurar_salidas()
    limpio = ejecutar_etapa1()
    vectorial, fraude = ejecutar_etapa2(limpio)
    ejecutar_etapa3(limpio, vectorial, fraude)
    print("\nPipeline completado (Etapa 1 + 2 + 3).")


if __name__ == "__main__":
    main()
