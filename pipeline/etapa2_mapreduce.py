"""Etapa 2 - Map/Reduce sobre Reclamos_Fraude con concurrent.futures.

Map: divide los reclamos en fragmentos y cada hilo emite pares
    (Resolucion, (Tiempo_Dias, 1)).
Reduce: consolida los pares, calcula el tiempo promedio por resolucion y
    descarta outliers con Tiempo_Dias > 1000.
Usa ThreadPoolExecutor.

Nota de ambigüedad: el enunciado dice "por Categoria" en el Reduce, pero el
Map emite Resolucion. Se agrupa por Resolucion y, como es sencillo, se agrega
adicionalmente el desglose por Categoria (JOIN Reclamos_Fraude ->
Transacciones -> Comercios). Documentado en README.
"""

import itertools
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from pipeline.config import DB_PATH, UMBRAL_TIEMPO_OUTLIER

N_HILOS = 4


def _obtener_columnas(db_path, consulta):
    """Ejecuta una consulta de 2 columnas y devuelve dos arrays numpy."""
    conn = sqlite3.connect(db_path)
    try:
        filas = conn.execute(consulta).fetchall()
    finally:
        conn.close()
    col1 = np.array(list(map(lambda f: f[0], filas)))
    col2 = np.array(
        list(map(lambda f: (float(f[1]) if f[1] is not None else np.nan), filas)),
        dtype=float,
    )
    return col1, col2


def _filtrar_validos(categorias, tiempos):
    """Descarta tiempos nulos y outliers mayores al umbral."""
    valida = (~np.isnan(tiempos)) & (tiempos <= UMBRAL_TIEMPO_OUTLIER)
    return categorias[valida], tiempos[valida]


def _procesar_fragmento(cats_frag, tiempos_frag):
    """Map de un fragmento: emite lista de (categoria, (tiempo, 1))."""
    unos = [1] * len(tiempos_frag)
    return list(zip(cats_frag.tolist(), list(zip(tiempos_frag.tolist(), unos))))


def _reducir(pares):
    """Reduce: consolida pares, promedio por categoria, sin ciclos."""
    if not pares:
        return {}
    cats = np.array(list(map(lambda p: p[0], pares)))
    tiempos = np.array(list(map(lambda p: p[1][0], pares)), dtype=float)
    unos = np.array(list(map(lambda p: p[1][1], pares)), dtype=float)

    unicos, inversa = np.unique(cats, return_inverse=True)
    suma_tiempos = np.bincount(inversa, weights=tiempos)
    conteos = np.bincount(inversa, weights=unos)
    promedios = suma_tiempos / np.where(conteos == 0, 1, conteos)

    items = list(
        map(
            lambda u, t, c: (
                u,
                {"tiempo_promedio_dias": round(float(t), 2), "conteo": int(c)},
            ),
            unicos.tolist(),
            promedios.tolist(),
            conteos.tolist(),
        )
    )
    return dict(items)


def map_reduce_por_resolucion(db_path=DB_PATH, n_hilos=N_HILOS):
    """Map/Reduce agrupando por Resolucion."""
    consulta = (
        "SELECT resolucion, tiempo_investigacion_dias FROM Reclamos_Fraude"
    )
    resoluciones, tiempos = _obtener_columnas(db_path, consulta)
    resoluciones, tiempos = _filtrar_validos(resoluciones, tiempos)

    if len(resoluciones) == 0:
        return {}

    frags_cats = np.array_split(resoluciones, n_hilos)
    frags_tiem = np.array_split(tiempos, n_hilos)

    with ThreadPoolExecutor(max_workers=n_hilos) as executor:
        resultados = list(
            executor.map(_procesar_fragmento, frags_cats, frags_tiem)
        )

    pares = list(itertools.chain.from_iterable(resultados))
    return _reducir(pares)


def map_reduce_por_categoria(db_path=DB_PATH, n_hilos=N_HILOS):
    """Map/Reduce opcional agrupando por Categoria (JOIN para obtenerla)."""
    consulta = """
        SELECT c.categoria, r.tiempo_investigacion_dias
        FROM Reclamos_Fraude AS r
        JOIN Transacciones AS t ON r.transaccion_id = t.id
        JOIN Comercios AS c ON t.comercio_id = c.id
    """
    categorias, tiempos = _obtener_columnas(db_path, consulta)
    categorias, tiempos = _filtrar_validos(categorias, tiempos)

    if len(categorias) == 0:
        return {}

    frags_cats = np.array_split(categorias, n_hilos)
    frags_tiem = np.array_split(tiempos, n_hilos)

    with ThreadPoolExecutor(max_workers=n_hilos) as executor:
        resultados = list(
            executor.map(_procesar_fragmento, frags_cats, frags_tiem)
        )

    pares = list(itertools.chain.from_iterable(resultados))
    return _reducir(pares)


def map_reduce_fraude(db_path=DB_PATH, n_hilos=N_HILOS):
    """Ejecuta Map/Reduce por resolucion y por categoria."""
    return {
        "por_resolucion": map_reduce_por_resolucion(db_path, n_hilos),
        "por_categoria": map_reduce_por_categoria(db_path, n_hilos),
    }


if __name__ == "__main__":  # pragma: no cover - prueba rapida manual
    resultado = map_reduce_fraude()
    print("Por resolucion:", resultado["por_resolucion"])
    print("Por categoria:", resultado["por_categoria"])
