from typing import Generator

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.infrastructure.database.session import SessionLocal

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

ADMIN_ROLES = {"SuperAdmin", "Admin"}


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_admin_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Valida el token contra elashesbackend /auth/me y verifica rol admin."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.salon_backend_url}/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo verificar credenciales con el servidor del salón",
        )

    if resp.status_code == 401:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo validar el usuario",
        )

    user_data = resp.json()
    role = user_data.get("role") or {}
    role_name = role.get("name") if isinstance(role, dict) else str(role)

    if role_name not in ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de Administrador o SuperAdministrador",
        )

    return user_data
