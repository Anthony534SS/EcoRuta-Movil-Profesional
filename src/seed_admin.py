import hashlib
import mysql.connector

DB_CONFIG = {
    'host': 'ecoruta-antonio-618d.c.aivencloud.com',
    'port': 21716,
    'user': 'avnadmin',
    'password': 'AVNS_Yum4uq8V_ok00akE24o',
    'database': 'ecoruta_db'
}

def cifrar_contrasena(contrasena: str) -> str:
    return hashlib.sha256(contrasena.strip().encode("utf-8")).hexdigest()

def crear_o_actualizar_admin():
    email = "admin@ecoruta.mx"
    password_plana = "EcoRuta2026"
    nombre = "Administrador EcoRuta"
    rol = "admin"
    
    pwd_cifrada = cifrar_contrasena(password_plana)

    db = mysql.connector.connect(**DB_CONFIG)
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
    user = cursor.fetchone()

    if user:
        cursor.execute(
            "UPDATE usuarios SET contrasena = %s, rol = %s WHERE email = %s",
            (pwd_cifrada, rol, email)
        )
        print("--> Administrador existente actualizado correctamente.")
    else:
        cursor.execute(
            "INSERT INTO usuarios (nombre, email, contrasena, rol) VALUES (%s, %s, %s, %s)",
            (nombre, email, pwd_cifrada, rol)
        )
        print("--> Administrador creado exitosamente.")

    db.commit()
    db.close()

if __name__ == "__main__":
    crear_o_actualizar_admin()