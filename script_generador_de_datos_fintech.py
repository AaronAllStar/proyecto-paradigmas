import sqlite3
import random
from datetime import datetime, timedelta

# Configuración de simulación
DB_NAME = 'fintech_transacciones.db'
NUM_USUARIOS = 1000
NUM_COMERCIOS = 50
NUM_TRANSACCIONES = 60000
NUM_RECLAMOS = 5000
START_DATE = datetime(2014, 1, 1)
END_DATE = datetime(2024, 1, 1)

def random_date(start, end):
    delta = end - start
    random_days = random.randrange(delta.days)
    return start + timedelta(days=random_days)

def generar_datos():
    print(f"Generando base de datos transaccional Fintech: {DB_NAME}...")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Creación de Esquema
    cursor.executescript('''
        DROP TABLE IF EXISTS Reclamos_Fraude;
        DROP TABLE IF EXISTS Transacciones;
        DROP TABLE IF EXISTS Comercios;
        DROP TABLE IF EXISTS Usuarios;

        CREATE TABLE Usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pais TEXT NOT NULL,
            tipo_cuenta TEXT,
            fecha_registro TEXT
        );

        CREATE TABLE Comercios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            categoria TEXT,
            nivel_riesgo TEXT
        );

        CREATE TABLE Transacciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            comercio_id INTEGER,
            monto_original NUMERIC,  -- Intencionalmente NUMERIC para permitir basura (strings, etc)
            moneda TEXT,
            fecha_hora TEXT,
            estado TEXT,
            FOREIGN KEY(usuario_id) REFERENCES Usuarios(id),
            FOREIGN KEY(comercio_id) REFERENCES Comercios(id)
        );

        CREATE TABLE Reclamos_Fraude (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaccion_id INTEGER,
            resolucion TEXT,
            tiempo_investigacion_dias NUMERIC,
            FOREIGN KEY(transaccion_id) REFERENCES Transacciones(id)
        );
    ''')

    # 2. Poblar Usuarios
    paises = ['Costa Rica', 'Mexico', 'Colombia', 'Argentina', 'Chile', None]
    tipos = ['Standard', 'Premium', 'Business']
    usuarios = []
    for _ in range(NUM_USUARIOS):
        usuarios.append((random.choice(paises), random.choice(tipos), random_date(START_DATE, END_DATE).isoformat()))
    cursor.executemany('INSERT INTO Usuarios (pais, tipo_cuenta, fecha_registro) VALUES (?, ?, ?)', usuarios)

    # 3. Poblar Comercios
    categorias = ['Retail', 'Digital Services', 'Travel', 'Crypto', 'Gaming']
    riesgos = ['BAJO', 'MEDIO', 'ALTO']
    comercios = []
    for i in range(NUM_COMERCIOS):
        comercios.append((f"Comercio_{i}", random.choice(categorias), random.choice(riesgos)))
    cursor.executemany('INSERT INTO Comercios (nombre, categoria, nivel_riesgo) VALUES (?, ?, ?)', comercios)

    # 4. Poblar Transacciones (Con Edge Cases)
    transacciones = []
    monedas = ['USD', 'CRC', 'MXN', 'COP']
    estados = ['COMPLETADA', 'PENDIENTE', 'RECHAZADA']
    
    for _ in range(NUM_TRANSACCIONES):
        u_id = random.randint(1, NUM_USUARIOS)
        c_id = random.randint(1, NUM_COMERCIOS)
        moneda = random.choice(monedas)
        
        # Generar montos con anomalías
        anomalia_monto = random.random()
        if anomalia_monto < 0.03:
            monto = f"${round(random.uniform(10, 500), 2)}" # String con símbolo
        elif anomalia_monto < 0.05:
            monto = round(random.uniform(-500, -10), 2) # Monto negativo absurdo
        else:
            monto = round(abs(random.gauss(150, 300)), 2) # Distribución normal de montos

        # Generar fechas con anomalías
        fecha_real = random_date(START_DATE, END_DATE)
        anomalia_fecha = random.random()
        if anomalia_fecha < 0.04:
            fecha_str = str(int(fecha_real.timestamp())) # Timestamp UNIX
        elif anomalia_fecha < 0.06:
            fecha_str = 'N/A'
        elif anomalia_fecha < 0.08:
            fecha_str = None
        else:
            fecha_str = fecha_real.isoformat()

        transacciones.append((u_id, c_id, monto, moneda, fecha_str, random.choice(estados)))

    cursor.executemany('''
        INSERT INTO Transacciones (usuario_id, comercio_id, monto_original, moneda, fecha_hora, estado) 
        VALUES (?, ?, ?, ?, ?, ?)
    ''', transacciones)

    # 5. Poblar Reclamos de Fraude (Con Edge Cases)
    reclamos = []
    resoluciones = ['A FAVOR CLIENTE', 'A FAVOR COMERCIO', 'EN REVISION']
    
    for _ in range(NUM_RECLAMOS):
        t_id = random.randint(1, NUM_TRANSACCIONES)
        
        # Anomalías en tiempo de investigación
        if random.random() < 0.02:
            tiempo = random.randint(5000, 10000) # Outliers extremos (años en días)
        elif random.random() < 0.05:
            tiempo = None
        else:
            tiempo = int(abs(random.gauss(15, 10))) # Promedio 15 días
            
        reclamos.append((t_id, random.choice(resoluciones), tiempo))

    cursor.executemany('''
        INSERT INTO Reclamos_Fraude (transaccion_id, resolucion, tiempo_investigacion_dias)
        VALUES (?, ?, ?)
    ''', reclamos)

    conn.commit()
    conn.close()
    print(f"¡Éxito! Dataset Fintech generado. Total de transacciones: {NUM_TRANSACCIONES}")

if __name__ == '__main__':
    generar_datos()