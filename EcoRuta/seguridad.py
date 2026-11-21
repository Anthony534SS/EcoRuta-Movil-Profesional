"""Hash Argon2id y tokens JWT HS256 usando únicamente secretos del entorno."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from argon2 import PasswordHasher, exceptions as argon2_exceptions
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

ALGORITMO = "HS256"
SECRET_KEY = os.getenv("ECORUTA_SECRET_KEY", "")
TOKEN_MINUTOS = int(os.getenv("TOKEN_MINUTOS", "720"))
_PASSWORD_HASHER = PasswordHasher()
_BEARER = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return _PASSWORD_HASHER.hash(password)


def verificar_password(password: str, almacenada: str | None) -> tuple[bool, bool]:
    """Retorna (válida, debe_migrarse_a_argon2)."""
    if not almacenada:
        return False, False
    if almacenada.startswith("$argon2"):
        try:
            return _PASSWORD_HASHER.verify(almacenada, password), False
        except (
            argon2_exceptions.VerifyMismatchError,
            argon2_exceptions.VerificationError,
            argon2_exceptions.InvalidHashError,
        ):
            return False, False
    if almacenada.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            import bcrypt
            valida = bcrypt.checkpw(password.encode("utf-8"), almacenada.encode("utf-8"))
            return bool(valida), bool(valida)
        except (ImportError, ValueError):
            return False, False
    # Compatibilidad con el SHA-256 simple que utilizaba la versión anterior.
    sha256 = hashlib.sha256(password.strip().encode("utf-8")).hexdigest()
    return hmac.compare_digest(sha256, almacenada), hmac.compare_digest(sha256, almacenada)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def crear_token(usuario: dict[str, Any]) -> str:
    if len(SECRET_KEY) < 32:
        raise RuntimeError("ECORUTA_SECRET_KEY debe tener al menos 32 caracteres.")
    ahora = int(time.time())
    encabezado = {"alg": ALGORITMO, "typ": "JWT"}
    carga = {
        "sub": str(usuario["id"]),
        "rol": str(usuario["rol"]),
        "iat": ahora,
        "exp": ahora + TOKEN_MINUTOS * 60,
    }
    parte1 = _b64url(json.dumps(encabezado, separators=(",", ":")).encode())
    parte2 = _b64url(json.dumps(carga, separators=(",", ":")).encode())
    mensaje = f"{parte1}.{parte2}".encode("ascii")
    firma = hmac.new(SECRET_KEY.encode(), mensaje, hashlib.sha256).digest()
    return f"{parte1}.{parte2}.{_b64url(firma)}"


def _decodificar_token(token: str) -> dict[str, Any]:
    if len(SECRET_KEY) < 32:
        raise ValueError("La clave de firma no está configurada.")
    partes = token.split(".")
    if len(partes) != 3:
        raise ValueError("Token mal formado.")
    parte1, parte2, firma_recibida = partes
    mensaje = f"{parte1}.{parte2}".encode("ascii")
    firma_esperada = _b64url(hmac.new(SECRET_KEY.encode(), mensaje, hashlib.sha256).digest())
    if not hmac.compare_digest(firma_esperada, firma_recibida):
        raise ValueError("Firma inválida.")
    carga = parte2 + "=" * (-len(parte2) % 4)
    datos = json.loads(base64.urlsafe_b64decode(carga.encode("ascii")))
    if int(datos.get("exp", 0)) <= int(time.time()):
        raise ValueError("Token vencido.")
    return datos


def usuario_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(_BEARER),
) -> dict[str, Any]:
    if credenciales is None:
        raise HTTPException(status_code=401, detail="Inicia sesión para continuar.")
    try:
        datos = _decodificar_token(credenciales.credentials)
        return {"id": int(datos["sub"]), "rol": str(datos["rol"])}
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail="Token inválido o vencido.")


def exigir_admin(usuario: dict[str, Any] = Depends(usuario_actual)) -> dict[str, Any]:
    if usuario.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Se requiere rol administrador.")
    return usuario
