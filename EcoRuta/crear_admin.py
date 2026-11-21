"""Crea o actualiza únicamente la cuenta de administrador configurada para EcoRuta.

Ejecutar manualmente una sola vez desde la carpeta EcoRuta:
    python crear_admin.py
No borra usuarios ni cambia identificadores de otras cuentas.
"""
import os

from conexion import obtener_conexion
from seguridad import hash_password

# Se conservan los datos administrativos que ya mostraba la aplicación original.
ADMIN_NAME = os.getenv("ADMIN_NAME", "Administrador EcoRuta")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@ecoruta.mx").strip().lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "EcoRuta2026")


def crear_o_actualizar_admin():
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        raise RuntimeError("Configura ADMIN_EMAIL y ADMIN_PASSWORD.")
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id_usuario FROM usuarios WHERE email = %s",
            (ADMIN_EMAIL,),
        )
        existente = cursor.fetchone()
        password_hash = hash_password(ADMIN_PASSWORD)
        if existente:
            cursor.execute(
                "UPDATE usuarios SET nombre = %s, password_hash = %s, rol = 'admin', activo = TRUE WHERE id_usuario = %s",
                (ADMIN_NAME, password_hash, existente["id_usuario"]),
            )
            accion = "La cuenta administrativa existente fue actualizada."
        else:
            cursor.execute(
                "INSERT INTO usuarios (nombre, email, password_hash, rol, activo) VALUES (%s, %s, %s, 'admin', TRUE)",
                (ADMIN_NAME, ADMIN_EMAIL, password_hash),
            )
            accion = "La cuenta administrativa fue creada."
        conexion.commit()
        print(accion)
        print(f"Correo configurado: {ADMIN_EMAIL}")
        print("La contraseña se mantuvo en el entorno local y no se imprime.")
    except Exception:
        conexion.rollback()
        raise
    finally:
        cursor.close()
        conexion.close()


if __name__ == "__main__":
    crear_o_actualizar_admin()
