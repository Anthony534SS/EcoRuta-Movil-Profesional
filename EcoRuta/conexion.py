"""Conexión MySQL segura para la base existente ecoruta en Aiven.io."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import mysql.connector
from mysql.connector import pooling

MODULE_DIR = Path(__file__).resolve().parent
# En la aplicación completa, conexion.py está dentro de EcoRuta/; en Render
# normalmente está en la raíz del repositorio. Ambos escenarios se resuelven.
ROOT = MODULE_DIR.parent if MODULE_DIR.name.lower() == "ecoruta" else MODULE_DIR

try:
    from dotenv import load_dotenv
    # Acepta .env en la raíz del proyecto o junto a estos módulos de backend.
    load_dotenv(ROOT / ".env", override=False)
    load_dotenv(MODULE_DIR / ".env", override=False)
except ImportError:
    pass

DB_CONFIG: dict[str, Any] = {
    "host": os.getenv("MYSQL_HOST", "ecoruta-antonio-618d.c.aivencloud.com").strip(),
    "port": int(os.getenv("MYSQL_PORT", "21716")),
    "user": os.getenv("MYSQL_USER", "avnadmin").strip(),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "ecoruta").strip() or "ecoruta",
    "connection_timeout": int(os.getenv("MYSQL_CONNECT_TIMEOUT", "12")),
    "autocommit": False,
    "charset": "utf8mb4",
    "use_unicode": True,
}

_pool: pooling.MySQLConnectionPool | None = None


def _configuracion_con_ssl() -> dict[str, Any]:
    config = DB_CONFIG.copy()
    host = config["host"].lower()
    ca_setting = os.getenv("MYSQL_SSL_CA", "").strip()

    if host not in {"localhost", "127.0.0.1"}:
        if not ca_setting:
            raise RuntimeError(
                "Falta MYSQL_SSL_CA. En Render agrega el CA de Aiven como "
                "Secret File y configura MYSQL_SSL_CA=/etc/secrets/ca.pem."
            )
        ca_path = Path(ca_setting)
        if not ca_path.is_absolute():
            ca_path = ROOT / ca_path
        if not ca_path.is_file():
            raise RuntimeError(f"No se encontró el certificado CA: {ca_path}")
        config.update(
            ssl_ca=str(ca_path),
            ssl_verify_cert=True,
            ssl_verify_identity=True,
        )
    return config


def _crear_pool() -> pooling.MySQLConnectionPool:
    if not DB_CONFIG["host"] or not DB_CONFIG["user"] or not DB_CONFIG["password"]:
        raise RuntimeError(
            "Configura MYSQL_HOST, MYSQL_USER y MYSQL_PASSWORD en las variables "
            "de entorno del servicio Render."
        )
    return pooling.MySQLConnectionPool(
        pool_name="ecoruta_pool",
        pool_size=5,
        pool_reset_session=True,
        **_configuracion_con_ssl(),
    )


def obtener_conexion():
    global _pool
    if _pool is None:
        _pool = _crear_pool()
    try:
        return _pool.get_connection()
    except mysql.connector.Error:
        # Recrea el pool una sola vez si la conexión entregada dejó de ser válida.
        _pool = _crear_pool()
        return _pool.get_connection()


def probar_conexion() -> dict[str, str]:
    conexion = obtener_conexion()
    cursor = None
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT DATABASE() AS base_datos, VERSION() AS version_mysql")
        resultado = cursor.fetchone() or {}
        if resultado.get("base_datos") != "ecoruta":
            raise RuntimeError(
                "La conexión se abrió a otra base de datos. Se esperaba exactamente 'ecoruta'."
            )
        return {
            "base_datos": str(resultado.get("base_datos")),
            "version_mysql": str(resultado.get("version_mysql")),
        }
    finally:
        if cursor is not None:
            cursor.close()
        conexion.close()
