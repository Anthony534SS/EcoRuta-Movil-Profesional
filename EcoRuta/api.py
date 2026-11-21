"""API REST de EcoRuta conectada exclusivamente a MySQL 'ecoruta' en Aiven."""
from __future__ import annotations

import base64
import binascii
import os
import re
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, Field, field_validator
from mysql.connector import Error, IntegrityError

from conexion import obtener_conexion, probar_conexion
from seguridad import (
    crear_token,
    exigir_admin,
    hash_password,
    usuario_actual,
    verificar_password,
)

APP_ROOT = Path(__file__).resolve().parent
MEDIA_DIR = Path(os.getenv("MEDIA_DIR", str(APP_ROOT / "uploads"))).resolve()
PUBLIC_API_URL = os.getenv("PUBLIC_API_URL", "https://ecoruta-api-antonio.onrender.com").strip().rstrip("/")
ESTADOS = ("Pendiente", "En revisión", "En proceso de atención", "Atendido", "Rechazado")
MAX_IMAGEN_BYTES = 5 * 1024 * 1024

app = FastAPI(
    title="EcoRuta API",
    version="3.0.0",
    description="API de EcoRuta. Los datos operativos se consultan y modifican en MySQL Aiven: ecoruta.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in os.getenv("CORS_ORIGINS", "*").split(",") if x.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


class LoginSchema(BaseModel):
    email: EmailStr
    contrasena: str = Field(min_length=1, max_length=128)


class RegistroSchema(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    email: EmailStr
    contrasena: str = Field(min_length=8, max_length=128)


class PerfilSchema(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    email: EmailStr
    nueva_contrasena: Optional[str] = Field(default=None, min_length=8, max_length=128)


class ReporteSchema(BaseModel):
    imagen: str = Field(min_length=1)
    latitud: float = Field(ge=-90, le=90)
    longitud: float = Field(ge=-180, le=180)
    categoria_id: int = Field(gt=0)
    descripcion: str = Field(min_length=5, max_length=5000)
    ubicacion_referencia: Optional[str] = Field(default=None, max_length=255)

    @field_validator("imagen")
    @classmethod
    def validar_imagen(cls, valor: str) -> str:
        coincidencia = re.fullmatch(r"data:image/(jpeg|png);base64,([A-Za-z0-9+/=]+)", valor or "")
        if not coincidencia:
            raise ValueError("La fotografía debe ser JPEG o PNG codificada en Base64.")
        try:
            contenido = base64.b64decode(coincidencia.group(2), validate=True)
        except (binascii.Error, ValueError):
            raise ValueError("La fotografía tiene una codificación inválida.")
        if not contenido or len(contenido) > MAX_IMAGEN_BYTES:
            raise ValueError("La fotografía debe pesar como máximo 5 MB.")
        mime = coincidencia.group(1)
        if mime == "jpeg" and not contenido.startswith(b"\xff\xd8\xff"):
            raise ValueError("El contenido no corresponde a una imagen JPEG.")
        if mime == "png" and not contenido.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("El contenido no corresponde a una imagen PNG.")
        return valor


class EstadoSchema(BaseModel):
    estado: str
    justificacion: Optional[str] = Field(default=None, max_length=2000)


class MensajeSchema(BaseModel):
    contenido: str = Field(default="", max_length=2000)
    reporte_id: Optional[int] = Field(default=None, gt=0)


class AsignacionSchema(BaseModel):
    area_id: int = Field(gt=0)
    observaciones: Optional[str] = Field(default=None, max_length=2000)


def _abrir_cursor(dictionary: bool = True):
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=dictionary)
    return conexion, cursor


def _cerrar(conexion, cursor):
    try:
        if cursor is not None:
            cursor.close()
    finally:
        if conexion is not None:
            conexion.close()


def _usuario_publico(fila: dict) -> dict:
    return {
        "id": int(fila["id_usuario"]),
        "id_usuario": int(fila["id_usuario"]),
        "nombre": fila["nombre"],
        "email": fila["email"],
        "rol": fila["rol"],
        "activo": bool(fila.get("activo", True)),
    }


def _fecha_texto(valor) -> str:
    if isinstance(valor, (datetime, date)):
        return valor.isoformat(sep=" ") if isinstance(valor, datetime) else valor.isoformat()
    return str(valor or "")


def _reporte_publico(fila: dict, request: Request) -> dict:
    imagen = fila.get("imagen_url")
    if imagen and str(imagen).startswith("/media/"):
        imagen = PUBLIC_API_URL + str(imagen)
    return {
        "id": int(fila["id_reporte"]),
        "id_reporte": int(fila["id_reporte"]),
        "usuario_id": int(fila["id_usuario"]),
        "id_usuario": int(fila["id_usuario"]),
        "categoria_id": int(fila["id_categoria"]),
        "categoria": fila.get("categoria_nombre") or "Sin categoría",
        "area_id": fila.get("id_area"),
        "area_responsable_id": fila.get("id_area"),
        "area_responsable": fila.get("area_nombre"),
        "imagen": imagen,
        "imagen_url": imagen,
        "latitud": float(fila["latitud"]) if fila.get("latitud") is not None else None,
        "longitud": float(fila["longitud"]) if fila.get("longitud") is not None else None,
        "ubicacion_referencia": fila.get("ubicacion"),
        "ubicacion": fila.get("ubicacion"),
        "descripcion": fila.get("descripcion") or "",
        "fecha_hora": _fecha_texto(fila.get("fecha_hora")),
        "estado": fila.get("estado"),
        "usuario_nombre": fila.get("usuario_nombre") or "Usuario",
        "usuario_email": fila.get("usuario_email") or "",
    }


def _consultar_reporte(cursor, reporte_id: int):
    cursor.execute(
        """SELECT r.id_reporte, r.id_usuario, r.id_categoria, r.id_area,
                  r.imagen_url, r.latitud, r.longitud, r.ubicacion, r.descripcion,
                  r.fecha_hora, r.estado, c.nombre AS categoria_nombre,
                  a.nombre AS area_nombre, u.nombre AS usuario_nombre, u.email AS usuario_email
           FROM reportes r
           JOIN usuarios u ON u.id_usuario = r.id_usuario
           JOIN categorias_residuos c ON c.id_categoria = r.id_categoria
           LEFT JOIN areas_responsables a ON a.id_area = r.id_area
           WHERE r.id_reporte = %s""",
        (reporte_id,),
    )
    return cursor.fetchone()


def _guardar_imagen(data_url: str) -> tuple[str, Path]:
    coincidencia = re.fullmatch(r"data:image/(jpeg|png);base64,([A-Za-z0-9+/=]+)", data_url)
    if not coincidencia:
        raise HTTPException(status_code=422, detail="Formato de imagen no admitido.")
    mime, contenido_b64 = coincidencia.groups()
    try:
        contenido = base64.b64decode(contenido_b64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail="La imagen Base64 no es válida.")
    extension = "jpg" if mime == "jpeg" else "png"
    nombre = f"{uuid.uuid4().hex}.{extension}"
    try:
        MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        destino = MEDIA_DIR / nombre
        with destino.open("xb") as archivo:
            archivo.write(contenido)
    except OSError:
        raise HTTPException(
            status_code=503,
            detail="No está disponible el almacenamiento de fotografías. Configura un Persistent Disk de Render y MEDIA_DIR=/var/data/ecoruta/uploads.",
        )
    return f"/media/{nombre}", destino


@app.get("/")
def inicio():
    return {"api": "EcoRuta", "estado": "operativa", "base_datos": "ecoruta"}


@app.get("/health")
def health():
    try:
        datos = probar_conexion()
        return {"ok": True, "api": "operativa", **datos}
    except Exception as error:
        # No se devuelven credenciales ni detalles internos de conexión.
        raise HTTPException(
            status_code=503,
            detail=f"FastAPI está activo, pero no pudo conectarse a MySQL ecoruta ({type(error).__name__}). Revisa MYSQL_PASSWORD, CA de Aiven y reglas de red.",
        )


@app.post("/auth/registro", status_code=201)
def registrar(data: RegistroSchema):
    conexion = cursor = None
    try:
        conexion, cursor = _abrir_cursor()
        cursor.execute("SELECT id_usuario FROM usuarios WHERE email = %s", (str(data.email).lower(),))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="El correo ya está registrado.")
        cursor.execute(
            """INSERT INTO usuarios (nombre, email, password_hash, rol, activo)
               VALUES (%s, %s, %s, 'usuario', TRUE)""",
            (data.nombre.strip(), str(data.email).lower(), hash_password(data.contrasena)),
        )
        conexion.commit()
        return {"ok": True, "mensaje": "Cuenta creada correctamente."}
    except HTTPException:
        if conexion:
            conexion.rollback()
        raise
    except IntegrityError:
        if conexion:
            conexion.rollback()
        raise HTTPException(status_code=409, detail="El correo ya está registrado.")
    except Error:
        if conexion:
            conexion.rollback()
        raise HTTPException(status_code=500, detail="No se pudo registrar la cuenta en MySQL.")
    finally:
        if conexion:
            _cerrar(conexion, cursor)


@app.post("/auth/login")
def login(data: LoginSchema):
    conexion = cursor = None
    try:
        conexion, cursor = _abrir_cursor()
        cursor.execute(
            "SELECT id_usuario, nombre, email, password_hash, rol, activo FROM usuarios WHERE email = %s",
            (str(data.email).lower(),),
        )
        fila = cursor.fetchone()
        if not fila or not bool(fila.get("activo")):
            raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos, o cuenta inactiva.")
        valida, migrar = verificar_password(data.contrasena, fila.get("password_hash"))
        if not valida:
            raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos.")
        if migrar:
            cursor.execute(
                "UPDATE usuarios SET password_hash = %s WHERE id_usuario = %s",
                (hash_password(data.contrasena), fila["id_usuario"]),
            )
            conexion.commit()
        public = _usuario_publico(fila)
        token = crear_token(public)
        return {"access_token": token, "token_type": "bearer", "usuario": public, **public}
    finally:
        if conexion:
            _cerrar(conexion, cursor)


@app.get("/auth/me")
def mi_sesion(auth=Depends(usuario_actual)):
    conexion = cursor = None
    try:
        conexion, cursor = _abrir_cursor()
        cursor.execute(
            "SELECT id_usuario, nombre, email, rol, activo FROM usuarios WHERE id_usuario = %s",
            (auth["id"],),
        )
        fila = cursor.fetchone()
        if not fila or not fila.get("activo"):
            raise HTTPException(status_code=401, detail="La cuenta ya no está activa.")
        return _usuario_publico(fila)
    finally:
        if conexion:
            _cerrar(conexion, cursor)


@app.get("/usuarios")
def listar_usuarios(auth=Depends(exigir_admin)):
    conexion = cursor = None
    try:
        conexion, cursor = _abrir_cursor()
        cursor.execute(
            """SELECT u.id_usuario, u.nombre, u.email, u.rol, u.activo,
                      COUNT(r.id_reporte) AS total_reportes
               FROM usuarios u LEFT JOIN reportes r ON r.id_usuario = u.id_usuario
               GROUP BY u.id_usuario, u.nombre, u.email, u.rol, u.activo
               ORDER BY u.nombre"""
        )
        return [
            {**_usuario_publico(fila), "total_reportes": int(fila.get("total_reportes") or 0)}
            for fila in cursor.fetchall()
        ]
    finally:
        if conexion:
            _cerrar(conexion, cursor)


@app.put("/usuarios/{usuario_id}")
def actualizar_perfil(usuario_id: int, data: PerfilSchema, auth=Depends(usuario_actual)):
    if auth["id"] != usuario_id and auth["rol"] != "admin":
        raise HTTPException(status_code=403, detail="No puedes modificar otro perfil.")
    conexion = cursor = None
    try:
        conexion, cursor = _abrir_cursor()
        cursor.execute("SELECT id_usuario FROM usuarios WHERE id_usuario = %s", (usuario_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Usuario no encontrado.")
        correo = str(data.email).lower()
        cursor.execute("SELECT id_usuario FROM usuarios WHERE email = %s AND id_usuario <> %s", (correo, usuario_id))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="Ese correo ya está registrado.")
        if data.nueva_contrasena:
            cursor.execute(
                "UPDATE usuarios SET nombre = %s, email = %s, password_hash = %s WHERE id_usuario = %s",
                (data.nombre.strip(), correo, hash_password(data.nueva_contrasena), usuario_id),
            )
        else:
            cursor.execute(
                "UPDATE usuarios SET nombre = %s, email = %s WHERE id_usuario = %s",
                (data.nombre.strip(), correo, usuario_id),
            )
        conexion.commit()
        cursor.execute(
            "SELECT id_usuario, nombre, email, rol, activo FROM usuarios WHERE id_usuario = %s",
            (usuario_id,),
        )
        return {"ok": True, "usuario": _usuario_publico(cursor.fetchone())}
    except HTTPException:
        if conexion:
            conexion.rollback()
        raise
    except IntegrityError:
        if conexion:
            conexion.rollback()
        raise HTTPException(status_code=409, detail="El correo ya está registrado.")
    finally:
        if conexion:
            _cerrar(conexion, cursor)


@app.get("/catalogos/categorias")
def listar_categorias(auth=Depends(usuario_actual)):
    conexion = cursor = None
    try:
        conexion, cursor = _abrir_cursor()
        cursor.execute(
            "SELECT id_categoria AS id, nombre, descripcion FROM categorias_residuos WHERE activo = TRUE ORDER BY nombre"
        )
        return cursor.fetchall()
    finally:
        if conexion:
            _cerrar(conexion, cursor)


@app.get("/catalogos/areas")
def listar_areas(auth=Depends(usuario_actual)):
    conexion = cursor = None
    try:
        conexion, cursor = _abrir_cursor()
        cursor.execute(
            "SELECT id_area AS id, nombre, institucion, nivel_gobierno, competencia FROM areas_responsables WHERE activo = TRUE ORDER BY nombre"
        )
        return cursor.fetchall()
    finally:
        if conexion:
            _cerrar(conexion, cursor)


@app.get("/reportes")
def listar_reportes(
    request: Request,
    limite: int = Query(100, ge=1, le=500),
    usuario_id: Optional[int] = Query(default=None, gt=0),
    auth=Depends(usuario_actual),
):
    if auth["rol"] != "admin" and usuario_id is not None and usuario_id != auth["id"]:
        raise HTTPException(status_code=403, detail="No puedes consultar los reportes privados de otra persona.")
    conexion = cursor = None
    try:
        conexion, cursor = _abrir_cursor()
        sql = """SELECT r.id_reporte, r.id_usuario, r.id_categoria, r.id_area,
                        r.imagen_url, r.latitud, r.longitud, r.ubicacion, r.descripcion,
                        r.fecha_hora, r.estado, c.nombre AS categoria_nombre,
                        a.nombre AS area_nombre, u.nombre AS usuario_nombre, u.email AS usuario_email
                 FROM reportes r
                 JOIN usuarios u ON u.id_usuario = r.id_usuario
                 JOIN categorias_residuos c ON c.id_categoria = r.id_categoria
                 LEFT JOIN areas_responsables a ON a.id_area = r.id_area"""
        parametros = []
        if usuario_id is not None:
            sql += " WHERE r.id_usuario = %s"
            parametros.append(usuario_id)
        sql += " ORDER BY r.fecha_hora DESC, r.id_reporte DESC LIMIT %s"
        parametros.append(limite)
        cursor.execute(sql, tuple(parametros))
        return [_reporte_publico(fila, request) for fila in cursor.fetchall()]
    finally:
        if conexion:
            _cerrar(conexion, cursor)


@app.get("/reportes/{reporte_id}")
def obtener_reporte(reporte_id: int, request: Request, auth=Depends(usuario_actual)):
    conexion = cursor = None
    try:
        conexion, cursor = _abrir_cursor()
        fila = _consultar_reporte(cursor, reporte_id)
        if not fila:
            raise HTTPException(status_code=404, detail="Reporte no encontrado.")
        return _reporte_publico(fila, request)
    finally:
        if conexion:
            _cerrar(conexion, cursor)


@app.post("/reportes", status_code=201)
def crear_reporte(data: ReporteSchema, request: Request, auth=Depends(usuario_actual)):
    conexion = cursor = None
    ruta_archivo = None
    try:
        conexion, cursor = _abrir_cursor(dictionary=False)
        cursor.execute("SELECT id_categoria FROM categorias_residuos WHERE id_categoria = %s AND activo = TRUE", (data.categoria_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=422, detail="Selecciona una categoría existente y activa.")
        imagen_url, ruta_archivo = _guardar_imagen(data.imagen)
        cursor.execute(
            """INSERT INTO reportes
               (id_usuario, id_categoria, id_area, imagen_url, latitud, longitud, ubicacion, descripcion, estado)
               VALUES (%s, %s, NULL, %s, %s, %s, %s, %s, 'Pendiente')""",
            (auth["id"], data.categoria_id, imagen_url, data.latitud, data.longitud,
             (data.ubicacion_referencia or "").strip() or None, data.descripcion.strip()),
        )
        reporte_id = cursor.lastrowid
        cursor.execute(
            """INSERT INTO seguimiento_reportes
               (id_reporte, id_usuario, estado_anterior, estado_nuevo, observaciones)
               VALUES (%s, %s, NULL, 'Pendiente', %s)""",
            (reporte_id, auth["id"], "Reporte recibido por EcoRuta."),
        )
        conexion.commit()
        return {"id": reporte_id, "id_reporte": reporte_id, "mensaje": "Reporte creado correctamente."}
    except HTTPException:
        if conexion:
            conexion.rollback()
        if ruta_archivo and ruta_archivo.exists():
            ruta_archivo.unlink(missing_ok=True)
        raise
    except Error:
        if conexion:
            conexion.rollback()
        if ruta_archivo and ruta_archivo.exists():
            ruta_archivo.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="No se pudo guardar el reporte en MySQL.")
    finally:
        if conexion:
            _cerrar(conexion, cursor)


@app.delete("/reportes/{reporte_id}")
def eliminar_reporte(reporte_id: int, auth=Depends(usuario_actual)):
    conexion = cursor = None
    archivo = None
    try:
        conexion, cursor = _abrir_cursor(dictionary=False)
        cursor.execute("SELECT id_usuario, imagen_url FROM reportes WHERE id_reporte = %s", (reporte_id,))
        fila = cursor.fetchone()
        if not fila:
            raise HTTPException(status_code=404, detail="Reporte no encontrado.")
        propietario_id, imagen_url = fila
        if auth["rol"] != "admin" and int(propietario_id) != auth["id"]:
            raise HTTPException(status_code=403, detail="Solo puedes eliminar tus propios reportes.")
        cursor.execute("DELETE FROM reportes WHERE id_reporte = %s", (reporte_id,))
        conexion.commit()
        if imagen_url and str(imagen_url).startswith("/media/"):
            nombre = str(imagen_url).rsplit("/", 1)[-1]
            archivo = MEDIA_DIR / nombre
        if archivo and archivo.is_file() and archivo.parent == MEDIA_DIR:
            archivo.unlink(missing_ok=True)
        return {"ok": True, "mensaje": "Reporte eliminado correctamente."}
    except HTTPException:
        if conexion:
            conexion.rollback()
        raise
    finally:
        if conexion:
            _cerrar(conexion, cursor)


@app.put("/reportes/{reporte_id}/estado")
def cambiar_estado(reporte_id: int, data: EstadoSchema, auth=Depends(exigir_admin)):
    if data.estado not in ESTADOS:
        raise HTTPException(status_code=422, detail="Estado de reporte no permitido.")
    if data.estado == "Rechazado" and not (data.justificacion or "").strip():
        raise HTTPException(status_code=422, detail="Para rechazar un reporte debes escribir una justificación.")
    conexion = cursor = None
    try:
        conexion, cursor = _abrir_cursor(dictionary=False)
        cursor.execute("SELECT id_usuario, estado FROM reportes WHERE id_reporte = %s", (reporte_id,))
        fila = cursor.fetchone()
        if not fila:
            raise HTTPException(status_code=404, detail="Reporte no encontrado.")
        propietario_id, estado_anterior = fila
        cursor.execute("UPDATE reportes SET estado = %s WHERE id_reporte = %s", (data.estado, reporte_id))
        cursor.execute(
            """INSERT INTO seguimiento_reportes
               (id_reporte, id_usuario, estado_anterior, estado_nuevo, observaciones)
               VALUES (%s, %s, %s, %s, %s)""",
            (reporte_id, auth["id"], estado_anterior, data.estado, (data.justificacion or "").strip() or None),
        )
        texto = data.justificacion.strip() if data.justificacion else f"El estado cambió a: {data.estado}."
        titulo = "Actualización de tu reporte"
        cursor.execute(
            "INSERT INTO notificaciones (id_usuario, id_reporte, titulo, contenido, leida) VALUES (%s, %s, %s, %s, FALSE)",
            (propietario_id, reporte_id, titulo, texto),
        )
        conexion.commit()
        return {"ok": True, "mensaje": "Estado actualizado correctamente."}
    except HTTPException:
        if conexion:
            conexion.rollback()
        raise
    except Error:
        if conexion:
            conexion.rollback()
        raise HTTPException(status_code=500, detail="No se pudo actualizar el estado del reporte.")
    finally:
        if conexion:
            _cerrar(conexion, cursor)


@app.get("/reportes/{reporte_id}/seguimiento")
def consultar_seguimiento(reporte_id: int, auth=Depends(usuario_actual)):
    conexion = cursor = None
    try:
        conexion, cursor = _abrir_cursor()
        cursor.execute("SELECT id_usuario FROM reportes WHERE id_reporte = %s", (reporte_id,))
        reporte = cursor.fetchone()
        if not reporte:
            raise HTTPException(status_code=404, detail="Reporte no encontrado.")
        if auth["rol"] != "admin" and int(reporte["id_usuario"]) != auth["id"]:
            raise HTTPException(status_code=403, detail="Solo puedes consultar el seguimiento de tus propios reportes.")
        cursor.execute(
            """SELECT s.id_seguimiento AS id, s.id_reporte AS reporte_id,
                      s.estado_anterior, s.estado_nuevo AS estado, s.observaciones AS observacion,
                      s.fecha_hora, u.nombre AS usuario_nombre
               FROM seguimiento_reportes s
               LEFT JOIN usuarios u ON u.id_usuario = s.id_usuario
               WHERE s.id_reporte = %s ORDER BY s.fecha_hora, s.id_seguimiento""",
            (reporte_id,),
        )
        return cursor.fetchall()
    finally:
        if conexion:
            _cerrar(conexion, cursor)


@app.post("/reportes/{reporte_id}/asignacion")
def asignar_area(reporte_id: int, data: AsignacionSchema, auth=Depends(exigir_admin)):
    conexion = cursor = None
    try:
        conexion, cursor = _abrir_cursor(dictionary=False)
        cursor.execute("SELECT id_usuario, estado FROM reportes WHERE id_reporte = %s", (reporte_id,))
        reporte = cursor.fetchone()
        if not reporte:
            raise HTTPException(status_code=404, detail="Reporte no encontrado.")
        cursor.execute("SELECT id_area FROM areas_responsables WHERE id_area = %s AND activo = TRUE", (data.area_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Área responsable no encontrada o inactiva.")
        cursor.execute("UPDATE reportes SET id_area = %s WHERE id_reporte = %s", (data.area_id, reporte_id))
        cursor.execute(
            """INSERT INTO asignaciones_reportes
               (id_reporte, id_area, id_usuario_asignador, observaciones)
               VALUES (%s, %s, %s, %s)""",
            (reporte_id, data.area_id, auth["id"], (data.observaciones or "").strip() or None),
        )
        cursor.execute(
            """INSERT INTO seguimiento_reportes
               (id_reporte, id_usuario, estado_anterior, estado_nuevo, observaciones)
               VALUES (%s, %s, %s, %s, %s)""",
            (reporte_id, auth["id"], reporte[1], reporte[1], (data.observaciones or "Área responsable asignada.").strip()),
        )
        cursor.execute(
            "INSERT INTO notificaciones (id_usuario, id_reporte, titulo, contenido, leida) VALUES (%s, %s, %s, %s, FALSE)",
            (reporte[0], reporte_id, "Área responsable asignada", "Tu reporte fue canalizado al área correspondiente."),
        )
        conexion.commit()
        return {"ok": True, "mensaje": "Área responsable asignada correctamente."}
    except HTTPException:
        if conexion:
            conexion.rollback()
        raise
    except Error:
        if conexion:
            conexion.rollback()
        raise HTTPException(status_code=500, detail="No se pudo asignar el área responsable.")
    finally:
        if conexion:
            _cerrar(conexion, cursor)


@app.get("/mensajes")
def listar_mensajes(auth=Depends(usuario_actual), limite: int = Query(100, ge=1, le=300)):
    conexion = cursor = None
    try:
        conexion, cursor = _abrir_cursor()
        cursor.execute(
            """SELECT m.id_mensaje AS id, m.id_usuario AS usuario_id,
                      m.id_reporte AS reporte_id, m.contenido, m.fecha_hora,
                      u.nombre AS usuario_nombre
               FROM mensajes m JOIN usuarios u ON u.id_usuario = m.id_usuario
               ORDER BY m.fecha_hora DESC, m.id_mensaje DESC LIMIT %s""",
            (limite,),
        )
        filas = cursor.fetchall()
        filas.reverse()
        for fila in filas:
            fila["fecha_hora"] = _fecha_texto(fila.get("fecha_hora"))
        return filas
    finally:
        if conexion:
            _cerrar(conexion, cursor)


@app.post("/mensajes", status_code=201)
def enviar_mensaje(data: MensajeSchema, auth=Depends(usuario_actual)):
    contenido = data.contenido.strip() or ("Reporte compartido" if data.reporte_id else "")
    if not contenido:
        raise HTTPException(status_code=422, detail="El mensaje no puede estar vacío.")
    conexion = cursor = None
    try:
        conexion, cursor = _abrir_cursor(dictionary=False)
        if data.reporte_id:
            cursor.execute("SELECT id_reporte FROM reportes WHERE id_reporte = %s", (data.reporte_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="El reporte adjunto no existe.")
        cursor.execute(
            "INSERT INTO mensajes (id_usuario, id_reporte, contenido) VALUES (%s, %s, %s)",
            (auth["id"], data.reporte_id, contenido),
        )
        mensaje_id = cursor.lastrowid
        conexion.commit()
        return {"id": mensaje_id, "mensaje": "Mensaje enviado correctamente."}
    except HTTPException:
        if conexion:
            conexion.rollback()
        raise
    finally:
        if conexion:
            _cerrar(conexion, cursor)


@app.get("/estadisticas")
def estadisticas(usuario_id: Optional[int] = None, auth=Depends(usuario_actual)):
    if auth["rol"] != "admin" and usuario_id is not None and usuario_id != auth["id"]:
        raise HTTPException(status_code=403, detail="No puedes consultar las estadísticas de otro usuario.")
    objetivo = usuario_id if usuario_id is not None else (auth["id"] if auth["rol"] != "admin" else None)
    conexion = cursor = None
    try:
        conexion, cursor = _abrir_cursor(dictionary=False)
        filtro = " WHERE id_usuario = %s" if objetivo is not None else ""
        params = (objetivo,) if objetivo is not None else ()
        cursor.execute(f"SELECT COUNT(*) FROM reportes{filtro}", params)
        total = int(cursor.fetchone()[0] or 0)
        cursor.execute(
            f"SELECT COUNT(*) FROM reportes{filtro}{' AND' if filtro else ' WHERE'} estado = %s",
            params + ("Pendiente",),
        )
        pendientes = int(cursor.fetchone()[0] or 0)
        cursor.execute(
            f"SELECT COUNT(*) FROM reportes{filtro}{' AND' if filtro else ' WHERE'} estado = %s",
            params + ("Atendido",),
        )
        atendidos = int(cursor.fetchone()[0] or 0)
        cursor.execute(
            "SELECT COUNT(*) FROM mensajes WHERE id_usuario = %s" if objetivo is not None else "SELECT COUNT(*) FROM mensajes",
            (objetivo,) if objetivo is not None else (),
        )
        mensajes = int(cursor.fetchone()[0] or 0)
        return {"reportes": total, "pendientes": pendientes, "atendidos": atendidos, "mensajes": mensajes}
    finally:
        if conexion:
            _cerrar(conexion, cursor)


@app.get("/admin/estadisticas")
def estadisticas_admin(auth=Depends(exigir_admin)):
    conexion = cursor = None
    try:
        conexion, cursor = _abrir_cursor(dictionary=False)
        cursor.execute("SELECT COUNT(*) FROM usuarios")
        usuarios = int(cursor.fetchone()[0] or 0)
        cursor.execute(
            """SELECT COUNT(*),
                      SUM(estado = 'Pendiente'),
                      SUM(estado = 'Atendido')
               FROM reportes"""
        )
        total, pendientes, atendidos = cursor.fetchone()
        return {
            "total_usuarios": usuarios,
            "total_reportes": int(total or 0),
            "pendientes": int(pendientes or 0),
            "atendidos": int(atendidos or 0),
        }
    finally:
        if conexion:
            _cerrar(conexion, cursor)


@app.get("/admin/estadisticas/categorias")
def estadisticas_categorias(auth=Depends(exigir_admin)):
    conexion = cursor = None
    try:
        conexion, cursor = _abrir_cursor()
        cursor.execute(
            """SELECT c.id_categoria AS id, c.nombre, COUNT(r.id_reporte) AS total
               FROM categorias_residuos c LEFT JOIN reportes r ON r.id_categoria = c.id_categoria
               GROUP BY c.id_categoria, c.nombre ORDER BY total DESC, c.nombre"""
        )
        return cursor.fetchall()
    finally:
        if conexion:
            _cerrar(conexion, cursor)


@app.get("/admin/estadisticas/areas")
def estadisticas_areas(auth=Depends(exigir_admin)):
    conexion = cursor = None
    try:
        conexion, cursor = _abrir_cursor()
        cursor.execute(
            """SELECT a.id_area AS id, a.nombre, COUNT(r.id_reporte) AS total
               FROM areas_responsables a LEFT JOIN reportes r ON r.id_area = a.id_area
               GROUP BY a.id_area, a.nombre ORDER BY total DESC, a.nombre"""
        )
        return cursor.fetchall()
    finally:
        if conexion:
            _cerrar(conexion, cursor)


@app.get("/admin/estadisticas/zonas")
def estadisticas_zonas(auth=Depends(exigir_admin), limite: int = Query(10, ge=1, le=100)):
    conexion = cursor = None
    try:
        conexion, cursor = _abrir_cursor()
        cursor.execute(
            """SELECT COALESCE(NULLIF(ubicacion, ''), 'Sin ubicación') AS zona,
                      COUNT(*) AS total
               FROM reportes GROUP BY zona ORDER BY total DESC LIMIT %s""",
            (limite,),
        )
        return cursor.fetchall()
    finally:
        if conexion:
            _cerrar(conexion, cursor)


@app.get("/admin/estadisticas/periodo")
def estadisticas_periodo(
    desde: date,
    hasta: date,
    auth=Depends(exigir_admin),
):
    if hasta < desde:
        raise HTTPException(status_code=422, detail="La fecha final debe ser posterior a la inicial.")
    conexion = cursor = None
    try:
        conexion, cursor = _abrir_cursor()
        cursor.execute(
            """SELECT DATE_FORMAT(fecha_hora, '%Y-%m') AS periodo, COUNT(*) AS total
               FROM reportes WHERE fecha_hora >= %s AND fecha_hora < DATE_ADD(%s, INTERVAL 1 DAY)
               GROUP BY DATE_FORMAT(fecha_hora, '%Y-%m') ORDER BY periodo""",
            (desde, hasta),
        )
        return cursor.fetchall()
    finally:
        if conexion:
            _cerrar(conexion, cursor)


@app.get("/notificaciones")
def listar_notificaciones(auth=Depends(usuario_actual)):
    conexion = cursor = None
    try:
        conexion, cursor = _abrir_cursor()
        cursor.execute(
            """SELECT id_notificacion AS id, id_reporte AS reporte_id, titulo,
                      contenido, leida, fecha_hora
               FROM notificaciones WHERE id_usuario = %s
               ORDER BY fecha_hora DESC, id_notificacion DESC LIMIT 100""",
            (auth["id"],),
        )
        return cursor.fetchall()
    finally:
        if conexion:
            _cerrar(conexion, cursor)


@app.put("/notificaciones/{notificacion_id}/leida")
def marcar_notificacion(notificacion_id: int, auth=Depends(usuario_actual)):
    conexion = cursor = None
    try:
        conexion, cursor = _abrir_cursor(dictionary=False)
        cursor.execute(
            "UPDATE notificaciones SET leida = TRUE WHERE id_notificacion = %s AND id_usuario = %s",
            (notificacion_id, auth["id"]),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Notificación no encontrada.")
        conexion.commit()
        return {"ok": True}
    finally:
        if conexion:
            _cerrar(conexion, cursor)


@app.get("/media/{nombre_archivo}")
def obtener_media(nombre_archivo: str):
    if not re.fullmatch(r"[a-f0-9]{32}\.(jpg|png)", nombre_archivo):
        raise HTTPException(status_code=404, detail="Imagen no encontrada.")
    archivo = (MEDIA_DIR / nombre_archivo).resolve()
    if archivo.parent != MEDIA_DIR or not archivo.is_file():
        raise HTTPException(status_code=404, detail="Imagen no encontrada.")
    media_type = "image/jpeg" if archivo.suffix == ".jpg" else "image/png"
    return FileResponse(archivo, media_type=media_type, headers={"Cache-Control": "public, max-age=86400"})
