"""
Auth propio del marketplace.
Los clientes se registran/loguean aquí (tabla mp_customers),
independiente del sistema admin de elashesbackend.
Flujo de login dual:
  1. Email + contraseña (cuenta marketplace propia).
  2. Email + CI del salón (si marketplace_enabled=True en elashesbackend).
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.config.settings import settings
from app.core.dependencies import get_db
from app.core.rate_limit import rate_limit
from app.domain.entities.customer import Customer
from app.domain.entities.review import Review

_SALON_BACKEND_URL = os.getenv("SALON_BACKEND_URL", "http://127.0.0.1:8000")

router = APIRouter(prefix="/api/v1/auth", tags=["Auth Clientes"])

_ALGO = "HS256"
_bearer = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ── Helpers ───────────────────────────────────────────────────────────────────
# bcrypt directo (passlib 1.7.4 es incompatible con bcrypt >= 4.1)

def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def _verify(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except ValueError:
        return False


def _create_token(customer_id: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.token_expire_minutes)
    return jwt.encode(
        {"sub": str(customer_id), "exp": exp},
        settings.secret_key,
        algorithm=_ALGO,
    )


def _get_by_id(db: Session, customer_id: int) -> Optional[Customer]:
    return db.query(Customer).filter(Customer.id == customer_id).first()


def get_current_customer(
    db: Session = Depends(get_db), token: str = Depends(_bearer)
) -> Customer:
    """Dependencia reutilizable para endpoints que requieren un cliente logueado
    (ej. dejar una reseña). Lanza 401 si el token es inválido o el cliente no existe."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[_ALGO])
        customer_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Token inválido")
    customer = _get_by_id(db, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    if not customer.is_active:
        raise HTTPException(status_code=403, detail="Cuenta desactivada")
    return customer


def _response(customer: Customer) -> dict:
    token = _create_token(customer.id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "id": customer.id,
        "nombre": customer.name,
        "email": customer.email,
        "phone": customer.phone,
        "external_user_id": customer.id,  # alias para compatibilidad con Flutter AuthUser
    }


# ── Schemas ───────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: Optional[str] = None
    country_code: Optional[str] = None


class LoginRequest(BaseModel):
    # Acepta email o nombre de usuario (no se valida formato de email)
    email: str
    password: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register", status_code=201)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    rate_limit(request, "register", max_attempts=5, window_seconds=60)
    # Sin importar mayúsculas/minúsculas — igual que el login, que ya busca
    # con func.lower(). Antes esta comparación era sensible a mayúsculas,
    # así que "Ana@x.com" y "ana@x.com" podían registrarse como dos cuentas
    # distintas y el login quedaba ambiguo sobre cuál resolvía.
    from sqlalchemy import func

    if (
        db.query(Customer)
        .filter(func.lower(Customer.email) == payload.email.strip().lower())
        .first()
    ):
        raise HTTPException(status_code=400, detail="Ya existe una cuenta con ese email")
    customer = Customer(
        name=payload.name,
        phone=payload.phone or "",
        email=payload.email,
        hashed_pw=_hash(payload.password),
        source="app",
        country_code=(payload.country_code or "").strip().upper() or None,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return _response(customer)


@router.post("/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    # Límite por IP — antes no había nada frenando fuerza bruta de contraseña/CI.
    rate_limit(request, "login", max_attempts=5, window_seconds=60)
    # ── 1. Intentar login normal con mp_customers (por email o nombre) ─────────
    from sqlalchemy import func

    identifier = payload.email.strip()
    ident_lower = identifier.lower()
    customer = (
        db.query(Customer).filter(func.lower(Customer.email) == ident_lower).first()
    )
    if not customer:
        customer = (
            db.query(Customer).filter(func.lower(Customer.name) == ident_lower).first()
        )
    if customer:
        if not customer.is_active:
            raise HTTPException(status_code=403, detail="Cuenta desactivada")
        if customer.hashed_pw and _verify(payload.password, customer.hashed_pw):
            return _response(customer)

    # ── 2. Intentar login con CI del salón ────────────────────────────────────
    try:
        r = httpx.post(
            f"{_SALON_BACKEND_URL}/clients/verify-salon-login",
            json={"email": identifier, "ci": payload.password},
            timeout=3.0,
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("valid"):
                if not customer:
                    # El cliente del salón puede no tener email: generar uno interno
                    email = data.get("email") or f"salon.{data['name'].lower().replace(' ', '.')}@elashes.local"
                    # Si ya existe cuenta con ese email (login previo por nombre), reutilizarla
                    customer = (
                        db.query(Customer)
                        .filter(func.lower(Customer.email) == email.lower())
                        .first()
                    )
                if not customer:
                    # Primera vez: auto-crear cuenta marketplace marcada como 'salon'
                    customer = Customer(
                        name=data["name"],
                        phone=data.get("phone") or "",
                        email=email,
                        hashed_pw=_hash(payload.password),
                        source="salon",
                    )
                    db.add(customer)
                    db.commit()
                    db.refresh(customer)
                else:
                    # CI cambió en el salón → actualizar hash almacenado
                    customer.hashed_pw = _hash(payload.password)
                    db.commit()
                return _response(customer)
            if data.get("reason") == "marketplace_not_enabled":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Tu acceso al marketplace no está habilitado. Consulta con el salón.",
                )
    except HTTPException:
        raise
    except Exception:
        pass  # elashesbackend no disponible; continuar con error genérico

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Email o contraseña incorrectos",
    )


@router.get("/me")
def me(customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)):
    reviews_count = db.query(Review).filter(Review.customer_id == customer.id).count()
    return {
        "id": customer.id,
        "nombre": customer.name,
        "email": customer.email,
        "phone": customer.phone,
        "reviews_count": reviews_count,
    }


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None


@router.put("/me")
def update_me(
    payload: UpdateProfileRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    if payload.name is not None and payload.name.strip():
        customer.name = payload.name.strip()
    if payload.phone is not None:
        customer.phone = payload.phone.strip()
    db.commit()
    db.refresh(customer)
    reviews_count = db.query(Review).filter(Review.customer_id == customer.id).count()
    return {
        "id": customer.id,
        "nombre": customer.name,
        "email": customer.email,
        "phone": customer.phone,
        "reviews_count": reviews_count,
    }
