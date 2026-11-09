"""Prueba automatica con ast: verifica que no hay nodos For ni While
en los modulos de la etapa 1 y etapa 2.

Regla de evaluacion: cero ciclos for/while (ni comprensiones como sustituto
de map/filter) en etapa1_*.py y etapa2_*.py.
"""

import ast
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIPELINE_DIR = os.path.join(BASE_DIR, "pipeline")

MODULOS_REVISADOS = [
    "etapa1_extraccion.py",
    "etapa1_transformacion.py",
    "etapa2_vectorial.py",
    "etapa2_mapreduce.py",
    "etapa3_exportacion.py",
]


def _modulo_tiene_ciclo(ruta):
    with open(ruta, "r", encoding="utf-8") as f:
        arbol = ast.parse(f.read(), filename=ruta)
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.For, ast.While)):
            return True
    return False


def test_no_ciclos_for_while_en_etapas():
    for nombre in MODULOS_REVISADOS:
        ruta = os.path.join(PIPELINE_DIR, nombre)
        if not os.path.exists(ruta):
            continue  # El modulo aun no se ha creado; no falla por eso
        assert not _modulo_tiene_ciclo(ruta), (
            f"{nombre} contiene ciclos For o While (prohibido en etapa 1/2)"
        )
