/* PayGlobal Fintech - Frontend (HTML5 + JS vanilla, sin frameworks)

Carga únicamente los archivos de salidas/. No re-ejecuta el pipeline ni se
conecta a la base de datos. Debe servirse desde la raíz del proyecto:
    python -m http.server 8000
    http://localhost:8000/frontend/

Rutas relativas a la raíz: ../salidas/transacciones_limpias.csv, etc.
*/

import * as hyparquet from "https://cdn.jsdelivr.net/npm/hyparquet@1.33.0/+esm";

// ---------------------------------------------------------------------------
// Rutas relativas a la raíz del proyecto (desde frontend/)
// ---------------------------------------------------------------------------
const RUTA_CSV = "../salidas/transacciones_limpias.csv";
const RUTA_JSON = "../salidas/alertas_resolucion.json";
const RUTA_PARQUET = "../salidas/serie_acumulada.parquet";

// ---------------------------------------------------------------------------
// Estado de la aplicación
// ---------------------------------------------------------------------------
let datosTransacciones = [];   // filas limpias del CSV
let datosParquet = [];         // serie acumulada (Vacum) del Parquet
let alertas = {};              // JSON del Map/Reduce
let graficas = {};             // instancias Chart.js
let ordenActual = { col: null, asc: true };

// Paginación para la tabla (evita congelar el navegador con 57,000+ filas en DOM)
let paginaActual = 1;
const FILAS_POR_PAGINA = 50;

// ---------------------------------------------------------------------------
// Carga de datos
// ---------------------------------------------------------------------------

async function cargarCSV() {
  const respuesta = await fetch(RUTA_CSV);
  const texto = await respuesta.text();
  const resultado = Papa.parse(texto, {
    header: true,
    dynamicTyping: true,
    skipEmptyLines: true,
  });
  datosTransacciones = resultado.data || [];
  return datosTransacciones;
}

async function cargarJSON() {
  const respuesta = await fetch(RUTA_JSON);
  alertas = await respuesta.json();
  return alertas;
}

async function cargarParquet() {
  const respuesta = await fetch(RUTA_PARQUET);
  const buffer = await respuesta.arrayBuffer();
  // hyparquet.parquetReadObjects devuelve una promesa que resuelve
  // directamente a la lista de filas decodificadas como objetos JS.
  datosParquet = await hyparquet.parquetReadObjects({ file: buffer });
  return datosParquet;
}

// ---------------------------------------------------------------------------
// Filtros
// ---------------------------------------------------------------------------

function obtenerFiltros() {
  return {
    pais: document.getElementById("filtro-pais").value,
    categoria: document.getElementById("filtro-categoria").value,
    estado: document.getElementById("filtro-estado").value,
    fechaDesde: document.getElementById("filtro-fecha-desde").value,
    fechaHasta: document.getElementById("filtro-fecha-hasta").value,
  };
}

function filaPasaFiltros(fila, f) {
  if (f.pais && String(fila.pais_usuario) !== f.pais) return false;
  if (f.categoria && String(fila.categoria_comercio) !== f.categoria) return false;
  if (f.estado && String(fila.estado) !== f.estado) return false;
  if (f.fechaDesde && String(fila.fecha_hora).slice(0, 10) < f.fechaDesde) return false;
  if (f.fechaHasta && String(fila.fecha_hora).slice(0, 10) > f.fechaHasta) return false;
  return true;
}

function datosFiltrados() {
  const f = obtenerFiltros();
  return datosTransacciones.filter((row) => filaPasaFiltros(row, f));
}

// ---------------------------------------------------------------------------
// KPIs
// ---------------------------------------------------------------------------

function actualizarKPIs() {
  const filtrados = datosFiltrados();
  const total = filtrados.length;
  const volumen = filtrados.reduce((s, r) => s + (Number(r.monto_usd) || 0), 0);
  const completadas = filtrados.filter((r) => String(r.estado) === "COMPLETADA").length;
  const pct = total ? ((completadas / total) * 100).toFixed(1) : 0;

  document.getElementById("kpi-total").textContent = total.toLocaleString();
  document.getElementById("kpi-volumen").textContent = volumen.toLocaleString("es-CO", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  document.getElementById("kpi-completadas").textContent = pct + "%";
}

// ---------------------------------------------------------------------------
// Gráficas Chart.js
// ---------------------------------------------------------------------------

function destruirGraficas() {
  Object.values(graficas).forEach((g) => g && g.destroy());
  graficas = {};
}

function renderGraficaLinea(filtrados) {
  // Usamos la serie Parquet (ordenada por fecha, con Vacum) filtrada por rango de fechas si aplica
  const f = obtenerFiltros();
  let serie = datosParquet.slice();
  if (f.fechaDesde) serie = serie.filter((r) => String(r.fecha_hora).slice(0, 10) >= f.fechaDesde);
  if (f.fechaHasta) serie = serie.filter((r) => String(r.fecha_hora).slice(0, 10) <= f.fechaHasta);

  // Muestreo si hay demasiados puntos para mantener la gráfica fluida
  const limitePuntos = 1000;
  let serieMuestreada = serie;
  if (serie.length > limitePuntos) {
    const paso = Math.max(1, Math.floor(serie.length / limitePuntos));
    serieMuestreada = serie.filter((_, idx) => idx % paso === 0 || idx === serie.length - 1);
  }

  const ctx = document.getElementById("grafica-linea").getContext("2d");
  if (graficas.linea) graficas.linea.destroy();
  graficas.linea = new Chart(ctx, {
    type: "line",
    data: {
      labels: serieMuestreada.map((r) => String(r.fecha_hora).slice(0, 10)),
      datasets: [{
        label: "Volumen acumulado Vacum (USD)",
        data: serieMuestreada.map((r) => Number(r.vacum) || 0),
        borderColor: "#2563eb",
        backgroundColor: "rgba(37, 99, 235, 0.1)",
        fill: true,
        tension: 0.2,
        pointRadius: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, title: { display: false } },
      scales: { y: { beginAtZero: true } },
    },
  });
}

function renderHistogramaZ(filtrados) {
  // Calculamos bins de |Z| del conjunto filtrado de forma segura contra call stack limit
  const valores = filtrados.map((r) => Math.abs(Number(r.zscore) || 0));
  const maxZ = valores.reduce((max, v) => (v > max ? v : max), 0);
  const binCount = 20;
  const binWidth = maxZ / binCount || 1;
  const bins = new Array(binCount).fill(0);

  for (const v of valores) {
    const idx = Math.min(Math.floor(v / binWidth), binCount - 1);
    bins[idx]++;
  }

  const etiquetas = bins.map((_, i) => {
    const ini = (i * binWidth).toFixed(1);
    const fin = ((i + 1) * binWidth).toFixed(1);
    return `${ini}-${fin}`;
  });
  const colores = bins.map((_, i) => {
    const centro = (i + 0.5) * binWidth;
    return centro > 3 ? "#dc2626" : "#2563eb"; // anomalías resaltadas
  });

  const ctx = document.getElementById("grafica-histograma").getContext("2d");
  if (graficas.histograma) graficas.histograma.destroy();
  graficas.histograma = new Chart(ctx, {
    type: "bar",
    data: {
      labels: etiquetas,
      datasets: [{
        label: "Conteo de transacciones",
        data: bins,
        backgroundColor: colores,
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true } },
    },
  });
}

function renderBarrasResolucion() {
  const porResolucion = alertas.por_resolucion || {};
  const etiquetas = Object.keys(porResolucion);
  const promedios = etiquetas.map((k) => porResolucion[k].tiempo_promedio_dias || 0);

  const ctx = document.getElementById("grafica-barras-resolucion").getContext("2d");
  if (graficas.barrasResolucion) graficas.barrasResolucion.destroy();
  graficas.barrasResolucion = new Chart(ctx, {
    type: "bar",
    data: {
      labels: etiquetas,
      datasets: [{
        label: "Tiempo promedio (días)",
        data: promedios,
        backgroundColor: "#2563eb",
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true } },
    },
  });
}

function poblarSelectCategorias() {
  const select = document.getElementById("select-categoria-barras");
  const porCategoria = alertas.por_categoria || {};
  const categorias = Object.keys(porCategoria);
  select.innerHTML = '<option value="">-- Todas las categorías --</option>';
  for (const cat of categorias) {
    const op = document.createElement("option");
    op.value = cat;
    op.textContent = cat;
    select.appendChild(op);
  }
}

function renderBarrasCategoria() {
  const select = document.getElementById("select-categoria-barras");
  const cat = select.value;
  const porCategoria = alertas.por_categoria || {};
  const ctx = document.getElementById("grafica-barras-categoria").getContext("2d");
  if (graficas.barrasCategoria) graficas.barrasCategoria.destroy();

  let etiquetas = [];
  let valores = [];

  if (!cat) {
    // Si no se selecciona una en específico, mostramos todas para no dejar el gráfico vacío
    etiquetas = Object.keys(porCategoria);
    valores = etiquetas.map((c) => porCategoria[c].tiempo_promedio_dias || 0);
  } else {
    const entrada = porCategoria[cat] || { tiempo_promedio_dias: 0, conteo: 0 };
    etiquetas = [cat];
    valores = [entrada.tiempo_promedio_dias || 0];
  }

  graficas.barrasCategoria = new Chart(ctx, {
    type: "bar",
    data: {
      labels: etiquetas,
      datasets: [{
        label: "Tiempo promedio (días)",
        data: valores,
        backgroundColor: "#059669",
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true } },
    },
  });
}

// ---------------------------------------------------------------------------
// Tabla y paginación
// ---------------------------------------------------------------------------

const COLUMNAS_TABLA = [
  "id_transaccion", "pais_usuario", "categoria_comercio",
  "monto_original", "moneda", "fecha_hora", "estado", "monto_usd", "zscore",
];

function poblarFiltros() {
  const paises = [...new Set(datosTransacciones.map((r) => r.pais_usuario).filter(Boolean))].sort();
  const categorias = [...new Set(datosTransacciones.map((r) => r.categoria_comercio).filter(Boolean))].sort();
  const estados = [...new Set(datosTransacciones.map((r) => r.estado).filter(Boolean))].sort();

  const selPais = document.getElementById("filtro-pais");
  const selCat = document.getElementById("filtro-categoria");
  const selEst = document.getElementById("filtro-estado");

  [selPais, selCat, selEst].forEach((s) => { while (s.options.length > 1) s.remove(1); });

  for (const p of paises) { const o = new Option(p, p); selPais.add(o); }
  for (const c of categorias) { const o = new Option(c, c); selCat.add(o); }
  for (const e of estados) { const o = new Option(e, e); selEst.add(o); }
}

function formatearCelda(col, val) {
  if (col === "monto_original" || col === "monto_usd") return Number(val || 0).toFixed(2);
  if (col === "zscore") return Number(val || 0).toFixed(2);
  return val === null || val === undefined ? "" : val;
}

function renderTabla(filtrados, colOrden, asc) {
  const datos = filtrados.slice();
  if (colOrden) {
    datos.sort((a, b) => {
      const va = a[colOrden];
      const vb = b[colOrden];
      if (va === null || va === undefined) return 1;
      if (vb === null || vb === undefined) return -1;
      let cmp = 0;
      if (typeof va === "number" && typeof vb === "number") {
        cmp = va - vb;
      } else {
        cmp = String(va).localeCompare(String(vb), undefined, { numeric: true });
      }
      return asc ? cmp : -cmp;
    });
  }

  const totalFilas = datos.length;
  const totalPaginas = Math.ceil(totalFilas / FILAS_POR_PAGINA) || 1;
  if (paginaActual > totalPaginas) paginaActual = totalPaginas;
  if (paginaActual < 1) paginaActual = 1;

  const inicio = (paginaActual - 1) * FILAS_POR_PAGINA;
  const fin = Math.min(inicio + FILAS_POR_PAGINA, totalFilas);
  const filasPagina = datos.slice(inicio, fin);

  const tbody = document.getElementById("cuerpo-tabla");
  tbody.innerHTML = "";

  const fragmento = document.createDocumentFragment();
  for (const fila of filasPagina) {
    const tr = document.createElement("tr");
    for (const col of COLUMNAS_TABLA) {
      const td = document.createElement("td");
      td.textContent = formatearCelda(col, fila[col]);
      tr.appendChild(td);
    }
    fragmento.appendChild(tr);
  }
  tbody.appendChild(fragmento);

  // Actualizar estado de paginación
  const infoPag = document.getElementById("info-paginacion");
  if (infoPag) {
    infoPag.textContent = `Página ${paginaActual} de ${totalPaginas}`;
  }
  const btnAnt = document.getElementById("btn-pag-anterior");
  const btnSig = document.getElementById("btn-pag-siguiente");
  if (btnAnt) btnAnt.disabled = paginaActual <= 1;
  if (btnSig) btnSig.disabled = paginaActual >= totalPaginas;

  const contadorEl = document.getElementById("contador-filas");
  if (contadorEl) {
    if (totalFilas === 0) {
      contadorEl.textContent = "0 filas";
    } else {
      contadorEl.textContent = `Mostrando ${inicio + 1} - ${fin} de ${totalFilas.toLocaleString()} filas`;
    }
  }

  // Indicador visual de orden en la cabecera
  document.querySelectorAll("th").forEach((th) => {
    const col = th.dataset.col;
    th.classList.toggle("ordenado", col === colOrden);
    th.setAttribute("aria-sort", col === colOrden ? (asc ? "ascending" : "descending") : "none");
  });
}

function inicializarOrdenamiento() {
  document.querySelectorAll("th[data-col]").forEach((th) => {
    th.addEventListener("click", () => {
      const col = th.dataset.col;
      if (ordenActual.col === col) {
        ordenActual.asc = !ordenActual.asc;
      } else {
        ordenActual.col = col;
        ordenActual.asc = true;
      }
      renderizarTodo();
    });
  });
}

function descargarCSVFiltrado() {
  const filtrados = datosFiltrados();
  const lineas = [];
  lineas.push(COLUMNAS_TABLA.join(","));
  for (const fila of filtrados) {
    lineas.push(COLUMNAS_TABLA.map((c) => {
      let v = formatearCelda(c, fila[c]);
      // escapar comillas y comas
      if (String(v).includes(",") || String(v).includes('"')) {
        v = '"' + String(v).replace(/"/g, '""') + '"';
      }
      return v;
    }).join(","));
  }
  const blob = new Blob([lineas.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "transacciones_filtradas.csv";
  a.click();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Orquestado de renderizado
// ---------------------------------------------------------------------------

function renderizarTodo() {
  const filtrados = datosFiltrados();
  actualizarKPIs();
  renderGraficaLinea(filtrados);
  renderHistogramaZ(filtrados);
  renderBarrasResolucion();
  renderBarrasCategoria();
  renderTabla(filtrados, ordenActual.col, ordenActual.asc);
}

// ---------------------------------------------------------------------------
// Inicialización
// ---------------------------------------------------------------------------

async function inicializar() {
  await Promise.all([cargarCSV(), cargarJSON(), cargarParquet()]);

  poblarFiltros();
  poblarSelectCategorias();

  // Eventos de filtros (resetean la paginación a la página 1)
  const inputsFiltro = [
    "filtro-pais", "filtro-categoria", "filtro-estado",
    "filtro-fecha-desde", "filtro-fecha-hasta",
  ];
  for (const id of inputsFiltro) {
    const el = document.getElementById(id);
    const manejador = () => {
      paginaActual = 1;
      renderizarTodo();
    };
    el.addEventListener("change", manejador);
    el.addEventListener("input", manejador);
  }

  document.getElementById("btn-limpiar-filtros").addEventListener("click", () => {
    for (const id of inputsFiltro) {
      const el = document.getElementById(id);
      if (el.tagName === "SELECT") el.selectedIndex = 0;
      else el.value = "";
    }
    paginaActual = 1;
    renderizarTodo();
  });

  // Eventos de paginación
  const btnAnt = document.getElementById("btn-pag-anterior");
  const btnSig = document.getElementById("btn-pag-siguiente");
  if (btnAnt) {
    btnAnt.addEventListener("click", () => {
      if (paginaActual > 1) {
        paginaActual--;
        renderizarTodo();
      }
    });
  }
  if (btnSig) {
    btnSig.addEventListener("click", () => {
      paginaActual++;
      renderizarTodo();
    });
  }

  document.getElementById("btn-descargar-csv").addEventListener("click", descargarCSVFiltrado);
  document.getElementById("select-categoria-barras").addEventListener("change", renderBarrasCategoria);

  inicializarOrdenamiento();

  renderizarTodo();
}

inicializar().catch((err) => {
  console.error("Error inicializando el frontend:", err);
  alert("No se pudieron cargar los datos. Asegúrate de ejecutar `python pipeline/main.py` primero y de servir con `python -m http.server 8000`.");
});
