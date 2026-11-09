# Pipeline ETL Transaccional y Detección de Fraude (PayGlobal Fintech)

Proyecto integrador de Ingeniería de Datos. Backend en **Python** (paradigma funcional y vectorial con **SQLite3**, **numpy**, **pandas**, **pyarrow**). Frontend en **HTML5 + JavaScript vanilla** (sin frameworks) con Chart.js, PapaParse y hyparquet desde CDN.

## Estructura del proyecto

```
proyecto-paradigmas/
├── script_generador_de_datos_fintech.py   # Generador de DB (no se modifica)
├── fintech_transacciones.db               # Base de datos SQLite generada
├── requirements.txt
├── README.md
├── pipeline/
│   ├── __init__.py
│   ├── config.py                          # Rutas, tasas de cambio, constantes
│   ├── etapa1_extraccion.py               # SQL con JOINs (lista de diccionarios)
│   ├── etapa1_transformacion.py           # Funciones puras con map/filter/lambda
│   ├── etapa2_vectorial.py                # numpy: broadcasting, z-score, cumsum
│   ├── etapa2_mapreduce.py                # Map/Reduce con ThreadPoolExecutor
│   ├── etapa3_exportacion.py              # pandas: JSON, CSV, Parquet
│   └── main.py                            # Orquestador del flujo completo
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── tests/
│   ├── test_no_loops.py                   # Prueba ast: cero For/While en etapas 1, 2 y 3
│   └── test_pipeline_integration.py       # Pruebas integracion: limpieza, vectorial y salidas
└── salidas/                               # Archivos generados por el pipeline
    ├── alertas_resolucion.json
    ├── transacciones_limpias.csv
    └── serie_acumulada.parquet
```

## Esquema de la base de datos

Se genera con `script_generador_de_datos_fintech.py`. Tablas y columnas usadas:

| Tabla | Columnas relevantes |
| ------- | --------------------- |
| `Usuarios` | `id`, `pais` (puede ser `None`), `tipo_cuenta`, `fecha_registro` |
| `Comercios` | `id`, `nombre`, `categoria`, `nivel_riesgo` |
| `Transacciones` | `id` (→ id_transaccion), `usuario_id`, `comercio_id`, `monto_original`, `moneda`, `fecha_hora`, `estado` |
| `Reclamos_Fraude` | `id`, `transaccion_id`, `resolucion`, `tiempo_investigacion_dias` (→ Tiempo_Dias) |

La extracción (Etapa 1) cruza `Transacciones ⋈ Usuarios ⋈ Comercios` resolviendo las llaves foráneas.

## Instalación

```cmd
pip install numpy pandas pyarrow pytest
```

O bien:

```cmd
pip install -r requirements.txt
```

## Ejecución del pipeline

Desde la raíz del proyecto:

```cmd
python pipeline/main.py
```

Esto ejecuta las tres etapas en orden y genera los archivos en `salidas/`:

1. **Etapa 1** — Extracción SQL (JOINs) + transformación funcional (`map`/`filter`/`lambda`):
   - descarta filas con `fecha_hora` `None`/`'N/A'`
   - convierte timestamps UNIX a ISO 8601
   - limpia montos con símbolos (`$150.50` → `150.50`) y aplica valor absoluto a negativos
   - reemplaza `pais_usuario` nulo por `'Internacional'`
2. **Etapa 2** — Análisis vectorial con `numpy` (sin bucles):
   - conversión a USD con `np.select` + broadcasting (CRC = 1/500, MXN = 1/17, COP = 1/4000, USD = 1.0)
   - z-score global `(MUSD − μ) / σ`
   - volumen acumulado con `np.cumsum` sobre estado `COMPLETADA` ordenado por fecha
   - Map/Reduce con `ThreadPoolExecutor` sobre `Reclamos_Fraude`: `(Resolucion, (Tiempo_Dias, 1))`, promedio por resolución, descarta outliers `> 1000` días; además `por_categoria` (JOIN a Comercios)
3. **Etapa 3** — Exportación declarativa con pandas (`to_csv` / `to_parquet` / `to_json`):
   - `salidas/transacciones_limpias.csv` — columnas + `monto_usd` y `zscore`
   - `salidas/serie_acumulada.parquet` — serie temporal ordenada con `Vacum` (compresión snappy)
   - `salidas/alertas_resolucion.json` — `{"por_resolucion": {...}, "por_categoria": {...}}`

## Pruebas automáticas

```cmd
python -m pytest tests/ -v
```

`tests/test_no_loops.py` usa el módulo `ast` para verificar que no existen nodos `For` ni `While` en `etapa1_*.py`, `etapa2_*.py` y `etapa3_*.py`.

## Visualización del Frontend

El frontend soporta dos modos de uso:

### Opción 1: Modo Offline Inmediato (Recomendado sin servidor)
Puedes abrir directamente el archivo [frontend/index.html](file:///d:/proyecto-paradigmas/frontend/index.html) haciendo **doble clic en el explorador de Windows** (protocolo `file:///`). El dashboard arranca de inmediato con todos los resultados del análisis vectorial, métricas globales, gráficas interactivas y transacciones cargadas localmente (sin errores de CORS ni bloqueos de localhost).

### Opción 2: Servidor HTTP Local
Si deseas servirlo mediante servidor web:
```cmd
# Desde la RAÍZ del proyecto
python -m http.server 8000
```
Luego abre en el navegador:
```
http://localhost:8000/frontend/
```
El panel cuenta con un botón en la cabecera para sincronizar o cargar archivos CSV locales en cualquier momento.

### Requisito previo

Generar los archivos de salida antes de abrir el frontend:

```cmd
python pipeline/main.py
```

## Funcionalidades del frontend

- **KPIs reactivos**: total de transacciones, volumen total en USD y porcentaje de transacciones `COMPLETADAS`. Recalculan al aplicar filtros.
- **Filtros interactivos**: país, categoría de comercio, estado y rango de fechas (select + inputs `date`).
- **Gráfica de línea** (Chart.js): volumen acumulado `Vacum` en el tiempo.
- **Histograma de Z-scores** (Chart.js): bins con `|Z| > 3` coloreados en rojo para resaltar anomalías.
- **Gráfica de barras** (Chart.js): tiempo promedio de resolución por tipo de resolución, y selector para desglose por categoría de comercio.
- **Tabla filtrable y paginada**: paginación fluida (50 filas por página), ordenamiento interactivo por columna y botón "Descargar CSV" que exporta la totalidad de las filas filtradas.

## Decisiones de diseño

1. **Ambiguedad Map/Reduce**: el enunciado dice "por Categoría" en el Reduce, pero el Map emite `Resolucion`. Se implementó agrupamiento por `Resolucion` (lo que emite el Map) y, al ser sencillo, se agregó además `por_categoria` mediante un JOIN `Reclamos_Fraude → Transacciones → Comercios`. Ambas claves se exportan en `alertas_resolucion.json`. Documentado en este README.
2. **Generador de dataset**: el script `script_generador_de_datos_fintech.py` declara `pais TEXT NOT NULL` pero inyecta `None` para ~1/6 de usuarios, lo que causa `IntegrityError`. No se modificó ese archivo (por instrucciones); la base se generó con `pais` nullable, coherente con el `None` del generador y con la transformación de la Etapa 1 que lo reemplaza por `'Internacional'`.
3. **Cero ciclos en etapas 1 y 2**: `etapa1_extraccion.py`, `etapa1_transformacion.py`, `etapa2_vectorial.py` y `etapa2_mapreduce.py` usan únicamente `map`, `filter`, `lambda`, `zip`, `dict`, `np.select`, `np.bincount`, comprensiones de numpy y `itertools.chain` — sin `for`/`while` ni comprensiones de Python como sustituto de `map`/`filter`. Verificado con prueba `ast`.
4. **Frontend sin frameworks**: HTML5 + JavaScript vanilla, librerías de CDN con versiones fijadas (verificadas en npm): Chart.js 4.6.1, PapaParse 5.7.0, hyparquet 1.33.0 (módulo ESM desde jsDelivr).
5. **Rutas del frontend**: relativas a la raíz del proyecto (`../salidas/...`) para funcionar bajo `python -m http.server 8000`.

## Versiones de librerías CDN (verificadas en npm)

| Librería | Versión | URL CDN |
| ---------- | --------- | --------- |
| Chart.js | 4.6.1 | `https://cdn.jsdelivr.net/npm/chart.js@4.6.1/dist/chart.umd.min.js` |
| PapaParse | 5.7.0 | `https://cdn.jsdelivr.net/npm/papaparse@5.7.0/papaparse.min.js` |
| hyparquet | 1.33.0 | `https://cdn.jsdelivr.net/npm/hyparquet@1.33.0/src/index.js` (ESM) |
