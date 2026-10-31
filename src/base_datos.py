import hashlib
import os
import sqlite3
from datetime import datetime
from pathlib import Path


ADMIN_EMAIL = "admin@ecoruta.mx"
ADMIN_PASSWORD = "EcoRuta2026"


def _ruta_datos() -> Path:
    # En Android/iOS Flet usa una carpeta privada y persistente.
    # En Thonny se crea una carpeta local junto al proyecto.
    ruta_flet = os.getenv("FLET_APP_STORAGE_DATA")
    if ruta_flet:
        ruta = Path(ruta_flet)
    else:
        ruta = Path(__file__).resolve().parent.parent / ".ecoruta_data"
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


RUTA_BD = _ruta_datos() / "ecoruta.db"


def conectar():
    conexion = sqlite3.connect(RUTA_BD)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion


def cifrar_contrasena(contrasena: str) -> str:
    # Adecuado para este prototipo académico; en producción se usaría
    # un algoritmo específico para contraseñas como Argon2 o bcrypt.
    return hashlib.sha256(contrasena.encode("utf-8")).hexdigest()


def crear_tablas():
    conexion = conectar()
    cursor = conexion.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            contrasena TEXT NOT NULL,
            rol TEXT NOT NULL DEFAULT 'usuario'
        )
    """)

    # Migración para bases creadas con versiones anteriores de EcoRuta.
    columnas = [fila["name"] for fila in cursor.execute("PRAGMA table_info(usuarios)")]
    if "rol" not in columnas:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN rol TEXT NOT NULL DEFAULT 'usuario'")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reportes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imagen BLOB NOT NULL,
            latitud REAL NOT NULL,
            longitud REAL NOT NULL,
            fecha_hora TEXT NOT NULL,
            estado TEXT NOT NULL,
            usuario_id INTEGER NOT NULL,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mensajes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contenido TEXT NOT NULL,
            fecha_hora TEXT NOT NULL,
            usuario_id INTEGER NOT NULL,
            reporte_id INTEGER,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
            FOREIGN KEY (reporte_id) REFERENCES reportes(id)
        )
    """)

    # Cuenta de administrador inicial para el prototipo.
    cursor.execute("SELECT id FROM usuarios WHERE email = ?", (ADMIN_EMAIL,))
    if cursor.fetchone() is None:
        cursor.execute(
            """
            INSERT INTO usuarios (nombre, email, contrasena, rol)
            VALUES (?, ?, ?, 'admin')
            """,
            ("Administrador EcoRuta", ADMIN_EMAIL, cifrar_contrasena(ADMIN_PASSWORD)),
        )
    else:
        # Garantiza que la cuenta reservada conserve el rol administrador.
        cursor.execute(
            "UPDATE usuarios SET rol = 'admin', contrasena = ? WHERE email = ?",
            (cifrar_contrasena(ADMIN_PASSWORD), ADMIN_EMAIL),
        )

    conexion.commit()
    conexion.close()


def registrar_usuario(nombre, email, contrasena):
    nombre = nombre.strip()
    email = email.strip().lower()
    contrasena = contrasena.strip()

    if not nombre or not email or not contrasena:
        return False, "Completa todos los campos."
    if "@" not in email or "." not in email:
        return False, "Escribe un correo electrónico válido."
    if len(contrasena) < 4:
        return False, "La contraseña debe tener al menos 4 caracteres."
    if email == ADMIN_EMAIL:
        return False, "Ese correo está reservado para administración."

    conexion = conectar()
    cursor = conexion.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO usuarios (nombre, email, contrasena, rol)
            VALUES (?, ?, ?, 'usuario')
            """,
            (nombre, email, cifrar_contrasena(contrasena)),
        )
        conexion.commit()
        return True, "Cuenta creada correctamente."
    except sqlite3.IntegrityError:
        return False, "Ese correo ya está registrado."
    finally:
        conexion.close()


def _iniciar_sesion_por_rol(email, contrasena, rol):
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute(
        """
        SELECT id, nombre, email, rol
        FROM usuarios
        WHERE email = ? AND contrasena = ? AND rol = ?
        """,
        (
            email.strip().lower(),
            cifrar_contrasena(contrasena.strip()),
            rol,
        ),
    )
    usuario = cursor.fetchone()
    conexion.close()
    return dict(usuario) if usuario else None


def iniciar_sesion(email, contrasena):
    return _iniciar_sesion_por_rol(email, contrasena, "usuario")


def iniciar_sesion_admin(email, contrasena):
    return _iniciar_sesion_por_rol(email, contrasena, "admin")


def actualizar_perfil(usuario_id, nombre, email, nueva_contrasena=""):
    nombre = nombre.strip()
    email = email.strip().lower()
    nueva_contrasena = nueva_contrasena.strip()

    if not nombre or not email:
        return False, "El nombre y el correo son obligatorios.", None
    if "@" not in email or "." not in email:
        return False, "Escribe un correo electrónico válido.", None

    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute("SELECT rol FROM usuarios WHERE id = ?", (usuario_id,))
    fila = cursor.fetchone()
    if not fila:
        conexion.close()
        return False, "No se encontró el usuario.", None

    if fila["rol"] != "admin" and email == ADMIN_EMAIL:
        conexion.close()
        return False, "Ese correo está reservado para administración.", None

    try:
        if nueva_contrasena:
            if len(nueva_contrasena) < 4:
                conexion.close()
                return False, "La nueva contraseña debe tener al menos 4 caracteres.", None
            cursor.execute(
                """
                UPDATE usuarios
                SET nombre = ?, email = ?, contrasena = ?
                WHERE id = ?
                """,
                (nombre, email, cifrar_contrasena(nueva_contrasena), usuario_id),
            )
        else:
            cursor.execute(
                "UPDATE usuarios SET nombre = ?, email = ? WHERE id = ?",
                (nombre, email, usuario_id),
            )
        conexion.commit()
    except sqlite3.IntegrityError:
        conexion.close()
        return False, "Ese correo ya está registrado.", None

    cursor.execute(
        "SELECT id, nombre, email, rol FROM usuarios WHERE id = ?",
        (usuario_id,),
    )
    actualizado = cursor.fetchone()
    conexion.close()
    return True, "Perfil actualizado correctamente.", dict(actualizado)


def obtener_usuarios():
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute("""
        SELECT
            u.id, u.nombre, u.email, u.rol,
            COUNT(r.id) AS total_reportes
        FROM usuarios u
        LEFT JOIN reportes r ON r.usuario_id = u.id
        WHERE u.rol = 'usuario'
        GROUP BY u.id, u.nombre, u.email, u.rol
        ORDER BY u.nombre COLLATE NOCASE ASC
    """)
    filas = [dict(fila) for fila in cursor.fetchall()]
    conexion.close()
    return filas


def crear_reporte(imagen, latitud, longitud, usuario_id):
    fecha_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute(
        """
        INSERT INTO reportes
        (imagen, latitud, longitud, fecha_hora, estado, usuario_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (imagen, latitud, longitud, fecha_hora, "Pendiente", usuario_id),
    )
    conexion.commit()
    reporte_id = cursor.lastrowid
    conexion.close()
    return reporte_id


def obtener_reportes(limite=None, usuario_id=None):
    conexion = conectar()
    cursor = conexion.cursor()
    sql = """
        SELECT
            r.id, r.imagen, r.latitud, r.longitud, r.fecha_hora,
            r.estado, r.usuario_id, u.nombre AS usuario_nombre,
            u.email AS usuario_email
        FROM reportes r
        INNER JOIN usuarios u ON u.id = r.usuario_id
    """
    parametros = []
    if usuario_id is not None:
        sql += " WHERE r.usuario_id = ?"
        parametros.append(usuario_id)
    sql += " ORDER BY r.id DESC"
    if limite is not None:
        sql += " LIMIT ?"
        parametros.append(limite)
    cursor.execute(sql, tuple(parametros))
    filas = [dict(fila) for fila in cursor.fetchall()]
    conexion.close()
    return filas


def obtener_reporte(reporte_id):
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute(
        """
        SELECT
            r.id, r.imagen, r.latitud, r.longitud, r.fecha_hora,
            r.estado, r.usuario_id, u.nombre AS usuario_nombre,
            u.email AS usuario_email
        FROM reportes r
        INNER JOIN usuarios u ON u.id = r.usuario_id
        WHERE r.id = ?
        """,
        (reporte_id,),
    )
    fila = cursor.fetchone()
    conexion.close()
    return dict(fila) if fila else None


def actualizar_estado_reporte(reporte_id, estado):
    estados_validos = ("Pendiente", "En revisión", "Atendido")
    if estado not in estados_validos:
        return False
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute(
        "UPDATE reportes SET estado = ? WHERE id = ?",
        (estado, reporte_id),
    )
    conexion.commit()
    cambiado = cursor.rowcount > 0
    conexion.close()
    return cambiado


def enviar_mensaje(contenido, usuario_id, reporte_id=None):
    contenido = contenido.strip()
    if not contenido and reporte_id is None:
        return False
    if not contenido:
        contenido = "Compartió un reporte"

    fecha_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute(
        """
        INSERT INTO mensajes (contenido, fecha_hora, usuario_id, reporte_id)
        VALUES (?, ?, ?, ?)
        """,
        (contenido, fecha_hora, usuario_id, reporte_id),
    )
    conexion.commit()
    conexion.close()
    return True


def obtener_mensajes():
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute("""
        SELECT
            m.id, m.contenido, m.fecha_hora, m.reporte_id, m.usuario_id,
            u.nombre AS usuario_nombre
        FROM mensajes m
        INNER JOIN usuarios u ON u.id = m.usuario_id
        WHERE u.rol = 'usuario'
        ORDER BY m.id ASC
    """)
    filas = [dict(fila) for fila in cursor.fetchall()]
    conexion.close()
    return filas


def obtener_estadisticas(usuario_id=None):
    conexion = conectar()
    cursor = conexion.cursor()

    if usuario_id is None:
        cursor.execute("SELECT COUNT(*) AS total FROM reportes")
        total_reportes = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) AS total FROM reportes WHERE estado = 'Pendiente'")
        pendientes = cursor.fetchone()["total"]
    else:
        cursor.execute(
            "SELECT COUNT(*) AS total FROM reportes WHERE usuario_id = ?",
            (usuario_id,),
        )
        total_reportes = cursor.fetchone()["total"]
        cursor.execute(
            """
            SELECT COUNT(*) AS total FROM reportes
            WHERE usuario_id = ? AND estado = 'Pendiente'
            """,
            (usuario_id,),
        )
        pendientes = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM mensajes")
    mensajes = cursor.fetchone()["total"]
    conexion.close()
    return {
        "reportes": total_reportes,
        "pendientes": pendientes,
        "mensajes": mensajes,
    }


def obtener_estadisticas_admin():
    conexion = conectar()
    cursor = conexion.cursor()

    cursor.execute("SELECT COUNT(*) AS total FROM usuarios WHERE rol = 'usuario'")
    usuarios = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM reportes")
    reportes = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM reportes WHERE estado = 'Pendiente'")
    pendientes = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM reportes WHERE estado = 'Atendido'")
    atendidos = cursor.fetchone()["total"]

    conexion.close()

    return {
        "usuarios": usuarios,
        "reportes": reportes,
        "pendientes": pendientes,
        "atendidos": atendidos,
    }


def eliminar_reporte(reporte_id, usuario_id=None):
    conexion = conectar()
    cursor = conexion.cursor()

    try:
        if usuario_id is None:
            cursor.execute(
                "SELECT id FROM reportes WHERE id = ?",
                (reporte_id,),
            )
        else:
            cursor.execute(
                "SELECT id FROM reportes WHERE id = ? AND usuario_id = ?",
                (reporte_id, usuario_id),
            )

        reporte = cursor.fetchone()

        if not reporte:
            return False

        cursor.execute(
            "DELETE FROM mensajes WHERE reporte_id = ?",
            (reporte_id,),
        )

        cursor.execute(
            "DELETE FROM reportes WHERE id = ?",
            (reporte_id,),
        )

        conexion.commit()
        return cursor.rowcount > 0

    except Exception:
        conexion.rollback()
        return False

    finally:
        conexion.close()
