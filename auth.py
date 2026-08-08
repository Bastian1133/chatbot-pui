import os
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from database.supabase_client import get_supabase_client

load_dotenv(Path(__file__).parent / "keys.env")

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise ValueError("Falta JWT_SECRET en el archivo keys.env")

JWT_ALGORITMO = "HS256"
HORAS_EXPIRACION = 8

# Extrae automáticamente el header "Authorization: Bearer <token>"
security = HTTPBearer()


def verificar_password(password_plano: str, password_hash: str) -> bool:
    return bcrypt.checkpw(
        password_plano.encode("utf-8"),
        password_hash.encode("utf-8")
    )

def crear_token(usuario: str) -> str:
    expiracion = datetime.now(timezone.utc) + timedelta(hours=HORAS_EXPIRACION)
    payload = {
        "sub": usuario,          # "subject": a quién pertenece el token
        "exp": expiracion,       # cuándo caduca
        "iat": datetime.now(timezone.utc)  # cuándo se emitió
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITMO)

def autenticar_admin(usuario: str, password: str) -> str:
    # Valida credenciales contra Supabase y devuelve un JWT.
    supabase = get_supabase_client()

    response = supabase.table("administradores") \
        .select("usuario, password_hash") \
        .eq("usuario", usuario) \
        .execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos"
        )

    admin = response.data[0]

    if not verificar_password(password, admin["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos"
        )

    return crear_token(admin["usuario"])

def obtener_admin_actual(credenciales: HTTPAuthorizationCredentials = Depends(security)) -> str:
    # Dependencia para proteger endpoints. Devuelve el usuario del token.
    token = credenciales.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITMO])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesión expiró, vuelve a iniciar sesión"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido"
        )

def cambiar_password(usuario: str, password_actual: str, password_nueva: str) -> None:
    """Verifica la contraseña actual y actualiza con la nueva hasheada."""
    supabase = get_supabase_client()

    # Obtener el hash actual del admin
    response = supabase.table("administradores") \
        .select("password_hash") \
        .eq("usuario", usuario) \
        .execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Administrador no encontrado"
        )

    hash_actual = response.data[0]["password_hash"]

    # Verificar que la contraseña actual es correcta
    if not verificar_password(password_actual, hash_actual):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La contraseña actual es incorrecta"
        )

    # Hashear y guardar la nueva contraseña
    nuevo_hash = bcrypt.hashpw(
        password_nueva.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    supabase.table("administradores") \
        .update({"password_hash": nuevo_hash}) \
        .eq("usuario", usuario) \
        .execute()