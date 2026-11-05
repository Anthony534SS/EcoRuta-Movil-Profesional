import base64
import requests

API_URL = "https://ecoruta-api-antonio.onrender.com"
ADMIN_EMAIL = "admin@ecoruta.mx"
ADMIN_PASSWORD = "EcoRuta2026"
MENSAJES_LOCALES = []


def iniciar_sesion(email, contrasena):
    print(f"Haciendo POST a {API_URL}/auth/login con email: {email}")
    try:
        resp = requests.post(
            f"{API_URL}/auth/login",
            json={
                "email": email.strip().lower(),
                "contrasena": contrasena.strip()
            },
            timeout=8,
        )
        print("Status Code de Render:", resp.status_code)
        if resp.status_code == 200:
            return resp.json()
        else:
            print("Respuesta de error de la API:", resp.text)
    except Exception as error:
        print(f"Error de conexión con la API: {error}")
    return None


def iniciar_sesion_admin(email, contrasena):
    usuario = iniciar_sesion(email, contrasena)
    print("Usuario retornado por iniciar_sesion:", usuario)
    if usuario and usuario.get("rol") == "admin":
        return usuario
    return None


def registrar_usuario(nombre, email, contrasena):
    try:
        resp = requests.post(
            f"{API_URL}/auth/registro",
            json={
                "nombre": nombre,
                "email": email,
                "contrasena": contrasena
            },
            timeout=8,
        )
        if resp.status_code == 200:
            datos = resp.json()
            return datos.get("ok", False), datos.get("mensaje", "Respuesta inesperada.")
        else:
            return False, "Error en la respuesta del servidor."
    except Exception as error:
        print(f"Error de conexión en registro: {error}")
        return False, "No se pudo conectar con el servidor."


def obtener_reportes(limite=None, usuario_id=None):
    try:
        params = {}
        if limite:
            params["limite"] = limite
        if usuario_id:
            params["usuario_id"] = usuario_id
            
        resp = requests.get(f"{API_URL}/reportes", params=params, timeout=8)
        if resp.status_code == 200:
            return resp.json()
    except Exception as error:
        print(f"Error al obtener reportes: {error}")
    return []


def obtener_reporte(reporte_id):
    try:
        resp = requests.get(f"{API_URL}/reportes/{reporte_id}", timeout=8)
        if resp.status_code == 200:
            return resp.json()
    except Exception as error:
        print(f"Error al obtener el reporte #{reporte_id}: {error}")
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
        resp = requests.post(f"{API_URL}/reportes", json=payload, timeout=12)
        if resp.status_code == 200:
            return resp.json().get("id")
    except Exception as error:
        print(f"Error al enviar reporte: {error}")
    return None


def eliminar_reporte(reporte_id, usuario_id=None, es_admin=False):
    """Envía la solicitud de eliminación de reporte al backend."""
    try:
        # Enviar parámetro o body informando al backend del permiso de administrador
        params = {"admin": "true"} if es_admin else {}
        payload = {"usuario_id": usuario_id, "es_admin": es_admin}
        
        # Probar DELETE a la ruta correspondiente
        respuesta = requests.delete(
            f"{API_URL}/reportes/{reporte_id}",
            json=payload,
            params=params,
            timeout=3
        )

        if respuesta.status_code in (200, 204):
            return True
        else:
            print(f"El backend rechazó la eliminación del reporte #{reporte_id}. Código HTTP: {respuesta.status_code}")
            return False
            
    except Exception as e:
        print(f"Excepción al intentar eliminar reporte #{reporte_id}: {e}")
        return False


def actualizar_estado_reporte(reporte_id, estado):
    try:
        resp = requests.put(
            f"{API_URL}/reportes/{reporte_id}/estado",
            json={"estado": estado},
            timeout=8,
        )
        return resp.status_code == 200
    except Exception:
        return False


def actualizar_perfil(usuario_id, nombre, email, nueva_contrasena=""):
    try:
        payload = {"nombre": nombre, "email": email, "nueva_contrasena": nueva_contrasena}
        resp = requests.put(f"{API_URL}/usuarios/{usuario_id}", json=payload, timeout=8)
        datos = resp.json()
        if resp.status_code == 200:
            return True, "Perfil actualizado correctamente.", datos.get("usuario")
        return False, datos.get("detail", "Error al actualizar."), None
    except Exception:
        return False, "Error de conexión con el servidor.", None


def obtener_usuarios():
    """Obtiene la lista completa de usuarios registrados."""
    try:
        respuesta = requests.get(f"{API_URL}/usuarios", timeout=3)
        if respuesta.status_code == 200:
            datos = respuesta.json()
            if isinstance(datos, dict) and "usuarios" in datos:
                return datos["usuarios"]
            return datos if isinstance(datos, list) else []
    except Exception as e:
        print(f"Error al obtener lista de usuarios: {e}")
    return []


def obtener_estadisticas(usuario_id=None):
    try:
        url = f"{API_URL}/estadisticas?usuario_id={usuario_id}" if usuario_id else f"{API_URL}/estadisticas"
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {"reportes": 0, "pendientes": 0, "mensajes": 0}


def obtener_estadisticas_admin():
    """Consulta las estadísticas globales desde la API para el panel de admin."""
    stats = {
        "usuarios": 0,
        "reportes": 0,
        "pendientes": 0,
        "atendidos": 0
    }
    
    try:
        # Petición a la API de estadísticas o cálculo desde los endpoints existentes
        respuesta = requests.get(f"{API_URL}/admin/estadisticas", timeout=3)
        if respuesta.status_code == 200:
            datos = respuesta.json()
            return {
                "usuarios": datos.get("total_usuarios", datos.get("usuarios", 0)),
                "reportes": datos.get("total_reportes", datos.get("reportes", 0)),
                "pendientes": datos.get("pendientes", 0),
                "atendidos": datos.get("atendidos", 0)
            }
    except Exception as e:
        print(f"Error al obtener estadísticas del backend: {e}")

    # Respaldos usando los endpoints directos si no existe el endpoint consolidado
    try:
        usuarios = obtener_usuarios()
        stats["usuarios"] = len(usuarios) if isinstance(usuarios, list) else 0

        reportes = obtener_reportes()
        if isinstance(reportes, list):
            stats["reportes"] = len(reportes)
            stats["pendientes"] = sum(1 for r in reportes if str(r.get("estado")).lower() == "pendiente")
            stats["atendidos"] = sum(1 for r in reportes if str(r.get("estado")).lower() in ("atendido", "resuelto"))
    except Exception as e:
        print(f"Error calculando respaldos de estadísticas: {e}")

    return stats


def obtener_mensajes():
    try:
        # Asegúrate de colocar la URL exacta de tu endpoint de mensajes (GET)
        respuesta = requests.get(f"{BASE_URL}/mensajes")
        if respuesta.status_code == 200:
            datos = respuesta.json()
            # Si el endpoint devuelve un diccionario tipo {"mensajes": [...]}, retorna esa lista
            if isinstance(datos, dict) and "mensajes" in datos:
                return datos["mensajes"]
            return datos if isinstance(datos, list) else []
        return []
    except Exception as e:
        print("Error al obtener mensajes:", e)
        return []


def enviar_mensaje(texto, usuario_id, reporte_id=None):
    global MENSAJES_LOCALES

    # Buscar el nombre del usuario desde el caché local
    nombre_usuario = "Usuario"
    if 'USUARIOS' in globals():
        for u in USUARIOS:
            if u.get("id") == usuario_id:
                nombre_usuario = u.get("nombre", "Usuario")
                break

    payload = {
        "contenido": texto,
        "usuario_id": usuario_id,
        "usuario_nombre": nombre_usuario,
        "reporte_id": reporte_id,
        "fecha_hora": "Reciente",
    }

    try:
        respuesta = requests.post(f"{API_URL}/mensajes", json=payload, timeout=3)
        if respuesta.status_code in (200, 201):
            datos_resp = respuesta.json()
            
            # Solo guardamos 'datos_resp' si el servidor devolvió el mensaje formateado con su 'contenido'
            if isinstance(datos_resp, dict) and "contenido" in datos_resp:
                MENSAJES_LOCALES.append(datos_resp)
            else:
                # Si la API respondió con {'ok': True, ...}, guardamos el 'payload' que nosotros creamos
                payload["id"] = len(MENSAJES_LOCALES) + 1
                MENSAJES_LOCALES.append(payload)
            return True
    except Exception as e:
        print(f"Error al enviar mensaje a la API: {e}")

    # Fallback/Respaldo local si la API falla o no está disponible
    payload["id"] = len(MENSAJES_LOCALES) + 1
    MENSAJES_LOCALES.append(payload)
    return True


def obtener_mensajes():
    global MENSAJES_LOCALES
    try:
        respuesta = requests.get(f"{API_URL}/mensajes", timeout=3)
        if respuesta.status_code == 200:
            datos = respuesta.json()
            # Validamos que la API realmente devuelva una lista de mensajes válidos
            if isinstance(datos, list) and len(datos) > 0 and "contenido" in datos[0]:
                return datos
    except Exception as e:
        print(f"Error al obtener mensajes: {e}")
    
    # Retorna la lista local con los mensajes correctamente estructurados
    return MENSAJES_LOCALES