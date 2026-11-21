"""Cliente HTTP de EcoRuta. Todas las operaciones persistentes pasan por FastAPI."""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import copy
import time

# Se conserva la URL de Render que ya utilizaba el primer ZIP.
API_URL = os.getenv("API_BASE_URL", "https://ecoruta-api-antonio.onrender.com").strip().rstrip("/")

# Se conservan las credenciales de administrador configuradas en el proyecto original.
ADMIN_EMAIL = "admin@ecoruta.mx"
ADMIN_PASSWORD = "EcoRuta2026"

_TOKEN: str | None = None
_ULTIMO_ERROR_API: str | None = None
_CACHE_GET = {}
_CACHE_TTL = 12


def obtener_ultimo_error_api():
    return _ULTIMO_ERROR_API


def establecer_token(token):
    global _TOKEN

    if _TOKEN != token:
        _CACHE_GET.clear()

    _TOKEN = token


def cerrar_sesion():
    establecer_token(None)


def _peticion_http(endpoint, metodo="GET", datos=None, params=None, timeout=15):
    global _ULTIMO_ERROR_API

    metodo = metodo.upper()
    url = f"{API_URL}{endpoint}"

    if params:
        url += "?" + urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None}
        )

    clave_cache = (url, _TOKEN)

    # Consultar caché solamente para solicitudes GET.
    if metodo == "GET":
        guardado = _CACHE_GET.get(clave_cache)

        if guardado:
            tiempo_guardado, codigo, resultado = guardado

            if time.monotonic() - tiempo_guardado < _CACHE_TTL:
                _ULTIMO_ERROR_API = None
                return codigo, copy.deepcopy(resultado)

            _CACHE_GET.pop(clave_cache, None)

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    if _TOKEN:
        headers["Authorization"] = f"Bearer {_TOKEN}"

    payload = (
        json.dumps(datos, ensure_ascii=False).encode("utf-8")
        if datos is not None else None
    )

    request = urllib.request.Request(
        url,
        data=payload,
        headers=headers,
        method=metodo,
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:

            body = response.read().decode("utf-8", errors="replace")

            resultado = json.loads(body) if body else {}

            _ULTIMO_ERROR_API = None

            if metodo == "GET":
                _CACHE_GET[clave_cache] = (
                    time.monotonic(),
                    response.status,
                    copy.deepcopy(resultado),
                )
            else:
                # Si se modifica información, renovar las consultas.
                _CACHE_GET.clear()

            return response.status, resultado

    except urllib.error.HTTPError as error:

        if metodo != "GET":
            _CACHE_GET.clear()

        body = error.read().decode("utf-8", errors="replace")

        try:
            resultado = json.loads(body) if body else {}
        except json.JSONDecodeError:
            resultado = {
                "detail": body or f"HTTP {error.code}"
            }

        detalle = (
            resultado.get("detail")
            if isinstance(resultado, dict)
            else None
        )

        _ULTIMO_ERROR_API = str(
            detalle or f"La API respondió con HTTP {error.code}."
        )

        if error.code == 401 and endpoint != "/auth/login":
            cerrar_sesion()

        return error.code, resultado

    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        json.JSONDecodeError,
    ) as error:

        _ULTIMO_ERROR_API = (
            f"No se pudo conectar con FastAPI en {API_URL}. "
            f"Comprueba Render. ({type(error).__name__})"
        )

        print(_ULTIMO_ERROR_API)

        return None, {"detail": _ULTIMO_ERROR_API}


def _detalle(datos, predeterminado):
    return datos.get("detail", datos.get("mensaje", predeterminado)) if isinstance(datos, dict) else predeterminado


# AUTENTICACIÓN Y PERFIL

def iniciar_sesion(email, contrasena):
    codigo, datos = _peticion_http(
        "/auth/login", "POST",
        {"email": str(email or "").strip().lower(), "contrasena": str(contrasena or "")},
    )
    if codigo == 200 and isinstance(datos, dict):
        establecer_token(datos.get("access_token"))
        return datos.get("usuario", datos)
    return None


def iniciar_sesion_admin(email, contrasena):
    """Inicia sesión y distingue una cuenta normal de una cuenta administradora."""
    usuario = iniciar_sesion(email, contrasena)

    if not usuario:
        return None

    if str(usuario.get("rol", "")).strip().lower() == "admin":
        return usuario

    cerrar_sesion()
    _set_error(
        "El correo y la contraseña son válidos, pero esta cuenta no tiene "
        "permisos de administrador. Inicializa la cuenta administrativa con "
        "el archivo crear_admin.py y vuelve a intentarlo."
    )
    return None


def registrar_usuario(nombre, email, contrasena):
    codigo, datos = _peticion_http(
        "/auth/registro", "POST",
        {"nombre": nombre, "email": email, "contrasena": contrasena},
    )
    return codigo in (200, 201), _detalle(datos, "No se pudo registrar la cuenta.")


def actualizar_perfil(usuario_id, nombre, email, nueva_contrasena=""):
    payload = {
        "nombre": nombre,
        "email": email,
        "nueva_contrasena": nueva_contrasena or None,
    }
    codigo, datos = _peticion_http(f"/usuarios/{usuario_id}", "PUT", payload)
    if codigo == 200 and isinstance(datos, dict):
        return True, "Perfil actualizado correctamente.", datos.get("usuario")
    return False, _detalle(datos, "Error al actualizar el perfil."), None


def obtener_usuarios():
    codigo, datos = _peticion_http("/usuarios")
    return datos if codigo == 200 and isinstance(datos, list) else []


# CATÁLOGOS

def obtener_categorias():
    codigo, datos = _peticion_http("/catalogos/categorias")
    return datos if codigo == 200 and isinstance(datos, list) else []


def obtener_areas():
    codigo, datos = _peticion_http("/catalogos/areas")
    return datos if codigo == 200 and isinstance(datos, list) else []


# REPORTES

def obtener_reportes(limite=None, usuario_id=None):
    codigo, datos = _peticion_http(
        "/reportes", params={"limite": limite or 100, "usuario_id": usuario_id}, timeout=20
    )
    return datos if codigo == 200 and isinstance(datos, list) else []

def obtener_mis_reportes(limite=200):
    """Devuelve una lista vacía si no hay reportes y None si ocurrió un error."""
    codigo, datos = _peticion_http(
        "/reportes/mis-reportes",
        params={"limite": limite},
        timeout=20,
    )
    if codigo == 200 and isinstance(datos, list):
        return datos

    if codigo == 401:
        _set_error("Tu sesión expiró. Inicia sesión nuevamente.")
    elif codigo is None:
        _set_error("No hay conexión con el servidor. Inténtalo nuevamente.")
    else:
        _set_error("No fue posible consultar el historial en este momento.")
    return None


def obtener_reporte(reporte_id):
    codigo, datos = _peticion_http(f"/reportes/{reporte_id}")
    return datos if codigo == 200 and isinstance(datos, dict) else None


def crear_reporte(
    bytes_imagen, latitud, longitud, usuario_id,
    categoria_id=None, descripcion=None, ubicacion_referencia=None,
):
    if not bytes_imagen:
        return None
    if bytes_imagen.startswith(b"\xff\xd8\xff"):
        mime = "jpeg"
    elif bytes_imagen.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "png"
    else:
        _set_error("La fotografía debe ser JPG/JPEG o PNG.")
        return None
    if not categoria_id:
        _set_error("Selecciona una categoría de residuo.")
        return None
    imagen = f"data:image/{mime};base64," + base64.b64encode(bytes_imagen).decode("ascii")
    payload = {
        "imagen": imagen,
        "latitud": float(latitud),
        "longitud": float(longitud),
        "categoria_id": int(categoria_id),
        "descripcion": (descripcion or "").strip(),
        "ubicacion_referencia": (ubicacion_referencia or "").strip() or None,
    }
    codigo, datos = _peticion_http("/reportes", "POST", payload, timeout=45)
    if codigo in (200, 201) and isinstance(datos, dict):
        return datos.get("id") or datos.get("id_reporte")
    _set_error(_detalle(datos, "No se pudo guardar el reporte."))
    return None


def eliminar_reporte(reporte_id, usuario_id=None, es_admin=False):
    codigo, datos = _peticion_http(f"/reportes/{reporte_id}", "DELETE")
    if codigo not in (200, 204):
        _set_error(_detalle(datos, "No se pudo eliminar el reporte."))
    return codigo in (200, 204)


def actualizar_estado_reporte(reporte_id, estado, justificacion=None):
    codigo, datos = _peticion_http(
        f"/reportes/{reporte_id}/estado", "PUT",
        {"estado": estado, "justificacion": justificacion},
    )
    if codigo != 200:
        _set_error(_detalle(datos, "No se pudo actualizar el estado."))
    return codigo == 200


def obtener_seguimiento(reporte_id):
    codigo, datos = _peticion_http(f"/reportes/{reporte_id}/seguimiento")
    return datos if codigo == 200 and isinstance(datos, list) else []


def asignar_area(reporte_id, area_id, observaciones=None):
    codigo, datos = _peticion_http(
        f"/reportes/{reporte_id}/asignacion", "POST",
        {"area_id": int(area_id), "observaciones": observaciones},
    )
    if codigo != 200:
        _set_error(_detalle(datos, "No se pudo asignar el área."))
    return codigo == 200


# CHAT Y ESTADÍSTICAS

def obtener_mensajes():
    codigo, datos = _peticion_http("/mensajes", timeout=20)
    return datos if codigo == 200 and isinstance(datos, list) else []


def enviar_mensaje(texto, usuario_id, reporte_id=None):
    codigo, datos = _peticion_http(
        "/mensajes", "POST",
        {"contenido": texto or "", "reporte_id": reporte_id},
    )
    if codigo not in (200, 201):
        _set_error(_detalle(datos, "No se pudo enviar el mensaje."))
    return codigo in (200, 201)


def obtener_estadisticas(usuario_id=None):
    codigo, datos = _peticion_http("/estadisticas", params={"usuario_id": usuario_id})
    return datos if codigo == 200 and isinstance(datos, dict) else {
        "reportes": "—", "pendientes": "—", "atendidos": "—", "mensajes": "—"
    }


def obtener_estadisticas_admin():
    codigo, datos = _peticion_http("/admin/estadisticas")
    if codigo == 200 and isinstance(datos, dict):
        return {
            "usuarios": datos.get("total_usuarios", 0),
            "reportes": datos.get("total_reportes", 0),
            "pendientes": datos.get("pendientes", 0),
            "atendidos": datos.get("atendidos", 0),
        }
    return {"usuarios": "—", "reportes": "—", "pendientes": "—", "atendidos": "—"}


def _set_error(mensaje):
    global _ULTIMO_ERROR_API
    _ULTIMO_ERROR_API = str(mensaje)

