"""Crea o restablece la cuenta administradora que muestra la aplicación EcoRuta.

Ejecutar desde la carpeta del proyecto:
    py EcoRuta/crear_admin.py

Actualiza únicamente la fila que coincide con admin@ecoruta.mx. No elimina
usuarios, reportes ni cambia identificadores.
"""
from __future__ import annotations

import os
from pathlib import Path

# Cargar .env antes de importar la conexión y los módulos de seguridad.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
except ImportError:
    pass

from conexion import obtener_conexion
from seguridad import hash_password

# Deben coincidir exactamente con src/cliente_api.py y la pantalla de acceso admin.
ADMIN_NAME = "Administrador EcoRuta"
ADMIN_EMAIL = "admin@ecoruta.mx"
ADMIN_PASSWORD = "EcoRuta2026"


def crear_o_actualizar_admin() -> None:
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id_usuario FROM usuarios WHERE LOWER(email) = %s LIMIT 1",
            (ADMIN_EMAIL,),
        )
        existente = cursor.fetchone()
        password_hash = hash_password(ADMIN_PASSWORD)

        if existente:
            cursor.execute(
                """UPDATE usuarios
                   SET nombre = %s, email = %s, password_hash = %s,
                       rol = 'admin', activo = TRUE
                   WHERE id_usuario = %s""",
                (ADMIN_NAME, ADMIN_EMAIL, password_hash, existente["id_usuario"]),
            )
            accion = "La cuenta administradora existente fue restablecida."
        else:
            cursor.execute(
                """INSERT INTO usuarios
                   (nombre, email, password_hash, rol, activo)
                   VALUES (%s, %s, %s, 'admin', TRUE)""",
                (ADMIN_NAME, ADMIN_EMAIL, password_hash),
            )
            accion = "La cuenta administradora fue creada."

        conexion.commit()
        cursor.execute(
            "SELECT id_usuario, email, rol, activo FROM usuarios WHERE email = %s",
            (ADMIN_EMAIL,),
        )
        verificacion = cursor.fetchone()
        if not verificacion or verificacion["rol"] != "admin" or not bool(verificacion["activo"]):
            raise RuntimeError("La verificación final del administrador no fue satisfactoria.")

        print(accion)
        print(f"ID de administrador: {verificacion['id_usuario']}")
        print(f"Correo: {verificacion['email']}")
        print(f"Rol: {verificacion['rol']}")
        print(f"Activo: {bool(verificacion['activo'])}")
        print("Contraseña configurada igual que la pantalla de acceso de EcoRuta.")
    except Exception:
        conexion.rollback()
        raise
    finally:
        cursor.close()
        conexion.close()


if __name__ == "__main__":
    crear_o_actualizar_admin()
