import base64
import hashlib
import os
import random
from datetime import datetime, timedelta
import mysql.connector

# Configuración de tu base de datos MySQL en Aiven
DB_CONFIG = {
    'host': 'ecoruta-antonio-618d.c.aivencloud.com',
    'port': 21716,
    'user': 'avnadmin',
    'password': 'AVNS_Yum4uq8V_ok00akE24o',
    'database': 'ecoruta_db'
}

def cifrar_contrasena(contrasena: str) -> str:
    return hashlib.sha256(contrasena.strip().encode("utf-8")).hexdigest()

def cargar_imagen_base64(ruta_completa):
    """Convierte un archivo de imagen local a cadena Base64 válida."""
    if not os.path.exists(ruta_completa):
        return None
    try:
        with open(ruta_completa, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
            # Detectar extensión para el MIME type
            ext = os.path.splitext(ruta_completa)[1].lower()
            mime = "image/png" if ext == ".png" else "image/jpeg"
            return f"data:{mime};base64,{encoded}"
    except Exception as e:
        print(f"Error al leer {ruta_completa}: {e}")
        return None

NOMBRES = ["Carlos", "Ana", "Luis", "María", "Jorge", "Sofía", "Pedro", "Lucía", "Miguel", "Elena", "Fernando", "Valeria"]
APELLIDOS = ["Gómez", "Hernández", "López", "Martínez", "Pérez", "Rodríguez", "Sánchez", "Torres", "Ramírez", "Flores"]
ESTADOS_REPORTE = ["Pendiente", "En revisión", "Atendido"]

def generar_datos_prueba():
    print("Conectando a la base de datos MySQL...")
    db = mysql.connector.connect(**DB_CONFIG)
    cursor = db.cursor()

    pwd_hash = cifrar_contrasena("Usuario123")
    usuarios_ids = []

    print("1. Insertando / Verificando 100 usuarios...")
    for i in range(1, 101):
        nombre = f"{random.choice(NOMBRES)} {random.choice(APELLIDOS)}"
        email = f"usuario{i}@ecoruta.mx"
        
        cursor.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
        existe = cursor.fetchone()
        
        if existe:
            usuarios_ids.append(existe[0])
        else:
            cursor.execute(
                "INSERT INTO usuarios (nombre, email, contrasena, rol) VALUES (%s, %s, %s, 'usuario')",
                (nombre, email, pwd_hash)
            )
            usuarios_ids.append(cursor.lastrowid)

    db.commit()

    # Obtener la ruta absoluta exacta de la carpeta 'imagenes'
    directorio_script = os.path.dirname(os.path.abspath(__file__))
    carpeta_imagenes = os.path.join(directorio_script, "imagenes")
    
    print(f"2. Buscando imágenes en: {carpeta_imagenes}")

    if not os.path.exists(carpeta_imagenes):
        print(f"\n[ERROR] La carpeta '{carpeta_imagenes}' no existe.")
        db.close()
        return

    imagenes_base64_cargadas = []
    # Escanear dinámicamente cualquier archivo de imagen dentro de la carpeta
    archivos_carpeta = os.listdir(carpeta_imagenes)
    
    for archivo in archivos_carpeta:
        if archivo.lower().endswith(('.jpg', '.jpeg', '.png')):
            ruta_archivo = os.path.join(carpeta_imagenes, archivo)
            b64 = cargar_imagen_base64(ruta_archivo)
            if b64:
                imagenes_base64_cargadas.append(b64)
                print(f" -> Imagen '{archivo}' cargada correctamente.")

    if not imagenes_base64_cargadas:
        print("\n[ERROR] No se encontraron archivos .jpg, .jpeg o .png dentro de la carpeta 'imagenes'.")
        db.close()
        return

    print("3. Limpiando reportes antiguos...")
    cursor.execute("DELETE FROM reportes")
    db.commit()

    print("4. Insertando 50 reportes variados con tus fotos reales...")
    lat_base, lon_base = 17.9892, -92.9475

    for i in range(50):
        usuario_id = random.choice(usuarios_ids)
        img_seleccionada = random.choice(imagenes_base64_cargadas)
        
        lat = round(lat_base + random.uniform(-0.05, 0.05), 6)
        lon = round(lon_base + random.uniform(-0.05, 0.05), 6)
        
        dias_atras = random.randint(0, 30)
        horas_atras = random.randint(0, 23)
        fecha_obj = datetime.now() - timedelta(days=dias_atras, hours=horas_atras)
        fecha_hora = fecha_obj.strftime("%d/%m/%Y %H:%M:%S")
        estado = random.choice(ESTADOS_REPORTE)

        cursor.execute("""
            INSERT INTO reportes (imagen, latitud, longitud, fecha_hora, estado, usuario_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (img_seleccionada, lat, lon, fecha_hora, estado, usuario_id))

    db.commit()
    cursor.close()
    db.close()
    print("\n¡Proceso finalizado con éxito! Se cargaron los 50 reportes en la base de datos usando tus imágenes reales.")

if __name__ == "__main__":
    generar_datos_prueba()