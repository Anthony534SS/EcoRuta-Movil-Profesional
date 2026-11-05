import base64
import json
import urllib.error
import urllib.request

API_URL = "https://ecoruta-api-antonio.onrender.com"
ADMIN_EMAIL = "admin@ecoruta.mx"
ADMIN_PASSWORD = "EcoRuta2026"
MENSAJES_LOCALES = []


def _peticion_http(endpoint, metodo="GET", datos=None, params=None, timeout=8):
    """Función auxiliar nativa que reemplaza a 'requests' sin requerir dependencias externas."""
    url = f"{API_URL}{endpoint}"
    if params:
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        url += f"?{query_string}"

    try:
        req = urllib.request.Request(url, method=metodo)
        req.add_header("Content-Type", "application/json")

        payload = None
        if datos is not None:
            payload = json.dumps(datos).encode("utf-8")

        with urllib.request.urlopen(req, data=payload, timeout=timeout) as respuesta:
            codigo = respuesta.status
            cuerpo = respuesta.read().decode("utf-8")
            datos_json = json.loads(cuerpo) if cuerpo else {}
            return codigo, datos_json

    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode("utf-8")
        datos_json = json.loads(cuerpo) if cuerpo else {}
        return e.code, datos_json
    except Exception as error:
        print(f"Error HTTP ({metodo} {url}): {error}")
        return None, None


# ------------------------------------------------------------------
# AUTENTICACIÓN
# ------------------------------------------------------------------

def iniciar_sesion(email, contrasena):
    print(f"Haciendo POST a {API_URL}/auth/login con email: {email}")
    payload = {
        "email": email.strip().lower(),
        "contrasena": contrasena.strip(),
    }
    codigo, datos = _peticion_http("/auth/login", metodo="POST", datos=payload, timeout=8)
    if codigo == 200 and isinstance(datos, dict):
        return datos
    print(f"Error login. Código HTTP: {codigo}, Respuesta: {datos}")
    return None


def iniciar_sesion_admin(email, contrasena):
    usuario = iniciar_sesion(email, contrasena)
    print("Usuario retornado por iniciar_sesion:", usuario)
    if usuario and usuario.get("rol") == "admin":
        return usuario
    return None


def registrar_usuario(nombre, email, contrasena):
    payload = {
        "nombre": nombre,
        "email": email,
        "contrasena": contrasena,
    }
    codigo, datos = _peticion_http("/auth/registro", metodo="POST", datos=payload, timeout=8)
    if codigo == 200 and isinstance(datos, dict):
        return datos.get("ok", False), datos.get("mensaje", "Respuesta inesperada.")
    return False, "No se pudo conectar con el servidor o error en la respuesta."


def actualizar_perfil(usuario_id, nombre, email, nueva_contrasena=""):
    payload = {"nombre": nombre, "email": email, "nueva_contrasena": nueva_contrasena}
    codigo, datos = _peticion_http(f"/usuarios/{usuario_id}", metodo="PUT", datos=payload, timeout=8)
    if codigo == 200 and isinstance(datos, dict):
        return True, "Perfil actualizado correctamente.", datos.get("usuario")
    mensaje = datos.get("detail", "Error al actualizar.") if isinstance(datos, dict) else "Error de conexión."
    return False, mensaje, None


def obtener_usuarios():
    """Obtiene la lista completa de usuarios registrados."""
    codigo, datos = _peticion_http("/usuarios", metodo="GET", timeout=5)
    if codigo == 200:
        if isinstance(datos, dict) and "usuarios" in datos:
            return datos["usuarios"]
        return datos if isinstance(datos, list) else []
    return []


# ------------------------------------------------------------------
# REPORTES
# ------------------------------------------------------------------

def obtener_reportes(limite=None, usuario_id=None):
    params = {}
    if limite:
        params["limite"] = limite
    if usuario_id:
        params["usuario_id"] = usuario_id

    codigo, datos = _peticion_http("/reportes", metodo="GET", params=params, timeout=8)
    if codigo == 200:
        if isinstance(datos, dict) and "reportes" in datos:
            return datos["reportes"]
        return datos if isinstance(datos, list) else []
    return []


def obtener_reporte(reporte_id):
    codigo, datos = _peticion_http(f"/reportes/{reporte_id}", metodo="GET", timeout=8)
    if codigo == 200 and isinstance(datos, dict):
        return datos
    return None


def crear_reporte(bytes_imagen, latitud, longitud, usuario_id):
    try:
        img_b64 = base64.b64encode(bytes_imagen).decode("utf-8")
        payload = {
            "imagen": f"data:image/jpeg;base64,{img_b64}",
            "latitud": latitud,
            "longitud": longitud,
            "usuario_id": usuario_id,
        }
        codigo, datos = _peticion_http("/reportes", metodo="POST", datos=payload, timeout=12)
        if codigo in (200, 201) and isinstance(datos, dict):
            return datos.get("id")
    except Exception as error:
        print(f"Error al procesar la imagen del reporte: {error}")
    return None


def eliminar_reporte(reporte_id, usuario_id=None, es_admin=False):
    """Envía la solicitud de eliminación de reporte al backend."""
    params = {"admin": "true"} if es_admin else {}
    payload = {"usuario_id": usuario_id, "es_admin": es_admin}
    
    codigo, _ = _peticion_http(
        f"/reportes/{reporte_id}",
        metodo="DELETE",
        datos=payload,
        params=params,
        timeout=5,
    )
    return codigo in (200, 204)


def actualizar_estado_reporte(reporte_id, estado):
    codigo, _ = _peticion_http(
        f"/reportes/{reporte_id}/estado",
        metodo="PUT",
        datos={"estado": estado},
        timeout=8,
    )
    return codigo == 200


# ------------------------------------------------------------------
# ESTADÍSTICAS Y CHAT
# ------------------------------------------------------------------

def obtener_estadisticas(usuario_id=None):
    endpoint = f"/estadisticas?usuario_id={usuario_id}" if usuario_id else "/estadisticas"
    codigo, datos = _peticion_http(endpoint, metodo="GET", timeout=8)
    if codigo == 200 and isinstance(datos, dict):
        return datos
    return {"reportes": 0, "pendientes": 0, "mensajes": len(MENSAJES_LOCALES)}


def obtener_estadisticas_admin():
    """Consulta las estadísticas globales para el panel de admin."""
    codigo, datos = _peticion_http("/admin/estadisticas", metodo="GET", timeout=5)
    if codigo == 200 and isinstance(datos, dict):
        return {
            "usuarios": datos.get("total_usuarios", datos.get("usuarios", 0)),
            "reportes": datos.get("total_reportes", datos.get("reportes", 0)),
            "pendientes": datos.get("pendientes", 0),
            "atendidos": datos.get("atendidos", 0),
        }

    # Respaldo realizando peticiones directas
    usuarios = obtener_usuarios()
    reportes = obtener_reportes()

    pendientes = sum(1 for r in reportes if str(r.get("estado")).lower() == "pendiente")
    atendidos = sum(
        1 for r in reportes if str(r.get("estado")).lower() in ("atendido", "resuelto")
    )

    return {
        "usuarios": len(usuarios) if isinstance(usuarios, list) else 0,
        "reportes": len(reportes) if isinstance(reportes, list) else 0,
        "pendientes": pendientes,
        "atendidos": atendidos,
    }


def obtener_mensajes():
    global MENSAJES_LOCALES
    codigo, datos = _peticion_http("/mensajes", metodo="GET", timeout=5)
    if codigo == 200:
        if isinstance(datos, dict) and "mensajes" in datos:
            return datos["mensajes"]
        if isinstance(datos, list) and len(datos) > 0:
            if isinstance(datos[0], dict) and "contenido" in datos[0]:
                return datos
    return MENSAJES_LOCALES


def enviar_mensaje(texto, usuario_id, reporte_id=None):
    global MENSAJES_LOCALES
    payload = {
        "contenido": texto,
        "usuario_id": usuario_id,
        "usuario_nombre": "Usuario",
        "reporte_id": reporte_id,
        "fecha_hora": "Reciente",
    }

    codigo, datos_resp = _peticion_http("/mensajes", metodo="POST", datos=payload, timeout=5)
    if codigo in (200, 201):
        if isinstance(datos_resp, dict) and "contenido" in datos_resp:
            MENSAJES_LOCALES.append(datos_resp)
        else:
            payload["id"] = len(MENSAJES_LOCALES) + 1
            MENSAJES_LOCALES.append(payload)
        return True

    # Fallback/Respaldo local si no hay respuesta de la API
    payload["id"] = len(MENSAJES_LOCALES) + 1
    MENSAJES_LOCALES.append(payload)
    return True
